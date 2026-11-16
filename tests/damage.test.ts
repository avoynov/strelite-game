import { describe, expect, it } from 'vitest';
import { applyDamage } from '../src/sim/damage';

describe('applyDamage', () => {
  it('deals full damage when the target survives', () => {
    expect(applyDamage(20, 5)).toEqual({ hpAfter: 15, dealt: 5, overkill: 0 });
  });
  it('wastes damage above remaining health', () => {
    expect(applyDamage(3, 10)).toEqual({ hpAfter: 0, dealt: 3, overkill: 7 });
  });
  it('wastes everything on a dead target', () => {
    expect(applyDamage(0, 10)).toEqual({ hpAfter: 0, dealt: 0, overkill: 10 });
  });
  it('heavy hits waste more on small targets than light hits', () => {
    const waste = (hp: number, dmg: number) => {
      let total = 0;
      while (hp > 0) {
        const r = applyDamage(hp, dmg);
        hp = r.hpAfter;
        total += r.overkill;
      }
      return total;
    };
    expect(waste(12, 50)).toBeGreaterThan(waste(12, 5));
  });
});
