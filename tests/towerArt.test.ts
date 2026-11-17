import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { TOWERS } from '../src/sim/content';
import { aimFrameName, frameForAim, spriteScale, stickyFrameForAim, type TowerArtManifest } from '../src/render/towers/towerArt';

const ART = fileURLToPath(new URL('../public/art', import.meta.url));

describe('tower art', () => {
  it('maps the simulation aim angle to one of 32 frames', () => {
    expect(frameForAim(0, 32)).toBe(0);
    expect(frameForAim(Math.PI / 2, 32)).toBe(8);
    expect(frameForAim(-Math.PI / 2, 32)).toBe(24);
    expect(frameForAim(Math.PI, 32)).toBe(16);
    expect(frameForAim(-Math.PI, 32)).toBe(16);
    expect(frameForAim(2 * Math.PI - 0.01, 32)).toBe(0);
    expect(frameForAim(0.11, 32)).toBe(1);
  });

  it('scales a sprite so that a tile is the stated number of metres', () => {
    // 12 m tile, 48 px diamond, 16 px per metre: 12 * √2 * 16 px of art span one tile width
    expect(spriteScale(48, 12, 16)).toBeCloseTo(48 / (12 * Math.SQRT2 * 16));
  });

  it('holds the current frame until the aim is clearly past the boundary', () => {
    const step = (2 * Math.PI) / 32;
    expect(stickyFrameForAim(0.55 * step, 32, 0)).toBe(0); // just over the line: stay
    expect(stickyFrameForAim(0.7 * step, 32, 0)).toBe(1);
    expect(stickyFrameForAim(0.45 * step, 32, 1)).toBe(1); // and the same on the way back
    expect(stickyFrameForAim(0.3 * step, 32, 1)).toBe(0);
    expect(stickyFrameForAim(-0.55 * step, 32, 0)).toBe(0); // across the 31 -> 0 wrap
    expect(stickyFrameForAim(-0.7 * step, 32, 0)).toBe(31);
    expect(stickyFrameForAim(Math.PI, 32, 3)).toBe(16);
  });

  // The art arrives level by level, so check whatever the manifest lists so far.
  it.skipIf(!existsSync(join(ART, 'towers.json')))('ships every frame the manifest promises', () => {
    const manifest = JSON.parse(readFileSync(join(ART, 'towers.json'), 'utf8')) as TowerArtManifest;
    expect(manifest.directions).toBe(32);
    for (const [id, tower] of Object.entries(manifest.towers)) {
      expect(Object.keys(TOWERS), `the game has no tower "${id}"`).toContain(id);
      expect(tower.levels.length, id).toBeGreaterThan(0);
      for (const lv of tower.levels) {
        expect(lv.muzzlePx.length).toBe(manifest.directions);
        expect(lv.muzzleM.length).toBe(manifest.directions);
        for (const density of ['@1x', '@2x']) {
          const sheet = JSON.parse(readFileSync(join(ART, `${lv.sheet}${density}.json`), 'utf8')) as {
            frames: Record<string, unknown>;
            meta: { image: string };
          };
          expect(existsSync(join(ART, 'towers', sheet.meta.image)), sheet.meta.image).toBe(true);
          expect(sheet.frames[lv.base], lv.base).toBeDefined();
          for (let i = 0; i < manifest.directions; i++) {
            const name = aimFrameName(lv, (i * 2 * Math.PI) / manifest.directions, manifest.directions);
            expect(sheet.frames[name], name).toBeDefined();
          }
        }
      }
    }
  });
});
