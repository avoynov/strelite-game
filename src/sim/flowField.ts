import type { Cell, Grid } from './grid';

const DIRS: ReadonlyArray<readonly [number, number]> = [
  [1, 0],
  [-1, 0],
  [0, 1],
  [0, -1],
];

/**
 * Distance field towards the goal cells. Every walker follows the neighbour
 * with the lowest distance, so one field serves any number of enemies and any
 * number of spawn points. Path mode restricts walkable cells to the carved
 * path; the open-field modes make open ground walkable and rebuild the field
 * whenever something is built.
 *
 * With `cost`, stepping into a cell costs that much instead of 1 (siege mode:
 * a fence or gun costs the walker the detour it would rather make than break
 * through). Then the field is built with Dijkstra rather than plain BFS.
 */
export class FlowField {
  readonly dist: Int32Array;
  /** Cost of stepping into each cell; null when every step costs 1. */
  private readonly enter: Int32Array | null;

  constructor(
    readonly grid: Grid,
    goals: Cell[],
    readonly walkable: (x: number, y: number) => boolean,
    cost?: (x: number, y: number) => number,
  ) {
    this.dist = new Int32Array(grid.cols * grid.rows).fill(-1);
    if (cost) {
      this.enter = new Int32Array(grid.cols * grid.rows);
      for (let y = 0; y < grid.rows; y++) for (let x = 0; x < grid.cols; x++) this.enter[grid.index(x, y)] = cost(x, y);
      this.dijkstra(goals);
      return;
    }
    this.enter = null;
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

  /** Costs are small integers, so a bucket queue does it. */
  private dijkstra(goals: Cell[]): void {
    const { grid } = this;
    const enter = this.enter!;
    const buckets: number[][] = [[]];
    for (const g of goals) {
      const i = grid.index(g.x, g.y);
      this.dist[i] = 0;
      buckets[0]!.push(i);
    }
    for (let d = 0; d < buckets.length; d++) {
      const list = buckets[d];
      if (!list) continue;
      for (const i of list) {
        if (this.dist[i] !== d) continue;
        const x = i % grid.cols;
        const y = (i - x) / grid.cols;
        // A walker on a neighbour reaches the goal by stepping into this cell first.
        const via = d + enter[i]!;
        for (const [dx, dy] of DIRS) {
          const nx = x + dx;
          const ny = y + dy;
          if (!grid.inBounds(nx, ny) || !this.walkable(nx, ny)) continue;
          const ni = grid.index(nx, ny);
          if (this.dist[ni] !== -1 && this.dist[ni]! <= via) continue;
          this.dist[ni] = via;
          (buckets[via] ??= []).push(ni);
        }
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
    // The neighbour this cell's distance came through: its own distance plus the cost of stepping in.
    let best: Cell | null = null;
    let bestVia = here + 1;
    for (const [dx, dy] of DIRS) {
      const d = this.distanceAt(x + dx, y + dy);
      if (d < 0) continue;
      const via = d + (this.enter ? this.enter[this.grid.index(x + dx, y + dy)]! : 1);
      if (via < bestVia) {
        bestVia = via;
        best = { x: x + dx, y: y + dy };
      }
    }
    return best;
  }
}
