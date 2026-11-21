import { TICK } from '../../src/sim/content';
import { BASE_MAP, HQ_LEVELS, jobPrice, LAB_LEVELS, newBase, type BaseState } from '../../src/sim/base';
import { Game, type Wallet } from '../../src/sim/game';
import { buildArcMap } from '../../src/sim/maps';
import type { Upgrades } from '../../src/sim/research';
import { spend } from './bot';

/**
 * Base mode for tests: the saved base, the treasury and a clock that runs with
 * the simulation (builders work on it), carried from one attack to the next.
 */
export class Campaign {
  base: BaseState = newBase();
  wallet: Wallet = { gold: 0 };
  /** ms on the shared clock before the current game started. */
  private offset = 0;
  game: Game;

  constructor(private readonly upgrades?: Upgrades) {
    this.game = this.open();
  }

  /** The base as it stands, ready for the next attack. */
  open(): Game {
    if (this.game) this.offset += this.game.time * 1000;
    const base = () => this.base;
    const now = () => this.offset + (current?.time ?? 0) * 1000;
    let current: Game | null = null;
    const g: Game = new Game(buildArcMap(BASE_MAP, 'siege'), {
      level: this.base.attack,
      ...(this.upgrades ? { upgrades: this.upgrades } : {}),
      base: {
        get state() {
          return base();
        },
        wallet: this.wallet,
        now,
      },
    });
    current = g;
    this.game = g;
    return g;
  }

  /** Keep what stands (after an attack, or while building in peace). */
  save(): void {
    this.base = { ...this.base, ...this.game.snapshot() };
  }

  /** Between attacks: skip the clock ahead to when the next gun job is done. */
  private waitForBuilders(): void {
    const g = this.game;
    const ends = g.towers.map((t) => t.job?.endsAt ?? Infinity);
    const next = Math.min(...ends);
    if (!Number.isFinite(next)) return;
    const now = this.offset + g.time * 1000;
    if (next > now) this.offset += next - now;
    g.step(TICK);
  }

  /** Let the clock run (peace or battle). */
  run(seconds: number): void {
    for (let i = 0; i < seconds / TICK && this.game.phase !== 'won' && this.game.phase !== 'lost'; i++) this.game.step(TICK);
  }

  /**
   * Between attacks (hours pass while the player plays elsewhere): raise the
   * headquarters, then the laboratory (never above the headquarters), when that
   * takes no more than a share of the treasury. Then mend
   * everything and spend the rest, one builder's job at a time.
   */
  prepare(): void {
    this.save();
    let raised = false;
    for (const [what, share] of [['hq', 0.5], ['lab', 0.25]] as const) {
      const price = jobPrice(this.base, what);
      if (!price || price.cost > this.wallet.gold * share) continue;
      if (what === 'lab' && this.base.lab && this.base.lab.level >= this.base.hq.level) continue;
      this.wallet.gold -= price.cost;
      if (what === 'hq') this.base = { ...this.base, hq: { level: this.base.hq.level + 1, hp: HQ_LEVELS[this.base.hq.level + 1]!.hp } };
      else if (this.base.lab) this.base = { ...this.base, lab: { level: this.base.lab.level + 1, hp: LAB_LEVELS[this.base.lab.level + 1]!.hp } };
      raised = true;
    }
    if (raised) this.open();
    const g = this.game;
    g.repairAll();
    for (let guard = 0; guard < 400; guard++) {
      const before = g.money;
      spend(g);
      const busy = g.towers.some((t) => t.job);
      if (!busy && g.money === before) break;
      this.waitForBuilders();
    }
  }

  /** Fight the next attack; returns whether the base held. */
  fight(): boolean {
    const g = this.game;
    while (g.phase === 'build') {
      if (g.wave > 0) spend(g);
      g.startWave();
      for (let i = 0; i < 20000 && g.phase === 'wave'; i++) g.step(TICK);
    }
    const won = g.phase === 'won';
    if (won) {
      this.save();
      this.base = { ...this.base, attack: this.base.attack + 1 };
    } else this.base = newBase();
    this.open();
    return won;
  }
}
