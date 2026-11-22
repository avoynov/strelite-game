import {
  advanceOrder,
  dayKey,
  medalGold,
  medalsFor,
  orderFor,
  orderForPlayer,
  orderReward,
  rollOrder,
  sanitizeOrder,
  starGold,
  stepsIfDone,
  type Order,
  type OrderEvent,
  type OrderState,
  type StarMode,
} from './sim/progress';

const STARS_KEY = 'strelite.stars';
const ORDER_KEY = 'strelite.order';

function read(key: string): unknown {
  try {
    return JSON.parse(localStorage.getItem(key) ?? 'null');
  } catch {
    return null;
  }
}

function write(key: string, v: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(v));
  } catch {
    // Blocked storage: it lasts for this visit only.
  }
}

interface StarsSave {
  path: Record<string, number>;
  arc: Record<string, number>;
  /** Medals already paid out. */
  medals: number;
}

function sanitizeStars(raw: unknown): StarsSave {
  const out: StarsSave = { path: {}, arc: {}, medals: 0 };
  if (!raw || typeof raw !== 'object') return out;
  const r = raw as Record<string, unknown>;
  for (const m of ['path', 'arc'] as const) {
    const src = r[m];
    if (!src || typeof src !== 'object') continue;
    for (const [k, v] of Object.entries(src as Record<string, unknown>)) {
      const level = Number(k);
      if (Number.isInteger(level) && level >= 1 && typeof v === 'number' && v >= 1) out[m][String(level)] = Math.min(3, Math.floor(v));
    }
  }
  out.medals = typeof r.medals === 'number' && r.medals > 0 ? Math.floor(r.medals) : 0;
  return out;
}

/** What a finished mission earned in stars. */
export interface StarResult {
  stars: number;
  /** Best before this battle. */
  before: number;
  gold: number;
  /** Medals newly earned, with their gold. */
  medals: number[];
}

/** What finishing today's order paid. */
export interface OrderPaid {
  gold: number;
  steps: number;
}

/** Stars per level, medals and the daily order, kept in the browser. */
export class ProgressStore {
  private stars: StarsSave;
  private orderState: OrderState;

  constructor(private readonly clock: () => Date = () => new Date()) {
    this.stars = sanitizeStars(read(STARS_KEY));
    this.orderState = sanitizeOrder(read(ORDER_KEY), dayKey(clock()));
  }

  // ---- stars ----------------------------------------------------------------

  starsOf(mode: StarMode, level: number): number {
    return this.stars[mode][String(level)] ?? 0;
  }

  totalStars(): number {
    let n = 0;
    for (const m of ['path', 'arc'] as const) for (const v of Object.values(this.stars[m])) n += v;
    return n;
  }

  get medals(): number {
    return this.stars.medals;
  }

  /** Record a finished mission; pays the stars that are new and any medal they complete. */
  recordStars(mode: StarMode, level: number, stars: number): StarResult {
    const before = this.starsOf(mode, level);
    const out: StarResult = { stars, before, gold: 0, medals: [] };
    if (stars <= before) return out;
    out.gold = starGold(level, before, stars);
    this.stars[mode][String(level)] = stars;
    const earned = medalsFor(this.totalStars());
    while (this.stars.medals < earned) {
      this.stars.medals++;
      out.medals.push(medalGold(this.stars.medals));
    }
    write(STARS_KEY, this.stars);
    return out;
  }

  // ---- daily order ----------------------------------------------------------

  private today(): string {
    return dayKey(this.clock());
  }

  /** Bring the order up to today (a new one is sealed at local midnight). True when it changed. */
  roll(): boolean {
    const next = rollOrder(this.orderState, this.today());
    if (next === this.orderState) return false;
    this.orderState = next;
    write(ORDER_KEY, next);
    return true;
  }

  get state(): OrderState {
    this.roll();
    return this.orderState;
  }

  /** Today's order as this player can fight it (`reached`: the highest map level they can play). */
  order(reached: number): Order {
    return orderForPlayer(orderFor(this.state.day), reached);
  }

  /** Gold today's order pays if done now, and the streak steps it would count. */
  reward(highestWon: number): OrderPaid {
    const steps = stepsIfDone(this.state, this.state.day);
    return { gold: orderReward(highestWon, steps), steps };
  }

  /** Open the envelope at the muster. */
  markRead(): void {
    if (this.state.read) return;
    this.orderState = { ...this.orderState, read: true };
    write(ORDER_KEY, this.orderState);
  }

  /** Count an event; when it finishes today's order, the reward (null otherwise). */
  report(ev: OrderEvent, reached: number, highestWon: number): OrderPaid | null {
    const s = this.state;
    if (s.done) return null;
    const r = advanceOrder(this.order(reached), s, ev);
    if (r.progress === s.progress && !r.done) return null;
    if (!r.done) {
      this.orderState = { ...s, progress: r.progress };
      write(ORDER_KEY, this.orderState);
      return null;
    }
    const paid = this.reward(highestWon);
    this.orderState = { ...s, progress: r.progress, done: true, steps: paid.steps, lastDone: s.day };
    write(ORDER_KEY, this.orderState);
    return paid;
  }
}
