import type { EnemyId } from './content';
import { ENEMIES } from './content';
import { victoryBonus } from './research';

/**
 * Reasons to come back: stars on the mission levels, veteran guns in the base
 * and a daily order. Plain data and pure functions; the app keeps the state
 * (src/progressStore.ts) and the tests drive it. All numbers are starting
 * values to tune.
 */

// ---- stars ------------------------------------------------------------------

export type StarMode = 'path' | 'arc';

export const STARS = {
  /** Each star earned for the first time pays this share of the level's win reward. */
  firstShare: 0.25,
  /** A medal every this many stars (both missions together). */
  perMedal: 25,
  /** A medal's gold: base plus a step for every medal before it. */
  medalGold: 1000,
  medalStep: 500,
} as const;

/**
 * Stars for a finished mission: 1 for the win, 2 when at least half the lives
 * are left, 3 when nothing got through at all.
 */
export function starsFor(won: boolean, lives: number, startLives: number): number {
  if (!won) return 0;
  if (lives >= startLives) return 3;
  if (lives * 2 >= startLives) return 2;
  return 1;
}

/** Gold the stars newly earned on a level pay (only stars above the best so far count). */
export function starGold(level: number, before: number, now: number): number {
  const fresh = Math.max(0, now - before);
  return Math.round(victoryBonus(level) * STARS.firstShare * fresh);
}

/** Medals a star total has earned. */
export const medalsFor = (stars: number): number => Math.floor(stars / STARS.perMedal);

/** Gold for the n-th medal (1-based). */
export const medalGold = (n: number): number => STARS.medalGold + STARS.medalStep * (n - 1);

// ---- veterans -----------------------------------------------------------------

/** Kills a base gun needs for each rank (rank 0 is a fresh gun), and what each rank adds. */
export const RANKS = [
  { kills: 0, damage: 0, hp: 0 },
  { kills: 25, damage: 0.03, hp: 0.05 },
  { kills: 100, damage: 0.06, hp: 0.1 },
  { kills: 300, damage: 0.09, hp: 0.15 },
  { kills: 1000, damage: 0.12, hp: 0.2 },
] as const;

export const MAX_RANK = RANKS.length - 1;

/** A gun's rank by the kills it has made in the base's battles. */
export function rankOf(kills: number): number {
  let r = 0;
  for (let i = 1; i < RANKS.length; i++) if (kills >= RANKS[i]!.kills) r = i;
  return r;
}

/** A destroyed gun drops one rank when rebuilt: its count falls to the start of the rank below. */
export function demoted(kills: number): number {
  const r = rankOf(kills);
  return r === 0 ? kills : RANKS[r - 1]!.kills;
}

/** Kills still to go to the next rank, or null at the top. */
export function toNextRank(kills: number): number | null {
  const r = rankOf(kills);
  return r >= MAX_RANK ? null : RANKS[r + 1]!.kills - kills;
}

// ---- daily order --------------------------------------------------------------

export type OrderKind = 'twoKinds' | 'noLeak' | 'kill' | 'winArc' | 'defend' | 'upgrade';
export const ORDER_KINDS: readonly OrderKind[] = ['twoKinds', 'noLeak', 'kill', 'winArc', 'defend', 'upgrade'];

/** Enemies a kill order can name, and how many of each. */
export const KILL_ORDERS: ReadonlyArray<readonly [EnemyId, number]> = [
  ['infantry', 60],
  ['moto', 25],
  ['truck', 15],
  ['apc', 8],
  ['tank', 5],
];

export const ORDER = {
  /** The reward is this many times the win reward of the player's highest level. */
  rewardShare: 1.5,
  /** Each day in a row adds this much, up to `maxSteps` steps. */
  streakStep: 0.1,
  maxSteps: 5,
} as const;

export interface Order {
  /** Local date, YYYY-MM-DD. */
  day: string;
  kind: OrderKind;
  /** Kill orders: what to bring down and how many. */
  enemy?: EnemyId;
  count?: number;
}

/** Today's date on the player's clock, YYYY-MM-DD: a new order every local midnight. */
export function dayKey(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Whole days from one date key to another. */
export function daysBetween(from: string, to: string): number {
  const ms = (k: string) => {
    const [y, m, d] = k.split('-').map(Number);
    return Date.UTC(y!, m! - 1, d!);
  };
  return Math.round((ms(to) - ms(from)) / 86400000);
}

/** A small fixed hash of the date, so every player gets the same order on the same day. */
function seed(day: string): number {
  let h = 2166136261;
  for (let i = 0; i < day.length; i++) {
    h ^= day.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  // Mix the low bits so neighbouring days spread out.
  h ^= h >>> 13;
  h = Math.imul(h, 0x5bd1e995);
  h ^= h >>> 15;
  return h >>> 0;
}

/** Days since 1970-01-01 of a date key. */
const dayNumber = (day: string): number => daysBetween('1970-01-01', day);

/** The kinds in a seeded shuffle for one block of days (one of each kind per block). */
function shuffled(block: number): OrderKind[] {
  const out = [...ORDER_KINDS];
  let h = seed(`block-${block}`);
  for (let i = out.length - 1; i > 0; i--) {
    h = Math.imul(h ^ (h >>> 15), 2246822519) >>> 0;
    const j = h % (i + 1);
    [out[i], out[j]] = [out[j]!, out[i]!];
  }
  return out;
}

/** A block's kinds, never opening with the kind the block before closed with (a swap at the start leaves its end alone). */
function blockKinds(block: number): OrderKind[] {
  const out = shuffled(block);
  if (out[0] === shuffled(block - 1)[out.length - 1]) [out[0], out[1]] = [out[1]!, out[0]!];
  return out;
}

/**
 * The order of a day, picked by the date alone: every player has the same one.
 * Each run of six days has every kind once, and no kind comes two days running.
 */
export function orderFor(day: string): Order {
  const n = dayNumber(day);
  const block = Math.floor(n / ORDER_KINDS.length);
  const kind = blockKinds(block)[n - block * ORDER_KINDS.length]!;
  if (kind !== 'kill') return { day, kind };
  const [enemy, count] = KILL_ORDERS[seed(day) % KILL_ORDERS.length]!;
  return { day, kind, enemy, count };
}

/**
 * The order as this player can do it: a kill order names an enemy the player
 * may not have met yet (it appears from some map level on); then it is infantry.
 */
export function orderForPlayer(order: Order, reached: number): Order {
  if (order.kind !== 'kill' || !order.enemy || ENEMIES[order.enemy].unlockLevel <= Math.max(1, reached)) return order;
  return { ...order, enemy: 'infantry', count: KILL_ORDERS[0]![1] };
}

/** What happened that may count towards the order. */
export type OrderEvent =
  | { type: 'win'; mode: StarMode; kinds: number; leaked: boolean }
  | { type: 'kill'; def: EnemyId }
  | { type: 'defend'; clean: boolean }
  | { type: 'upgrade' };

export interface OrderState {
  /** Day of the order these fields describe. */
  day: string;
  /** Kill orders: how many so far. */
  progress: number;
  done: boolean;
  /** The envelope has been opened at the muster. */
  read: boolean;
  /** Streak steps (0..maxSteps) as of the last order done. */
  steps: number;
  /** Day of the last order done, or null. */
  lastDone: string | null;
}

export function newOrderState(day: string): OrderState {
  return { day, progress: 0, done: false, read: false, steps: 0, lastDone: null };
}

/** Move the state to today: a new day brings a new sealed order; the streak is kept. */
export function rollOrder(s: OrderState, day: string): OrderState {
  if (s.day === day) return s;
  return { ...s, day, progress: 0, done: false, read: false };
}

/**
 * Streak steps if today's order is done: one more for a day in a row (up to
 * the cap); each missed day takes one step off instead, never below zero.
 */
export function stepsIfDone(s: OrderState, day: string): number {
  if (!s.lastDone) return 0;
  const gap = daysBetween(s.lastDone, day);
  if (gap <= 0) return s.steps;
  if (gap === 1) return Math.min(ORDER.maxSteps, s.steps + 1);
  return Math.max(0, s.steps - (gap - 1));
}

/** Gold for an order: 1.5× the win reward of the highest level reached, plus the streak. */
export function orderReward(highestWon: number, steps: number): number {
  return Math.round(victoryBonus(Math.max(1, highestWon)) * ORDER.rewardShare * (1 + ORDER.streakStep * Math.min(ORDER.maxSteps, steps)));
}

/** Whether an event fulfils (or, for kills, advances) the order. Returns the new progress and done flag. */
export function advanceOrder(order: Order, s: OrderState, ev: OrderEvent): { progress: number; done: boolean } {
  if (s.done) return { progress: s.progress, done: true };
  switch (order.kind) {
    case 'twoKinds':
      return { progress: 0, done: ev.type === 'win' && ev.kinds <= 2 };
    case 'noLeak':
      return { progress: 0, done: ev.type === 'win' && !ev.leaked };
    case 'winArc':
      return { progress: 0, done: ev.type === 'win' && ev.mode === 'arc' };
    case 'defend':
      return { progress: 0, done: ev.type === 'defend' && ev.clean };
    case 'upgrade':
      return { progress: 0, done: ev.type === 'upgrade' };
    case 'kill': {
      if (ev.type !== 'kill' || ev.def !== order.enemy) return { progress: s.progress, done: false };
      const progress = s.progress + 1;
      return { progress, done: progress >= (order.count ?? 1) };
    }
  }
}

export function sanitizeOrder(raw: unknown, day: string): OrderState {
  const s = newOrderState(day);
  if (!raw || typeof raw !== 'object') return s;
  const r = raw as Record<string, unknown>;
  const isDay = (v: unknown): v is string => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v);
  const out: OrderState = {
    day: isDay(r.day) ? r.day : day,
    progress: typeof r.progress === 'number' && r.progress >= 0 ? Math.floor(r.progress) : 0,
    done: r.done === true,
    read: r.read === true,
    steps: typeof r.steps === 'number' ? Math.max(0, Math.min(ORDER.maxSteps, Math.floor(r.steps))) : 0,
    lastDone: isDay(r.lastDone) ? r.lastDone : null,
  };
  return rollOrder(out, day);
}
