import { Assets, Container, Graphics, Matrix, Text, TilingSprite, type Texture } from 'pixi.js';
import { ENEMIES, METRES_PER_TILE, TOWERS, type TowerId } from '../sim/content';
import type { Building, Fence, Game, Tower } from '../sim/game';
import { BUILDING_SIZE, gunJobSeconds, HQ_LEVELS, HQ_SPOT } from '../sim/base';
import { BuildingView } from './buildingView';
import { Camera, type Rect } from './camera';
import { Effects } from './effects';
import { FENCE_HEIGHT, FenceView, NX, NY, PX, PY } from './fenceView';
import { FLY_HEIGHT, PlaceholderEnemyView, SpriteEnemyView, type EnemyView } from './enemyView';
import { depth, diamond, isoX, isoY, project, RISE, TILE_W, unproject } from './iso';
import { PALETTE } from './palette';
import { roadCentreLines, stripOutline } from './road';
import { PlaceholderTowerView } from './towers/placeholderTowerView';
import { SpriteTowerView, type Density, type TowerArt } from './towers/spriteTowerView';
import { shotEffects, spriteScale } from './towers/towerArt';
import type { TowerView } from './towers/towerView';

/** What the build menu has picked: a gun, or (siege mode) fences. */
export type Armed = TowerId | 'fence';

export type Selection =
  /** An existing gun, by id. */
  | { kind: 'tower'; id: number }
  /** Siege mode: an existing fence, by id. */
  | { kind: 'fence'; id: number }
  /** Base mode: the headquarters or the laboratory. */
  | { kind: 'building'; what: 'hq' | 'lab' }
  /** A gun about to be built, footprint's top-left cell at (cx, cy). */
  | { kind: 'place'; def: TowerId; cx: number; cy: number };

type PixiTowerView = TowerView & { node: Container };
type PixiEnemyView = EnemyView & { node: Container };

interface FloatText {
  node: Text;
  age: number;
  /** Ground position in grid cells and height above it, in tiles. */
  gx: number;
  gy: number;
  h: number;
}

interface Burst {
  gx: number;
  gy: number;
  radius: number;
  age: number;
}

/** Where a projectile visibly starts, relative to the point the simulation fired it from. */
interface ShotOrigin {
  dx: number;
  dy: number;
  /** Muzzle height in tiles. */
  h: number;
}

const FLOAT_LIFE = 0.9;
const STRIKE_LIFE = 0.18;

const RAIL_LIFE = 0.35;

/** Screen rotation of a direction on the ground (`a` = atan2(dy, dx) in grid cells). */
function screenAngle(a: number): number {
  return Math.atan2((Math.cos(a) + Math.sin(a)) / 2, Math.cos(a) - Math.sin(a));
}

/** World pixels on screen that `tiles` of ground span in direction `a`. */
function groundLengthPx(tiles: number, a: number): number {
  return Math.hypot(isoX(Math.cos(a), Math.sin(a)), isoY(Math.cos(a), Math.sin(a))) * tiles;
}
/** Size of the burst a destroyed vehicle goes up in; units not listed just fall. */
const VEHICLE_BURST: Record<string, number> = { truck: 0.65, apc: 0.75, tank: 0.85, fortress: 1.4 };
const BURST_LIFE = 0.45;
/** Seconds before a railgun shot that its charge glow starts building. */
const RAIL_CHARGE = 0.9;
/** Height in tiles at which rounds arrive (roughly the middle of a vehicle). */
const HIT_HEIGHT = 0.2;
/** Closest zoom: one tile this many CSS pixels wide. */
const MAX_TILE_PX = 150;
/** Room above the top tile for tall objects, in tiles of width. */
const HEADROOM = 0.8;

/**
 * Draws the board: ground, road, guns, enemies, shots. The simulation does not
 * know how it is drawn. Guns and enemies are separate view objects behind small
 * interfaces (TowerView, EnemyView): rendered sprites today, replaceable later.
 */
export class BoardRenderer {
  /** Screen-space root: add this to the stage. */
  readonly root = new Container();
  readonly camera = new Camera();
  private readonly world = new Container();
  private readonly groundLayer = new Container();
  private readonly map = new Graphics();
  private readonly overlay = new Graphics();
  private readonly objects = new Container();
  private readonly shots = new Graphics();
  private readonly floats = new Container();
  private floatTexts: FloatText[] = [];
  private bursts: Burst[] = [];
  /** Railgun traces fading out: ends in grid cells. */
  private rails: { x1: number; y1: number; x2: number; y2: number; age: number }[] = [];
  /** Siege mode: enemy shots at guns and fences, fading out. */
  private strikes: { x1: number; y1: number; x2: number; y2: number; age: number }[] = [];
  private readonly fenceViews = new Map<number, FenceView>();
  private readonly buildingViews = new Map<'hq' | 'lab', BuildingView>();
  private readonly towerViews = new Map<number, { view: PixiTowerView; level: number }>();
  private readonly enemyViews = new Map<number, { view: PixiEnemyView; kind: string; gx: number; gy: number }>();
  /** Rendered one-shot animations, when the art has them. */
  private readonly effects: Effects | null;
  private readonly shotOrigins = new Map<number, ShotOrigin>();
  private readonly shotFxCache = new Map<string, string[]>();
  private overlayKey = '';
  private groundSprite: TilingSprite | null = null;
  private groundDensity: Density = 1;
  private roadTexture: Texture | null = null;
  private readonly bounds: Rect;
  private screenW = 0;
  private screenH = 0;
  private resolution = 1;
  private readonly offArt: (() => void) | undefined;

  constructor(
    private readonly game: Game,
    /** Rendered tower art, or null to draw stand-ins. */
    private readonly art: TowerArt | null,
    private readonly artUrl: string,
  ) {
    this.objects.sortableChildren = true;
    this.world.addChild(this.groundLayer, this.map, this.overlay, this.objects, this.shots);
    this.root.addChild(this.world, this.floats);
    this.bounds = this.mapBounds();
    this.offArt = art?.onChange(() => void this.loadGround());
    this.effects = art ? new Effects(art, this.objects, this.artScale()) : null;
  }

  /** Sprite scale that puts @1x art at real size on the board. */
  private artScale(): number {
    return this.art ? spriteScale(TILE_W, METRES_PER_TILE, this.art.manifest.pxPerMetre['@1x']) : 1;
  }

  destroy(): void {
    this.offArt?.();
    this.effects?.destroy();
    this.root.destroy({ children: true });
  }

  // ---- layout and camera ---------------------------------------------------

  /** Extent of the playable cells in world pixels. */
  private mapBounds(): Rect {
    const { grid } = this.game.map;
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    for (let y = 0; y < grid.rows; y++) {
      for (let x = 0; x < grid.cols; x++) {
        if (grid.get(x, y) === 'blocked') continue;
        minX = Math.min(minX, isoX(x, y + 1));
        maxX = Math.max(maxX, isoX(x + 1, y));
        minY = Math.min(minY, isoY(x, y));
        maxY = Math.max(maxY, isoY(x + 1, y + 1));
      }
    }
    minY -= HEADROOM * TILE_W;
    return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
  }

  /**
   * Fit the map into the free screen rectangle (between the HUD bars); the
   * ground fills the whole screen.
   */
  layout(view: Rect, screenW: number, screenH: number, resolution: number): void {
    this.screenW = screenW;
    this.screenH = screenH;
    this.resolution = resolution;
    this.camera.configure(this.bounds, view, MAX_TILE_PX / TILE_W);
    this.drawGround();
    this.drawMap();
    this.applyCamera();
  }

  private applyCamera(): void {
    this.world.scale.set(this.camera.scale);
    this.world.position.set(Math.round(this.camera.x), Math.round(this.camera.y));
    // Sharper atlases once a metre covers clearly more device pixels than @1x holds.
    if (this.art) {
      const pxPerMetre = this.art.manifest.pxPerMetre['@1x'];
      const need = spriteScale(TILE_W, METRES_PER_TILE, pxPerMetre) * this.camera.scale * this.resolution;
      if (this.art.density === 1 && need > 1.3) this.art.setDensity(2);
      else if (this.art.density === 2 && need < 1.05) this.art.setDensity(1);
    }
  }

  /** Screen point to (fractional) grid coordinates on the ground. */
  gridAt(sx: number, sy: number): { x: number; y: number } {
    const w = this.camera.toWorld(sx, sy);
    return unproject(w.x, w.y);
  }

  /** Screen point to grid cell, or null when outside the map. */
  cellAt(sx: number, sy: number): { x: number; y: number } | null {
    const g = this.gridAt(sx, sy);
    const x = Math.floor(g.x);
    const y = Math.floor(g.y);
    const { grid } = this.game.map;
    return grid.inBounds(x, y) && grid.get(x, y) !== 'blocked' ? { x, y } : null;
  }

  /** Screen point of a ground position given in grid cells. */
  gridToScreen(gx: number, gy: number, h = 0): { x: number; y: number } {
    const p = project(gx, gy, h);
    return this.camera.toScreen(p.x, p.y);
  }

  // ---- static layers -------------------------------------------------------

  /** World rectangle the camera can ever show: the map plus half a screen at the widest zoom. */
  private visibleWorld(): Rect {
    const mx = this.screenW / this.camera.minScale;
    const my = this.screenH / this.camera.minScale;
    return { x: this.bounds.x - mx, y: this.bounds.y - my, w: this.bounds.w + 2 * mx, h: this.bounds.h + 2 * my };
  }

  private drawGround(): void {
    const r = this.visibleWorld();
    if (this.groundSprite) {
      this.groundSprite.position.set(r.x, r.y);
      this.groundSprite.width = r.w;
      this.groundSprite.height = r.h;
      // Keep the pattern fixed to the world, not to the sprite's corner.
      this.groundSprite.tilePosition.set(-r.x, -r.y);
      return;
    }
    this.groundLayer.removeChildren().forEach((c) => c.destroy());
    this.groundLayer.addChild(new Graphics().rect(r.x, r.y, r.w, r.h).fill(PALETTE.field));
    void this.loadGround();
  }

  /** Swap the flat stand-in ground and road for the rendered, seamless textures once they exist. */
  private async loadGround(): Promise<void> {
    const ground = this.art?.manifest.ground;
    if (!this.art || !ground?.field) return;
    const density = this.art.density;
    if (this.groundSprite && density === this.groundDensity) return;
    const load = async (image: string | undefined): Promise<Texture | null> => {
      if (!image) return null;
      try {
        const texture = await Assets.load<Texture>(`${this.artUrl}/${image}@${density}x.webp`);
        texture.source.addressMode = 'repeat';
        return texture;
      } catch {
        return null;
      }
    };
    const [field, road] = await Promise.all([load(ground.field.image), load(ground.road?.image)]);
    if (this.root.destroyed || density !== this.art.density || !field) return;
    this.groundDensity = density;
    this.roadTexture = road;
    if (this.groundSprite) {
      this.groundSprite.texture = field;
    } else {
      const scale = spriteScale(TILE_W, METRES_PER_TILE, ground.field.sizePx1x[0] / ground.field.metres);
      this.groundSprite = new TilingSprite({ texture: field, tileScale: { x: scale, y: scale } });
      this.groundLayer.removeChildren().forEach((c) => c.destroy());
      this.groundLayer.addChild(this.groundSprite);
      this.drawGround();
    }
    this.drawMap();
  }

  /**
   * The road, drawn over the ground: the rendered packed-earth texture cut to
   * the road's shape, with two wider, fainter copies underneath so the edge
   * fades into the field instead of ending in a hard line.
   */
  private drawMap(): void {
    const g = this.map;
    g.clear();
    const r = this.visibleWorld();
    const reach = Math.ceil(Math.max(r.w, r.h) / TILE_W) + 2;
    const def = this.art?.manifest.ground?.road;
    const scale = def ? spriteScale(TILE_W, METRES_PER_TILE, def.sizePx1x[0] / def.metres) : 1;
    const matrix = new Matrix().scale(scale, scale);
    for (const line of roadCentreLines(this.game, reach)) {
      for (const [half, alpha] of [[0.6, 0.3], [0.55, 0.55], [0.5, 1]] as const) {
        const pts = stripOutline(line, half).flatMap((p) => [isoX(p.x, p.y), isoY(p.x, p.y)]);
        if (this.roadTexture) g.poly(pts).fill({ texture: this.roadTexture, matrix, textureSpace: 'global', alpha });
        else g.poly(pts).fill({ color: PALETTE.path, alpha: alpha * 0.8 });
      }
    }
    if (this.game.openField) this.drawArcField(g);
  }

  /** Arc mode: rock outcrops inside the field and the fortified goal (drawn stand-ins until there is art). */
  private drawArcField(g: Graphics): void {
    const { grid } = this.game.map;
    const band = (x: number, y: number) => grid.inBounds(x, y) && Math.abs(x - y) <= 10;
    for (let y = 0; y < grid.rows; y++) {
      for (let x = 0; x < grid.cols; x++) {
        if (grid.get(x, y) !== 'blocked' || !band(x, y)) continue;
        const d = diamond(x, y, x + 1, y + 1);
        g.poly(d).fill({ color: PALETTE.rockShade, alpha: 0.95 });
        g.poly(diamond(x + 0.15, y + 0.15, x + 0.85, y + 0.85).map((v, i) => (i % 2 ? v - 6 : v))).fill({ color: PALETTE.rock });
      }
    }
    // The base draws its headquarters as a building of its own.
    if (this.game.hq) return;
    const goals = this.game.map.goals;
    const gx = Math.min(...goals.map((c) => c.x));
    const gy = Math.min(...goals.map((c) => c.y));
    const size = 2;
    // Earth rampart, a raised stone keep and a flag.
    g.poly(diamond(gx - 0.2, gy - 0.2, gx + size + 0.2, gy + size + 0.2)).fill({ color: PALETTE.pathEdge, alpha: 0.9 });
    const lift = 18;
    const top = diamond(gx + 0.3, gy + 0.3, gx + size - 0.3, gy + size - 0.3);
    const raised = top.map((v, i) => (i % 2 ? v - lift : v));
    // Side walls: the two lower faces of the keep.
    const [, , rx, ry, bx, by, lx, ly] = top as [number, number, number, number, number, number, number, number];
    g.poly([lx, ly, bx, by, bx, by - lift, lx, ly - lift]).fill({ color: PALETTE.rockShade });
    g.poly([bx, by, rx, ry, rx, ry - lift, bx, by - lift]).fill({ color: PALETTE.rock });
    g.poly(raised).fill({ color: PALETTE.towerBaseTop }).stroke({ width: 1, color: PALETTE.towerBaseSide });
    const cx = isoX(gx + size / 2, gy + size / 2);
    const cy = isoY(gx + size / 2, gy + size / 2) - lift;
    g.moveTo(cx, cy).lineTo(cx, cy - 34).stroke({ width: 2, color: PALETTE.towerGun });
    g.poly([cx, cy - 34, cx + 16, cy - 29, cx, cy - 24]).fill({ color: PALETTE.goal });
  }

  // ---- events from the simulation ------------------------------------------

  addFloat(text: string, gx: number, gy: number, color: number): void {
    const node = new Text({
      text,
      style: { fontFamily: 'system-ui, sans-serif', fontSize: 13, fontWeight: '700', fill: color, stroke: { color: 0x000000, width: 3 } },
    });
    node.anchor.set(0.5);
    this.floats.addChild(node);
    this.floatTexts.push({ node, age: 0, gx, gy, h: 0.6 });
  }

  /** A gun fired: flash and recoil on its view, and remember where the round visibly starts. */
  onShot(towerId: number, projectileId: number): void {
    const tower = this.game.towerById(towerId);
    const entry = this.towerViews.get(towerId);
    if (!tower || !entry) return;
    entry.view.setAim(tower.aim);
    entry.view.fire();
    const m = entry.view.muzzle();
    this.shotOrigins.set(projectileId, { dx: m.gx - tower.x, dy: m.gy - tower.y, h: m.heightM / METRES_PER_TILE });
    // Only what this gun's art asks for: powder guns flash and smoke, engines fire silently.
    const fx = this.effects;
    const wanted = this.shotFx(tower.def);
    if (!fx || !wanted.length) return;
    const a = entry.view instanceof SpriteTowerView ? entry.view.aimAngle() : tower.aim;
    const size = tower.size / 3;
    const opts = { height: (m.heightM / METRES_PER_TILE) * RISE, zBias: depth(tower.x, tower.y) - depth(m.gx, m.gy) + 0.01 };
    // Flame along the barrel as it lies on screen; drawn just over the gun it belongs to.
    if (wanted.includes('muzzle_flash')) fx.play('muzzle_flash', m.gx, m.gy, { ...opts, rotation: screenAngle(a), size: 0.5 + 0.5 * size });
    if (wanted.includes('muzzle_smoke')) fx.play('muzzle_smoke', m.gx, m.gy, { ...opts, zBias: opts.zBias + 0.01, size: 0.6 + 0.6 * size, lift: 10 });
  }

  /** Effects a gun shows when it fires (cached per gun id). */
  private shotFx(def: string): string[] {
    let list = this.shotFxCache.get(def);
    if (!list) {
      list = shotEffects(this.art?.manifest, def);
      this.shotFxCache.set(def, list);
    }
    return list;
  }

  onBurst(gx: number, gy: number, radius: number): void {
    // The rendered burst is made for a 1.3-tile blast; bigger shells get a bigger cloud.
    if (this.effects?.has('shell_burst')) this.effects.play('shell_burst', gx, gy, { size: radius / 1.3, zBias: 0.2 });
    else this.bursts.push({ gx, gy, radius, age: 0 });
  }

  /** A direct round struck: a small spray of earth and smoke at the target. */
  onImpact(gx: number, gy: number): void {
    this.effects?.play('shell_burst', gx, gy, { size: 0.3, zBias: 0.2 });
  }

  /** A unit was destroyed: vehicles go up in a burst of their own. */
  onKill(enemyId: number): void {
    const e = this.enemyViews.get(enemyId);
    if (!e || !VEHICLE_BURST[e.kind]) return;
    this.effects?.play('shell_burst', e.gx, e.gy, { size: VEHICLE_BURST[e.kind], zBias: 0.2 });
  }

  /** A railgun slug: the rendered beam when the art has it, else a bright drawn line out to the end of its range. */
  onRail(towerId: number, x1: number, y1: number, x2: number, y2: number): void {
    const tower = this.game.towerById(towerId);
    const m = this.towerViews.get(towerId)?.view.muzzle();
    if (tower && m && this.shotFx(tower.def).includes('rail_beam') && this.effects?.has('rail_beam')) {
      const a = Math.atan2(y2 - y1, x2 - x1);
      const len = Math.hypot(x2 - m.gx, y2 - m.gy);
      this.effects.play('rail_beam', m.gx, m.gy, {
        height: (m.heightM / METRES_PER_TILE) * RISE,
        rotation: screenAngle(a),
        lengthPx: groundLengthPx(len, a),
        zBias: 0.5,
      });
      return;
    }
    this.rails.push({ x1, y1, x2, y2, age: 0 });
  }

  /** Siege mode: a unit fired at or rammed a gun or fence. */
  onStrike(kind: 'shoot' | 'ram', x1: number, y1: number, x2: number, y2: number): void {
    if (kind === 'shoot') this.strikes.push({ x1, y1, x2, y2, age: 0 });
    // A ram lands where the vehicle meets the wall.
    const ix = kind === 'ram' ? (x1 + x2) / 2 : x2;
    const iy = kind === 'ram' ? (y1 + y2) / 2 : y2;
    if (this.effects?.has('shell_burst')) this.effects.play('shell_burst', ix, iy, { size: kind === 'ram' ? 0.45 : 0.22, zBias: 0.3 });
    else if (kind === 'ram') this.bursts.push({ gx: ix, gy: iy, radius: 0.4, age: 0 });
  }

  /** Siege mode: a gun or fence was destroyed. */
  onWrecked(gx: number, gy: number, size: number): void {
    if (this.effects?.has('shell_burst')) this.effects.play('shell_burst', gx, gy, { size: 0.5 + 0.35 * size, zBias: 0.3 });
    else this.bursts.push({ gx, gy, radius: 0.5 * size + 0.3, age: 0 });
  }

  // ---- per frame -----------------------------------------------------------

  private syncFences(): void {
    const fences = this.game.fences;
    if (!fences.length && !this.fenceViews.size) return;
    const { grid } = this.game.map;
    const at = new Set(fences.map((f) => grid.index(f.cx, f.cy)));
    const has = (x: number, y: number) => grid.inBounds(x, y) && at.has(grid.index(x, y));
    const seen = new Set<number>();
    for (const f of fences) {
      seen.add(f.id);
      let view = this.fenceViews.get(f.id);
      if (!view) {
        view = new FenceView(this.art, this.artScale(), f.x, f.y);
        this.objects.addChild(view.node);
        this.fenceViews.set(f.id, view);
      }
      // Walls join their neighbours into one line.
      const mask = (has(f.cx + 1, f.cy) ? PX : 0) | (has(f.cx - 1, f.cy) ? NX : 0) | (has(f.cx, f.cy + 1) ? PY : 0) | (has(f.cx, f.cy - 1) ? NY : 0);
      view.update(f.level, mask);
    }
    for (const [id, view] of this.fenceViews) {
      if (seen.has(id)) continue;
      view.destroy();
      this.fenceViews.delete(id);
    }
  }

  /** Base mode: the headquarters and the laboratory (gone once destroyed). */
  private syncBuildings(): void {
    for (const b of [this.game.hq, this.game.lab] as const) {
      if (!b) continue;
      let view = this.buildingViews.get(b.kind);
      if (!view) {
        view = new BuildingView(b.kind, b.x, b.y);
        this.objects.addChild(view.node);
        this.buildingViews.set(b.kind, view);
      }
      view.update(b.level);
    }
    for (const [kind, view] of this.buildingViews) {
      if ((kind === 'hq' ? this.game.hq : this.game.lab) !== null) continue;
      view.destroy();
      this.buildingViews.delete(kind);
    }
  }

  /** Siege mode: health bars over damaged guns and fences, and enemy shots; in the base, the builders' progress. */
  private drawSiege(g: Graphics, dt: number): void {
    const now = Date.now();
    const speed = this.game.base?.speed ?? 1;
    for (const t of this.game.towers) {
      const view = this.towerViews.get(t.id)?.view;
      if (view) view.node.alpha = t.job?.kind === 'build' ? 0.45 : 1;
      if (!t.job) continue;
      const total = (gunJobSeconds(t.def, t.job.kind === 'build' ? 0 : t.level + 1) * 1000) / speed;
      const f = Math.min(1, Math.max(0, 1 - (t.job.endsAt - now) / total));
      const w = Math.max(26, 14 * t.size);
      const x = isoX(t.x, t.y);
      const y = isoY(t.x, t.y, 0.35 * t.size + 0.4) - 16;
      g.rect(x - w / 2 - 1, y - 1, w + 2, 6).fill({ color: 0x000000, alpha: 0.6 });
      g.rect(x - w / 2, y, w * f, 4).fill(0x5fb4ff);
    }
    const bar = (s: Tower | Fence | Building, size: number, lift: number) => {
      if (s.hp >= s.maxHp) return;
      const f = Math.max(0, s.hp / s.maxHp);
      const w = Math.max(22, 14 * size);
      const x = isoX(s.x, s.y);
      const y = isoY(s.x, s.y, lift) - 8;
      g.rect(x - w / 2 - 1, y - 1, w + 2, 6).fill({ color: 0x000000, alpha: 0.6 });
      g.rect(x - w / 2, y, w * f, 4).fill(f > 0.5 ? 0x7bd36a : f > 0.25 ? 0xe6c14a : 0xe0624f);
    };
    for (const t of this.game.towers) bar(t, t.size, 0.35 * t.size + 0.4);
    for (const f of this.game.fences) bar(f, 1, FENCE_HEIGHT[Math.min(f.level, 2)]! * 1.2 + 0.1);
    if (this.game.hq) bar(this.game.hq, 3, 1.4 + 0.18 * this.game.hq.level);
    if (this.game.lab) bar(this.game.lab, 3, 1.1);
    this.strikes = this.strikes.filter((s) => {
      s.age += dt;
      const k = s.age / STRIKE_LIFE;
      if (k >= 1) return false;
      g.moveTo(isoX(s.x1, s.y1), isoY(s.x1, s.y1, 0.25))
        .lineTo(isoX(s.x2, s.y2), isoY(s.x2, s.y2, 0.3))
        .stroke({ width: 1.5, color: 0xff9a5a, alpha: 0.9 * (1 - k), cap: 'round' });
      return true;
    });
  }

  private createTowerView(t: Tower): PixiTowerView {
    const spec = { tower: t.def, level: t.level + 1, size: t.size, flash: this.shotFx(t.def).includes('muzzle_flash') };
    const view = this.art?.level(t.def, t.level + 1) ? new SpriteTowerView(this.art, spec, METRES_PER_TILE) : new PlaceholderTowerView(spec);
    view.place(t.x, t.y);
    view.setAim(t.aim);
    this.objects.addChild(view.node);
    return view;
  }

  private syncTowers(dt: number): void {
    const seen = new Set<number>();
    for (const t of this.game.towers) {
      seen.add(t.id);
      let entry = this.towerViews.get(t.id);
      if (!entry) {
        entry = { view: this.createTowerView(t), level: t.level };
        this.towerViews.set(t.id, entry);
      }
      if (entry.level !== t.level) {
        entry.level = t.level;
        entry.view.setLevel(t.level + 1);
      }
      entry.view.setAim(t.aim);
      entry.view.update(dt);
    }
    for (const [id, entry] of this.towerViews) {
      if (seen.has(id)) continue;
      entry.view.destroy();
      this.towerViews.delete(id);
    }
  }

  private syncEnemies(alpha: number): void {
    const seen = new Set<number>();
    for (const e of this.game.enemies) {
      seen.add(e.id);
      let entry = this.enemyViews.get(e.id);
      if (!entry) {
        const def = this.art?.manifest.enemies?.[e.def];
        const view: PixiEnemyView = this.art && def ? new SpriteEnemyView(this.art, def, e.def, this.artScale(), METRES_PER_TILE) : new PlaceholderEnemyView(e.def, ENEMIES[e.def].radius);
        entry = { view, kind: e.def, gx: e.x, gy: e.y };
        this.enemyViews.set(e.id, entry);
        this.objects.addChild(view.node);
      }
      entry.gx = e.px + (e.x - e.px) * alpha;
      entry.gy = e.py + (e.y - e.py) * alpha;
      entry.view.place(entry.gx, entry.gy);
      entry.view.setHeading(e.heading);
      entry.view.setHealth(e.hp / e.maxHp);
    }
    for (const [id, { view }] of this.enemyViews) {
      if (seen.has(id)) continue;
      view.destroy();
      this.enemyViews.delete(id);
    }
  }

  private drawOverlay(selection: Selection | null, armed: Armed | null): void {
    const o = this.overlay;
    const game = this.game;
    const { grid } = game.map;
    // Redraw only when something it shows has changed.
    const key = JSON.stringify([selection, armed, game.towers.map((t) => [t.id, t.level]), game.fences.length, game.openField ? game.arcWidth() : 0, game.hq?.level, !!game.lab]);
    if (key === this.overlayKey) return;
    this.overlayKey = key;
    o.clear();

    // Open field: mark the stretch of edge the running or next wave comes in from.
    if (game.openField) {
      for (const c of game.activeSpawns()) o.poly(diamond(c.x, c.y, c.x + 1, c.y + 1)).fill({ color: PALETTE.invalid, alpha: 0.28 });
    }

    // While a gun is picked for building, show where it can stand.
    if (selection?.kind === 'place' || (armed && !selection)) {
      for (let y = 0; y < grid.rows; y++) {
        for (let x = 0; x < grid.cols; x++) {
          if (grid.get(x, y) !== 'build' || game.towerAt(x, y) || game.fenceAt(x, y) || game.buildingAt(x, y) || !game.inArea(x, y, 1)) continue;
          o.poly(diamond(x, y, x + 1, y + 1)).stroke({ width: 1, color: PALETTE.gridLine, alpha: 0.22 });
        }
      }
    }

    // The base: the ring the headquarters lets the player build inside.
    if (game.hq && (selection?.kind === 'place' || armed || selection?.kind === 'building')) {
      const r = HQ_LEVELS[game.hq.level]!.radius;
      const hx = HQ_SPOT[0] + BUILDING_SIZE / 2;
      const hy = HQ_SPOT[1] + BUILDING_SIZE / 2;
      const pts: number[] = [];
      for (let i = 0; i <= 64; i++) {
        const a = (i / 64) * Math.PI * 2;
        pts.push(isoX(hx + r * Math.cos(a), hy + r * Math.sin(a)), isoY(hx + r * Math.cos(a), hy + r * Math.sin(a)));
      }
      o.poly(pts).stroke({ width: 2, color: 0xf2c94c, alpha: 0.7 });
    }

    const range = (gx: number, gy: number, radius: number, minRadius = 0) => {
      const rx = (radius * TILE_W) / Math.SQRT2;
      o.ellipse(isoX(gx, gy), isoY(gx, gy), rx, rx / 2).fill({ color: PALETTE.range, alpha: 0.1 }).stroke({ width: 2, color: PALETTE.range, alpha: 0.6 });
      if (minRadius > 0) {
        const mr = (minRadius * TILE_W) / Math.SQRT2;
        o.ellipse(isoX(gx, gy), isoY(gx, gy), mr, mr / 2).stroke({ width: 1.5, color: PALETTE.invalid, alpha: 0.5 });
      }
    };

    if (selection?.kind === 'building') {
      const b = selection.what === 'hq' ? game.hq : game.lab;
      if (b) o.poly(diamond(b.cx, b.cy, b.cx + b.size, b.cy + b.size)).stroke({ width: 2.5, color: PALETTE.range, alpha: 0.9 });
    }

    if (selection?.kind === 'place') {
      const def = TOWERS[selection.def];
      const ok = game.canBuildAt(selection.def, selection.cx, selection.cy);
      const d = diamond(selection.cx, selection.cy, selection.cx + def.size, selection.cy + def.size);
      const color = ok ? PALETTE.valid : PALETTE.invalid;
      if (ok) range(selection.cx + def.size / 2, selection.cy + def.size / 2, def.levels[0].range, 'minRange' in def ? def.minRange : 0);
      o.poly(d).fill({ color, alpha: 0.3 }).stroke({ width: 2.5, color, alpha: 0.95 });
    } else if (selection?.kind === 'tower') {
      const t = game.towerById(selection.id);
      if (t) {
        const def = TOWERS[t.def];
        range(t.x, t.y, game.levelOf(t).range, 'minRange' in def ? def.minRange : 0);
        o.poly(diamond(t.cx, t.cy, t.cx + t.size, t.cy + t.size)).stroke({ width: 2.5, color: PALETTE.hover, alpha: 0.9 });
      }
    } else if (selection?.kind === 'fence') {
      const f = game.fenceById(selection.id);
      if (f) o.poly(diamond(f.cx, f.cy, f.cx + 1, f.cy + 1)).stroke({ width: 2.5, color: PALETTE.hover, alpha: 0.9 });
    }
  }

  private drawShots(alpha: number, dt: number): void {
    const g = this.shots;
    g.clear();
    const live = new Set<number>();
    for (const p of this.game.projectiles) {
      live.add(p.id);
      const o = this.shotOrigins.get(p.id) ?? { dx: 0, dy: 0, h: 0.3 };
      const t = p.pt + (p.t - p.pt) * alpha;
      // The simulation fires from the gun's centre; visibly the round leaves the muzzle.
      const gx = p.px + (p.x - p.px) * alpha + o.dx * (1 - t);
      const gy = p.py + (p.y - p.py) * alpha + o.dy * (1 - t);
      if (p.kind === 'shell') {
        const lob = Math.hypot(p.tx - p.ox, p.ty - p.oy) * 0.22;
        const h = o.h + (0 - o.h) * t + 4 * lob * t * (1 - t);
        g.ellipse(isoX(gx, gy), isoY(gx, gy), 3.5, 1.75).fill({ color: 0x000000, alpha: 0.22 });
        g.circle(isoX(gx, gy), isoY(gx, gy, h), 2.6).fill(PALETTE.shell);
      } else {
        // Rounds at a drone climb to it.
        const hit = this.game.enemies.find((e) => e.id === p.targetId)?.air ? FLY_HEIGHT : HIT_HEIGHT;
        const h = o.h + (hit - o.h) * t;
        const x = isoX(gx, gy);
        const y = isoY(gx, gy, h);
        const dx = isoX(p.tx, p.ty) - x;
        const dy = isoY(p.tx, p.ty, hit) - y;
        const d = Math.hypot(dx, dy) || 1;
        const len = Math.min(d, 16);
        g.moveTo(x - (dx / d) * len, y - (dy / d) * len).lineTo(x, y).stroke({ width: 2, color: PALETTE.tracer, alpha: 0.9, cap: 'round' });
      }
    }
    for (const id of this.shotOrigins.keys()) if (!live.has(id)) this.shotOrigins.delete(id);
    if (this.game.mode === 'siege') this.drawSiege(g, dt);

    // Greek fire: a jet of flame from the siphon to its target (rendered when the art has it).
    for (const t of this.game.towers) {
      if (!t.firing) continue;
      const target = this.game.enemies.find((e) => e.id === t.targetId);
      if (!target) continue;
      const m = this.towerViews.get(t.id)?.view.muzzle();
      const mx = m?.gx ?? t.x;
      const my = m?.gy ?? t.y;
      const mh = (m?.heightM ?? 1) / METRES_PER_TILE;
      const heat = Math.min(1, t.heat / 3);
      if (this.shotFx(t.def).includes('fire_stream')) {
        const a = Math.atan2(target.y - my, target.x - mx);
        const len = Math.hypot(target.x - mx, target.y - my);
        const shown = this.effects?.hold(`flame:${t.id}`, 'fire_stream', mx, my, {
          height: mh * RISE,
          rotation: screenAngle(a),
          lengthPx: groundLengthPx(len, a),
          size: 0.7 + 0.3 * heat,
          zBias: 0.4,
        });
        if (shown) continue;
      }
      const x0 = isoX(mx, my);
      const y0 = isoY(mx, my, mh);
      const x1 = isoX(target.x, target.y);
      const y1 = isoY(target.x, target.y, HIT_HEIGHT);
      const flicker = 0.75 + 0.25 * Math.sin(this.game.time * 40 + t.id);
      g.moveTo(x0, y0).lineTo(x1, y1).stroke({ width: 9 * flicker, color: 0xd9531e, alpha: 0.35 + 0.25 * heat, cap: 'round' });
      g.moveTo(x0, y0).lineTo(x1, y1).stroke({ width: 4 * flicker, color: 0xffc04a, alpha: 0.8, cap: 'round' });
      g.circle(x1, y1, 6 + 6 * heat * flicker).fill({ color: 0xff8a2a, alpha: 0.5 });
    }

    // Railgun charge: a glow at the muzzle building up over the last moments before the slug.
    for (const t of this.game.towers) {
      if (!t.targetId || !this.shotFx(t.def).includes('rail_charge')) continue;
      const k = 1 - Math.min(1, t.cooldown / RAIL_CHARGE);
      if (k <= 0) continue;
      const m = this.towerViews.get(t.id)?.view.muzzle();
      if (!m) continue;
      const h = m.heightM / METRES_PER_TILE;
      const shown = this.effects?.hold(`charge:${t.id}`, 'rail_charge', m.gx, m.gy, {
        height: h * RISE,
        size: 0.4 + 0.6 * k,
        zBias: depth(t.x, t.y) - depth(m.gx, m.gy) + 0.01,
      });
      if (shown) continue;
      const x = isoX(m.gx, m.gy);
      const y = isoY(m.gx, m.gy, h);
      const pulse = 0.85 + 0.15 * Math.sin(this.game.time * 30 + t.id);
      g.circle(x, y, (3 + 7 * k) * pulse).fill({ color: 0x7fd4ff, alpha: 0.35 * k });
      g.circle(x, y, (1.5 + 2.5 * k) * pulse).fill({ color: 0xffffff, alpha: 0.6 * k });
    }

    // Railgun traces.
    this.rails = this.rails.filter((r) => {
      r.age += dt;
      const k = r.age / RAIL_LIFE;
      if (k >= 1) return false;
      const a = [isoX(r.x1, r.y1), isoY(r.x1, r.y1, 0.35)] as const;
      const b = [isoX(r.x2, r.y2), isoY(r.x2, r.y2, 0.35)] as const;
      g.moveTo(a[0], a[1]).lineTo(b[0], b[1]).stroke({ width: 8 * (1 - k), color: 0x7fd4ff, alpha: 0.5 * (1 - k), cap: 'round' });
      g.moveTo(a[0], a[1]).lineTo(b[0], b[1]).stroke({ width: 2.5, color: 0xffffff, alpha: 1 - k, cap: 'round' });
      return true;
    });

    // Shell bursts: a quick flash, then dust spreading over the blast circle.
    this.bursts = this.bursts.filter((b) => {
      b.age += dt;
      const k = b.age / BURST_LIFE;
      if (k >= 1) return false;
      const x = isoX(b.gx, b.gy);
      const y = isoY(b.gx, b.gy);
      const rx = ((b.radius * TILE_W) / Math.SQRT2) * (0.35 + 0.65 * Math.sqrt(k));
      g.ellipse(x, y, rx, rx / 2).fill({ color: PALETTE.dust, alpha: 0.45 * (1 - k) });
      g.ellipse(x, y, rx, rx / 2).stroke({ width: 2, color: PALETTE.dust, alpha: 0.7 * (1 - k) });
      if (k < 0.3) g.circle(x, y - 6, 14 * (1 - k / 0.3) + 4).fill({ color: PALETTE.blast, alpha: 0.9 * (1 - k / 0.3) });
      return true;
    });
  }

  /**
   * Draw one frame. `alpha` interpolates between the last two sim steps.
   * `armed` is the gun picked in the build menu, if any.
   */
  render(alpha: number, selection: Selection | null, armed: Armed | null, dtSeconds: number): void {
    this.applyCamera();
    this.syncTowers(dtSeconds);
    this.syncFences();
    if (this.game.hq) this.syncBuildings();
    this.syncEnemies(alpha);
    this.drawOverlay(selection, armed);
    this.drawShots(alpha, dtSeconds);
    this.effects?.update(dtSeconds);

    // Floating texts rise and fade; they live in screen space so they stay crisp at any zoom.
    this.floatTexts = this.floatTexts.filter((f) => {
      f.age += dtSeconds;
      f.h += dtSeconds * 1.2;
      const p = this.gridToScreen(f.gx, f.gy, f.h);
      f.node.position.set(p.x, p.y);
      f.node.alpha = Math.max(0, 1 - f.age / FLOAT_LIFE);
      if (f.age >= FLOAT_LIFE) {
        f.node.destroy();
        return false;
      }
      return true;
    });
  }
}
