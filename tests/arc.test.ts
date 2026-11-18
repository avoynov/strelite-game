import { describe, expect, it } from 'vitest';
import { ECONOMY, TICK } from '../src/sim/content';
import { Game } from '../src/sim/game';
import { arcHalfWidth, levelArcMap, levelWaves } from '../src/sim/levels';
import { buildArcMap } from '../src/sim/maps';
import { run } from './helpers/bot';

const arcGame = (level = 1) => new Game(buildArcMap(levelArcMap(level)), { level });

describe('arc mode', () => {
  it('every edge cell enemies may come from reaches the goal, on every level', () => {
    for (const l of [1, 2, 7, 40, 300]) {
      const g = arcGame(l);
      const spawns = g.map.arcSpawns!;
      expect(spawns.length, `level ${l}`).toBeGreaterThan(20);
      for (const s of spawns) expect(g.flow.distanceAt(s.x, s.y), `level ${l} ${s.x},${s.y}`).toBeGreaterThan(0);
    }
  });

  it('the arc widens over the waves of a level, and more on later levels, up to a cap', () => {
    const n = levelWaves(1);
    expect(arcHalfWidth(n, n, 1)).toBeGreaterThan(arcHalfWidth(1, n, 1));
    expect(arcHalfWidth(10, 10, 20)).toBeGreaterThan(arcHalfWidth(10, 10, 1));
    expect(arcHalfWidth(50, 50, 10000)).toBeLessThan(Math.PI * 0.6);
    const g = arcGame();
    const first = g.activeSpawns().length;
    expect(first).toBeGreaterThan(0);
    expect(first).toBeLessThan(g.map.arcSpawns!.length);
  });

  it('enemies walk in from the arc to the goal and cost lives', () => {
    const g = arcGame();
    g.startWave();
    run(g, 120);
    expect(g.lives).toBeLessThan(ECONOMY.startLives);
  });

  it('guns are walked around, but may not shut the goal off', () => {
    const g = arcGame();
    g.money = 100000;
    const [gx, gy] = levelArcMap(1).goal;
    const before = g.flow.distanceAt(gx - 4, gy - 4);
    // A ring of 2x2 crossbows around the goal: the last gap must be refused.
    const ring: [number, number][] = [];
    for (let x = gx - 2; x <= gx + 2; x += 2) ring.push([x, gy - 2], [x, gy + 2]);
    ring.push([gx - 2, gy], [gx + 2, gy]);
    const results = ring.filter(([x, y]) => g.canBuildAt('crossbow', x, y)).map(([x, y]) => g.build('crossbow', x, y));
    expect(results.some((r) => !r.ok && r.reason === 'blocks')).toBe(true);
    expect(results.filter((r) => r.ok).length).toBeGreaterThan(3);
    // Still a way in, and the route got longer around the guns.
    expect(g.flow.distanceAt(gx - 4, gy - 4)).toBeGreaterThanOrEqual(before);
    g.startWave();
    for (let i = 0; i < 120 / TICK && g.phase === 'wave'; i++) g.step(TICK);
    expect(g.phase === 'build' || g.phase === 'lost').toBe(true);
  });
});
