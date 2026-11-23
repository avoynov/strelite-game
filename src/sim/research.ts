import { LAB_LEVELS } from './base';
import type { Targeting, TowerId } from './content';
import { TRAP_IDS, type TrapId } from './traps';

/**
 * Research tree: gold banked from battles buys guns, boosts and effects. Each
 * item costs gold and takes real time. The laboratory in the player's base
 * decides how many run at once, and the deeper items need it raised (it never
 * makes research faster); while it lies destroyed, research stands still. The state is plain
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
  /** Flash: multiplies how long it stuns. */
  stun: number;
  /** Flash: radians added to the cone's half-angle. */
  cone: number;
  /** Flash: damage the big flash deals (at level 1; it grows with the level). */
  flashDamage: number;
  /** Flash: every this many flashes is a big one (0: the gun's own, every third). */
  bigEvery: number;
  /** Disc: more bounces. */
  bounces: number;
  /** Disc: added to the share lost per bounce (negative: less lost). */
  bounceLoss: number;
  /** Share more gold for every kill the gun makes. */
  killGold: number;
  /** Lens: seconds between moving on to the healthiest (0: the gun's own). */
  retarget: number;
  /** Harpoon: the hook slows its target (1 when researched). */
  spool: number;
  /** Darts: more per burst. */
  darts: number;
}

export interface Upgrades {
  guns: readonly TowerId[];
  /** Highest gun level (1-based) each gun may be raised to in battle. */
  maxLevel: Record<TowerId, number>;
  startGold: number;
  lives: number;
  /** Per gun, boosts for every gun already folded in. */
  gun: Record<TowerId, GunMods>;
  /** Share added to the gold a battle banks (the full Fortress set). */
  goldBonus: number;
  /** Targeting modes research opened per gun, on top of the gun's own. */
  aims: Record<TowerId, Targeting[]>;
  /** Per trap, what its action is multiplied by (its levels, and the full set). */
  traps: Record<TrapId, number>;
  /** Per trap, the level research has raised it to (1 with none); it picks the trap's look. */
  trapLevels: Record<TrapId, number>;
  /** Greek fire lights tar patches. */
  burningTar: boolean;
}

type ItemEffect =
  | { kind: 'gun'; gun: TowerId }
  | { kind: 'damage'; add: number }
  | { kind: 'reload'; mul: number }
  | { kind: 'startGold'; add: number }
  | { kind: 'lives'; add: number }
  | { kind: 'gunMod'; gun: TowerId; mods: Partial<GunMods> }
  | { kind: 'maxLevel'; gun: TowerId; level: number }
  | { kind: 'aim'; gun: TowerId; mode: Targeting }
  | { kind: 'trap'; trap: TrapId; level: number; add: number }
  | { kind: 'burningTar' };

export type Branch = 'guns' | 'levels' | 'boosts' | 'effects' | 'traps';

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
  /**
   * Headquarters level (1-based) at which it joins the tree, when above 1;
   * the laboratory must stand at least as high to research it. Raising the
   * headquarters widens the tree and lets the laboratory rise further.
   */
  hq?: number;
}

const MIN = 60;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

type Effect = ResearchItem['effect'];

/**
 * The tree comes in nine acts, one per headquarters level: an item joins the
 * tree with its act's headquarters, and the laboratory must stand at least as
 * high to research it. A gun's level IV also needs laboratory 3 and its level
 * V laboratory 6, so nobody researches a level the headquarters cannot allow yet.
 */
export const ACTS = 9;
export const LEVEL4_LAB = 3;
export const LEVEL5_LAB = 6;

const item = (id: string, branch: Branch, act: number, cost: number, seconds: number, requires: string[], effect: Effect): ResearchItem => ({
  id,
  branch,
  cost,
  seconds,
  requires,
  effect,
  ...(act > 1 ? { hq: act } : {}),
});
const gun = (g: TowerId): Effect => ({ kind: 'gun', gun: g });
const lvl = (g: TowerId, level: number): Effect => ({ kind: 'maxLevel', gun: g, level });
const mod = (g: TowerId, mods: Partial<GunMods>): Effect => ({ kind: 'gunMod', gun: g, mods });
const lvl4 = (g: TowerId, act: number, cost: number, seconds: number, requires: string[]) => item(`lvl4.${g}`, 'levels', Math.max(act, LEVEL4_LAB), cost, seconds, requires, lvl(g, 4));
const lvl5 = (g: TowerId, act: number, cost: number, seconds: number) => item(`lvl5.${g}`, 'levels', Math.max(act, LEVEL5_LAB), cost, seconds, [`lvl4.${g}`], lvl(g, 5));
/** Levels past V (only guns whose art has them): each needs the one before, in the act of the last headquarters. */
const lvlUp = (g: TowerId, level: number, cost: number, seconds: number) => item(`lvl${level}.${g}`, 'levels', LAB_LEVELS.length, cost, seconds, [`lvl${level - 1}.${g}`], lvl(g, level));
/** A trap's level II or III: +60% to what it does, in the act its headquarters brings it. */
const TRAP_STEP = 0.6;
const trapLvl = (tr: TrapId, act: number, level: 2 | 3 | 4, cost: number, seconds: number) =>
  item(`trap.${tr}.${level}`, 'traps', act, cost, seconds, level > 2 ? [`trap.${tr}.${level - 1}`] : [], { kind: 'trap', trap: tr, level, add: TRAP_STEP });

/**
 * The tree. Guns come one by one in the agreed order, each in its act; levels
 * 4 and 5 of a gun once the gun is known; each boost and effect leans on the
 * one before it. Cost and time grow the deeper an item sits. Prices follow
 * what battles pay at the map levels where an item is needed (see
 * tests/balance.test.ts STAGES).
 */
export const RESEARCH: readonly ResearchItem[] = [
  // Guns: the agreed unlock order, act by act.
  item('gun.howitzer', 'guns', 1, 500, 20 * MIN, [], gun('howitzer')),
  item('gun.scorpion', 'guns', 1, 800, HOUR, ['gun.howitzer'], gun('scorpion')),
  item('gun.zadnoper', 'guns', 2, 1100, 2 * HOUR, ['gun.scorpion'], gun('zadnoper')),
  item('gun.trebuchet', 'guns', 3, 1500, 4 * HOUR, ['gun.zadnoper'], gun('trebuchet')),
  item('gun.flasher', 'guns', 3, 1900, 6 * HOUR, ['gun.trebuchet'], gun('flasher')),
  item('gun.rockets', 'guns', 4, 2300, 8 * HOUR, ['gun.flasher'], gun('rockets')),
  item('gun.tarkan', 'guns', 5, 2700, 10 * HOUR, ['gun.rockets'], gun('tarkan')),
  item('gun.greekfire', 'guns', 5, 3200, 14 * HOUR, ['gun.tarkan'], gun('greekfire')),
  item('gun.ricochet', 'guns', 6, 3800, 18 * HOUR, ['gun.greekfire'], gun('ricochet')),
  item('gun.railgun', 'guns', 7, 4600, DAY, ['gun.ricochet'], gun('railgun')),
  item('gun.glass', 'guns', 7, 5600, 1.5 * DAY, ['gun.railgun'], gun('glass')),
  item('gun.harpoon', 'guns', 8, 6600, 2 * DAY, ['gun.glass'], gun('harpoon')),
  item('gun.bees', 'guns', 9, 8000, 3 * DAY, ['gun.harpoon'], gun('bees')),

  // Gun levels 4 and 5 (1–3 are open from the start).
  lvl4('crossbow', 1, 400, 20 * MIN, []),
  lvl4('zis3', 1, 450, 25 * MIN, []),
  lvl4('howitzer', 1, 900, 2 * HOUR, ['gun.howitzer']),
  lvl5('crossbow', 1, 1200, 4 * HOUR),
  lvl5('zis3', 1, 1300, 4 * HOUR),
  lvl4('scorpion', 1, 1800, 8 * HOUR, ['gun.scorpion']),
  lvl4('trebuchet', 3, 2600, 12 * HOUR, ['gun.trebuchet']),
  lvl5('howitzer', 1, 2800, 12 * HOUR),
  lvl4('greekfire', 5, 4500, DAY, ['gun.greekfire']),
  lvl5('scorpion', 1, 3800, DAY),
  lvl4('railgun', 7, 6000, 2 * DAY, ['gun.railgun']),
  lvl5('trebuchet', 3, 5000, 2 * DAY),
  lvl5('greekfire', 5, 6500, 2.5 * DAY),
  lvl5('railgun', 7, 8000, 3.5 * DAY),
  lvl4('zadnoper', 2, 2000, 8 * HOUR, ['gun.zadnoper']),
  lvl5('zadnoper', 2, 3600, DAY),
  lvl4('flasher', 3, 3000, 12 * HOUR, ['gun.flasher']),
  lvl5('flasher', 3, 4800, 1.5 * DAY),
  lvl4('rockets', 4, 3400, 16 * HOUR, ['gun.rockets']),
  lvl5('rockets', 4, 5200, 2 * DAY),
  lvl4('tarkan', 5, 3800, 18 * HOUR, ['gun.tarkan']),
  lvl5('tarkan', 5, 5600, 2 * DAY),
  lvl4('ricochet', 6, 5000, 1.5 * DAY, ['gun.ricochet']),
  lvl5('ricochet', 6, 7000, 3 * DAY),
  lvl4('glass', 7, 7000, 2.5 * DAY, ['gun.glass']),
  lvl5('glass', 7, 9000, 4 * DAY),
  lvl4('harpoon', 8, 8000, 3 * DAY, ['gun.harpoon']),
  lvl5('harpoon', 8, 10000, 4 * DAY),
  lvlUp('harpoon', 6, 13000, 5 * DAY),
  lvlUp('harpoon', 7, 16000, 6 * DAY),
  lvl4('bees', 9, 10000, 4 * DAY, ['gun.bees']),
  lvl5('bees', 9, 12500, 5 * DAY),

  // Boosts: for every gun.
  item('boost.gold1', 'boosts', 1, 200, 2 * MIN, [], { kind: 'startGold', add: 100 }),
  item('boost.damage1', 'boosts', 1, 350, 10 * MIN, ['boost.gold1'], { kind: 'damage', add: 0.1 }),
  item('boost.lives1', 'boosts', 1, 600, 45 * MIN, ['boost.damage1'], { kind: 'lives', add: 5 }),
  item('boost.damage2', 'boosts', 2, 1000, 2 * HOUR, ['boost.lives1'], { kind: 'damage', add: 0.1 }),
  item('boost.reload1', 'boosts', 3, 1600, 4 * HOUR, ['boost.damage2'], { kind: 'reload', mul: 0.9 }),
  item('boost.gold2', 'boosts', 3, 2000, 8 * HOUR, ['boost.reload1'], { kind: 'startGold', add: 150 }),
  item('boost.damage3', 'boosts', 4, 3000, 16 * HOUR, ['boost.gold2'], { kind: 'damage', add: 0.1 }),

  // Effects: one per gun, once the gun is known.
  item('fx.crossbow', 'effects', 1, 300, 5 * MIN, [], mod('crossbow', { pierce: 0.25 })),
  item('fx.zis3', 'effects', 1, 600, 45 * MIN, ['fx.crossbow'], mod('zis3', { range: 1, reload: 0.85 })),
  item('fx.howitzer', 'effects', 1, 900, 2 * HOUR, ['gun.howitzer', 'fx.zis3'], mod('howitzer', { splash: 0.4 })),
  item('fx.scorpion', 'effects', 2, 1800, 8 * HOUR, ['gun.scorpion', 'fx.howitzer'], mod('scorpion', { passThrough: 1, pierce: 0.2 })),
  item('fx.trebuchet', 'effects', 3, 2600, 12 * HOUR, ['gun.trebuchet', 'fx.scorpion'], mod('trebuchet', { splash: 0.5, pierce: 0.3 })),
  item('fx.greekfire', 'effects', 5, 4500, DAY, ['gun.greekfire', 'fx.trebuchet'], mod('greekfire', { rampTime: 0.5, range: 0.5 })),
  item('fx.railgun', 'effects', 7, 6000, 2 * DAY, ['gun.railgun', 'fx.greekfire'], mod('railgun', { reload: 0.8 })),
  item('fx.zadnoper', 'effects', 2, 2000, 8 * HOUR, ['gun.zadnoper'], mod('zadnoper', { pierce: 0.3, range: 1 })),
  item('fx.flasher', 'effects', 3, 2400, 10 * HOUR, ['gun.flasher'], mod('flasher', { cone: (15 * Math.PI) / 180 })),
  item('fx.flasher.stun', 'effects', 3, 3000, 12 * HOUR, ['fx.flasher'], mod('flasher', { stun: 1.4 })),
  item('fx.flasher.fire', 'effects', 3, 3600, DAY, ['fx.flasher.stun'], mod('flasher', { flashDamage: 40 })),
  item('fx.flasher.rhythm', 'effects', 3, 4800, 1.5 * DAY, ['fx.flasher.fire'], mod('flasher', { bigEvery: 2 })),
  item('fx.rockets', 'effects', 4, 3400, 16 * HOUR, ['gun.rockets'], mod('rockets', { splash: 0.4, pierce: 0.2 })),
  item('fx.tarkan', 'effects', 5, 3800, 18 * HOUR, ['gun.tarkan'], mod('tarkan', { killGold: 0.2 })),
  item('fx.ricochet', 'effects', 6, 5000, 1.5 * DAY, ['gun.ricochet'], mod('ricochet', { bounces: 1, bounceLoss: -0.05 })),
  item('fx.glass', 'effects', 7, 7000, 2.5 * DAY, ['gun.glass'], mod('glass', { retarget: 8 })),
  item('fx.glass.2', 'effects', 7, 9000, 4 * DAY, ['fx.glass'], mod('glass', { retarget: 6 })),
  item('fx.harpoon', 'effects', 8, 8000, 3 * DAY, ['gun.harpoon'], mod('harpoon', { spool: 1 })),
  item('fx.bees', 'effects', 9, 10000, 4 * DAY, ['gun.bees'], mod('bees', { darts: 4, reload: 0.85 })),

  // Traps: each kind's levels II and III, then the set's effect.
  trapLvl('mine', 2, 2, 900, HOUR),
  trapLvl('mine', 2, 3, 2000, 8 * HOUR),
  trapLvl('mine', 4, 4, 3000, 12 * HOUR),
  trapLvl('pit', 4, 2, 1800, 6 * HOUR),
  trapLvl('pit', 4, 3, 3200, 14 * HOUR),
  trapLvl('leg', 6, 2, 3000, 12 * HOUR),
  trapLvl('leg', 6, 3, 4600, DAY),
  trapLvl('tar', 8, 2, 4500, DAY),
  trapLvl('tar', 8, 3, 6500, 2 * DAY),
  item('fx.tar', 'traps', 8, 5500, 1.5 * DAY, ['trap.tar.2', 'gun.greekfire'], { kind: 'burningTar' }),
  // Aiming: targeting modes the player can set on a gun.
  item('aim.crossbow', 'effects', 3, 700, HOUR, ['lvl4.crossbow'], { kind: 'aim', gun: 'crossbow', mode: 'weakest' }),
];

const BY_ID = new Map(RESEARCH.map((r) => [r.id, r]));

export function researchItem(id: string): ResearchItem | undefined {
  return BY_ID.get(id);
}

export interface ActiveItem {
  id: string;
  /** ms since the epoch. */
  endsAt: number;
}

export interface ResearchState {
  /** The treasury: banked gold, spent on research and on the base. */
  gold: number;
  done: string[];
  /** Items in progress and when they finish. */
  active: ActiveItem[];
  /** When the laboratory was destroyed (clocks stand still), or null while it stands. */
  pausedAt: number | null;
  /** Items a destroyed laboratory lost: done again for half the gold and half the time. */
  halfPrice: string[];
}

/**
 * The base as research sees it: the laboratory's 0-based level and whether it
 * stands, and the headquarters' 0-based level (how far the tree reaches).
 */
export interface LabInfo {
  level: number;
  standing: boolean;
  /** Headquarters level, 0-based. Absent: the whole tree (tests, tools). */
  hq?: number;
}

export const FIRST_LAB: LabInfo = { level: 0, standing: true, hq: 0 };
/** Every item in the tree (pure tests and tools). */
export const WHOLE_TREE: LabInfo = { level: 0, standing: true };

/** Whether an item is part of the tree at this headquarters level; finished items always stay. */
export function inTree(id: string, lab: LabInfo, done: readonly string[] = []): boolean {
  const item = BY_ID.get(id);
  if (!item) return false;
  return lab.hq === undefined || (item.hq ?? 1) <= lab.hq + 1 || done.includes(id);
}

export function newResearch(): ResearchState {
  return { gold: 0, done: [], active: [], pausedAt: null, halfPrice: [] };
}

/** Repairs a state loaded from storage: unknown items and bad numbers are dropped. */
export function sanitize(raw: unknown): ResearchState {
  const s = newResearch();
  if (!raw || typeof raw !== 'object') return s;
  const r = raw as Partial<ResearchState>;
  if (typeof r.gold === 'number' && Number.isFinite(r.gold)) s.gold = Math.max(0, Math.floor(r.gold));
  if (Array.isArray(r.done)) s.done = [...new Set(r.done.filter((id): id is string => typeof id === 'string' && BY_ID.has(id)))];
  // Older saves kept a single item.
  const list: unknown[] = Array.isArray(r.active) ? r.active : r.active ? [r.active] : [];
  for (const a of list) {
    if (!a || typeof a !== 'object') continue;
    const { id, endsAt } = a as Partial<ActiveItem>;
    if (typeof id === 'string' && BY_ID.has(id) && typeof endsAt === 'number' && Number.isFinite(endsAt) && !s.done.includes(id) && !s.active.some((o) => o.id === id)) {
      s.active.push({ id, endsAt });
    }
  }
  if (typeof r.pausedAt === 'number' && Number.isFinite(r.pausedAt)) s.pausedAt = r.pausedAt;
  if (Array.isArray(r.halfPrice)) s.halfPrice = r.halfPrice.filter((id): id is string => typeof id === 'string' && BY_ID.has(id) && !s.done.includes(id));
  return s;
}

export type ResearchStatus = 'done' | 'active' | 'ready' | 'locked';

export function status(s: ResearchState, id: string): ResearchStatus {
  if (s.done.includes(id)) return 'done';
  if (s.active.some((a) => a.id === id)) return 'active';
  const item = BY_ID.get(id);
  return item && item.requires.every((r) => s.done.includes(r)) ? 'ready' : 'locked';
}

export type StartError = 'busy' | 'locked' | 'noGold' | 'done' | 'noLab' | 'hqLevel' | 'labLevel';

/** Items the laboratory runs at once. */
export const labSlots = (lab: LabInfo): number => LAB_LEVELS[lab.level]?.slots ?? 1;

/** Why `id` cannot be started now, or null when it can. */
export function startError(s: ResearchState, id: string, lab: LabInfo = FIRST_LAB): StartError | null {
  const st = status(s, id);
  if (st === 'done' || st === 'active') return 'done';
  if (st === 'locked') return 'locked';
  const item = BY_ID.get(id)!;
  if (!lab.standing) return 'noLab';
  if (!inTree(id, lab, s.done)) return 'hqLevel';
  // The deepest items also need a laboratory raised as far (and the headquarters caps the laboratory).
  if ((item.hq ?? 1) > lab.level + 1) return 'labLevel';
  if (s.active.length >= labSlots(lab)) return 'busy';
  if (s.gold < itemCost(item, s)) return 'noGold';
  return null;
}

/** Real seconds an item takes; `speed` > 1 shortens every timer (testing builds). */
export function itemSeconds(item: ResearchItem, speed = 1, s?: ResearchState): number {
  return (item.seconds * (s?.halfPrice.includes(item.id) ? 0.5 : 1)) / speed;
}

/** Gold an item costs: half for one a destroyed laboratory lost. */
export function itemCost(item: ResearchItem, s?: ResearchState): number {
  return s?.halfPrice.includes(item.id) ? Math.ceil(item.cost / 2) : item.cost;
}

/**
 * The laboratory was destroyed: the research running in it is lost, gold and
 * all. With nothing running, the last item finished is lost instead, but it
 * can be done again for half the gold and half the time. Guns it opened stay
 * on the field; new ones cannot be built until it is done again.
 */
export function labDestroyed(s: ResearchState): { state: ResearchState; lost: string[] } {
  if (s.active.length) return { state: { ...s, active: [] }, lost: s.active.map((a) => a.id) };
  const last = s.done[s.done.length - 1];
  if (!last) return { state: s, lost: [] };
  return { state: { ...s, done: s.done.slice(0, -1), halfPrice: [...s.halfPrice.filter((id) => id !== last), last] }, lost: [last] };
}

/** Pay for `id` and start its clock. */
export function start(s: ResearchState, id: string, now: number, speed = 1, lab: LabInfo = FIRST_LAB): ResearchState {
  if (startError(s, id, lab)) return s;
  const item = BY_ID.get(id)!;
  return {
    ...s,
    gold: s.gold - itemCost(item, s),
    active: [...s.active, { id, endsAt: now + itemSeconds(item, speed, s) * 1000 }],
    halfPrice: s.halfPrice.filter((h) => h !== id),
  };
}

/** Finish the running items whose time is up (nothing moves while the laboratory lies destroyed). */
export function settle(s: ResearchState, now: number): ResearchState {
  if (s.pausedAt !== null) return s;
  const done = s.active.filter((a) => a.endsAt <= now);
  if (!done.length) return s;
  return { ...s, done: [...s.done, ...done.map((a) => a.id)], active: s.active.filter((a) => a.endsAt > now) };
}

/** The laboratory was destroyed: the clocks stop. */
export function pause(s: ResearchState, now: number): ResearchState {
  return s.pausedAt !== null ? s : { ...settle(s, now), pausedAt: now };
}

/** The laboratory stands again: the clocks go on from where they stopped. */
export function resume(s: ResearchState, now: number): ResearchState {
  if (s.pausedAt === null) return s;
  const gap = Math.max(0, now - s.pausedAt);
  return { ...s, pausedAt: null, active: s.active.map((a) => ({ ...a, endsAt: a.endsAt + gap })) };
}

/** Take gold out of the treasury (the base's spending); never below zero. */
export function setGold(s: ResearchState, gold: number): ResearchState {
  const g = Math.max(0, Math.floor(gold));
  return g === s.gold ? s : { ...s, gold: g };
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

const NO_MODS: GunMods = { damage: 1, reload: 1, range: 0, splash: 0, pierce: 0, passThrough: 0, rampTime: 1, stun: 1, cone: 0, flashDamage: 0, bigEvery: 0, bounces: 0, bounceLoss: 0, killGold: 0, retarget: 0, spool: 0, darts: 0 };

/** The upgrades a set of finished items gives. */
export function upgrades(done: readonly string[], gunIds: readonly TowerId[], lab: LabInfo = WHOLE_TREE): Upgrades {
  const guns = new Set<TowerId>(START_GUNS);
  let damage = 1;
  let reload = 1;
  let startGold = 0;
  let lives = 0;
  const per = Object.fromEntries(gunIds.map((id) => [id, { ...NO_MODS }])) as Record<TowerId, GunMods>;
  const maxLevel = Object.fromEntries(gunIds.map((id) => [id, FREE_LEVELS])) as Record<TowerId, number>;
  const aims = Object.fromEntries(gunIds.map((id) => [id, [] as Targeting[]])) as Record<TowerId, Targeting[]>;
  const traps = Object.fromEntries(TRAP_IDS.map((id) => [id, 1])) as Record<TrapId, number>;
  const trapLevels = Object.fromEntries(TRAP_IDS.map((id) => [id, 1])) as Record<TrapId, number>;
  let burningTar = false;
  for (const id of done) {
    const e = BY_ID.get(id)?.effect;
    if (!e) continue;
    if (e.kind === 'gun') guns.add(e.gun);
    else if (e.kind === 'damage') damage += e.add;
    else if (e.kind === 'reload') reload *= e.mul;
    else if (e.kind === 'startGold') startGold += e.add;
    else if (e.kind === 'lives') lives += e.add;
    else if (e.kind === 'maxLevel') maxLevel[e.gun] = Math.max(maxLevel[e.gun] ?? FREE_LEVELS, e.level);
    else if (e.kind === 'aim') {
      if (aims[e.gun] && !aims[e.gun]!.includes(e.mode)) aims[e.gun]!.push(e.mode);
    }
    else if (e.kind === 'trap') {
      traps[e.trap] += e.add;
      trapLevels[e.trap] = Math.max(trapLevels[e.trap], e.level);
    }
    else if (e.kind === 'burningTar') burningTar = true;
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
      m.stun *= e.mods.stun ?? 1;
      m.cone += e.mods.cone ?? 0;
      m.flashDamage += e.mods.flashDamage ?? 0;
      if (e.mods.bigEvery) m.bigEvery = m.bigEvery ? Math.min(m.bigEvery, e.mods.bigEvery) : e.mods.bigEvery;
      m.bounces += e.mods.bounces ?? 0;
      m.bounceLoss += e.mods.bounceLoss ?? 0;
      m.killGold += e.mods.killGold ?? 0;
      if (e.mods.retarget) m.retarget = m.retarget ? Math.min(m.retarget, e.mods.retarget) : e.mods.retarget;
      m.spool += e.mods.spool ?? 0;
      m.darts += e.mods.darts ?? 0;
    }
  }
  for (const m of Object.values(per)) {
    m.damage *= damage;
    m.reload *= reload;
  }
  // A full set: a small bonus on top (see RESEARCH_SETS).
  const full = new Set(completeSets(done, lab));
  for (const id of gunIds) if (full.has(id)) per[id]!.damage *= 1 + MASTERY_DAMAGE;
  if (full.has('traps')) for (const id of TRAP_IDS) traps[id] *= 1 + MASTERY_DAMAGE;
  return { guns: gunIds.filter((id) => guns.has(id)), maxLevel, startGold, lives, gun: per, goldBonus: full.has('fortress') ? MASTERY_GOLD : 0, aims, traps, trapLevels, burningTar };
}

// ------------------------------------------------------------------- sets

/** The guns in the order they are unlocked: the order of the sets on the research screen. */
export const GUN_ORDER: readonly TowerId[] = ['crossbow', 'zis3', 'howitzer', 'scorpion', 'zadnoper', 'trebuchet', 'flasher', 'rockets', 'tarkan', 'greekfire', 'ricochet', 'railgun', 'glass', 'harpoon', 'bees'];

export type SetId = TowerId | 'fortress' | 'traps';

/**
 * A set the player completes for a medal: each gun (the gun, levels 4 and 5,
 * its effect, any aiming modes) and the Fortress (every boost). A starting gun's unlock is no
 * research item but counts as done, so the tree never starts at zero.
 */
export interface ResearchSet {
  id: SetId;
  /** The gun is there from the start. */
  starter: boolean;
  /** Research items, in the order they are shown. */
  items: readonly string[];
}

export const RESEARCH_SETS: readonly ResearchSet[] = [
  ...GUN_ORDER.map((g): ResearchSet => {
    const starter = START_GUNS.includes(g);
    const fx = RESEARCH.filter((r) => r.branch === 'effects' && 'gun' in r.effect && r.effect.gun === g).map((r) => r.id);
    const more = RESEARCH.filter((r) => r.effect.kind === 'maxLevel' && r.effect.gun === g && r.effect.level > 5).map((r) => r.id);
    return { id: g, starter, items: [...(starter ? [] : [`gun.${g}`]), `lvl4.${g}`, `lvl5.${g}`, ...more, ...fx] };
  }),
  { id: 'fortress', starter: false, items: RESEARCH.filter((r) => r.branch === 'boosts').map((r) => r.id) },
  { id: 'traps', starter: false, items: RESEARCH.filter((r) => r.branch === 'traps').map((r) => r.id) },
];

/** A full gun set: this much more damage for that gun. */
export const MASTERY_DAMAGE = 0.05;
/** The full Fortress set: this share more gold banked from every battle. */
export const MASTERY_GOLD = 0.05;

export interface Progress {
  done: number;
  total: number;
}

/** How far a set is: a starting gun counts as one done. */
/** A set's pieces in the tree at this headquarters level. */
export function setItems(set: ResearchSet, lab: LabInfo = WHOLE_TREE, done: readonly string[] = []): string[] {
  return set.items.filter((id) => inTree(id, lab, done));
}

/** How far a set is, counting only the pieces in the tree now: a starting gun counts as one done. */
export function setProgress(set: ResearchSet, done: readonly string[], lab: LabInfo = WHOLE_TREE): Progress {
  const extra = set.starter ? 1 : 0;
  const items = setItems(set, lab, done);
  return { done: extra + items.filter((id) => done.includes(id)).length, total: extra + items.length };
}

/**
 * The sets with every piece in the tree done. A set can be full at one
 * headquarters level and open again at the next, when the tree has grown.
 */
export function completeSets(done: readonly string[], lab: LabInfo = WHOLE_TREE): SetId[] {
  return RESEARCH_SETS.filter((set) => {
    const items = setItems(set, lab, done);
    return items.length > 0 && items.every((id) => done.includes(id));
  }).map((set) => set.id);
}

/** The tree at this headquarters level: every set's pieces in it together. */
export function treeProgress(done: readonly string[], lab: LabInfo = WHOLE_TREE): Progress {
  let d = 0;
  let total = 0;
  for (const set of RESEARCH_SETS) {
    const p = setProgress(set, done, lab);
    d += p.done;
    total += p.total;
  }
  return { done: d, total };
}

/** The set an item belongs to. */
export function setOf(id: string): ResearchSet | undefined {
  return RESEARCH_SETS.find((set) => set.items.includes(id));
}

/**
 * What to research next: of the items that can start now, the one that brings
 * a set closest to its medal, then the cheapest. When none can start, the
 * cheapest item the laboratory could run once there is gold and a free place.
 * Null when there is none.
 */
export function suggestNext(s: ResearchState, lab: LabInfo = FIRST_LAB): string | null {
  const left = (id: string) => {
    const set = setOf(id);
    if (!set) return Infinity;
    const p = setProgress(set, s.done, lab);
    return p.total - p.done;
  };
  const byGoal = (a: ResearchItem, b: ResearchItem) => left(a.id) - left(b.id) || a.cost - b.cost;
  const now = RESEARCH.filter((r) => startError(s, r.id, lab) === null).sort(byGoal);
  if (now.length) return now[0]!.id;
  const later = RESEARCH.filter((r) => status(s, r.id) === 'ready' && inTree(r.id, lab, s.done) && (r.hq ?? 1) <= lab.level + 1).sort((a, b) => a.cost - b.cost);
  return later[0]?.id ?? null;
}
