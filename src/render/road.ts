import type { Game } from '../sim/game';
import type { Point } from './iso';

/**
 * Centre line of the road for every spawn, in grid cells: from far before the
 * spawn (the road comes in from off screen), through every corner, to far past
 * the goal. Only the corner points are listed.
 */
export function roadCentreLines(game: Game, reach: number): Point[][] {
  const { flow, map } = game;
  const lines: Point[][] = [];
  for (const spawn of map.spawns) {
    const cells = [spawn];
    for (let n = flow.next(spawn.x, spawn.y); n; n = flow.next(n.x, n.y)) cells.push(n);
    if (cells.length < 2) continue;
    const pts: Point[] = [];
    const first = cells[0]!;
    const second = cells[1]!;
    pts.push({ x: first.x + 0.5 - (second.x - first.x) * reach, y: first.y + 0.5 - (second.y - first.y) * reach });
    for (let i = 1; i < cells.length - 1; i++) {
      const a = cells[i - 1]!;
      const b = cells[i]!;
      const c = cells[i + 1]!;
      if (b.x - a.x !== c.x - b.x || b.y - a.y !== c.y - b.y) pts.push({ x: b.x + 0.5, y: b.y + 0.5 });
    }
    const last = cells[cells.length - 1]!;
    const prev = cells[cells.length - 2]!;
    pts.push({ x: last.x + 0.5 + (last.x - prev.x) * reach, y: last.y + 0.5 + (last.y - prev.y) * reach });
    lines.push(pts);
  }
  return lines;
}

/**
 * Outline of a strip `2 * half` wide around a line of straight runs joined by
 * right-angle corners: one closed polygon with square (mitred) corners.
 */
export function stripOutline(line: Point[], half: number): Point[] {
  const dir = (a: Point, b: Point): Point => {
    const d = Math.hypot(b.x - a.x, b.y - a.y) || 1;
    return { x: (b.x - a.x) / d, y: (b.y - a.y) / d };
  };
  const left: Point[] = [];
  const right: Point[] = [];
  for (let i = 0; i < line.length; i++) {
    const p = line[i]!;
    const din = i > 0 ? dir(line[i - 1]!, p) : dir(p, line[i + 1]!);
    const dout = i < line.length - 1 ? dir(p, line[i + 1]!) : din;
    // Left normals of the two runs; at a right-angle corner their sum is the mitre.
    const same = Math.abs(din.x - dout.x) + Math.abs(din.y - dout.y) < 1e-9;
    const nx = same ? -din.y : -din.y - dout.y;
    const ny = same ? din.x : din.x + dout.x;
    left.push({ x: p.x + nx * half, y: p.y + ny * half });
    right.push({ x: p.x - nx * half, y: p.y - ny * half });
  }
  return [...left, ...right.reverse()];
}
