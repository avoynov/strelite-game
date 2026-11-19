/**
 * Graphics quality for weak phones. "auto" starts from what the device says
 * about itself and steps down while the game runs if frames are slow; the
 * player can also force high or low.
 */
export type QualityChoice = 'auto' | 'high' | 'low';

export interface Quality {
  /** Canvas pixels per CSS pixel. */
  resolution: number;
  /** Edge smoothing; costly on weak GPUs. Takes effect on the next start. */
  antialias: boolean;
  /** Load the sharp @2x atlases when zoomed in (twice the texture memory). */
  sharpArt: boolean;
  /** Frame cap; 0 = the display's own rate. */
  maxFps: number;
}

const CHOICE_KEY = 'strelite.quality';
/** Where auto ended up last time, so a weak phone starts low next time instead of stuttering first. */
const AUTO_KEY = 'strelite.quality.auto';

/** Auto steps, best first. */
export const AUTO_STEPS = 4;

export function readChoice(): QualityChoice {
  try {
    const v = localStorage.getItem(CHOICE_KEY);
    return v === 'high' || v === 'low' ? v : 'auto';
  } catch {
    return 'auto';
  }
}

export function saveChoice(c: QualityChoice): void {
  try {
    localStorage.setItem(CHOICE_KEY, c);
  } catch {
    // This visit only.
  }
}

function readAutoStep(): number | null {
  try {
    const v = localStorage.getItem(AUTO_KEY);
    if (v === null) return null;
    const n = Math.floor(Number(v));
    return n >= 0 && n < AUTO_STEPS ? n : null;
  } catch {
    return null;
  }
}

export function saveAutoStep(step: number): void {
  try {
    localStorage.setItem(AUTO_KEY, String(step));
  } catch {
    // This visit only.
  }
}

/** A guess at the device: few cores or little memory means a weak phone. */
export function deviceStep(nav: { hardwareConcurrency?: number; deviceMemory?: number } = navigator as never): number {
  const mem = nav.deviceMemory ?? 8;
  const cores = nav.hardwareConcurrency ?? 8;
  if (mem <= 2 || cores <= 2) return 2;
  if (mem <= 4 || cores <= 4) return 1;
  return 0;
}

/** The first auto step this start: last time's, or the device guess. */
export function startStep(): number {
  return readAutoStep() ?? deviceStep();
}

/** Settings for a step of auto (0 = best), or for a forced choice. */
export function qualityFor(choice: QualityChoice, step: number, dpr = window.devicePixelRatio || 1): Quality {
  if (choice === 'high') return { resolution: Math.min(dpr, 2), antialias: true, sharpArt: true, maxFps: 0 };
  if (choice === 'low') step = AUTO_STEPS - 1;
  switch (step) {
    case 0:
      return { resolution: Math.min(dpr, 2), antialias: true, sharpArt: true, maxFps: 0 };
    case 1:
      return { resolution: Math.min(dpr, 1.5), antialias: false, sharpArt: true, maxFps: 0 };
    case 2:
      return { resolution: Math.min(dpr, 1.25), antialias: false, sharpArt: false, maxFps: 0 };
    default:
      return { resolution: 1, antialias: false, sharpArt: false, maxFps: 30 };
  }
}

/**
 * Watches frame times during play. Reports `true` once frames have been slow
 * for a few seconds in a row (time to step down), never in the first seconds
 * after a change, and never while nothing moves.
 */
export class FrameWatch {
  private sum = 0;
  private frames = 0;
  private slowWindows = 0;
  private settle = 3;

  constructor(
    /** Below this many frames a second counts as slow. */
    private readonly minFps = 40,
    /** Seconds per measuring window. */
    private readonly window = 2,
    /** Slow windows in a row before stepping down. */
    private readonly needed = 2,
  ) {}

  /** Start over (after a quality change, or after a pause). */
  reset(settleSeconds = 3): void {
    this.sum = 0;
    this.frames = 0;
    this.slowWindows = 0;
    this.settle = settleSeconds;
  }

  /** Feed one frame's real duration in seconds; true when quality should step down. */
  frame(seconds: number): boolean {
    // A long gap (tab switch, GC pause) says nothing about steady speed.
    if (seconds > 0.5) return false;
    if (this.settle > 0) {
      this.settle -= seconds;
      return false;
    }
    this.sum += seconds;
    this.frames++;
    if (this.sum < this.window) return false;
    const fps = this.frames / this.sum;
    this.sum = 0;
    this.frames = 0;
    this.slowWindows = fps < this.minFps ? this.slowWindows + 1 : 0;
    if (this.slowWindows >= this.needed) {
      this.reset();
      return true;
    }
    return false;
  }
}
