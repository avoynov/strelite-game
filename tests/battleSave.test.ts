import { describe, expect, it } from 'vitest';
import { TICK } from '../src/sim/content';
import { Game } from '../src/sim/game';
import { levelArcMap, levelMap } from '../src/sim/levels';
import { buildArcMap, buildPathMap } from '../src/sim/maps';
import { spend } from './helpers/bot';

const make = (mode: 'path' | 'arc', level: number) =>
  new Game(mode === 'path' ? buildPathMap(levelMap(level)) : buildArcMap(levelArcMap(level)), { level });

const steps = (g: Game, seconds: number) => {
  for (let i = 0; i < seconds / TICK; i++) g.step(TICK);
};

/** What should be the same for two games that ran the same way. */
const state = (g: Game) => ({ lives: g.lives, wave: g.wave, phase: g.phase, money: g.money, earned: g.goldEarned, enemies: g.enemies.map((e) => [e.id, e.hp, +e.x.toFixed(6), +e.y.toFixed(6)]), towers: g.towers.map((t) => [t.id, t.stats.dealt]) });

describe('saving a running battle', () => {
  for (const mode of ['path', 'arc'] as const) {
    it(`${mode}: a battle saved mid-wave goes on exactly as if it never stopped`, () => {
      const a = make(mode, 3);
      a.money = 5000;
      spend(a);
      a.startWave();
      steps(a, 12);
      expect(a.enemies.length).toBeGreaterThan(0);
      const save = JSON.parse(JSON.stringify(a.saveBattle()));
      const b = make(mode, 3);
      expect(b.restoreBattle(save)).toBe(true);
      expect(state(b)).toEqual(state(a));
      steps(a, 20);
      steps(b, 20);
      expect(state(b)).toEqual(state(a));
      // Built ground stays taken.
      const t = b.towers[0]!;
      expect(b.towerAt(t.cx, t.cy)?.id).toBe(t.id);
    });
  }

  it('refuses a save from another level or mode, and saves nothing once the battle is over', () => {
    const a = make('path', 2);
    const save = a.saveBattle();
    expect(make('path', 3).restoreBattle(save)).toBe(false);
    expect(make('arc', 2).restoreBattle(save)).toBe(false);
    expect(make('path', 2).restoreBattle({ v: 99 })).toBe(false);
    expect(make('path', 2).restoreBattle(null)).toBe(false);
    a.lives = 0;
    a.phase = 'lost';
    expect(a.saveBattle()).toBeNull();
  });
});
