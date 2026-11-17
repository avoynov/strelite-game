import { afterArmor, applyDamage } from './damage';
import type { Upgrades } from './research';
import { ECONOMY, ENEMIES, TOWERS, type EnemyId, type TowerDef, type TowerId, type TowerLevel } from './content';
import { FlowField } from './flowField';
import type { Cell } from './grid';
import type { BuiltMap } from './maps';
import { TOTAL_WAVES, waveSpec, type WaveSpec } from './waves';

export type Phase = 'build' | 'wave' | 'won' | 'lost';

export interface Enemy {
  id: number;
  def: EnemyId;
  hp: number;
  maxHp: number;
  reward: number;
  x: number;
  y: number;
  /** Position at the start of the last step, for render interpolation. */
  px: number;
  py: number;
  /** Direction of travel, radians: atan2(dy, dx) in grid cells. */
  heading: number;
  /** Cell the enemy is currently walking towards. */
  target: Cell;
  /** Remaining path length to the goal in cells; lower means further along. */
  remaining: number;
  alive: boolean;
  /** Flying: goes straight to the goal and only some guns can hit it. */
  air: boolean;
  /** Phase of the speed surges of a swerving unit. */
  phase: number;
}

export interface TowerStats {
  dealt: number;
  wasted: number;
  kills: number;
  invested: number;
}

export interface Tower {
  id: number;
  def: TowerId;
  /** 0-based index into the def's levels. */
  level: number;
  /** Top-left cell of the footprint. */
  cx: number;
  cy: number;
  /** Footprint side in tiles. */
  size: number;
  /** Ground centre in grid cells: the point the gun turns about. */
  x: number;
  y: number;
  cooldown: number;
  /** Direction the gun points, radians: atan2(dy, dx) in grid cells. */
  aim: number;
  /** Enemy the gun is on; kept until it dies or leaves range. 0 for none. */
  targetId: number;
  /** Flame: seconds spent on the current target (the flame heats up). */
  heat: number;
  /** Flame: true while it is burning a target this step. */
  firing: boolean;
  stats: TowerStats;
}

export interface Projectile {
  id: number;
  towerId: number;
  kind: 'direct' | 'shell';
  /** Enemy a direct round follows; 0 for shells. */
  targetId: number;
  damage: number;
  /** Fraction of armour the round ignores. */
  pierce: number;
  /** More enemies a direct round goes on into after its target. */
  passThrough: number;
  speed: number;
  splash: number;
  /** Where it was fired from and where it is going (shells: fixed burst point). */
  ox: number;
  oy: number;
  tx: number;
  ty: number;
  x: number;
  y: number;
  px: number;
  py: number;
  /** Flight progress 0..1, and its value at the start of the last step. */
  t: number;
  pt: number;
}

export type GameEvent =
  | { type: 'shot'; towerId: number; projectileId: number }
  | { type: 'hit'; enemyId: number; dealt: number; overkill: number; x: number; y: number }
  | { type: 'burst'; x: number; y: number; radius: number }
  /** A direct round struck its target. */
  | { type: 'impact'; x: number; y: number }
  | { type: 'fizzle'; projectileId: number; x: number; y: number }
  /** A railgun fired: everything on the segment was hit. */
  | { type: 'rail'; towerId: number; x1: number; y1: number; x2: number; y2: number }
  | { type: 'kill'; enemyId: number; reward: number; x: number; y: number }
  | { type: 'leak'; enemyId: number }
  | { type: 'waveStart'; wave: number }
  | { type: 'waveClear'; wave: number; bonus: number }
  | { type: 'won' }
  | { type: 'lost' };

export type ActionResult = { ok: true } | { ok: false; reason: 'noMoney' | 'notBuildable' | 'occupied' | 'maxLevel' | 'notFound' | 'busy' | 'locked' };

export interface GameOptions {
  /** Map level, 1-based: decides which guns can be built and which enemies attack. */
  level?: number;
  /** Wave plan to use instead of the standard one (for tests and scenarios). */
  waves?: (n: number, level: number) => WaveSpec;
  /** Finished research: which guns can be built, and the boosts. Without it every gun is open and nothing is boosted. */
  upgrades?: Upgrades;
}

const ARRIVE_EPS = 1e-6;
/** A gun fires once it points within this angle of its aim point. */
const AIM_TOLERANCE = (4 * Math.PI) / 180;
const TWO_PI = Math.PI * 2;
/** A flame counts as this many hits a second against armour. */
const BEAM_HITS_PER_SECOND = 2;
/** Half-width of a railgun slug's path, in tiles (added to each enemy's radius). */
const RAIL_HALF_WIDTH = 0.35;
/** A round passing through looks for its next victim this far from the impact. */
const PASS_THROUGH_REACH = 1.2;

/** Seconds a swerving unit holds one speed before it jerks to another. */
const SWERVE_SECONDS = 1.4;

/** Deterministic pseudo-random number in [0, 1) from an integer. */
function hash01(n: number): number {
  let h = n | 0;
  h = Math.imul(h ^ (h >>> 16), 0x45d9f3b);
  h = Math.imul(h ^ (h >>> 16), 0x45d9f3b);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

/** Smallest signed difference b - a, in (-π, π]. */
export function angleDelta(a: number, b: number): number {
  let d = (b - a) % TWO_PI;
  if (d > Math.PI) d -= TWO_PI;
  else if (d <= -Math.PI) d += TWO_PI;
  return d;
}

interface SpawnState {
  left: number;
  timer: number;
}

/** Gold at the start of a map level. */
export function startMoney(level: number): number {
  return ECONOMY.startMoney + ECONOMY.startMoneyPerLevel * (Math.min(level, 8) - 1);
}

export class Game {
  readonly flow: FlowField;
  money: number;
  lives = ECONOMY.startLives;
  /** Number of the current or last started wave, 0 before the first. */
  wave = 0;
  readonly totalWaves = TOTAL_WAVES;
  readonly level: number;
  /** Gold taken in this battle (kills and wave bonuses), whatever was spent. */
  goldEarned = 0;
  phase: Phase = 'build';
  time = 0;

  enemies: Enemy[] = [];
  towers: Tower[] = [];
  projectiles: Projectile[] = [];

  private nextId = 1;
  private currentWave: WaveSpec | null = null;
  private spawnState: SpawnState[] = [];
  private spawned = 0;
  private events: GameEvent[] = [];
  /** Units dropped during this step (by destroyed APCs); join after it. */
  private dropped: Enemy[] = [];
  private readonly waves: (n: number, level: number) => WaveSpec;
  private readonly upgrades: Upgrades | null;
  /** Gun stats with research applied, per gun and level. */
  private readonly levelCache = new Map<string, TowerLevel>();
  private readonly defCache = new Map<TowerId, TowerDef>();
  /** Tower id per cell, 0 where free. */
  private readonly occupied: Int32Array;

  constructor(
    readonly map: BuiltMap,
    opts: GameOptions = {},
  ) {
    this.level = Math.max(1, Math.floor(opts.level ?? 1));
    this.upgrades = opts.upgrades ?? null;
    this.money = startMoney(this.level) + (this.upgrades?.startGold ?? 0);
    this.lives += this.upgrades?.lives ?? 0;
    this.waves = opts.waves ?? waveSpec;
    this.flow = new FlowField(map.grid, map.goals, (x, y) => map.grid.get(x, y) === 'path');
    this.occupied = new Int32Array(map.grid.cols * map.grid.rows);
  }

  // ---- queries -------------------------------------------------------------

  /** The tower whose footprint covers this cell. */
  towerAt(cx: number, cy: number): Tower | undefined {
    if (!this.map.grid.inBounds(cx, cy)) return undefined;
    const id = this.occupied[this.map.grid.index(cx, cy)];
    return id ? this.towerById(id) : undefined;
  }

  towerById(id: number): Tower | undefined {
    return this.towers.find((t) => t.id === id);
  }

  levelOf(tower: Tower): TowerLevel {
    return this.levelStats(tower.def, tower.level);
  }

  /** A gun level's numbers with research applied (level is 0-based). */
  levelStats(def: TowerId, level: number): TowerLevel {
    const key = `${def}:${level}`;
    let l = this.levelCache.get(key);
    if (!l) {
      const base: TowerLevel = TOWERS[def].levels[level]!;
      const m = this.upgrades?.gun[def];
      l = m
        ? {
            ...base,
            damage: Math.round(base.damage * m.damage * 10) / 10,
            fireInterval: Math.round(base.fireInterval * m.reload * 1000) / 1000,
            range: base.range + m.range,
            ...(base.splash ? { splash: Math.round((base.splash + m.splash) * 100) / 100 } : {}),
          }
        : base;
      this.levelCache.set(key, l);
    }
    return l;
  }

  /** A gun's definition with research applied (armour pierce, pass-through, flame heat-up). */
  defOf(id: TowerId): TowerDef {
    let d = this.defCache.get(id);
    if (!d) {
      const base: TowerDef = TOWERS[id];
      const m = this.upgrades?.gun[id];
      d = m
        ? {
            ...base,
            pierce: Math.min(1, base.pierce + m.pierce),
            ...(base.passThrough !== undefined || m.passThrough ? { passThrough: (base.passThrough ?? 0) + m.passThrough } : {}),
            ...(base.rampTime !== undefined ? { rampTime: base.rampTime * m.rampTime } : {}),
          }
        : base;
      this.defCache.set(id, d);
    }
    return d;
  }

  /** Cost of the next level, or null at max level. */
  upgradeCost(tower: Tower): number | null {
    return TOWERS[tower.def].levels[tower.level + 1]?.cost ?? null;
  }

  sellValue(tower: Tower): number {
    return Math.floor(tower.stats.invested * ECONOMY.sellRefund);
  }

  /** Why a gun cannot stand with its footprint's top-left cell at (cx, cy), or null when it can. */
  placementError(def: TowerId, cx: number, cy: number): 'notBuildable' | 'occupied' | null {
    const { grid } = this.map;
    const size = TOWERS[def].size;
    let occupied = false;
    for (let y = cy; y < cy + size; y++) {
      for (let x = cx; x < cx + size; x++) {
        if (grid.get(x, y) !== 'build') return 'notBuildable';
        if (this.occupied[grid.index(x, y)]) occupied = true;
      }
    }
    return occupied ? 'occupied' : null;
  }

  /** Whether research has opened the gun (every gun is open when the game has no research). */
  isUnlocked(def: TowerId): boolean {
    return this.upgrades ? this.upgrades.guns.includes(def) : true;
  }

  canBuildAt(def: TowerId, cx: number, cy: number): boolean {
    return this.placementError(def, cx, cy) === null;
  }

  /** Enemies still to come in the running wave. */
  get spawnLeft(): number {
    return this.spawnState.reduce((s, g) => s + g.left, 0);
  }

  drainEvents(): GameEvent[] {
    const e = this.events;
    this.events = [];
    return e;
  }

  // ---- player actions ------------------------------------------------------

  /** Build a gun with its footprint's top-left cell at (cx, cy). */
  build(def: TowerId, cx: number, cy: number): ActionResult {
    if (this.phase === 'won' || this.phase === 'lost') return { ok: false, reason: 'busy' };
    if (!this.isUnlocked(def)) return { ok: false, reason: 'locked' };
    const err = this.placementError(def, cx, cy);
    if (err) return { ok: false, reason: err };
    const d = TOWERS[def];
    const cost = d.levels[0].cost;
    if (this.money < cost) return { ok: false, reason: 'noMoney' };
    this.money -= cost;
    const tower: Tower = {
      id: this.nextId++,
      def,
      level: 0,
      cx,
      cy,
      size: d.size,
      x: cx + d.size / 2,
      y: cy + d.size / 2,
      cooldown: 0,
      aim: this.initialAim(cx + d.size / 2, cy + d.size / 2),
      targetId: 0,
      heat: 0,
      firing: false,
      stats: { dealt: 0, wasted: 0, kills: 0, invested: cost },
    };
    this.towers.push(tower);
    this.markFootprint(tower, tower.id);
    return { ok: true };
  }

  upgrade(towerId: number): ActionResult {
    const t = this.towerById(towerId);
    if (!t) return { ok: false, reason: 'notFound' };
    const cost = this.upgradeCost(t);
    if (cost === null) return { ok: false, reason: 'maxLevel' };
    if (this.money < cost) return { ok: false, reason: 'noMoney' };
    this.money -= cost;
    t.level++;
    t.stats.invested += cost;
    return { ok: true };
  }

  sell(towerId: number): ActionResult {
    const t = this.towerById(towerId);
    if (!t) return { ok: false, reason: 'notFound' };
    this.money += this.sellValue(t);
    this.markFootprint(t, 0);
    this.towers = this.towers.filter((o) => o !== t);
    return { ok: true };
  }

  startWave(): ActionResult {
    if (this.phase !== 'build' || this.wave >= this.totalWaves) return { ok: false, reason: 'busy' };
    this.wave++;
    this.currentWave = this.waves(this.wave, this.level);
    this.spawnState = this.currentWave.groups.map((g) => ({ left: g.count, timer: g.delay }));
    this.phase = 'wave';
    this.events.push({ type: 'waveStart', wave: this.wave });
    return { ok: true };
  }

  // ---- simulation ----------------------------------------------------------

  /** Advance the world by one fixed step of `dt` seconds. */
  step(dt: number): void {
    if (this.phase === 'won' || this.phase === 'lost') return;
    this.time += dt;
    for (const e of this.enemies) {
      e.px = e.x;
      e.py = e.y;
    }
    for (const p of this.projectiles) {
      p.px = p.x;
      p.py = p.y;
      p.pt = p.t;
    }
    this.spawn(dt);
    this.moveEnemies(dt);
    this.fireTowers(dt);
    this.moveProjectiles(dt);
    this.enemies = this.enemies.filter((e) => e.alive);
    if (this.dropped.length) {
      this.enemies.push(...this.dropped);
      this.dropped = [];
    }
    this.checkWaveEnd();
  }

  private markFootprint(t: Tower, value: number): void {
    for (let y = t.cy; y < t.cy + t.size; y++) {
      for (let x = t.cx; x < t.cx + t.size; x++) this.occupied[this.map.grid.index(x, y)] = value;
    }
  }

  /** A new gun starts pointing at the nearest stretch of road. */
  private initialAim(x: number, y: number): number {
    const { grid } = this.map;
    let best = Infinity;
    let aim = -Math.PI / 2;
    for (let cy = 0; cy < grid.rows; cy++) {
      for (let cx = 0; cx < grid.cols; cx++) {
        if (grid.get(cx, cy) !== 'path') continue;
        const d = Math.hypot(cx + 0.5 - x, cy + 0.5 - y);
        if (d < best) {
          best = d;
          aim = Math.atan2(cy + 0.5 - y, cx + 0.5 - x);
        }
      }
    }
    return aim;
  }

  private spawn(dt: number): void {
    const w = this.currentWave;
    if (!w) return;
    w.groups.forEach((g, i) => {
      const st = this.spawnState[i]!;
      if (st.left <= 0) return;
      st.timer -= dt;
      while (st.left > 0 && st.timer <= 0) {
        const s = this.map.spawns[this.spawned++ % this.map.spawns.length]!;
        this.enemies.push(this.makeEnemy(g.enemy, g.hp, g.reward, s.x + 0.5, s.y + 0.5, { x: s.x, y: s.y }));
        st.left--;
        st.timer += g.interval;
      }
    });
  }

  private makeEnemy(def: EnemyId, hp: number, reward: number, x: number, y: number, target: Cell): Enemy {
    const id = this.nextId++;
    const air = 'air' in ENEMIES[def] && ENEMIES[def].air === true;
    const e: Enemy = {
      id,
      def,
      hp,
      maxHp: hp,
      reward,
      x,
      y,
      px: x,
      py: y,
      heading: 0,
      target,
      remaining: 0,
      alive: true,
      air,
      // Spread the surges of swerving riders so they do not move in step.
      phase: (id * 2.399963) % TWO_PI,
    };
    if (air) {
      // Flyers ignore the road and head straight for the goal.
      e.target = this.map.goals[0] ?? target;
      e.heading = Math.atan2(e.target.y + 0.5 - y, e.target.x + 0.5 - x);
      e.remaining = Math.hypot(e.target.x + 0.5 - x, e.target.y + 0.5 - y);
    } else {
      const next = this.flow.next(target.x, target.y);
      e.heading = next ? Math.atan2(next.y - target.y, next.x - target.x) : 0;
      e.remaining = this.flow.distanceAt(target.x, target.y) + Math.hypot(target.x + 0.5 - x, target.y + 0.5 - y);
    }
    return e;
  }

  /**
   * Speed right now. Swerving units jerk between bursts and brakes: every
   * SWERVE_SECONDS each picks a new speed between (1 − swerve) and (1 + swerve)
   * times its nominal speed. It averages out, so they arrive on time, but a gun
   * that leads its target lands its round where the rider would have been.
   */
  speedOf(e: Enemy): number {
    const d = ENEMIES[e.def];
    const swerve = 'swerve' in d ? d.swerve : 0;
    if (!swerve) return d.speed;
    const seg = Math.floor((this.time + e.phase) / SWERVE_SECONDS);
    return d.speed * (1 + swerve * (2 * hash01(e.id * 7919 + seg * 104729) - 1));
  }

  /** Move a flyer straight towards its goal; false once it arrives. */
  private fly(e: Enemy, budget: number): boolean {
    const tx = e.target.x + 0.5;
    const ty = e.target.y + 0.5;
    const d = Math.hypot(tx - e.x, ty - e.y);
    if (d <= budget) return false;
    e.x += ((tx - e.x) / d) * budget;
    e.y += ((ty - e.y) / d) * budget;
    e.remaining = d - budget;
    return true;
  }

  /**
   * Walk a point along the flow field for `budget` cells of distance.
   * Returns false when it runs off the end of the road (reached the goal).
   */
  private walk(pos: { x: number; y: number; target: Cell; heading?: number }, budget: number): boolean {
    while (budget > 0) {
      const tx = pos.target.x + 0.5;
      const ty = pos.target.y + 0.5;
      const dx = tx - pos.x;
      const dy = ty - pos.y;
      const d = Math.hypot(dx, dy);
      if (d > ARRIVE_EPS) {
        const m = Math.min(d, budget);
        pos.x += (dx / d) * m;
        pos.y += (dy / d) * m;
        if (pos.heading !== undefined) pos.heading = Math.atan2(dy, dx);
        budget -= m;
        if (m < d) break;
      }
      const next = this.flow.next(pos.target.x, pos.target.y);
      if (!next) return false;
      pos.target = next;
    }
    return true;
  }

  private moveEnemies(dt: number): void {
    for (const e of this.enemies) {
      if (!e.alive) continue;
      if (e.air) {
        if (!this.fly(e, this.speedOf(e) * dt)) this.leak(e);
        continue;
      }
      if (!this.walk(e, this.speedOf(e) * dt)) {
        this.leak(e);
        continue;
      }
      const tdist = Math.hypot(e.target.x + 0.5 - e.x, e.target.y + 0.5 - e.y);
      e.remaining = this.flow.distanceAt(e.target.x, e.target.y) + tdist;
    }
  }

  /**
   * Where an enemy will be after `seconds` at its nominal speed. Guns lead their
   * targets with this, so units that surge and brake make them miss.
   */
  predict(e: Enemy, seconds: number): { x: number; y: number } {
    const budget = ENEMIES[e.def].speed * seconds;
    if (e.air) {
      const tx = e.target.x + 0.5;
      const ty = e.target.y + 0.5;
      const d = Math.hypot(tx - e.x, ty - e.y);
      const k = d > 0 ? Math.min(1, budget / d) : 0;
      return { x: e.x + (tx - e.x) * k, y: e.y + (ty - e.y) * k };
    }
    const p = { x: e.x, y: e.y, target: e.target };
    this.walk(p, budget);
    return p;
  }

  private leak(e: Enemy): void {
    e.alive = false;
    this.lives = Math.max(0, this.lives - ENEMIES[e.def].leakDamage);
    this.events.push({ type: 'leak', enemyId: e.id });
    if (this.lives <= 0) {
      this.phase = 'lost';
      this.events.push({ type: 'lost' });
    }
  }

  private fireTowers(dt: number): void {
    for (const t of this.towers) {
      t.cooldown = Math.max(0, t.cooldown - dt);
      t.firing = false;
      const def: TowerDef = this.defOf(t.def);
      const lvl = this.levelOf(t);
      const target = this.pickTarget(t);
      if (!target) {
        t.targetId = 0;
        t.heat = 0;
        continue;
      }
      if (target.id !== t.targetId) {
        t.targetId = target.id;
        t.heat = 0;
      }

      // Aim point: the target itself, or for a lobbed shell the place it will have reached.
      let ax = target.x;
      let ay = target.y;
      if (def.projectile === 'shell') {
        for (let i = 0; i < 2; i++) {
          const p = this.predict(target, Math.hypot(ax - t.x, ay - t.y) / lvl.projectileSpeed);
          ax = p.x;
          ay = p.y;
        }
      }

      const want = Math.atan2(ay - t.y, ax - t.x);
      const off = angleDelta(t.aim, want);
      const turn = def.turnRate * dt;
      t.aim = Math.abs(off) <= turn ? want : t.aim + Math.sign(off) * turn;
      const aimed = Math.abs(angleDelta(t.aim, want)) <= AIM_TOLERANCE;

      if (def.projectile === 'beam') {
        if (aimed) this.burn(t, def, lvl, target, dt);
        continue;
      }
      if (t.cooldown > 0 || !aimed) continue;
      t.cooldown += lvl.fireInterval;

      if (def.projectile === 'rail') {
        this.fireRail(t, def, lvl);
        continue;
      }
      const id = this.nextId++;
      this.projectiles.push({
        id,
        towerId: t.id,
        kind: def.projectile,
        targetId: def.projectile === 'direct' ? target.id : 0,
        damage: lvl.damage,
        pierce: def.pierce,
        passThrough: def.passThrough ?? 0,
        speed: lvl.projectileSpeed,
        splash: lvl.splash ?? 0,
        ox: t.x,
        oy: t.y,
        tx: ax,
        ty: ay,
        x: t.x,
        y: t.y,
        px: t.x,
        py: t.y,
        t: 0,
        pt: 0,
      });
      this.events.push({ type: 'shot', towerId: t.id, projectileId: id });
    }
  }

  /** Flame: damage per second ramps from `rampFrom` to full while it stays on one target. */
  private burn(t: Tower, def: TowerDef, lvl: TowerLevel, target: Enemy, dt: number): void {
    const full = lvl.damage;
    // The starting heat grows with the level just like the top heat.
    const from = (def.rampFrom ?? full) * (full / def.levels[0]!.damage);
    const k = def.rampTime ? Math.min(1, t.heat / def.rampTime) : 1;
    const dps = from + (full - from) * k;
    t.heat += dt;
    t.firing = true;
    const per = dps / BEAM_HITS_PER_SECOND;
    const through = afterArmor(per, ENEMIES[target.def].armor, def.pierce) * BEAM_HITS_PER_SECOND;
    t.stats.wasted += (dps - through) * dt;
    t.stats.wasted += this.damageEnemy(target, through * dt, t, 0, 0, false);
  }

  /** Railgun: everything on the ground along the line, out to full range, takes the whole hit. */
  private fireRail(t: Tower, def: TowerDef, lvl: TowerLevel): void {
    const x2 = t.x + Math.cos(t.aim) * lvl.range;
    const y2 = t.y + Math.sin(t.aim) * lvl.range;
    this.events.push({ type: 'rail', towerId: t.id, x1: t.x, y1: t.y, x2, y2 });
    let hitAny = false;
    for (const e of this.onLine(t.x, t.y, x2, y2)) {
      hitAny = true;
      t.stats.wasted += this.damageEnemy(e, lvl.damage, t, ENEMIES[e.def].armor, def.pierce);
    }
    if (!hitAny) t.stats.wasted += lvl.damage;
  }

  /** Live ground enemies whose body touches the segment (x1, y1)–(x2, y2). */
  private onLine(x1: number, y1: number, x2: number, y2: number): Enemy[] {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const len2 = dx * dx + dy * dy || 1;
    return this.enemies.filter((e) => {
      if (!e.alive || e.air) return false;
      const k = Math.max(0, Math.min(1, ((e.x - x1) * dx + (e.y - y1) * dy) / len2));
      return Math.hypot(e.x - (x1 + dx * k), e.y - (y1 + dy * k)) <= RAIL_HALF_WIDTH + ENEMIES[e.def].radius;
    });
  }

  /** Enemies this gun could shoot at now. */
  private candidates(t: Tower): Enemy[] {
    const def: TowerDef = this.defOf(t.def);
    const range = this.levelOf(t).range;
    const min = def.minRange ?? 0;
    return this.enemies.filter((e) => {
      if (!e.alive || (e.air && !def.hitsAir)) return false;
      const d = Math.hypot(e.x - t.x, e.y - t.y);
      return d <= range && d >= min;
    });
  }

  /**
   * The gun keeps its target until it dies or leaves range; then it picks by
   * its own fixed priority, and takes the first on the path when nothing
   * matches that priority.
   */
  private pickTarget(t: Tower): Enemy | undefined {
    const list = this.candidates(t);
    if (!list.length) return undefined;
    const kept = t.targetId ? list.find((e) => e.id === t.targetId) : undefined;
    if (kept) return kept;
    const def: TowerDef = this.defOf(t.def);
    const first = (es: Enemy[]) => es.reduce<Enemy | undefined>((b, e) => (!b || e.remaining < b.remaining ? e : b), undefined);
    /** Highest score wins; ties go to the one closest to the goal. */
    const best = (score: (e: Enemy) => number) => {
      let pick: Enemy | undefined;
      let top = -Infinity;
      for (const e of list) {
        const s = score(e);
        if (s > top || (s === top && pick && e.remaining < pick.remaining)) {
          top = s;
          pick = e;
        }
      }
      return pick;
    };
    switch (def.targeting) {
      case 'airFast': {
        const air = list.filter((e) => e.air);
        if (air.length) return first(air);
        return best((e) => ENEMIES[e.def].speed);
      }
      case 'armored': {
        const max = def.maxArmor ?? Infinity;
        const fit = list.filter((e) => ENEMIES[e.def].armor > 0 && ENEMIES[e.def].armor <= max);
        if (!fit.length) return first(list);
        const top = Math.max(...fit.map((e) => ENEMIES[e.def].armor));
        return first(fit.filter((e) => ENEMIES[e.def].armor === top));
      }
      case 'crowd': {
        const r = this.levelOf(t).splash ?? 0;
        return best((e) => list.filter((o) => Math.hypot(o.x - e.x, o.y - e.y) <= r + ENEMIES[o.def].radius).length);
      }
      case 'strongest':
        return best((e) => e.hp);
      case 'line': {
        const range = this.levelOf(t).range;
        return best((e) => {
          const a = Math.atan2(e.y - t.y, e.x - t.x);
          return this.onLine(t.x, t.y, t.x + Math.cos(a) * range, t.y + Math.sin(a) * range).reduce((s, o) => s + o.hp, 0);
        });
      }
      default:
        return first(list);
    }
  }

  private moveProjectiles(dt: number): void {
    const keep: Projectile[] = [];
    for (const p of this.projectiles) {
      const tower = this.towerById(p.towerId);
      if (p.kind === 'direct') {
        const target = this.enemies.find((e) => e.id === p.targetId && e.alive);
        if (!target) {
          // Target died or escaped before impact: the whole shot is wasted.
          if (tower) tower.stats.wasted += p.damage;
          this.events.push({ type: 'fizzle', projectileId: p.id, x: p.x, y: p.y });
          continue;
        }
        p.tx = target.x;
        p.ty = target.y;
      }
      const dx = p.tx - p.x;
      const dy = p.ty - p.y;
      const d = Math.hypot(dx, dy);
      const m = p.speed * dt;
      if (m < d) {
        p.x += (dx / d) * m;
        p.y += (dy / d) * m;
        const total = Math.hypot(p.x - p.ox, p.y - p.oy) + (d - m);
        p.t = Math.max(p.t, total > 0 ? 1 - (d - m) / total : 1);
        keep.push(p);
        continue;
      }
      if (p.kind === 'direct') {
        const target = this.enemies.find((e) => e.id === p.targetId)!;
        this.events.push({ type: 'impact', x: target.x, y: target.y });
        let wasted = this.damageEnemy(target, p.damage, tower, ENEMIES[target.def].armor, p.pierce);
        // A bolt that goes through carries on into the nearest others behind its target.
        const hit = new Set([target.id]);
        for (let i = 0; i < p.passThrough; i++) {
          const next = this.enemies
            .filter((e) => e.alive && !hit.has(e.id) && e.air === target.air && Math.hypot(e.x - target.x, e.y - target.y) <= PASS_THROUGH_REACH + ENEMIES[e.def].radius)
            .sort((a, b) => Math.hypot(a.x - target.x, a.y - target.y) - Math.hypot(b.x - target.x, b.y - target.y))[0];
          if (!next) break;
          hit.add(next.id);
          wasted += this.damageEnemy(next, p.damage, tower, ENEMIES[next.def].armor, p.pierce);
        }
        if (tower) tower.stats.wasted += wasted;
      } else {
        this.events.push({ type: 'burst', x: p.tx, y: p.ty, radius: p.splash });
        let hitAny = false;
        let wasted = 0;
        // Shells burst on the ground: flyers are out of reach.
        for (const e of this.enemies) {
          if (!e.alive || e.air || Math.hypot(e.x - p.tx, e.y - p.ty) > p.splash + ENEMIES[e.def].radius) continue;
          hitAny = true;
          wasted += this.damageEnemy(e, p.damage, tower, ENEMIES[e.def].armor, p.pierce);
        }
        // Overkill and armour on a blast count per target; a shell that hits nothing is wasted whole.
        if (tower) tower.stats.wasted += hitAny ? wasted : p.damage;
      }
    }
    this.projectiles = keep;
  }

  /**
   * Apply a hit through armour; returns the damage lost to overkill and armour.
   * `announce` is false for the many small ticks of a flame.
   */
  private damageEnemy(target: Enemy, damage: number, tower: Tower | undefined, armor = 0, pierce = 0, announce = true): number {
    const r = applyDamage(target.hp, damage, armor, pierce);
    target.hp = r.hpAfter;
    if (tower) tower.stats.dealt += r.dealt;
    if (announce) this.events.push({ type: 'hit', enemyId: target.id, dealt: r.dealt, overkill: r.overkill, x: target.x, y: target.y });
    if (target.hp <= 0) {
      target.alive = false;
      this.money += target.reward;
      this.goldEarned += target.reward;
      if (tower) tower.stats.kills++;
      this.events.push({ type: 'kill', enemyId: target.id, reward: target.reward, x: target.x, y: target.y });
      this.dropUnits(target);
    }
    return r.overkill + r.blocked;
  }

  /** A destroyed APC unloads its squad where it stopped, at the same strength as its wave. */
  private dropUnits(from: Enemy): void {
    const def = ENEMIES[from.def];
    if (!('dropsOnDeath' in def)) return;
    const drop = def.dropsOnDeath;
    const kind = drop.enemy as EnemyId;
    const k = from.maxHp / def.baseHp;
    const hp = Math.max(1, Math.round(ENEMIES[kind].baseHp * k));
    for (let i = 0; i < drop.count; i++) {
      // A short file behind the wreck, all walking on towards the same cell.
      const back = 0.18 * i;
      const x = from.x - Math.cos(from.heading) * back;
      const y = from.y - Math.sin(from.heading) * back;
      const e = this.makeEnemy(kind, hp, ENEMIES[kind].baseReward, x, y, from.target);
      this.dropped.push(e);
    }
  }

  private checkWaveEnd(): void {
    if (this.phase !== 'wave' || this.spawnLeft > 0) return;
    if (this.enemies.length > 0 || this.projectiles.length > 0) return;
    const bonus = this.currentWave?.clearBonus ?? 0;
    this.money += bonus;
    this.goldEarned += bonus;
    this.currentWave = null;
    this.spawnState = [];
    this.events.push({ type: 'waveClear', wave: this.wave, bonus });
    if (this.wave >= this.totalWaves) {
      this.phase = 'won';
      this.events.push({ type: 'won' });
    } else {
      this.phase = 'build';
    }
  }
}
