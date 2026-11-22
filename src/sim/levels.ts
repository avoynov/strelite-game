import type { ArcMapSpec, PathMapSpec } from './maps';

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
/** The level list shows levels in pages of this many; a page opens once the player reaches it. */
export const LEVELS_PER_PAGE = 100;

/** Pages of the level list the player can see: up to the one holding the next level to win. */
export function levelPages(won: number): number {
  return Math.floor(won / LEVELS_PER_PAGE) + 1;
}

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

/** Shortest straight run of the road, in tiles: keeps a pocket of at least two tiles between parallel runs. */
export const MIN_RUN = 3;

/**
 * The road for a level: from the top of the diagonal band to its bottom, in
 * runs along +x and +y. Every level draws its own shape from its number: which
 * edge the road enters from, where, and for each run how far it swings, from a
 * full crossing of the band to a short step that keeps to one side, so roads
 * range from wide zig-zags to staircases. No run swings
 * further than the level's swing from the band's middle. Level 1, a new
 * player's first battle, keeps the even zig-zag its balance was tuned on.
 */
export function levelMap(level: number): PathMapSpec {
  if (level <= 1) return firstMap();
  const swing = levelSwing(level);
  let salt = 100;
  const roll = () => rand(level, salt++);
  /** A whole number in [lo, hi]. */
  const pick = (lo: number, hi: number) => (hi <= lo ? lo : lo + Math.floor(roll() * (hi - lo + 1)));
  // Diagonal offset d = x - y; runs along +x raise it, runs along +y lower it.
  let alongX = roll() < 0.5;
  const enter = pick(Math.ceil(swing / 2), swing);
  // The first run must have room to swing the other way.
  let x = alongX ? 0 : enter;
  let y = alongX ? enter : 0;
  const waypoints: Array<[number, number]> = [[x, y]];
  for (;;) {
    const d = x - y;
    let target: number;
    const room = alongX ? swing - d : d + swing;
    if (room <= MIN_RUN || roll() < 0.7) {
      // Across the band to the far side, by a varied amount.
      const far = pick(Math.max(1, Math.ceil(swing / 2)), swing);
      target = alongX ? far : -far;
    } else {
      // A short step that stays near this side: a staircase.
      const step = pick(MIN_RUN, Math.min(room, MIN_RUN + 2));
      target = alongX ? d + step : d - step;
    }
    // Every run is at least MIN_RUN long, and never past the swing.
    target = alongX ? Math.min(swing, Math.max(target, d + MIN_RUN)) : Math.max(-swing, Math.min(target, d - MIN_RUN));
    if (alongX) x = Math.min(COLS - 1, x + (target - d));
    else y = Math.min(COLS - 1, y + (d - target));
    waypoints.push([x, y]);
    if (x === COLS - 1 || y === COLS - 1) break;
    alongX = !alongX;
  }
  return { id: `level-${level}`, cols: COLS, rows: COLS, band: BAND, waypoints };
}

/** Level 1: a full swing to each side in turn. */
function firstMap(): PathMapSpec {
  const swing = FIRST_SWING;
  const side = (i: number) => swing - (rand(1, 100 + i) < 0.4 ? 1 : 0);
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
  return { id: 'level-1', cols: COLS, rows: COLS, band: BAND, waypoints };
}

// ---- arc mode ---------------------------------------------------------------

const ARC_BAND = 10;
const DEG = Math.PI / 180;
/**
 * Arc mode dials, tuned with the bot (tests/balance.test.ts). Half-widths of
 * the sector enemies come from, in radians: `start` on a level's first wave;
 * `endFirst` on level 1's last wave, each level widening the last wave by
 * `growth`, never past `max` (enemies never come from behind the goal).
 * Enemy health in arc mode relative to path mode: `hpFirst` on level 1, less
 * by `hpStep` each level (the widening arc already makes later levels harder),
 * never under `hpMin`.
 */
export const ARC_TUNING = { start: 15 * DEG, endFirst: 40 * DEG, growth: 1 * DEG, max: 60 * DEG, hpFirst: 1.35, hpStep: 0.05, hpMin: 0.75 };

/** Arc mode: enemy health relative to path mode on a level. */
export function arcHpFactor(level: number): number {
  return Math.max(ARC_TUNING.hpMin, ARC_TUNING.hpFirst - ARC_TUNING.hpStep * (level - 1));
}

/**
 * Siege mode: enemy health relative to arc mode, tuned with the bot. Guns can
 * be wrecked and every breach costs guns, so later levels are weaker to make
 * up for it: `hpFirst` on level 1, less by `hpStep` each level, never under `hpMin`.
 */
export const SIEGE_TUNING = { hpFirst: 0.75, hpStep: 0.09, hpMin: 0.45 };

/** Siege mode: enemy health relative to arc mode on a level. */
export function siegeHpFactor(level: number): number {
  return Math.max(SIEGE_TUNING.hpMin, SIEGE_TUNING.hpFirst - SIEGE_TUNING.hpStep * (level - 1));
}

/** Half-width of the sector enemies come from on wave n (1-based) of `total`. */
export function arcHalfWidth(n: number, total: number, level: number): number {
  const { start, endFirst, growth, max } = ARC_TUNING;
  const end = Math.min(max, endFirst + growth * (level - 1));
  const t = total > 1 ? (Math.max(1, Math.min(n, total)) - 1) / (total - 1) : 1;
  return start + (end - start) * t;
}

/** The open field for a level in arc mode: the goal near the bottom, a few rock outcrops. */
export function levelArcMap(level: number): ArcMapSpec {
  const goal: [number, number] = [24, 24];
  const rocks: Array<[number, number]> = [];
  const count = 3 + Math.floor(rand(level, 3) * 4);
  for (let i = 0; rocks.length < count && i < 60; i++) {
    const x = Math.floor(rand(level, 200 + i * 2) * (COLS - 2));
    const y = x + Math.round((rand(level, 201 + i * 2) * 2 - 1) * (ARC_BAND - 2));
    if (y < 1 || y > COLS - 3) continue;
    // Keep clear of the goal and of each other, so the field stays open.
    if (Math.hypot(x - goal[0], y - goal[1]) < 6) continue;
    if (rocks.some(([rx, ry]) => Math.abs(rx - x) < 4 && Math.abs(ry - y) < 4)) continue;
    rocks.push([x, y]);
  }
  return { id: `arc-${level}`, cols: COLS, rows: COLS, band: ARC_BAND, goal, rocks, minSpawnDistance: 12 };
}
