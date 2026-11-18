import { TOWER_IDS } from './sim/content';
import { bank, FIRST_LAB, newResearch, pause, resume, sanitize, setGold, settle, start, startError, upgrades, type LabInfo, type ResearchState, type StartError, type Upgrades } from './sim/research';

const KEY = 'strelite.research';

/**
 * The player's research, kept in the browser between visits. Timers are wall
 * clock times, so research goes on while the game is closed.
 */
export class ResearchStore {
  private s: ResearchState;
  /** The laboratory in the player's base: how many items, how fast, and whether research runs at all. */
  private labInfo: LabInfo = FIRST_LAB;
  private readonly listeners = new Set<() => void>();

  constructor(
    /** Timers run this many times faster (`?fastresearch` for trying the tree out). */
    readonly speed = 1,
  ) {
    let raw: unknown = null;
    try {
      raw = JSON.parse(localStorage.getItem(KEY) ?? 'null');
    } catch {
      // Blocked storage or a broken save: start fresh.
    }
    this.s = sanitize(raw);
  }

  /** Current state, with a finished timer already counted as done. */
  get state(): ResearchState {
    this.tick();
    return this.s;
  }

  upgrades(): Upgrades {
    return upgrades(this.state.done, TOWER_IDS);
  }

  /** Complete the running item if its time is up; true when it just finished. */
  tick(now = Date.now()): boolean {
    const next = settle(this.s, now);
    if (next === this.s) return false;
    this.set(next);
    return true;
  }

  get lab(): LabInfo {
    return this.labInfo;
  }

  /** The laboratory changed: destroyed stops the clocks, standing again starts them. */
  setLab(lab: LabInfo, now = Date.now()): void {
    this.labInfo = lab;
    const next = lab.standing ? resume(this.s, now) : pause(this.s, now);
    if (next !== this.s) this.set(next);
  }

  start(id: string): StartError | null {
    const err = startError(this.state, id, this.labInfo);
    if (!err) this.set(start(this.s, id, Date.now(), this.speed, this.labInfo));
    return err;
  }

  bank(gold: number): void {
    if (gold > 0) this.set(bank(this.s, gold));
  }

  /** The base spends straight from the treasury. */
  setGold(gold: number): void {
    const next = setGold(this.s, gold);
    if (next !== this.s) this.set(next);
  }

  onChange(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  /** Forget everything (for testing builds). */
  reset(): void {
    this.set(newResearch());
  }

  private set(s: ResearchState): void {
    this.s = s;
    try {
      localStorage.setItem(KEY, JSON.stringify(s));
    } catch {
      // Not saved: it lasts for this visit only.
    }
    this.listeners.forEach((fn) => fn());
  }
}
