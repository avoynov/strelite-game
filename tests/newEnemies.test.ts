import { describe, expect, it } from 'vitest';
import { ENEMIES, TICK, TOWER_IDS, type EnemyId } from '../src/sim/content';
import { Game, type Enemy, type GameEvent } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';
import type { WaveGroup } from '../src/sim/waves';
import { upgrades } from '../src/sim/research';

function scenario(groups: Partial<WaveGroup>[]): Game {
  const g = new Game(buildPathMap(MEADOW), {
    level: 80,
    upgrades: upgrades([], TOWER_IDS),
    waves: () => ({
      groups: groups.map((gr) => ({ enemy: 'infantry', count: 1, hp: ENEMIES[gr.enemy ?? 'infantry'].baseHp, interval: 1, delay: 0, reward: 1, ...gr })),
      clearBonus: 0,
    }),
    totalWaves: 2,
  });
  g.money = 1e5;
  return g;
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

const of = (g: Game, def: EnemyId): Enemy[] => g.enemies.filter((e) => e.alive && e.def === def);

describe('new enemies', () => {
  it('a repair wagon mends the machines round it and keeps behind the one ahead', () => {
    const g = scenario([
      { enemy: 'tank', hp: 1000 },
      { enemy: 'wagon', hp: 1000, delay: 1.2 },
    ]);
    g.startWave();
    play(g, 3);
    const tank = of(g, 'tank')[0]!;
    tank.hp = 500;
    let healed = 0;
    let passed = false;
    play(g, 20, () => {
      const w = of(g, 'wagon')[0];
      if (w && tank.alive && w.remaining < tank.remaining - 0.05) passed = true;
      healed = tank.hp;
    });
    expect(healed).toBeGreaterThan(500);
    expect(passed).toBe(false);
  });

  it('a shield-bearer armours what is close behind it, and the column never passes it', () => {
    const g = scenario([
      { enemy: 'shield', hp: 1e5 },
      { enemy: 'apc', hp: 1e5, delay: 1.5 },
    ]);
    g.startWave();
    let covered = false;
    let passed = false;
    play(g, 40, () => {
      const sh = of(g, 'shield')[0];
      const apc = of(g, 'apc')[0];
      if (!sh || !apc) return;
      if (g.armorOf(apc) === ENEMIES.apc.armor + 6) covered = true;
      if (apc.remaining < sh.remaining - 0.05) passed = true;
    });
    expect(covered).toBe(true);
    expect(passed).toBe(false);
  });

  it('sappers disarm traps instead of setting them off', () => {
    const g = scenario([{ enemy: 'sapper', count: 1, hp: 1e5 }]);
    const { grid } = g.map;
    let cell: { x: number; y: number; d: number } | null = null;
    for (let y = 0; y < grid.rows; y++) for (let x = 0; x < grid.cols; x++) {
      if (grid.get(x, y) !== 'path') continue;
      const d = g.flow.distanceAt(x, y);
      if (d > 5 && (!cell || d < cell.d)) cell = { x, y, d };
    }
    expect(g.buildTrap('mine', cell!.x, cell!.y).ok).toBe(true);
    g.startWave();
    const ev = play(g, 120);
    expect(ev.some((e) => e.type === 'disarmed')).toBe(true);
    expect(ev.some((e) => e.type === 'trap')).toBe(false);
  });

  it('the dreadnought lets out its escort as it breaks up', () => {
    const g = scenario([{ enemy: 'dreadnought', hp: 30000 }]);
    g.startWave();
    play(g, 2);
    const d = of(g, 'dreadnought')[0]!;
    const before = g.enemies.length;
    d.hp = 0.6 * d.maxHp + 1;
    // A hit past two thirds of its health.
    (g as unknown as { damageEnemy(e: Enemy, n: number): void }).damageEnemy(d, 10);
    play(g, TICK);
    expect(g.enemies.length).toBe(before + 5);
    expect(of(g, 'armorcar')).toHaveLength(1);
  });
});
