/** Finger travel in CSS pixels before a touch counts as a drag instead of a tap. */
const TAP_SLOP = 8;
/** How fast a flick slows down: share of speed kept per millisecond. */
const FRICTION = 0.995;

export interface PanZoomOptions {
  minScale?: number;
  maxScale?: number;
}

/**
 * Moves and scales a page of HTML inside a fixed viewport, like a map: one
 * finger (or the mouse) drags it and a flick glides on, two fingers pinch-zoom
 * about their middle, the wheel zooms about the pointer (a trackpad's
 * two-finger scroll pans). A press that does not move stays a tap, so buttons
 * on the page keep working; the click that ends a drag is swallowed.
 */
export class PanZoom {
  /** Screen = t + k · page, in CSS pixels from the viewport's top-left. */
  private k = 1;
  private tx = 0;
  private ty = 0;
  private readonly pointers = new Map<number, { x: number; y: number }>();
  private moved = 0;
  private dragging = false;
  private swallowClick = false;
  private vx = 0;
  private vy = 0;
  private lastMove = 0;
  private glide = 0;
  private readonly minScale: number;
  private readonly maxScale: number;
  /** Called after every move or zoom. */
  onChange: (() => void) | null = null;

  constructor(
    private readonly viewport: HTMLElement,
    private readonly content: HTMLElement,
    opts: PanZoomOptions = {},
  ) {
    this.minScale = opts.minScale ?? 0.6;
    this.maxScale = opts.maxScale ?? 2.4;
    content.style.transformOrigin = '0 0';
    viewport.addEventListener('pointerdown', (ev) => this.down(ev));
    viewport.addEventListener('pointermove', (ev) => this.move(ev));
    viewport.addEventListener('pointerup', (ev) => this.up(ev));
    viewport.addEventListener('pointercancel', (ev) => this.up(ev));
    // Taking the capture from the element under a finger fires this on that element too (it bubbles): only ours counts.
    viewport.addEventListener('lostpointercapture', (ev) => {
      if (ev.target === viewport) this.up(ev);
    });
    viewport.addEventListener('wheel', (ev) => this.wheel(ev), { passive: false });
    // The click that ends a drag must not press the button under the finger.
    viewport.addEventListener(
      'click',
      (ev) => {
        if (!this.swallowClick) return;
        this.swallowClick = false;
        ev.stopPropagation();
        ev.preventDefault();
      },
      true,
    );
  }

  get scale(): number {
    return this.k;
  }

  /** Back to the top, at the scale that fits the page's width. */
  reset(): void {
    this.stopGlide();
    this.k = 1;
    this.tx = 0;
    this.ty = 0;
    this.apply(false);
  }

  /** Keep the page in view after the viewport or the page changed size. */
  refit(): void {
    this.apply(false);
  }

  /** Bring a point of the page (page pixels from its top) to `margin` below the viewport's top. */
  showY(pageY: number, margin = 12, smooth = true): void {
    this.stopGlide();
    this.ty = margin - pageY * this.k;
    this.apply(smooth);
  }

  /** Move the page by a screen offset. */
  panBy(dx: number, dy: number): void {
    this.tx += dx;
    this.ty += dy;
    this.apply(false);
  }

  /** Zoom by `factor` keeping the screen point (x, y), relative to the viewport, still. */
  zoomAt(x: number, y: number, factor: number): void {
    const k = Math.min(this.maxScale, Math.max(this.minScale, this.k * factor));
    const f = k / this.k;
    this.tx = x - (x - this.tx) * f;
    this.ty = y - (y - this.ty) * f;
    this.k = k;
    this.apply(false);
  }

  // ------------------------------------------------------------- input

  private local(ev: { clientX: number; clientY: number }): { x: number; y: number } {
    const r = this.viewport.getBoundingClientRect();
    return { x: ev.clientX - r.left, y: ev.clientY - r.top };
  }

  private down(ev: PointerEvent): void {
    if (ev.pointerType === 'mouse' && ev.button !== 0) return;
    this.stopGlide();
    if (this.pointers.size === 0) {
      this.moved = 0;
      this.dragging = false;
      this.swallowClick = false;
    }
    this.pointers.set(ev.pointerId, this.local(ev));
    this.vx = this.vy = 0;
    this.lastMove = ev.timeStamp;
    // A second finger: this is a pinch, never a tap.
    if (this.pointers.size > 1) this.startDrag(ev);
  }

  /** From here on the gesture moves the page; capture keeps it ours even off the viewport. */
  private startDrag(ev: PointerEvent): void {
    this.dragging = true;
    this.swallowClick = true;
    for (const id of this.pointers.keys()) {
      try {
        this.viewport.setPointerCapture(id);
      } catch {
        // The pointer is gone already.
      }
    }
    void ev;
  }

  private spread(): { d: number; cx: number; cy: number } {
    const [a, b] = [...this.pointers.values()];
    return { d: Math.hypot(a!.x - b!.x, a!.y - b!.y), cx: (a!.x + b!.x) / 2, cy: (a!.y + b!.y) / 2 };
  }

  private move(ev: PointerEvent): void {
    const p = this.pointers.get(ev.pointerId);
    if (!p) return;
    const q = this.local(ev);
    if (this.pointers.size === 1) {
      const dx = q.x - p.x;
      const dy = q.y - p.y;
      if (!this.dragging) {
        this.moved += Math.hypot(dx, dy);
        if (this.moved <= TAP_SLOP) return;
        this.startDrag(ev);
      }
      p.x = q.x;
      p.y = q.y;
      const dt = Math.max(1, ev.timeStamp - this.lastMove);
      this.lastMove = ev.timeStamp;
      // Smoothed speed, for the glide after a flick.
      this.vx = 0.7 * (dx / dt) + 0.3 * this.vx;
      this.vy = 0.7 * (dy / dt) + 0.3 * this.vy;
      this.panBy(dx, dy);
      return;
    }
    if (this.pointers.size === 2) {
      const a = this.spread();
      p.x = q.x;
      p.y = q.y;
      const b = this.spread();
      this.tx += b.cx - a.cx;
      this.ty += b.cy - a.cy;
      if (a.d > 0) this.zoomAt(b.cx, b.cy, b.d / a.d);
      else this.apply(false);
      this.vx = this.vy = 0;
    }
  }

  private up(ev: PointerEvent): void {
    if (!this.pointers.delete(ev.pointerId)) return;
    if (this.pointers.size === 1) {
      // One finger left after a pinch: it carries on dragging from where it is.
      this.vx = this.vy = 0;
      return;
    }
    if (this.pointers.size === 0 && this.dragging && ev.timeStamp - this.lastMove < 80) this.startGlide();
  }

  private wheel(ev: WheelEvent): void {
    ev.preventDefault();
    this.stopGlide();
    const q = this.local(ev);
    const lines = ev.deltaMode === 1 ? 16 : ev.deltaMode === 2 ? this.viewport.clientHeight : 1;
    const dx = ev.deltaX * lines;
    const dy = ev.deltaY * lines;
    // A pinch on a trackpad comes as a wheel with ctrl; a mouse wheel moves in whole notches.
    const mouseWheel = ev.deltaMode !== 0 || (dx === 0 && Math.abs(dy) >= 50 && Number.isInteger(dy));
    if (ev.ctrlKey || mouseWheel) this.zoomAt(q.x, q.y, Math.exp(-dy * (ev.ctrlKey ? 0.01 : 0.0015)));
    else this.panBy(-dx, -dy);
  }

  private startGlide(): void {
    let last = performance.now();
    const step = (now: number) => {
      const dt = Math.min(48, now - last);
      last = now;
      const keep = Math.pow(FRICTION, dt);
      this.vx *= keep;
      this.vy *= keep;
      if (Math.hypot(this.vx, this.vy) < 0.02) {
        this.glide = 0;
        return;
      }
      const before = [this.tx, this.ty];
      this.panBy(this.vx * dt, this.vy * dt);
      // Stopped by an edge.
      if (before[0] === this.tx) this.vx = 0;
      if (before[1] === this.ty) this.vy = 0;
      this.glide = requestAnimationFrame(step);
    };
    this.glide = requestAnimationFrame(step);
  }

  private stopGlide(): void {
    if (this.glide) cancelAnimationFrame(this.glide);
    this.glide = 0;
  }

  /** Keep the page inside the viewport (centred across when it is narrower) and draw it. */
  private apply(smooth: boolean): void {
    const vw = this.viewport.clientWidth;
    const vh = this.viewport.clientHeight;
    const w = this.content.offsetWidth * this.k;
    const h = this.content.offsetHeight * this.k;
    this.tx = w <= vw ? (vw - w) / 2 : Math.min(0, Math.max(vw - w, this.tx));
    this.ty = h <= vh ? 0 : Math.min(0, Math.max(vh - h, this.ty));
    this.content.style.transition = smooth ? 'transform 0.35s cubic-bezier(0.2, 0.7, 0.2, 1)' : '';
    this.content.style.transform = `translate(${this.tx.toFixed(1)}px, ${this.ty.toFixed(1)}px) scale(${this.k.toFixed(4)})`;
    this.onChange?.();
  }
}
