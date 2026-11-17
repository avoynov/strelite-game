import { Assets, Container, Graphics, Matrix, Text, TilingSprite, type Texture } from 'pixi.js';
import { ENEMIES, METRES_PER_TILE, TOWERS, type TowerId } from '../sim/content';
import type { Game, Tower } from '../sim/game';
import { Camera, type Rect } from './camera';
import { PlaceholderEnemyView } from './enemyView';
import { diamond, isoX, isoY, project, TILE_W, unproject } from './iso';
import { PALETTE } from './palette';
import { roadCentreLines, stripOutline } from './road';
import { PlaceholderTowerView } from './towers/placeholderTowerView';
import { SpriteTowerView, type Density, type TowerArt } from './towers/spriteTowerView';
import { spriteScale } from './towers/towerArt';
import type { TowerView } from './towers/towerView';

export type Selection =
  /** An existing gun, by id. */
  | { kind: 'tower'; id: number }
  /** A gun about to be built, footprint's top-left cell at (cx, cy). */
  | { kind: 'place'; def: TowerId; cx: number; cy: number };

type PixiTowerView = TowerView & { node: Container };

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
const BURST_LIFE = 0.45;
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
  private readonly towerViews = new Map<number, { view: PixiTowerView; level: number }>();
  private readonly enemyViews = new Map<number, PlaceholderEnemyView>();
  private readonly shotOrigins = new Map<number, ShotOrigin>();
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
  }

  destroy(): void {
    this.offArt?.();
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
  }

  onBurst(gx: number, gy: number, radius: number): void {
    this.bursts.push({ gx, gy, radius, age: 0 });
  }

  // ---- per frame -----------------------------------------------------------

  private createTowerView(t: Tower): PixiTowerView {
    const spec = { tower: t.def, level: t.level + 1, size: t.size };
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
      let view = this.enemyViews.get(e.id);
      if (!view) {
        view = new PlaceholderEnemyView(e.def, ENEMIES[e.def].radius);
        this.enemyViews.set(e.id, view);
        this.objects.addChild(view.node);
      }
      view.place(e.px + (e.x - e.px) * alpha, e.py + (e.y - e.py) * alpha);
      view.setHeading(e.heading);
      view.setHealth(e.hp / e.maxHp);
    }
    for (const [id, view] of this.enemyViews) {
      if (seen.has(id)) continue;
      view.destroy();
      this.enemyViews.delete(id);
    }
  }

  private drawOverlay(selection: Selection | null, armed: TowerId | null): void {
    const o = this.overlay;
    const game = this.game;
    const { grid } = game.map;
    // Redraw only when something it shows has changed.
    const key = JSON.stringify([selection, armed, game.towers.map((t) => [t.id, t.level])]);
    if (key === this.overlayKey) return;
    this.overlayKey = key;
    o.clear();

    // While a gun is picked for building, show where it can stand.
    if (selection?.kind === 'place' || (armed && !selection)) {
      for (let y = 0; y < grid.rows; y++) {
        for (let x = 0; x < grid.cols; x++) {
          if (grid.get(x, y) !== 'build' || game.towerAt(x, y)) continue;
          o.poly(diamond(x, y, x + 1, y + 1)).stroke({ width: 1, color: PALETTE.gridLine, alpha: 0.22 });
        }
      }
    }

    const range = (gx: number, gy: number, radius: number, minRadius = 0) => {
      const rx = (radius * TILE_W) / Math.SQRT2;
      o.ellipse(isoX(gx, gy), isoY(gx, gy), rx, rx / 2).fill({ color: PALETTE.range, alpha: 0.1 }).stroke({ width: 2, color: PALETTE.range, alpha: 0.6 });
      if (minRadius > 0) {
        const mr = (minRadius * TILE_W) / Math.SQRT2;
        o.ellipse(isoX(gx, gy), isoY(gx, gy), mr, mr / 2).stroke({ width: 1.5, color: PALETTE.invalid, alpha: 0.5 });
      }
    };

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
        const h = o.h + (HIT_HEIGHT - o.h) * t;
        const x = isoX(gx, gy);
        const y = isoY(gx, gy, h);
        const dx = isoX(p.tx, p.ty) - x;
        const dy = isoY(p.tx, p.ty, HIT_HEIGHT) - y;
        const d = Math.hypot(dx, dy) || 1;
        const len = Math.min(d, 16);
        g.moveTo(x - (dx / d) * len, y - (dy / d) * len).lineTo(x, y).stroke({ width: 2, color: PALETTE.tracer, alpha: 0.9, cap: 'round' });
      }
    }
    for (const id of this.shotOrigins.keys()) if (!live.has(id)) this.shotOrigins.delete(id);

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
  render(alpha: number, selection: Selection | null, armed: TowerId | null, dtSeconds: number): void {
    this.applyCamera();
    this.syncTowers(dtSeconds);
    this.syncEnemies(alpha);
    this.drawOverlay(selection, armed);
    this.drawShots(alpha, dtSeconds);

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
