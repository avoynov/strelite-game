/**
 * The board's projection: 2:1 dimetric, Clash of Clans style. Square tiles
 * become diamonds seen from a corner; grid +x runs to the screen's lower
 * right, +y to the lower left. It matches the camera the art is rendered with
 * (30° elevation, 45° azimuth), so sprites drop straight onto the board.
 *
 * Everything on the board is laid out once in "world pixels" at a fixed tile
 * size; the camera then scales and moves the whole world.
 */

/** Width of one tile's diamond in world pixels. */
export const TILE_W = 64;
export const TILE_H = TILE_W / 2;
/** World pixels per tile of height: cos(30°) / √2 of the tile width. */
export const RISE = TILE_W * 0.6124;

export interface Point {
  x: number;
  y: number;
}

/** Grid point (+ height in tiles) to world x. */
export function isoX(gx: number, gy: number): number {
  return ((gx - gy) * TILE_W) / 2;
}

/** Grid point (+ height in tiles) to world y. */
export function isoY(gx: number, gy: number, h = 0): number {
  return ((gx + gy) * TILE_H) / 2 - h * RISE;
}

export function project(gx: number, gy: number, h = 0): Point {
  return { x: isoX(gx, gy), y: isoY(gx, gy, h) };
}

/** World point on the ground back to (fractional) grid coordinates. */
export function unproject(wx: number, wy: number): Point {
  const u = wx / (TILE_W / 2); // gx - gy
  const v = wy / (TILE_H / 2); // gx + gy
  return { x: (u + v) / 2, y: (v - u) / 2 };
}

/** Draw order: larger gx + gy is nearer the camera. */
export function depth(gx: number, gy: number): number {
  return gx + gy;
}

/** Outline of the grid rectangle [x0, x1] x [y0, y1] as a flat point list. */
export function diamond(x0: number, y0: number, x1: number, y1: number, h = 0): number[] {
  return [isoX(x0, y0), isoY(x0, y0, h), isoX(x1, y0), isoY(x1, y0, h), isoX(x1, y1), isoY(x1, y1, h), isoX(x0, y1), isoY(x0, y1, h)];
}
