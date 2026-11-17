import type { PathMapSpec } from './maps';

/**
 * Generated map levels. Nothing about a level is stored: its number seeds
 * everything, so there can be as many as the player reaches. Each level has a
 * small chance of one more wave and of a slightly straighter road (fewer
 * pockets where one gun covers two stretches); both changes stop at a cap.
 */

export const FIRST_LEVEL_WAVES = 3;
/** Chance that a level has one wave more than the one before. */
export const MORE_WAVES_CHANCE = 0.3;
export const MAX_WAVES = 50;
/** How far the road swings to either side of the band's middle on level 1, in tiles. */
export const FIRST_SWING = 7;
/** Chance that a level's road swings one tile less than the one before. */
export const STRAIGHTER_CHANCE = 0.12;
/** The road never swings less than this (it keeps a few pockets for heavy guns). */
export const MIN_SWING = 3;
/** Levels shown ahead of the furthest one won, so the end is never in sight. */
export const LEVELS_AHEAD = 100;

const COLS = 30;
const BAND = 8;

/** Deterministic number in [0, 1) for a level and a purpose. */
function rand(level: number, salt: number): number {
  let h = Math.imul(level ^ 0x9e3779b9, 0x85ebca6b) ^ Math.imul(salt + 1, 0xc2b2ae35);
  h = Math.imul(h ^ (h >>> 16), 0x45d9f3b);
  h = Math.imul(h ^ (h >>> 16), 0x45d9f3b);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

/** How many of levels 2..level rolled under `chance` (a walk that only goes up). */
function steps(level: number, chance: number, salt: number, cap: number): number {
  let n = 0;
  for (let l = 2; l <= level && n < cap; l++) if (rand(l, salt) < chance) n++;
  return n;
}

export function levelWaves(level: number): number {
  return FIRST_LEVEL_WAVES + steps(level, MORE_WAVES_CHANCE, 1, MAX_WAVES - FIRST_LEVEL_WAVES);
}

/** Widest swing of the road to either side, in tiles. */
export function levelSwing(level: number): number {
  return FIRST_SWING - steps(level, STRAIGHTER_CHANCE, 2, FIRST_SWING - MIN_SWING);
}

/**
 * The road for a level: from the top of the diagonal band to its bottom, in
 * alternating runs along +x and +y. Each run swings the road from one side of
 * the band's middle to the other, by up to the level's swing.
 */
export function levelMap(level: number): PathMapSpec {
  const swing = levelSwing(level);
  const side = (i: number) => swing - (rand(level, 100 + i) < 0.4 ? 1 : 0);
  // Diagonal offset d = x - y; runs along +x raise it, runs along +y lower it.
  let x = 0;
  let y = side(0);
  const waypoints: Array<[number, number]> = [[x, y]];
  for (let i = 1; ; i++) {
    const alongX = i % 2 === 1;
    const target = alongX ? side(i) : -side(i);
    const d = x - y;
    if (alongX) x = Math.min(COLS - 1, x + (target - d));
    else y = Math.min(COLS - 1, y + (d - target));
    waypoints.push([x, y]);
    if (x === COLS - 1 || y === COLS - 1) break;
  }
  return { id: `level-${level}`, cols: COLS, rows: COLS, band: BAND, waypoints };
}
