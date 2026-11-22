import { Container, Graphics } from 'pixi.js';
import { depth, isoX, isoY, RISE } from '../iso';
import type { TowerView, TowerViewSpec } from './towerView';

const DIRS = 32;
const OLIVE = 0x5b6b3a;
const OLIVE_DARK = 0x3d4a27;
const STEEL = 0x2b2f2a;
const SOIL = 0x6b5a3e;
/** Stand-in colours per gun, until it has rendered art: wood, bronze, steel. */
const KIT: Record<string, { body: number; dark: number }> = {
  crossbow: { body: 0x8a6a3e, dark: 0x5a4228 },
  scorpion: { body: 0x9a7848, dark: 0x5e4426 },
  greekfire: { body: 0xb07a3a, dark: 0x6b4a22 },
  trebuchet: { body: 0x7d5f38, dark: 0x4e3a22 },
  railgun: { body: 0x6a7c8e, dark: 0x2e3a46 },
  zadnoper: { body: 0x7a5a34, dark: 0x3e2c18 },
  flasher: { body: 0xc9b26a, dark: 0x6e5e2c },
  rockets: { body: 0x8e3b2e, dark: 0x4e1e16 },
  tarkan: { body: 0x4a4f55, dark: 0x24272b },
  ricochet: { body: 0x7e8a6a, dark: 0x3c4430 },
  glass: { body: 0xa8c4d6, dark: 0x4a6478 },
  harpoon: { body: 0xb9b9ae, dark: 0x5c5c54 },
  bees: { body: 0xc8a032, dark: 0x5a4612 },
};

/**
 * Stand-in for a tower that has no rendered art yet: a simple drawn field gun
 * on a patch of soil. Same interface as the sprite view, so the art can arrive
 * later without touching anything else.
 */
export class PlaceholderTowerView implements TowerView {
  readonly node = new Container();
  private readonly g = new Graphics();
  private frame = -1;
  private aim = 0;
  private level: number;
  private gx = 0;
  private gy = 0;
  private flashAge = Infinity;

  constructor(private readonly spec: TowerViewSpec) {
    this.level = spec.level;
    this.node.addChild(this.g);
    this.setAim(0);
  }

  place(gx: number, gy: number): void {
    this.gx = gx;
    this.gy = gy;
    this.node.position.set(isoX(gx, gy), isoY(gx, gy));
    this.node.zIndex = depth(gx, gy);
  }

  setAim(aim: number): void {
    const step = (2 * Math.PI) / DIRS;
    const frame = ((Math.round(aim / step) % DIRS) + DIRS) % DIRS;
    if (frame === this.frame) return;
    this.frame = frame;
    this.aim = frame * step;
    this.draw();
  }

  setLevel(level: number): void {
    if (level === this.level) return;
    this.level = level;
    this.draw();
  }

  fire(): number {
    if (!this.spec.flash) return 0;
    this.flashAge = 0;
    this.draw();
    return 0;
  }

  setFiring(): void {}

  update(dt: number): void {
    if (this.flashAge === Infinity) return;
    this.flashAge += dt;
    if (this.flashAge > 0.1) {
      this.flashAge = Infinity;
      this.draw();
    }
  }

  muzzle(): { gx: number; gy: number; heightM: number } {
    const len = this.barrel();
    return { gx: this.gx + Math.cos(this.aim) * len, gy: this.gy + Math.sin(this.aim) * len, heightM: 1.2 };
  }

  destroy(): void {
    this.node.destroy({ children: true });
  }

  /** Barrel length in tiles. */
  private barrel(): number {
    return this.spec.size * 0.42;
  }

  private draw(): void {
    const g = this.g;
    const s = this.spec.size;
    const c = Math.cos(this.aim);
    const sn = Math.sin(this.aim);
    // Local point: `f` tiles forward along the aim, `r` tiles to its right, `h` tiles up.
    const pt = (f: number, r: number, h = 0): [number, number] => [isoX(c * f - sn * r, sn * f + c * r), isoY(c * f - sn * r, sn * f + c * r) - h * RISE];
    const line = (a: [number, number], b: [number, number], width: number, color: number) =>
      g.moveTo(a[0], a[1]).lineTo(b[0], b[1]).stroke({ width, color, cap: 'round' });

    const kit = KIT[this.spec.tower] ?? { body: OLIVE, dark: OLIVE_DARK };
    g.clear();
    g.ellipse(0, 0, isoX(s * 0.36, -s * 0.36), isoX(s * 0.36, -s * 0.36) / 2).fill({ color: SOIL, alpha: 0.85 });
    // Sandbag ring grows with the level.
    for (let i = 0; i < this.level - 1; i++) {
      const r = isoX(s * (0.4 + 0.05 * i), -s * (0.4 + 0.05 * i));
      g.ellipse(0, 0, r, r / 2).stroke({ width: 4, color: 0xa39a7a, alpha: 0.9 });
    }
    const len = this.barrel();
    // Trails, wheels, shield, barrel: back to front is close enough for a stand-in.
    line(pt(-0.05 * s, 0, 0.12), pt(-len * 0.9, s * 0.16), 3, kit.dark);
    line(pt(-0.05 * s, 0, 0.12), pt(-len * 0.9, -s * 0.16), 3, kit.dark);
    for (const side of [-1, 1]) {
      const [x, y] = pt(0, side * s * 0.14, 0.1);
      g.circle(x, y, 2 + s * 1.5).fill(STEEL);
    }
    line(pt(0.03 * s, -s * 0.13, 0.22), pt(0.03 * s, s * 0.13, 0.22), 7, kit.body);
    line(pt(0, 0, 0.2), pt(len, 0, 0.3), 4.5, kit.dark);
    if (this.flashAge !== Infinity) {
      const [x, y] = pt(len, 0, 0.3);
      g.circle(x, y, 7).fill({ color: 0xffe7a3, alpha: 0.9 });
    }
  }
}
