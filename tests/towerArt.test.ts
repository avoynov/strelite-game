import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { ENEMIES, METRES_PER_TILE, TOWERS } from '../src/sim/content';
import {
  aimFrameName,
  fireFrameAt,
  fireSheet,
  frameForAim,
  frameName,
  releaseDelay,
  spriteScale,
  stickyFrameForAim,
  type TowerArtManifest,
  type TowerFireArt,
} from '../src/render/towers/towerArt';

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

  // footprintRadiusM covers everything solid; only the soil patch's faded edge may reach past it.
  it.skipIf(!existsSync(join(ART, 'towers.json')))('fits every gun inside the footprint the game gives it', () => {
    const manifest = JSON.parse(readFileSync(join(ART, 'towers.json'), 'utf8')) as TowerArtManifest;
    for (const [id, tower] of Object.entries(manifest.towers)) {
      const size = TOWERS[id as keyof typeof TOWERS]?.size ?? 0;
      for (const lv of tower.levels) expect(lv.footprintRadiusM, `${id} L${lv.level}`).toBeLessThanOrEqual((size * METRES_PER_TILE) / 2);
    }
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

describe.skipIf(!existsSync(join(ART, 'towers.json')))('enemy and effect art', () => {
  const manifest = existsSync(join(ART, 'towers.json')) ? (JSON.parse(readFileSync(join(ART, 'towers.json'), 'utf8')) as TowerArtManifest) : null;
  const frames = (sheet: string, density: 1 | 2) =>
    (JSON.parse(readFileSync(join(ART, `${sheet}@${density}x.json`), 'utf8')) as { frames: Record<string, { frame: { w: number; h: number } }> }).frames;

  it('has a sprite for every heading of every enemy it draws, at the size the game uses', () => {
    // Enemies without art yet (new kinds) are drawn as stand-ins by the board.
    const drawn = Object.entries(manifest!.enemies ?? {});
    expect(drawn.length).toBeGreaterThan(0);
    for (const [id, art] of drawn) {
      const def = ENEMIES[id as keyof typeof ENEMIES];
      expect(def, id).toBeDefined();
      // The sprite is real size; the simulation's hit radius may be a little tighter.
      expect(Math.abs(art.radiusM - def.radius * METRES_PER_TILE)).toBeLessThan(0.6);
      for (const density of [1, 2] as const) {
        const sheet = frames(art.sheet, density);
        for (let n = 0; n < art.directions; n++) expect(sheet[frameName(art.frames, n)], `${id} ${n} @${density}x`).toBeDefined();
      }
    }
  });

  it('draws every wall piece at the same pixels per metre as the towers', () => {
    // A wall sheet packed at another scale would stand twice as tall as the guns beside it.
    const walls = Object.values(manifest!.fences ?? {});
    expect(walls.length).toBeGreaterThan(0);
    for (const wall of walls) {
      for (const density of [1, 2] as const) {
        const sheet = JSON.parse(readFileSync(join(ART, `${wall.sheet}@${density}x.json`), 'utf8')) as {
          frames: Record<string, { sourceSize: { w: number } }>;
        };
        for (const piece of ['post', 'px', 'nx', 'py', 'ny'] as const) {
          const f = sheet.frames[wall[piece]];
          expect(f, `${wall.sheet} ${piece} @${density}x`).toBeDefined();
          expect(Math.abs(f!.sourceSize.w - wall.frameM! * manifest!.pxPerMetre[`@${density}x`])).toBeLessThanOrEqual(2);
        }
      }
    }
  });

  it('has every effect frame at both densities, and the @1x frames are the @2x ones at half size', () => {
    for (const name of ['muzzle_flash', 'muzzle_smoke', 'shell_burst']) {
      const fx = manifest!.effects?.[name];
      expect(fx, name).toBeDefined();
      const one = frames(fx!.sheet, 1);
      const two = frames(fx!.sheet, 2);
      for (let n = 0; n < fx!.count; n++) {
        const a = one[frameName(fx!.frames, n)]!.frame;
        const b = two[frameName(fx!.frames, n)]!.frame;
        // Catches a broken downscale: @1x frames that came out empty or as noise.
        expect(Math.abs(a.w - b.w / 2), `${name} ${n} width`).toBeLessThanOrEqual(4);
        expect(Math.abs(a.h - b.h / 2), `${name} ${n} height`).toBeLessThanOrEqual(4);
      }
    }
  });
});

describe('fire animation timing', () => {
  // Trebuchet-like: 16 frames at 16 fps, the stone leaves at frame 6, reload from 12.
  const fire: TowerFireArt = { sheet: 's_<DD>', animation: 'a_<DD>', dirs: 32, frames: 16, fps: 16, releaseFrame: 6, reloadFrom: 12 };

  it('names the sheet of a direction', () => {
    expect(fireSheet(fire, 7)).toEqual({ sheet: 's_07', animation: 'a_07' });
  });

  it('plays the swing at fps, then spreads the reload frames over the reload', () => {
    expect(fireFrameAt(fire, 0, 4)).toBe(1);
    expect(fireFrameAt(fire, 5.5 / 16, 4)).toBe(6);
    expect(fireFrameAt(fire, 11 / 16 + 0.01, 4)).toBe(12);
    expect(fireFrameAt(fire, 3.9, 4)).toBe(16);
    expect(fireFrameAt(fire, 4.01, 4)).toBe(0);
    expect(releaseDelay(fire, 4)).toBeCloseTo(5 / 16);
  });

  it('fits the whole shot into a reload shorter than the animation', () => {
    expect(fireFrameAt(fire, 0.49, 0.5)).toBe(16);
    expect(fireFrameAt(fire, 0.51, 0.5)).toBe(0);
    expect(releaseDelay(fire, 0.5)).toBeCloseTo(5 / 32);
  });
});
