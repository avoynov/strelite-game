import { applyDamage } from './damage';
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
  stats: TowerStats;
}

export interface Projectile {
  id: number;
  towerId: number;
  kind: 'direct' | 'shell';
  /** Enemy a direct round follows; 0 for shells. */
  targetId: number;
  damage: number;
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
  | { type: 'fizzle'; projectileId: number; x: number; y: number }
  | { type: 'kill'; enemyId: number; reward: number; x: number; y: number }
  | { type: 'leak'; enemyId: number }
  | { type: 'waveStart'; wave: number }
  | { type: 'waveClear'; wave: number; bonus: number }
  | { type: 'won' }
  | { type: 'lost' };

export type ActionResult = { ok: true } | { ok: false; reason: 'noMoney' | 'notBuildable' | 'occupied' | 'maxLevel' | 'notFound' | 'busy' };

const ARRIVE_EPS = 1e-6;
/** A gun fires once it points within this angle of its aim point. */
const AIM_TOLERANCE = (4 * Math.PI) / 180;
const TWO_PI = Math.PI * 2;

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

export class Game {
  readonly flow: FlowField;
  money = ECONOMY.startMoney;
  lives = ECONOMY.startLives;
  /** Number of the current or last started wave, 0 before the first. */
  wave = 0;
  readonly totalWaves = TOTAL_WAVES;
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
  /** Tower id per cell, 0 where free. */
  private readonly occupied: Int32Array;

  constructor(readonly map: BuiltMap) {
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
    return TOWERS[tower.def].levels[tower.level]!;
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
    this.currentWave = waveSpec(this.wave);
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
        const x = s.x + 0.5;
        const y = s.y + 0.5;
        const next = this.flow.next(s.x, s.y);
        this.enemies.push({
          id: this.nextId++,
          def: g.enemy,
          hp: g.hp,
          maxHp: g.hp,
          reward: g.reward,
          x,
          y,
          px: x,
          py: y,
          heading: next ? Math.atan2(next.y - s.y, next.x - s.x) : 0,
          target: { x: s.x, y: s.y },
          remaining: this.flow.distanceAt(s.x, s.y),
          alive: true,
        });
        st.left--;
        st.timer += g.interval;
      }
    });
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
      if (!this.walk(e, ENEMIES[e.def].speed * dt)) {
        this.leak(e);
        continue;
      }
      const tdist = Math.hypot(e.target.x + 0.5 - e.x, e.target.y + 0.5 - e.y);
      e.remaining = this.flow.distanceAt(e.target.x, e.target.y) + tdist;
    }
  }

  /** Where an enemy will be after `seconds`, if nothing stops it. */
  predict(e: Enemy, seconds: number): { x: number; y: number } {
    const p = { x: e.x, y: e.y, target: e.target };
    this.walk(p, ENEMIES[e.def].speed * seconds);
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
      const def: TowerDef = TOWERS[t.def];
      const lvl = this.levelOf(t);
      const target = this.pickTarget(t, lvl.range, def.minRange ?? 0);
      if (!target) continue;

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
      if (t.cooldown > 0 || Math.abs(angleDelta(t.aim, want)) > AIM_TOLERANCE) continue;

      t.cooldown += lvl.fireInterval;
      const id = this.nextId++;
      this.projectiles.push({
        id,
        towerId: t.id,
        kind: def.projectile,
        targetId: def.projectile === 'direct' ? target.id : 0,
        damage: lvl.damage,
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

  /** "First" targeting: the enemy in range that is closest to the goal. */
  private pickTarget(t: Tower, range: number, minRange: number): Enemy | undefined {
    let best: Enemy | undefined;
    for (const e of this.enemies) {
      if (!e.alive) continue;
      const d = Math.hypot(e.x - t.x, e.y - t.y);
      if (d > range || d < minRange) continue;
      if (!best || e.remaining < best.remaining) best = e;
    }
    return best;
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
        if (tower) tower.stats.wasted += this.damageEnemy(target, p.damage, tower);
      } else {
        this.events.push({ type: 'burst', x: p.tx, y: p.ty, radius: p.splash });
        let hitAny = false;
        let wasted = 0;
        for (const e of this.enemies) {
          if (!e.alive || Math.hypot(e.x - p.tx, e.y - p.ty) > p.splash + ENEMIES[e.def].radius) continue;
          hitAny = true;
          wasted += this.damageEnemy(e, p.damage, tower);
        }
        // Overkill on a blast counts per target; a shell that hits nothing is wasted whole.
        if (tower) tower.stats.wasted += hitAny ? wasted : p.damage;
      }
    }
    this.projectiles = keep;
  }

  /** Apply a hit; returns the overkill (damage beyond the target's health). */
  private damageEnemy(target: Enemy, damage: number, tower: Tower | undefined): number {
    const r = applyDamage(target.hp, damage);
    target.hp = r.hpAfter;
    if (tower) tower.stats.dealt += r.dealt;
    this.events.push({ type: 'hit', enemyId: target.id, dealt: r.dealt, overkill: r.overkill, x: target.x, y: target.y });
    if (target.hp <= 0) {
      target.alive = false;
      this.money += target.reward;
      if (tower) tower.stats.kills++;
      this.events.push({ type: 'kill', enemyId: target.id, reward: target.reward, x: target.x, y: target.y });
    }
    return r.overkill;
  }

  private checkWaveEnd(): void {
    if (this.phase !== 'wave' || this.spawnLeft > 0) return;
    if (this.enemies.length > 0 || this.projectiles.length > 0) return;
    const bonus = this.currentWave?.clearBonus ?? 0;
    this.money += bonus;
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
