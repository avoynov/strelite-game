import { Container, Sprite } from 'pixi.js';
import { depth, isoX, isoY } from './iso';
import type { TowerArt } from './towers/spriteTowerView';
import { frameName, type EffectArtDef } from './towers/towerArt';

interface Playing {
  sprite: Sprite;
  def: EffectArtDef;
  age: number;
  /** Height above the ground in world pixels, rising by `lift` per second. */
  lift: number;
}

export interface EffectOptions {
  /** Height above the ground in world pixels. */
  height?: number;
  /** Size relative to real scale. */
  size?: number;
  /** Screen rotation in radians (the muzzle flash points along +x). */
  rotation?: number;
  /** Added to the draw order, so the effect sorts with the right objects. */
  zBias?: number;
  /** World pixels per second the effect drifts upward. */
  lift?: number;
  /** Stretch the sprite along its own x axis to this many world pixels (beams and jets). */
  lengthPx?: number;
}

interface Held {
  sprite: Sprite;
  def: EffectArtDef;
  age: number;
  /** Set each frame the owner still wants it; dropped otherwise. */
  live: boolean;
}

/**
 * Plays the rendered one-shot animations (muzzle flash, muzzle smoke, shell
 * burst) on the board's object layer, sorted with guns and enemies.
 */
export class Effects {
  private playing: Playing[] = [];
  private held = new Map<string, Held>();

  constructor(
    private readonly art: TowerArt,
    private readonly layer: Container,
    /** Sprite scale that puts @1x art at real size on the board. */
    private readonly scale: number,
  ) {}

  has(name: string): boolean {
    return !!this.art.manifest.effects?.[name];
  }

  /** Start effect `name` at a ground point (grid cells). Does nothing until its sheet is loaded. */
  play(name: string, gx: number, gy: number, opts: EffectOptions = {}): void {
    const def = this.art.manifest.effects?.[name];
    if (!def) return;
    const tex = this.art.sheetTexture(def.sheet, frameName(def.frames, 0));
    if (!tex) return;
    const sprite = new Sprite(tex);
    if (def.blend === 'add') sprite.blendMode = 'add';
    this.place(sprite, def, gx, gy, opts);
    this.layer.addChild(sprite);
    this.playing.push({ sprite, def, age: 0, lift: opts.lift ?? 0 });
  }

  /**
   * Keep looping effect `name` (a flame jet, a charge glow) showing under `key`
   * for this frame. Call every frame it should stay; `update` drops the ones
   * not held since. Returns false while the art is missing or not loaded.
   */
  hold(key: string, name: string, gx: number, gy: number, opts: EffectOptions = {}): boolean {
    const def = this.art.manifest.effects?.[name];
    if (!def) return false;
    let h = this.held.get(key);
    if (!h || h.def !== def) {
      const tex = this.art.sheetTexture(def.sheet, frameName(def.frames, 0));
      if (!tex) return false;
      h?.sprite.destroy();
      const sprite = new Sprite(tex);
      if (def.blend === 'add') sprite.blendMode = 'add';
      this.layer.addChild(sprite);
      h = { sprite, def, age: 0, live: true };
      this.held.set(key, h);
    }
    h.live = true;
    this.place(h.sprite, def, gx, gy, opts);
    return true;
  }

  private place(sprite: Sprite, def: EffectArtDef, gx: number, gy: number, opts: EffectOptions): void {
    sprite.anchor.set(def.anchor[0], def.anchor[1]);
    const s = this.scale * (opts.size ?? 1);
    // Width from the texture's full frame, so trimmed frames keep the same reach.
    const sx = opts.lengthPx !== undefined ? opts.lengthPx / (sprite.texture.orig.width || 1) : s;
    sprite.scale.set(sx, s);
    sprite.rotation = opts.rotation ?? 0;
    sprite.position.set(isoX(gx, gy), isoY(gx, gy) - (opts.height ?? 0));
    sprite.zIndex = depth(gx, gy) + (opts.zBias ?? 0);
  }

  update(dt: number): void {
    this.playing = this.playing.filter((p) => {
      p.age += dt;
      const n = Math.floor(p.age * p.def.fps);
      if (n >= p.def.count) {
        p.sprite.destroy();
        return false;
      }
      const tex = this.art.sheetTexture(p.def.sheet, frameName(p.def.frames, n));
      if (tex) p.sprite.texture = tex;
      p.sprite.y -= p.lift * dt;
      return true;
    });
    for (const [key, h] of this.held) {
      if (!h.live) {
        h.sprite.destroy();
        this.held.delete(key);
        continue;
      }
      h.live = false;
      h.age += dt;
      const n = Math.floor(h.age * h.def.fps) % h.def.count;
      const tex = this.art.sheetTexture(h.def.sheet, frameName(h.def.frames, n));
      if (tex) h.sprite.texture = tex;
    }
  }

  destroy(): void {
    this.playing.forEach((p) => p.sprite.destroy());
    this.playing = [];
    this.held.forEach((h) => h.sprite.destroy());
    this.held.clear();
  }
}
