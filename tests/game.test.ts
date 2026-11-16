import { describe, expect, it } from 'vitest';
import { ECONOMY, TICK, TOWERS } from '../src/sim/content';
import { Game } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';

const newGame = () => new Game(buildPathMap(MEADOW));
const run = (g: Game, seconds: number) => {
  for (let i = 0; i < seconds / TICK; i++) g.step(TICK);
};

describe('Game', () => {
  it('builds only on build cells and charges money', () => {
    const g = newGame();
    expect(g.build('crossbow', 1, 0)).toEqual({ ok: false, reason: 'notBuildable' });
    expect(g.build('crossbow', 0, 2)).toEqual({ ok: true });
    expect(g.money).toBe(ECONOMY.startMoney - TOWERS.crossbow.levels[0].cost);
    expect(g.build('crossbow', 0, 2)).toEqual({ ok: false, reason: 'occupied' });
  });

  it('refuses to build without money', () => {
    const g = newGame();
    g.money = 10;
    expect(g.build('crossbow', 0, 2)).toEqual({ ok: false, reason: 'noMoney' });
  });

  it('upgrades up to max level and sells for a partial refund', () => {
    const g = newGame();
    g.money = 1000;
    g.build('crossbow', 0, 2);
    const t = g.towers[0]!;
    expect(g.upgrade(t.id).ok).toBe(true);
    expect(g.upgrade(t.id).ok).toBe(true);
    expect(g.upgrade(t.id)).toEqual({ ok: false, reason: 'maxLevel' });
    const invested = TOWERS.crossbow.levels.reduce((s, l) => s + l.cost, 0);
    const before = g.money;
    g.sell(t.id);
    expect(g.money - before).toBe(Math.floor(invested * ECONOMY.sellRefund));
    expect(g.towers).toHaveLength(0);
  });

  it('loses lives when undefended enemies leak', () => {
    const g = newGame();
    g.startWave();
    run(g, 60);
    expect(g.lives).toBe(ECONOMY.startLives - 7);
    expect(g.phase).toBe('build');
  });

  it('kills enemies, pays rewards and tracks dealt/wasted damage', () => {
    const g = newGame();
    g.money = 1000;
    for (const [x, y] of [[0, 2], [2, 2], [0, 4], [3, 4], [6, 6], [8, 4]] as const) g.build('crossbow', x, y);
    const moneyBefore = g.money;
    g.startWave();
    run(g, 60);
    expect(g.lives).toBe(ECONOMY.startLives);
    expect(g.money).toBeGreaterThan(moneyBefore);
    const dealt = g.towers.reduce((s, t) => s + t.stats.dealt, 0);
    const kills = g.towers.reduce((s, t) => s + t.stats.kills, 0);
    expect(kills).toBe(7);
    expect(dealt).toBe(7 * 20);
    // 20 hp / 5 damage = exact multiple, so no overkill from direct hits at level 1;
    // any waste comes from shots in flight at already-dead targets.
    const wasted = g.towers.reduce((s, t) => s + t.stats.wasted, 0);
    expect(wasted % 5).toBe(0);
  });

  it('is deterministic', () => {
    const play = () => {
      const g = newGame();
      g.money = 500;
      g.build('crossbow', 0, 2);
      g.build('crossbow', 2, 4);
      for (let w = 0; w < 3; w++) {
        g.startWave();
        run(g, 40);
      }
      return [g.money, g.lives, g.time, g.towers.map((t) => t.stats)];
    };
    expect(play()).toEqual(play());
  });

  it('ends in a loss when lives run out', () => {
    const g = newGame();
    g.lives = 1;
    g.startWave();
    run(g, 60);
    expect(g.phase).toBe('lost');
  });
});
