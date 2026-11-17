import { describe, expect, it } from 'vitest';
import { ECONOMY, ENEMIES, FENCE_LEVELS, TICK } from '../src/sim/content';
import { Game } from '../src/sim/game';
import { levelArcMap } from '../src/sim/levels';
import { buildArcMap } from '../src/sim/maps';
import type { WaveSpec } from '../src/sim/waves';
import { run } from './helpers/bot';

const siege = (level = 1, waves?: (n: number) => WaveSpec) => new Game(buildArcMap(levelArcMap(level), 'siege'), { level, ...(waves ? { waves } : {}) });
const only = (enemy: keyof typeof ENEMIES, count: number, hp = 50): WaveSpec => ({ groups: [{ enemy, count, hp, interval: 0.8, delay: 0, reward: 1 }], clearBonus: 0 });

/** A closed ring of fences two tiles out from the goal; returns how many were built. */
function ring(g: Game, out = 2): number {
  const [gx, gy] = levelArcMap(g.level).goal;
  let n = 0;
  for (let y = gy - out; y <= gy + 1 + out; y++) {
    for (let x = gx - out; x <= gx + 1 + out; x++) {
      const edge = x === gx - out || x === gx + 1 + out || y === gy - out || y === gy + 1 + out;
      if (edge && g.buildFence(x, y).ok) n++;
    }
  }
  return n;
}

describe('siege mode', () => {
  it('a fence costs 10 gold, upgrades to stone and steel, each tougher', () => {
    const g = siege();
    g.money = 1000;
    const [gx, gy] = levelArcMap(1).goal;
    expect(g.buildFence(gx - 3, gy).ok).toBe(true);
    expect(g.money).toBe(1000 - FENCE_LEVELS[0].cost);
    expect(FENCE_LEVELS[0].cost).toBe(10);
    const f = g.fenceAt(gx - 3, gy)!;
    expect(g.upgradeFence(f.id).ok).toBe(true);
    expect(g.upgradeFence(f.id).ok).toBe(true);
    expect(f.maxHp).toBe(FENCE_LEVELS[2].hp);
    expect(g.upgradeFence(f.id)).toEqual({ ok: false, reason: 'maxLevel' });
    expect(FENCE_LEVELS[1].hp).toBeGreaterThan(FENCE_LEVELS[0].hp);
    expect(FENCE_LEVELS[2].hp).toBeGreaterThan(FENCE_LEVELS[1].hp);
    // Nothing else can stand on it.
    expect(g.canBuildAt('crossbow', gx - 3, gy)).toBe(false);
  });

  it('fences may close the way completely, and infantry breaks through', () => {
    const g = siege(1, () => only('infantry', 6));
    g.money = 1000;
    expect(ring(g)).toBeGreaterThan(15);
    const before = g.fences.length;
    g.startWave();
    run(g, 200);
    expect(g.fences.length).toBeLessThan(before);
    expect(g.lives).toBeLessThan(ECONOMY.startLives);
  });

  it('units that only pass by go round through a gap, however far', () => {
    const g = siege(1, () => only('truck', 3, 30000));
    g.money = 1000;
    ring(g);
    const [gx, gy] = levelArcMap(1).goal;
    // Open one gap on the far side.
    g.sellFence(g.fenceAt(gx + 3, gy + 1)!.id);
    const before = g.fences.length;
    g.startWave();
    run(g, 200);
    expect(g.fences.length).toBe(before);
    expect(g.lives).toBe(ECONOMY.startLives - 3 * ENEMIES.truck.leakDamage);
  });

  it('each kind follows a gap only up to its own detour: infantry goes round, tanks break through', () => {
    const [gx, gy] = levelArcMap(1).goal;
    const result = (kind: 'infantry' | 'tank') => {
      const g = siege(1, () => only(kind, 1, 30000));
      g.money = 1000;
      ring(g, 4);
      // A gap low in the left side: from the top-left that is three tiles past the goal and back.
      g.sellFence(g.fenceAt(gx - 4, gy + 4)!.id);
      const before = g.fences.length;
      g.startWave();
      run(g, 300);
      expect(g.lives, kind).toBeLessThan(ECONOMY.startLives);
      return before - g.fences.length;
    };
    expect(result('infantry')).toBe(0);
    expect(result('tank')).toBeGreaterThan(0);
  });

  it('infantry shoots guns it passes and wrecks them; a wrecked gun is gone', () => {
    const g = siege(1, () => only('infantry', 30, 30000));
    g.money = 1000;
    const [gx, gy] = levelArcMap(1).goal;
    expect(g.build('crossbow', gx - 2, gy - 2).ok).toBe(true);
    g.startWave();
    const events: string[] = [];
    for (let i = 0; i < 200 / TICK && g.phase === 'wave'; i++) {
      g.step(TICK);
      for (const e of g.drainEvents()) events.push(e.type);
    }
    expect(events).toContain('strike');
    expect(events).toContain('wrecked');
    expect(g.towers.length).toBe(0);
  });

  it('trucks, riders and drones never strike guns', () => {
    for (const kind of ['truck', 'moto', 'drone'] as const) {
      const g = siege(5, () => only(kind, 10, 30000));
      g.money = 1000;
      const [gx, gy] = levelArcMap(5).goal;
      g.build('crossbow', gx - 2, gy - 2);
      g.startWave();
      run(g, 120);
      expect(g.towers[0]!.hp, kind).toBe(g.towers[0]!.maxHp);
    }
  });

  it('a gun gets sturdier with each level', () => {
    const g = siege();
    g.money = 1000;
    const [gx, gy] = levelArcMap(1).goal;
    g.build('zis3', gx - 4, gy - 4);
    const t = g.towers[0]!;
    const hp = t.maxHp;
    g.upgrade(t.id);
    expect(t.maxHp).toBeGreaterThan(hp);
    expect(t.hp).toBe(t.maxHp);
  });

  it('flyers ignore fences', () => {
    const g = siege(3, () => only('drone', 3, 30000));
    g.money = 1000;
    ring(g);
    const before = g.fences.length;
    g.startWave();
    run(g, 120);
    expect(g.fences.length).toBe(before);
    expect(g.lives).toBe(ECONOMY.startLives - 3);
  });
});
