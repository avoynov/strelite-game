import { Assets, Container, Graphics, Sprite, type Spritesheet, type Texture } from 'pixi.js';
import { depth, isoX, isoY, TILE_W } from '../iso';
import { spriteScale, stickyFrameForAim, type TowerArtLevel, type TowerArtManifest } from './towerArt';
import type { TowerView, TowerViewSpec } from './towerView';

export type Density = 1 | 2;

/**
 * The rendered tower atlases. One instance is shared by all tower views.
 *
 * The manifest lists whatever art exists so far (levels arrive one by one), so
 * everything here is driven by it. Sheets load on demand, per tower level and
 * per density: @1x (16 px per metre) for the normal zoomed-out view, @2x when
 * the player zooms in.
 */
export class TowerArt {
  private readonly sheets = new Map<string, Spritesheet>();
  private readonly loading = new Map<string, Promise<void>>();
  private readonly listeners = new Set<() => void>();
  /** Density the board currently wants; views follow it as sheets arrive. */
  density: Density = 1;

  private constructor(
    readonly manifest: TowerArtManifest,
    private readonly baseUrl: string,
  ) {}

  /** @param baseUrl folder that holds towers.json, e.g. `${import.meta.env.BASE_URL}art` */
  static async load(baseUrl: string): Promise<TowerArt | null> {
    try {
      const res = await fetch(`${baseUrl}/towers.json`);
      if (!res.ok) return null;
      return new TowerArt((await res.json()) as TowerArtManifest, baseUrl);
    } catch {
      return null;
    }
  }

  /** Art for a tower level (1-based); falls back to the nearest lower level that exists. */
  level(tower: string, level: number): TowerArtLevel | undefined {
    const levels = this.manifest.towers[tower]?.levels ?? [];
    let best: TowerArtLevel | undefined;
    for (const lv of levels) if (lv.level <= level && (!best || lv.level > best.level)) best = lv;
    return best ?? levels[0];
  }

  /** Called whenever a sheet finishes loading or the wanted density changes. */
  onChange(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  setDensity(density: Density): void {
    if (density === this.density) return;
    this.density = density;
    this.listeners.forEach((fn) => fn());
  }

  /** Start loading a level's sheet at a density; resolves when it can be drawn. */
  request(lv: TowerArtLevel, density: Density = this.density): Promise<void> {
    const key = `${lv.sheet}@${density}x`;
    let p = this.loading.get(key);
    if (!p) {
      // Both densities use the same frame names, so each gets its own cache prefix.
      p = Assets.load<Spritesheet>({ src: `${this.baseUrl}/${key}.json`, data: { cachePrefix: `${key}/` } })
        .then((sheet) => {
          this.sheets.set(key, sheet);
          this.listeners.forEach((fn) => fn());
        })
        .catch((err: unknown) => console.warn(`tower art ${key} failed to load`, err));
      this.loading.set(key, p);
    }
    return p;
  }

  /** Load the first level of every tower, so the first build shows at once. */
  async preload(): Promise<void> {
    await Promise.all(Object.keys(this.manifest.towers).map((id) => {
      const lv = this.level(id, 1);
      return lv ? this.request(lv) : undefined;
    }));
  }

  /**
   * Inline CSS that shows a tower's level-1 picture inside a `box`-pixel square
   * (for HTML menus), or '' while its @1x sheet is not loaded.
   */
  iconCss(tower: string, box: number): string {
    const lv = this.level(tower, 1);
    const sheet = lv && this.sheets.get(`${lv.sheet}@1x`);
    if (!lv || !sheet) return '';
    const data = sheet.data;
    const f = data.frames[`${lv.aim}_00`]?.frame;
    const size = data.meta.size;
    if (!f || !size || !data.meta.image) return '';
    const k = box / Math.max(f.w, f.h);
    const url = `${this.baseUrl}/${lv.sheet.replace(/[^/]+$/, '')}${data.meta.image}`;
    return `width:${f.w}px;height:${f.h}px;background-image:url('${url}');background-position:-${f.x}px -${f.y}px;background-size:${size.w}px ${size.h}px;transform:scale(${k.toFixed(3)}) translate(-50%,-50%)`;
  }

  /** A frame at the wanted density if loaded, else at the other one, else undefined. */
  texture(lv: TowerArtLevel, frame: string): Texture | undefined {
    const other: Density = this.density === 1 ? 2 : 1;
    return this.sheets.get(`${lv.sheet}@${this.density}x`)?.textures[frame] ?? this.sheets.get(`${lv.sheet}@${other}x`)?.textures[frame];
  }
}

const FLASH_LIFE = 0.11;
const RECOIL_LIFE = 0.32;
/** How far the gun jumps back on a shot, in metres. */
const RECOIL_M = 0.22;

/**
 * A tower drawn from the rendered atlases: one static sprite (ground patch,
 * fortifications) and one sprite that swaps between the 32 aim frames. `node`
 * goes into the board's object layer; its origin is the tower's ground point.
 */
export class SpriteTowerView implements TowerView {
  readonly node = new Container();
  private readonly base = new Sprite();
  private readonly gun = new Sprite();
  private readonly flash = new Graphics();
  private lv: TowerArtLevel;
  private level: number;
  private frame = 0;
  private gx = 0;
  private gy = 0;
  private flashAge = Infinity;
  private recoilAge = Infinity;
  private readonly off: () => void;

  constructor(
    private readonly art: TowerArt,
    private readonly spec: TowerViewSpec,
    private readonly metresPerTile: number,
  ) {
    this.base.anchor.set(0.5);
    this.gun.anchor.set(0.5);
    this.flash.visible = false;
    this.node.addChild(this.base, this.gun, this.flash);
    this.node.scale.set(spriteScale(TILE_W, metresPerTile, art.manifest.pxPerMetre['@1x']));
    this.level = spec.level;
    this.lv = art.level(spec.tower, spec.level)!;
    this.off = art.onChange(() => this.refresh());
    this.refresh();
  }

  place(gx: number, gy: number): void {
    this.gx = gx;
    this.gy = gy;
    this.node.position.set(isoX(gx, gy), isoY(gx, gy));
    this.node.zIndex = depth(gx, gy);
  }

  setAim(aim: number): void {
    const frame = stickyFrameForAim(aim, this.art.manifest.directions, this.frame);
    if (frame === this.frame) return;
    this.frame = frame;
    this.refresh();
  }

  setLevel(level: number): void {
    if (level === this.level) return;
    this.level = level;
    this.lv = this.art.level(this.spec.tower, level)!;
    this.refresh();
  }

  fire(): void {
    this.flashAge = 0;
    this.recoilAge = 0;
    const m = this.lv.muzzlePx[this.frame] ?? [0, 0];
    const r = 1.1 * this.art.manifest.pxPerMetre['@1x'] * (this.spec.size / 3);
    this.flash.clear();
    this.flash.circle(0, 0, r).fill({ color: 0xffb347, alpha: 0.55 });
    this.flash.circle(0, 0, r * 0.6).fill({ color: 0xffe7a3, alpha: 0.9 });
    this.flash.circle(0, 0, r * 0.3).fill({ color: 0xffffff });
    this.flash.position.set(m[0], m[1]);
    this.flash.visible = true;
  }

  update(dt: number): void {
    if (this.flashAge < FLASH_LIFE) {
      this.flashAge += dt;
      const k = Math.min(1, this.flashAge / FLASH_LIFE);
      this.flash.alpha = 1 - k;
      this.flash.scale.set(0.7 + 0.8 * k);
      if (k >= 1) this.flash.visible = false;
    }
    if (this.recoilAge < RECOIL_LIFE) {
      this.recoilAge += dt;
      // Kick back fast, settle slowly; along the barrel as it lies on screen.
      const k = Math.min(1, this.recoilAge / RECOIL_LIFE);
      const kick = k < 0.15 ? k / 0.15 : 1 - (k - 0.15) / 0.85;
      const a = (this.frame * 2 * Math.PI) / this.art.manifest.directions;
      const d = (-RECOIL_M * kick * this.art.manifest.pxPerMetre['@1x']) / Math.SQRT2;
      this.gun.position.set((Math.cos(a) - Math.sin(a)) * d, ((Math.cos(a) + Math.sin(a)) * d) / 2);
    }
  }

  muzzle(): { gx: number; gy: number; heightM: number } {
    const m = this.lv.muzzleM[this.frame] ?? [0, 0, 0];
    return { gx: this.gx + m[0] / this.metresPerTile, gy: this.gy + m[1] / this.metresPerTile, heightM: m[2] };
  }

  destroy(): void {
    this.off();
    this.node.destroy({ children: true });
  }

  private refresh(): void {
    void this.art.request(this.lv);
    const n = String(this.frame).padStart(2, '0');
    const base = this.art.texture(this.lv, this.lv.base);
    const gun = this.art.texture(this.lv, `${this.lv.aim}_${n}`);
    if (base) this.base.texture = base;
    if (gun) this.gun.texture = gun;
    this.node.visible = !!(base && gun);
  }
}
