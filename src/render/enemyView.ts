import { Container, Graphics, Sprite } from 'pixi.js';
import type { TowerArt } from './towers/spriteTowerView';
import { frameForAim, frameName, moveFrameName, type EnemyArtDef } from './towers/towerArt';
import { depth, isoX, isoY, RISE, TILE_W } from './iso';

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
  moto: { body: 0x5c5a48, dark: 0x2a2a24 },
  drone: { body: 0x8a8f94, dark: 0x3a3f44 },
  truck: { body: 0x4d5a3a, dark: 0x2c3422 },
  apc: { body: 0x5a6346, dark: 0x30372a },
  tank: { body: 0x55603d, dark: 0x2e3523 },
  fortress: { body: 0x4a4f3c, dark: 0x262a1f },
} as const;
/** Height a flyer is drawn above its ground point, in tiles (stand-in; the airship art says its own). */
export const FLY_HEIGHT = 1.2;
/** A unit counts as standing once it has not moved for this long. */
const STAND_AFTER_MS = 250;
/** Added to a flyer's depth so it draws over everything on the ground. */
export const FLYER_Z = 10_000;

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
    const y = -RISE * (this.kind === 'infantry' || this.kind === 'moto' ? 0.55 : this.kind === 'drone' ? FLY_HEIGHT + 0.4 : this.kind === 'fortress' ? 1 : 0.75) - 6;
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
    if (this.kind === 'moto') {
      // Three riders in a staggered line.
      for (const [f, side] of [[0.8, -0.4], [0, 0.45], [-0.8, -0.2]] as const) {
        const [x0, y0] = pt(f * r - 0.12, side * r);
        const [x1, y1] = pt(f * r + 0.12, side * r);
        g.ellipse((x0 + x1) / 2 + 3, (y0 + y1) / 2 - 1, 6, 2.4).fill({ color: 0x000000, alpha: 0.3 });
        g.moveTo(x0, y0 - 3).lineTo(x1, y1 - 3).stroke({ width: 3.5, color: kit.dark, cap: 'round' });
        g.roundRect((x0 + x1) / 2 - 2, (y0 + y1) / 2 - 12, 4, 9, 2).fill(kit.body);
        g.circle((x0 + x1) / 2, (y0 + y1) / 2 - 13.5, 2.5).fill(kit.dark);
      }
      return;
    }
    if (this.kind === 'drone') {
      // Shadow on the ground, the craft high above it: four rotors on a cross.
      g.ellipse(4, -1, 9, 4).fill({ color: 0x000000, alpha: 0.22 });
      const h = FLY_HEIGHT;
      for (const [f, side] of [[0.9, 0.9], [0.9, -0.9], [-0.9, 0.9], [-0.9, -0.9]] as const) {
        const [x, y] = pt(f * r, side * r, h);
        const [cx, cy] = pt(0, 0, h);
        g.moveTo(cx, cy).lineTo(x, y).stroke({ width: 2, color: kit.dark });
        g.ellipse(x, y, 5, 2.5).fill({ color: kit.body, alpha: 0.7 });
      }
      const [cx, cy] = pt(0, 0, h);
      g.ellipse(cx, cy, 5, 3.5).fill(kit.dark);
      return;
    }
    // Vehicles: shadow, hull, then cab or turret; the sun is at the lower left.
    const half = r * 0.45;
    g.poly([...pt(-r, -half), ...pt(r, -half), ...pt(r, half), ...pt(-r, half)].map((v, i) => v + (i % 2 ? -3 : 5))).fill({ color: 0x000000, alpha: 0.28 });
    quad(-r, r, half, 0.12, kit.dark);
    quad(-r, r, half * 0.9, 0.3, kit.body);
    if (this.kind === 'tank' || this.kind === 'fortress') {
      // The fortress carries two turrets.
      const turrets = this.kind === 'fortress' ? [r * 0.35, -r * 0.45] : [-r * 0.1];
      for (const f of turrets) {
        const [tx, ty] = pt(f, 0, 0.42);
        g.ellipse(tx, ty, isoX(r * 0.26, -r * 0.26), isoX(r * 0.26, -r * 0.26) / 2).fill(kit.dark);
        const [bx, by] = pt(f + r * 1.1, 0, 0.42);
        g.moveTo(tx, ty).lineTo(bx, by).stroke({ width: this.kind === 'fortress' ? 6 : 4, color: kit.dark, cap: 'round' });
      }
    } else if (this.kind === 'apc') {
      // Eight wheels and a small roof gun.
      for (const f of [-0.75, -0.25, 0.25, 0.75]) {
        for (const side of [-1, 1]) {
          const [x, y] = pt(f * r, side * half, 0.08);
          g.circle(x, y, 3).fill(0x1e211b);
        }
      }
      const [tx, ty] = pt(r * 0.15, 0, 0.42);
      g.circle(tx, ty, 4).fill(kit.dark);
      const [bx, by] = pt(r * 0.8, 0, 0.42);
      g.moveTo(tx, ty).lineTo(bx, by).stroke({ width: 2, color: kit.dark, cap: 'round' });
    } else {
      quad(r * 0.35, r * 0.95, half * 0.85, 0.5, kit.dark);
      quad(-r * 0.95, r * 0.25, half * 0.85, 0.42, 0x7a7355);
    }
  }
}

/** Height of the health bar above the ground, in metres, per enemy kind. */
/** Over the craft's own centre for flyers. */
const BAR_HEIGHT_M: Record<string, number> = { infantry: 2.2, moto: 2.2, drone: 3, truck: 3.4, apc: 3.2, tank: 3.2, fortress: 4.5 };

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
  private readonly flying: boolean;
  /** Movement loop state: metres travelled, where it was last placed, when it last moved. */
  private distanceM = 0;
  private lastX = NaN;
  private lastY = NaN;
  private movedAt = -Infinity;
  private readonly phase = Math.random();

  constructor(
    private readonly art: TowerArt,
    private readonly def: EnemyArtDef,
    readonly kind: string,
    scale: number,
    private readonly metresPerTile: number,
  ) {
    this.sprite.anchor.set(0.5);
    this.sprite.scale.set(scale);
    this.flying = !!def.flying;
    const lift = def.flying ? ((def.flightHeightM ?? 0) / metresPerTile) * RISE : 0;
    if (def.flying) {
      // The craft hangs high over its ground point; its shadow lies on the ground below.
      const rx = (def.lengthM / metresPerTile) * TILE_W * 0.26;
      const shadow = new Graphics().ellipse(0, 0, rx, rx / 2).fill({ color: 0x000000, alpha: 0.2 });
      this.node.addChild(shadow);
      this.sprite.position.y = -lift;
    }
    this.node.addChild(this.sprite, this.bar);
    this.bar.position.y = -lift - ((BAR_HEIGHT_M[kind] ?? 3) / metresPerTile) * RISE;
    this.off = art.onChange(() => this.refresh());
    this.setHeading(0);
    this.setHealth(1);
  }

  place(gx: number, gy: number): void {
    this.node.position.set(isoX(gx, gy), isoY(gx, gy));
    // Flyers pass over everything on the ground.
    this.node.zIndex = depth(gx, gy) + (this.flying ? FLYER_Z : 0);
    const d = Math.hypot(gx - this.lastX, gy - this.lastY);
    if (d > 1e-4) {
      this.distanceM += d * this.metresPerTile;
      this.movedAt = performance.now();
    }
    this.lastX = gx;
    this.lastY = gy;
    if (this.def.move) this.refresh();
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
    const move = this.def.move;
    const now = performance.now();
    // A unit that has not moved for a moment (firing at a wall, say) stands still; propellers always turn.
    const moving = move && (move.fps || now - this.movedAt < STAND_AFTER_MS);
    const name = moving ? moveFrameName(move, this.frame, this.distanceM, now / 1000, this.phase) : frameName(this.def.frames, this.frame);
    const tex = this.art.sheetTexture(this.def.sheet, name) ?? this.art.sheetTexture(this.def.sheet, frameName(this.def.frames, this.frame));
    if (tex && tex !== this.sprite.texture) this.sprite.texture = tex;
    this.sprite.visible = !!tex;
  }
}
