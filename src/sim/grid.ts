export type CellKind = 'build' | 'path' | 'blocked';

export interface Cell {
  x: number;
  y: number;
}

export class Grid {
  readonly cells: CellKind[];

  constructor(
    readonly cols: number,
    readonly rows: number,
    fill: CellKind = 'build',
  ) {
    this.cells = new Array<CellKind>(cols * rows).fill(fill);
  }

  inBounds(x: number, y: number): boolean {
    return x >= 0 && y >= 0 && x < this.cols && y < this.rows;
  }

  index(x: number, y: number): number {
    return y * this.cols + x;
  }

  get(x: number, y: number): CellKind {
    return this.inBounds(x, y) ? (this.cells[this.index(x, y)] ?? 'blocked') : 'blocked';
  }

  set(x: number, y: number, kind: CellKind): void {
    if (this.inBounds(x, y)) this.cells[this.index(x, y)] = kind;
  }
}
