import { describe, expect, it } from 'vitest';
import { DEFAULT_SHOT_EFFECTS, shotEffects } from '../src/render/towers/towerArt';
import { TOWERS } from '../src/sim/content';

describe('shot effects per gun', () => {
  it('only powder guns flash and smoke; tension engines fire silently', () => {
    for (const id of ['crossbow', 'scorpion', 'trebuchet']) expect(shotEffects(null, id)).toEqual([]);
    for (const id of ['zis3', 'howitzer']) expect(shotEffects(null, id)).toEqual(['muzzle_flash', 'muzzle_smoke']);
    expect(shotEffects(null, 'greekfire')).toEqual(['fire_stream']);
    expect(shotEffects(null, 'railgun')).toEqual(['rail_charge', 'rail_beam']);
  });

  it('covers every gun in the roster', () => {
    for (const id of Object.keys(TOWERS)) expect(DEFAULT_SHOT_EFFECTS[id], id).toBeDefined();
  });

  it('the art manifest wins over the defaults', () => {
    const manifest = { towers: { zis3: { shotEffects: ['muzzle_smoke'] } } } as never;
    expect(shotEffects(manifest, 'zis3')).toEqual(['muzzle_smoke']);
  });
});
