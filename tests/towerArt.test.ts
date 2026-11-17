import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { aimFrameName, frameForAim, spriteScale, type TowerArtManifest } from '../src/render/towers/towerArt';

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

  it('ships every frame the manifest promises', () => {
    const manifest = JSON.parse(readFileSync(join(ART, 'towers.json'), 'utf8')) as TowerArtManifest;
    expect(manifest.directions).toBe(32);
    for (const [id, tower] of Object.entries(manifest.towers)) {
      expect(tower.levels.length, id).toBe(3);
      for (const lv of tower.levels) {
        expect(lv.muzzlePx.length).toBe(manifest.directions);
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
