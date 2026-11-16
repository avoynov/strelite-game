import type { Cell, Grid } from './grid';

const DIRS: ReadonlyArray<readonly [number, number]> = [
  [1, 0],
  [-1, 0],
  [0, 1],
  [0, -1],
];

/**
 * Breadth-first distance field towards the goal cells. Every walker follows
 * the neighbour with the lowest distance, so one field serves any number of
 * enemies and any number of spawn points. Path mode restricts walkable cells to
 * the carved path; the later "arc" mode will make open ground walkable and
 * rebuild the field whenever a tower is placed.
 */
export class FlowField {
  readonly dist: Int32Array;

  constructor(
    readonly grid: Grid,
    goals: Cell[],
    readonly walkable: (x: number, y: number) => boolean,
  ) {
    this.dist = new Int32Array(grid.cols * grid.rows).fill(-1);
    const queue: number[] = [];
    for (const g of goals) {
      const i = grid.index(g.x, g.y);
      this.dist[i] = 0;
      queue.push(i);
    }
    for (let head = 0; head < queue.length; head++) {
      const i = queue[head]!;
      const x = i % grid.cols;
      const y = (i - x) / grid.cols;
      for (const [dx, dy] of DIRS) {
        const nx = x + dx;
        const ny = y + dy;
        if (!grid.inBounds(nx, ny) || !walkable(nx, ny)) continue;
        const ni = grid.index(nx, ny);
        if (this.dist[ni] !== -1) continue;
        this.dist[ni] = this.dist[i]! + 1;
        queue.push(ni);
      }
    }
  }

  distanceAt(x: number, y: number): number {
    return this.grid.inBounds(x, y) ? this.dist[this.grid.index(x, y)]! : -1;
  }

  /** Next cell to step into from (x, y), or null at the goal / unreachable. */
  next(x: number, y: number): Cell | null {
    const here = this.distanceAt(x, y);
    if (here <= 0) return null;
    let best: Cell | null = null;
    let bestDist = here;
    for (const [dx, dy] of DIRS) {
      const d = this.distanceAt(x + dx, y + dy);
      if (d >= 0 && d < bestDist) {
        bestDist = d;
        best = { x: x + dx, y: y + dy };
      }
    }
    return best;
  }
}
