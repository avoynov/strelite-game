import { describe, expect, it } from 'vitest';
import { ECONOMY, ENEMIES, TICK, TOWERS, type EnemyId } from '../src/sim/content';
import { angleDelta, Game, startMoney, type GameEvent } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';
import { groupWeight, olderGroups, waveOfStrength, waveSpec, waveStrength, type WaveGroup } from '../src/sim/waves';
import { levelWaves } from '../src/sim/levels';
import { run } from './helpers/bot';

/** Map level 2 on the fixed test map, its waves rising from strength 1 (so the first is small). */
const newGame = (level = 2) => new Game(buildPathMap(MEADOW), { level, totalWaves: 15, waves: (n, l) => waveOfStrength(n, l) });
/** Lives lost if a whole wave walks through. */
const leakOf = (n: number) => waveOfStrength(n, 2).groups.reduce((s, g) => s + g.count * ENEMIES[g.enemy].leakDamage, 0);

describe('building', () => {
  it('needs the whole footprint on free build cells and charges money', () => {
    const g = newGame();
    expect(g.build('zis3', 0, 6)).toEqual({ ok: false, reason: 'notBuildable' }); // on the road
    expect(g.build('zis3', 1, 5)).toEqual({ ok: false, reason: 'notBuildable' }); // one corner on the road
    expect(g.build('zis3', 20, 0)).toEqual({ ok: false, reason: 'notBuildable' }); // off the map
    expect(g.build('zis3', 2, 2)).toEqual({ ok: true });
    expect(g.money).toBe(startMoney(2) - TOWERS.zis3.levels[0].cost);
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
    g.money = 5000;
    g.build('zis3', 2, 2);
    const t = g.towers[0]!;
    for (let i = 1; i < TOWERS.zis3.levels.length; i++) expect(g.upgrade(t.id).ok).toBe(true);
    expect(t.level).toBe(4);
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
    const events: GameEvent[] = [];
    for (let i = 0; i < 90 / TICK; i++) {
      g.step(TICK);
      events.push(...g.drainEvents());
    }
    const spec = waveOfStrength(1, 2).groups[0]!;
    // Every direct hit is announced as an impact, for the board's hit effect.
    expect(events.filter((e) => e.type === 'impact').length).toBe(events.filter((e) => e.type === 'hit').length);
    expect(g.lives).toBe(ECONOMY.startLives);
    expect(g.money).toBe(moneyBefore + spec.count * spec.reward + waveOfStrength(1, 2).clearBonus);
    const sum = (k: 'dealt' | 'kills' | 'wasted') => g.towers.reduce((s, t) => s + t.stats[k], 0);
    expect(sum('kills')).toBe(spec.count);
    expect(sum('dealt')).toBeCloseTo(spec.count * spec.hp);
    // 45 damage into a soldier with less: the rest of every shot is overkill.
    expect(sum('wasted')).toBeGreaterThanOrEqual(spec.count * (45 - spec.hp) - 1e-6);
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
    // 170 damage into 21 hp soldiers: most of it is wasted, which is the point of a heavy gun.
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
  it('mixes enemy kinds as the waves grow stronger, each arriving with the map level of its counter', () => {
    const kinds = (k: number, level: number) => waveOfStrength(k, level).groups.map((g) => g.enemy);
    expect(kinds(1, 1)).toEqual(['infantry']);
    expect(kinds(15, 1)).toEqual(['infantry', 'truck']);
    expect(kinds(5, 2)).toEqual(['infantry', 'moto', 'truck', 'apc']);
    expect(kinds(5, 3)).toContain('drone');
    expect(kinds(5, 4)).toContain('tank');
    // The boss comes on a map's last wave only, from map 5: the fortress, from map 80 the dreadnought.
    expect(kinds(10, 5)).not.toContain('fortress');
    const last = (level: number) => waveSpec(levelWaves(level), level).groups.map((g) => g.enemy);
    expect(last(4)).not.toContain('fortress');
    expect(last(5)).toContain('fortress');
    expect(last(79)).toContain('fortress');
    expect(last(80)).toContain('dreadnought');
    expect(last(80)).not.toContain('fortress');
    // One newcomer per act from map 10.
    const open: Array<[EnemyId, number, number]> = [['wagon', 10, 6], ['rider', 16, 6], ['glider', 23, 6], ['armorcar', 31, 8], ['sapper', 40, 8], ['shield', 51, 10], ['boat', 64, 10]];
    for (const [e, level, k] of open) {
      expect(kinds(k, level), `${e} on ${level}`).toContain(e);
      expect(kinds(k, level - 1), `${e} before ${level}`).not.toContain(e);
      expect(kinds(k - 1, level), `${e} below ${k}`).not.toContain(e);
    }
  });

  it('keeps a wave\'s weight as the newcomers and the boss join: the older seven thin out', () => {
    const weight = (groups: WaveGroup[]) => groups.reduce((s, g) => s + groupWeight(g), 0);
    for (const level of [10, 16, 23, 31, 40, 51, 64, 80]) {
      for (const k of [10, 14, 18]) {
        const target = weight(olderGroups(k, level));
        for (const opts of [{}, { boss: true, even: true }]) {
          const w = waveOfStrength(k, level, 0, opts);
          // Rounding the thinned numbers (at least one of each) leaves a little over.
          expect(weight(w.groups) / target, `${level} k${k}`).toBeGreaterThan(0.85);
          expect(weight(w.groups) / target, `${level} k${k}`).toBeLessThan(1.15);
        }
      }
    }
  });

  it('starts each map level a little stronger, up to a cap', () => {
    expect(waveStrength(1, 1)).toBe(4);
    expect(waveStrength(3, 1)).toBe(6);
    expect(waveStrength(1, 3)).toBe(5);
    expect(waveStrength(1, 1000)).toBe(10);
    expect(waveStrength(40, 1000)).toBe(18);
    expect(waveSpec(2, 3)).toEqual(waveOfStrength(6, 3));
  });
});
