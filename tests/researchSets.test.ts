import { describe, expect, it } from 'vitest';
import { TOWER_IDS } from '../src/sim/content';
import { bank, completeSets, GUN_ORDER, MASTERY_DAMAGE, MASTERY_GOLD, newResearch, RESEARCH, RESEARCH_SETS, setItems, setOf, setProgress, start, suggestNext, treeProgress, upgrades } from '../src/sim/research';

const set = (id: string) => RESEARCH_SETS.find((s) => s.id === id)!;

describe('research sets', () => {
  it('every research item sits in exactly one set', () => {
    const all = RESEARCH_SETS.flatMap((s) => s.items);
    expect([...all].sort()).toEqual(RESEARCH.map((r) => r.id).sort());
    expect(new Set(all).size).toBe(all.length);
  });

  it('one set per gun in unlock order, then the Fortress and the Traps', () => {
    expect(RESEARCH_SETS.map((s) => s.id)).toEqual([...GUN_ORDER, 'fortress', 'traps']);
    expect([...GUN_ORDER].sort()).toEqual([...TOWER_IDS].sort());
  });

  it('the starting guns count as one piece done, so the tree never starts at zero', () => {
    // The crossbow's set also holds its sight (aiming at the most vulnerable target).
    expect(setProgress(set('crossbow'), [])).toEqual({ done: 1, total: 5 });
    expect(setProgress(set('zis3'), [])).toEqual({ done: 1, total: 4 });
    expect(setProgress(set('howitzer'), [])).toEqual({ done: 0, total: 4 });
    expect(treeProgress([])).toEqual({ done: 2, total: RESEARCH.length + 2 });
    expect(treeProgress(RESEARCH.map((r) => r.id))).toEqual({ done: RESEARCH.length + 2, total: RESEARCH.length + 2 });
  });

  it('a set is complete only with every piece', () => {
    expect(completeSets(['lvl4.crossbow', 'lvl5.crossbow'])).toEqual([]);
    expect(completeSets(['lvl4.crossbow', 'lvl5.crossbow', 'fx.crossbow'])).toEqual([]);
    expect(completeSets(['lvl4.crossbow', 'lvl5.crossbow', 'fx.crossbow', 'aim.crossbow'])).toEqual(['crossbow']);
    expect(setOf('boost.reload1')?.id).toBe('fortress');
  });

  it('a full set gives its bonus: more damage for that gun, more banked gold for the Fortress', () => {
    const none = upgrades([], TOWER_IDS);
    const crossbow = upgrades(set('crossbow').items, TOWER_IDS);
    expect(crossbow.gun.crossbow.damage).toBeCloseTo(1 + MASTERY_DAMAGE);
    expect(crossbow.gun.zis3.damage).toBe(1);
    expect(none.goldBonus).toBe(0);
    expect(upgrades(set('fortress').items, TOWER_IDS).goldBonus).toBe(MASTERY_GOLD);
  });

  it('the headquarters sets how far the tree reaches: a set full now opens again when it grows', () => {
    const hq0 = { level: 0, standing: true, hq: 0 };
    const hq3 = { ...hq0, hq: 2 };
    // Act I: the crossbow's effect only (level IV comes with act III, level V with act VI).
    expect(setItems(set('crossbow'), hq0)).toEqual(['fx.crossbow']);
    const done = ['fx.crossbow'];
    expect(completeSets(done, hq0)).toContain('crossbow');
    expect(upgrades(done, TOWER_IDS, hq0).gun.crossbow.damage).toBeCloseTo(1 + MASTERY_DAMAGE);
    // Act III brings level IV into the tree: the set is open again, its bonus waits for it.
    expect(setItems(set('crossbow'), hq3)).toContain('lvl4.crossbow');
    expect(completeSets(done, hq3)).not.toContain('crossbow');
    expect(upgrades(done, TOWER_IDS, hq3).gun.crossbow.damage).toBe(1);
    // The whole tree grows with the levels, and nothing finished ever leaves it.
    const sizes = [0, 1, 2, 3, 4, 5, 6, 7, 8].map((hq) => treeProgress([], { ...hq0, hq }).total);
    for (let i = 1; i < sizes.length; i++) expect(sizes[i]!).toBeGreaterThan(sizes[i - 1]!);
    expect(sizes[8]).toBe(treeProgress([]).total);
    expect(treeProgress(['gun.railgun'], hq0).done).toBe(3);
    // A set with nothing in the tree yet earns no medal.
    expect(completeSets([], hq0)).not.toContain('railgun');
  });

  it('suggests what brings a set closest to its medal, then the cheapest', () => {
    const rich = bank(newResearch(), 100000);
    // Fresh: of the sets closest to a medal, the cheapest piece that can start.
    expect(suggestNext(rich)).toBe('fx.crossbow');
    // Three ZIS-3 pieces done: its last open piece comes first, once the laboratory is high enough.
    const s = { ...rich, done: ['fx.crossbow', 'fx.zis3', 'lvl4.zis3'] };
    expect(suggestNext(s, { level: 5, standing: true })).toBe('lvl5.zis3');
    expect(suggestNext(s)).not.toBe('lvl5.zis3');
    // Busy laboratory: nothing can start, so the cheapest ready item to save for.
    expect(suggestNext(start(rich, 'boost.gold1', 0))).toBe('fx.crossbow');
    // Poor: still points at the cheapest ready item.
    expect(suggestNext(newResearch())).toBe('boost.gold1');
    expect(suggestNext({ ...rich, done: RESEARCH.map((r) => r.id) })).toBeNull();
  });
});
