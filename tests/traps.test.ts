import { describe, expect, it } from 'vitest';
import { ENEMIES, TICK, TOWER_IDS } from '../src/sim/content';
import { RESEARCH, RESEARCH_SETS, upgrades } from '../src/sim/research';
import { Game, type GameEvent } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';
import { trapCap, TRAPS } from '../src/sim/traps';
import { newBase, sanitizeBase } from '../src/sim/base';
import type { WaveGroup } from '../src/sim/waves';

function scenario(groups: Partial<WaveGroup>[], opts: { hqLevel?: number; done?: string[] } = {}): Game {
  const g = new Game(buildPathMap(MEADOW), {
    level: 8,
    hqLevel: opts.hqLevel,
    ...(opts.done ? { upgrades: upgrades(opts.done, TOWER_IDS) } : {}),
    waves: () => ({
      groups: groups.map((gr) => ({ enemy: 'infantry', count: 1, hp: ENEMIES[gr.enemy ?? 'infantry'].baseHp, interval: 1, delay: 0, reward: 1, ...gr })),
      clearBonus: 0,
    }),
    totalWaves: 3,
  });
  g.money = 1e5;
  return g;
}

/** A road cell some way along the way, so a trap there is met by everyone. */
function roadCell(g: Game, along = 0.4): { x: number; y: number } {
  const road: { x: number; y: number; d: number }[] = [];
  const { grid } = g.map;
  for (let y = 0; y < grid.rows; y++) for (let x = 0; x < grid.cols; x++) if (grid.get(x, y) === 'path') road.push({ x, y, d: g.flow.distanceAt(x, y) });
  road.sort((a, b) => b.d - a.d);
  return road[Math.floor(road.length * along)]!;
}

function play(g: Game, seconds: number, each?: () => void): GameEvent[] {
  const ev: GameEvent[] = [];
  for (let i = 0; i < seconds / TICK && g.phase !== 'lost' && g.phase !== 'won'; i++) {
    g.step(TICK);
    ev.push(...g.drainEvents());
    each?.();
  }
  return ev;
}

describe('traps', () => {
  it('the headquarters decides which traps there are and how many', () => {
    expect([0, 1, 2, 3, 4, 5, 6, 7, 8].map(trapCap)).toEqual([0, 1, 1, 2, 2, 3, 3, 4, 5]);
    const g = scenario([], { hqLevel: 1 });
    const c = roadCell(g);
    expect(g.buildTrap('pit', c.x, c.y)).toEqual({ ok: false, reason: 'trapHq' });
    expect(g.buildTrap('mine', c.x, c.y).ok).toBe(true);
    const c2 = roadCell(g, 0.6);
    expect(g.buildTrap('mine', c2.x, c2.y)).toEqual({ ok: false, reason: 'trapCap' });
  });

  it('in path mode they go on the road only', () => {
    const g = scenario([]);
    const { grid } = g.map;
    let off: { x: number; y: number } | null = null;
    for (let y = 0; y < grid.rows && !off; y++) for (let x = 0; x < grid.cols && !off; x++) if (grid.get(x, y) === 'build') off = { x, y };
    expect(g.buildTrap('mine', off!.x, off!.y)).toEqual({ ok: false, reason: 'notBuildable' });
  });

  it('a mine blows up a group; a spent trap re-arms itself between waves for part of its price', () => {
    const g = scenario([{ enemy: 'infantry', count: 4, hp: 200, interval: 0.15 }]);
    const c = roadCell(g);
    g.buildTrap('mine', c.x, c.y);
    const money = g.money;
    g.startWave();
    const ev = play(g, 60);
    expect(ev.filter((e) => e.type === 'trap')).toHaveLength(1);
    expect(ev.filter((e) => e.type === 'kill').length).toBeGreaterThanOrEqual(2);
    // Cleared: re-armed for the recharge price (kill gold came in too).
    expect(g.traps[0]!.armed).toBe(true);
    const gold = ev.filter((e) => e.type === 'kill').reduce((s, e) => s + (e.type === 'kill' ? e.reward : 0), 0);
    expect(g.money).toBe(money + gold - TRAPS.mine.recharge);
  });

  it('with the switch off a spent trap waits to be re-armed by hand', () => {
    const g = scenario([{ enemy: 'infantry', count: 1, hp: 10 }]);
    g.trapAuto = false;
    const c = roadCell(g);
    g.buildTrap('pit', c.x, c.y);
    g.startWave();
    play(g, 60);
    const tr = g.traps[0]!;
    expect(tr.armed).toBe(false);
    expect(g.rechargeTrap(tr.id).ok).toBe(true);
    expect(tr.armed).toBe(true);
  });

  it('a leg trap holds a unit on foot; flyers pass over everything', () => {
    const g = scenario([{ enemy: 'moto', count: 1, hp: 1e5 }]);
    const c = roadCell(g);
    g.buildTrap('leg', c.x, c.y);
    g.startWave();
    let held = 0;
    play(g, 30, () => {
      if (g.enemies.some((e) => (e.held ?? 0) > 0)) held++;
    });
    expect(held * TICK).toBeGreaterThan(2.5);
    const air = scenario([{ enemy: 'drone', count: 3, hp: 1e5 }]);
    const ca = roadCell(air);
    air.buildTrap('mine', ca.x, ca.y);
    air.startWave();
    expect(play(air, 40).some((e) => e.type === 'trap')).toBe(false);
  });

  it('tar slows everyone in its patch', () => {
    const g = scenario([{ enemy: 'truck', count: 5, hp: 1e5, interval: 0.4 }]);
    const c = roadCell(g);
    g.buildTrap('tar', c.x, c.y);
    g.startWave();
    let slowed = 0;
    play(g, 30, () => {
      for (const e of g.enemies) if ((e.tarred ?? 0) > 0) slowed++;
    });
    expect(slowed).toBeGreaterThan(30);
  });

  it('research: each trap level adds 60%; the mine has a level IV; the set has every trap research', () => {
    const u = upgrades(['trap.mine.2', 'trap.mine.3'], TOWER_IDS);
    expect(u.traps.mine).toBeCloseTo(2.2);
    expect(u.traps.pit).toBe(1);
    expect(u.trapLevels.mine).toBe(3);
    const four = upgrades(['trap.mine.2', 'trap.mine.3', 'trap.mine.4'], TOWER_IDS);
    expect(four.traps.mine).toBeCloseTo(2.8);
    expect(four.trapLevels).toMatchObject({ mine: 4, pit: 1 });
    expect(RESEARCH.find((r) => r.id === 'trap.mine.4')!.requires).toEqual(['trap.mine.3']);
    const set = RESEARCH_SETS.find((s) => s.id === 'traps')!;
    expect(set.items).toEqual(RESEARCH.filter((r) => r.branch === 'traps').map((r) => r.id));
    expect(set.items).toContain('fx.tar');
  });

  it('the base keeps its traps, spent ones too', () => {
    const saved = sanitizeBase(JSON.parse(JSON.stringify({ ...newBase(), traps: [{ kind: 'mine', cx: 20, cy: 25, armed: false }, { kind: 'nope', cx: 1, cy: 1 }] })));
    expect(saved.traps).toEqual([{ kind: 'mine', cx: 20, cy: 25, armed: false }]);
  });
});
