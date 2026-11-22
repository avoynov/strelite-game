import { Container, Graphics, Sprite } from 'pixi.js';
import type { TowerArt } from './towers/spriteTowerView';
import { box, type Look } from './fenceView';
import { depth, isoX, isoY } from './iso';
import type { BuildingKind } from '../sim/base';

/** How a building looks now: whole, hit hard, in ruins, or (the headquarters) held by the enemy. */
export type BuildingState = 'ok' | 'damaged' | 'rubble' | 'occupied';

/**
 * The base's buildings: the rendered art (one frame per level, and per state
 * when the manifest has them) once the sheet has loaded, else drawn from
 * simple shapes: the headquarters (a stone keep that grows a storey and
 * battlements with each level, a flag on top), the laboratory (a brick hall
 * with a glass dome), the muster (a timber hall with a brass bugle on a post),
 * the arsenal (a shed with gun barrels racked by it) and the treasury (a
 * squat strongroom with a vault door and gold). Ruins are a heap of rubble;
 * a headquarters held by the enemy flies the enemy's black flag. Coordinates
 * are tiles from the building's centre; each is 2×2 tiles.
 */

const STONE: Look = { top: 0xb9b3a6, left: 0x6f6a60, right: 0x8e887c, line: 0x45413b };
const DARK_STONE: Look = { top: 0x9a948a, left: 0x57534c, right: 0x736e65, line: 0x35322d };
const EARTH: Look = { top: 0x8a7a5a, left: 0x5a4d36, right: 0x6e5f44, line: 0x3b3223 };
const BRICK: Look = { top: 0x9c5a42, left: 0x5e3426, right: 0x7a4431, line: 0x3a2018 };
const ROOF: Look = { top: 0x4f5d66, left: 0x2f383e, right: 0x3e4a52, line: 0x1d2327 };
const BRASS: Look = { top: 0xd9a441, left: 0x8a6420, right: 0xb0822c, line: 0x5a4114 };

const TIMBER: Look = { top: 0x8b6a45, left: 0x4f3a24, right: 0x6a4e31, line: 0x2e2114 };
const STEEL: Look = { top: 0x7d868c, left: 0x41484d, right: 0x5a6268, line: 0x24292c };
const GOLD: Look = { top: 0xf2c94c, left: 0xa07a1c, right: 0xc89a2a, line: 0x6a5010 };
const RUBBLE: Look = { top: 0x7a746a, left: 0x4a4640, right: 0x605b53, line: 0x2f2c28 };

/** Flag on a pole from a roof point: the player's red, or the enemy's black. */
function flag(g: Graphics, fx: number, fy: number, enemy: boolean): void {
  g.moveTo(fx, fy).lineTo(fx, fy - 30).stroke({ width: 2, color: 0x3a3a3a });
  g.poly([fx, fy - 30, fx + 16, fy - 25, fx, fy - 20]).fill(enemy ? 0x1c1c1c : 0xc8323c);
  if (enemy) g.circle(fx + 6, fy - 25, 2).fill(0xd9a441);
}

function drawHq(g: Graphics, level: number, enemy = false): void {
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
  flag(g, isoX(0, 0), isoY(0, 0, top), enemy);
}

function drawMuster(g: Graphics, level: number): void {
  // Timber hall on a stone plinth, a brass bugle on a post by the door, banners from level 3.
  box(g, -0.95, -0.95, 0.95, 0.95, 0, 0.06, DARK_STONE);
  const h = 0.4 + 0.07 * level;
  box(g, -0.7, -0.6, 0.55, 0.55, 0.06, h, TIMBER);
  box(g, -0.75, -0.65, 0.6, 0.6, h, h + 0.08, ROOF);
  // The bugle: a post and a brass horn flaring towards the viewer.
  box(g, 0.62, 0.62, 0.72, 0.72, 0.06, 0.62, TIMBER);
  const bx = isoX(0.67, 0.67);
  const by = isoY(0.67, 0.67, 0.62);
  g.moveTo(bx - 10, by - 2).lineTo(bx + 6, by - 6).stroke({ width: 3, color: 0xb0822c, cap: 'round' });
  g.ellipse(bx + 9, by - 7, 5, 6).fill(0xd9a441).stroke({ width: 1, color: 0x5a4114 });
  if (level >= 2) {
    for (const x of [-0.5, 0.1]) {
      const px = isoX(x, 0.55);
      const py = isoY(x, 0.55, h);
      g.rect(px - 3, py, 6, 14).fill(0xc8323c);
    }
  }
}

function drawArsenal(g: Graphics, level: number): void {
  // Steel-roofed shed; barrels racked along its front, more with each level.
  box(g, -0.95, -0.95, 0.95, 0.95, 0, 0.06, DARK_STONE);
  const h = 0.42 + 0.06 * level;
  box(g, -0.75, -0.75, 0.45, 0.45, 0.06, h, BRICK);
  box(g, -0.8, -0.8, 0.5, 0.5, h, h + 0.07, STEEL);
  const n = 2 + Math.min(level, 3);
  for (let i = 0; i < n; i++) {
    const y = -0.6 + i * 0.28;
    box(g, 0.55, y, 0.9, y + 0.1, 0.06, 0.16, STEEL);
  }
  // Wide doors.
  g.poly([isoX(-0.45, 0.45), isoY(-0.45, 0.45, 0.06), isoX(0.15, 0.45), isoY(0.15, 0.45, 0.06), isoX(0.15, 0.45), isoY(0.15, 0.45, h * 0.8), isoX(-0.45, 0.45), isoY(-0.45, 0.45, h * 0.8)]).fill(0x2a241d);
}

function drawTreasury(g: Graphics, level: number): void {
  // A squat strongroom of dressed stone with a round vault door and gold stacked by it.
  box(g, -0.95, -0.95, 0.95, 0.95, 0, 0.06, DARK_STONE);
  const h = 0.38 + 0.05 * level;
  box(g, -0.65, -0.65, 0.55, 0.55, 0.06, h, STONE);
  box(g, -0.7, -0.7, 0.6, 0.6, h, h + 0.06, BRASS);
  const dx = isoX(0.55, -0.05);
  const dy = isoY(0.55, -0.05, h * 0.5);
  g.ellipse(dx, dy, 9, 11).fill(0x5a6268).stroke({ width: 2, color: 0x2b2b2b });
  g.circle(dx, dy, 3).fill(0xd9a441);
  const stacks = 1 + Math.min(level, 3);
  for (let i = 0; i < stacks; i++) box(g, -0.55 + i * 0.25, 0.65, -0.4 + i * 0.25, 0.8, 0.06, 0.14 + 0.03 * i, GOLD);
}

/** A heap of broken masonry and beams where a building stood. */
function drawRubble(g: Graphics, level: number): void {
  box(g, -0.95, -0.95, 0.95, 0.95, 0, 0.05, EARTH);
  const pieces: Array<[number, number, number, number, number]> = [
    [-0.7, -0.6, -0.2, -0.2, 0.22],
    [-0.1, -0.7, 0.4, -0.3, 0.16],
    [-0.6, 0.1, -0.15, 0.55, 0.14],
    [0.1, 0.0, 0.6, 0.45, 0.2],
    [-0.25, -0.2, 0.15, 0.2, 0.3 + 0.04 * level],
  ];
  for (const [x0, y0, x1, y1, z] of pieces) box(g, x0, y0, x1, y1, 0.05, z, RUBBLE);
  // A charred beam across the heap.
  g.moveTo(isoX(-0.6, 0.3), isoY(-0.6, 0.3, 0.25)).lineTo(isoX(0.5, -0.4), isoY(0.5, -0.4, 0.32)).stroke({ width: 4, color: 0x2a1d12, cap: 'round' });
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
  private state: BuildingState = 'ok';
  private readonly off: (() => void) | undefined;

  /**
   * @param x, y  the building's centre in grid cells
   * @param art   rendered art, or null for the drawn stand-in
   * @param scale sprite scale that puts @1x art at real size on the board
   */
  constructor(
    readonly kind: BuildingKind,
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
  update(level: number, state: BuildingState = 'ok'): void {
    this.level = level;
    this.state = state;
    this.draw();
  }

  destroy(): void {
    this.off?.();
    this.node.destroy({ children: true });
  }

  /** The rendered frame for the level and state, when the manifest has one. */
  private texture() {
    const def = this.art?.manifest.buildings?.[this.kind];
    if (!def) return undefined;
    const pick = (list: string[] | undefined) => list?.[Math.min(this.level, list.length - 1)];
    if (this.state !== 'ok') {
      const frame = pick(def.states?.[this.state]);
      // No rendered state yet: ruins and an enemy flag are drawn; damage shows on the whole building.
      if (frame) return this.art!.sheetTexture(def.states!.sheet, frame);
      if (this.state !== 'damaged') return undefined;
    }
    const frame = pick(def.levels);
    return frame ? this.art!.sheetTexture(def.sheet, frame) : undefined;
  }

  private draw(): void {
    const tex = this.texture();
    const key = tex ? `${tex.uid} ${this.state}` : `drawn ${this.level} ${this.state}`;
    if (key === this.key) return;
    this.key = key;
    this.node.removeChildren().forEach((c) => c.destroy());
    if (tex) {
      const sprite = new Sprite(tex);
      // The frame is anchored at the building's ground centre (below the frame's middle).
      sprite.anchor.set(tex.defaultAnchor?.x ?? 0.5, tex.defaultAnchor?.y ?? 0.5);
      sprite.scale.set(this.scale);
      if (this.state === 'damaged' && !this.art?.manifest.buildings?.[this.kind]?.states?.damaged) sprite.tint = 0xb8aca0;
      this.node.addChild(sprite);
      if (this.state === 'occupied' && !this.art?.manifest.buildings?.[this.kind]?.states?.occupied) {
        const g = new Graphics();
        flag(g, isoX(0, 0), isoY(0, 0, 1.6), true);
        this.node.addChild(g);
      }
      return;
    }
    const g = new Graphics();
    if (this.state === 'rubble' || (this.state === 'occupied' && this.kind !== 'hq')) drawRubble(g, this.level);
    else if (this.kind === 'hq') drawHq(g, this.level, this.state === 'occupied');
    else if (this.kind === 'lab') drawLab(g, this.level);
    else if (this.kind === 'muster') drawMuster(g, this.level);
    else if (this.kind === 'arsenal') drawArsenal(g, this.level);
    else drawTreasury(g, this.level);
    if (this.state === 'damaged') g.tint = 0xb8aca0;
    this.node.addChild(g);
  }
}
