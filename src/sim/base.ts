import { ENEMY_IDS, FENCE_LEVELS, gunHp, TOWER_IDS, TOWERS, type EnemyId, type TowerId } from './content';
import { levelArcMap } from './levels';
import type { ArcMapSpec } from './maps';

/**
 * The player's base: one fixed field the player builds on, kept between
 * attacks, and the game's hub. Its buildings are the menus: the headquarters
 * (raising it, provoking the next attack), the muster (missions in the other
 * modes), the arsenal (the guns), the laboratory (research) and the treasury
 * (the gold).
 *
 * Attackers go for everything. What they break stays broken until the player
 * mends it; a destroyed building lies in ruins and does not work until it is
 * rebuilt, each with its own penalty. When the headquarters falls the army
 * that took it holds it, and the player wins it back in a battle of its own.
 * The base is never wiped.
 *
 * Plain data and pure functions, so the app saves it and tests drive it.
 */

/** The base's field: the arc mode's first field, the same for every attack. */
export const BASE_MAP: ArcMapSpec = { ...levelArcMap(1), id: 'base' };

export const BUILDING_KINDS = ['hq', 'muster', 'arsenal', 'lab', 'treasury'] as const;
export type BuildingKind = (typeof BUILDING_KINDS)[number];

/** Headquarters: top-left cell of its 2×2 (the map's goal). */
export const HQ_SPOT: readonly [number, number] = BASE_MAP.goal;
/** Top-left cell of each building's 2×2, round the headquarters; the treasury stands behind it. */
export const BUILDING_SPOTS: Readonly<Record<BuildingKind, readonly [number, number]>> = {
  hq: HQ_SPOT,
  lab: [26, 21],
  muster: [21, 25],
  arsenal: [27, 24],
  treasury: [24, 27],
};
export const BUILDING_SIZE = 2;

const MIN = 60;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

export interface HqLevel {
  hp: number;
  /** Guns and fences may stand this far from the headquarters' centre, in tiles. */
  radius: number;
  /** Highest gun level (1-based) the base allows, on top of what research allows. */
  maxGun: number;
  /** Traps the player may lay on one field. */
  traps: number;
  /** Gold and real seconds to raise it to this level (level 1 stands from the start). */
  cost: number;
  seconds: number;
}

export const HQ_LEVELS: readonly HqLevel[] = [
  { hp: 1200, radius: 7, maxGun: 3, traps: 0, cost: 0, seconds: 0 },
  { hp: 1800, radius: 9, maxGun: 3, traps: 1, cost: 600, seconds: 25 * MIN },
  { hp: 2500, radius: 10, maxGun: 4, traps: 1, cost: 1500, seconds: 3 * HOUR },
  { hp: 3200, radius: 11, maxGun: 4, traps: 2, cost: 2400, seconds: 6 * HOUR },
  { hp: 3900, radius: 12, maxGun: 4, traps: 2, cost: 3500, seconds: 16 * HOUR },
  { hp: 4600, radius: 13, maxGun: 5, traps: 3, cost: 4800, seconds: DAY },
  { hp: 5300, radius: 14, maxGun: 5, traps: 3, cost: 6400, seconds: DAY + 8 * HOUR },
  { hp: 5900, radius: 15, maxGun: 5, traps: 4, cost: 8200, seconds: 2 * DAY },
  { hp: 6400, radius: 16, maxGun: 5, traps: 5, cost: 10500, seconds: 2 * DAY + 12 * HOUR },
];

export interface LabLevel {
  hp: number;
  /** Research items running at once. A higher laboratory opens deeper research (the headquarters caps it); it never makes research faster. */
  slots: number;
  /** Building jobs running at once. */
  builders: number;
  cost: number;
  seconds: number;
}

/** The laboratory is raised very slowly: the higher levels take days. */
export const LAB_LEVELS: readonly LabLevel[] = [
  { hp: 600, slots: 1, builders: 1, cost: 0, seconds: 0 },
  { hp: 850, slots: 1, builders: 1, cost: 600, seconds: 4 * HOUR },
  { hp: 1100, slots: 1, builders: 2, cost: 1200, seconds: 12 * HOUR },
  { hp: 1400, slots: 2, builders: 2, cost: 2000, seconds: DAY },
  { hp: 1750, slots: 2, builders: 2, cost: 3000, seconds: 1.5 * DAY },
  { hp: 2100, slots: 2, builders: 2, cost: 4200, seconds: 2 * DAY },
  { hp: 2500, slots: 2, builders: 3, cost: 5600, seconds: 3 * DAY },
  { hp: 2900, slots: 2, builders: 3, cost: 7200, seconds: 4 * DAY },
  { hp: 3400, slots: 2, builders: 3, cost: 9000, seconds: 5 * DAY },
];

export interface TreasuryLevel {
  hp: number;
  /** Gold the vault keeps safe when the treasury is destroyed. */
  protect: number;
  cost: number;
  seconds: number;
}

export const TREASURY_LEVELS: readonly TreasuryLevel[] = [
  { hp: 700, protect: 300, cost: 0, seconds: 0 },
  { hp: 1000, protect: 1000, cost: 500, seconds: 30 * MIN },
  { hp: 1400, protect: 3000, cost: 1500, seconds: 3 * HOUR },
  { hp: 1900, protect: 8000, cost: 4000, seconds: 12 * HOUR },
  { hp: 2600, protect: 20000, cost: 9000, seconds: 2 * DAY },
];

/** The muster and the arsenal grow with the headquarters: their level is its level. Their health per level. */
export const MUSTER_HP = [700, 950, 1200, 1500, 1800, 2100, 2400, 2700, 3000] as const;
export const ARSENAL_HP = [800, 1100, 1400, 1700, 2050, 2400, 2750, 3100, 3500] as const;

/** Buildings the player raises on their own; the muster and the arsenal follow the headquarters. */
export type Raisable = 'hq' | 'lab' | 'treasury';
export const RAISABLE: readonly Raisable[] = ['hq', 'lab', 'treasury'];
export const isRaisable = (k: BuildingKind): k is Raisable => k === 'hq' || k === 'lab' || k === 'treasury';

/** Highest level (0-based) of each building: the treasury has 5, the rest follow the headquarters' 9. */
export function maxBuildingLevel(kind: BuildingKind): number {
  return kind === 'treasury' ? TREASURY_LEVELS.length - 1 : HQ_LEVELS.length - 1;
}

/** Full health of a building at a level (0-based). */
export function buildingHp(kind: BuildingKind, level: number): number {
  const i = Math.max(0, Math.min(maxBuildingLevel(kind), level));
  switch (kind) {
    case 'hq':
      return HQ_LEVELS[i]!.hp;
    case 'lab':
      return LAB_LEVELS[i]!.hp;
    case 'treasury':
      return TREASURY_LEVELS[i]!.hp;
    case 'muster':
      return MUSTER_HP[i]!;
    case 'arsenal':
      return ARSENAL_HP[i]!;
  }
}

/** Value of a level-1 building, for repairs and for counting what an attack destroyed. */
export const BUILDING_BASE_VALUE: Readonly<Record<BuildingKind, number>> = { hq: 600, lab: 400, treasury: 300, muster: 300, arsenal: 400 };

/** Gold a building's levels are worth so far. */
export function buildingValue(kind: BuildingKind, level: number): number {
  let v = BUILDING_BASE_VALUE[kind];
  const levels: readonly { cost: number }[] | null = kind === 'hq' || kind === 'muster' || kind === 'arsenal' ? HQ_LEVELS : kind === 'lab' ? LAB_LEVELS : TREASURY_LEVELS;
  // The muster and the arsenal come with the headquarters' levels: count a third of them.
  const share = kind === 'muster' || kind === 'arsenal' ? 1 / 3 : 1;
  for (let i = 1; i <= level; i++) v += Math.round(levels[i]!.cost * share);
  return v;
}

/** Real seconds to rebuild a destroyed building: longer the higher it was. */
export const REBUILD_SECONDS = [10 * MIN, 45 * MIN, 2 * HOUR, 4 * HOUR, 6 * HOUR, 9 * HOUR, 12 * HOUR, 18 * HOUR, DAY] as const;

/**
 * Real seconds a builder takes to build a gun (to level 1) or raise it to each
 * next level: the middle level takes 10 minutes, the higher ones more. Heavy
 * 3×3 guns take half as long again. Fences go up at once. During an attack it
 * is the same price and the same time. Rebuilding a wrecked gun takes as long
 * as its level did.
 */
export const GUN_JOB_SECONDS = [1 * MIN, 4 * MIN, 10 * MIN, 30 * MIN, 90 * MIN] as const;

export function gunJobSeconds(def: TowerId, level: number): number {
  return GUN_JOB_SECONDS[Math.min(level, GUN_JOB_SECONDS.length - 1)]! * (TOWERS[def].size >= 3 ? 1.5 : 1);
}

export const BASE_RULES = {
  /** A full repair (or rebuilding a ruin) costs this share of what the part is worth; less damage, less gold. */
  repairShare: 0.5,
  /** Gold a battle earns, multiplied (the bonus goes to the treasury at the end). */
  goldFactor: 1.5,
  /** The battle is lost once this share of the base's value (buildings and guns, not fences) is destroyed. */
  lossShare: 0.5,
  /** A destroyed treasury loses this share of the gold above what its vault protects. */
  treasuryLoss: 0.2,
  /** A wrecked gun sells for this share of its normal price. */
  wreckSale: 0.5,
};

export interface BaseGun {
  def: TowerId;
  /** 0-based. */
  level: number;
  cx: number;
  cy: number;
  /** 0 for a wreck. */
  hp: number;
  invested: number;
  /** A builder at work on it: building it (it does not fire yet), raising it a level, or rebuilding a wreck. */
  job?: GunJob;
}

export interface GunJob {
  kind: 'build' | 'upgrade' | 'repair';
  /** ms since the epoch. */
  endsAt: number;
}

export interface BaseFence {
  cx: number;
  cy: number;
  level: number;
  hp: number;
  invested: number;
}

export interface BaseBuilding {
  /** 0-based. */
  level: number;
  /** 0 while it lies in ruins. */
  hp: number;
}

export interface BaseJob {
  what: BuildingKind;
  /** Raising it a level, or rebuilding its ruins. */
  kind: 'upgrade' | 'rebuild';
  /** ms since the epoch. */
  endsAt: number;
}

/** A unit of the army holding the headquarters. */
export interface Occupier {
  def: EnemyId;
  hp: number;
  maxHp: number;
  reward: number;
}

export interface BaseState {
  /** The next attack to fight, 1-based. */
  attack: number;
  buildings: Record<BuildingKind, BaseBuilding>;
  guns: BaseGun[];
  fences: BaseFence[];
  jobs: BaseJob[];
  /** The army that took the headquarters and holds it; null while it is the player's. */
  occupied: Occupier[] | null;
}

/** Two crossbows in front of the headquarters, so a new base is not bare. */
const STARTER_GUNS: ReadonlyArray<readonly [TowerId, number, number]> = [
  ['crossbow', 21, 21],
  ['crossbow', 24, 19],
];

export function newBase(): BaseState {
  const buildings = {} as Record<BuildingKind, BaseBuilding>;
  for (const k of BUILDING_KINDS) buildings[k] = { level: 0, hp: buildingHp(k, 0) };
  return {
    attack: 1,
    buildings,
    guns: STARTER_GUNS.map(([def, cx, cy]) => ({ def, level: 0, cx, cy, hp: gunHp(TOWERS[def].size, 0), invested: TOWERS[def].levels[0].cost })),
    fences: [],
    jobs: [],
    occupied: null,
  };
}

const num = (v: unknown, min: number, max: number): number | null => (typeof v === 'number' && Number.isFinite(v) ? Math.min(max, Math.max(min, v)) : null);
const int = (v: unknown, min: number, max: number): number | null => {
  const n = num(v, min, max);
  return n === null ? null : Math.floor(n);
};

/** Repairs a base loaded from storage: anything malformed is dropped, numbers are clamped. Older saves (headquarters and laboratory only) carry over. */
export function sanitizeBase(raw: unknown): BaseState {
  if (!raw || typeof raw !== 'object') return newBase();
  const r = raw as Record<string, unknown>;
  const s = newBase();
  s.guns = [];
  s.attack = int(r.attack, 1, 1e6) ?? 1;
  const src = (r.buildings && typeof r.buildings === 'object' ? r.buildings : {}) as Record<string, unknown>;
  // Old saves: `hq` and `lab` at the top, a destroyed laboratory as null.
  if (!r.buildings) {
    src.hq = r.hq;
    src.lab = r.lab === null ? { level: 0, hp: 0 } : r.lab;
  }
  for (const k of BUILDING_KINDS) {
    const v = src[k];
    if (!v || typeof v !== 'object') continue;
    const b = v as Record<string, unknown>;
    const level = int(b.level, 0, maxBuildingLevel(k));
    if (level === null) continue;
    s.buildings[k] = { level, hp: num(b.hp, 0, buildingHp(k, level)) ?? buildingHp(k, level) };
  }
  if (Array.isArray(r.occupied)) {
    s.occupied = [];
    for (const v of r.occupied as unknown[]) {
      if (!v || typeof v !== 'object') continue;
      const o = v as Record<string, unknown>;
      const def = ENEMY_IDS.find((id) => id === o.def);
      const maxHp = num(o.maxHp, 1, 1e9);
      const hp = num(o.hp, 0, maxHp ?? 1);
      if (!def || maxHp === null || hp === null || hp <= 0) continue;
      s.occupied.push({ def, hp, maxHp, reward: int(o.reward, 0, 1e6) ?? 0 });
    }
    s.buildings.hq.hp = 0;
  } else if (s.buildings.hq.hp <= 0) {
    // A headquarters at 0 with nobody in it: an old save that lost its base. Stand it up again.
    s.buildings.hq.hp = buildingHp('hq', s.buildings.hq.level);
  }
  // The muster and the arsenal follow the headquarters.
  for (const k of ['muster', 'arsenal'] as const) {
    const b = s.buildings[k];
    if (b.level !== s.buildings.hq.level) s.buildings[k] = { level: s.buildings.hq.level, hp: b.hp > 0 ? buildingHp(k, s.buildings.hq.level) : 0 };
  }
  if (Array.isArray(r.guns)) {
    for (const v of r.guns as unknown[]) {
      if (!v || typeof v !== 'object') continue;
      const g = v as Record<string, unknown>;
      const def = TOWER_IDS.find((id) => id === g.def);
      if (!def) continue;
      const level = int(g.level, 0, TOWERS[def].levels.length - 1);
      const cx = int(g.cx, 0, BASE_MAP.cols - 1);
      const cy = int(g.cy, 0, BASE_MAP.rows - 1);
      if (level === null || cx === null || cy === null) continue;
      const hp = num(g.hp, 0, gunHp(TOWERS[def].size, level));
      if (hp === null) continue;
      const gun: BaseGun = { def, level, cx, cy, hp, invested: int(g.invested, 0, 1e9) ?? 0 };
      const j = g.job as Record<string, unknown> | undefined;
      if (j && (j.kind === 'build' || j.kind === 'upgrade' || j.kind === 'repair') && typeof j.endsAt === 'number' && Number.isFinite(j.endsAt)) gun.job = { kind: j.kind, endsAt: j.endsAt };
      if (hp <= 0 && gun.job?.kind !== 'repair') delete gun.job;
      s.guns.push(gun);
    }
  }
  if (Array.isArray(r.fences)) {
    for (const v of r.fences as unknown[]) {
      if (!v || typeof v !== 'object') continue;
      const f = v as Record<string, unknown>;
      const level = int(f.level, 0, FENCE_LEVELS.length - 1);
      const cx = int(f.cx, 0, BASE_MAP.cols - 1);
      const cy = int(f.cy, 0, BASE_MAP.rows - 1);
      if (level === null || cx === null || cy === null) continue;
      const hp = num(f.hp, 0, FENCE_LEVELS[level]!.hp);
      if (hp === null || hp <= 0) continue;
      s.fences.push({ cx, cy, level, hp, invested: int(f.invested, 0, 1e9) ?? 0 });
    }
  }
  if (Array.isArray(r.jobs)) {
    for (const v of r.jobs as unknown[]) {
      if (!v || typeof v !== 'object') continue;
      const j = v as Record<string, unknown>;
      const what = BUILDING_KINDS.find((k) => k === j.what);
      // Old saves: a job on a destroyed laboratory rebuilt it.
      const kind = j.kind === 'rebuild' || j.kind === 'upgrade' ? j.kind : what && s.buildings[what].hp <= 0 ? 'rebuild' : 'upgrade';
      if (!what || typeof j.endsAt !== 'number' || !Number.isFinite(j.endsAt) || s.jobs.some((o) => o.what === what)) continue;
      if (kind === 'upgrade' && !isRaisable(what)) continue;
      if (kind === 'rebuild' && s.buildings[what].hp > 0) continue;
      s.jobs.push({ what, kind, endsAt: j.endsAt });
    }
  }
  return s;
}

/**
 * Enemy health in the base relative to arc mode, by attack: tuned with the bot
 * (tests/base.test.ts). The base keeps what it built, so attacks do not get
 * weaker the way the one-off siege levels did.
 */
export const BASE_TUNING = { hpFirst: 0.4, hpStep: 0, hpMin: 0.4 };

export function baseHpFactor(attack: number): number {
  return Math.max(BASE_TUNING.hpMin, BASE_TUNING.hpFirst - BASE_TUNING.hpStep * (attack - 1));
}

/**
 * A stronger headquarters draws stronger attackers, who pay more: per
 * headquarters level (0-based) above the first, this much more health and
 * gold per kill.
 */
export const HQ_THREAT = 0.15;

/** Attackers' health and kill gold relative to a level-1 headquarters. */
export function hqThreat(hqLevel: number): number {
  return 1 + HQ_THREAT * Math.max(0, hqLevel);
}

/** Gold an attack adds to the treasury on top of what its kills already paid into it. */
export function baseTakings(earned: number, won: boolean, attack: number): number {
  const bonus = won ? 100 + 40 * attack : 0;
  return Math.round(earned * (BASE_RULES.goldFactor - 1) + bonus * BASE_RULES.goldFactor);
}

// ---- buildings and builders ---------------------------------------------------

/** A building works while it stands; ruins (and ruins being rebuilt) do not. */
export const standing = (b: BaseState, k: BuildingKind): boolean => b.buildings[k].hp > 0;

export const hqLevel = (b: BaseState): HqLevel => HQ_LEVELS[b.buildings.hq.level]!;
/** The laboratory's level while it stands, or null while it lies in ruins. */
export const labLevel = (b: BaseState): LabLevel | null => (standing(b, 'lab') ? LAB_LEVELS[b.buildings.lab.level]! : null);

/** Builders at work at once: the laboratory's level gives more; without it there is one. */
export function builders(b: BaseState): number {
  return labLevel(b)?.builders ?? 1;
}

/** Whether a building job takes a builder: rebuilding the muster does not (and costs nothing). */
export const takesBuilder = (j: Pick<BaseJob, 'what' | 'kind'>): boolean => !(j.what === 'muster' && j.kind === 'rebuild');

/** Builders busy now: on the buildings and the guns. */
export function busyBuilders(b: BaseState): number {
  return b.jobs.filter(takesBuilder).length + b.guns.filter((g) => g.job).length;
}

/** What raising a building (or rebuilding its ruins) costs; null when there is nothing to do. */
export function jobPrice(b: BaseState, what: BuildingKind): { kind: BaseJob['kind']; cost: number; seconds: number } | null {
  const bl = b.buildings[what];
  if (bl.hp <= 0) {
    // The headquarters is not rebuilt: it is won back.
    if (what === 'hq') return null;
    const cost = what === 'muster' ? 0 : Math.ceil(buildingValue(what, bl.level) * BASE_RULES.repairShare);
    return { kind: 'rebuild', cost, seconds: REBUILD_SECONDS[bl.level]! };
  }
  if (!isRaisable(what)) return null;
  const levels = what === 'hq' ? HQ_LEVELS : what === 'lab' ? LAB_LEVELS : TREASURY_LEVELS;
  const next = levels[bl.level + 1];
  return next ? { kind: 'upgrade', cost: next.cost, seconds: next.seconds } : null;
}

/** `hqLevel`: the laboratory cannot rise above the headquarters' level. */
export type JobError = 'maxLevel' | 'hqLevel' | 'running' | 'noBuilder' | 'noGold' | 'occupied';

export function jobError(b: BaseState, what: BuildingKind, gold: number): JobError | null {
  if (b.occupied && what === 'hq') return 'occupied';
  const price = jobPrice(b, what);
  if (!price) return 'maxLevel';
  if (what === 'lab' && price.kind === 'upgrade' && b.buildings.lab.level + 1 > b.buildings.hq.level) return 'hqLevel';
  if (b.jobs.some((j) => j.what === what)) return 'running';
  if (takesBuilder({ what, kind: price.kind }) && busyBuilders(b) >= builders(b)) return 'noBuilder';
  if (gold < price.cost) return 'noGold';
  return null;
}

/** Start a job (the caller takes the gold). `speed` > 1 shortens timers for testing builds. */
export function startJob(b: BaseState, what: BuildingKind, now: number, speed = 1): BaseState {
  const price = jobPrice(b, what);
  if (!price) return b;
  return { ...b, jobs: [...b.jobs, { what, kind: price.kind, endsAt: now + (price.seconds * 1000) / speed }] };
}

/** Set a building's level, keeping the damage it has taken; the muster and the arsenal follow the headquarters. */
function setLevel(s: BaseState, what: BuildingKind, level: number): BaseState {
  const buildings = { ...s.buildings };
  const put = (k: BuildingKind) => {
    const old = buildings[k];
    const hp = old.hp > 0 ? Math.max(1, old.hp + buildingHp(k, level) - buildingHp(k, old.level)) : 0;
    buildings[k] = { level, hp };
  };
  put(what);
  if (what === 'hq') {
    put('muster');
    put('arsenal');
  }
  return { ...s, buildings };
}

/** Finish the jobs whose time is up. Returns the same object when nothing finished. */
export function settleJobs(b: BaseState, now: number): BaseState {
  const done = b.jobs.filter((j) => j.endsAt <= now);
  if (!done.length) return b;
  let s: BaseState = { ...b, jobs: b.jobs.filter((j) => j.endsAt > now) };
  for (const j of done) {
    const bl = s.buildings[j.what];
    if (j.kind === 'rebuild') s = { ...s, buildings: { ...s.buildings, [j.what]: { level: bl.level, hp: buildingHp(j.what, bl.level) } } };
    else s = setLevel(s, j.what, Math.min(maxBuildingLevel(j.what), bl.level + 1));
  }
  return s;
}

/** The headquarters fell: the army that took it holds it. */
export function occupy(b: BaseState, army: Occupier[]): BaseState {
  return {
    ...b,
    buildings: { ...b.buildings, hq: { ...b.buildings.hq, hp: 0 } },
    // A job on the headquarters is lost with it.
    jobs: b.jobs.filter((j) => j.what !== 'hq'),
    occupied: army,
  };
}

/** The headquarters is won back: it stands again one level lower; the muster and the arsenal follow. */
export function liberate(b: BaseState): BaseState {
  const level = Math.max(0, b.buildings.hq.level - 1);
  const s = setLevel({ ...b, occupied: null }, 'hq', level);
  return { ...s, buildings: { ...s.buildings, hq: { level, hp: buildingHp('hq', level) } } };
}

/** Gold lost when the treasury is destroyed: a share of what its vault does not protect. */
export function treasuryLoss(b: BaseState, gold: number): number {
  const protect = TREASURY_LEVELS[b.buildings.treasury.level]!.protect;
  return Math.floor(Math.max(0, gold - protect) * BASE_RULES.treasuryLoss);
}

// ---- gold -------------------------------------------------------------------

/** Gold to repair a part fully: a share of what it cost, by how much of it is broken. */
export function repairCost(hp: number, maxHp: number, invested: number): number {
  if (hp >= maxHp || maxHp <= 0) return 0;
  return Math.max(1, Math.ceil(invested * BASE_RULES.repairShare * (1 - hp / maxHp)));
}

/** Whether a footprint lies inside the area the headquarters' level lets the player build on. */
export function inBuildArea(hqLevelIndex: number, cx: number, cy: number, size: number): boolean {
  const r = HQ_LEVELS[hqLevelIndex]!.radius;
  const hx = HQ_SPOT[0] + BUILDING_SIZE / 2;
  const hy = HQ_SPOT[1] + BUILDING_SIZE / 2;
  for (let y = cy; y < cy + size; y++) {
    for (let x = cx; x < cx + size; x++) if (Math.hypot(x + 0.5 - hx, y + 0.5 - hy) > r) return false;
  }
  return true;
}
