import type { TowerId } from './content';

/**
 * Research tree: gold banked from battles buys guns, boosts and effects. Each
 * item costs gold and takes real time; one runs at a time. The state is plain
 * data (saved by the app) and every function here is pure, so the timing and
 * effects are testable without a clock or storage.
 */

/** Guns the player has from the very first battle. */
export const START_GUNS: readonly TowerId[] = ['crossbow', 'zis3'];

/** What finished research does to a battle. Multipliers are 1 and additions 0 when nothing is researched. */
export interface GunMods {
  damage: number;
  /** Multiplies the time between shots (lower is faster). */
  reload: number;
  range: number;
  splash: number;
  pierce: number;
  passThrough: number;
  /** Multiplies how long a flame takes to reach full heat. */
  rampTime: number;
}

export interface Upgrades {
  guns: readonly TowerId[];
  startGold: number;
  lives: number;
  /** Per gun, boosts for every gun already folded in. */
  gun: Record<TowerId, GunMods>;
}

type ItemEffect =
  | { kind: 'gun'; gun: TowerId }
  | { kind: 'damage'; add: number }
  | { kind: 'reload'; mul: number }
  | { kind: 'startGold'; add: number }
  | { kind: 'lives'; add: number }
  | { kind: 'gunMod'; gun: TowerId; mods: Partial<GunMods> };

export type Branch = 'guns' | 'boosts' | 'effects';

export interface ResearchItem {
  id: string;
  branch: Branch;
  cost: number;
  /** Real seconds it takes. */
  seconds: number;
  /** Items that must be finished first. */
  requires: readonly string[];
  effect: ItemEffect;
}

const MIN = 60;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

/**
 * The tree. Guns come one by one in the agreed order; each boost and effect
 * leans on the one before it. Cost and time grow the deeper an item sits.
 */
export const RESEARCH: readonly ResearchItem[] = [
  // Guns: the agreed unlock order.
  { id: 'gun.howitzer', branch: 'guns', cost: 1200, seconds: 10 * MIN, requires: [], effect: { kind: 'gun', gun: 'howitzer' } },
  { id: 'gun.scorpion', branch: 'guns', cost: 1800, seconds: 45 * MIN, requires: ['gun.howitzer'], effect: { kind: 'gun', gun: 'scorpion' } },
  { id: 'gun.trebuchet', branch: 'guns', cost: 2600, seconds: 3 * HOUR, requires: ['gun.scorpion'], effect: { kind: 'gun', gun: 'trebuchet' } },
  { id: 'gun.greekfire', branch: 'guns', cost: 3500, seconds: 8 * HOUR, requires: ['gun.trebuchet'], effect: { kind: 'gun', gun: 'greekfire' } },
  { id: 'gun.railgun', branch: 'guns', cost: 7000, seconds: 2 * DAY, requires: ['gun.greekfire'], effect: { kind: 'gun', gun: 'railgun' } },

  // Boosts: for every gun.
  { id: 'boost.damage1', branch: 'boosts', cost: 600, seconds: 3 * MIN, requires: [], effect: { kind: 'damage', add: 0.1 } },
  { id: 'boost.gold1', branch: 'boosts', cost: 900, seconds: 15 * MIN, requires: ['boost.damage1'], effect: { kind: 'startGold', add: 100 } },
  { id: 'boost.lives1', branch: 'boosts', cost: 1200, seconds: 40 * MIN, requires: ['boost.gold1'], effect: { kind: 'lives', add: 5 } },
  { id: 'boost.damage2', branch: 'boosts', cost: 1800, seconds: 2 * HOUR, requires: ['boost.lives1'], effect: { kind: 'damage', add: 0.1 } },
  { id: 'boost.reload1', branch: 'boosts', cost: 2500, seconds: 6 * HOUR, requires: ['boost.damage2'], effect: { kind: 'reload', mul: 0.9 } },
  { id: 'boost.gold2', branch: 'boosts', cost: 3500, seconds: 16 * HOUR, requires: ['boost.reload1'], effect: { kind: 'startGold', add: 150 } },
  { id: 'boost.damage3', branch: 'boosts', cost: 4500, seconds: DAY, requires: ['boost.gold2'], effect: { kind: 'damage', add: 0.1 } },

  // Effects: one per gun, once the gun is known.
  { id: 'fx.crossbow', branch: 'effects', cost: 700, seconds: 5 * MIN, requires: [], effect: { kind: 'gunMod', gun: 'crossbow', mods: { pierce: 0.25 } } },
  { id: 'fx.zis3', branch: 'effects', cost: 1000, seconds: 20 * MIN, requires: ['fx.crossbow'], effect: { kind: 'gunMod', gun: 'zis3', mods: { range: 1, reload: 0.85 } } },
  { id: 'fx.howitzer', branch: 'effects', cost: 1600, seconds: HOUR, requires: ['gun.howitzer', 'fx.zis3'], effect: { kind: 'gunMod', gun: 'howitzer', mods: { splash: 0.4 } } },
  { id: 'fx.scorpion', branch: 'effects', cost: 2000, seconds: 4 * HOUR, requires: ['gun.scorpion', 'fx.howitzer'], effect: { kind: 'gunMod', gun: 'scorpion', mods: { passThrough: 1, pierce: 0.2 } } },
  { id: 'fx.trebuchet', branch: 'effects', cost: 3000, seconds: 12 * HOUR, requires: ['gun.trebuchet', 'fx.scorpion'], effect: { kind: 'gunMod', gun: 'trebuchet', mods: { splash: 0.5, pierce: 0.3 } } },
  { id: 'fx.greekfire', branch: 'effects', cost: 4000, seconds: DAY, requires: ['gun.greekfire', 'fx.trebuchet'], effect: { kind: 'gunMod', gun: 'greekfire', mods: { rampTime: 0.5, range: 0.5 } } },
  { id: 'fx.railgun', branch: 'effects', cost: 6000, seconds: 2 * DAY, requires: ['gun.railgun', 'fx.greekfire'], effect: { kind: 'gunMod', gun: 'railgun', mods: { reload: 0.8 } } },
];

const BY_ID = new Map(RESEARCH.map((r) => [r.id, r]));

export function researchItem(id: string): ResearchItem | undefined {
  return BY_ID.get(id);
}

export interface ResearchState {
  /** Banked gold, spent here only. */
  gold: number;
  done: string[];
  /** The item in progress and when it finishes (ms since the epoch). */
  active: { id: string; endsAt: number } | null;
}

export function newResearch(): ResearchState {
  return { gold: 0, done: [], active: null };
}

/** Repairs a state loaded from storage: unknown items and bad numbers are dropped. */
export function sanitize(raw: unknown): ResearchState {
  const s = newResearch();
  if (!raw || typeof raw !== 'object') return s;
  const r = raw as Partial<ResearchState>;
  if (typeof r.gold === 'number' && Number.isFinite(r.gold)) s.gold = Math.max(0, Math.floor(r.gold));
  if (Array.isArray(r.done)) s.done = [...new Set(r.done.filter((id): id is string => typeof id === 'string' && BY_ID.has(id)))];
  if (r.active && typeof r.active.id === 'string' && BY_ID.has(r.active.id) && Number.isFinite(r.active.endsAt) && !s.done.includes(r.active.id)) {
    s.active = { id: r.active.id, endsAt: r.active.endsAt };
  }
  return s;
}

export type ResearchStatus = 'done' | 'active' | 'ready' | 'locked';

export function status(s: ResearchState, id: string): ResearchStatus {
  if (s.done.includes(id)) return 'done';
  if (s.active?.id === id) return 'active';
  const item = BY_ID.get(id);
  return item && item.requires.every((r) => s.done.includes(r)) ? 'ready' : 'locked';
}

export type StartError = 'busy' | 'locked' | 'noGold' | 'done';

/** Why `id` cannot be started now, or null when it can. */
export function startError(s: ResearchState, id: string): StartError | null {
  const st = status(s, id);
  if (st === 'done' || st === 'active') return 'done';
  if (st === 'locked') return 'locked';
  if (s.active) return 'busy';
  if (s.gold < BY_ID.get(id)!.cost) return 'noGold';
  return null;
}

/** Pay for `id` and start its clock. `speed` > 1 shortens every timer (for testing builds). */
export function start(s: ResearchState, id: string, now: number, speed = 1): ResearchState {
  if (startError(s, id)) return s;
  const item = BY_ID.get(id)!;
  return { ...s, gold: s.gold - item.cost, active: { id, endsAt: now + (item.seconds * 1000) / speed } };
}

/** Finish the running item if its time is up. */
export function settle(s: ResearchState, now: number): ResearchState {
  if (!s.active || now < s.active.endsAt) return s;
  return { ...s, done: [...s.done, s.active.id], active: null };
}

export function bank(s: ResearchState, gold: number): ResearchState {
  return gold > 0 ? { ...s, gold: s.gold + Math.floor(gold) } : s;
}

/** Gold banked on top of the battle's takings for winning a map level. */
export function victoryBonus(level: number): number {
  return 300 + 100 * level;
}

const NO_MODS: GunMods = { damage: 1, reload: 1, range: 0, splash: 0, pierce: 0, passThrough: 0, rampTime: 1 };

/** The upgrades a set of finished items gives. */
export function upgrades(done: readonly string[], gunIds: readonly TowerId[]): Upgrades {
  const guns = new Set<TowerId>(START_GUNS);
  let damage = 1;
  let reload = 1;
  let startGold = 0;
  let lives = 0;
  const per = Object.fromEntries(gunIds.map((id) => [id, { ...NO_MODS }])) as Record<TowerId, GunMods>;
  for (const id of done) {
    const e = BY_ID.get(id)?.effect;
    if (!e) continue;
    if (e.kind === 'gun') guns.add(e.gun);
    else if (e.kind === 'damage') damage += e.add;
    else if (e.kind === 'reload') reload *= e.mul;
    else if (e.kind === 'startGold') startGold += e.add;
    else if (e.kind === 'lives') lives += e.add;
    else {
      const m = per[e.gun];
      if (!m) continue;
      m.damage *= e.mods.damage ?? 1;
      m.reload *= e.mods.reload ?? 1;
      m.range += e.mods.range ?? 0;
      m.splash += e.mods.splash ?? 0;
      m.pierce += e.mods.pierce ?? 0;
      m.passThrough += e.mods.passThrough ?? 0;
      m.rampTime *= e.mods.rampTime ?? 1;
    }
  }
  for (const m of Object.values(per)) {
    m.damage *= damage;
    m.reload *= reload;
  }
  return { guns: gunIds.filter((id) => guns.has(id)), startGold, lives, gun: per };
}
