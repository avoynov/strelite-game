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
  /** Highest gun level (1-based) each gun may be raised to in battle. */
  maxLevel: Record<TowerId, number>;
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
  | { kind: 'gunMod'; gun: TowerId; mods: Partial<GunMods> }
  | { kind: 'maxLevel'; gun: TowerId; level: number };

export type Branch = 'guns' | 'levels' | 'boosts' | 'effects';

/** Gun levels open without research; the ones above it are researched. */
export const FREE_LEVELS = 3;

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

type Effect = ResearchItem['effect'];
const item = (id: string, branch: Branch, cost: number, seconds: number, requires: string[], effect: Effect): ResearchItem => ({ id, branch, cost, seconds, requires, effect });
const gun = (g: TowerId): Effect => ({ kind: 'gun', gun: g });
const lvl = (g: TowerId, level: number): Effect => ({ kind: 'maxLevel', gun: g, level });
const mod = (g: TowerId, mods: Partial<GunMods>): Effect => ({ kind: 'gunMod', gun: g, mods });

/**
 * The tree. Guns come one by one in the agreed order; levels 4 and 5 of a gun
 * once the gun is known; each boost and effect leans on the one before it.
 * Cost and time grow the deeper an item sits. Prices follow what battles pay
 * at the map levels where an item is needed (see tests/balance.test.ts STAGES).
 */
export const RESEARCH: readonly ResearchItem[] = [
  // Guns: the agreed unlock order.
  item('gun.howitzer', 'guns', 500, 20 * MIN, [], gun('howitzer')),
  item('gun.scorpion', 'guns', 800, HOUR, ['gun.howitzer'], gun('scorpion')),
  item('gun.trebuchet', 'guns', 1500, 4 * HOUR, ['gun.scorpion'], gun('trebuchet')),
  item('gun.greekfire', 'guns', 2200, 8 * HOUR, ['gun.trebuchet'], gun('greekfire')),
  item('gun.railgun', 'guns', 4000, DAY, ['gun.greekfire'], gun('railgun')),

  // Gun levels 4 and 5 (1–3 are open from the start).
  item('lvl4.crossbow', 'levels', 400, 20 * MIN, [], lvl('crossbow', 4)),
  item('lvl4.zis3', 'levels', 450, 25 * MIN, [], lvl('zis3', 4)),
  item('lvl4.howitzer', 'levels', 900, 2 * HOUR, ['gun.howitzer'], lvl('howitzer', 4)),
  item('lvl5.crossbow', 'levels', 1200, 4 * HOUR, ['lvl4.crossbow'], lvl('crossbow', 5)),
  item('lvl5.zis3', 'levels', 1300, 4 * HOUR, ['lvl4.zis3'], lvl('zis3', 5)),
  item('lvl4.scorpion', 'levels', 1800, 8 * HOUR, ['gun.scorpion'], lvl('scorpion', 4)),
  item('lvl4.trebuchet', 'levels', 2600, 12 * HOUR, ['gun.trebuchet'], lvl('trebuchet', 4)),
  item('lvl5.howitzer', 'levels', 2800, 12 * HOUR, ['lvl4.howitzer'], lvl('howitzer', 5)),
  item('lvl4.greekfire', 'levels', 3500, DAY, ['gun.greekfire'], lvl('greekfire', 4)),
  item('lvl5.scorpion', 'levels', 3800, DAY, ['lvl4.scorpion'], lvl('scorpion', 5)),
  item('lvl4.railgun', 'levels', 5000, 2 * DAY, ['gun.railgun'], lvl('railgun', 4)),
  item('lvl5.trebuchet', 'levels', 5000, 2 * DAY, ['lvl4.trebuchet'], lvl('trebuchet', 5)),
  item('lvl5.greekfire', 'levels', 5500, 2 * DAY, ['lvl4.greekfire'], lvl('greekfire', 5)),
  item('lvl5.railgun', 'levels', 7000, 3 * DAY, ['lvl4.railgun'], lvl('railgun', 5)),

  // Boosts: for every gun.
  item('boost.gold1', 'boosts', 200, 2 * MIN, [], { kind: 'startGold', add: 100 }),
  item('boost.damage1', 'boosts', 350, 10 * MIN, ['boost.gold1'], { kind: 'damage', add: 0.1 }),
  item('boost.lives1', 'boosts', 600, 45 * MIN, ['boost.damage1'], { kind: 'lives', add: 5 }),
  item('boost.damage2', 'boosts', 1000, 2 * HOUR, ['boost.lives1'], { kind: 'damage', add: 0.1 }),
  item('boost.reload1', 'boosts', 1600, 4 * HOUR, ['boost.damage2'], { kind: 'reload', mul: 0.9 }),
  item('boost.gold2', 'boosts', 2000, 8 * HOUR, ['boost.reload1'], { kind: 'startGold', add: 150 }),
  item('boost.damage3', 'boosts', 3000, 16 * HOUR, ['boost.gold2'], { kind: 'damage', add: 0.1 }),

  // Effects: one per gun, once the gun is known.
  item('fx.crossbow', 'effects', 300, 5 * MIN, [], mod('crossbow', { pierce: 0.25 })),
  item('fx.zis3', 'effects', 600, 45 * MIN, ['fx.crossbow'], mod('zis3', { range: 1, reload: 0.85 })),
  item('fx.howitzer', 'effects', 900, 2 * HOUR, ['gun.howitzer', 'fx.zis3'], mod('howitzer', { splash: 0.4 })),
  item('fx.scorpion', 'effects', 1800, 8 * HOUR, ['gun.scorpion', 'fx.howitzer'], mod('scorpion', { passThrough: 1, pierce: 0.2 })),
  item('fx.trebuchet', 'effects', 2600, 12 * HOUR, ['gun.trebuchet', 'fx.scorpion'], mod('trebuchet', { splash: 0.5, pierce: 0.3 })),
  item('fx.greekfire', 'effects', 3500, DAY, ['gun.greekfire', 'fx.trebuchet'], mod('greekfire', { rampTime: 0.5, range: 0.5 })),
  item('fx.railgun', 'effects', 5000, 2 * DAY, ['gun.railgun', 'fx.greekfire'], mod('railgun', { reload: 0.8 })),
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
  return 100 + 40 * level;
}

/**
 * What a finished battle puts in the treasury: the gold it earned and did not
 * spend (spent is spent; the starting gold is not the battle's to give), and a
 * bonus for a win.
 */
export function battleTakings(moneyLeft: number, earned: number, won: boolean, level: number): number {
  return Math.max(0, Math.min(moneyLeft, earned)) + (won ? victoryBonus(level) : 0);
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
  const maxLevel = Object.fromEntries(gunIds.map((id) => [id, FREE_LEVELS])) as Record<TowerId, number>;
  for (const id of done) {
    const e = BY_ID.get(id)?.effect;
    if (!e) continue;
    if (e.kind === 'gun') guns.add(e.gun);
    else if (e.kind === 'damage') damage += e.add;
    else if (e.kind === 'reload') reload *= e.mul;
    else if (e.kind === 'startGold') startGold += e.add;
    else if (e.kind === 'lives') lives += e.add;
    else if (e.kind === 'maxLevel') maxLevel[e.gun] = Math.max(maxLevel[e.gun] ?? FREE_LEVELS, e.level);
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
  return { guns: gunIds.filter((id) => guns.has(id)), maxLevel, startGold, lives, gun: per };
}
