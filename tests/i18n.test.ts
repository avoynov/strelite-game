import { describe, expect, it } from 'vitest';
import { bg } from '../src/i18n/bg';
import { en } from '../src/i18n/en';
import { ENEMIES, TOWERS } from '../src/sim/content';

describe('i18n', () => {
  it('en has exactly the bg keys', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(bg).sort());
  });
  it('every tower and enemy has a name', () => {
    for (const id of Object.keys(TOWERS)) expect(bg).toHaveProperty(`tower.${id}`);
    for (const id of Object.keys(ENEMIES)) expect(bg).toHaveProperty(`enemy.${id}`);
  });
  it('placeholders match between languages', () => {
    const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
    for (const k of Object.keys(bg) as Array<keyof typeof bg>) expect(ph(en[k])).toEqual(ph(bg[k]));
  });
});
