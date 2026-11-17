import { Container, Graphics, Sprite } from 'pixi.js';
import type { TowerArt } from './towers/spriteTowerView';
import { frameForAim, frameName, type EnemyArtDef } from './towers/towerArt';
import { depth, isoX, isoY, RISE } from './iso';

/**
 * How the game shows one enemy, independent of how it is drawn. Like
 * TowerView: grid cells and radians in, so rendered sprites (or 3D) can
 * replace the stand-in drawing below without touching the board.
 */
export interface EnemyView {
  place(gx: number, gy: number): void;
  /** Direction of travel: atan2(dy, dx) in grid cells. */
  setHeading(heading: number): void;
  /** Health as a fraction 0..1. */
  setHealth(frac: number): void;
  destroy(): void;
}

const DIRS = 16;
const KIT = {
  infantry: { body: 0x6a6f4c, dark: 0x3c402b },
  truck: { body: 0x4d5a3a, dark: 0x2c3422 },
  tank: { body: 0x55603d, dark: 0x2e3523 },
} as const;

/** Stand-in enemies until style В sprites exist: a squad, a truck, a tank, drawn flat. */
export class PlaceholderEnemyView implements EnemyView {
  readonly node = new Container();
  private readonly body = new Graphics();
  private readonly bar = new Graphics();
  private frame = -1;
  private health = -1;

  constructor(
    private readonly kind: string,
    /** Visual radius in tiles. */
    private readonly radius: number,
  ) {
    this.node.addChild(this.body, this.bar);
    this.setHeading(0);
    this.setHealth(1);
  }

  place(gx: number, gy: number): void {
    this.node.position.set(isoX(gx, gy), isoY(gx, gy));
    this.node.zIndex = depth(gx, gy);
  }

  setHeading(heading: number): void {
    const step = (2 * Math.PI) / DIRS;
    const frame = ((Math.round(heading / step) % DIRS) + DIRS) % DIRS;
    if (frame === this.frame) return;
    this.frame = frame;
    this.draw(frame * step);
  }

  setHealth(frac: number): void {
    const f = Math.max(0, Math.min(1, frac));
    if (Math.abs(f - this.health) < 0.01) return;
    this.health = f;
    const w = Math.max(20, isoX(this.radius * 0.8, -this.radius * 0.8));
    const y = -RISE * (this.kind === 'infantry' ? 0.55 : 0.75) - 6;
    this.bar.clear();
    this.bar.visible = f < 1;
    this.bar.rect(-w / 2 - 1, y - 1, w + 2, 6).fill({ color: 0x000000, alpha: 0.6 });
    this.bar.rect(-w / 2, y, w * f, 4).fill(f > 0.5 ? 0x7bd36a : f > 0.25 ? 0xe6c14a : 0xe0624f);
  }

  destroy(): void {
    this.node.destroy({ children: true });
  }

  private draw(a: number): void {
    const g = this.body;
    const r = this.radius;
    const c = Math.cos(a);
    const s = Math.sin(a);
    const pt = (f: number, side: number, h = 0): [number, number] => [isoX(c * f - s * side, s * f + c * side), isoY(c * f - s * side, s * f + c * side) - h * RISE];
    const quad = (f0: number, f1: number, half: number, h: number, color: number) =>
      g.poly([...pt(f0, -half, h), ...pt(f1, -half, h), ...pt(f1, half, h), ...pt(f0, half, h)]).fill(color);
    const kit = KIT[this.kind as keyof typeof KIT] ?? KIT.infantry;

    g.clear();
    if (this.kind === 'infantry') {
      // A small squad: five soldiers in a loose wedge.
      for (const [f, side] of [[0.9, 0], [0.1, -0.7], [0.1, 0.7], [-0.8, -0.35], [-0.8, 0.35]] as const) {
        const [x, y] = pt(f * r, side * r);
        g.ellipse(x + 3, y - 1.5, 5, 2.2).fill({ color: 0x000000, alpha: 0.3 });
        g.roundRect(x - 2.5, y - 13, 5, 13, 2.5).fill(kit.body);
        g.circle(x, y - 14.5, 2.8).fill(kit.dark);
      }
      return;
    }
    // Vehicles: shadow, hull, then cab or turret; the sun is at the lower left.
    const half = r * 0.45;
    g.poly([...pt(-r, -half), ...pt(r, -half), ...pt(r, half), ...pt(-r, half)].map((v, i) => v + (i % 2 ? -3 : 5))).fill({ color: 0x000000, alpha: 0.28 });
    quad(-r, r, half, 0.12, kit.dark);
    quad(-r, r, half * 0.9, 0.3, kit.body);
    if (this.kind === 'tank') {
      const [tx, ty] = pt(-r * 0.1, 0, 0.42);
      g.ellipse(tx, ty, isoX(r * 0.26, -r * 0.26), isoX(r * 0.26, -r * 0.26) / 2).fill(kit.dark);
      const [bx, by] = pt(r * 1.25, 0, 0.42);
      g.moveTo(tx, ty).lineTo(bx, by).stroke({ width: 4, color: kit.dark, cap: 'round' });
    } else {
      quad(r * 0.35, r * 0.95, half * 0.85, 0.5, kit.dark);
      quad(-r * 0.95, r * 0.25, half * 0.85, 0.42, 0x7a7355);
    }
  }
}

/** Height of the health bar above the ground, in metres, per enemy kind. */
const BAR_HEIGHT_M: Record<string, number> = { infantry: 2.2, truck: 3.4, tank: 3.2 };

/**
 * An enemy drawn from its rendered atlas: one sprite that swaps between the
 * headings the art was rendered in (16), plus a health bar. The art is real
 * size at the manifest's pixels per metre, so `scale` is the same one towers use.
 */
export class SpriteEnemyView implements EnemyView {
  readonly node = new Container();
  private readonly sprite = new Sprite();
  private readonly bar = new Graphics();
  private frame = -1;
  private health = -1;
  private readonly off: () => void;

  constructor(
    private readonly art: TowerArt,
    private readonly def: EnemyArtDef,
    readonly kind: string,
    scale: number,
    metresPerTile: number,
  ) {
    this.sprite.anchor.set(0.5);
    this.sprite.scale.set(scale);
    this.node.addChild(this.sprite, this.bar);
    this.bar.position.y = -((BAR_HEIGHT_M[kind] ?? 3) / metresPerTile) * RISE;
    this.off = art.onChange(() => this.refresh());
    this.setHeading(0);
    this.setHealth(1);
  }

  place(gx: number, gy: number): void {
    this.node.position.set(isoX(gx, gy), isoY(gx, gy));
    this.node.zIndex = depth(gx, gy);
  }

  setHeading(heading: number): void {
    const frame = frameForAim(heading, this.def.directions);
    if (frame === this.frame) return;
    this.frame = frame;
    this.refresh();
  }

  setHealth(frac: number): void {
    const f = Math.max(0, Math.min(1, frac));
    if (Math.abs(f - this.health) < 0.01) return;
    this.health = f;
    const w = this.kind === 'infantry' ? 18 : 28;
    this.bar.clear();
    this.bar.visible = f < 1;
    this.bar.rect(-w / 2 - 1, -1, w + 2, 5).fill({ color: 0x000000, alpha: 0.6 });
    this.bar.rect(-w / 2, 0, w * f, 3).fill(f > 0.5 ? 0x7bd36a : f > 0.25 ? 0xe6c14a : 0xe0624f);
  }

  destroy(): void {
    this.off();
    this.node.destroy({ children: true });
  }

  private refresh(): void {
    const tex = this.art.sheetTexture(this.def.sheet, frameName(this.def.frames, this.frame));
    if (tex) this.sprite.texture = tex;
    this.sprite.visible = !!tex;
  }
}
