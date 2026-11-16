import { describe, expect, it } from 'vitest';
import { FixedStep } from '../src/sim/fixedStep';

describe('FixedStep', () => {
  it('runs the same number of steps regardless of frame size', () => {
    let a = 0;
    let b = 0;
    const la = new FixedStep(0.1, () => a++);
    const lb = new FixedStep(0.1, () => b++);
    for (let i = 0; i < 100; i++) la.advance(0.01);
    for (let i = 0; i < 10; i++) lb.advance(0.1);
    expect(Math.abs(a - b)).toBeLessThanOrEqual(1);
    expect(b).toBeGreaterThanOrEqual(9);
  });
  it('applies the speed multiplier and pause', () => {
    let n = 0;
    const l = new FixedStep(0.1, () => n++);
    l.speed = 2;
    l.advance(0.2);
    expect(n).toBe(4);
    l.paused = true;
    l.advance(0.2);
    expect(n).toBe(4);
  });
  it('returns interpolation alpha', () => {
    const l = new FixedStep(0.1, () => {});
    expect(l.advance(0.25)).toBeCloseTo(0.5);
  });
});
