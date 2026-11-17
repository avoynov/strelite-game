import { describe, expect, it } from 'vitest';
import { TOWER_IDS } from '../src/sim/content';
import { Game } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';
import { playOut } from './helpers/bot';

const LEVELS = [1, 2, 3, 4, 5, 6, 7, 8];

/**
 * The bot is a plain player (see helpers/bot.ts). These hold the balance to the
 * plan: a mixed defence clears every map level, and from level 3 on, when
 * drones, riders and armour are all in play, no gun wins on its own.
 */
describe('balance', () => {
  it.each(LEVELS)('a mixed defence wins map level %i', (level) => {
    const g = new Game(buildPathMap(MEADOW), { level });
    playOut(g);
    expect(g.phase).toBe('won');
  });

  it.each(LEVELS.filter((l) => l >= 3))('no single gun wins map level %i alone', (level) => {
    for (const id of TOWER_IDS) {
      const g = new Game(buildPathMap(MEADOW), { level });
      if (!g.isUnlocked(id)) continue;
      playOut(g, [id]);
      expect(g.phase, `${id} alone on level ${level}`).toBe('lost');
    }
  });
});
