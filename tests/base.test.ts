import { describe, expect, it } from 'vitest';
import { ENEMIES, TOWERS, TICK, gunHp } from '../src/sim/content';
import {
  BASE_MAP,
  BASE_RULES,
  builders,
  gunJobSeconds,
  HQ_LEVELS,
  HQ_SPOT,
  inBuildArea,
  jobError,
  LAB_LEVELS,
  LAB_REBUILD,
  LAB_SPOT,
  lossSale,
  newBase,
  sanitizeBase,
  settleJobs,
  startJob,
} from '../src/sim/base';
import { Game } from '../src/sim/game';
import { buildArcMap } from '../src/sim/maps';
import { waveSpec, type WaveSpec } from '../src/sim/waves';
import { Campaign } from './helpers/baseBot';
import { upTo } from './helpers/stages';
import { TOWER_IDS } from '../src/sim/content';
import { upgrades } from '../src/sim/research';
import { baseTakings, hqThreat } from '../src/sim/base';
import { attackStrength, defenceStrength } from '../src/sim/strength';

const only = (enemy: keyof typeof ENEMIES, count: number, hp = 50): WaveSpec => ({ groups: [{ enemy, count, hp, interval: 0.8, delay: 0, reward: 1 }], clearBonus: 0 });

/** A game at the base with a hand-driven clock. */
function baseGame(gold = 1000, waves?: (n: number) => WaveSpec, state = newBase()) {
  const clock = { ms: 0 };
  const wallet = { gold };
  const g = new Game(buildArcMap(BASE_MAP, 'siege'), { level: state.attack, base: { state, wallet, now: () => clock.ms }, ...(waves ? { waves, totalWaves: 1 } : {}) });
  return { g, clock, wallet, state };
}

describe('the base', () => {
  it('a new base: headquarters on the goal, the laboratory and two crossbows, all inside the area', () => {
    const { g } = baseGame();
    expect(g.hq).toMatchObject({ cx: HQ_SPOT[0], cy: HQ_SPOT[1], level: 0, hp: HQ_LEVELS[0]!.hp });
    expect(g.lab).toMatchObject({ cx: LAB_SPOT[0], cy: LAB_SPOT[1], level: 0 });
    expect(g.buildingAt(LAB_SPOT[0] + 1, LAB_SPOT[1] + 1)?.kind).toBe('lab');
    expect(g.towers.map((t) => t.def)).toEqual(['crossbow', 'crossbow']);
    for (const t of g.towers) expect(inBuildArea(0, t.cx, t.cy, t.size)).toBe(true);
    expect(inBuildArea(0, LAB_SPOT[0], LAB_SPOT[1], 2)).toBe(true);
  });

  it('spends from the treasury; building a gun takes a builder and real time, a fence goes up at once', () => {
    const { g, clock, wallet } = baseGame(1000);
    const [hx, hy] = HQ_SPOT;
    expect(g.build('zis3', hx - 4, hy).ok).toBe(true);
    expect(wallet.gold).toBe(1000 - TOWERS.zis3.levels[0].cost);
    const t = g.towerAt(hx - 4, hy)!;
    expect(t.job?.kind).toBe('build');
    // One builder at the start: the next gun waits.
    expect(g.build('crossbow', hx - 1, hy + 3)).toEqual({ ok: false, reason: 'noBuilder' });
    // Fences need no builder.
    expect(g.buildFence(hx - 2, hy + 3).ok).toBe(true);
    // The first level takes a minute, the middle one ten.
    expect(gunJobSeconds('zis3', 0)).toBe(60);
    expect(gunJobSeconds('zis3', 2)).toBe(600);
    expect(gunJobSeconds('zis3', 4)).toBeGreaterThan(gunJobSeconds('zis3', 3));
    clock.ms = 59_999;
    g.step(TICK);
    expect(t.job).toBeDefined();
    clock.ms = 60_000;
    g.step(TICK);
    expect(t.job).toBeUndefined();
    expect(g.drainEvents().some((e) => e.type === 'built')).toBe(true);
    // Raising it takes time too, the same in battle; it stays at its level until done.
    expect(g.upgrade(t.id).ok).toBe(true);
    expect(t.level).toBe(0);
    clock.ms += gunJobSeconds('zis3', 1) * 1000;
    g.step(TICK);
    expect(t.level).toBe(1);
    expect(t.maxHp).toBe(gunHp(t.size, 1));
  });

  it('a gun still being built does not fire', () => {
    const { g } = baseGame(1000, () => only('infantry', 3, 20));
    for (const t of g.towers) t.job = { kind: 'build', endsAt: 1e12 };
    g.startWave();
    for (let i = 0; i < 60 / TICK && g.phase === 'wave'; i++) g.step(TICK);
    expect(g.towers.every((t) => t.stats.dealt === 0)).toBe(true);
  });

  it('nothing is built outside the area the headquarters allows', () => {
    const { g } = baseGame(1000);
    const [hx, hy] = HQ_SPOT;
    const far = hx - 8;
    expect(g.placementError('crossbow', far, hy)).toBe('notBuildable');
    expect(g.fenceError(far, hy)).toBe('notBuildable');
    expect(inBuildArea(1, far, hy, 2)).toBe(true);
  });

  it('whatever gets through strikes the headquarters; when it falls the base is lost', () => {
    const { g } = baseGame(0, () => only('truck', 40, 50000));
    for (const t of [...g.towers]) g.sell(t.id);
    g.startWave();
    for (let i = 0; i < 600 / TICK && g.phase === 'wave'; i++) g.step(TICK);
    expect(g.phase).toBe('lost');
    expect(g.hq!.hp).toBe(0);
    expect(g.lives).toBeGreaterThan(0); // the base counts the headquarters, not lives
  });

  it('attackers wreck the laboratory when they get near it', () => {
    const { g } = baseGame(0, () => only('tank', 6, 50000));
    g.hq!.hp = g.hq!.maxHp = 1e9;
    g.startWave();
    let wrecked = false;
    for (let i = 0; i < 900 / TICK && g.phase === 'wave' && g.lab; i++) {
      g.step(TICK);
      wrecked ||= g.drainEvents().some((e) => e.type === 'wrecked' && e.building === 'lab');
    }
    expect(g.lab).toBeNull();
    expect(wrecked).toBe(true);
    expect(g.buildingAt(LAB_SPOT[0], LAB_SPOT[1])).toBeUndefined();
  });

  it('repairs cost less than new, and mend fully', () => {
    const { g, wallet } = baseGame(1000);
    const t = g.towers[0]!;
    t.hp = 1;
    const cost = g.repairCost(t);
    expect(cost).toBeLessThan(t.stats.invested);
    expect(cost).toBe(Math.ceil(t.stats.invested * BASE_RULES.repairShare * (1 - 1 / t.maxHp)));
    expect(g.repair(t).ok).toBe(true);
    expect(t.hp).toBe(t.maxHp);
    expect(wallet.gold).toBe(1000 - cost);
    g.hq!.hp -= 100;
    expect(g.repairAll().ok).toBe(true);
    expect(g.repairAllCost()).toBe(0);
  });

  it('keeps what stands from one game to the next, damage and all', () => {
    const { g } = baseGame(1000);
    g.buildFence(HQ_SPOT[0] - 2, HQ_SPOT[1]);
    g.towers[0]!.hp = 50;
    const saved = sanitizeBase(JSON.parse(JSON.stringify({ ...newBase(), ...g.snapshot(), attack: 4 })));
    const next = baseGame(0, undefined, saved).g;
    expect(next.level).toBe(4);
    expect(next.towers[0]!.hp).toBe(50);
    expect(next.fences).toHaveLength(1);
  });

  it('builders raise the headquarters (wider area, higher guns) and the laboratory (more builders) on the clock', () => {
    let b = newBase();
    expect(builders(b)).toBe(1);
    expect(jobError(b, 'hq', 0)).toBe('noGold');
    // The laboratory never rises above the headquarters.
    expect(jobError(b, 'lab', 1e9)).toBe('hqLevel');
    b = startJob(b, 'hq', 0);
    b = settleJobs(b, HQ_LEVELS[1]!.seconds * 1000);
    expect(b.hq.level).toBe(1);
    expect(jobError(b, 'lab', 1e9)).toBeNull();
    b = startJob(b, 'lab', 0);
    expect(jobError(b, 'hq', 1e9)).toBe('noBuilder');
    b = { ...b, jobs: [] };
    expect(b.hq.hp).toBe(HQ_LEVELS[1]!.hp);
    // The headquarters caps gun levels on top of research.
    const g3 = baseGame(1e6, undefined, { ...b, hq: { level: 2, hp: HQ_LEVELS[2]!.hp } }).g;
    expect(g3.maxGunLevel('crossbow')).toBe(HQ_LEVELS[2]!.maxGun);
    // Laboratory level 3: two builders.
    b = { ...b, lab: { level: 2, hp: LAB_LEVELS[2]!.hp } };
    expect(builders(b)).toBe(2);
    // The laboratory is slow: its top levels take days.
    expect(LAB_LEVELS[4]!.seconds).toBeGreaterThanOrEqual(3 * 24 * 3600);
    // Destroyed, it is rebuilt at level 1, and that takes long.
    b = { ...b, lab: null };
    b = startJob(b, 'lab', 0);
    b = settleJobs(b, LAB_REBUILD.seconds * 1000);
    expect(b.lab).toEqual({ level: 0, hp: LAB_LEVELS[0]!.hp });
  });

  it('once the headquarters falls, what still stands sells at a reduced price', () => {
    const b = newBase();
    const invested = b.guns.reduce((s, x) => s + x.invested, 0);
    expect(lossSale(b)).toBe(Math.floor(invested * BASE_RULES.lossSale));
  });

  it('a broken save becomes a new base', () => {
    expect(sanitizeBase(null)).toEqual(newBase());
    expect(sanitizeBase({ hq: { level: 99, hp: 5 }, guns: [{ def: 'nope' }], attack: -3 }).attack).toBe(1);
  });

  it('the bot can play attacks one after another on the same base', () => {
    const c = new Campaign();
    c.wallet.gold = 400;
    c.prepare();
    expect(c.game.towers.length).toBeGreaterThan(2);
    const won = c.fight();
    expect(typeof won).toBe('boolean');
  });
});

/**
 * Attacks on the base, played by the bot one after another on the same base,
 * with gold coming in from the other modes between them (tests/helpers/baseBot.ts).
 * Held to: a new player loses the first attack; research and gold carry the
 * base further; the strength shown before an attack points the right way.
 */
/** Campaigns play many attacks; CI machines are slower than a laptop. */
const SLOW = 120_000;

describe('balance at the base', () => {
  const campaign = (stage: number, startGold: number, income: number, attacks: number) => {
    const c = new Campaign(upgrades(upTo(stage), TOWER_IDS));
    c.wallet.gold = startGold;
    const results: { attack: number; won: boolean; you: number; enemy: number }[] = [];
    for (let i = 0; i < attacks; i++) {
      c.wallet.gold += income;
      c.prepare();
      const attack = c.game.level;
      const you = defenceStrength(c.game);
      const enemy = attackStrength(attack, undefined, undefined, c.game.hq?.level ?? 0);
      const before = c.wallet.gold;
      const won = c.fight();
      c.wallet.gold += baseTakings(Math.max(0, c.wallet.gold - before), won, attack);
      results.push({ attack, won, you, enemy });
    }
    return results;
  };
  const furthest = (r: { attack: number; won: boolean }[]) => Math.max(0, ...r.filter((x) => x.won).map((x) => x.attack));

  it('a new player with the two starting crossbows and no gold loses the first attack', () => {
    expect(campaign(0, 0, 0, 1)[0]!.won).toBe(false);
  });

  it('the first research item and a little gold hold the first attack, but not the second', () => {
    expect(furthest(campaign(1, 200, 200, 6))).toBe(1);
  }, SLOW);

  it('more research and gold carry the base further', () => {
    expect(furthest(campaign(3, 300, 400, 10))).toBeGreaterThanOrEqual(5);
    expect(furthest(campaign(6, 500, 800, 10))).toBeGreaterThanOrEqual(10);
  }, SLOW);

  it('a stronger headquarters draws stronger attackers who pay more', () => {
    const at = (hq: number) => {
      const g = baseGame(0, undefined, { ...newBase(), hq: { level: hq, hp: HQ_LEVELS[hq]!.hp } }).g;
      g.startWave();
      for (let i = 0; i < 4000 && g.enemies.length < 12; i++) g.step(TICK);
      return g.enemies;
    };
    const low = at(0);
    const high = at(2);
    expect(high[0]!.maxHp).toBeCloseTo(low[0]!.maxHp * hqThreat(2), -1);
    const gold = (es: { reward: number }[]) => es.slice(0, 12).reduce((s, e) => s + e.reward, 0);
    expect(gold(high)).toBeGreaterThan(gold(low));
    expect(attackStrength(3, undefined, undefined, 2)).toBeGreaterThan(attackStrength(3));
    // More of them, and kinds that would come only later.
    const kinds = (hq: number) => new Set(waveSpec(1, 1, hq).groups.map((gr) => gr.enemy));
    const count = (hq: number) => waveSpec(1, 1, hq).groups.reduce((s, gr) => s + gr.count, 0);
    expect(kinds(2).size).toBeGreaterThan(kinds(0).size);
    expect(count(2)).toBeGreaterThan(count(0) * 1.3);
    for (const k of kinds(0)) expect(kinds(2).has(k)).toBe(true);
  });

  it('the strength shown before an attack points the right way when the sides are far apart', () => {
    const all = [...campaign(1, 200, 200, 4), ...campaign(3, 300, 400, 8)];
    for (const r of all) {
      if (r.you > 3 * r.enemy) expect(r.won, `attack ${r.attack}: ${r.you} vs ${r.enemy}`).toBe(true);
      if (r.enemy > 1.5 * r.you) expect(r.won, `attack ${r.attack}: ${r.you} vs ${r.enemy}`).toBe(false);
    }
  }, SLOW);
});
