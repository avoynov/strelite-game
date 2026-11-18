export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * Pan and zoom of the board: screen = world * scale + (x, y). The most
 * zoomed-out view fits the whole map between the HUD bars; zooming in is for
 * looking at the guns up close. The middle of the view can never leave the map.
 */
export class Camera {
  scale = 1;
  x = 0;
  y = 0;
  minScale = 1;
  maxScale = 4;
  private bounds: Rect = { x: 0, y: 0, w: 1, h: 1 };
  private view: Rect = { x: 0, y: 0, w: 1, h: 1 };

  /**
   * @param bounds   the map in world pixels
   * @param view     the free part of the screen (between the HUD bars)
   * @param maxScale closest zoom
   */
  configure(bounds: Rect, view: Rect, maxScale: number): void {
    const first = this.bounds.w === 1 && this.view.w === 1;
    const wasFit = first || this.scale <= this.minScale * 1.001;
    this.bounds = bounds;
    this.view = view;
    this.minScale = Math.min(view.w / bounds.w, view.h / bounds.h);
    this.maxScale = Math.max(maxScale, this.minScale);
    if (wasFit) {
      this.scale = this.minScale;
      this.x = view.x + view.w / 2 - (bounds.x + bounds.w / 2) * this.scale;
      this.y = view.y + view.h / 2 - (bounds.y + bounds.h / 2) * this.scale;
    }
    this.clamp();
  }

  /** Zoom to `scale` (within limits) with the world point (wx, wy) in the middle of the view, as far as the map allows. */
  focus(wx: number, wy: number, scale: number): void {
    this.scale = Math.min(this.maxScale, Math.max(this.minScale, scale));
    this.x = this.view.x + this.view.w / 2 - wx * this.scale;
    this.y = this.view.y + this.view.h / 2 - wy * this.scale;
    this.clamp();
  }

  toWorld(sx: number, sy: number): { x: number; y: number } {
    return { x: (sx - this.x) / this.scale, y: (sy - this.y) / this.scale };
  }

  toScreen(wx: number, wy: number): { x: number; y: number } {
    return { x: wx * this.scale + this.x, y: wy * this.scale + this.y };
  }

  panBy(dx: number, dy: number): void {
    this.x += dx;
    this.y += dy;
    this.clamp();
  }

  /** Zoom by `factor`, keeping the world point under screen point (sx, sy) in place. */
  zoomAt(sx: number, sy: number, factor: number): void {
    const next = Math.min(this.maxScale, Math.max(this.minScale, this.scale * factor));
    const w = this.toWorld(sx, sy);
    this.scale = next;
    this.x = sx - w.x * next;
    this.y = sy - w.y * next;
    this.clamp();
  }

  private clamp(): void {
    const { bounds: b, view: v } = this;
    const cx = v.x + v.w / 2;
    const cy = v.y + v.h / 2;
    // World point under the middle of the view must stay inside the map.
    const wx = Math.min(b.x + b.w, Math.max(b.x, (cx - this.x) / this.scale));
    const wy = Math.min(b.y + b.h, Math.max(b.y, (cy - this.y) / this.scale));
    // Fully zoomed out, the map is simply centred.
    const t = this.maxScale > this.minScale ? Math.min(1, (this.scale - this.minScale) / (this.minScale * 0.25)) : 0;
    const mx = b.x + b.w / 2;
    const my = b.y + b.h / 2;
    this.x = cx - (mx + (wx - mx) * t) * this.scale;
    this.y = cy - (my + (wy - my) * t) * this.scale;
  }
}
