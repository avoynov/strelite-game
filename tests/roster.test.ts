import { describe, expect, it } from 'vitest';
import { ENEMIES, TICK, TOWER_IDS, TOWERS, type EnemyId, type TowerId } from '../src/sim/content';
import { RESEARCH, upgrades } from '../src/sim/research';
import { Game, type GameEvent } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';
import type { WaveGroup } from '../src/sim/waves';

/** A game on the last map level (everything unlocked) whose first wave is exactly `groups`. */
function scenario(groups: Partial<WaveGroup>[], level = 8, done?: string[]): Game {
  const g = new Game(buildPathMap(MEADOW), {
    level,
    ...(done ? { upgrades: upgrades(done, TOWER_IDS) } : {}),
    waves: () => ({
      groups: groups.map((gr) => ({ enemy: 'infantry', count: 1, hp: ENEMIES[gr.enemy ?? 'infantry'].baseHp, interval: 1, delay: 0, reward: 1, ...gr })),
      clearBonus: 0,
    }),
  });
  g.money = 1e6;
  return g;
}

/** Build `def` with its footprint's corner as close as possible to (x, y). */
function buildNear(g: Game, def: TowerId, x: number, y: number): void {
  let best: [number, number] | null = null;
  for (let cy = 0; cy < 30; cy++) {
    for (let cx = 0; cx < 30; cx++) {
      if (!g.canBuildAt(def, cx, cy)) continue;
      if (!best || Math.hypot(cx - x, cy - y) < Math.hypot(best[0] - x, best[1] - y)) best = [cx, cy];
    }
  }
  expect(best).not.toBeNull();
  expect(g.build(def, best![0], best![1]).ok).toBe(true);
}

function play(g: Game, seconds: number): GameEvent[] {
  const events: GameEvent[] = [];
  for (let i = 0; i < seconds / TICK && g.phase !== 'lost'; i++) {
    g.step(TICK);
    events.push(...g.drainEvents());
  }
  return events;
}

describe('roster', () => {
  it('has the seven guns, five levels each, ordered light to heavy', () => {
    expect(TOWER_IDS).toEqual(['crossbow', 'scorpion', 'zis3', 'howitzer', 'greekfire', 'trebuchet', 'railgun']);
    for (const id of TOWER_IDS) {
      const levels = TOWERS[id].levels;
      expect(levels).toHaveLength(5);
      for (let i = 1; i < 5; i++) expect(levels[i]!.damage).toBeGreaterThan(levels[i - 1]!.damage);
    }
  });

  it('opens guns by research, starting with the crossbow and ZIS-3', () => {
    const open = (done: string[]) => TOWER_IDS.filter((id) => new Game(buildPathMap(MEADOW), { upgrades: upgrades(done, TOWER_IDS) }).isUnlocked(id));
    expect(open([])).toEqual(['crossbow', 'zis3']);
    expect(open(['gun.howitzer'])).toEqual(['crossbow', 'zis3', 'howitzer']);
    expect(open(RESEARCH.map((r) => r.id))).toHaveLength(7);
    const g = new Game(buildPathMap(MEADOW), { upgrades: upgrades([], TOWER_IDS) });
    expect(g.build('howitzer', 4, 0)).toEqual({ ok: false, reason: 'locked' });
  });
});

describe('armour', () => {
  it('turns crossbow bolts into scratches on a tank, but not on infantry', () => {
    const dealtPerShot = (enemy: EnemyId) => {
      const g = scenario([{ enemy, hp: 1e6 }]);
      buildNear(g, 'crossbow', 2, 4);
      g.startWave();
      const hits = play(g, 20).filter((e) => e.type === 'hit');
      expect(hits.length).toBeGreaterThan(5);
      return hits[0]!.type === 'hit' ? hits[0]!.dealt : 0;
    };
    expect(dealtPerShot('infantry')).toBeCloseTo(6);
    expect(dealtPerShot('tank')).toBeCloseTo(0.6); // 6 − 14, but never under a tenth
  });

  it('is ignored by the railgun, which hits everything on its line', () => {
    const g = scenario([{ enemy: 'tank', count: 4, hp: 1e6, interval: 1.5 }]);
    buildNear(g, 'railgun', 5, 3);
    g.startWave();
    const events = play(g, 60);
    const rail = events.find((e) => e.type === 'rail');
    expect(rail).toBeDefined();
    const hits = events.filter((e) => e.type === 'hit');
    for (const h of hits) if (h.type === 'hit') expect(h.dealt).toBe(TOWERS.railgun.levels[0].damage);
    // The first slug finds more than one tank in a row.
    const firstShotHits = events.slice(events.indexOf(rail!)).filter((e) => e.type === 'hit').length;
    expect(firstShotHits).toBeGreaterThan(1);
  });
});

describe('targeting', () => {
  it('research opens the crossbow\'s "most vulnerable" mode, which the player sets per gun', () => {
    const groups: Partial<WaveGroup>[] = [
      { enemy: 'truck', hp: 1e6 },
      { enemy: 'infantry', count: 6, hp: 1e5, interval: 0.4, delay: 0.6 },
    ];
    const kinds = (g: Game) => {
      const kindOf = new Map<number, EnemyId>();
      const hits: EnemyId[] = [];
      g.startWave();
      for (let i = 0; i < 14 / TICK; i++) {
        for (const e of g.enemies) kindOf.set(e.id, e.def);
        g.step(TICK);
        for (const ev of g.drainEvents()) if (ev.type === 'hit') hits.push(kindOf.get(ev.enemyId)!);
      }
      return hits;
    };
    // Without the research the crossbow has one mode, and cannot be switched.
    const plain = scenario(groups, 8, []);
    buildNear(plain, 'crossbow', 3, 3);
    expect(plain.aimModes('crossbow')).toEqual(['first']);
    expect(plain.setAim(plain.towers[0]!.id, 'weakest')).toEqual({ ok: false, reason: 'locked' });
    expect(kinds(plain)[0]).toBe('truck');
    // With it: set to the most vulnerable, it lets the tough truck by and shoots the soldiers.
    const g = scenario(groups, 8, ['lvl4.crossbow', 'aim.crossbow']);
    buildNear(g, 'crossbow', 3, 3);
    expect(g.aimModes('crossbow')).toEqual(['first', 'weakest']);
    expect(g.setAim(g.towers[0]!.id, 'weakest')).toEqual({ ok: true });
    const hits = kinds(g);
    expect(hits.length).toBeGreaterThan(5);
    expect(hits.filter((k) => k === 'infantry').length).toBeGreaterThan(hits.length * 0.8);
    // A new crossbow takes the mode the player last set.
    buildNear(g, 'crossbow', 12, 8);
    expect(g.aimOf(g.towers[1]!)).toBe('weakest');
  });

  it('ЗИС-3 prefers the most armoured target up to armour 10, then falls back to the first', () => {
    const g = scenario([
      { enemy: 'infantry', count: 12, hp: 40, interval: 0.6 },
      { enemy: 'apc', hp: 1e6, delay: 2 },
    ]);
    buildNear(g, 'zis3', 2, 4);
    g.startWave();
    const kindOf = new Map<number, EnemyId>();
    const hits: EnemyId[] = [];
    const t = g.towers[0]!;
    let apcSeen = false;
    for (let i = 0; i < 30 / TICK; i++) {
      for (const e of g.enemies) kindOf.set(e.id, e.def);
      // Stop once the APC has driven out of range again.
      const apc = g.enemies.find((e) => e.def === 'apc');
      const inRange = !!apc && Math.hypot(apc.x - t.x, apc.y - t.y) <= TOWERS.zis3.levels[0].range;
      if (inRange) apcSeen = true;
      else if (apcSeen) break;
      g.step(TICK);
      for (const ev of g.drainEvents()) if (ev.type === 'hit') hits.push(kindOf.get(ev.enemyId)!);
    }
    // Infantry first, while nothing armoured is in range…
    expect(hits[0]).toBe('infantry');
    // …then, once it has picked the APC, it stays on it although soldiers keep walking by.
    const firstApc = hits.indexOf('apc');
    expect(firstApc).toBeGreaterThan(0);
    expect(hits.slice(firstApc).every((k) => k === 'apc')).toBe(true);
  });

  it('keeps its target until it dies or leaves range', () => {
    const g = scenario([{ enemy: 'infantry', count: 8, hp: 1e6, interval: 0.3 }]);
    buildNear(g, 'trebuchet', 6, 1);
    const t = g.towers[0]!;
    g.startWave();
    let current = 0;
    let switches = 0;
    for (let i = 0; i < 40 / TICK; i++) {
      g.step(TICK);
      const target = g.enemies.find((e) => e.id === t.targetId);
      if (t.targetId && t.targetId !== current) {
        if (current && g.enemies.some((e) => e.id === current && Math.hypot(e.x - t.x, e.y - t.y) <= TOWERS.trebuchet.levels[0].range)) switches++;
        current = t.targetId;
      }
      if (target) expect(target.alive).toBe(true);
    }
    expect(switches).toBe(0);
  });

  it('the scorpion goes for drones first; ground-only guns never aim at them', () => {
    const g = scenario([
      { enemy: 'infantry', count: 5, hp: 30, interval: 0.3 },
      { enemy: 'drone', hp: 1e6, delay: 0.5 },
    ]);
    buildNear(g, 'scorpion', 3, 3);
    buildNear(g, 'howitzer', 9, 2);
    g.startWave();
    const [scorpion, howitzer] = g.towers;
    let scorpionOnDrone = false;
    for (let i = 0; i < 30 / TICK; i++) {
      g.step(TICK);
      const drone = g.enemies.find((e) => e.def === 'drone');
      if (drone && scorpion!.targetId === drone.id) scorpionOnDrone = true;
      if (drone) expect(howitzer!.targetId).not.toBe(drone.id);
    }
    expect(scorpionOnDrone).toBe(true);
  });

  it('the howitzer drops its shell on the thickest crowd', () => {
    const g = scenario([
      { enemy: 'truck', hp: 1e6 },
      { enemy: 'infantry', count: 10, hp: 1e6, interval: 0.15, delay: 3 },
    ]);
    buildNear(g, 'howitzer', 14, 14);
    g.startWave();
    const bursts = play(g, 40).filter((e) => e.type === 'burst');
    expect(bursts.length).toBeGreaterThan(1);
  });
});

describe('enemies', () => {
  it('drones fly straight to the goal and shells cannot touch them', () => {
    const g = scenario([{ enemy: 'drone', hp: 1e6 }]);
    buildNear(g, 'howitzer', 9, 2);
    g.startWave();
    play(g, 1);
    const d = g.enemies[0]!;
    const goal = g.map.goals[0]!;
    // Heading straight at the goal, not along the road.
    expect(Math.abs(Math.atan2(goal.y + 0.5 - d.y, goal.x + 0.5 - d.x) - d.heading)).toBeLessThan(0.05);
    const events = play(g, 60);
    expect(events.some((e) => e.type === 'hit')).toBe(false);
    expect(events.some((e) => e.type === 'leak')).toBe(true);
  });

  it('a destroyed APC drops four infantry where it stopped', () => {
    const g = scenario([{ enemy: 'apc', hp: 50 }]);
    buildNear(g, 'trebuchet', 6, 1);
    g.startWave();
    let dropped: { x: number; y: number }[] = [];
    let apcAt = { x: 0, y: 0 };
    for (let i = 0; i < 60 / TICK && !dropped.length; i++) {
      const apc = g.enemies.find((e) => e.def === 'apc');
      if (apc) apcAt = { x: apc.x, y: apc.y };
      g.step(TICK);
      dropped = g.enemies.filter((e) => e.def === 'infantry');
    }
    expect(dropped).toHaveLength(4);
    for (const e of dropped) expect(Math.hypot(e.x - apcAt.x, e.y - apcAt.y)).toBeLessThan(1.5);
  });

  it('riders surge and brake, so lobbed shells miss them far more than steady trucks', () => {
    const missRate = (enemy: EnemyId) => {
      const g = scenario([{ enemy, count: 30, hp: 1e6, interval: 2.5 }]);
      buildNear(g, 'trebuchet', 14, 8);
      g.startWave();
      const events = play(g, 120);
      const bursts = events.filter((e) => e.type === 'burst').length;
      const hits = events.filter((e) => e.type === 'hit').length;
      expect(bursts).toBeGreaterThan(5);
      return 1 - Math.min(1, hits / bursts);
    };
    expect(missRate('truck')).toBeLessThan(0.1);
    expect(missRate('moto')).toBeGreaterThan(0.3);
  });
});

describe('greek fire', () => {
  it('burns hotter the longer it stays on one target', () => {
    const g = scenario([{ enemy: 'truck', hp: 1e6 }]);
    buildNear(g, 'greekfire', 1, 4);
    const t = g.towers[0]!;
    g.startWave();
    const samples: number[] = [];
    let last = 0;
    for (let i = 0; i < 40 / TICK; i++) {
      g.step(TICK);
      if (t.firing) samples.push(t.stats.dealt - last);
      last = t.stats.dealt;
    }
    expect(samples.length).toBeGreaterThan(2 / TICK);
    // Truck armour 3, half pierced: 10/s at first (just over 7 through), about 70/s once hot.
    expect(samples[0]! / TICK).toBeLessThan(15);
    expect(samples[Math.round(2.5 / TICK)]! / TICK).toBeGreaterThan(60);
  });
});
