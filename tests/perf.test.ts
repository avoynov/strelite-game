import { describe, expect, it } from 'vitest';
import { AUTO_STEPS, deviceStep, FrameWatch, qualityFor } from '../src/perf';

describe('quality fallback', () => {
  it('weak devices start lower', () => {
    expect(deviceStep({ hardwareConcurrency: 8, deviceMemory: 8 })).toBe(0);
    expect(deviceStep({ hardwareConcurrency: 4, deviceMemory: 8 })).toBe(1);
    expect(deviceStep({ hardwareConcurrency: 8, deviceMemory: 2 })).toBe(2);
    expect(deviceStep({})).toBe(0);
  });

  it('each auto step costs less than the one before', () => {
    for (let s = 1; s < AUTO_STEPS; s++) {
      const a = qualityFor('auto', s - 1, 3);
      const b = qualityFor('auto', s, 3);
      expect(b.resolution).toBeLessThanOrEqual(a.resolution);
    }
    expect(qualityFor('low', 0, 3)).toEqual(qualityFor('auto', AUTO_STEPS - 1, 3));
    expect(qualityFor('high', AUTO_STEPS - 1, 3).resolution).toBe(2);
  });

  it('steps down only after slow frames last a while, and ignores long stalls', () => {
    const w = new FrameWatch(40, 2, 2);
    let down = false;
    for (let i = 0; i < 60 * 10; i++) down ||= w.frame(1 / 60);
    expect(down).toBe(false);
    for (let i = 0; i < 20; i++) down ||= w.frame(2);
    expect(down).toBe(false);
    let at = -1;
    for (let i = 0; i < 25 * 10 && at < 0; i++) if (w.frame(1 / 25)) at = i;
    expect(at).toBeGreaterThan(25 * 3);
  });
});
