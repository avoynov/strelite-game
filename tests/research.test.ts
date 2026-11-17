import { describe, expect, it } from 'vitest';
import { TOWER_IDS } from '../src/sim/content';
import { Game } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';
import { bank, newResearch, RESEARCH, sanitize, settle, start, startError, status, upgrades } from '../src/sim/research';

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
    let s = bank(newResearch(), 1000);
    expect(startError(s, 'gun.scorpion')).toBe('locked');
    expect(startError(s, 'gun.howitzer')).toBe('noGold');
    s = start(s, 'boost.damage1', 0);
    expect(s.gold).toBe(400);
    expect(status(s, 'boost.damage1')).toBe('active');
    expect(startError(bank(s, 5000), 'gun.howitzer')).toBe('busy');
    expect(settle(s, 3 * 60 * 1000 - 1)).toBe(s);
    s = settle(s, 3 * 60 * 1000);
    expect(s.done).toEqual(['boost.damage1']);
    expect(s.active).toBeNull();
    expect(startError(s, 'boost.damage1')).toBe('done');
  });

  it('a faster clock shortens the timer', () => {
    const s = start(bank(newResearch(), 1000), 'boost.damage1', 0, 600);
    expect(s.active?.endsAt).toBe(300);
  });

  it('repairs a broken save', () => {
    expect(sanitize(null)).toEqual(newResearch());
    expect(sanitize({ gold: -5, done: ['gun.howitzer', 'nope', 'gun.howitzer'], active: { id: 'gun.howitzer', endsAt: 1 } })).toEqual({ gold: 0, done: ['gun.howitzer'], active: null });
  });

  it('applies boosts and effects to the battle', () => {
    const all = RESEARCH.map((r) => r.id);
    const base = new Game(buildPathMap(MEADOW), { upgrades: upgrades([], TOWER_IDS) });
    const g = new Game(buildPathMap(MEADOW), { upgrades: upgrades(all, TOWER_IDS) });
    expect(g.money).toBe(base.money + 250);
    expect(g.lives).toBe(base.lives + 5);
    expect(g.levelStats('crossbow', 0).damage).toBeCloseTo(base.levelStats('crossbow', 0).damage * 1.3, 1);
    expect(g.levelStats('railgun', 0).fireInterval).toBeCloseTo(base.levelStats('railgun', 0).fireInterval * 0.9 * 0.8, 2);
    expect(g.levelStats('zis3', 0).range).toBe(base.levelStats('zis3', 0).range + 1);
    expect(g.defOf('crossbow').pierce).toBe(0.25);
    expect(g.defOf('scorpion').passThrough).toBe(2);
    expect(g.defOf('greekfire').rampTime).toBe(1);
  });
});
