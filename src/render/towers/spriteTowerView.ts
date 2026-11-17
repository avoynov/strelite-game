import { Assets, Container, Sprite, type Spritesheet, type Texture } from 'pixi.js';
import { aimFrameName, frameForAim, spriteScale, type TowerArtLevel, type TowerArtManifest } from './towerArt';
import type { TowerView } from './towerView';

/** The loaded tower atlases. Load once, share between all tower views. */
export class TowerArt {
  private readonly sheets = new Map<string, Spritesheet>();

  private constructor(
    readonly manifest: TowerArtManifest,
    private readonly baseUrl: string,
    /** 1 = small atlases (16 px per metre), 2 = sharp ones (32 px per metre, four times the memory). */
    readonly density: 1 | 2,
  ) {}

  /**
   * @param baseUrl folder that holds towers.json, e.g. `${import.meta.env.BASE_URL}art`
   * @param towers  ids to load; all towers in the manifest when omitted
   */
  static async load(baseUrl: string, density: 1 | 2 = 2, towers?: string[]): Promise<TowerArt> {
    const manifest = (await (await fetch(`${baseUrl}/towers.json`)).json()) as TowerArtManifest;
    const art = new TowerArt(manifest, baseUrl, density);
    const ids = towers ?? Object.keys(manifest.towers);
    await Promise.all(ids.flatMap((id) => (manifest.towers[id]?.levels ?? []).map((lv) => art.loadSheet(lv))));
    return art;
  }

  private async loadSheet(lv: TowerArtLevel): Promise<void> {
    const sheet = await Assets.load<Spritesheet>(`${this.baseUrl}/${lv.sheet}@${this.density}x.json`);
    this.sheets.set(lv.sheet, sheet);
  }

  level(tower: string, level: number): TowerArtLevel {
    const lv = this.manifest.towers[tower]?.levels.find((l) => l.level === level);
    if (!lv) throw new Error(`no art for tower "${tower}" level ${level}`);
    return lv;
  }

  texture(lv: TowerArtLevel, frame: string): Texture {
    const tex = this.sheets.get(lv.sheet)?.textures[frame];
    if (!tex) throw new Error(`frame "${frame}" is not loaded (sheet ${lv.sheet})`);
    return tex;
  }
}

/**
 * A tower drawn from the rendered atlases: one static sprite (ground patch,
 * fortifications) and one sprite that swaps between the 32 aim frames.
 * Add `node` to the board's object layer and sort it by depth like any other
 * object (its origin is the tower's ground point).
 */
export class SpriteTowerView implements TowerView {
  readonly node = new Container();
  private readonly base = new Sprite();
  private readonly gun = new Sprite();
  private lv: TowerArtLevel;
  private frame = 0;
  private gx = 0;
  private gy = 0;

  /**
   * @param project grid cells -> position in the parent of `node`
   * @param cellPx  width of one tile's diamond in that same space
   */
  constructor(
    private readonly art: TowerArt,
    private readonly tower: string,
    level: number,
    private readonly project: (gx: number, gy: number) => { x: number; y: number },
    cellPx: number,
    private readonly metresPerTile = art.manifest.suggestedMetresPerTile,
  ) {
    this.base.anchor.set(0.5);
    this.gun.anchor.set(0.5);
    this.node.addChild(this.base, this.gun);
    this.lv = art.level(tower, level);
    this.setCellSize(cellPx);
    this.refresh();
  }

  /** Call when the board is laid out again and the tile size changes. */
  setCellSize(cellPx: number): void {
    this.node.scale.set(spriteScale(cellPx, this.metresPerTile, this.art.manifest.pxPerMetre['@1x']));
    this.place(this.gx, this.gy);
  }

  place(gx: number, gy: number): void {
    this.gx = gx;
    this.gy = gy;
    const p = this.project(gx, gy);
    this.node.position.set(p.x, p.y);
  }

  setAim(aim: number): void {
    const frame = frameForAim(aim, this.art.manifest.directions);
    if (frame === this.frame) return;
    this.frame = frame;
    this.gun.texture = this.art.texture(this.lv, aimFrameName(this.lv, aim, this.art.manifest.directions));
  }

  setLevel(level: number): void {
    this.lv = this.art.level(this.tower, level);
    this.refresh();
  }

  muzzle(): { gx: number; gy: number; heightM: number } {
    const m = this.lv.muzzleM[this.frame] ?? [0, 0, 0];
    return { gx: this.gx + m[0] / this.metresPerTile, gy: this.gy + m[1] / this.metresPerTile, heightM: m[2] };
  }

  destroy(): void {
    this.node.destroy({ children: true });
  }

  private refresh(): void {
    const n = String(this.frame).padStart(2, '0');
    this.base.texture = this.art.texture(this.lv, this.lv.base);
    this.gun.texture = this.art.texture(this.lv, `${this.lv.aim}_${n}`);
  }
}
