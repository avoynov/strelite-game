import { LAB_LEVELS } from './base';
import type { Targeting, TowerId } from './content';

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
}

type ItemEffect =
  | { kind: 'gun'; gun: TowerId }
  | { kind: 'damage'; add: number }
  | { kind: 'reload'; mul: number }
  | { kind: 'startGold'; add: number }
  | { kind: 'lives'; add: number }
  | { kind: 'gunMod'; gun: TowerId; mods: Partial<GunMods> }
  | { kind: 'maxLevel'; gun: TowerId; level: number }
  | { kind: 'aim'; gun: TowerId; mode: Targeting };

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
/** Headquarters level (1-based) at which an item of this price joins the tree: the deeper (dearer) the item, the higher the headquarters. */
export function hqFor(cost: number): number {
  return cost < 1000 ? 1 : cost < 2000 ? 2 : cost < 3500 ? 3 : cost < 5500 ? 4 : 5;
}

const item = (id: string, branch: Branch, cost: number, seconds: number, requires: string[], effect: Effect): ResearchItem => {
  const hq = hqFor(cost);
  return { id, branch, cost, seconds, requires, effect, ...(hq > 1 ? { hq } : {}) };
};
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

  // Aiming: targeting modes the player can set on a gun.
  item('aim.crossbow', 'effects', 700, HOUR, ['lvl4.crossbow'], { kind: 'aim', gun: 'crossbow', mode: 'smallest' }),
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
  return { gold: 0, done: [], active: [], pausedAt: null };
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
  if (s.gold < item.cost) return 'noGold';
  return null;
}

/** Real seconds an item takes; `speed` > 1 shortens every timer (testing builds). */
export function itemSeconds(item: ResearchItem, speed = 1): number {
  return item.seconds / speed;
}

/** Pay for `id` and start its clock. */
export function start(s: ResearchState, id: string, now: number, speed = 1, lab: LabInfo = FIRST_LAB): ResearchState {
  if (startError(s, id, lab)) return s;
  const item = BY_ID.get(id)!;
  return { ...s, gold: s.gold - item.cost, active: [...s.active, { id, endsAt: now + itemSeconds(item, speed) * 1000 }] };
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

const NO_MODS: GunMods = { damage: 1, reload: 1, range: 0, splash: 0, pierce: 0, passThrough: 0, rampTime: 1 };

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
  // A full set: a small bonus on top (see RESEARCH_SETS).
  const full = new Set(completeSets(done, lab));
  for (const id of gunIds) if (full.has(id)) per[id]!.damage *= 1 + MASTERY_DAMAGE;
  return { guns: gunIds.filter((id) => guns.has(id)), maxLevel, startGold, lives, gun: per, goldBonus: full.has('fortress') ? MASTERY_GOLD : 0, aims };
}

// ------------------------------------------------------------------- sets

/** The guns in the order they are unlocked: the order of the sets on the research screen. */
export const GUN_ORDER: readonly TowerId[] = ['crossbow', 'zis3', 'howitzer', 'scorpion', 'trebuchet', 'greekfire', 'railgun'];

export type SetId = TowerId | 'fortress';

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
    const aims = RESEARCH.filter((r) => r.effect.kind === 'aim' && r.effect.gun === g).map((r) => r.id);
    return { id: g, starter, items: [...(starter ? [] : [`gun.${g}`]), `lvl4.${g}`, `lvl5.${g}`, `fx.${g}`, ...aims] };
  }),
  { id: 'fortress', starter: false, items: RESEARCH.filter((r) => r.branch === 'boosts').map((r) => r.id) },
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
