import { Assets, Container, Graphics, Sprite, type Spritesheet, type Texture } from 'pixi.js';
import { depth, isoX, isoY, TILE_W } from '../iso';
import { spriteScale, stickyFrameForAim, type TowerArtLevel, type TowerArtManifest } from './towerArt';
import type { TowerView, TowerViewSpec } from './towerView';

export type Density = 1 | 2;

/** One gun frame located on its sheet; pixels of that sheet. */
export interface GunPortrait {
  url: string;
  sheetSize: [number, number];
  /** x, y, w, h of the frame on the sheet. */
  frame: [number, number, number, number];
  /** Top-left of the frame relative to the ground point. */
  offset: [number, number];
  /** Radius around the ground point that every heading of this gun fits in. */
  reach: number;
}

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
  private readonly reach = new WeakMap<Spritesheet, number>();
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
    return this.requestSheet(lv.sheet, density);
  }

  /** Start loading any sheet (towers, enemies, effects) at a density. */
  requestSheet(sheet: string, density: Density = this.density): Promise<void> {
    const key = `${sheet}@${density}x`;
    let p = this.loading.get(key);
    if (!p) {
      // Both densities use the same frame names, so each gets its own cache prefix.
      p = Assets.load<Spritesheet>({ src: `${this.baseUrl}/${key}.json`, data: { cachePrefix: `${key}/` } })
        .then((sheet) => {
          this.sheets.set(key, sheet);
          this.listeners.forEach((fn) => fn());
        })
        .catch((err: unknown) => console.warn(`art ${key} failed to load`, err));
      this.loading.set(key, p);
    }
    return p;
  }

  /** Load the first level of every tower, the enemies and the effects, so they show at once. */
  async preload(): Promise<void> {
    const sheets = [
      ...Object.keys(this.manifest.towers).map((id) => this.level(id, 1)?.sheet),
      ...Object.values(this.manifest.enemies ?? {}).map((e) => e.sheet),
      ...Object.values(this.manifest.effects ?? {}).map((e) => e.sheet),
    ];
    await Promise.all(sheets.map((s) => (s ? this.requestSheet(s) : undefined)));
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

  /**
   * A large still of a tower level's gun for HTML screens: one aim frame placed
   * inside its untrimmed square, so every frame shares the same ground point and
   * scale and the gun can turn in place. Uses @2x when loaded (and starts
   * loading it), else @1x; undefined while neither is ready.
   */
  portrait(tower: string, level: number, frame: number): GunPortrait | undefined {
    const lv = this.level(tower, level);
    if (!lv) return undefined;
    if (!this.sheets.has(`${lv.sheet}@2x`)) void this.requestSheet(lv.sheet, 2);
    if (!this.sheets.has(`${lv.sheet}@1x`)) void this.requestSheet(lv.sheet, 1);
    const sheet = this.sheets.get(`${lv.sheet}@2x`) ?? this.sheets.get(`${lv.sheet}@1x`);
    if (!sheet) return undefined;
    const data = sheet.data;
    const name = `${lv.aim}_${String(frame % this.manifest.directions).padStart(2, '0')}`;
    const f = data.frames[name];
    if (!f || !data.meta.image || !data.meta.size || !f.sourceSize) return undefined;
    // Radius around the ground point that holds the gun in every heading.
    let reach = this.reach.get(sheet);
    if (reach === undefined) {
      reach = 1;
      for (const [key, fr] of Object.entries(data.frames)) {
        if (!key.startsWith(lv.aim) || !fr.sourceSize) continue;
        const o = fr.spriteSourceSize ?? { x: 0, y: 0, w: fr.frame.w, h: fr.frame.h };
        const cx = fr.sourceSize.w / 2, cy = fr.sourceSize.h / 2;
        reach = Math.max(reach, cx - o.x, o.x + (o.w ?? fr.frame.w) - cx, cy - o.y, o.y + (o.h ?? fr.frame.h) - cy);
      }
      this.reach.set(sheet, reach);
    }
    const src = f.spriteSourceSize ?? { x: 0, y: 0 };
    return {
      url: `${this.baseUrl}/${lv.sheet.replace(/[^/]+$/, '')}${data.meta.image}`,
      sheetSize: [data.meta.size.w, data.meta.size.h],
      frame: [f.frame.x, f.frame.y, f.frame.w, f.frame.h],
      offset: [src.x - f.sourceSize.w / 2, src.y - f.sourceSize.h / 2],
      reach,
    };
  }

  /** A frame at the wanted density if loaded, else at the other one, else undefined. */
  texture(lv: TowerArtLevel, frame: string): Texture | undefined {
    return this.sheetTexture(lv.sheet, frame);
  }

  /** Like texture(), for any sheet; also starts loading the wanted density. */
  sheetTexture(sheet: string, frame: string): Texture | undefined {
    const other: Density = this.density === 1 ? 2 : 1;
    const want = this.sheets.get(`${sheet}@${this.density}x`);
    if (!want) void this.requestSheet(sheet);
    return want?.textures[frame] ?? this.sheets.get(`${sheet}@${other}x`)?.textures[frame];
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
    this.recoilAge = 0;
    // The board plays the rendered flash and smoke when the art has them.
    if (this.art.manifest.effects?.muzzle_flash) return;
    this.flashAge = 0;
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

  /** Barrel direction of the current aim frame, in radians (same convention as setAim). */
  aimAngle(): number {
    return (this.frame * 2 * Math.PI) / this.art.manifest.directions;
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
