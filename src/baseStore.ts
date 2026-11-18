import { jobError, jobPrice, newBase, sanitizeBase, settleJobs, startJob, type BaseState, type JobError, type JobTarget } from './sim/base';

const KEY = 'strelite.base';

/** The player's base, kept in the browser between visits and battles. */
export class BaseStore {
  private s: BaseState;

  constructor(
    /** Building timers run this many times faster (testing builds). */
    readonly speed = 1,
  ) {
    let raw: unknown = null;
    try {
      raw = JSON.parse(localStorage.getItem(KEY) ?? 'null');
    } catch {
      // Blocked storage or a broken save: a new base.
    }
    this.s = sanitizeBase(raw);
  }

  get state(): BaseState {
    return this.s;
  }

  set(s: BaseState): void {
    this.s = s;
    try {
      localStorage.setItem(KEY, JSON.stringify(s));
    } catch {
      // Not saved: it lasts for this visit only.
    }
  }

  /** Finish building jobs whose time is up; true when something finished. */
  settle(now = Date.now()): boolean {
    const next = settleJobs(this.s, now);
    if (next === this.s) return false;
    this.set(next);
    return true;
  }

  /** Start raising (or rebuilding) a building, paid from the treasury. */
  startJob(what: JobTarget, wallet: { gold: number }): JobError | null {
    const err = jobError(this.s, what, wallet.gold);
    if (err) return err;
    wallet.gold -= jobPrice(this.s, what)!.cost;
    this.set(startJob(this.s, what, Date.now(), this.speed));
    return null;
  }

  /** The base is lost: start over. */
  reset(): void {
    this.set(newBase());
  }
}
