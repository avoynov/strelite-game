import { describe, expect, it } from 'vitest';
import { TOWER_IDS } from '../src/sim/content';
import { Game } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';
import { RESEARCH, upgrades } from '../src/sim/research';
import { playOut } from './helpers/bot';

/**
 * What a player has researched by the time they beat each map level: stage k
 * is needed for level k. Stage 0 is a new player (crossbow and ZIS-3 only).
 */
export const STAGES: string[][] = [
  [],
  ['boost.damage1', 'gun.howitzer'],
  ['boost.gold1', 'fx.crossbow'],
  ['gun.scorpion', 'boost.lives1', 'fx.zis3'],
  ['boost.damage2', 'gun.trebuchet', 'fx.howitzer'],
  ['boost.reload1', 'gun.greekfire', 'fx.scorpion'],
  ['boost.gold2', 'fx.trebuchet'],
  ['boost.damage3', 'fx.greekfire'],
  ['gun.railgun', 'fx.railgun'],
];
const upTo = (k: number) => STAGES.slice(0, k + 1).flat();
const game = (level: number, stage: number) => new Game(buildPathMap(MEADOW), { level, upgrades: upgrades(upTo(stage), TOWER_IDS) });

const LEVELS = [1, 2, 3, 4, 5, 6, 7, 8];

/**
 * The bot is a plain player (see helpers/bot.ts). These hold the balance to the
 * plan: a new player loses the first map level part-way through, research is
 * what wins it, and each map level needs the research of its stage.
 */
describe('balance', () => {
  it('the stages cover the whole tree, in an order the tree allows', () => {
    expect(upTo(STAGES.length - 1).sort()).toEqual(RESEARCH.map((r) => r.id).sort());
    for (let k = 0; k < STAGES.length; k++) {
      for (const id of STAGES[k]!) {
        const item = RESEARCH.find((r) => r.id === id)!;
        for (const req of item.requires) expect(upTo(k), `${id} needs ${req}`).toContain(req);
      }
    }
  });

  it('a new player with two guns loses map level 1 after holding a good part of it', () => {
    const g = game(1, 0);
    playOut(g);
    expect(g.phase).toBe('lost');
    expect(g.wave).toBeGreaterThanOrEqual(8);
  });

  it.each(LEVELS)('the research of its stage wins map level %i', (level) => {
    const g = game(level, level);
    playOut(g);
    expect(g.phase).toBe('won');
  });

  it.each([2, 4])('map level %i is lost without its stage', (level) => {
    const g = game(level, level - 1);
    playOut(g);
    expect(g.phase).toBe('lost');
  });

  it.each(LEVELS.filter((l) => l >= 3))('no single gun wins map level %i alone, even fully researched', (level) => {
    for (const id of TOWER_IDS) {
      const g = game(level, STAGES.length - 1);
      playOut(g, [id]);
      expect(g.phase, `${id} alone on level ${level}`).toBe('lost');
    }
  });
});
