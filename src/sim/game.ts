import { afterArmor, applyDamage } from './damage';
import type { Upgrades } from './research';
import { ECONOMY, ENEMIES, FENCE_LEVELS, gunHp, PUSH_DPS, TOWERS, type Assault, type EnemyId, type Targeting, type TowerDef, type TowerId, type TowerLevel } from './content';
import { FlowField } from './flowField';
import type { Cell } from './grid';
import type { BuiltMap } from './maps';
import { arcHalfWidth, arcHpFactor, levelWaves, siegeHpFactor } from './levels';
import {
  BASE_RULES,
  BUILDING_SIZE,
  buildingValue,
  builders,
  gunJobSeconds,
  HQ_BASE_VALUE,
  HQ_LEVELS,
  HQ_SPOT,
  hqThreat,
  inBuildArea,
  LAB_BASE_VALUE,
  LAB_LEVELS,
  LAB_SPOT,
  baseHpFactor,
  repairCost,
  type BaseState,
  type GunJob,
} from './base';
import { goldBefore, waveSpec, type WaveSpec } from './waves';

export type Phase = 'build' | 'wave' | 'won' | 'lost';

const BATTLE_SAVE_VERSION = 1;

/** A running path or arc battle, as saved between visits. */
export interface BattleSave {
  v: number;
  mode: 'path' | 'arc' | 'siege';
  level: number;
  totalWaves: number;
  lives: number;
  wave: number;
  phase: Phase;
  time: number;
  goldEarned: number;
  money: number;
  nextId: number;
  spawned: number;
  spawnState: Array<{ left: number; timer: number }>;
  towers: Tower[];
  enemies: Enemy[];
  projectiles: Projectile[];
}

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
  /** Siege mode: index of the cell of the fence or gun it stands stopped at, -1 when walking. */
  wall: number;
  /** Siege mode: seconds until it can strike again. */
  attackCooldown: number;
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
  /** A targeting mode the player set (research opens them); the gun's own when absent. */
  aimMode?: Targeting;
  /** Flame: seconds spent on the current target (the flame heats up). */
  heat: number;
  /** Flame: true while it is burning a target this step. */
  firing: boolean;
  /** Siege mode: health; the gun is wrecked at 0. Unused elsewhere. */
  hp: number;
  maxHp: number;
  stats: TowerStats;
  /** Base mode: a builder at work on it (a gun being built does not fire). */
  job?: GunJob;
}

/** Base mode: the headquarters (the goal) or the laboratory. */
export interface Building {
  id: number;
  kind: 'hq' | 'lab';
  cx: number;
  cy: number;
  size: number;
  x: number;
  y: number;
  /** 0-based. */
  level: number;
  hp: number;
  maxHp: number;
}

/** Base mode: where the gold comes from and goes to (the treasury). */
export interface Wallet {
  gold: number;
}

export interface BaseSetup {
  state: BaseState;
  wallet: Wallet;
  /** Wall clock in ms (builders work in real time). */
  now?: () => number;
  /** Building timers run this many times faster (testing builds). */
  speed?: number;
}

/** Siege mode: one tile of fence. Level 0 wood, 1 stone, 2 steel. */
export interface Fence {
  id: number;
  kind: 'fence';
  cx: number;
  cy: number;
  /** Centre in grid cells. */
  x: number;
  y: number;
  level: number;
  hp: number;
  maxHp: number;
  invested: number;
}

/** Something siege enemies can stop at and break: a gun, a fence or a building of the base. */
export type Structure = Tower | Fence | Building;
const isFence = (s: Structure): s is Fence => 'kind' in s && s.kind === 'fence';
const isBuilding = (s: Structure): s is Building => 'kind' in s && (s.kind === 'hq' || s.kind === 'lab');

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
  /** A direct round struck; `air` when the target flies (the hit is up where it is). */
  | { type: 'impact'; x: number; y: number; air?: boolean }
  | { type: 'fizzle'; projectileId: number; x: number; y: number }
  /** A railgun fired: everything on the segment was hit. */
  | { type: 'rail'; towerId: number; x1: number; y1: number; x2: number; y2: number }
  | { type: 'kill'; enemyId: number; def: EnemyId; reward: number; x: number; y: number }
  | { type: 'leak'; enemyId: number; def: EnemyId }
  /** Siege mode: a unit shot at or rammed a gun or fence. */
  | { type: 'strike'; kind: Assault['kind']; enemyId: number; x1: number; y1: number; x2: number; y2: number }
  /** Siege mode: a gun, fence or building was destroyed. */
  | { type: 'wrecked'; fence: boolean; building?: 'hq' | 'lab'; x: number; y: number; size: number }
  /** Base mode: a builder finished a gun or raised it. */
  | { type: 'built'; towerId: number; kind: GunJob['kind'] }
  | { type: 'waveStart'; wave: number }
  | { type: 'waveClear'; wave: number; bonus: number }
  | { type: 'won' }
  | { type: 'lost' };

export type ActionResult = { ok: true } | { ok: false; reason: 'noMoney' | 'notBuildable' | 'occupied' | 'maxLevel' | 'notFound' | 'busy' | 'locked' | 'levelLocked' | 'blocks' | 'noBuilder' };

export interface GameOptions {
  /** Map level, 1-based: decides which guns can be built and which enemies attack. */
  level?: number;
  /** Waves to clear to win; the level's own number when absent. */
  totalWaves?: number;
  /** Wave plan to use instead of the standard one (for tests and scenarios). */
  waves?: (n: number, level: number) => WaveSpec;
  /** Finished research: which guns can be built, and the boosts. Without it every gun is open and nothing is boosted. */
  upgrades?: Upgrades;
  /** Siege mode with the player's base: what stands, the treasury, the builders. */
  base?: BaseSetup;
  /** Targeting modes the player set on each gun kind before (see Game.setAim). */
  aimPrefs?: Partial<Record<TowerId, Targeting>>;
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

/** Siege mode: what stepping into a wall costs a unit that never breaks one (it goes round any way there is). */
const NO_BREAK = 1000;

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
  const perLevel = ECONOMY.startMoneyPerLevel * (Math.min(level, ECONOMY.startMoneyLevelCap) - 1);
  return ECONOMY.startMoney + perLevel + Math.round((ECONOMY.headStart * goldBefore(level)) / 5) * 5;
}

export class Game {
  /** Distance field to the goal; rebuilt in arc mode whenever a gun is built or sold. */
  flow: FlowField;
  lives = ECONOMY.startLives;
  /** Number of the current or last started wave, 0 before the first. */
  wave = 0;
  readonly totalWaves: number;
  readonly level: number;
  /** Gold taken in this battle (kills and wave bonuses), whatever was spent. */
  goldEarned = 0;
  phase: Phase = 'build';
  time = 0;

  enemies: Enemy[] = [];
  towers: Tower[] = [];
  /** Siege mode only. */
  fences: Fence[] = [];
  /** Base mode: the headquarters (goal) and the laboratory (null once destroyed). */
  hq: Building | null = null;
  lab: Building | null = null;
  /** Base mode, or null. */
  readonly base: BaseSetup | null;
  projectiles: Projectile[] = [];

  private nextId = 1;
  private currentWave: WaveSpec | null = null;
  private spawnState: SpawnState[] = [];
  private spawned = 0;
  private events: GameEvent[] = [];
  /** Units dropped during this step (by destroyed APCs); join after it. */
  private dropped: Enemy[] = [];
  private readonly waves: (n: number, level: number, hq?: number) => WaveSpec;
  private readonly upgrades: Upgrades | null;
  /** Targeting mode the player last set per gun kind; new guns of that kind take it. */
  aimPrefs: Partial<Record<TowerId, Targeting>> = {};
  /** Kill gold not yet paid out as a whole coin (stronger attackers pay fractions more). */
  private rewardCarry = 0;
  /** Gun stats with research applied, per gun and level. */
  private readonly levelCache = new Map<string, TowerLevel>();
  private readonly defCache = new Map<TowerId, TowerDef>();
  /** Tower id per cell, 0 where free. */
  private readonly occupied: Int32Array;
  /** Siege mode: fence id per cell, 0 where none. */
  private readonly fenceGrid: Int32Array;
  /** Siege mode: one field per detour length, built when first needed after the walls change. */
  private readonly fields = new Map<number, FlowField>();
  /** Siege mode: the open-ground distance, walls ignored; orders the enemies along the way. */
  private readonly ground: FlowField | null;
  /** Siege mode: cells enemies come in from; nothing can be built there. */
  private readonly entry: Set<number>;
  /** Gold outside base mode. */
  private purse = 0;

  constructor(
    readonly map: BuiltMap,
    opts: GameOptions = {},
  ) {
    this.level = Math.max(1, Math.floor(opts.level ?? 1));
    this.totalWaves = opts.totalWaves ?? levelWaves(this.level);
    this.upgrades = opts.upgrades ?? null;
    this.aimPrefs = { ...opts.aimPrefs };
    this.base = map.mode === 'siege' ? (opts.base ?? null) : null;
    if (!this.base) this.money = startMoney(this.level) + (this.upgrades?.startGold ?? 0);
    this.lives += this.upgrades?.lives ?? 0;
    this.waves = opts.waves ?? waveSpec;
    this.occupied = new Int32Array(map.grid.cols * map.grid.rows);
    this.fenceGrid = new Int32Array(map.grid.cols * map.grid.rows);
    const { grid } = map;
    this.ground = map.mode === 'siege' ? new FlowField(grid, map.goals, (x, y) => grid.get(x, y) !== 'blocked') : null;
    this.entry = new Set(map.mode === 'siege' ? (map.arcSpawns ?? []).map((c) => grid.index(c.x, c.y)) : []);
    if (this.base) this.loadBase(this.base.state);
    this.flow = this.makeFlow(this.occupied);
  }

  /** Gold to spend: the battle's own, or in base mode the treasury. */
  get money(): number {
    return this.base ? this.base.wallet.gold : this.purse;
  }

  set money(v: number) {
    if (this.base) this.base.wallet.gold = v;
    else this.purse = v;
  }

  private now(): number {
    return this.base?.now?.() ?? Date.now();
  }

  /** Base mode: put the saved base on the field. */
  private loadBase(b: BaseState): void {
    const [hx, hy] = HQ_SPOT;
    const hqMax = HQ_LEVELS[b.hq.level]!.hp;
    this.hq = { id: this.nextId++, kind: 'hq', cx: hx, cy: hy, size: BUILDING_SIZE, x: hx + 1, y: hy + 1, level: b.hq.level, hp: Math.min(b.hq.hp, hqMax), maxHp: hqMax };
    if (b.lab) {
      const [lx, ly] = LAB_SPOT;
      const max = LAB_LEVELS[b.lab.level]!.hp;
      this.lab = { id: this.nextId++, kind: 'lab', cx: lx, cy: ly, size: BUILDING_SIZE, x: lx + 1, y: ly + 1, level: b.lab.level, hp: Math.min(b.lab.hp, max), maxHp: max };
      for (let y = ly; y < ly + BUILDING_SIZE; y++) for (let x = lx; x < lx + BUILDING_SIZE; x++) this.occupied[this.map.grid.index(x, y)] = this.lab.id;
    }
    for (const g of b.guns) {
      if (this.placementError(g.def, g.cx, g.cy, true)) continue;
      const t = this.newTower(g.def, g.cx, g.cy, g.level, g.invested);
      t.hp = Math.min(g.hp, t.maxHp);
      if (g.job) t.job = { ...g.job };
    }
    for (const f of b.fences) {
      if (this.fenceError(f.cx, f.cy, true)) continue;
      const fence = this.newFence(f.cx, f.cy, f.level, f.invested);
      fence.hp = Math.min(f.hp, fence.maxHp);
    }
    this.settleJobs();
  }

  /**
   * Path and arc modes: the whole running battle as plain data, so a closed
   * game picks up where it left off. Null in base mode (the base saves itself)
   * and once the battle is over.
   */
  saveBattle(): BattleSave | null {
    if (this.base || this.mode === 'siege' || this.phase === 'won' || this.phase === 'lost') return null;
    const copy = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;
    return {
      v: BATTLE_SAVE_VERSION,
      mode: this.mode,
      level: this.level,
      totalWaves: this.totalWaves,
      lives: this.lives,
      wave: this.wave,
      phase: this.phase,
      time: this.time,
      goldEarned: this.goldEarned,
      money: this.purse,
      nextId: this.nextId,
      spawned: this.spawned,
      spawnState: copy(this.spawnState),
      towers: copy(this.towers),
      enemies: copy(this.enemies),
      projectiles: copy(this.projectiles),
    };
  }

  /** Put a saved battle back on this (fresh, same map and level) game; false when it does not fit. */
  restoreBattle(s: unknown): boolean {
    const b = s as Partial<BattleSave> | null;
    if (!b || b.v !== BATTLE_SAVE_VERSION || b.mode !== this.mode || b.level !== this.level || b.totalWaves !== this.totalWaves) return false;
    if (this.base || this.towers.length || this.wave || (b.phase !== 'build' && b.phase !== 'wave')) return false;
    if (!Array.isArray(b.towers) || !Array.isArray(b.enemies) || !Array.isArray(b.projectiles) || !Array.isArray(b.spawnState)) return false;
    const { grid } = this.map;
    for (const t of b.towers) {
      if (!(t.def in TOWERS) || !grid.inBounds(t.cx, t.cy) || !grid.inBounds(t.cx + t.size - 1, t.cy + t.size - 1)) return false;
    }
    if (b.enemies.some((e) => !(e.def in ENEMIES))) return false;
    this.lives = Number(b.lives) || 0;
    this.wave = Number(b.wave) || 0;
    this.time = Number(b.time) || 0;
    this.goldEarned = Number(b.goldEarned) || 0;
    this.purse = Number(b.money) || 0;
    this.nextId = Math.max(1, Number(b.nextId) || 1);
    this.spawned = Number(b.spawned) || 0;
    this.towers = b.towers;
    for (const t of this.towers) this.markFootprint(t, t.id);
    this.enemies = b.enemies;
    this.projectiles = b.projectiles;
    this.phase = b.phase;
    this.currentWave = b.phase === 'wave' ? this.waves(this.wave, this.level, this.base ? (this.hq?.level ?? 0) : 0) : null;
    this.spawnState = b.phase === 'wave' ? b.spawnState : [];
    this.rebuildFlow();
    return true;
  }

  /** Base mode: the base as it stands now, to be saved (attack number and building jobs are the caller's). */
  snapshot(): Pick<BaseState, 'hq' | 'lab' | 'guns' | 'fences'> {
    return {
      hq: { level: this.hq?.level ?? 0, hp: Math.max(0, this.hq?.hp ?? 0) },
      lab: this.lab ? { level: this.lab.level, hp: this.lab.hp } : null,
      guns: this.towers.map((t) => ({ def: t.def, level: t.level, cx: t.cx, cy: t.cy, hp: t.hp, invested: t.stats.invested, ...(t.job ? { job: { ...t.job } } : {}) })),
      fences: this.fences.map((f) => ({ cx: f.cx, cy: f.cy, level: f.level, hp: f.hp, invested: f.invested })),
    };
  }

  /** Base mode: builders free now (the headquarters' and laboratory's jobs count, as do the guns'). */
  freeBuilders(): number {
    if (!this.base) return Infinity;
    const st = this.base.state;
    const total = builders({ ...st, lab: this.lab ? { level: this.lab.level, hp: this.lab.hp } : null });
    return total - st.jobs.length - this.towers.filter((t) => t.job).length;
  }

  /** Base mode: finish the guns whose builders are done. */
  private settleJobs(): void {
    const now = this.now();
    for (const t of this.towers) {
      if (!t.job || t.job.endsAt > now) continue;
      const kind = t.job.kind;
      delete t.job;
      if (kind === 'upgrade') this.raise(t);
      this.events.push({ type: 'built', towerId: t.id, kind });
    }
  }

  /** Base mode: may footprints go here (the headquarters' level sets how far out)? */
  inArea(cx: number, cy: number, size: number): boolean {
    return !this.base || !this.hq || inBuildArea(this.hq.level, cx, cy, size);
  }

  /** Base mode: the building on a cell (the laboratory or the headquarters). */
  buildingAt(cx: number, cy: number): Building | undefined {
    for (const b of [this.hq, this.lab]) if (b && cx >= b.cx && cx < b.cx + b.size && cy >= b.cy && cy < b.cy + b.size) return b;
    return undefined;
  }

  /** Gold a part cost: guns and fences what was paid, buildings the price of their levels. */
  private worth(s: Structure): number {
    if (isFence(s)) return s.invested;
    if (isBuilding(s)) return s.kind === 'hq' ? buildingValue(HQ_LEVELS, s.level, HQ_BASE_VALUE) : buildingValue(LAB_LEVELS, s.level, LAB_BASE_VALUE);
    return s.stats.invested;
  }

  /** Base mode: gold to mend a part fully. */
  repairCost(s: Structure): number {
    return this.base ? repairCost(s.hp, s.maxHp, this.worth(s)) : 0;
  }

  private parts(): Structure[] {
    const out: Structure[] = [...this.towers, ...this.fences];
    if (this.hq) out.push(this.hq);
    if (this.lab) out.push(this.lab);
    return out;
  }

  /** Base mode: gold to mend everything. */
  repairAllCost(): number {
    return this.parts().reduce((sum, s) => sum + this.repairCost(s), 0);
  }

  /** Base mode: mend one part at once. */
  repair(s: Structure): ActionResult {
    if (!this.base || this.phase === 'won' || this.phase === 'lost') return { ok: false, reason: 'busy' };
    const cost = this.repairCost(s);
    if (cost <= 0) return { ok: false, reason: 'maxLevel' };
    if (this.money < cost) return { ok: false, reason: 'noMoney' };
    this.money -= cost;
    s.hp = s.maxHp;
    return { ok: true };
  }

  /** Base mode: mend everything that the treasury can pay for: the headquarters first, then the cheapest. */
  repairAll(): ActionResult {
    const rank = (s: Structure) => (s === this.hq ? -1e9 : this.repairCost(s));
    const broken = this.parts().filter((s) => this.repairCost(s) > 0).sort((a, b) => rank(a) - rank(b));
    if (!broken.length) return { ok: false, reason: 'maxLevel' };
    let any = false;
    for (const s of broken) if (this.repair(s).ok) any = true;
    return any ? { ok: true } : { ok: false, reason: 'noMoney' };
  }

  // ---- queries -------------------------------------------------------------

  get mode(): 'path' | 'arc' | 'siege' {
    return this.map.mode;
  }

  /** Arc and siege modes: enemies cross open ground from a widening arc. */
  get openField(): boolean {
    return this.map.mode !== 'path';
  }

  /** Arc mode: half-width (radians) of the sector the running or next wave comes from. */
  arcWidth(): number {
    const n = this.phase === 'wave' ? this.wave : Math.min(this.wave + 1, this.totalWaves);
    return arcHalfWidth(n, this.totalWaves, this.level);
  }

  /** Arc mode: the edge cells the running or next wave comes in from. */
  activeSpawns(): Cell[] {
    const w = this.arcWidth();
    return (this.map.arcSpawns ?? []).filter((s) => Math.abs(s.off) <= w);
  }

  /** The tower whose footprint covers this cell. */
  towerAt(cx: number, cy: number): Tower | undefined {
    if (!this.map.grid.inBounds(cx, cy)) return undefined;
    const id = this.occupied[this.map.grid.index(cx, cy)];
    return id ? this.towerById(id) : undefined;
  }

  towerById(id: number): Tower | undefined {
    return this.towers.find((t) => t.id === id);
  }

  fenceAt(cx: number, cy: number): Fence | undefined {
    if (!this.map.grid.inBounds(cx, cy)) return undefined;
    const id = this.fenceGrid[this.map.grid.index(cx, cy)];
    return id ? this.fenceById(id) : undefined;
  }

  fenceById(id: number): Fence | undefined {
    return this.fences.find((f) => f.id === id);
  }

  /** Cost to put up a wooden fence. */
  fenceCost(): number {
    return FENCE_LEVELS[0].cost;
  }

  /** Cost to build a gun (level 1). */
  buildCost(def: TowerId): number {
    return TOWERS[def].levels[0].cost;
  }

  /** Cost to raise a fence to its next level, or null at steel. */
  fenceUpgradeCost(f: Fence): number | null {
    return FENCE_LEVELS[f.level + 1]?.cost ?? null;
  }

  fenceSellValue(f: Fence): number {
    return Math.floor(f.invested * ECONOMY.sellRefund);
  }

  /** Why a fence cannot go on this cell, or null when it can. */
  fenceError(cx: number, cy: number, loading = false): 'notBuildable' | 'occupied' | null {
    const { grid } = this.map;
    if (this.mode !== 'siege' || grid.get(cx, cy) !== 'build' || this.entry.has(grid.index(cx, cy))) return 'notBuildable';
    if (!loading && !this.inArea(cx, cy, 1)) return 'notBuildable';
    if (this.occupied[grid.index(cx, cy)] || this.fenceGrid[grid.index(cx, cy)] || this.walkerOn(cx, cy, 1)) return 'occupied';
    return null;
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

  /** Highest gun level (1-based) research and, in base mode, the headquarters allow. */
  maxGunLevel(def: TowerId): number {
    const research = this.upgrades ? (this.upgrades.maxLevel[def] ?? Infinity) : Infinity;
    return Math.min(research, this.hq ? HQ_LEVELS[this.hq.level]!.maxGun : Infinity);
  }

  /** Whether research (and the headquarters) allow raising the gun to its next level. */
  canRaise(tower: Tower): boolean {
    return tower.level + 2 <= this.maxGunLevel(tower.def);
  }

  sellValue(tower: Tower): number {
    return Math.floor(tower.stats.invested * ECONOMY.sellRefund);
  }

  /** Why a gun cannot stand with its footprint's top-left cell at (cx, cy), or null when it can. */
  placementError(def: TowerId, cx: number, cy: number, loading = false): 'notBuildable' | 'occupied' | null {
    const { grid } = this.map;
    const size = TOWERS[def].size;
    if (!loading && !this.inArea(cx, cy, size)) return 'notBuildable';
    let occupied = false;
    for (let y = cy; y < cy + size; y++) {
      for (let x = cx; x < cx + size; x++) {
        if (grid.get(x, y) !== 'build' || this.entry.has(grid.index(x, y))) return 'notBuildable';
        if (this.occupied[grid.index(x, y)] || this.fenceGrid[grid.index(x, y)]) occupied = true;
      }
    }
    return occupied ? 'occupied' : null;
  }

  /** Targeting modes a gun can be set to: its own first, then the ones research opened. */
  aimModes(def: TowerId): Targeting[] {
    const own = TOWERS[def].targeting;
    return [own, ...(this.upgrades?.aims[def] ?? []).filter((m) => m !== own)];
  }

  /** The targeting mode a gun uses now. */
  aimOf(tower: Tower): Targeting {
    const modes = this.aimModes(tower.def);
    return tower.aimMode && modes.includes(tower.aimMode) ? tower.aimMode : modes[0]!;
  }

  /**
   * Set a gun's targeting mode. New guns of the same kind take it too
   * (`aimPrefs`, which the app keeps between battles).
   */
  setAim(towerId: number, mode: Targeting): ActionResult {
    const t = this.towerById(towerId);
    if (!t) return { ok: false, reason: 'notFound' };
    if (!this.aimModes(t.def).includes(mode)) return { ok: false, reason: 'locked' };
    t.aimMode = mode;
    t.targetId = 0;
    this.aimPrefs[t.def] = mode;
    return { ok: true };
  }

  /** Whether research has opened the gun (every gun is open when the game has no research). */
  isUnlocked(def: TowerId): boolean {
    return this.upgrades ? this.upgrades.guns.includes(def) : true;
  }

  canBuildAt(def: TowerId, cx: number, cy: number): boolean {
    if (this.placementError(def, cx, cy) !== null) return false;
    if (this.mode === 'siege') return !this.walkerOn(cx, cy, TOWERS[def].size);
    return this.mode !== 'arc' || this.blockError(cx, cy, TOWERS[def].size) === null;
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
    if (this.mode === 'arc') {
      const block = this.blockError(cx, cy, d.size);
      if (block) return { ok: false, reason: block };
    }
    if (this.mode === 'siege' && this.walkerOn(cx, cy, d.size)) return { ok: false, reason: 'occupied' };
    if (this.freeBuilders() <= 0) return { ok: false, reason: 'noBuilder' };
    this.money -= cost;
    const tower = this.newTower(def, cx, cy, 0, cost);
    if (this.base) tower.job = { kind: 'build', endsAt: this.now() + (gunJobSeconds(def, 0) * 1000) / (this.base.speed ?? 1) };
    this.rebuildFlow();
    return { ok: true };
  }

  private newTower(def: TowerId, cx: number, cy: number, level: number, invested: number): Tower {
    const d = TOWERS[def];
    const tower: Tower = {
      id: this.nextId++,
      def,
      level,
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
      hp: gunHp(d.size, level),
      maxHp: gunHp(d.size, level),
      stats: { dealt: 0, wasted: 0, kills: 0, invested },
    };
    const pref = this.aimPrefs[def];
    if (pref && pref !== d.targeting && this.aimModes(def).includes(pref)) tower.aimMode = pref;
    this.towers.push(tower);
    this.markFootprint(tower, tower.id);
    return tower;
  }

  private newFence(cx: number, cy: number, level: number, invested: number): Fence {
    const { hp } = FENCE_LEVELS[level]!;
    const f: Fence = { id: this.nextId++, kind: 'fence', cx, cy, x: cx + 0.5, y: cy + 0.5, level, hp, maxHp: hp, invested };
    this.fences.push(f);
    this.fenceGrid[this.map.grid.index(cx, cy)] = f.id;
    return f;
  }

  upgrade(towerId: number): ActionResult {
    const t = this.towerById(towerId);
    if (!t) return { ok: false, reason: 'notFound' };
    const cost = this.upgradeCost(t);
    if (cost === null) return { ok: false, reason: 'maxLevel' };
    if (!this.canRaise(t)) return { ok: false, reason: 'levelLocked' };
    if (t.job) return { ok: false, reason: 'busy' };
    if (this.money < cost) return { ok: false, reason: 'noMoney' };
    if (this.freeBuilders() <= 0) return { ok: false, reason: 'noBuilder' };
    this.money -= cost;
    t.stats.invested += cost;
    // In the base a builder raises it in real time; it keeps firing at its old level meanwhile.
    if (this.base) t.job = { kind: 'upgrade', endsAt: this.now() + (gunJobSeconds(t.def, t.level + 1) * 1000) / (this.base.speed ?? 1) };
    else this.raise(t);
    return { ok: true };
  }

  private raise(t: Tower): void {
    t.level = Math.min(t.level + 1, TOWERS[t.def].levels.length - 1);
    // A bigger gun is sturdier by the difference; damage taken stays.
    const maxHp = gunHp(t.size, t.level);
    t.hp += maxHp - t.maxHp;
    t.maxHp = maxHp;
  }

  sell(towerId: number): ActionResult {
    const t = this.towerById(towerId);
    if (!t) return { ok: false, reason: 'notFound' };
    this.money += this.sellValue(t);
    this.markFootprint(t, 0);
    this.towers = this.towers.filter((o) => o !== t);
    this.rebuildFlow();
    return { ok: true };
  }

  /** Siege mode: put a wooden fence on one tile. */
  buildFence(cx: number, cy: number): ActionResult {
    if (this.phase === 'won' || this.phase === 'lost') return { ok: false, reason: 'busy' };
    const err = this.fenceError(cx, cy);
    if (err) return { ok: false, reason: err };
    const { cost } = FENCE_LEVELS[0];
    if (this.money < cost) return { ok: false, reason: 'noMoney' };
    this.money -= cost;
    this.newFence(cx, cy, 0, cost);
    this.rebuildFlow();
    return { ok: true };
  }

  /** Wood to stone, stone to steel; adds the difference in health. */
  upgradeFence(id: number): ActionResult {
    const f = this.fenceById(id);
    if (!f) return { ok: false, reason: 'notFound' };
    const cost = this.fenceUpgradeCost(f);
    if (cost === null) return { ok: false, reason: 'maxLevel' };
    if (this.money < cost) return { ok: false, reason: 'noMoney' };
    this.money -= cost;
    f.level++;
    f.invested += cost;
    const maxHp = FENCE_LEVELS[f.level]!.hp;
    f.hp += maxHp - f.maxHp;
    f.maxHp = maxHp;
    return { ok: true };
  }

  sellFence(id: number): ActionResult {
    const f = this.fenceById(id);
    if (!f) return { ok: false, reason: 'notFound' };
    this.money += this.fenceSellValue(f);
    this.removeFence(f);
    return { ok: true };
  }

  startWave(): ActionResult {
    if (this.phase !== 'build' || this.wave >= this.totalWaves) return { ok: false, reason: 'busy' };
    this.wave++;
    this.currentWave = this.waves(this.wave, this.level, this.base ? (this.hq?.level ?? 0) : 0);
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
    if (this.base) this.settleJobs();
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
    if (this.mode === 'siege') this.assault(dt);
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

  /**
   * Ground the walkers may use: the road in path mode; open, unbuilt ground in
   * arc mode. In siege mode the field of the units that never break through.
   */
  private makeFlow(occupied: Int32Array): FlowField {
    const { grid } = this.map;
    if (this.map.mode === 'path') return new FlowField(grid, this.map.goals, (x, y) => grid.get(x, y) === 'path');
    if (this.map.mode === 'siege') return this.field(NO_BREAK);
    return new FlowField(grid, this.map.goals, (x, y) => grid.get(x, y) !== 'blocked' && !occupied[grid.index(x, y)]);
  }

  /**
   * Siege mode: the way to the goal for a unit that would rather walk `detour`
   * tiles round to a gap than break through a wall. Walls are walkable at that
   * cost, so with no gap near it heads into the wall and breaks it.
   */
  private field(detour: number): FlowField {
    let f = this.fields.get(detour);
    if (!f) {
      const { grid } = this.map;
      const wall = (x: number, y: number) => this.occupied[grid.index(x, y)] !== 0 || this.fenceGrid[grid.index(x, y)] !== 0;
      f = new FlowField(grid, this.map.goals, (x, y) => grid.get(x, y) !== 'blocked', (x, y) => (wall(x, y) ? 1 + detour : 1));
      this.fields.set(detour, f);
    }
    return f;
  }

  /** The field a unit walks by: its own detour in siege mode, the shared one elsewhere. */
  private fieldOf(def: EnemyId): FlowField {
    if (this.mode !== 'siege') return this.flow;
    const d = ENEMIES[def];
    return this.field('assault' in d && 'detour' in d ? d.detour : NO_BREAK);
  }

  /** Siege mode: whether a fence or gun stands on the cell. */
  private isWall(x: number, y: number): boolean {
    const i = this.map.grid.index(x, y);
    return this.occupied[i] !== 0 || this.fenceGrid[i] !== 0;
  }

  /** Siege mode: the gun or fence on a cell, by index. */
  private structureAt(i: number): Structure | undefined {
    const tid = this.occupied[i];
    if (tid && this.lab?.id === tid) return this.lab;
    if (tid) return this.towerById(tid);
    const fid = this.fenceGrid[i];
    return fid ? this.fenceById(fid) : undefined;
  }

  /** A walker stands on the square, or is about to step into it. */
  private walkerOn(cx: number, cy: number, size: number): boolean {
    const onIt = (x: number, y: number) => x >= cx && x < cx + size && y >= cy && y < cy + size;
    return this.enemies.some((e) => !e.air && (onIt(Math.floor(e.x), Math.floor(e.y)) || onIt(e.target.x, e.target.y)));
  }

  /** Arc mode: after the guns changed, walk around them; a walker whose next cell is now built on steps back to its own. */
  private rebuildFlow(): void {
    if (this.mode === 'siege') {
      this.fields.clear();
      this.flow = this.makeFlow(this.occupied);
      return;
    }
    if (this.mode !== 'arc') return;
    this.flow = this.makeFlow(this.occupied);
    for (const e of this.enemies) {
      if (e.air || this.flow.distanceAt(e.target.x, e.target.y) >= 0) continue;
      e.target = { x: Math.floor(e.x), y: Math.floor(e.y) };
    }
  }

  /**
   * Arc mode: a gun may not stand on a walker, nor shut the goal off from any
   * edge enemies can come from or from any walker already on the field.
   */
  private blockError(cx: number, cy: number, size: number): 'occupied' | 'blocks' | null {
    if (this.walkerOn(cx, cy, size)) return 'occupied';
    const trial = this.occupied.slice();
    for (let y = cy; y < cy + size; y++) for (let x = cx; x < cx + size; x++) trial[this.map.grid.index(x, y)] = -1;
    const flow = this.makeFlow(trial);
    const cut = (c: Cell) => flow.distanceAt(c.x, c.y) < 0;
    if ((this.map.arcSpawns ?? []).some(cut)) return 'blocks';
    if (this.enemies.some((e) => !e.air && cut({ x: Math.floor(e.x), y: Math.floor(e.y) }))) return 'blocks';
    return null;
  }

  /** A new gun starts pointing at the nearest stretch of road (in arc mode: out towards the arc). */
  private initialAim(x: number, y: number): number {
    if (this.openField) {
      const g = this.map.goals[0]!;
      return Math.atan2(y - g.y - 1, x - g.x - 1);
    }
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
        const s = this.spawnCell();
        const siege = this.base ? baseHpFactor(this.level) : this.mode === 'siege' ? siegeHpFactor(this.level) : 1;
        // The player's base: a stronger headquarters draws stronger attackers, who pay more.
        const threat = this.base ? hqThreat(this.hq?.level ?? 0) : 1;
        const hp = this.mode === 'path' ? g.hp : Math.round(g.hp * arcHpFactor(this.level) * siege * threat);
        // Kill gold stays whole: the fractions carry over to the next unit.
        this.rewardCarry += g.reward * threat;
        const reward = Math.floor(this.rewardCarry + 1e-9);
        this.rewardCarry -= reward;
        this.enemies.push(this.makeEnemy(g.enemy, hp, reward, s.x + 0.5, s.y + 0.5, { x: s.x, y: s.y }));
        st.left--;
        st.timer += g.interval;
      }
    });
  }

  /** Where the next enemy enters: the road's start, or (arc mode) a cell of the current arc, spread evenly over it. */
  private spawnCell(): Cell {
    const n = this.spawned++;
    if (!this.openField) return this.map.spawns[n % this.map.spawns.length]!;
    const cells = this.activeSpawns();
    return cells[Math.floor(hash01(n * 2654435761 + this.wave) * cells.length)] ?? this.map.arcSpawns![0]!;
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
      wall: -1,
      attackCooldown: 0,
    };
    if (air) {
      // Flyers ignore the road and head straight for the goal.
      e.target = this.map.goals[0] ?? target;
      e.heading = Math.atan2(e.target.y + 0.5 - y, e.target.x + 0.5 - x);
      e.remaining = Math.hypot(e.target.x + 0.5 - x, e.target.y + 0.5 - y);
    } else {
      const next = this.fieldOf(def).next(target.x, target.y);
      e.heading = next ? Math.atan2(next.y - target.y, next.x - target.x) : 0;
      e.remaining = (this.ground ?? this.flow).distanceAt(target.x, target.y) + Math.hypot(target.x + 0.5 - x, target.y + 0.5 - y);
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
   * Walk a point along a flow field for `budget` cells of distance.
   * Returns false when it runs off the end of the road (reached the goal).
   * In siege mode it stops at the middle of its cell when the next one is a
   * fence or gun, and `wall` says which.
   */
  private walk(pos: { x: number; y: number; target: Cell; heading?: number; wall?: number }, budget: number, flow = this.flow): boolean {
    if (pos.wall !== undefined) pos.wall = -1;
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
      const next = flow.next(pos.target.x, pos.target.y);
      if (!next) return false;
      if (this.mode === 'siege' && this.isWall(next.x, next.y)) {
        if (pos.wall !== undefined) pos.wall = this.map.grid.index(next.x, next.y);
        break;
      }
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
      if (!this.walk(e, this.speedOf(e) * dt, this.fieldOf(e.def))) {
        this.leak(e);
        continue;
      }
      const tdist = Math.hypot(e.target.x + 0.5 - e.x, e.target.y + 0.5 - e.y);
      e.remaining = (this.ground ?? this.flow).distanceAt(e.target.x, e.target.y) + tdist;
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
    this.walk(p, budget, this.fieldOf(e.def));
    return p;
  }

  /**
   * Siege mode: every unit with an assault strikes the wall it stands at, or
   * else a gun within its reach; one that only passes by leans on the wall it
   * is stuck at.
   */
  private assault(dt: number): void {
    for (const e of this.enemies) {
      if (!e.alive || e.air) continue;
      const d = ENEMIES[e.def];
      // Blows grow with the unit: the square root of how much its wave raised its health.
      const power = Math.sqrt(e.maxHp / d.baseHp);
      const wall = e.wall >= 0 ? this.structureAt(e.wall) : undefined;
      if (!('assault' in d)) {
        if (wall) this.hitStructure(wall, PUSH_DPS * power * dt);
        continue;
      }
      e.attackCooldown = Math.max(0, e.attackCooldown - dt);
      if (e.attackCooldown > 0) continue;
      const a: Assault = d.assault;
      const reach = a.kind === 'ram' ? a.range + d.radius : a.range;
      let target: Structure | undefined = wall;
      if (!target) {
        let best = Infinity;
        for (const t of this.targetsInBase()) {
          const dist = Math.hypot(Math.max(t.cx - e.x, 0, e.x - t.cx - t.size), Math.max(t.cy - e.y, 0, e.y - t.cy - t.size));
          if (dist <= reach && dist < best) {
            best = dist;
            target = t;
          }
        }
      }
      if (!target) continue;
      e.attackCooldown = a.interval;
      this.events.push({ type: 'strike', kind: a.kind, enemyId: e.id, x1: e.x, y1: e.y, x2: target.x, y2: target.y });
      this.hitStructure(target, a.damage * power);
    }
  }

  /** What attackers may shoot at when nearby: guns, and in the base its buildings. */
  private targetsInBase(): Array<Tower | Building> {
    if (!this.hq) return this.towers;
    const out: Array<Tower | Building> = [...this.towers, this.hq];
    if (this.lab) out.push(this.lab);
    return out;
  }

  private hitStructure(s: Structure, damage: number): void {
    if (this.phase === 'lost') return;
    s.hp -= damage;
    if (s.hp > 0) return;
    if (isBuilding(s)) {
      this.events.push({ type: 'wrecked', fence: false, building: s.kind, x: s.x, y: s.y, size: s.size });
      if (s.kind === 'hq') {
        s.hp = 0;
        this.phase = 'lost';
        this.events.push({ type: 'lost' });
        return;
      }
      for (let y = s.cy; y < s.cy + s.size; y++) for (let x = s.cx; x < s.cx + s.size; x++) this.occupied[this.map.grid.index(x, y)] = 0;
      this.lab = null;
      this.rebuildFlow();
      return;
    }
    if (isFence(s)) {
      this.removeFence(s);
      this.events.push({ type: 'wrecked', fence: true, x: s.x, y: s.y, size: 1 });
      return;
    }
    if (!this.towerById(s.id)) return;
    this.markFootprint(s, 0);
    this.towers = this.towers.filter((o) => o !== s);
    this.events.push({ type: 'wrecked', fence: false, x: s.x, y: s.y, size: s.size });
    this.rebuildFlow();
  }

  private removeFence(f: Fence): void {
    if (!this.fenceById(f.id)) return;
    this.fenceGrid[this.map.grid.index(f.cx, f.cy)] = 0;
    this.fences = this.fences.filter((o) => o !== f);
    this.rebuildFlow();
  }

  private leak(e: Enemy): void {
    e.alive = false;
    if (this.hq) {
      // In the base whatever gets through strikes the headquarters.
      this.events.push({ type: 'leak', enemyId: e.id, def: e.def });
      this.hitStructure(this.hq, ENEMIES[e.def].leakDamage * BASE_RULES.leakHp);
      return;
    }
    this.lives = Math.max(0, this.lives - ENEMIES[e.def].leakDamage);
    this.events.push({ type: 'leak', enemyId: e.id, def: e.def });
    if (this.lives <= 0) {
      this.phase = 'lost';
      this.events.push({ type: 'lost' });
    }
  }

  private fireTowers(dt: number): void {
    for (const t of this.towers) {
      t.cooldown = Math.max(0, t.cooldown - dt);
      t.firing = false;
      // A gun still being built does not fire.
      if (t.job?.kind === 'build') continue;
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
   * its priority (its own, or the mode the player set), and takes the first on
   * the path when nothing matches that priority.
   */
  private pickTarget(t: Tower): Enemy | undefined {
    const list = this.candidates(t);
    if (!list.length) return undefined;
    const mode = this.aimOf(t);
    const kept = t.targetId ? list.find((e) => e.id === t.targetId) : undefined;
    // Set to the smallest, a gun leaves its target for a smaller one that comes in range.
    const smaller = mode === 'smallest' && kept && list.some((e) => ENEMIES[e.def].radius < ENEMIES[kept.def].radius);
    if (kept && !smaller) return kept;
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
    switch (mode) {
      case 'smallest':
        return best((e) => -ENEMIES[e.def].radius);
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
        this.events.push({ type: 'impact', x: target.x, y: target.y, ...(target.air ? { air: true } : {}) });
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
      this.events.push({ type: 'kill', enemyId: target.id, def: target.def, reward: target.reward, x: target.x, y: target.y });
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
