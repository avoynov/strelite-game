import { FENCE_LEVELS, gunHp, TOWER_IDS, TOWERS, type TowerId } from './content';
import { levelArcMap } from './levels';
import type { ArcMapSpec } from './maps';

/**
 * The player's base ("Разрушаване"): one fixed field the player builds on, kept
 * between attacks. Guns and fences keep their damage; what was wrecked stays
 * gone. The headquarters (the goal) and the laboratory are buildings of the
 * base; both are raised on real-time timers by the base's builders. When the
 * headquarters falls the whole base is lost.
 *
 * Plain data and pure functions, so the app saves it and tests drive it.
 */

/** The base's field: the arc mode's first field, the same for every attack. */
export const BASE_MAP: ArcMapSpec = { ...levelArcMap(1), id: 'base' };

/** Headquarters: top-left cell of its 2×2 (the goal). */
export const HQ_SPOT: readonly [number, number] = BASE_MAP.goal;
/** Laboratory: top-left cell of its 2×2, beside the headquarters. */
export const LAB_SPOT: readonly [number, number] = [26, 21];
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
  /** Gold and real seconds to raise it to this level (level 1 stands from the start). */
  cost: number;
  seconds: number;
}

export const HQ_LEVELS: readonly HqLevel[] = [
  { hp: 1200, radius: 7, maxGun: 3, cost: 0, seconds: 0 },
  { hp: 1800, radius: 9, maxGun: 3, cost: 600, seconds: 15 * MIN },
  { hp: 2600, radius: 11, maxGun: 4, cost: 1500, seconds: 2 * HOUR },
  { hp: 3600, radius: 13, maxGun: 4, cost: 3500, seconds: 8 * HOUR },
  { hp: 5000, radius: 16, maxGun: 5, cost: 7000, seconds: DAY },
];

export interface LabLevel {
  hp: number;
  /** Research runs this many times faster. */
  speed: number;
  /** Research items running at once. */
  slots: number;
  /** Building jobs (headquarters, laboratory) running at once. */
  builders: number;
  cost: number;
  seconds: number;
}

export const LAB_LEVELS: readonly LabLevel[] = [
  { hp: 600, speed: 1, slots: 1, builders: 1, cost: 0, seconds: 0 },
  { hp: 900, speed: 1.25, slots: 1, builders: 1, cost: 500, seconds: 20 * MIN },
  { hp: 1300, speed: 1.5, slots: 1, builders: 2, cost: 1400, seconds: 2 * HOUR },
  { hp: 1800, speed: 1.75, slots: 2, builders: 2, cost: 3000, seconds: 8 * HOUR },
  { hp: 2500, speed: 2, slots: 2, builders: 3, cost: 6000, seconds: DAY },
];

/** Building the laboratory again after it was destroyed: it comes back at level 1. */
export const LAB_REBUILD = { cost: 400, seconds: 3 * HOUR };

/**
 * Real seconds a builder takes to build a gun (to level 1) or raise it to each
 * next level; heavy 3×3 guns take half as long again. Fences go up at once.
 * During an attack it is the same price and the same time.
 */
export const GUN_JOB_SECONDS = [10, 20, 45, 90, 180] as const;

export function gunJobSeconds(def: TowerId, level: number): number {
  return GUN_JOB_SECONDS[Math.min(level, GUN_JOB_SECONDS.length - 1)]! * (TOWERS[def].size >= 3 ? 1.5 : 1);
}

export const BASE_RULES = {
  /** A full repair costs this share of what the part cost; less damage, less gold. */
  repairShare: 0.5,
  /** Gold a battle earns, multiplied (the bonus goes to the treasury at the end). */
  goldFactor: 1.5,
  /** Selling what still stands after the headquarters fell: this share of what it cost. */
  lossSale: 0.35,
  /** Headquarters health one leaked "life" takes. */
  leakHp: 60,
};

export interface BaseGun {
  def: TowerId;
  /** 0-based. */
  level: number;
  cx: number;
  cy: number;
  hp: number;
  invested: number;
  /** A builder at work on it: building it (it does not fire yet) or raising it a level. */
  job?: GunJob;
}

export interface GunJob {
  kind: 'build' | 'upgrade';
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
  /** 0-based index into HQ_LEVELS / LAB_LEVELS. */
  level: number;
  hp: number;
}

export type JobTarget = 'hq' | 'lab';

export interface BaseJob {
  what: JobTarget;
  /** ms since the epoch. */
  endsAt: number;
}

export interface BaseState {
  /** The next attack to fight, 1-based. */
  attack: number;
  hq: BaseBuilding;
  /** null while destroyed. */
  lab: BaseBuilding | null;
  guns: BaseGun[];
  fences: BaseFence[];
  jobs: BaseJob[];
}

/** Two crossbows in front of the headquarters, so a new base is not bare. */
const STARTER_GUNS: ReadonlyArray<readonly [TowerId, number, number]> = [
  ['crossbow', 21, 21],
  ['crossbow', 24, 19],
];

export function newBase(): BaseState {
  return {
    attack: 1,
    hq: { level: 0, hp: HQ_LEVELS[0]!.hp },
    lab: { level: 0, hp: LAB_LEVELS[0]!.hp },
    guns: STARTER_GUNS.map(([def, cx, cy]) => ({ def, level: 0, cx, cy, hp: gunHp(TOWERS[def].size, 0), invested: TOWERS[def].levels[0].cost })),
    fences: [],
    jobs: [],
  };
}

const num = (v: unknown, min: number, max: number): number | null => (typeof v === 'number' && Number.isFinite(v) ? Math.min(max, Math.max(min, v)) : null);
const int = (v: unknown, min: number, max: number): number | null => {
  const n = num(v, min, max);
  return n === null ? null : Math.floor(n);
};

/** Repairs a base loaded from storage: anything malformed is dropped, numbers are clamped. */
export function sanitizeBase(raw: unknown): BaseState {
  if (!raw || typeof raw !== 'object') return newBase();
  const r = raw as Record<string, unknown>;
  const building = (v: unknown, levels: readonly { hp: number }[]): BaseBuilding | null => {
    if (!v || typeof v !== 'object') return null;
    const b = v as Record<string, unknown>;
    const level = int(b.level, 0, levels.length - 1);
    if (level === null) return null;
    const hp = num(b.hp, 0, levels[level]!.hp);
    return hp === null || hp <= 0 ? null : { level, hp };
  };
  const hq = building(r.hq, HQ_LEVELS);
  if (!hq) return newBase();
  const s: BaseState = { attack: int(r.attack, 1, 1e6) ?? 1, hq, lab: building(r.lab, LAB_LEVELS), guns: [], fences: [], jobs: [] };
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
      if (hp === null || hp <= 0) continue;
      const gun: BaseGun = { def, level, cx, cy, hp, invested: int(g.invested, 0, 1e9) ?? 0 };
      const j = g.job as Record<string, unknown> | undefined;
      if (j && (j.kind === 'build' || j.kind === 'upgrade') && typeof j.endsAt === 'number' && Number.isFinite(j.endsAt)) gun.job = { kind: j.kind, endsAt: j.endsAt };
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
      if ((j.what === 'hq' || j.what === 'lab') && typeof j.endsAt === 'number' && Number.isFinite(j.endsAt) && !s.jobs.some((o) => o.what === j.what)) {
        s.jobs.push({ what: j.what, endsAt: j.endsAt });
      }
    }
  }
  return s;
}

/**
 * Enemy health in the base relative to arc mode, by attack: tuned with the bot
 * (tests/base.test.ts). The base keeps what it built, so attacks do not get
 * weaker the way the one-off siege levels did.
 */
export const BASE_TUNING = { hpFirst: 0.55, hpStep: 0, hpMin: 0.45 };

export function baseHpFactor(attack: number): number {
  return Math.max(BASE_TUNING.hpMin, BASE_TUNING.hpFirst - BASE_TUNING.hpStep * (attack - 1));
}

/** Gold an attack adds to the treasury on top of what its kills already paid into it. */
export function baseTakings(earned: number, won: boolean, attack: number): number {
  const bonus = won ? 100 + 40 * attack : 0;
  return Math.round(earned * (BASE_RULES.goldFactor - 1) + bonus * BASE_RULES.goldFactor);
}

// ---- buildings and builders ---------------------------------------------------

export const hqLevel = (b: BaseState): HqLevel => HQ_LEVELS[b.hq.level]!;
export const labLevel = (b: BaseState): LabLevel | null => (b.lab ? LAB_LEVELS[b.lab.level]! : null);

/** Builders at work at once: the laboratory's level gives more; without it there is one. */
export function builders(b: BaseState): number {
  return labLevel(b)?.builders ?? 1;
}

/** Builders busy now: on the headquarters, the laboratory and the guns. */
export function busyBuilders(b: BaseState): number {
  return b.jobs.length + b.guns.filter((g) => g.job).length;
}

/** What raising (or, for a destroyed laboratory, rebuilding) a building costs; null when it is at its top level. */
export function jobPrice(b: BaseState, what: JobTarget): { cost: number; seconds: number } | null {
  if (what === 'hq') {
    const next = HQ_LEVELS[b.hq.level + 1];
    return next ? { cost: next.cost, seconds: next.seconds } : null;
  }
  if (!b.lab) return { ...LAB_REBUILD };
  const next = LAB_LEVELS[b.lab.level + 1];
  return next ? { cost: next.cost, seconds: next.seconds } : null;
}

export type JobError = 'maxLevel' | 'running' | 'noBuilder' | 'noGold';

export function jobError(b: BaseState, what: JobTarget, gold: number): JobError | null {
  const price = jobPrice(b, what);
  if (!price) return 'maxLevel';
  if (b.jobs.some((j) => j.what === what)) return 'running';
  if (busyBuilders(b) >= builders(b)) return 'noBuilder';
  if (gold < price.cost) return 'noGold';
  return null;
}

/** Start a job (the caller takes the gold). `speed` > 1 shortens timers for testing builds. */
export function startJob(b: BaseState, what: JobTarget, now: number, speed = 1): BaseState {
  const price = jobPrice(b, what);
  if (!price) return b;
  return { ...b, jobs: [...b.jobs, { what, endsAt: now + (price.seconds * 1000) / speed }] };
}

/** Finish the jobs whose time is up. Returns the same object when nothing finished. */
export function settleJobs(b: BaseState, now: number): BaseState {
  const done = b.jobs.filter((j) => j.endsAt <= now);
  if (!done.length) return b;
  let s: BaseState = { ...b, jobs: b.jobs.filter((j) => j.endsAt > now) };
  for (const j of done) {
    if (j.what === 'hq') {
      const level = Math.min(HQ_LEVELS.length - 1, s.hq.level + 1);
      // A raised building is sturdier by the difference; damage taken stays.
      s = { ...s, hq: { level, hp: s.hq.hp + HQ_LEVELS[level]!.hp - HQ_LEVELS[s.hq.level]!.hp } };
    } else if (!s.lab) {
      s = { ...s, lab: { level: 0, hp: LAB_LEVELS[0]!.hp } };
    } else {
      const level = Math.min(LAB_LEVELS.length - 1, s.lab.level + 1);
      s = { ...s, lab: { level, hp: s.lab.hp + LAB_LEVELS[level]!.hp - LAB_LEVELS[s.lab.level]!.hp } };
    }
  }
  return s;
}

// ---- gold -------------------------------------------------------------------

/** Gold a building's levels cost so far (what repairing and selling it are measured by). */
export function buildingValue(levels: readonly { cost: number }[], level: number, floor: number): number {
  let v = floor;
  for (let i = 1; i <= level; i++) v += levels[i]!.cost;
  return v;
}

/** Value of a level-1 headquarters and laboratory for repairs (they cost nothing to stand). */
export const HQ_BASE_VALUE = 200;
export const LAB_BASE_VALUE = LAB_REBUILD.cost;

/** Gold to repair a part fully: a share of what it cost, by how much of it is broken. */
export function repairCost(hp: number, maxHp: number, invested: number): number {
  if (hp >= maxHp || maxHp <= 0) return 0;
  return Math.max(1, Math.ceil(invested * BASE_RULES.repairShare * (1 - hp / maxHp)));
}

/** What the parts still standing sell for once the headquarters fell. */
export function lossSale(b: BaseState): number {
  let v = 0;
  for (const g of b.guns) v += g.invested;
  for (const f of b.fences) v += f.invested;
  if (b.lab) v += buildingValue(LAB_LEVELS, b.lab.level, 0);
  return Math.floor(v * BASE_RULES.lossSale);
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
