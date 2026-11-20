import { Container, Graphics, Sprite } from 'pixi.js';
import type { TowerArt } from './towers/spriteTowerView';
import { box, type Look } from './fenceView';
import { depth, isoX, isoY } from './iso';

/**
 * The base's buildings: the rendered art (one frame per level) when the
 * manifest has it and the sheet has loaded, else drawn from simple shapes: the
 * headquarters (a stone keep that grows a storey and battlements with each
 * level, a flag on top) and the laboratory (a brick hall with a glass dome,
 * a brass chimney and, at higher levels, an annex and a mast). Coordinates
 * are tiles from the building's centre; each is 2×2 tiles.
 */

const STONE: Look = { top: 0xb9b3a6, left: 0x6f6a60, right: 0x8e887c, line: 0x45413b };
const DARK_STONE: Look = { top: 0x9a948a, left: 0x57534c, right: 0x736e65, line: 0x35322d };
const EARTH: Look = { top: 0x8a7a5a, left: 0x5a4d36, right: 0x6e5f44, line: 0x3b3223 };
const BRICK: Look = { top: 0x9c5a42, left: 0x5e3426, right: 0x7a4431, line: 0x3a2018 };
const ROOF: Look = { top: 0x4f5d66, left: 0x2f383e, right: 0x3e4a52, line: 0x1d2327 };
const BRASS: Look = { top: 0xd9a441, left: 0x8a6420, right: 0xb0822c, line: 0x5a4114 };

function drawHq(g: Graphics, level: number): void {
  // Earth rampart round a stone keep; each level adds height and, from level 3, corner towers.
  box(g, -1, -1, 1, 1, 0, 0.12, EARTH);
  const h = 0.55 + 0.18 * level;
  if (level >= 2) {
    for (const [x, y] of [[-0.85, -0.85], [0.45, -0.85], [-0.85, 0.45]] as const) box(g, x, y, x + 0.4, y + 0.4, 0.12, h * 0.75, DARK_STONE);
  }
  box(g, -0.62, -0.62, 0.62, 0.62, 0.12, h, STONE);
  // Battlements along the two front edges.
  const n = 4;
  for (let i = 0; i < n; i++) {
    const a = -0.62 + (i * 1.24) / n;
    box(g, a, 0.5, a + 0.16, 0.62, h, h + 0.08, STONE);
    box(g, 0.5, a, 0.62, a + 0.16, h, h + 0.08, STONE);
  }
  if (level >= 2) for (const [x, y] of [[0.45, 0.45]] as const) box(g, x, y, x + 0.4, y + 0.4, 0.12, h * 0.75, DARK_STONE);
  if (level >= 4) box(g, -0.3, -0.3, 0.3, 0.3, h, h + 0.35, STONE);
  // Doorway on the front-left face.
  g.poly([isoX(-0.15, 0.62), isoY(-0.15, 0.62, 0.12), isoX(0.15, 0.62), isoY(0.15, 0.62, 0.12), isoX(0.15, 0.62), isoY(0.15, 0.62, 0.36), isoX(-0.15, 0.62), isoY(-0.15, 0.62, 0.36)]).fill(0x2a241d);
  // Flag.
  const top = h + (level >= 4 ? 0.35 : 0.08);
  const fx = isoX(0, 0);
  const fy = isoY(0, 0, top);
  g.moveTo(fx, fy).lineTo(fx, fy - 30).stroke({ width: 2, color: 0x3a3a3a });
  g.poly([fx, fy - 30, fx + 16, fy - 25, fx, fy - 20]).fill(0xc8323c);
}

function drawLab(g: Graphics, level: number): void {
  box(g, -0.95, -0.95, 0.95, 0.95, 0, 0.06, DARK_STONE);
  if (level >= 2) box(g, -0.85, 0.15, -0.15, 0.85, 0.06, 0.4, BRICK);
  const h = 0.45 + 0.08 * level;
  box(g, -0.6, -0.75, 0.6, 0.4, 0.06, h, BRICK);
  box(g, -0.65, -0.8, 0.65, 0.45, h, h + 0.06, ROOF);
  // Windows along the front face.
  for (let i = 0; i < 3; i++) {
    const a = -0.45 + i * 0.35;
    g.poly([isoX(a, 0.4), isoY(a, 0.4, h * 0.35), isoX(a + 0.18, 0.4), isoY(a + 0.18, 0.4, h * 0.35), isoX(a + 0.18, 0.4), isoY(a + 0.18, 0.4, h * 0.75), isoX(a, 0.4), isoY(a, 0.4, h * 0.75)]).fill(0xf2d27a);
  }
  // Glass dome.
  const dx = isoX(-0.05, -0.2);
  const dy = isoY(-0.05, -0.2, h + 0.06);
  const r = 13 + 2 * level;
  g.ellipse(dx, dy, r, r * 0.5).fill(0x3d5560);
  g.moveTo(dx - r, dy).arc(dx, dy, r, Math.PI, 0).fill({ color: 0x9fd4e6, alpha: 0.85 }).stroke({ width: 1, color: 0x5b7c88 });
  // Brass chimney with a puff.
  box(g, 0.3, -0.7, 0.45, -0.55, h, h + 0.35, BRASS);
  if (level >= 3) {
    // Radio mast.
    const mx = isoX(0.55, 0.3);
    const my = isoY(0.55, 0.3, h + 0.06);
    g.moveTo(mx, my).lineTo(mx, my - 26 - 4 * level).stroke({ width: 1.5, color: 0x2b2b2b });
    g.circle(mx, my - 26 - 4 * level, 2.5).fill(0xe0624f);
  }
}

export class BuildingView {
  readonly node = new Container();
  private key = '';
  private level = 0;
  private readonly off: (() => void) | undefined;

  /**
   * @param x, y  the building's centre in grid cells
   * @param art   rendered art, or null for the drawn stand-in
   * @param scale sprite scale that puts @1x art at real size on the board
   */
  constructor(
    readonly kind: 'hq' | 'lab',
    x: number,
    y: number,
    private readonly art: TowerArt | null = null,
    private readonly scale = 1,
  ) {
    this.node.position.set(isoX(x, y), isoY(x, y));
    this.node.zIndex = depth(x, y);
    // Redraw once the sheet arrives (or the zoom swaps @1x for @2x).
    this.off = art?.onChange(() => this.draw());
  }

  /** @param level 0-based, as in the base's state */
  update(level: number): void {
    this.level = level;
    this.draw();
  }

  destroy(): void {
    this.off?.();
    this.node.destroy({ children: true });
  }

  private draw(): void {
    const def = this.art?.manifest.buildings?.[this.kind];
    const frame = def?.levels[Math.min(this.level, def.levels.length - 1)];
    const tex = def && frame ? this.art!.sheetTexture(def.sheet, frame) : undefined;
    const key = tex ? `${tex.uid}` : `drawn ${this.level}`;
    if (key === this.key) return;
    this.key = key;
    this.node.removeChildren().forEach((c) => c.destroy());
    if (tex) {
      const sprite = new Sprite(tex);
      // The frame is anchored at the building's ground centre (below the frame's middle).
      sprite.anchor.set(tex.defaultAnchor?.x ?? 0.5, tex.defaultAnchor?.y ?? 0.5);
      sprite.scale.set(this.scale);
      this.node.addChild(sprite);
      return;
    }
    const g = new Graphics();
    if (this.kind === 'hq') drawHq(g, this.level);
    else drawLab(g, this.level);
    this.node.addChild(g);
  }
}
