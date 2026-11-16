import { Grid, type Cell } from './grid';

export interface PathMapSpec {
  id: string;
  cols: number;
  rows: number;
  /** Corner points of the path, joined by straight horizontal/vertical runs. */
  waypoints: Array<[number, number]>;
  /**
   * Optional diagonal band: only cells with |x - y| <= band are part of the map.
   * Seen isometrically, such a band runs straight down the screen, which fits a
   * portrait phone far better than a full diamond.
   */
  band?: number;
}

export interface BuiltMap {
  id: string;
  grid: Grid;
  spawns: Cell[];
  goals: Cell[];
}

/**
 * Portrait map for phones. In the isometric view the band runs top to bottom;
 * the path zig-zags down it, alternating down-right (+x) and down-left (+y) runs.
 */
export const MEADOW: PathMapSpec = {
  id: 'meadow',
  cols: 16,
  rows: 16,
  band: 4,
  waypoints: [
    [0, 4],
    [8, 4],
    [8, 12],
    [15, 12],
    [15, 15],
  ],
};

export function buildPathMap(spec: PathMapSpec): BuiltMap {
  const grid = new Grid(spec.cols, spec.rows, 'build');
  if (spec.band !== undefined) {
    for (let y = 0; y < spec.rows; y++) {
      for (let x = 0; x < spec.cols; x++) if (Math.abs(x - y) > spec.band) grid.set(x, y, 'blocked');
    }
  }
  const pts = spec.waypoints;
  for (let i = 0; i < pts.length - 1; i++) {
    const [ax, ay] = pts[i]!;
    const [bx, by] = pts[i + 1]!;
    if (ax !== bx && ay !== by) throw new Error(`Map ${spec.id}: diagonal segment at ${i}`);
    const sx = Math.sign(bx - ax);
    const sy = Math.sign(by - ay);
    let x = ax;
    let y = ay;
    if (grid.get(x, y) === 'blocked') throw new Error(`Map ${spec.id}: path leaves the map at ${x},${y}`);
    grid.set(x, y, 'path');
    while (x !== bx || y !== by) {
      x += sx;
      y += sy;
      if (grid.get(x, y) === 'blocked') throw new Error(`Map ${spec.id}: path leaves the map at ${x},${y}`);
      grid.set(x, y, 'path');
    }
  }
  const first = pts[0]!;
  const last = pts[pts.length - 1]!;
  return {
    id: spec.id,
    grid,
    spawns: [{ x: first[0], y: first[1] }],
    goals: [{ x: last[0], y: last[1] }],
  };
}
