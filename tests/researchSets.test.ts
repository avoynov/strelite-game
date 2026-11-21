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

  it('one set per gun in unlock order, then the Fortress', () => {
    expect(RESEARCH_SETS.map((s) => s.id)).toEqual([...GUN_ORDER, 'fortress']);
    expect([...GUN_ORDER].sort()).toEqual([...TOWER_IDS].sort());
  });

  it('the starting guns count as one piece done, so the tree never starts at zero', () => {
    // The crossbow's set also holds its sight (aiming at the smallest target).
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
    const hq1 = { ...hq0, hq: 1 };
    // Level I: the crossbow's cheap pieces only (level V comes later).
    expect(setItems(set('crossbow'), hq0)).toEqual(['lvl4.crossbow', 'fx.crossbow', 'aim.crossbow']);
    const done = ['lvl4.crossbow', 'fx.crossbow', 'aim.crossbow'];
    expect(completeSets(done, hq0)).toContain('crossbow');
    expect(upgrades(done, TOWER_IDS, hq0).gun.crossbow.damage).toBeCloseTo(1 + MASTERY_DAMAGE);
    // Level II brings level V into the tree: the set is open again, its bonus waits for it.
    expect(setItems(set('crossbow'), hq1)).toContain('lvl5.crossbow');
    expect(completeSets(done, hq1)).not.toContain('crossbow');
    expect(upgrades(done, TOWER_IDS, hq1).gun.crossbow.damage).toBe(1);
    // The whole tree grows with every level, and nothing finished ever leaves it.
    const sizes = [0, 1, 2, 3, 4].map((hq) => treeProgress([], { ...hq0, hq }).total);
    for (let i = 1; i < sizes.length; i++) expect(sizes[i]!).toBeGreaterThan(sizes[i - 1]!);
    expect(sizes[4]).toBe(treeProgress([]).total);
    expect(treeProgress(['gun.railgun'], hq0).done).toBe(3);
    // A set with nothing in the tree yet earns no medal.
    expect(completeSets([], hq0)).not.toContain('railgun');
  });

  it('suggests what brings a set closest to its medal, then the cheapest', () => {
    const rich = bank(newResearch(), 100000);
    // Fresh: the ZIS-3 set is the shortest with a piece already; of its open pieces the one that can start.
    expect(suggestNext(rich)).toBe('lvl4.zis3');
    // Three ZIS-3 pieces done: its last open piece comes first, once the laboratory is high enough.
    const s = { ...rich, done: ['fx.crossbow', 'fx.zis3', 'lvl4.zis3'] };
    expect(suggestNext(s, { level: 1, standing: true })).toBe('lvl5.zis3');
    expect(suggestNext(s)).not.toBe('lvl5.zis3');
    // Busy laboratory: nothing can start, so the cheapest ready item to save for.
    expect(suggestNext(start(rich, 'boost.gold1', 0))).toBe('fx.crossbow');
    // Poor: still points at the cheapest ready item.
    expect(suggestNext(newResearch())).toBe('boost.gold1');
    expect(suggestNext({ ...rich, done: RESEARCH.map((r) => r.id) })).toBeNull();
  });
});
