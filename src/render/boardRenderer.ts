import { Container, Graphics, Text } from 'pixi.js';
import type { Game } from '../sim/game';
import { PALETTE } from './palette';

export interface Selection {
  kind: 'cell' | 'tower';
  x: number;
  y: number;
}

interface FloatText {
  node: Text;
  age: number;
  /** Ground position in grid units and height above it, in cells. */
  gx: number;
  gy: number;
  h: number;
}

const FLOAT_LIFE = 0.9;
/** Screen pixels per cell of height, as a fraction of the tile width. */
const RISE = 0.55;
/** Room above the top tile for tall objects, as a fraction of the tile width. */
const HEADROOM = 0.6;

/**
 * Isometric view, Clash of Clans style: square cells become 2:1 diamonds seen
 * from a corner, objects stand up from the ground and are drawn back to front.
 * Phase 3 replaces the shapes with rendered sprites; the simulation does not
 * know or care how it is drawn.
 */
export class BoardRenderer {
  readonly root = new Container();
  private readonly ground = new Graphics();
  private readonly overlay = new Graphics();
  private readonly objects = new Graphics();
  private readonly shots = new Graphics();
  private readonly floats = new Container();
  private floatTexts: FloatText[] = [];
  /** Tile width in screen pixels (tile height is half of it). */
  cell = 48;

  constructor(private readonly game: Game) {
    this.root.addChild(this.ground, this.overlay, this.objects, this.shots, this.floats);
    this.drawGround();
  }

  /** Grid point + height (cells) to local screen x. */
  private ix(gx: number, gy: number): number {
    return ((gx - gy) * this.cell) / 2;
  }
  /** Grid point + height (cells) to local screen y. */
  private iy(gx: number, gy: number, h = 0): number {
    return ((gx + gy) * this.cell) / 4 - h * this.cell * RISE;
  }

  /** Extent of the playable cells in units of tile width, before scaling. */
  private bounds(): { minX: number; maxX: number; minY: number; maxY: number } {
    const { grid } = this.game.map;
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    for (let y = 0; y < grid.rows; y++) {
      for (let x = 0; x < grid.cols; x++) {
        if (grid.get(x, y) === 'blocked') continue;
        minX = Math.min(minX, (x - y - 1) / 2);
        maxX = Math.max(maxX, (x - y + 1) / 2);
        minY = Math.min(minY, (x + y) / 4);
        maxY = Math.max(maxY, (x + y + 2) / 4);
      }
    }
    return { minX, maxX, minY: minY - HEADROOM, maxY };
  }

  /** Full screen size, so the field can be drawn to every edge. */
  private screenW = 0;
  private screenH = 0;

  /** Fit the playable map into the given screen rectangle, centred; the field fills the whole screen. */
  layout(x: number, y: number, w: number, h: number, screenW: number, screenH: number): void {
    this.screenW = screenW;
    this.screenH = screenH;
    const b = this.bounds();
    const bw = b.maxX - b.minX;
    const bh = b.maxY - b.minY;
    this.cell = Math.max(12, Math.floor(Math.min(w / bw, h / bh)));
    const c = this.cell;
    this.root.position.set(Math.round(x + (w - bw * c) / 2 - b.minX * c), Math.round(y + (h - bh * c) / 2 - b.minY * c));
    this.drawGround();
  }

  /** Screen point to grid cell, or null when outside the map. */
  cellAt(px: number, py: number): { x: number; y: number } | null {
    const u = (px - this.root.x) / (this.cell / 2); // gx - gy
    const v = (py - this.root.y) / (this.cell / 4); // gx + gy
    const x = Math.floor((u + v) / 2);
    const y = Math.floor((v - u) / 2);
    const { grid } = this.game.map;
    return grid.inBounds(x, y) && grid.get(x, y) !== 'blocked' ? { x, y } : null;
  }

  /** Screen point at the centre of a cell's ground tile. */
  cellToScreen(x: number, y: number): { x: number; y: number } {
    return { x: this.root.x + this.ix(x + 0.5, y + 0.5), y: this.root.y + this.iy(x + 0.5, y + 0.5) };
  }

  addFloat(text: string, gx: number, gy: number, color: number): void {
    const node = new Text({
      text,
      style: { fontFamily: 'system-ui, sans-serif', fontSize: Math.max(11, this.cell * 0.28), fontWeight: '700', fill: color, stroke: { color: 0x000000, width: 3 } },
    });
    node.anchor.set(0.5);
    this.floats.addChild(node);
    this.floatTexts.push({ node, age: 0, gx, gy, h: 0.9 });
  }

  /** Diamond outline of cell (x, y), inset by `inset` grid units, at height h. */
  private diamond(x: number, y: number, inset = 0, h = 0): number[] {
    const a = inset;
    const b = 1 - inset;
    return [
      this.ix(x + a, y + a), this.iy(x + a, y + a, h),
      this.ix(x + b, y + a), this.iy(x + b, y + a, h),
      this.ix(x + b, y + b), this.iy(x + b, y + b, h),
      this.ix(x + a, y + b), this.iy(x + a, y + b, h),
    ];
  }

  /** Cheap deterministic hash of a cell, 0..1, for scattering decoration. */
  private static hash(x: number, y: number): number {
    let h = Math.imul(x, 374761393) + Math.imul(y, 668265263);
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  }

  /**
   * Road cells outside the map: the path continues straight back from the
   * spawn and straight on past the goal, off the edge of the screen.
   */
  private roadOutside(range: number): Set<string> {
    const cells = new Set<string>();
    const { flow, map } = this.game;
    const extend = (from: { x: number; y: number }, dx: number, dy: number) => {
      for (let i = 1; i <= range; i++) cells.add(`${from.x + dx * i},${from.y + dy * i}`);
    };
    for (const s of map.spawns) {
      const n = flow.next(s.x, s.y);
      if (n) extend(s, s.x - n.x, s.y - n.y);
    }
    for (const g of map.goals) {
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]] as const) {
        if (flow.distanceAt(g.x + dx, g.y + dy) === 1) extend(g, -dx, -dy);
      }
    }
    return cells;
  }

  private drawGround(): void {
    const g = this.ground;
    const c = this.cell;
    const { grid, spawns, goals } = this.game.map;
    const open = (x: number, y: number) => grid.get(x, y) !== 'blocked';
    g.clear();

    // Range of cells that can touch the screen: invert the four screen corners.
    const corners = [
      [0, 0],
      [this.screenW, 0],
      [0, this.screenH],
      [this.screenW, this.screenH],
    ].map(([px, py]) => {
      const u = (px! - this.root.x) / (c / 2);
      const v = (py! - this.root.y) / (c / 4);
      return [(u + v) / 2, (v - u) / 2] as const;
    });
    const x0 = Math.floor(Math.min(...corners.map((p) => p[0]))) - 2;
    const x1 = Math.ceil(Math.max(...corners.map((p) => p[0]))) + 2;
    const y0 = Math.floor(Math.min(...corners.map((p) => p[1]))) - 2;
    const y1 = Math.ceil(Math.max(...corners.map((p) => p[1]))) + 2;
    const road = this.roadOutside(Math.max(x1 - x0, y1 - y0));

    // Tiles, back to front so decoration overlaps correctly.
    const decor: Array<() => void> = [];
    for (let s = x0 + y0; s <= x1 + y1; s++) {
      for (let x = x0; x <= x1; x++) {
        const y = s - x;
        if (y < y0 || y > y1) continue;
        if (open(x, y)) {
          const kind = grid.get(x, y);
          const color = kind === 'path' ? PALETTE.path : (x + y) % 2 ? PALETTE.grass : PALETTE.grassAlt;
          g.poly(this.diamond(x, y)).fill(color);
          if (kind === 'path') g.poly(this.diamond(x, y)).stroke({ width: 1, color: PALETTE.pathEdge, alpha: 0.3 });
          continue;
        }
        if (road.has(`${x},${y}`)) {
          g.poly(this.diamond(x, y)).fill(PALETTE.path);
          g.poly(this.diamond(x, y)).stroke({ width: 1, color: PALETTE.pathEdge, alpha: 0.3 });
          continue;
        }
        const r = BoardRenderer.hash(x, y);
        g.poly(this.diamond(x, y)).fill(r < 0.5 ? PALETTE.field : PALETTE.fieldAlt);
        // Keep the strip next to the map clear so nothing hides the play area.
        const nearMap = [-1, 0, 1].some((dy) => [-1, 0, 1].some((dx) => open(x + dx, y + dy)));
        if (nearMap || road.has(`${x + 1},${y}`) || road.has(`${x},${y + 1}`) || road.has(`${x - 1},${y}`) || road.has(`${x},${y - 1}`)) continue;
        if (r > 0.86) decor.push(() => this.drawTree(x + 0.5, y + 0.5, BoardRenderer.hash(y, x)));
        else if (r > 0.8) decor.push(() => this.drawRock(x + 0.5, y + 0.5));
        else if (r < 0.06) decor.push(() => this.drawTree(x + 0.5, y + 0.5, BoardRenderer.hash(y, x)));
      }
    }

    // Soft light line along the border of the playable area.
    for (let y = 0; y < grid.rows; y++) {
      for (let x = 0; x < grid.cols; x++) {
        if (!open(x, y)) continue;
        const d = this.diamond(x, y);
        const edge = (i: number, j: number) => g.moveTo(d[i]!, d[i + 1]!).lineTo(d[j]!, d[j + 1]!).stroke({ width: 1.5, color: PALETTE.fieldEdge, alpha: 0.35 });
        if (!open(x, y - 1)) edge(0, 2);
        if (!open(x + 1, y)) edge(2, 4);
        if (!open(x, y + 1)) edge(4, 6);
        if (!open(x - 1, y)) edge(6, 0);
      }
    }
    for (const s of spawns) g.poly(this.diamond(s.x, s.y)).fill({ color: PALETTE.spawn, alpha: 0.35 });
    for (const s of goals) g.poly(this.diamond(s.x, s.y)).fill({ color: PALETTE.goal, alpha: 0.6 });
    for (const d of decor) d();
  }

  private drawTree(gx: number, gy: number, v: number): void {
    const g = this.ground;
    const c = this.cell;
    const x = this.ix(gx, gy) + (v - 0.5) * c * 0.2;
    const y = this.iy(gx, gy);
    const s = 0.8 + v * 0.5;
    g.ellipse(x + c * 0.08, y + c * 0.02, c * 0.28 * s, c * 0.12 * s).fill({ color: PALETTE.shadow, alpha: 0.25 });
    g.rect(x - c * 0.04, y - c * 0.2 * s, c * 0.08, c * 0.2 * s).fill(PALETTE.treeTrunk);
    g.circle(x, y - c * 0.38 * s, c * 0.26 * s).fill(PALETTE.treeDark);
    g.circle(x - c * 0.07 * s, y - c * 0.45 * s, c * 0.15 * s).fill(PALETTE.treeLight);
  }

  private drawRock(gx: number, gy: number): void {
    const g = this.ground;
    const c = this.cell;
    const x = this.ix(gx, gy);
    const y = this.iy(gx, gy);
    g.ellipse(x, y - c * 0.04, c * 0.16, c * 0.1).fill(PALETTE.rockShade);
    g.ellipse(x - c * 0.02, y - c * 0.07, c * 0.12, c * 0.07).fill(PALETTE.rock);
  }

  /** Draw one frame. `alpha` interpolates between the last two sim steps. */
  render(alpha: number, selection: Selection | null, dtSeconds: number): void {
    const c = this.cell;
    const game = this.game;

    // Selection outline on the ground + range ellipse (a grid circle seen isometrically).
    const o = this.overlay;
    o.clear();
    if (selection) {
      const tower = selection.kind === 'tower' ? game.towerAt(selection.x, selection.y) : undefined;
      const valid = tower ? true : game.canBuildAt(selection.x, selection.y);
      o.poly(this.diamond(selection.x, selection.y, 0.04)).stroke({ width: 2, color: valid ? PALETTE.hover : PALETTE.invalid });
      if (tower) {
        const rx = (game.levelOf(tower).range * c) / Math.SQRT2;
        o.ellipse(this.ix(tower.cx + 0.5, tower.cy + 0.5), this.iy(tower.cx + 0.5, tower.cy + 0.5), rx, rx / 2)
          .fill({ color: PALETTE.range, alpha: 0.12 })
          .stroke({ width: 1.5, color: PALETTE.range, alpha: 0.6 });
      }
    }

    // Towers and enemies, back to front: larger gx + gy is nearer the camera.
    type Drawable = { depth: number; draw: () => void };
    const list: Drawable[] = [];
    for (const t of game.towers) list.push({ depth: t.cx + t.cy + 1, draw: () => this.drawTower(t.cx, t.cy, t.level, t.aim) });
    for (const e of game.enemies) {
      const gx = e.px + (e.x - e.px) * alpha;
      const gy = e.py + (e.y - e.py) * alpha;
      list.push({ depth: gx + gy, draw: () => this.drawEnemy(gx, gy, e.hp / e.maxHp) });
    }
    list.sort((a, b) => a.depth - b.depth);
    this.objects.clear();
    for (const d of list) d.draw();

    // Bolts fly at roughly turret height.
    const sg = this.shots;
    sg.clear();
    for (const p of game.projectiles) {
      const gx = p.px + (p.x - p.px) * alpha;
      const gy = p.py + (p.y - p.py) * alpha;
      const x = this.ix(gx, gy);
      const y = this.iy(gx, gy, 0.5);
      const dx = this.ix(p.x, p.y) - this.ix(p.px, p.py);
      const dy = this.iy(p.x, p.y) - this.iy(p.px, p.py);
      const d = Math.hypot(dx, dy) || 1;
      const len = c * 0.22;
      sg.moveTo(x - (dx / d) * len, y - (dy / d) * len).lineTo(x, y).stroke({ width: Math.max(2, c * 0.045), color: PALETTE.bolt, cap: 'round' });
    }

    // Floating texts rise and fade.
    this.floatTexts = this.floatTexts.filter((f) => {
      f.age += dtSeconds;
      f.h += dtSeconds * 1.2;
      f.node.position.set(this.ix(f.gx, f.gy), this.iy(f.gx, f.gy, f.h));
      f.node.alpha = Math.max(0, 1 - f.age / FLOAT_LIFE);
      if (f.age >= FLOAT_LIFE) {
        f.node.destroy();
        return false;
      }
      return true;
    });
  }

  /** A square stone plinth with a round turret and a barrel; grows a little per level. */
  private drawTower(cx: number, cy: number, level: number, aim: number): void {
    const g = this.objects;
    const c = this.cell;
    const inset = 0.12;
    const baseH = 0.45 + 0.1 * level;
    const gx = cx + 0.5;
    const gy = cy + 0.5;

    // Shadow towards bottom-right of the tile.
    g.ellipse(this.ix(gx, gy) + c * 0.08, this.iy(gx, gy) + c * 0.03, c * 0.42, c * 0.21).fill({ color: PALETTE.shadow, alpha: 0.25 });

    // Plinth: left (south-west) face, right (south-east) face, then top.
    const a = inset;
    const b = 1 - inset;
    const W = [this.ix(cx + a, cy + b), this.iy(cx + a, cy + b)] as const;
    const S = [this.ix(cx + b, cy + b), this.iy(cx + b, cy + b)] as const;
    const E = [this.ix(cx + b, cy + a), this.iy(cx + b, cy + a)] as const;
    const lift = baseH * c * RISE;
    g.poly([W[0], W[1], S[0], S[1], S[0], S[1] - lift, W[0], W[1] - lift]).fill(PALETTE.towerBaseFront);
    g.poly([S[0], S[1], E[0], E[1], E[0], E[1] - lift, S[0], S[1] - lift]).fill(PALETTE.towerBaseSide);
    g.poly(this.diamond(cx, cy, inset, baseH)).fill(PALETTE.towerBaseTop);
    // Level pips along the left face.
    for (let i = 0; i <= level; i++) {
      const t = 0.25 + i * 0.22;
      g.circle(W[0] + (S[0] - W[0]) * t, W[1] + (S[1] - W[1]) * t - lift / 2, c * 0.04).fill(PALETTE.levelPip);
    }

    // Turret: a short cylinder (iso circle = 2:1 ellipse).
    const x = this.ix(gx, gy);
    const top = this.iy(gx, gy, baseH);
    const r = c * (0.2 + 0.02 * level);
    const th = c * RISE * 0.22;
    g.ellipse(x, top, r, r / 2).fill(PALETTE.towerBody);
    g.rect(x - r, top - th, 2 * r, th).fill(PALETTE.towerBody);
    g.ellipse(x, top - th, r, r / 2).fill(PALETTE.towerTop);

    // Barrel pointing along the aim direction on the ground plane.
    const len = 0.42;
    const bx = this.ix(gx + Math.cos(aim) * len, gy + Math.sin(aim) * len);
    const by = this.iy(gx + Math.cos(aim) * len, gy + Math.sin(aim) * len) - (this.iy(gx, gy) - top) - th;
    g.moveTo(x, top - th).lineTo(bx, by).stroke({ width: c * 0.08, color: PALETTE.towerGun, cap: 'round' });
  }

  private drawEnemy(gx: number, gy: number, hpFrac: number): void {
    const g = this.objects;
    const c = this.cell;
    const x = this.ix(gx, gy);
    const r = c * 0.16;
    g.ellipse(x, this.iy(gx, gy), r * 1.1, r * 0.55).fill({ color: PALETTE.shadow, alpha: 0.3 });
    const cy = this.iy(gx, gy, 0.3);
    g.circle(x, cy, r).fill(PALETTE.enemy).stroke({ width: 2, color: PALETTE.enemyEdge });
    g.circle(x - r * 0.3, cy - r * 0.3, r * 0.35).fill({ color: PALETTE.enemyLight, alpha: 0.7 });
    const bw = c * 0.5;
    const bh = Math.max(3, c * 0.07);
    const by = cy - r - bh - 4;
    g.rect(x - bw / 2, by, bw, bh).fill(PALETTE.hpBack);
    g.rect(x - bw / 2, by, bw * hpFrac, bh).fill(PALETTE.hpFill);
  }
}
