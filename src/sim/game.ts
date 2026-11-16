import { applyDamage } from './damage';
import { ECONOMY, ENEMIES, TOWERS, type EnemyId, type TowerId, type TowerLevel } from './content';
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
  cx: number;
  cy: number;
  cooldown: number;
  /** Angle the gun faces, radians; render only. */
  aim: number;
  stats: TowerStats;
}

export interface Projectile {
  id: number;
  towerId: number;
  targetId: number;
  damage: number;
  speed: number;
  x: number;
  y: number;
  px: number;
  py: number;
}

export type GameEvent =
  | { type: 'shot'; towerId: number }
  | { type: 'hit'; enemyId: number; dealt: number; overkill: number; x: number; y: number }
  | { type: 'fizzle'; projectileId: number; x: number; y: number }
  | { type: 'kill'; enemyId: number; reward: number; x: number; y: number }
  | { type: 'leak'; enemyId: number }
  | { type: 'waveStart'; wave: number }
  | { type: 'waveClear'; wave: number; bonus: number }
  | { type: 'won' }
  | { type: 'lost' };

export type ActionResult = { ok: true } | { ok: false; reason: 'noMoney' | 'notBuildable' | 'occupied' | 'maxLevel' | 'notFound' | 'busy' };

const ARRIVE_EPS = 1e-6;

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
  private spawnLeft = 0;
  private spawnTimer = 0;
  private currentWave: WaveSpec | null = null;
  private events: GameEvent[] = [];

  constructor(readonly map: BuiltMap) {
    this.flow = new FlowField(map.grid, map.goals, (x, y) => map.grid.get(x, y) === 'path');
  }

  // ---- queries -------------------------------------------------------------

  towerAt(cx: number, cy: number): Tower | undefined {
    return this.towers.find((t) => t.cx === cx && t.cy === cy);
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

  canBuildAt(cx: number, cy: number): boolean {
    return this.map.grid.get(cx, cy) === 'build' && !this.towerAt(cx, cy);
  }

  drainEvents(): GameEvent[] {
    const e = this.events;
    this.events = [];
    return e;
  }

  // ---- player actions ------------------------------------------------------

  build(def: TowerId, cx: number, cy: number): ActionResult {
    if (this.phase === 'won' || this.phase === 'lost') return { ok: false, reason: 'busy' };
    if (this.map.grid.get(cx, cy) !== 'build') return { ok: false, reason: 'notBuildable' };
    if (this.towerAt(cx, cy)) return { ok: false, reason: 'occupied' };
    const cost = TOWERS[def].levels[0].cost;
    if (this.money < cost) return { ok: false, reason: 'noMoney' };
    this.money -= cost;
    this.towers.push({
      id: this.nextId++,
      def,
      level: 0,
      cx,
      cy,
      cooldown: 0,
      aim: -Math.PI / 2,
      stats: { dealt: 0, wasted: 0, kills: 0, invested: cost },
    });
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
    this.towers = this.towers.filter((o) => o !== t);
    return { ok: true };
  }

  startWave(): ActionResult {
    if (this.phase !== 'build' || this.wave >= this.totalWaves) return { ok: false, reason: 'busy' };
    this.wave++;
    this.currentWave = waveSpec(this.wave);
    this.spawnLeft = this.currentWave.count;
    this.spawnTimer = 0;
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
    }
    this.spawn(dt);
    this.moveEnemies(dt);
    this.fireTowers(dt);
    this.moveProjectiles(dt);
    this.enemies = this.enemies.filter((e) => e.alive);
    this.checkWaveEnd();
  }

  private spawn(dt: number): void {
    const w = this.currentWave;
    if (!w || this.spawnLeft <= 0) return;
    this.spawnTimer -= dt;
    while (this.spawnLeft > 0 && this.spawnTimer <= 0) {
      const s = this.map.spawns[(w.count - this.spawnLeft) % this.map.spawns.length]!;
      const x = s.x + 0.5;
      const y = s.y + 0.5;
      this.enemies.push({
        id: this.nextId++,
        def: w.enemy,
        hp: w.hp,
        maxHp: w.hp,
        reward: w.reward,
        x,
        y,
        px: x,
        py: y,
        target: { x: s.x, y: s.y },
        remaining: this.flow.distanceAt(s.x, s.y),
        alive: true,
      });
      this.spawnLeft--;
      this.spawnTimer += w.spawnInterval;
    }
  }

  private moveEnemies(dt: number): void {
    for (const e of this.enemies) {
      if (!e.alive) continue;
      let budget = ENEMIES[e.def].speed * dt;
      while (budget > 0) {
        const tx = e.target.x + 0.5;
        const ty = e.target.y + 0.5;
        const dx = tx - e.x;
        const dy = ty - e.y;
        const d = Math.hypot(dx, dy);
        if (d > ARRIVE_EPS) {
          const m = Math.min(d, budget);
          e.x += (dx / d) * m;
          e.y += (dy / d) * m;
          budget -= m;
          if (m < d) break;
        }
        const next = this.flow.next(e.target.x, e.target.y);
        if (!next) {
          this.leak(e);
          break;
        }
        e.target = next;
      }
      if (e.alive) {
        const tdist = Math.hypot(e.target.x + 0.5 - e.x, e.target.y + 0.5 - e.y);
        e.remaining = this.flow.distanceAt(e.target.x, e.target.y) + tdist;
      }
    }
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
      const lvl = this.levelOf(t);
      const target = this.pickTarget(t, lvl.range);
      if (!target) continue;
      const ox = t.cx + 0.5;
      const oy = t.cy + 0.5;
      t.aim = Math.atan2(target.y - oy, target.x - ox);
      if (t.cooldown > 0) continue;
      t.cooldown += lvl.fireInterval;
      this.projectiles.push({
        id: this.nextId++,
        towerId: t.id,
        targetId: target.id,
        damage: lvl.damage,
        speed: lvl.projectileSpeed,
        x: ox,
        y: oy,
        px: ox,
        py: oy,
      });
      this.events.push({ type: 'shot', towerId: t.id });
    }
  }

  /** "First" targeting: the enemy in range that is closest to the goal. */
  private pickTarget(t: Tower, range: number): Enemy | undefined {
    const ox = t.cx + 0.5;
    const oy = t.cy + 0.5;
    let best: Enemy | undefined;
    for (const e of this.enemies) {
      if (!e.alive) continue;
      if (Math.hypot(e.x - ox, e.y - oy) > range) continue;
      if (!best || e.remaining < best.remaining) best = e;
    }
    return best;
  }

  private moveProjectiles(dt: number): void {
    const keep: Projectile[] = [];
    for (const p of this.projectiles) {
      const target = this.enemies.find((e) => e.id === p.targetId && e.alive);
      const tower = this.towerById(p.towerId);
      if (!target) {
        // Target died or escaped before impact: the whole shot is wasted.
        if (tower) tower.stats.wasted += p.damage;
        this.events.push({ type: 'fizzle', projectileId: p.id, x: p.x, y: p.y });
        continue;
      }
      const dx = target.x - p.x;
      const dy = target.y - p.y;
      const d = Math.hypot(dx, dy);
      const m = p.speed * dt;
      if (m < d) {
        p.x += (dx / d) * m;
        p.y += (dy / d) * m;
        keep.push(p);
        continue;
      }
      const r = applyDamage(target.hp, p.damage);
      target.hp = r.hpAfter;
      if (tower) {
        tower.stats.dealt += r.dealt;
        tower.stats.wasted += r.overkill;
      }
      this.events.push({ type: 'hit', enemyId: target.id, dealt: r.dealt, overkill: r.overkill, x: target.x, y: target.y });
      if (target.hp <= 0) {
        target.alive = false;
        this.money += target.reward;
        if (tower) tower.stats.kills++;
        this.events.push({ type: 'kill', enemyId: target.id, reward: target.reward, x: target.x, y: target.y });
      }
    }
    this.projectiles = keep;
  }

  private checkWaveEnd(): void {
    if (this.phase !== 'wave' || this.spawnLeft > 0) return;
    if (this.enemies.length > 0 || this.projectiles.length > 0) return;
    const bonus = this.currentWave?.clearBonus ?? 0;
    this.money += bonus;
    this.currentWave = null;
    this.events.push({ type: 'waveClear', wave: this.wave, bonus });
    if (this.wave >= this.totalWaves) {
      this.phase = 'won';
      this.events.push({ type: 'won' });
    } else {
      this.phase = 'build';
    }
  }
}
