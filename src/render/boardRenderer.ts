import { Assets, Container, Graphics, Matrix, Sprite, Text, TilingSprite, type Texture } from 'pixi.js';
import { ENEMIES, METRES_PER_TILE, TOWERS, type TowerDef, type TowerId } from '../sim/content';
import { isWreck, type Building, type Fence, type Game, type Tower } from '../sim/game';
import { BUILDING_SIZE, gunJobSeconds, HQ_LEVELS, HQ_SPOT, type BuildingKind } from '../sim/base';
import { isTrapId, TRAPS, type TrapId } from '../sim/traps';
import { BuildingView, type BuildingState } from './buildingView';
import { Camera, type Rect } from './camera';
import { Effects } from './effects';
import { FENCE_HEIGHT, FenceView, NX, NY, PX, PY } from './fenceView';
import { FLY_HEIGHT, FLYER_Z, PlaceholderEnemyView, SpriteEnemyView, type EnemyView } from './enemyView';
import { depth, diamond, isoX, isoY, project, RISE, TILE_H, TILE_W, unproject } from './iso';
import { PALETTE } from './palette';
import { roadCentreLines, stripOutline } from './road';
import { PlaceholderTowerView } from './towers/placeholderTowerView';
import { SpriteTowerView, type Density, type TowerArt } from './towers/spriteTowerView';
import { frameForAim, shotEffects, spriteScale, type ProjectileArtDef } from './towers/towerArt';
import type { TowerView } from './towers/towerView';

/** What the build menu has picked: a gun, fences (siege mode) or a kind of trap. */
export type Armed = TowerId | 'fence' | TrapId;

/** The picked gun, when a gun (not fences or a trap) is picked. */
export function armedGun(a: Armed | null): TowerId | null {
  return a && a !== 'fence' && !isTrapId(a) ? a : null;
}

export type Selection =
  /** An existing gun, by id. */
  | { kind: 'tower'; id: number }
  /** Siege mode: an existing fence, by id. */
  | { kind: 'fence'; id: number }
  /** A trap on the map, by id. */
  | { kind: 'trap'; id: number }
  /** Base mode: one of the base's buildings. */
  | { kind: 'building'; what: BuildingKind }
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
  /** Seconds before the round visibly leaves (a trebuchet's arm swings first), and seconds since the shot. */
  delay: number;
  age: number;
  /** Flight progress when the round visibly left. */
  t0: number;
  /** The round's own picture: sheet and frame prefix, when the art has one. */
  round?: { def: ProjectileArtDef; sheet: string; animation: string };
}

const FLOAT_LIFE = 0.9;
const STRIKE_LIFE = 0.18;

const RAIL_LIFE = 0.35;
const FLASH_LIFE = 0.3;
const GLANCE_LIFE = 0.25;

/** Screen rotation of a direction on the ground (`a` = atan2(dy, dx) in grid cells). */
function screenAngle(a: number): number {
  return Math.atan2((Math.cos(a) + Math.sin(a)) / 2, Math.cos(a) - Math.sin(a));
}

/** World pixels on screen that `tiles` of ground span in direction `a`. */
function groundLengthPx(tiles: number, a: number): number {
  return Math.hypot(isoX(Math.cos(a), Math.sin(a)), isoY(Math.cos(a), Math.sin(a))) * tiles;
}
/** Size of the burst a destroyed vehicle goes up in; units not listed just fall. */
const VEHICLE_BURST: Record<string, number> = { drone: 0.6, truck: 0.65, apc: 0.75, tank: 0.85, fortress: 1.4, wagon: 0.6, glider: 0.4, armorcar: 0.65, shield: 0.85, boat: 1.1, dreadnought: 1.7 };
/** Units drawn up in the air: their hits and wrecks burst at flying height. */
const AIR_KINDS = new Set<string>(Object.values(ENEMIES).filter((e) => 'air' in e && e.air).map((e) => e.id));
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
  /** Dazzle lamp flashes: a lit cone on the ground, fading. */
  private flashes: { x: number; y: number; aim: number; cone: number; range: number; big: boolean; age: number }[] = [];
  /** Ricochet discs glancing from one enemy to the next. */
  private glances: { x1: number; y1: number; x2: number; y2: number; age: number }[] = [];
  /** Siege mode: enemy shots at guns and fences, fading out. */
  private strikes: { x1: number; y1: number; x2: number; y2: number; age: number }[] = [];
  private readonly fenceViews = new Map<number, FenceView>();
  private readonly buildingViews = new Map<BuildingKind, BuildingView>();
  /** The selected building's name, under it (like Clash of Clans: only while it is selected). */
  /** The raid that provokes an attack: friendly riders. */
  private readonly raiderViews: PixiEnemyView[] = [];
  /** Base mode: marks over the base: the sealed daily order over the muster, star medals by the headquarters. */
  marks = { envelope: false, medals: 0 };
  /** Base mode: the camera has been put on the base once. */
  private focused = false;
  private readonly towerViews = new Map<number, { view: PixiTowerView; level: number }>();
  private readonly enemyViews = new Map<number, { view: PixiEnemyView; kind: string; gx: number; gy: number }>();
  /** Rendered one-shot animations, when the art has them. */
  private readonly effects: Effects | null;
  private readonly shotOrigins = new Map<number, ShotOrigin>();
  /** Rendered rounds in flight, by projectile id. */
  private readonly rounds = new Container();
  private readonly roundSprites = new Map<number, Sprite>();
  private readonly shotFxCache = new Map<string, string[]>();
  private overlayKey = '';
  /** Traps and tar patches, on the ground under everything that stands. */
  private readonly trapLayer = new Graphics();
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
    this.world.addChild(this.groundLayer, this.map, this.overlay, this.trapLayer, this.objects, this.shots, this.rounds);
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
    // The base opens on the base: closer in, the headquarters low in the view and the way the enemy comes above it.
    if (this.game.hq && !this.focused) {
      this.focused = true;
      const p = project(HQ_SPOT[0] - 3, HQ_SPOT[1] - 3);
      this.camera.focus(p.x, p.y, this.camera.minScale * 1.45);
    }
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

  /** A rising number; `air` starts it up at flying height. */
  addFloat(text: string, gx: number, gy: number, color: number, air = false): void {
    const node = new Text({
      text,
      style: { fontFamily: 'system-ui, sans-serif', fontSize: 13, fontWeight: '700', fill: color, stroke: { color: 0x000000, width: 3 } },
    });
    node.anchor.set(0.5);
    this.floats.addChild(node);
    this.floatTexts.push({ node, age: 0, gx, gy, h: air ? this.flyHeight() + 0.6 : 0.6 });
  }

  /** A gun fired: flash and recoil on its view, and remember where the round visibly starts. */
  onShot(towerId: number, projectileId: number): void {
    const tower = this.game.towerById(towerId);
    const entry = this.towerViews.get(towerId);
    if (!tower || !entry) return;
    entry.view.setAim(tower.aim);
    const delay = entry.view.fire(this.game.levelOf(tower).fireInterval);
    const m = entry.view.muzzle();
    this.shotOrigins.set(projectileId, {
      dx: m.gx - tower.x,
      dy: m.gy - tower.y,
      h: m.heightM / METRES_PER_TILE,
      delay,
      age: 0,
      t0: 0,
      round: this.roundArt(tower.def, tower.level + 1),
    });
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

  /** The picture of a gun's round in flight at a level, if the art has one. */
  private roundArt(tower: string, level: number): ShotOrigin['round'] {
    const def = this.art?.manifest.projectiles?.[tower];
    if (!def?.levels.length) return undefined;
    const lv = def.levels.includes(level) ? level : Math.max(...def.levels.filter((l) => l <= level), def.levels[0]!);
    return { def, sheet: def.sheet, animation: def.animation.replace('<level>', String(lv)) };
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

  /**
   * A direct round struck: a small spray of earth and smoke at the target. On
   * a flyer it strikes sparks up on its hull, drawn over it (earth would not
   * fly up there, and dust does not show on a grey hull).
   */
  onImpact(gx: number, gy: number, air = false): void {
    if (air) this.airHit(gx, gy, 1);
    else this.effects?.play('shell_burst', gx, gy, { size: 0.3, zBias: 0.2 });
  }

  /** Sparks and a puff of smoke at a flyer's height over a ground point; `size` 1 for a bolt. */
  private airHit(gx: number, gy: number, size: number): void {
    const fx = this.effects;
    if (!fx) return;
    // Not every bolt on the same spot of the hull.
    const jx = (Math.random() - 0.5) * 0.5;
    const jy = (Math.random() - 0.5) * 0.5;
    const height = this.flyHeight() * RISE + (Math.random() - 0.5) * 10;
    const a = Math.random() * Math.PI * 2;
    const opts = { height, zBias: FLYER_Z + 0.3 };
    fx.play('muzzle_flash', gx + jx, gy + jy, { ...opts, size: 0.4 * size, rotation: a });
    fx.play('muzzle_flash', gx + jx, gy + jy, { ...opts, size: 0.3 * size, rotation: a + Math.PI * (0.8 + Math.random() * 0.4) });
    fx.play('muzzle_smoke', gx + jx, gy + jy, { ...opts, zBias: FLYER_Z + 0.25, size: 0.3 * size, lift: 8 });
  }

  /** A unit was destroyed: vehicles go up in a burst of their own. */
  onKill(enemyId: number): void {
    const e = this.enemyViews.get(enemyId);
    if (!e || !VEHICLE_BURST[e.kind]) return;
    // A flyer goes up in the air where it was, not on the ground under it.
    const air = AIR_KINDS.has(e.kind);
    this.effects?.play('shell_burst', e.gx, e.gy, { size: VEHICLE_BURST[e.kind], zBias: air ? FLYER_Z + 0.2 : 0.2, height: air ? this.flyHeight() * RISE : 0 });
    if (air) this.airHit(e.gx, e.gy, 2.2);
  }

  /** A railgun slug: the rendered beam when the art has it, else a bright drawn line out to the end of its range. */
  onRail(towerId: number, x1: number, y1: number, x2: number, y2: number): void {
    const tower = this.game.towerById(towerId);
    const view = this.towerViews.get(towerId)?.view;
    if (tower && view) {
      view.setAim(tower.aim);
      view.fire(this.game.levelOf(tower).fireInterval);
    }
    const m = view?.muzzle();
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

  /** Dazzle lamp: a flash over its cone (stand-in drawing until it has art). */
  onFlash(towerId: number, x: number, y: number, aim: number, cone: number, range: number, big: boolean): void {
    const tower = this.game.towerById(towerId);
    const view = this.towerViews.get(towerId)?.view;
    if (tower && view) {
      view.setAim(tower.aim);
      view.fire(this.game.levelOf(tower).fireInterval);
    }
    this.flashes.push({ x, y, aim, cone, range, big, age: 0 });
  }

  /** Ricochet disc: a streak from the enemy it hit to the next one. */
  onBounce(x1: number, y1: number, x2: number, y2: number): void {
    this.glances.push({ x1, y1, x2, y2, age: 0 });
  }

  /** Siege mode: a unit fired at or rammed a gun or fence. */
  onStrike(kind: 'shoot' | 'ram' | 'bomb' | 'blast', x1: number, y1: number, x2: number, y2: number): void {
    if (kind === 'bomb') {
      this.onBurst(x2, y2, 0.7);
      return;
    }
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

  /** Base mode: every building, in its state (whole, hit hard, in ruins, held by the enemy). */
  private syncBuildings(): void {
    const occupied = !!this.game.base?.state.occupied;
    for (const b of this.game.buildings) {
      let view = this.buildingViews.get(b.kind);
      if (!view) {
        view = new BuildingView(b.kind, b.x, b.y, this.art, this.artScale());
        this.objects.addChild(view.node);
        this.buildingViews.set(b.kind, view);
      }
      const state: BuildingState = b.kind === 'hq' && occupied && b.hp <= 0 ? 'occupied' : b.hp <= 0 ? 'rubble' : b.hp < b.maxHp / 2 ? 'damaged' : 'ok';
      view.update(b.level, state);
      // Hit hard: a breach burns under a column of smoke; ruins only smoke.
      if (state !== 'ok') {
        this.effects?.hold(`smoke:${b.kind}`, 'smoke_plume', b.x, b.y, { size: 1.4, zBias: 1.5 });
        if (state === 'damaged') this.effects?.hold(`fire:${b.kind}`, 'fire_burn', b.x + 0.3, b.y + 0.3, { size: 0.9, zBias: 1.4 });
      }
    }
  }

  /** The raiding party, while it rides: the defenders' riders (the bikers' art, in the player's colours, until their own is there). */
  private syncRaid(): void {
    const riders = this.game.raiders();
    while (this.raiderViews.length > riders.length) this.raiderViews.pop()!.destroy();
    riders.forEach((r, i) => {
      let view = this.raiderViews[i];
      if (!view) {
        const own = this.art?.manifest.allies?.raiders;
        const def = own ?? this.art?.manifest.enemies?.moto;
        view = this.art && def ? new SpriteEnemyView(this.art, def, own ? 'raiders' : 'moto', this.artScale(), METRES_PER_TILE) : new PlaceholderEnemyView('moto', ENEMIES.moto.radius);
        if (!own) view.node.tint = 0x9fc4ff;
        this.objects.addChild(view.node);
        this.raiderViews[i] = view;
      }
      view.place(r.x, r.y);
      view.setHeading(r.heading);
      view.setHealth(1);
    });
  }

  private wreckArt(t: Tower): boolean {
    return !!this.art?.level(t.def, t.level + 1)?.states?.wreck;
  }

  /**
   * Where the floating menu of the selection hangs, in CSS px: the footprint's
   * horizontal centre, the top of the object (roughly, art height) and its front corner.
   */
  anchorOf(selection: Selection | null): { x: number; top: number; bottom: number } | null {
    let f: { cx: number; cy: number; size: number; tall: number } | null = null;
    if (selection?.kind === 'building') {
      const b = this.game.building(selection.what);
      if (b) f = { cx: b.cx, cy: b.cy, size: b.size, tall: 1.5 };
    } else if (selection?.kind === 'tower') {
      const t = this.game.towerById(selection.id);
      if (t) f = { cx: t.cx, cy: t.cy, size: t.size, tall: 1.1 };
    } else if (selection?.kind === 'fence') {
      const fc = this.game.fenceById(selection.id);
      if (fc) f = { cx: fc.cx, cy: fc.cy, size: 1, tall: 0.5 };
    } else if (selection?.kind === 'trap') {
      const tr = this.game.trapById(selection.id);
      if (tr) f = { cx: tr.cx, cy: tr.cy, size: 1, tall: 0.3 };
    }
    if (!f) return null;
    const mid = this.gridToScreen(f.cx + f.size / 2, f.cy + f.size / 2);
    const back = this.gridToScreen(f.cx, f.cy);
    const front = this.gridToScreen(f.cx + f.size, f.cy + f.size);
    return { x: mid.x, top: back.y - f.tall * f.size * TILE_H * this.camera.scale, bottom: front.y };
  }

  /** Siege mode: health bars over damaged guns and fences, and enemy shots; in the base, the builders' progress. */
  private drawSiege(g: Graphics, dt: number): void {
    const now = Date.now();
    const speed = this.game.base?.speed ?? 1;
    for (const t of this.game.towers) {
      const view = this.towerViews.get(t.id)?.view;
      if (view) {
        const wreck = isWreck(t);
        view.node.alpha = t.job?.kind === 'build' ? 0.45 : wreck && !this.wreckArt(t) ? 0.85 : 1;
        // A wreck: the art's wreck frame, else the gun burnt dark.
        const drawn = view.setWreck?.(wreck) ?? false;
        view.node.tint = wreck && !drawn ? 0x4a4440 : 0xffffff;
        if (wreck || t.hp < t.maxHp / 2) {
          this.effects?.hold(`smoke:t${t.id}`, 'smoke_plume', t.x, t.y, { size: 0.5 + 0.35 * t.size, zBias: 1 });
          if (!wreck) this.effects?.hold(`fire:t${t.id}`, 'fire_burn', t.x, t.y, { size: 0.3 + 0.25 * t.size, zBias: 0.9 });
        }
      }
      if (!t.job) continue;
      const total = (gunJobSeconds(t.def, t.job.kind === 'build' ? 0 : t.job.kind === 'repair' ? t.level : t.level + 1) * 1000) / speed;
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
    for (const t of this.game.towers) if (!isWreck(t)) bar(t, t.size, 0.35 * t.size + 0.4);
    if (this.game.base) this.drawMarks(g);
    for (const f of this.game.fences) bar(f, 1, FENCE_HEIGHT[Math.min(f.level, 2)]! * 1.2 + 0.1);
    for (const b of this.game.buildings) if (b.hp > 0) bar(b, 3, b.kind === 'hq' ? 1.4 + 0.18 * b.level : 1.1);
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

  /**
   * Base mode: a veteran's chevrons at the front corner of its footprint, the
   * sealed envelope floating over the muster while the day's order is unread,
   * and a ribbon per star medal by the headquarters.
   */
  private drawMarks(g: Graphics): void {
    const gold = 0xf2c94c;
    for (const t of this.game.towers) {
      const rank = this.game.rank(t);
      if (!rank || isWreck(t)) continue;
      const x = isoX(t.cx + t.size, t.cy + t.size);
      const y = isoY(t.cx + t.size, t.cy + t.size) + 2;
      for (let i = 0; i < rank; i++) {
        const yy = y + i * 4;
        g.moveTo(x - 6, yy).lineTo(x, yy + 4).lineTo(x + 6, yy).stroke({ width: 3.5, color: 0x1a1408, alpha: 0.85, cap: 'round', join: 'round' });
        g.moveTo(x - 6, yy).lineTo(x, yy + 4).lineTo(x + 6, yy).stroke({ width: 2, color: gold, cap: 'round', join: 'round' });
      }
    }
    const muster = this.game.building('muster');
    if (this.marks.envelope && muster && muster.hp > 0) {
      // A gentle bob so it catches the eye.
      const bob = Math.sin(Date.now() / 380) * 2.5;
      const x = isoX(muster.x, muster.y);
      const y = isoY(muster.x, muster.y, 2.1) + bob;
      const w = 22;
      const h = 15;
      g.roundRect(x - w / 2 - 1.5, y - h / 2 - 1.5, w + 3, h + 3, 3).fill({ color: 0x000000, alpha: 0.55 });
      g.roundRect(x - w / 2, y - h / 2, w, h, 2).fill(0xe9dcc0);
      g.moveTo(x - w / 2, y - h / 2).lineTo(x, y + 1).lineTo(x + w / 2, y - h / 2).stroke({ width: 1.4, color: 0x7a6a4a });
      g.circle(x, y + 1, 3.6).fill(0xa8261d);
    }
    const hq = this.game.hq;
    if (this.marks.medals > 0 && hq && hq.hp > 0) {
      const n = Math.min(this.marks.medals, 5);
      const x0 = isoX(hq.cx + hq.size, hq.cy) - 4;
      const y0 = isoY(hq.cx + hq.size, hq.cy, 1.2);
      for (let i = 0; i < n; i++) {
        const x = x0 + i * 8;
        g.rect(x - 2.5, y0 - 8, 5, 7).fill(i % 2 ? 0x2f5aa8 : 0xa8261d);
        g.circle(x, y0 + 1, 3.6).fill({ color: 0x1a1408, alpha: 0.8 });
        g.circle(x, y0 + 1, 2.8).fill(gold);
      }
    }
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
      entry.view.setFiring(t.firing);
      entry.view.update(isWreck(t) ? 0 : dt);
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
    const key = JSON.stringify([selection, armed, game.towers.map((t) => [t.id, t.level]), game.fences.length, game.traps.length, game.openField ? game.arcWidth() : 0, game.hq?.level, game.buildings.map((b) => b.hp > 0)]);
    if (key === this.overlayKey) return;
    this.overlayKey = key;
    o.clear();

    // Open field: mark the stretch of edge the running or next wave comes in from.
    if (game.openField) {
      for (const c of game.activeSpawns()) o.poly(diamond(c.x, c.y, c.x + 1, c.y + 1)).fill({ color: PALETTE.invalid, alpha: 0.28 });
    }

    // While a trap is picked, show the tiles it can go on.
    if (armed && isTrapId(armed)) {
      for (let y = 0; y < grid.rows; y++) {
        for (let x = 0; x < grid.cols; x++) {
          const err = game.trapError(armed, x, y);
          if (err === 'notBuildable' || err === 'occupied') continue;
          o.poly(diamond(x, y, x + 1, y + 1)).stroke({ width: 1, color: PALETTE.valid, alpha: 0.35 });
        }
      }
    } else if (selection?.kind === 'place' || (armed && !selection)) {
    // While a gun is picked for building, show where it can stand.
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
      const b = game.building(selection.what);
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
    } else if (selection?.kind === 'trap') {
      const tr = game.trapById(selection.id);
      if (tr) o.poly(diamond(tr.cx, tr.cy, tr.cx + 1, tr.cy + 1)).stroke({ width: 2.5, color: PALETTE.hover, alpha: 0.9 });
    }
  }

  /** Traps: stand-in drawings until they have art; a spent one is faded; tar shows its patch (alight when burning). */
  private drawTraps(): void {
    const g = this.trapLayer;
    g.clear();
    for (const tr of this.game.traps) {
      const x = isoX(tr.x, tr.y);
      const y = isoY(tr.x, tr.y);
      const a = tr.armed ? 1 : 0.45;
      if (tr.patch > 0) {
        const rx = (((TRAPS.tar.radius ?? 1) * TILE_W) / Math.SQRT2) * Math.min(1, 0.4 + tr.patch);
        g.ellipse(x, y, rx, rx / 2).fill({ color: 0x15110c, alpha: 0.7 });
        if (tr.burning > 0) {
          const f = 0.8 + 0.2 * Math.sin(this.game.time * 25 + tr.id);
          g.ellipse(x, y - 2, rx * 0.85 * f, (rx / 2) * 0.85 * f).fill({ color: 0xff7a22, alpha: 0.45 });
          g.ellipse(x, y - 3, rx * 0.5 * f, (rx / 4) * f).fill({ color: 0xffd060, alpha: 0.5 });
        }
      }
      switch (tr.kind) {
        case 'mine':
          g.ellipse(x, y, 9, 4.5).fill({ color: 0x3a3a30, alpha: a }).stroke({ width: 1, color: 0x1c1c16, alpha: a });
          g.circle(x, y - 2, 2).fill({ color: tr.armed ? 0xc23a2a : 0x555555, alpha: a });
          break;
        case 'pit':
          g.poly(diamond(tr.cx + 0.12, tr.cy + 0.12, tr.cx + 0.88, tr.cy + 0.88)).fill({ color: 0x2a2116, alpha: 0.9 * a });
          for (let i = -1; i <= 1; i++) g.moveTo(x + i * 7, y + 2).lineTo(x + i * 7, y - 6).stroke({ width: 2, color: 0x9a7a4a, alpha: a });
          break;
        case 'leg':
          g.ellipse(x, y, 10, 5).stroke({ width: 2, color: 0x6c7076, alpha: a });
          for (let i = -2; i <= 2; i++) g.moveTo(x + i * 4, y - 3).lineTo(x + i * 4, y + 3).stroke({ width: 1, color: 0x9ca0a6, alpha: a });
          break;
        case 'tar':
          if (tr.armed) {
            g.ellipse(x, y, 7, 3.5).fill({ color: 0x000000, alpha: 0.25 });
            g.roundRect(x - 6, y - 15, 12, 15, 3).fill({ color: 0x5a3c22 }).stroke({ width: 1, color: 0x2a1a0e });
            g.moveTo(x - 6, y - 11).lineTo(x + 6, y - 11).moveTo(x - 6, y - 4).lineTo(x + 6, y - 4).stroke({ width: 1, color: 0x2a2a2a });
          } else if (tr.patch <= 0) g.ellipse(x, y, 8, 4).fill({ color: 0x15110c, alpha: 0.35 });
          break;
      }
    }
  }

  /** Height flyers are drawn at, in tiles: the airship's own when its art is in. */
  private flyHeight(): number {
    const m = this.art?.manifest.enemies?.drone?.flightHeightM;
    return m ? m / METRES_PER_TILE : FLY_HEIGHT;
  }

  /**
   * Put a round's rendered picture at a point of its flight: the frame for its
   * heading (bolts) or the next tumbling frame (stones). False while the art
   * is not loaded, so the caller draws the stand-in.
   */
  private drawRound(id: number, o: ShotOrigin, gx: number, gy: number, h: number, heading: number): boolean {
    const r = o.round;
    if (!r || !this.art) return false;
    const n = r.def.headings ? frameForAim(heading, r.def.frames) : Math.floor((o.age - o.delay) * r.def.fps) % r.def.frames;
    const tex = this.art.sheetTexture(r.sheet, `${r.animation}_${String(n).padStart(2, '0')}`);
    if (!tex) return false;
    let sprite = this.roundSprites.get(id);
    if (!sprite) {
      sprite = new Sprite();
      sprite.anchor.set(0.5);
      sprite.scale.set(this.artScale());
      this.rounds.addChild(sprite);
      this.roundSprites.set(id, sprite);
    }
    sprite.texture = tex;
    sprite.position.set(isoX(gx, gy), isoY(gx, gy, h));
    return true;
  }

  private drawShots(alpha: number, dt: number): void {
    const g = this.shots;
    g.clear();
    const live = new Set<number>();
    for (const p of this.game.projectiles) {
      live.add(p.id);
      const o = this.shotOrigins.get(p.id) ?? { dx: 0, dy: 0, h: 0.3, delay: 0, age: 0, t0: 0 };
      const st = p.pt + (p.t - p.pt) * alpha;
      // A round still in the sling: wait for the arm, then cover the rest of the flight in the time left.
      o.age += dt;
      if (o.age < o.delay) {
        o.t0 = st;
        continue;
      }
      const t = o.t0 > 0 ? Math.max(0, (st - o.t0) / (1 - o.t0)) : st;
      // The simulation fires from the gun's centre; visibly the round leaves the muzzle.
      let gx: number;
      let gy: number;
      if (o.t0 > 0) {
        gx = p.ox + (p.tx - p.ox) * t + o.dx * (1 - t);
        gy = p.oy + (p.ty - p.oy) * t + o.dy * (1 - t);
      } else {
        gx = p.px + (p.x - p.px) * alpha + o.dx * (1 - t);
        gy = p.py + (p.y - p.py) * alpha + o.dy * (1 - t);
      }
      if (p.kind === 'shell') {
        const lob = Math.hypot(p.tx - p.ox, p.ty - p.oy) * 0.22;
        const h = o.h + (0 - o.h) * t + 4 * lob * t * (1 - t);
        g.ellipse(isoX(gx, gy), isoY(gx, gy), 3.5, 1.75).fill({ color: 0x000000, alpha: 0.22 });
        if (!this.drawRound(p.id, o, gx, gy, h, Math.atan2(p.ty - p.oy, p.tx - p.ox))) g.circle(isoX(gx, gy), isoY(gx, gy, h), 2.6).fill(PALETTE.shell);
      } else {
        // Rounds at a flyer climb to it.
        const hit = this.game.enemies.find((e) => e.id === p.targetId)?.air ? this.flyHeight() : HIT_HEIGHT;
        const h = o.h + (hit - o.h) * t;
        const x = isoX(gx, gy);
        const y = isoY(gx, gy, h);
        const dx = isoX(p.tx, p.ty) - x;
        const dy = isoY(p.tx, p.ty, hit) - y;
        const d = Math.hypot(dx, dy) || 1;
        if (o.round) {
          g.ellipse(isoX(gx, gy), isoY(gx, gy), 4, 2).fill({ color: 0x000000, alpha: 0.25 });
          if (this.drawRound(p.id, o, gx, gy, h, Math.atan2(p.ty - gy, p.tx - gx))) continue;
        }
        const ux = dx / d;
        const uy = dy / d;
        if (p.kind === 'rocket') {
          // A firework: a sparking trail behind a bright head.
          g.moveTo(x - ux * 18, y - uy * 18).lineTo(x, y).stroke({ width: 3, color: 0xff9a3c, alpha: 0.55, cap: 'round' });
          g.circle(x, y, 2.4).fill({ color: 0xfff1b0, alpha: 0.95 });
        } else if (p.kind === 'disc') {
          g.ellipse(isoX(gx, gy), isoY(gx, gy), 4, 2).fill({ color: 0x000000, alpha: 0.25 });
          g.ellipse(x, y, 5, 2.5).fill({ color: 0x9aa39a }).stroke({ width: 1, color: 0x3c4430 });
        } else if (p.kind === 'dart') {
          g.moveTo(x - ux * 5, y - uy * 5).lineTo(x, y).stroke({ width: 1.2, color: 0xe8d27a, alpha: 0.95, cap: 'round' });
        } else if (p.hook) {
          // Harpoon: a pale line trailing back to the gun.
          const tw = this.game.towerById(p.towerId);
          if (tw) g.moveTo(isoX(tw.x, tw.y), isoY(tw.x, tw.y, o.h)).lineTo(x, y).stroke({ width: 1, color: 0xdfe6e0, alpha: 0.5 });
          g.moveTo(x - ux * 12, y - uy * 12).lineTo(x, y).stroke({ width: 2.5, color: 0xcfd6d0, alpha: 0.95, cap: 'round' });
        } else {
          const len = Math.min(d, 16);
          g.moveTo(x - ux * len, y - uy * len).lineTo(x, y).stroke({ width: 2, color: PALETTE.tracer, alpha: 0.9, cap: 'round' });
        }
      }
    }
    for (const [id, sprite] of this.roundSprites) {
      if (live.has(id)) continue;
      sprite.destroy();
      this.roundSprites.delete(id);
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
      if (t.def === 'glass') {
        // Devil's glass: a thin, hard beam of sunlight that sharpens as it focuses.
        const focus = Math.min(1, t.heat / ((TOWERS.glass as TowerDef).focus || 0.5));
        const bx0 = isoX(mx, my);
        const by0 = isoY(mx, my, mh);
        const bx1 = isoX(target.x, target.y);
        const by1 = isoY(target.x, target.y, target.air ? this.flyHeight() : HIT_HEIGHT);
        g.moveTo(bx0, by0).lineTo(bx1, by1).stroke({ width: 6 * (1.4 - focus), color: 0xfff3c0, alpha: 0.25 * focus, cap: 'round' });
        g.moveTo(bx0, by0).lineTo(bx1, by1).stroke({ width: 1.6, color: 0xffffff, alpha: 0.5 + 0.5 * focus, cap: 'round' });
        g.circle(bx1, by1, 2 + 4 * focus).fill({ color: 0xfff3c0, alpha: 0.7 * focus });
        continue;
      }
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

    // Dazzle lamp: the lit cone on the ground fades out quickly.
    this.flashes = this.flashes.filter((f) => {
      f.age += dt;
      const k = f.age / FLASH_LIFE;
      if (k >= 1) return false;
      const steps = 10;
      g.moveTo(isoX(f.x, f.y), isoY(f.x, f.y));
      for (let i = 0; i <= steps; i++) {
        const a = f.aim - f.cone + (2 * f.cone * i) / steps;
        g.lineTo(isoX(f.x + Math.cos(a) * f.range, f.y + Math.sin(a) * f.range), isoY(f.x + Math.cos(a) * f.range, f.y + Math.sin(a) * f.range));
      }
      g.closePath().fill({ color: 0xfffbe0, alpha: (f.big ? 0.55 : 0.35) * (1 - k) });
      return true;
    });

    // Ricochet: a short grey streak along each glance.
    this.glances = this.glances.filter((r) => {
      r.age += dt;
      const k = r.age / GLANCE_LIFE;
      if (k >= 1) return false;
      g.moveTo(isoX(r.x1, r.y1), isoY(r.x1, r.y1, HIT_HEIGHT)).lineTo(isoX(r.x2, r.y2), isoY(r.x2, r.y2, HIT_HEIGHT)).stroke({ width: 2, color: 0xc8cfc8, alpha: 0.8 * (1 - k), cap: 'round' });
      return true;
    });

    // Stunned enemies: a small ring of light above them.
    for (const e of this.game.enemies) {
      if (!e.alive || e.stun <= 0) continue;
      const v = this.enemyViews.get(e.id);
      const ex = v?.gx ?? e.x;
      const ey = v?.gy ?? e.y;
      const h = (e.air ? this.flyHeight() : HIT_HEIGHT) + 0.5;
      const spin = this.game.time * 6 + e.id;
      for (let i = 0; i < 3; i++) {
        const a = spin + (i * 2 * Math.PI) / 3;
        g.circle(isoX(ex, ey) + Math.cos(a) * 6, isoY(ex, ey, h) + Math.sin(a) * 2.5, 1.6).fill({ color: 0xfff1a0, alpha: 0.9 });
      }
    }

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
    this.syncRaid();
    this.drawOverlay(selection, armed);
    this.drawTraps();
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
