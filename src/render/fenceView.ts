import { Container, Graphics, Sprite } from 'pixi.js';
import { depth, isoX, isoY } from './iso';
import type { TowerArt } from './towers/spriteTowerView';

/**
 * Siege mode fences. Each fence tile is drawn as pieces: a post in the middle
 * and a half wall from the middle to each edge that has a fence beyond it, so
 * neighbouring tiles join into one thin wall. Rendered pieces come from the
 * art manifest (`fences.wood|stone|steel`, pieces `post px nx py ny`) once
 * they exist; until then the same pieces are drawn from simple shapes.
 */

export const FENCE_MATERIALS = ['wood', 'stone', 'steel'] as const;
export type FencePiece = 'post' | 'px' | 'nx' | 'py' | 'ny';

/** Neighbour bits: a fence on the +x, −x, +y, −y side. */
export const PX = 1;
export const NX = 2;
export const PY = 4;
export const NY = 8;

/** Wall height in tiles (a tile is 4 m): a 2 m palisade, a 1.8 m stone wall, a 2.2 m steel wall. */
export const FENCE_HEIGHT = [0.5, 0.45, 0.55] as const;

/**
 * The pieces a tile shows, back to front. A fence with no neighbours stands as
 * a short straight wall along x; one with a single neighbour ends in its post.
 */
export function fencePieces(mask: number): FencePiece[] {
  const m = mask || PX | NX;
  const back: FencePiece[] = [];
  const front: FencePiece[] = [];
  if (m & NY) back.push('ny');
  if (m & NX) back.push('nx');
  if (m & PY) front.push('py');
  if (m & PX) front.push('px');
  return [...back, 'post', ...front];
}

interface Look {
  top: number;
  left: number;
  right: number;
  line: number;
}

const LOOKS: readonly Look[] = [
  { top: 0xa47a48, left: 0x6b4b2a, right: 0x86613a, line: 0x3e2a17 },
  { top: 0xb3ada0, left: 0x6f6a60, right: 0x8c877c, line: 0x4c4841 },
  { top: 0x8995a1, left: 0x48525c, right: 0x616c77, line: 0x262c32 },
];

/** An upright box [x0, x1] × [y0, y1] from height z0 to z1 (tiles), seen from the camera's corner. */
function box(g: Graphics, x0: number, y0: number, x1: number, y1: number, z0: number, z1: number, look: Look): void {
  const p = (x: number, y: number, z: number) => [isoX(x, y), isoY(x, y, z)] as const;
  const [lbx, lby] = p(x0, y1, z0);
  const [bbx, bby] = p(x1, y1, z0);
  const [rbx, rby] = p(x1, y0, z0);
  const [ltx, lty] = p(x0, y1, z1);
  const [btx, bty] = p(x1, y1, z1);
  const [rtx, rty] = p(x1, y0, z1);
  const [ttx, tty] = p(x0, y0, z1);
  g.poly([lbx, lby, bbx, bby, btx, bty, ltx, lty]).fill(look.left);
  g.poly([bbx, bby, rbx, rby, rtx, rty, btx, bty]).fill(look.right);
  g.poly([ttx, tty, rtx, rty, btx, bty, ltx, lty]).fill(look.top).stroke({ width: 0.8, color: look.line, alpha: 0.6 });
}

/** A line across the front face of an arm (the +y face of an x arm, the +x face of a y arm). */
function seam(g: Graphics, alongX: boolean, a0: number, a1: number, side: number, z0: number, z1: number, look: Look, alpha = 0.55): void {
  const [x0, y0] = alongX ? [a0, side] : [side, a0];
  const [x1, y1] = alongX ? [a1, side] : [side, a1];
  g.moveTo(isoX(x0, y0), isoY(x0, y0, z0)).lineTo(isoX(x1, y1), isoY(x1, y1, z1)).stroke({ width: 0.9, color: look.line, alpha });
}

/** Extent of a half wall along its axis: from the middle to the tile edge. */
function span(piece: FencePiece): { alongX: boolean; a0: number; a1: number } {
  const alongX = piece === 'px' || piece === 'nx';
  return piece === 'px' || piece === 'py' ? { alongX, a0: 0, a1: 0.5 } : { alongX, a0: -0.5, a1: 0 };
}

function armBox(g: Graphics, piece: FencePiece, half: number, z0: number, z1: number, look: Look): void {
  const { alongX, a0, a1 } = span(piece);
  if (alongX) box(g, a0, -half, a1, half, z0, z1, look);
  else box(g, -half, a0, half, a1, z0, z1, look);
}

/** Wood: a palisade of sharpened stakes bound with two rope bands. */
function drawWood(g: Graphics, piece: FencePiece, h: number, look: Look): void {
  if (piece === 'post') {
    box(g, -0.08, -0.08, 0.08, 0.08, 0, h * 1.15, look);
    return;
  }
  const { alongX, a0, a1 } = span(piece);
  const n = 5;
  const w = (a1 - a0) / n;
  for (let i = 0; i < n; i++) {
    const s0 = a0 + i * w + 0.005;
    const s1 = s0 + w - 0.01;
    const top = h * (0.92 + 0.08 * (((i * 7 + (alongX ? 1 : 3)) % 5) / 4));
    if (alongX) box(g, s0, -0.05, s1, 0.05, 0, top, look);
    else box(g, -0.05, s0, 0.05, s1, 0, top, look);
    // The sharpened tip.
    const m = (s0 + s1) / 2;
    const [tx, ty] = alongX ? [m, 0.05] : [0.05, m];
    const [ax, ay] = alongX ? [s0, 0.05] : [0.05, s0];
    const [bx, by] = alongX ? [s1, 0.05] : [0.05, s1];
    g.poly([isoX(ax, ay), isoY(ax, ay, top), isoX(bx, by), isoY(bx, by, top), isoX(tx, ty), isoY(tx, ty, top + 0.07)]).fill(look.top);
  }
  for (const z of [0.3, 0.75]) seam(g, alongX, a0, a1, 0.052, h * z, h * z, { ...look, line: 0xc9b07a }, 0.85);
}

/** Stone: dressed blocks in staggered courses under a wider coping. */
function drawStone(g: Graphics, piece: FencePiece, h: number, look: Look): void {
  if (piece === 'post') {
    box(g, -0.15, -0.15, 0.15, 0.15, 0, h * 1.12, look);
    box(g, -0.18, -0.18, 0.18, 0.18, h * 1.12, h * 1.2, look);
    return;
  }
  armBox(g, piece, 0.1, 0, h, look);
  armBox(g, piece, 0.13, h, h * 1.08, look);
  const { alongX, a0, a1 } = span(piece);
  const courses = 3;
  for (let c = 1; c < courses; c++) seam(g, alongX, a0, a1, 0.1, (h * c) / courses, (h * c) / courses, look);
  for (let c = 0; c < courses; c++) {
    const off = c % 2 ? 0.125 : 0;
    for (let a = a0 + 0.25 - off; a < a1; a += 0.25) if (a > a0) seam(g, alongX, a, a, 0.1, (h * c) / courses, (h * (c + 1)) / courses, look);
  }
}

/** Steel: riveted plates on a frame, a brass-capped post. */
function drawSteel(g: Graphics, piece: FencePiece, h: number, look: Look): void {
  if (piece === 'post') {
    box(g, -0.1, -0.1, 0.1, 0.1, 0, h * 1.18, look);
    box(g, -0.12, -0.12, 0.12, 0.12, h * 1.18, h * 1.25, { top: 0xd9a441, left: 0x8a6420, right: 0xb0822c, line: 0x5a4114 });
    return;
  }
  armBox(g, piece, 0.06, 0, h, look);
  const { alongX, a0, a1 } = span(piece);
  for (const a of [a0 + 0.17, a0 + 0.34]) seam(g, alongX, a, a, 0.06, 0, h, look, 0.8);
  seam(g, alongX, a0, a1, 0.06, h * 0.92, h * 0.92, look, 0.8);
  for (let a = a0 + 0.06; a < a1; a += 0.085) {
    for (const z of [0.12, 0.8]) {
      const [x, y] = alongX ? [a, 0.062] : [0.062, a];
      g.circle(isoX(x, y), isoY(x, y, h * z), 1).fill(0xc9d2da);
    }
  }
}

const DRAW = [drawWood, drawStone, drawSteel] as const;

export class FenceView {
  readonly node = new Container();
  private key = '';

  constructor(
    private readonly art: TowerArt | null,
    /** Sprite scale that puts @1x art at real size on the board. */
    private readonly artScale: number,
    gx: number,
    gy: number,
  ) {
    this.node.position.set(isoX(gx, gy), isoY(gx, gy));
    this.node.zIndex = depth(gx, gy);
  }

  /** Redraw when the level, the neighbours or the art's readiness changed. */
  update(level: number, mask: number): void {
    const pieces = fencePieces(mask);
    const def = this.art?.manifest.fences?.[FENCE_MATERIALS[level] ?? 'steel'];
    const textures = def ? pieces.map((p) => this.art!.sheetTexture(def.sheet, def[p])) : [];
    const rendered = def !== undefined && textures.every(Boolean);
    const key = `${level}:${mask}:${rendered}`;
    if (key === this.key) return;
    this.key = key;
    this.node.removeChildren().forEach((c) => c.destroy());
    if (rendered) {
      for (const t of textures) {
        const s = new Sprite(t!);
        s.anchor.set(0.5);
        s.scale.set(this.artScale);
        this.node.addChild(s);
      }
      return;
    }
    const g = new Graphics();
    const lvl = Math.min(level, 2);
    for (const p of pieces) DRAW[lvl]!(g, p, FENCE_HEIGHT[lvl]!, LOOKS[lvl]!);
    this.node.addChild(g);
  }

  destroy(): void {
    this.node.destroy({ children: true });
  }
}
