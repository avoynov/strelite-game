import type { Camera } from '../render/camera';

/** Finger travel in CSS pixels before a touch counts as a drag instead of a tap. */
const TAP_SLOP = 9;

/**
 * Touch and mouse control of the board: one finger drags the view, two fingers
 * pinch-zoom, the wheel zooms on a desktop, and a touch that does not move is a tap.
 */
export function attachGestures(el: HTMLElement, getCamera: () => Camera, onTap: (x: number, y: number) => void): void {
  const pointers = new Map<number, { x: number; y: number }>();
  let moved = 0;
  let multi = false;

  const spread = () => {
    const [a, b] = [...pointers.values()];
    return { d: Math.hypot(a!.x - b!.x, a!.y - b!.y), cx: (a!.x + b!.x) / 2, cy: (a!.y + b!.y) / 2 };
  };

  el.addEventListener('pointerdown', (ev) => {
    if (pointers.size === 0) {
      moved = 0;
      multi = false;
    }
    pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
    if (pointers.size > 1) multi = true;
    el.setPointerCapture(ev.pointerId);
  });

  el.addEventListener('pointermove', (ev) => {
    const p = pointers.get(ev.pointerId);
    if (!p) return;
    const cam = getCamera();
    if (pointers.size === 1) {
      const dx = ev.clientX - p.x;
      const dy = ev.clientY - p.y;
      const before = moved;
      moved += Math.hypot(dx, dy);
      p.x = ev.clientX;
      p.y = ev.clientY;
      if (moved > TAP_SLOP) cam.panBy(before > TAP_SLOP ? dx : 0, before > TAP_SLOP ? dy : 0);
      return;
    }
    if (pointers.size === 2) {
      const a = spread();
      p.x = ev.clientX;
      p.y = ev.clientY;
      const b = spread();
      cam.panBy(b.cx - a.cx, b.cy - a.cy);
      if (a.d > 0) cam.zoomAt(b.cx, b.cy, b.d / a.d);
    }
  });

  const end = (ev: PointerEvent, cancelled: boolean) => {
    if (!pointers.delete(ev.pointerId)) return;
    if (pointers.size === 0 && !cancelled && !multi && moved <= TAP_SLOP) onTap(ev.clientX, ev.clientY);
  };
  el.addEventListener('pointerup', (ev) => end(ev, false));
  el.addEventListener('pointercancel', (ev) => end(ev, true));

  el.addEventListener(
    'wheel',
    (ev) => {
      ev.preventDefault();
      getCamera().zoomAt(ev.clientX, ev.clientY, Math.exp(-ev.deltaY * 0.0015));
    },
    { passive: false },
  );
}
