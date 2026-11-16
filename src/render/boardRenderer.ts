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
}

const FLOAT_LIFE = 0.9;

/**
 * Flat top-down view of the simulation. Phase 2 swaps this for an isometric
 * renderer; the simulation does not know or care which one draws it.
 */
export class BoardRenderer {
  readonly root = new Container();
  private readonly ground = new Graphics();
  private readonly overlay = new Graphics();
  private readonly towers = new Graphics();
  private readonly enemies = new Graphics();
  private readonly shots = new Graphics();
  private readonly floats = new Container();
  private floatTexts: FloatText[] = [];
  /** Size of one cell in screen pixels. */
  cell = 40;

  constructor(private readonly game: Game) {
    this.root.addChild(this.ground, this.overlay, this.towers, this.enemies, this.shots, this.floats);
    this.drawGround();
  }

  /** Fit the board into the given screen rectangle, centred. */
  layout(x: number, y: number, w: number, h: number): void {
    const { cols, rows } = this.game.map.grid;
    this.cell = Math.max(8, Math.floor(Math.min(w / cols, h / rows)));
    this.root.position.set(Math.round(x + (w - cols * this.cell) / 2), Math.round(y + (h - rows * this.cell) / 2));
    this.drawGround();
  }

  /** Screen point to grid cell, or null when outside the board. */
  cellAt(sx: number, sy: number): { x: number; y: number } | null {
    const lx = (sx - this.root.x) / this.cell;
    const ly = (sy - this.root.y) / this.cell;
    const x = Math.floor(lx);
    const y = Math.floor(ly);
    return this.game.map.grid.inBounds(x, y) ? { x, y } : null;
  }

  addFloat(text: string, gx: number, gy: number, color: number): void {
    const node = new Text({
      text,
      style: { fontFamily: 'system-ui, sans-serif', fontSize: Math.max(11, this.cell * 0.32), fontWeight: '700', fill: color, stroke: { color: 0x000000, width: 3 } },
    });
    node.anchor.set(0.5);
    node.position.set(gx * this.cell, gy * this.cell);
    this.floats.addChild(node);
    this.floatTexts.push({ node, age: 0 });
  }

  private drawGround(): void {
    const g = this.ground;
    const c = this.cell;
    const { grid, spawns, goals } = this.game.map;
    g.clear();
    for (let y = 0; y < grid.rows; y++) {
      for (let x = 0; x < grid.cols; x++) {
        const kind = grid.get(x, y);
        const color = kind === 'path' ? PALETTE.path : (x + y) % 2 ? PALETTE.grass : PALETTE.grassAlt;
        g.rect(x * c, y * c, c, c).fill(color);
        if (kind === 'path') g.rect(x * c, y * c, c, c).stroke({ width: 1, color: PALETTE.pathEdge, alpha: 0.35 });
      }
    }
    for (const s of spawns) g.rect(s.x * c, s.y * c, c, c).fill({ color: PALETTE.spawn, alpha: 0.5 });
    for (const s of goals) g.rect(s.x * c, s.y * c, c, c).fill({ color: PALETTE.goal, alpha: 0.6 });
  }

  /** Draw one frame. `alpha` interpolates between the last two sim steps. */
  render(alpha: number, selection: Selection | null, dtSeconds: number): void {
    const c = this.cell;
    const game = this.game;

    // Selection highlight + range ring.
    const o = this.overlay;
    o.clear();
    if (selection) {
      const tower = selection.kind === 'tower' ? game.towerAt(selection.x, selection.y) : undefined;
      const valid = tower ? true : game.canBuildAt(selection.x, selection.y);
      o.rect(selection.x * c + 1, selection.y * c + 1, c - 2, c - 2).stroke({ width: 2, color: valid ? PALETTE.hover : PALETTE.invalid });
      if (tower) {
        const r = game.levelOf(tower).range * c;
        o.circle((tower.cx + 0.5) * c, (tower.cy + 0.5) * c, r).fill({ color: PALETTE.range, alpha: 0.12 }).stroke({ width: 1.5, color: PALETTE.range, alpha: 0.6 });
      }
    }

    // Towers: square base, round top, a barrel pointing at the target, level pips.
    const tg = this.towers;
    tg.clear();
    for (const t of game.towers) {
      const cx = (t.cx + 0.5) * c;
      const cy = (t.cy + 0.5) * c;
      const pad = c * 0.12;
      tg.roundRect(t.cx * c + pad, t.cy * c + pad, c - 2 * pad, c - 2 * pad, c * 0.12).fill(PALETTE.towerBase);
      tg.circle(cx, cy, c * (0.24 + 0.03 * t.level)).fill(PALETTE.towerTop);
      const len = c * 0.38;
      tg.moveTo(cx, cy).lineTo(cx + Math.cos(t.aim) * len, cy + Math.sin(t.aim) * len).stroke({ width: c * 0.1, color: PALETTE.towerGun, cap: 'round' });
      for (let i = 0; i <= t.level; i++) tg.circle(t.cx * c + pad + c * 0.1 + i * c * 0.16, t.cy * c + c - pad - c * 0.08, c * 0.05).fill(PALETTE.levelPip);
    }

    // Enemies with health bars.
    const eg = this.enemies;
    eg.clear();
    for (const e of game.enemies) {
      const x = (e.px + (e.x - e.px) * alpha) * c;
      const y = (e.py + (e.y - e.py) * alpha) * c;
      const r = c * 0.22;
      eg.circle(x, y, r).fill(PALETTE.enemy).stroke({ width: 2, color: PALETTE.enemyEdge });
      const bw = c * 0.6;
      const bh = Math.max(3, c * 0.08);
      eg.rect(x - bw / 2, y - r - bh - 3, bw, bh).fill(PALETTE.hpBack);
      eg.rect(x - bw / 2, y - r - bh - 3, bw * (e.hp / e.maxHp), bh).fill(PALETTE.hpFill);
    }

    // Bolts as short streaks along their direction of travel.
    const sg = this.shots;
    sg.clear();
    for (const p of game.projectiles) {
      const x = (p.px + (p.x - p.px) * alpha) * c;
      const y = (p.py + (p.y - p.py) * alpha) * c;
      const dx = p.x - p.px;
      const dy = p.y - p.py;
      const d = Math.hypot(dx, dy) || 1;
      const len = c * 0.25;
      sg.moveTo(x - (dx / d) * len, y - (dy / d) * len).lineTo(x, y).stroke({ width: Math.max(2, c * 0.05), color: PALETTE.bolt, cap: 'round' });
    }

    // Floating texts drift up and fade.
    this.floatTexts = this.floatTexts.filter((f) => {
      f.age += dtSeconds;
      f.node.y -= dtSeconds * c * 0.8;
      f.node.alpha = Math.max(0, 1 - f.age / FLOAT_LIFE);
      if (f.age >= FLOAT_LIFE) {
        f.node.destroy();
        return false;
      }
      return true;
    });
  }
}
