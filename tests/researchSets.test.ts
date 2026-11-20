import { describe, expect, it } from 'vitest';
import { TOWER_IDS } from '../src/sim/content';
import { bank, completeSets, GUN_ORDER, MASTERY_DAMAGE, MASTERY_GOLD, newResearch, RESEARCH, RESEARCH_SETS, setOf, setProgress, start, suggestNext, treeProgress, upgrades } from '../src/sim/research';

const set = (id: string) => RESEARCH_SETS.find((s) => s.id === id)!;

describe('research sets', () => {
  it('every research item sits in exactly one set', () => {
    const all = RESEARCH_SETS.flatMap((s) => s.items);
    expect([...all].sort()).toEqual(RESEARCH.map((r) => r.id).sort());
    expect(new Set(all).size).toBe(all.length);
  });

  it('one set per gun in unlock order, then the Fortress', () => {
    expect(RESEARCH_SETS.map((s) => s.id)).toEqual([...GUN_ORDER, 'fortress']);
    expect([...GUN_ORDER].sort()).toEqual([...TOWER_IDS].sort());
  });

  it('the starting guns count as one piece done, so the tree never starts at zero', () => {
    expect(setProgress(set('crossbow'), [])).toEqual({ done: 1, total: 4 });
    expect(setProgress(set('howitzer'), [])).toEqual({ done: 0, total: 4 });
    expect(treeProgress([])).toEqual({ done: 2, total: RESEARCH.length + 2 });
    expect(treeProgress(RESEARCH.map((r) => r.id))).toEqual({ done: RESEARCH.length + 2, total: RESEARCH.length + 2 });
  });

  it('a set is complete only with every piece', () => {
    expect(completeSets(['lvl4.crossbow', 'lvl5.crossbow'])).toEqual([]);
    expect(completeSets(['lvl4.crossbow', 'lvl5.crossbow', 'fx.crossbow'])).toEqual(['crossbow']);
    expect(setOf('boost.reload1')?.id).toBe('fortress');
  });

  it('a full set gives its bonus: more damage for that gun, more banked gold for the Fortress', () => {
    const none = upgrades([], TOWER_IDS);
    const crossbow = upgrades(['lvl4.crossbow', 'lvl5.crossbow', 'fx.crossbow'], TOWER_IDS);
    expect(crossbow.gun.crossbow.damage).toBeCloseTo(1 + MASTERY_DAMAGE);
    expect(crossbow.gun.zis3.damage).toBe(1);
    expect(none.goldBonus).toBe(0);
    expect(upgrades(set('fortress').items, TOWER_IDS).goldBonus).toBe(MASTERY_GOLD);
  });

  it('suggests what brings a set closest to its medal, then the cheapest', () => {
    const rich = bank(newResearch(), 100000);
    // Fresh: the crossbow set has a piece already; of its two open pieces the cheaper.
    expect(suggestNext(rich)).toBe('fx.crossbow');
    // Two crossbow pieces done: its last open piece comes first, once the laboratory is high enough.
    const s = { ...rich, done: ['fx.crossbow', 'lvl4.crossbow'] };
    expect(suggestNext(s, { level: 1, standing: true })).toBe('lvl5.crossbow');
    expect(suggestNext(s)).not.toBe('lvl5.crossbow');
    // Busy laboratory: nothing can start, so the cheapest ready item to save for.
    expect(suggestNext(start(rich, 'boost.gold1', 0))).toBe('fx.crossbow');
    // Poor: still points at the cheapest ready item.
    expect(suggestNext(newResearch())).toBe('boost.gold1');
    expect(suggestNext({ ...rich, done: RESEARCH.map((r) => r.id) })).toBeNull();
  });
});
