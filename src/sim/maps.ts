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

export type Mode = 'path' | 'arc';

/** A cell enemies may enter the field from, in arc mode. */
export interface ArcSpawn extends Cell {
  /** Angle off the arc's middle direction, radians (negative to one side, positive to the other). */
  off: number;
}

export interface BuiltMap {
  id: string;
  mode: Mode;
  grid: Grid;
  /** Path mode: where the road starts. Arc mode: unused (see arcSpawns). */
  spawns: Cell[];
  goals: Cell[];
  /** Arc mode: every edge cell enemies could come from, with its angle off the arc's middle. */
  arcSpawns?: ArcSpawn[];
}

/**
 * Arc mode: an open field (the same portrait band) with a goal near its bottom
 * end. Enemies walk in over open ground from the far edges, from a sector of
 * directions around the goal that widens as the waves go on.
 */
export interface ArcMapSpec {
  id: string;
  cols: number;
  rows: number;
  band: number;
  /** Top-left cell of the 2x2 goal. */
  goal: [number, number];
  /** Rock outcrops nobody walks or builds on: top-left cells of 2x2 blocks. */
  rocks: Array<[number, number]>;
  /** Spawn cells must be at least this far from the goal, in tiles. */
  minSpawnDistance: number;
}

/**
 * Portrait map for phones. In the isometric view the band runs top to bottom;
 * the road zig-zags down it, alternating down-right (+x) and down-left (+y)
 * runs. The pockets between the runs take the 3x3 heavy guns.
 */
export const MEADOW: PathMapSpec = {
  id: 'meadow',
  cols: 30,
  rows: 30,
  band: 8,
  waypoints: [
    [0, 6],
    [13, 6],
    [13, 19],
    [26, 19],
    [26, 29],
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
    mode: 'path',
    grid,
    spawns: [{ x: first[0], y: first[1] }],
    goals: [{ x: last[0], y: last[1] }],
  };
}

/** The arc's middle direction: from the goal towards the far (top) end of the band. */
export const ARC_FACING = Math.atan2(-1, -1);

export function buildArcMap(spec: ArcMapSpec): BuiltMap {
  const grid = new Grid(spec.cols, spec.rows, 'build');
  for (let y = 0; y < spec.rows; y++) {
    for (let x = 0; x < spec.cols; x++) if (Math.abs(x - y) > spec.band) grid.set(x, y, 'blocked');
  }
  for (const [rx, ry] of spec.rocks) for (let y = ry; y < ry + 2; y++) for (let x = rx; x < rx + 2; x++) grid.set(x, y, 'blocked');
  const [gx, gy] = spec.goal;
  const goals: Cell[] = [];
  for (let y = gy; y < gy + 2; y++) {
    for (let x = gx; x < gx + 2; x++) {
      grid.set(x, y, 'path');
      goals.push({ x, y });
    }
  }
  // Edge cells: open cells next to the outside or the band's edge, far enough from the goal.
  const cx = gx + 1;
  const cy = gy + 1;
  const arcSpawns: ArcSpawn[] = [];
  for (let y = 0; y < spec.rows; y++) {
    for (let x = 0; x < spec.cols; x++) {
      if (grid.get(x, y) !== 'build') continue;
      const edge = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => {
        const nx = x + dx!;
        const ny = y + dy!;
        return !grid.inBounds(nx, ny) || Math.abs(nx - ny) > spec.band;
      });
      if (!edge) continue;
      const vx = x + 0.5 - cx;
      const vy = y + 0.5 - cy;
      if (Math.hypot(vx, vy) < spec.minSpawnDistance) continue;
      let off = Math.atan2(vy, vx) - ARC_FACING;
      off = Math.atan2(Math.sin(off), Math.cos(off));
      arcSpawns.push({ x, y, off });
    }
  }
  arcSpawns.sort((a, b) => a.off - b.off);
  return { id: spec.id, mode: 'arc', grid, spawns: [], goals, arcSpawns };
}
