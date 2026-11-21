import { describe, expect, it } from 'vitest';
import { Game } from '../src/sim/game';
import { FIRST_LEVEL_WAVES, levelMap, levelPages, levelSwing, levelWaves, MAX_WAVES, MIN_RUN, MIN_SWING } from '../src/sim/levels';
import { buildPathMap } from '../src/sim/maps';

describe('generated levels', () => {
  it('level 1 is short, and waves only grow, a little at a time, up to the cap', () => {
    expect(levelWaves(1)).toBe(FIRST_LEVEL_WAVES);
    for (let l = 2; l <= 600; l++) {
      const d = levelWaves(l) - levelWaves(l - 1);
      expect(d === 0 || d === 1, `level ${l}`).toBe(true);
    }
    expect(levelWaves(100)).toBeGreaterThan(15);
    expect(levelWaves(5000)).toBe(MAX_WAVES);
  });

  it('roads only get straighter, a step at a time, down to a floor', () => {
    for (let l = 2; l <= 600; l++) expect(levelSwing(l - 1) - levelSwing(l)).toBeGreaterThanOrEqual(0);
    expect(levelSwing(5000)).toBe(MIN_SWING);
  });

  it('lists levels in pages of 100, opening the next page once the player reaches it', () => {
    expect(levelPages(0)).toBe(1);
    expect(levelPages(99)).toBe(1);
    expect(levelPages(100)).toBe(2);
    expect(levelPages(250)).toBe(3);
  });

  it('is the same level every time for the same number', () => {
    expect(levelMap(37)).toEqual(levelMap(37));
    expect(levelMap(37)).not.toEqual(levelMap(38));
  });

  it('draws a different road shape on every level', () => {
    const shape = (l: number) => JSON.stringify(levelMap(l).waypoints);
    const shapes = new Set<string>();
    for (let l = 1; l <= 60; l++) {
      shapes.add(shape(l));
      if (l > 1) expect(shape(l), `level ${l}`).not.toBe(shape(l - 1));
    }
    expect(shapes.size).toBeGreaterThanOrEqual(58);
    // Runs keep pockets between them: every straight stretch but the last is at least MIN_RUN long.
    for (let l = 2; l <= 300; l++) {
      const w = levelMap(l).waypoints;
      for (let i = 1; i < w.length - 1; i++) {
        const len = Math.abs(w[i]![0] - w[i - 1]![0]) + Math.abs(w[i]![1] - w[i - 1]![1]);
        expect(len, `level ${l} run ${i}`).toBeGreaterThanOrEqual(MIN_RUN);
      }
    }
  });

  it('builds a playable map for every level: a road from spawn to goal with room to build', () => {
    for (const l of [1, 2, 3, 10, 50, 99, 100, 101, 500, 2000]) {
      const map = buildPathMap(levelMap(l));
      const g = new Game(map, { level: l });
      const spawn = map.spawns[0]!;
      expect(g.flow.next(spawn.x, spawn.y), `level ${l}`).toBeDefined();
      let free = 0;
      for (let y = 0; y < map.grid.rows; y++) for (let x = 0; x < map.grid.cols; x++) if (g.canBuildAt('howitzer', x, y)) free++;
      expect(free, `level ${l}`).toBeGreaterThan(30);
    }
  });
});
