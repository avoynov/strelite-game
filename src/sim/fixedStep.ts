/**
 * Runs a simulation at a fixed step regardless of frame rate. Rendering reads
 * `alpha` (0..1) to interpolate between the last two steps.
 */
export class FixedStep {
  private acc = 0;
  /** Simulation speed multiplier (1x, 2x, ...). */
  speed = 1;
  paused = false;

  constructor(
    readonly dt: number,
    private readonly stepFn: (dt: number) => void,
    /** Cap on real seconds consumed per frame, avoids a death spiral after a stall. */
    private readonly maxFrame = 0.25,
  ) {}

  /** Feed real elapsed seconds; returns the interpolation factor. */
  advance(frameSeconds: number): number {
    if (this.paused) return 1;
    this.acc += Math.min(frameSeconds, this.maxFrame) * this.speed;
    while (this.acc >= this.dt) {
      this.stepFn(this.dt);
      this.acc -= this.dt;
    }
    return this.acc / this.dt;
  }
}
