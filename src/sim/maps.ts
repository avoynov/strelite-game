import { Grid, type Cell } from './grid';

export interface PathMapSpec {
  id: string;
  cols: number;
  rows: number;
  /** Corner points of the path, joined by straight horizontal/vertical runs. */
  waypoints: Array<[number, number]>;
}

export interface BuiltMap {
  id: string;
  grid: Grid;
  spawns: Cell[];
  goals: Cell[];
}

/** Portrait map for phones: enemies enter at the top and wind down to the bottom. */
export const MEADOW: PathMapSpec = {
  id: 'meadow',
  cols: 9,
  rows: 15,
  waypoints: [
    [1, 0],
    [1, 3],
    [7, 3],
    [7, 7],
    [2, 7],
    [2, 11],
    [6, 11],
    [6, 14],
  ],
};

export function buildPathMap(spec: PathMapSpec): BuiltMap {
  const grid = new Grid(spec.cols, spec.rows, 'build');
  const pts = spec.waypoints;
  for (let i = 0; i < pts.length - 1; i++) {
    const [ax, ay] = pts[i]!;
    const [bx, by] = pts[i + 1]!;
    if (ax !== bx && ay !== by) throw new Error(`Map ${spec.id}: diagonal segment at ${i}`);
    const sx = Math.sign(bx - ax);
    const sy = Math.sign(by - ay);
    let x = ax;
    let y = ay;
    grid.set(x, y, 'path');
    while (x !== bx || y !== by) {
      x += sx;
      y += sy;
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
