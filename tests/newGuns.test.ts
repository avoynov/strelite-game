import { describe, expect, it } from 'vitest';
import { ENEMIES, TICK, TOWER_IDS, TOWERS, type TowerId } from '../src/sim/content';
import { upgrades } from '../src/sim/research';
import { Game, type GameEvent } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';
import type { WaveGroup } from '../src/sim/waves';

/** A game on a late map level (everything unlocked) whose first wave is exactly `groups`. */
function scenario(groups: Partial<WaveGroup>[], done?: string[]): Game {
  const g = new Game(buildPathMap(MEADOW), {
    level: 8,
    ...(done ? { upgrades: upgrades(done, TOWER_IDS) } : {}),
    waves: () => ({
      groups: groups.map((gr) => ({ enemy: 'infantry', count: 1, hp: ENEMIES[gr.enemy ?? 'infantry'].baseHp, interval: 1, delay: 0, reward: 1, ...gr })),
      clearBonus: 0,
    }),
  });
  g.money = 1e6;
  return g;
}

function buildNear(g: Game, def: TowerId, x: number, y: number): number {
  let best: [number, number] | null = null;
  for (let cy = 0; cy < 30; cy++) {
    for (let cx = 0; cx < 30; cx++) {
      if (!g.canBuildAt(def, cx, cy)) continue;
      if (!best || Math.hypot(cx - x, cy - y) < Math.hypot(best[0] - x, best[1] - y)) best = [cx, cy];
    }
  }
  expect(best).not.toBeNull();
  expect(g.build(def, best![0], best![1]).ok).toBe(true);
  return g.towers[g.towers.length - 1]!.id;
}

function play(g: Game, seconds: number, each?: () => void): GameEvent[] {
  const events: GameEvent[] = [];
  for (let i = 0; i < seconds / TICK && g.phase !== 'lost'; i++) {
    g.step(TICK);
    events.push(...g.drainEvents());
    each?.();
  }
  return events;
}

const hits = (ev: GameEvent[]) => ev.filter((e): e is Extract<GameEvent, { type: 'hit' }> => e.type === 'hit');

describe('new guns', () => {
  it('dazzle lamp: stuns what is in its cone and deals no damage at first', () => {
    const g = scenario([{ enemy: 'truck', count: 3, hp: 1e5, interval: 0.6 }]);
    buildNear(g, 'flasher', 4, 2);
    g.startWave();
    let stunned = 0;
    const ev = play(g, 40, () => {
      if (g.enemies.some((e) => e.alive && e.stun > 0)) stunned++;
    });
    expect(ev.some((e) => e.type === 'flash')).toBe(true);
    expect(stunned).toBeGreaterThan(0);
    expect(hits(ev)).toHaveLength(0);
  });

  it('rockets only shoot at flyers', () => {
    const ground = scenario([{ enemy: 'truck', count: 3, hp: 1e5 }]);
    buildNear(ground, 'rockets', 4, 2);
    ground.startWave();
    expect(play(ground, 30).some((e) => e.type === 'shot')).toBe(false);
    const air = scenario([{ enemy: 'drone', count: 3, hp: 1e5 }]);
    buildNear(air, 'rockets', 4, 2);
    air.startWave();
    expect(hits(play(air, 30)).length).toBeGreaterThan(0);
  });

  it('devil\'s glass and the soul-ripper cut through any armour by share of health', () => {
    for (const id of ['glass', 'harpoon'] as const) {
      const g = scenario([{ enemy: 'tank', hp: 20000 }]);
      buildNear(g, id, 4, 2);
      g.startWave();
      play(g, 40);
      const tank = g.enemies.find((e) => e.def === 'tank');
      // A plain gun barely scratches armour 14; these take a share of its health.
      expect(tank ? tank.hp : 0, id).toBeLessThan(20000 * 0.8);
    }
  });

  it('ricochet: a disc bounces on to further enemies', () => {
    const g = scenario([{ enemy: 'infantry', count: 8, hp: 1e5, interval: 0.3 }]);
    buildNear(g, 'ricochet', 4, 2);
    g.startWave();
    expect(play(g, 40).some((e) => e.type === 'bounce')).toBe(true);
  });

  it('steel bees: a burst of many darts, then a pause', () => {
    const g = scenario([{ enemy: 'infantry', count: 20, hp: 1e5, interval: 0.3 }]);
    const id = buildNear(g, 'bees', 4, 2);
    g.startWave();
    const shots = play(g, 3.5).filter((e) => e.type === 'shot' && e.towerId === id);
    expect(shots.length).toBeGreaterThanOrEqual(TOWERS.bees.levels[0].darts!);
    expect(shots.length).toBeLessThanOrEqual(2 * TOWERS.bees.levels[0].darts!);
  });

  it('tailspear locks on to the rearmost enemy in range', () => {
    const g = scenario([{ enemy: 'truck', count: 8, hp: 1e5, interval: 0.5 }]);
    const id = buildNear(g, 'zadnoper', 6, 2);
    g.startWave();
    let last = 0;
    let locks = 0;
    play(g, 40, () => {
      const t = g.towerById(id)!;
      if (!t.targetId || t.targetId === last) return;
      last = t.targetId;
      const target = g.enemies.find((e) => e.id === t.targetId)!;
      const inRange = g.enemies.filter((e) => e.alive && Math.hypot(e.x - t.x, e.y - t.y) <= g.levelOf(t).range);
      // A new lock: nothing in range is further from the goal than it (later trucks are further back).
      expect(inRange.every((e) => e.id <= target.id)).toBe(true);
      locks++;
    });
    expect(locks).toBeGreaterThan(1);
  });

  it('tarkan gun: every gun has a name and the sure-kill gun finishes what it starts', () => {
    for (const id of TOWER_IDS) expect(TOWERS[id].levels).toHaveLength(5);
    const g = scenario([{ enemy: 'infantry', count: 6, hp: 30, interval: 0.5 }]);
    buildNear(g, 'tarkan', 4, 2);
    g.startWave();
    const ev = play(g, 40);
    expect(ev.filter((e) => e.type === 'kill').length).toBeGreaterThan(3);
  });
});
