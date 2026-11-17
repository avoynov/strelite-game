import { describe, expect, it } from 'vitest';
import { afterArmor, applyDamage } from '../src/sim/damage';

describe('applyDamage', () => {
  it('deals full damage when the target survives', () => {
    expect(applyDamage(20, 5)).toEqual({ hpAfter: 15, dealt: 5, overkill: 0, blocked: 0 });
  });
  it('wastes damage above remaining health', () => {
    expect(applyDamage(3, 10)).toEqual({ hpAfter: 0, dealt: 3, overkill: 7, blocked: 0 });
  });
  it('wastes everything on a dead target', () => {
    expect(applyDamage(0, 10)).toEqual({ hpAfter: 0, dealt: 0, overkill: 10, blocked: 0 });
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

describe('armour', () => {
  it('takes armor × (1 − pierce) off every hit', () => {
    expect(afterArmor(45, 7, 0.5)).toBeCloseTo(41.5);
    expect(applyDamage(300, 45, 7, 0.5)).toEqual({ hpAfter: 258.5, dealt: 41.5, overkill: 0, blocked: 3.5 });
  });
  it('always lets a tenth of the hit through', () => {
    // The doc's example: a crossbow bolt of 5 on a tank with armour 14.
    expect(afterArmor(5, 14, 0)).toBeCloseTo(0.5);
  });
  it('is ignored by a gun with full pierce', () => {
    expect(afterArmor(1200, 22, 1)).toBe(1200);
  });
  it('hurts light fast guns far more than heavy ones', () => {
    const share = (dmg: number) => afterArmor(dmg, 14) / dmg;
    expect(share(520)).toBeGreaterThan(0.95);
    expect(share(5)).toBeLessThan(0.15);
  });
});
