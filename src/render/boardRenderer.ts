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
/** Ground depth foreshortening: 1 = straight down, smaller = flatter camera. */
const TILT = 0.72;
/** Screen pixels per cell of height, as a fraction of the cell size. */
const RISE = 0.8;
/** Visible thickness of the board's front edge, in cells. */
const EDGE = 0.35;
/** Room above the top row for tall objects, in cells. */
const HEADROOM = 0.7;

/**
 * Three-quarter view of the simulation: the camera looks down at an angle, so
 * the ground is foreshortened and towers and enemies stand up from it. Objects
 * are drawn back to front. Phase 2–3 replace the shapes with rendered sprites;
 * the simulation does not know or care how it is drawn.
 */
export class BoardRenderer {
  readonly root = new Container();
  private readonly ground = new Graphics();
  private readonly overlay = new Graphics();
  private readonly objects = new Graphics();
  private readonly shots = new Graphics();
  private readonly floats = new Container();
  private floatTexts: FloatText[] = [];
  /** Width of one cell in screen pixels. */
  cell = 40;

  constructor(private readonly game: Game) {
    this.root.addChild(this.ground, this.overlay, this.objects, this.shots, this.floats);
    this.drawGround();
  }

  /** Ground point (grid units) plus height (cells) to local screen coordinates. */
  private sx(gx: number): number {
    return gx * this.cell;
  }
  private sy(gy: number, h = 0): number {
    return gy * this.cell * TILT - h * this.cell * RISE;
  }

  /** Fit the board into the given screen rectangle, centred. */
  layout(x: number, y: number, w: number, h: number): void {
    const { cols, rows } = this.game.map.grid;
    this.cell = Math.max(8, Math.floor(Math.min(w / cols, h / (rows * TILT + EDGE + HEADROOM))));
    const bw = cols * this.cell;
    const bh = (rows * TILT + EDGE + HEADROOM) * this.cell;
    this.root.position.set(Math.round(x + (w - bw) / 2), Math.round(y + (h - bh) / 2 + HEADROOM * this.cell));
    this.drawGround();
  }

  /** Screen point to grid cell, or null when outside the board. */
  cellAt(px: number, py: number): { x: number; y: number } | null {
    const x = Math.floor((px - this.root.x) / this.cell);
    const y = Math.floor((py - this.root.y) / (this.cell * TILT));
    return this.game.map.grid.inBounds(x, y) ? { x, y } : null;
  }

  addFloat(text: string, gx: number, gy: number, color: number): void {
    const node = new Text({
      text,
      style: { fontFamily: 'system-ui, sans-serif', fontSize: Math.max(11, this.cell * 0.32), fontWeight: '700', fill: color, stroke: { color: 0x000000, width: 3 } },
    });
    node.anchor.set(0.5);
    this.floats.addChild(node);
    this.floatTexts.push({ node, age: 0, gx, gy, h: 0.7 });
  }

  private drawGround(): void {
    const g = this.ground;
    const c = this.cell;
    const ch = c * TILT;
    const { grid, spawns, goals } = this.game.map;
    g.clear();
    for (let y = 0; y < grid.rows; y++) {
      for (let x = 0; x < grid.cols; x++) {
        const path = grid.get(x, y) === 'path';
        const color = path ? PALETTE.path : (x + y) % 2 ? PALETTE.grass : PALETTE.grassAlt;
        g.rect(x * c, y * ch, c, ch).fill(color);
        if (path) g.rect(x * c, y * ch, c, ch).stroke({ width: 1, color: PALETTE.pathEdge, alpha: 0.3 });
      }
    }
    for (const s of spawns) g.rect(s.x * c, s.y * ch, c, ch).fill({ color: PALETTE.spawn, alpha: 0.5 });
    for (const s of goals) g.rect(s.x * c, s.y * ch, c, ch).fill({ color: PALETTE.goal, alpha: 0.6 });
    // Front edge of the board, so it reads as a slab seen from above and in front.
    const bottom = grid.rows * ch;
    const w = grid.cols * c;
    g.rect(0, bottom, w, EDGE * c * 0.55).fill(PALETTE.edgeTop);
    g.rect(0, bottom + EDGE * c * 0.55, w, EDGE * c * 0.45).fill(PALETTE.edgeBottom);
  }

  /** Draw one frame. `alpha` interpolates between the last two sim steps. */
  render(alpha: number, selection: Selection | null, dtSeconds: number): void {
    const c = this.cell;
    const ch = c * TILT;
    const game = this.game;

    // Selection outline on the ground + range ellipse.
    const o = this.overlay;
    o.clear();
    if (selection) {
      const tower = selection.kind === 'tower' ? game.towerAt(selection.x, selection.y) : undefined;
      const valid = tower ? true : game.canBuildAt(selection.x, selection.y);
      o.rect(selection.x * c + 1, selection.y * ch + 1, c - 2, ch - 2).stroke({ width: 2, color: valid ? PALETTE.hover : PALETTE.invalid });
      if (tower) {
        const r = game.levelOf(tower).range * c;
        o.ellipse(this.sx(tower.cx + 0.5), this.sy(tower.cy + 0.5), r, r * TILT)
          .fill({ color: PALETTE.range, alpha: 0.12 })
          .stroke({ width: 1.5, color: PALETTE.range, alpha: 0.6 });
      }
    }

    // Towers and enemies, sorted back to front by ground depth.
    type Drawable = { depth: number; draw: () => void };
    const list: Drawable[] = [];
    for (const t of game.towers) list.push({ depth: t.cy + 0.5, draw: () => this.drawTower(t.cx + 0.5, t.cy + 0.5, t.level, t.aim) });
    for (const e of game.enemies) {
      const gx = e.px + (e.x - e.px) * alpha;
      const gy = e.py + (e.y - e.py) * alpha;
      list.push({ depth: gy, draw: () => this.drawEnemy(gx, gy, e.hp / e.maxHp) });
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
      const dx = p.x - p.px;
      const dy = (p.y - p.py) * TILT;
      const d = Math.hypot(dx, dy) || 1;
      const len = c * 0.25;
      const x = this.sx(gx);
      const y = this.sy(gy, 0.45);
      sg.moveTo(x - (dx / d) * len, y - (dy / d) * len).lineTo(x, y).stroke({ width: Math.max(2, c * 0.05), color: PALETTE.bolt, cap: 'round' });
    }

    // Floating texts rise and fade.
    this.floatTexts = this.floatTexts.filter((f) => {
      f.age += dtSeconds;
      f.h += dtSeconds;
      f.node.position.set(this.sx(f.gx), this.sy(f.gy, f.h));
      f.node.alpha = Math.max(0, 1 - f.age / FLOAT_LIFE);
      if (f.age >= FLOAT_LIFE) {
        f.node.destroy();
        return false;
      }
      return true;
    });
  }

  /** A stone plinth with a round turret and a barrel; grows a little per level. */
  private drawTower(gx: number, gy: number, level: number, aim: number): void {
    const g = this.objects;
    const c = this.cell;
    const x = this.sx(gx);
    const y = this.sy(gy);
    const w = c * 0.78;
    const d = w * TILT;
    const baseH = c * RISE * (0.32 + 0.06 * level);

    g.ellipse(x + c * 0.06, y + c * 0.04, w * 0.6, d * 0.6).fill({ color: PALETTE.shadow, alpha: 0.25 });
    // Plinth: front face then top face.
    g.rect(x - w / 2, y + d / 2 - baseH, w, baseH).fill(PALETTE.towerBaseFront);
    g.rect(x - w / 2, y - d / 2 - baseH, w, d).fill(PALETTE.towerBaseTop);
    g.rect(x - w / 2, y - d / 2 - baseH, w, d).stroke({ width: 1, color: PALETTE.towerBaseFront, alpha: 0.6 });
    for (let i = 0; i <= level; i++) {
      g.circle(x - w / 2 + c * 0.12 + i * c * 0.15, y + d / 2 - baseH / 2, c * 0.045).fill(PALETTE.levelPip);
    }

    // Turret: a short cylinder on top of the plinth.
    const r = c * (0.22 + 0.025 * level);
    const top = y - baseH;
    const th = c * RISE * 0.18;
    g.ellipse(x, top, r, r * TILT).fill(PALETTE.towerBody);
    g.rect(x - r, top - th, 2 * r, th).fill(PALETTE.towerBody);
    g.ellipse(x, top - th, r, r * TILT).fill(PALETTE.towerTop);

    // Barrel, foreshortened along the ground direction.
    const len = c * 0.42;
    const bx = x + Math.cos(aim) * len;
    const by = top - th + Math.sin(aim) * len * TILT;
    g.moveTo(x, top - th).lineTo(bx, by).stroke({ width: c * 0.1, color: PALETTE.towerGun, cap: 'round' });
  }

  private drawEnemy(gx: number, gy: number, hpFrac: number): void {
    const g = this.objects;
    const c = this.cell;
    const x = this.sx(gx);
    const y = this.sy(gy);
    const r = c * 0.2;
    g.ellipse(x, y, r * 1.05, r * 1.05 * TILT * 0.6).fill({ color: PALETTE.shadow, alpha: 0.3 });
    const cy = this.sy(gy, 0.28);
    g.circle(x, cy, r).fill(PALETTE.enemy).stroke({ width: 2, color: PALETTE.enemyEdge });
    g.circle(x - r * 0.3, cy - r * 0.3, r * 0.35).fill({ color: PALETTE.enemyLight, alpha: 0.7 });
    const bw = c * 0.6;
    const bh = Math.max(3, c * 0.08);
    const by = cy - r - bh - 4;
    g.rect(x - bw / 2, by, bw, bh).fill(PALETTE.hpBack);
    g.rect(x - bw / 2, by, bw * hpFrac, bh).fill(PALETTE.hpFill);
  }
}
