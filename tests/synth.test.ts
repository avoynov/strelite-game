import { describe, expect, it } from 'vitest';
import { MUSIC_BAR_SAMPLES, MUSIC_BARS, musicBar, SAMPLE_RATE, SOUND_NAMES, synth } from '../src/audio/synth';

describe('synthesised sounds', () => {
  it('every sound is finite, audible, never clips and stays short', () => {
    for (const name of SOUND_NAMES) {
      const s = synth(name, 1);
      let peak = 0;
      for (const v of s) {
        expect(Number.isFinite(v), name).toBe(true);
        peak = Math.max(peak, Math.abs(v));
      }
      expect(peak, name).toBeGreaterThan(0.2);
      expect(peak, name).toBeLessThanOrEqual(1);
      expect(s.length / SAMPLE_RATE, name).toBeLessThan(3);
    }
  });

  it('takes of one sound differ, and the same take is always the same', () => {
    expect(synth('zis3', 1)).toEqual(synth('zis3', 1));
    expect(synth('zis3', 1)).not.toEqual(synth('zis3', 2));
  });

  it('music bars are finite and ring out a little past the bar', () => {
    for (let b = 0; b < MUSIC_BARS; b++) {
      const bar = musicBar(b);
      expect(bar.length).toBeGreaterThan(MUSIC_BAR_SAMPLES);
      expect(bar.every((v) => Number.isFinite(v))).toBe(true);
    }
  });
});
