import { describe, expect, it } from 'vitest';
import { TOWER_IDS } from '../src/sim/content';
import { Game } from '../src/sim/game';
import { levelArcMap, levelMap } from '../src/sim/levels';
import { buildArcMap, buildPathMap, type Mode } from '../src/sim/maps';
import { battleTakings, RESEARCH, upgrades } from '../src/sim/research';
import { playOut } from './helpers/bot';

/**
 * The order a player researches in. Stage 0 is a new player (crossbow and
 * ZIS-3, gun levels 1–3 only); each stage adds a few items.
 */
export const STAGES: string[][] = [
  [],
  ['boost.gold1'],
  ['boost.damage1', 'fx.crossbow'],
  ['gun.howitzer', 'lvl4.crossbow', 'lvl4.zis3'],
  ['boost.lives1', 'fx.zis3', 'gun.scorpion'],
  ['boost.damage2', 'fx.howitzer', 'lvl4.howitzer'],
  ['gun.trebuchet', 'lvl5.crossbow', 'lvl5.zis3', 'boost.reload1'],
  ['gun.greekfire', 'fx.scorpion', 'lvl4.scorpion', 'boost.gold2'],
  ['fx.trebuchet', 'lvl4.trebuchet', 'lvl5.howitzer', 'boost.damage3'],
  ['gun.railgun', 'fx.greekfire', 'lvl4.greekfire', 'lvl5.scorpion'],
  ['fx.railgun', 'lvl4.railgun', 'lvl5.trebuchet', 'lvl5.greekfire', 'lvl5.railgun'],
];
const FULL = STAGES.length - 1;
const upTo = (k: number) => STAGES.slice(0, k + 1).flat();
const play = (level: number, stage: number, only?: (typeof TOWER_IDS)[number][], mode: Mode = 'path') => {
  const map = mode === 'path' ? buildPathMap(levelMap(level)) : buildArcMap(levelArcMap(level), mode);
  const g = new Game(map, { level, upgrades: upgrades(upTo(stage), TOWER_IDS) });
  playOut(g, only);
  return g;
};

/** The stage a map level needs: the bot wins with it and loses two stages short of it. */
const NEEDS: [level: number, stage: number][] = [
  [1, 1],
  [5, 4],
  [8, 6],
  [12, 8],
  [20, FULL],
];

/**
 * The bot is a plain player (see helpers/bot.ts). These hold the balance to the
 * plan: a new player loses map level 1, one cheap research item wins it, and
 * each further map level asks for more of the tree; the whole tree holds out
 * deep into the endless levels.
 */
describe('balance', () => {
  it('the stages cover the whole tree, in an order the tree allows', () => {
    expect(upTo(FULL).sort()).toEqual(RESEARCH.map((r) => r.id).sort());
    for (let k = 0; k <= FULL; k++) {
      for (const id of STAGES[k]!) {
        const item = RESEARCH.find((r) => r.id === id)!;
        for (const req of item.requires) expect(upTo(k), `${id} needs ${req}`).toContain(req);
      }
    }
  });

  it('a new player with the two starting guns loses map level 1, and two such losses pay for the first item', () => {
    const g = play(1, 0);
    expect(g.phase).toBe('lost');
    const first = RESEARCH.find((r) => r.id === STAGES[1]![0])!;
    expect(2 * battleTakings(g.money, g.goldEarned, false, 1)).toBeGreaterThanOrEqual(first.cost);
  });

  it.each(NEEDS)('map level %i is won with research stage %i', (level, stage) => {
    expect(play(level, stage).phase).toBe('won');
  });

  it.each(NEEDS.filter(([, stage]) => stage >= 2))('map level %i is lost two stages short of %i', (level, stage) => {
    expect(play(level, stage - 2).phase).toBe('lost');
  });

  it('the whole tree still wins a long level far along', () => {
    expect(play(50, FULL).phase).toBe('won');
  });

  it('no single gun wins map level 20 alone, even fully researched', () => {
    for (const id of TOWER_IDS) expect(play(20, FULL, [id]).phase, `${id} alone`).toBe('lost');
  });
});

/** Arc mode: the same ladder; the widening arc asks for a little more of the tree. */
const ARC_NEEDS: [level: number, stage: number][] = [
  [1, 1],
  [5, 6],
  [12, 6],
];

describe('balance in arc mode', () => {
  it('a new player loses map level 1 in arc mode too', () => {
    expect(play(1, 0, undefined, 'arc').phase).toBe('lost');
  });

  it.each(ARC_NEEDS)('arc map level %i is won with research stage %i', (level, stage) => {
    expect(play(level, stage, undefined, 'arc').phase).toBe('won');
  });

  it.each(ARC_NEEDS.filter(([, stage]) => stage >= 2))('arc map level %i is lost two stages short of %i', (level, stage) => {
    expect(play(level, stage - 2, undefined, 'arc').phase).toBe('lost');
  });
});

/**
 * Siege mode: the bot keeps its guns out of the attackers' reach and, once it
 * can spare the gold, walls the goal in with fences and repairs them.
 */
const SIEGE_NEEDS: [level: number, stage: number][] = [
  [1, 1],
  [5, 6],
  [12, 6],
];

describe('balance in siege mode', () => {
  it('a new player loses map level 1 in siege mode too', () => {
    expect(play(1, 0, undefined, 'siege').phase).toBe('lost');
  });

  it.each(SIEGE_NEEDS)('siege map level %i is won with research stage %i', (level, stage) => {
    expect(play(level, stage, undefined, 'siege').phase).toBe('won');
  });

  it.each(SIEGE_NEEDS.filter(([, stage]) => stage >= 2))('siege map level %i is lost two stages short of %i', (level, stage) => {
    expect(play(level, stage - 2, undefined, 'siege').phase).toBe('lost');
  });
});
