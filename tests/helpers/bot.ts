import { TICK, TOWER_IDS, TOWERS, type TowerId } from '../../src/sim/content';
import type { Game } from '../../src/sim/game';

/** Number of road cells a gun at this anchor could reach. */
function coverage(g: Game, def: TowerId, cx: number, cy: number): number {
  const d = TOWERS[def];
  const range = d.levels[0].range;
  const min = 'minRange' in d ? d.minRange : 0;
  const x = cx + d.size / 2;
  const y = cy + d.size / 2;
  let n = 0;
  for (let py = 0; py < g.map.grid.rows; py++) {
    for (let px = 0; px < g.map.grid.cols; px++) {
      if (g.map.grid.get(px, py) !== 'path') continue;
      const dist = Math.hypot(px + 0.5 - x, py + 0.5 - y);
      if (dist <= range && dist >= min) n++;
    }
  }
  return n;
}

function bestSpot(g: Game, def: TowerId): { cx: number; cy: number } | null {
  let best: { cx: number; cy: number } | null = null;
  let bestScore = 0;
  for (let cy = 0; cy < g.map.grid.rows; cy++) {
    for (let cx = 0; cx < g.map.grid.cols; cx++) {
      if (!g.canBuildAt(def, cx, cy)) continue;
      const score = coverage(g, def, cx, cy);
      if (score > bestScore) {
        bestScore = score;
        best = { cx, cy };
      }
    }
  }
  return best;
}

/** How much of its money a sensible player puts into each gun, relative to the others. */
const MIX: Record<TowerId, number> = { crossbow: 2, scorpion: 1.5, zis3: 2, howitzer: 2, greekfire: 1.5, trebuchet: 1.5, railgun: 1 };

/**
 * A plain, sensible player: keeps its spending on each allowed gun close to
 * MIX, building the gun it is shortest of at the spot that sees most road, and
 * upgrading every other purchase once it has a few guns. `only` limits it to
 * some guns (to show that one gun alone does not win).
 */
export function spend(g: Game, only?: readonly TowerId[]): void {
  const allowed = (only ?? TOWER_IDS).filter((id) => g.isUnlocked(id));
  if (!allowed.length) return;
  for (let guard = 0; guard < 60; guard++) {
    const invested = (id: TowerId) => g.towers.filter((t) => t.def === id).reduce((s, t) => s + t.stats.invested, 0);
    const want = [...allowed].sort((a, b) => invested(a) / MIX[a] - invested(b) / MIX[b] || TOWERS[a].levels[0].cost - TOWERS[b].levels[0].cost)[0]!;
    const cost = TOWERS[want].levels[0].cost;
    const upgradable = g.towers
      .map((t) => ({ t, cost: g.upgradeCost(t) }))
      .filter((u): u is { t: (typeof g.towers)[number]; cost: number } => u.cost !== null)
      .sort((a, b) => a.cost - b.cost)[0];
    // Alternate: every other purchase is an upgrade when one is affordable.
    if (upgradable && g.money >= upgradable.cost && g.towers.length >= 4 && guard % 2 === 1) {
      g.upgrade(upgradable.t.id);
      continue;
    }
    if (g.money >= cost) {
      const spot = bestSpot(g, want);
      if (spot && g.build(want, spot.cx, spot.cy).ok) continue;
    }
    // Can't afford the gun it wants yet: save up for it rather than upgrade.
    if (g.money < cost) break;
    if (upgradable && g.money >= upgradable.cost) {
      g.upgrade(upgradable.t.id);
      continue;
    }
    break;
  }
}

export function run(g: Game, seconds: number): void {
  for (let i = 0; i < seconds / TICK; i++) g.step(TICK);
}

/** Play a whole game with the bot; returns per-wave lives for tuning. */
export function playOut(g: Game, only?: readonly TowerId[]): number[] {
  const lives: number[] = [];
  while (g.phase === 'build') {
    spend(g, only);
    g.startWave();
    for (let i = 0; i < 20000 && g.phase === 'wave'; i++) g.step(TICK);
    lives.push(g.lives);
  }
  return lives;
}
