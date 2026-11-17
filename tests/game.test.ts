import { describe, expect, it } from 'vitest';
import { ECONOMY, ENEMIES, TICK, TOWERS } from '../src/sim/content';
import { angleDelta, Game } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';
import { waveSpec } from '../src/sim/waves';
import { playOut, run } from './helpers/bot';

const newGame = () => new Game(buildPathMap(MEADOW));
/** Lives lost if a whole wave walks through. */
const leakOf = (n: number) => waveSpec(n).groups.reduce((s, g) => s + g.count * ENEMIES[g.enemy].leakDamage, 0);

describe('building', () => {
  it('needs the whole footprint on free build cells and charges money', () => {
    const g = newGame();
    expect(g.build('zis3', 0, 6)).toEqual({ ok: false, reason: 'notBuildable' }); // on the road
    expect(g.build('zis3', 1, 5)).toEqual({ ok: false, reason: 'notBuildable' }); // one corner on the road
    expect(g.build('zis3', 20, 0)).toEqual({ ok: false, reason: 'notBuildable' }); // off the map
    expect(g.build('zis3', 2, 2)).toEqual({ ok: true });
    expect(g.money).toBe(ECONOMY.startMoney - TOWERS.zis3.levels[0].cost);
    expect(g.build('zis3', 3, 3)).toEqual({ ok: false, reason: 'occupied' }); // overlaps by one cell
    expect(g.build('zis3', 4, 2)).toEqual({ ok: true }); // right next to it
  });

  it('finds a gun from any cell of its footprint and puts it in the middle', () => {
    const g = newGame();
    g.build('howitzer', 4, 0);
    const t = g.towers[0]!;
    expect([t.x, t.y, t.size]).toEqual([5.5, 1.5, 3]);
    for (const [x, y] of [[4, 0], [6, 2], [5, 1]] as const) expect(g.towerAt(x, y)).toBe(t);
    expect(g.towerAt(7, 0)).toBeUndefined();
    expect(g.towerAt(-1, 0)).toBeUndefined();
  });

  it('refuses to build without money', () => {
    const g = newGame();
    g.money = 10;
    expect(g.build('zis3', 2, 2)).toEqual({ ok: false, reason: 'noMoney' });
  });

  it('upgrades up to max level, sells for a partial refund and frees the ground', () => {
    const g = newGame();
    g.money = 1000;
    g.build('zis3', 2, 2);
    const t = g.towers[0]!;
    expect(g.upgrade(t.id).ok).toBe(true);
    expect(g.upgrade(t.id).ok).toBe(true);
    expect(g.upgrade(t.id)).toEqual({ ok: false, reason: 'maxLevel' });
    const invested = TOWERS.zis3.levels.reduce((s, l) => s + l.cost, 0);
    const before = g.money;
    g.sell(t.id);
    expect(g.money - before).toBe(Math.floor(invested * ECONOMY.sellRefund));
    expect(g.towers).toHaveLength(0);
    expect(g.canBuildAt('zis3', 2, 2)).toBe(true);
  });

  it('points a new gun at the road', () => {
    const g = newGame();
    g.build('zis3', 5, 3); // centre (6, 4); the road runs along y = 6, i.e. towards +y
    expect(Math.abs(g.towers[0]!.aim - Math.PI / 2)).toBeLessThan(0.3);
  });
});

describe('fighting', () => {
  it('loses lives when undefended enemies leak', () => {
    const g = newGame();
    g.startWave();
    run(g, 90);
    expect(g.lives).toBe(ECONOMY.startLives - leakOf(1));
    expect(g.phase).toBe('build');
  });

  it('turns the gun at its turn rate and fires only once it points at the target', () => {
    const g = newGame();
    g.build('howitzer', 2, 1); // centre (3.5, 2.5), aims at the road towards +y
    const t = g.towers[0]!;
    t.aim = -Math.PI / 2; // face away
    g.startWave();
    let prev = t.aim;
    let firedAt = -1;
    for (let i = 0; i < 400 && firedAt < 0; i++) {
      g.step(TICK);
      expect(Math.abs(angleDelta(prev, t.aim))).toBeLessThanOrEqual(TOWERS.howitzer.turnRate * TICK + 1e-9);
      prev = t.aim;
      if (g.projectiles.length) firedAt = i;
    }
    // Half a turn at 70°/s takes over two seconds; it cannot fire before that.
    expect(firedAt * TICK).toBeGreaterThan(2);
    const p = g.projectiles[0]!;
    expect(Math.abs(angleDelta(t.aim, Math.atan2(p.ty - t.y, p.tx - t.x)))).toBeLessThan(0.08);
  });

  it('kills with direct fire, pays rewards and tracks dealt and wasted damage', () => {
    const g = newGame();
    g.money = 1000;
    for (const [x, y] of [[2, 3], [5, 3], [8, 3], [10, 3], [4, 7]] as const) expect(g.build('zis3', x, y).ok).toBe(true);
    const moneyBefore = g.money;
    g.startWave();
    run(g, 90);
    const spec = waveSpec(1).groups[0]!;
    expect(g.lives).toBe(ECONOMY.startLives);
    expect(g.money).toBe(moneyBefore + spec.count * spec.reward + waveSpec(1).clearBonus);
    const sum = (k: 'dealt' | 'kills' | 'wasted') => g.towers.reduce((s, t) => s + t.stats[k], 0);
    expect(sum('kills')).toBe(spec.count);
    expect(sum('dealt')).toBe(spec.count * spec.hp);
    // 16 hp against 12 damage: the second hit on every soldier overkills by 8.
    expect(sum('wasted')).toBeGreaterThanOrEqual(spec.count * 8);
  });

  it('bursts a shell where the target will be and damages everything in the blast', () => {
    const g = newGame();
    g.money = 1000;
    g.build('howitzer', 5, 2);
    g.startWave();
    const events = [];
    for (let i = 0; i < 90 / TICK && g.phase === 'wave'; i++) {
      g.step(TICK);
      events.push(...g.drainEvents());
    }
    const bursts = events.filter((e) => e.type === 'burst');
    expect(bursts.length).toBeGreaterThan(0);
    // Every burst lands on the road, where the enemy had walked to meanwhile.
    for (const b of bursts) if (b.type === 'burst') expect(g.map.grid.get(Math.floor(b.x), Math.floor(b.y))).toBe('path');
    const t = g.towers[0]!;
    expect(t.stats.kills).toBeGreaterThan(0);
    // 160 damage into 16 hp soldiers: most of it is wasted, which is the point of a heavy gun.
    expect(t.stats.wasted).toBeGreaterThan(t.stats.dealt);
  });

  it('does not drop shells inside the minimum range', () => {
    const g = newGame();
    g.money = 1000;
    g.build('howitzer', 5, 2);
    const t = g.towers[0]!;
    g.startWave();
    for (let i = 0; i < 90 / TICK && g.phase === 'wave'; i++) {
      g.step(TICK);
      for (const p of g.projectiles) expect(Math.hypot(p.tx - t.x, p.ty - t.y)).toBeGreaterThan(TOWERS.howitzer.minRange - 0.6);
    }
  });

  it('is deterministic', () => {
    const play = () => {
      const g = newGame();
      g.money = 500;
      g.build('zis3', 2, 2);
      g.build('howitzer', 6, 2);
      for (let w = 0; w < 3; w++) {
        g.startWave();
        run(g, 90);
      }
      return [g.money, g.lives, g.time, g.towers.map((t) => t.stats)];
    };
    expect(play()).toEqual(play());
  });

  it('ends in a loss when lives run out', () => {
    const g = newGame();
    g.lives = 1;
    g.startWave();
    run(g, 90);
    expect(g.phase).toBe('lost');
  });
});

describe('balance', () => {
  it('mixes enemy kinds as the waves go on', () => {
    expect(waveSpec(1).groups.map((g) => g.enemy)).toEqual(['infantry']);
    expect(waveSpec(3).groups.map((g) => g.enemy)).toEqual(['infantry', 'truck']);
    expect(waveSpec(5).groups.map((g) => g.enemy)).toEqual(['infantry', 'truck', 'tank']);
  });

  it('can be won with a mixed defence but not with light guns alone', () => {
    const mixed = newGame();
    playOut(mixed, 3);
    expect(mixed.phase).toBe('won');
    const lightOnly = newGame();
    playOut(lightOnly, 1000);
    expect(lightOnly.phase).toBe('lost');
  });
});
