import { describe, expect, it } from 'vitest';
import { ENEMIES, TOWERS, TICK, gunHp } from '../src/sim/content';
import {
  BASE_MAP,
  BASE_RULES,
  BUILDING_KINDS,
  BUILDING_SPOTS,
  buildingHp,
  builders,
  gunJobSeconds,
  HQ_LEVELS,
  HQ_SPOT,
  inBuildArea,
  jobError,
  jobPrice,
  LAB_LEVELS,
  liberate,
  newBase,
  occupy,
  REBUILD_SECONDS,
  sanitizeBase,
  settleJobs,
  startJob,
  treasuryLoss,
  TREASURY_LEVELS,
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
  it('a new base: five buildings round the headquarters and two crossbows, all inside the area', () => {
    const { g } = baseGame();
    expect(g.hq).toMatchObject({ cx: HQ_SPOT[0], cy: HQ_SPOT[1], level: 0, hp: HQ_LEVELS[0]!.hp });
    expect(g.buildings.map((b) => b.kind).sort()).toEqual([...BUILDING_KINDS].sort());
    for (const k of BUILDING_KINDS) {
      const [x, y] = BUILDING_SPOTS[k];
      expect(g.buildingAt(x + 1, y + 1)?.kind).toBe(k);
      expect(inBuildArea(0, x, y, 2)).toBe(true);
    }
    expect(g.towers.map((t) => t.def)).toEqual(['crossbow', 'crossbow']);
    for (const t of g.towers) expect(inBuildArea(0, t.cx, t.cy, t.size)).toBe(true);
  });

  it('spends from the treasury; building a gun takes a builder and real time, a fence goes up at once', () => {
    const { g, clock, wallet } = baseGame(1000);
    const [hx, hy] = HQ_SPOT;
    expect(g.build('zis3', hx - 5, hy - 1).ok).toBe(true);
    expect(wallet.gold).toBe(1000 - TOWERS.zis3.levels[0].cost);
    const t = g.towerAt(hx - 5, hy - 1)!;
    expect(t.job?.kind).toBe('build');
    // One builder at the start: the next gun waits.
    expect(g.build('crossbow', hx - 6, hy + 1)).toEqual({ ok: false, reason: 'noBuilder' });
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

  it('the fortress makes for the headquarters; when it falls the battle is lost and the army holds it', () => {
    const { g } = baseGame(0, () => only('fortress', 2, 50000));
    for (const t of [...g.towers]) g.sell(t.id);
    g.startWave();
    for (let i = 0; i < 900 / TICK && g.phase === 'wave'; i++) g.step(TICK);
    expect(g.phase).toBe('lost');
    expect(g.hqFell).toBe(true);
    expect(g.hq!.hp).toBe(0);
    expect(g.survivors().length).toBe(2);
    expect(g.lives).toBeGreaterThan(0); // the base counts its buildings, not lives
  });

  it('each enemy goes for its own kind of target', () => {
    const goals = (enemy: keyof typeof ENEMIES) => {
      const { g } = baseGame(1000, () => only(enemy, 1, 1e6));
      expect(g.buildFence(HQ_SPOT[0] - 1, HQ_SPOT[1] - 2).ok).toBe(true);
      g.startWave();
      for (let i = 0; i < 2 / TICK; i++) g.step(TICK);
      const e = g.enemies[0]!;
      const s = [...g.buildings, ...g.towers, ...g.fences].find((x) => x.id === e.goal)!;
      return 'kind' in s ? s.kind : 'gun';
    };
    expect(goals('moto')).toBe('treasury');
    expect(goals('fortress')).toBe('hq');
    expect(goals('tank')).toBe('gun');
    expect(goals('apc')).toBe('gun');
    expect(goals('drone')).toBe('gun');
    expect(goals('truck')).toBe('fence');
  });

  it('bikers reach and wreck the treasury; it loses a share of the gold its vault does not protect', () => {
    const { g } = baseGame(0, () => only('moto', 12, 50000));
    for (const t of [...g.towers]) g.sell(t.id);
    g.startWave();
    let wrecked = false;
    for (let i = 0; i < 900 / TICK && g.phase === 'wave' && !wrecked; i++) {
      g.step(TICK);
      wrecked = g.drainEvents().some((e) => e.type === 'wrecked' && e.building === 'treasury');
    }
    expect(wrecked).toBe(true);
    expect(g.stands('treasury')).toBe(false);
    // Ruins stay where they stood: nothing new goes there.
    const [tx, ty] = BUILDING_SPOTS.treasury;
    expect(g.buildingAt(tx, ty)?.hp).toBe(0);
    expect(g.placementError('crossbow', tx, ty)).not.toBeNull();
    const b = newBase();
    const protect = TREASURY_LEVELS[0]!.protect;
    expect(treasuryLoss(b, protect)).toBe(0);
    expect(treasuryLoss(b, protect + 1000)).toBe(Math.floor(1000 * BASE_RULES.treasuryLoss));
  });

  it('sappers blow up the fences and themselves', () => {
    const { g } = baseGame(1000, () => only('truck', 1, 1e6));
    for (let d = -6; d <= 6; d++) g.buildFence(HQ_SPOT[0] - 6, HQ_SPOT[1] + d);
    const before = g.fences.length;
    g.startWave();
    let blast = false;
    for (let i = 0; i < 300 / TICK && !blast; i++) {
      g.step(TICK);
      blast = g.drainEvents().some((e) => e.type === 'blast');
    }
    expect(blast).toBe(true);
    expect(g.enemies.length).toBe(0);
    expect(g.fences.length).toBeLessThan(before);
  });

  it('a wrecked gun stays as a wreck: it does not fire and is rebuilt by a builder', () => {
    const { g } = baseGame(1000, () => only('tank', 3, 1e6));
    g.hq!.hp = g.hq!.maxHp = 1e9;
    g.startWave();
    for (let i = 0; i < 900 / TICK && g.phase === 'wave' && !g.towers.some((t) => t.hp <= 0); i++) g.step(TICK);
    const w = g.towers.find((t) => t.hp <= 0)!;
    expect(w).toBeDefined();
    expect(g.towerAt(w.cx, w.cy)).toBe(w);
    expect(g.upgrade(w.id)).toEqual({ ok: false, reason: 'wreck' });
    const { g: peace, wallet, clock } = baseGame(1000, undefined, sanitizeBase(JSON.parse(JSON.stringify({ ...newBase(), ...g.snapshot() }))));
    const wreck = peace.towers.find((t) => t.hp <= 0)!;
    expect(wreck).toBeDefined();
    const cost = peace.rebuildCost(wreck);
    expect(peace.rebuildGun(wreck.id).ok).toBe(true);
    expect(wallet.gold).toBe(1000 - cost);
    expect(wreck.job?.kind).toBe('repair');
    clock.ms += gunJobSeconds(wreck.def, wreck.level) * 1000;
    peace.step(TICK);
    expect(wreck.hp).toBe(wreck.maxHp);
    expect(wreck.job).toBeUndefined();
  });

  it('the battle is lost once half the base by value is destroyed, the headquarters standing or not', () => {
    const { g } = baseGame(0, () => only('infantry', 1, 1e6));
    g.startWave();
    const hit = (g as unknown as { hitStructure(s: unknown, d: number): void }).hitStructure.bind(g);
    hit(g.building('lab'), 1e9);
    hit(g.building('arsenal'), 1e9);
    expect(g.phase).toBe('wave');
    hit(g.building('muster'), 1e9);
    hit(g.building('treasury'), 1e9);
    expect(g.phase).toBe('lost');
    expect(g.hqFell).toBe(false);
    expect(g.lostShare()).toBeGreaterThanOrEqual(BASE_RULES.lossShare);
  });

  it('a ruined arsenal sends no new guns to the base', () => {
    const b = newBase();
    b.buildings.arsenal.hp = 0;
    const { g } = baseGame(1000, undefined, b);
    expect(g.build('crossbow', HQ_SPOT[0] - 4, HQ_SPOT[1]).ok).toBe(false);
  });

  it('the held headquarters is won back in a battle against the army that took it; it comes back a level lower', () => {
    let b = newBase();
    b = { ...b, buildings: { ...b.buildings, hq: { level: 2, hp: buildingHp('hq', 2) } } };
    b = occupy(b, [{ def: 'infantry', hp: 10, maxHp: 20, reward: 1 }, { def: 'infantry', hp: 20, maxHp: 20, reward: 1 }]);
    expect(jobError(b, 'hq', 1e9)).toBe('occupied');
    const { g } = baseGame(1000, undefined, b);
    expect(g.retake).toBe(true);
    expect(g.totalWaves).toBe(1);
    g.startWave();
    for (let i = 0; i < 300 / TICK && g.phase === 'wave'; i++) g.step(TICK);
    expect(g.phase).toBe('won');
    const back = liberate(b);
    expect(back.occupied).toBeNull();
    expect(back.buildings.hq).toEqual({ level: 1, hp: buildingHp('hq', 1) });
    expect(back.buildings.muster.level).toBe(1);
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
    expect(b.buildings.hq.level).toBe(1);
    expect(jobError(b, 'lab', 1e9)).toBeNull();
    b = startJob(b, 'lab', 0);
    expect(jobError(b, 'hq', 1e9)).toBe('noBuilder');
    b = { ...b, jobs: [] };
    expect(b.buildings.hq.hp).toBe(HQ_LEVELS[1]!.hp);
    // The muster and the arsenal grow with it.
    expect(b.buildings.muster.level).toBe(1);
    expect(b.buildings.arsenal.level).toBe(1);
    // The headquarters caps gun levels on top of research.
    const g3 = baseGame(1e6, undefined, { ...b, buildings: { ...b.buildings, hq: { level: 2, hp: HQ_LEVELS[2]!.hp } } }).g;
    expect(g3.maxGunLevel('crossbow')).toBe(HQ_LEVELS[2]!.maxGun);
    // Laboratory level 3: two builders.
    b = { ...b, buildings: { ...b.buildings, lab: { level: 2, hp: LAB_LEVELS[2]!.hp } } };
    expect(builders(b)).toBe(2);
    // The laboratory is slow: its top levels take days.
    expect(LAB_LEVELS[4]!.seconds).toBeGreaterThanOrEqual(3 * 24 * 3600);
    // Destroyed, it keeps its level and is rebuilt in a time that grows with it.
    b = { ...b, buildings: { ...b.buildings, lab: { level: 2, hp: 0 } } };
    expect(jobPrice(b, 'lab')?.kind).toBe('rebuild');
    b = startJob(b, 'lab', 0);
    b = settleJobs(b, REBUILD_SECONDS[2] * 1000);
    expect(b.buildings.lab).toEqual({ level: 2, hp: LAB_LEVELS[2]!.hp });
    // The muster is rebuilt for free, with no builder.
    b = { ...b, jobs: [], buildings: { ...b.buildings, muster: { level: 1, hp: 0 } } };
    expect(jobPrice(b, 'muster')?.cost).toBe(0);
    b = startJob(b, 'treasury', 0);
    b = startJob(b, 'lab', 0);
    expect(jobError(b, 'muster', 0)).toBeNull();
  });

  it('older saves (headquarters and laboratory only) carry over', () => {
    const old = { attack: 3, hq: { level: 1, hp: 500 }, lab: null, guns: [], fences: [], jobs: [{ what: 'lab', endsAt: 5 }] };
    const b = sanitizeBase(old);
    expect(b.attack).toBe(3);
    expect(b.buildings.hq).toEqual({ level: 1, hp: 500 });
    expect(b.buildings.lab.hp).toBe(0);
    expect(b.buildings.muster.level).toBe(1);
    expect(b.jobs).toEqual([{ what: 'lab', kind: 'rebuild', endsAt: 5 }]);
    expect(b.occupied).toBeNull();
  });

  it('a broken save becomes a new base', () => {
    expect(sanitizeBase(null)).toEqual(newBase());
    expect(sanitizeBase({ hq: { level: 99, hp: 5 }, guns: [{ def: 'nope' }], attack: -3 }).attack).toBe(1);
    expect(sanitizeBase({ buildings: { hq: { level: 0, hp: 0 } } }).buildings.hq.hp).toBe(HQ_LEVELS[0]!.hp);
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
    const results: { attack: number; won: boolean; you: number; enemy: number; retake: boolean }[] = [];
    for (let i = 0; i < attacks; i++) {
      c.wallet.gold += income;
      c.prepare();
      const attack = c.game.level;
      const you = defenceStrength(c.game);
      const enemy = attackStrength(attack, undefined, undefined, c.game.hq?.level ?? 0);
      const before = c.wallet.gold;
      const retake = c.game.retake;
      const won = c.fight();
      if (process.env.BALANCE_LOG) console.log(`  ${retake ? 'retake' : 'attack'} ${attack} ${won ? 'won' : 'lost'} fell=${c.base.occupied ? c.base.occupied.length : '-'} you=${you} enemy=${enemy} gold=${c.wallet.gold} hq=${c.base.buildings.hq.level} guns=${c.base.guns.filter((x) => x.hp > 0).length}/${c.base.guns.length} ruins=${Object.entries(c.base.buildings).filter(([, b]) => b.hp <= 0).map(([k]) => k).join(',')}`);
      c.wallet.gold += baseTakings(Math.max(0, c.wallet.gold - before), won, attack);
      results.push({ attack, won, you, enemy, retake });
    }
    if (process.env.BALANCE_LOG) console.log(stage, results.map((r) => `${r.attack}${r.won ? '+' : '-'}`).join(' '));
    return results;
  };
  const furthest = (r: { attack: number; won: boolean; retake: boolean }[]) => Math.max(0, ...r.filter((x) => x.won && !x.retake).map((x) => x.attack));

  it('a new player with the two starting crossbows and no gold loses the first attack', () => {
    expect(campaign(0, 0, 0, 1)[0]!.won).toBe(false);
  });

  it('the first research item and a little gold hold the first attack, but not the second at the first try', () => {
    const r = campaign(1, 200, 200, 6).filter((x) => !x.retake);
    expect(r[0]).toMatchObject({ attack: 1, won: true });
    expect(r[1]).toMatchObject({ attack: 2, won: false });
  }, SLOW);

  it('more research and gold carry the base further', () => {
    expect(furthest(campaign(3, 300, 400, 10))).toBeGreaterThanOrEqual(3);
    expect(furthest(campaign(6, 500, 800, 10))).toBeGreaterThanOrEqual(7);
  }, SLOW);

  it('a stronger headquarters draws stronger attackers who pay more', () => {
    const at = (hq: number) => {
      const g = baseGame(0, undefined, { ...newBase(), buildings: { ...newBase().buildings, hq: { level: hq, hp: HQ_LEVELS[hq]!.hp } } }).g;
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
    for (const r of all.filter((x) => !x.retake)) {
      if (r.you > 3 * r.enemy) expect(r.won, `attack ${r.attack}: ${r.you} vs ${r.enemy}`).toBe(true);
      if (r.enemy > 1.5 * r.you) expect(r.won, `attack ${r.attack}: ${r.you} vs ${r.enemy}`).toBe(false);
    }
  }, SLOW);
});
