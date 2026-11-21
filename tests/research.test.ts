import { describe, expect, it } from 'vitest';
import { TOWER_IDS } from '../src/sim/content';
import { Game } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';
import { bank, battleTakings, MASTERY_DAMAGE, newResearch, pause, RESEARCH, resume, sanitize, settle, start, startError, status, upgrades, victoryBonus } from '../src/sim/research';

describe('research', () => {
  it('every item needs only items that exist, and deeper items cost more and take longer', () => {
    const ids = new Set(RESEARCH.map((r) => r.id));
    for (const r of RESEARCH) {
      for (const req of r.requires) {
        expect(ids.has(req), `${r.id} needs ${req}`).toBe(true);
        const before = RESEARCH.find((x) => x.id === req)!;
        if (before.branch === r.branch) {
          expect(r.cost, r.id).toBeGreaterThan(before.cost);
          expect(r.seconds, r.id).toBeGreaterThan(before.seconds);
        }
      }
    }
  });

  it('costs gold, runs one at a time and finishes on the clock', () => {
    let s = bank(newResearch(), 300);
    expect(startError(s, 'gun.scorpion')).toBe('locked');
    expect(startError(s, 'gun.howitzer')).toBe('noGold');
    s = start(s, 'boost.gold1', 0);
    expect(s.gold).toBe(100);
    expect(status(s, 'boost.gold1')).toBe('active');
    expect(startError(bank(s, 5000), 'fx.crossbow')).toBe('busy');
    expect(settle(s, 2 * 60 * 1000 - 1)).toBe(s);
    s = settle(s, 2 * 60 * 1000);
    expect(s.done).toEqual(['boost.gold1']);
    expect(s.active).toEqual([]);
    expect(startError(s, 'boost.gold1')).toBe('done');
  });

  it('a faster clock shortens the timer', () => {
    const s = start(bank(newResearch(), 1000), 'boost.gold1', 0, 600);
    expect(s.active[0]?.endsAt).toBe(200);
  });

  it('banks only the gold a battle earned and did not spend, plus a bonus for a win', () => {
    expect(battleTakings(500, 120, false, 1)).toBe(120); // the starting gold stays behind
    expect(battleTakings(30, 400, false, 1)).toBe(30); // spent is spent
    expect(battleTakings(30, 400, true, 3)).toBe(30 + victoryBonus(3));
  });

  it('opens gun levels 4 and 5 only through research', () => {
    const none = upgrades([], TOWER_IDS);
    expect(none.maxLevel.crossbow).toBe(3);
    expect(upgrades(['lvl4.crossbow', 'lvl5.crossbow'], TOWER_IDS).maxLevel.crossbow).toBe(5);
    const g = new Game(buildPathMap(MEADOW), { upgrades: none });
    g.money = 10000;
    g.build('crossbow', 2, 2);
    const t = g.towers[0]!;
    g.upgrade(t.id);
    g.upgrade(t.id);
    expect(t.level + 1).toBe(3);
    expect(g.upgrade(t.id)).toEqual({ ok: false, reason: 'levelLocked' });
  });

  it('repairs a broken save', () => {
    expect(sanitize(null)).toEqual(newResearch());
    expect(sanitize({ gold: -5, done: ['gun.howitzer', 'nope', 'gun.howitzer'], active: { id: 'gun.howitzer', endsAt: 1 } })).toEqual({ gold: 0, done: ['gun.howitzer'], active: [], pausedAt: null });
    // An older save with one running item keeps it.
    expect(sanitize({ gold: 1, done: [], active: { id: 'gun.howitzer', endsAt: 5 } }).active).toEqual([{ id: 'gun.howitzer', endsAt: 5 }]);
  });

  it('applies boosts and effects to the battle', () => {
    const all = RESEARCH.map((r) => r.id);
    const base = new Game(buildPathMap(MEADOW), { upgrades: upgrades([], TOWER_IDS) });
    const g = new Game(buildPathMap(MEADOW), { upgrades: upgrades(all, TOWER_IDS) });
    expect(g.money).toBe(base.money + 250);
    expect(g.lives).toBe(base.lives + 5);
    // Three damage boosts, and the full crossbow set on top.
    expect(g.levelStats('crossbow', 0).damage).toBeCloseTo(base.levelStats('crossbow', 0).damage * 1.3 * (1 + MASTERY_DAMAGE), 1);
    expect(g.levelStats('railgun', 0).fireInterval).toBeCloseTo(base.levelStats('railgun', 0).fireInterval * 0.9 * 0.8, 2);
    expect(g.levelStats('zis3', 0).range).toBe(base.levelStats('zis3', 0).range + 1);
    expect(g.defOf('crossbow').pierce).toBe(0.25);
    expect(g.defOf('scorpion').passThrough).toBe(2);
    expect(g.defOf('greekfire').rampTime).toBe(1);
  });

  it('the laboratory: a higher one runs two at once (no faster); the headquarters opens the deeper items; destroyed, it stops the clocks', () => {
    const rich = bank(newResearch(), 100000);
    // Level 1: one at a time.
    let s = start(rich, 'boost.gold1', 0);
    expect(startError(s, 'fx.crossbow')).toBe('busy');
    // Level 4 (index 3): two at once, at the same speed.
    const lab4 = { level: 3, standing: true };
    s = start(rich, 'boost.gold1', 0, 1, lab4);
    expect(s.active[0]!.endsAt).toBe(2 * 60 * 1000);
    expect(startError(s, 'fx.crossbow', lab4)).toBeNull();
    s = start(s, 'fx.crossbow', 0, 1, lab4);
    expect(s.active).toHaveLength(2);
    expect(startError(s, 'lvl4.crossbow', lab4)).toBe('busy');
    // The headquarters decides how far the tree reaches; the laboratory's level does not.
    const railReady = { ...rich, done: ['gun.howitzer', 'gun.scorpion', 'gun.trebuchet', 'gun.greekfire'] };
    expect(startError(railReady, 'gun.railgun')).toBe('hqLevel');
    expect(startError(railReady, 'gun.railgun', { level: 4, standing: true, hq: 2 })).toBe('hqLevel');
    expect(startError(railReady, 'gun.railgun', { level: 0, standing: true, hq: 3 })).toBeNull();
    // The deeper (dearer) the item, the higher the headquarters that brings it into the tree.
    for (const r of RESEARCH) for (const req of r.requires) expect(r.hq ?? 1, r.id).toBeGreaterThanOrEqual(RESEARCH.find((x) => x.id === req)!.hq ?? 1);
    expect(RESEARCH.filter((r) => (r.hq ?? 1) === 5).length).toBeGreaterThan(0);
    // Destroyed: nothing starts, nothing finishes; rebuilt, the clock goes on.
    expect(startError(rich, 'boost.gold1', { level: 0, standing: false })).toBe('noLab');
    let p = start(rich, 'boost.gold1', 0);
    p = pause(p, 60_000);
    expect(settle(p, 10 * 60_000)).toBe(p);
    p = resume(p, 10 * 60_000);
    expect(settle(p, 11 * 60_000 - 1).done).toEqual([]);
    expect(settle(p, 11 * 60_000).done).toEqual(['boost.gold1']);
  });
});
