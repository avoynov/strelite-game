import { TICK, TOWERS, type TowerId } from '../../src/sim/content';
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

/**
 * A plain, sensible player: light guns first, a heavy gun for every `heavyEvery`
 * light ones once tanks are near, upgrades when nothing new is affordable.
 */
export function spend(g: Game, heavyEvery = 3): void {
  for (let guard = 0; guard < 50; guard++) {
    const light = g.towers.filter((t) => t.def === 'zis3').length;
    const heavy = g.towers.filter((t) => t.def === 'howitzer').length;
    const want: TowerId = g.wave >= 3 && heavy < Math.floor(light / heavyEvery) + (g.wave >= 4 ? 1 : 0) ? 'howitzer' : 'zis3';
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
export function playOut(g: Game, heavyEvery = 3): number[] {
  const lives: number[] = [];
  while (g.phase === 'build') {
    spend(g, heavyEvery);
    g.startWave();
    for (let i = 0; i < 20000 && g.phase === 'wave'; i++) g.step(TICK);
    lives.push(g.lives);
  }
  return lives;
}
