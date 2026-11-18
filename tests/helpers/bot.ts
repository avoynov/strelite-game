import { ENEMIES, ENEMY_IDS, FENCE_LEVELS, TICK, TOWER_IDS, TOWERS, type TowerId } from '../../src/sim/content';
import type { Game } from '../../src/sim/game';

/**
 * How much each cell is walked: 1 per road cell in path mode; in arc mode the
 * number of routes from the arc's edge cells to the goal that pass through it.
 * In siege mode a route ends at the first fence in its way, where its
 * enemies stop to break through.
 */
const traffic = new WeakMap<object, Float32Array>();
function trafficOf(g: Game): Float32Array {
  const key = g.openField ? g.flow : g.map;
  let t = traffic.get(key);
  if (t) return t;
  const { grid } = g.map;
  t = new Float32Array(grid.cols * grid.rows);
  if (g.mode === 'path') {
    for (let i = 0; i < t.length; i++) if (grid.cells[i] === 'path') t[i] = 1;
  } else {
    for (const s of g.map.arcSpawns ?? []) {
      // Edge cells the enemies come from all through the level count alike.
      for (let c: { x: number; y: number } | null = s; c; c = g.flow.next(c.x, c.y)) {
        if (g.mode === 'siege' && g.fenceAt(c.x, c.y)) break;
        t[grid.index(c.x, c.y)]! += 1 / 8;
      }
    }
  }
  traffic.set(key, t);
  return t;
}

/** Siege mode: keep each gun this much further from where enemies walk than the longest reach of any attacker on the level. */
const SIEGE_MARGIN = 0.5;
function clearance(g: Game): number {
  let reach = 0;
  for (const id of ENEMY_IDS) {
    const d = ENEMIES[id];
    if (g.level >= d.unlockLevel && 'assault' in d) reach = Math.max(reach, d.assault.range + (d.assault.kind === 'ram' ? d.radius : 0));
  }
  return reach + SIEGE_MARGIN;
}

/** How much traffic a gun at this anchor could reach (0 in siege mode when it would stand by the way). */
function coverage(g: Game, def: TowerId, cx: number, cy: number): number {
  const d = TOWERS[def];
  const range = d.levels[0].range;
  const min = 'minRange' in d ? d.minRange : 0;
  const x = cx + d.size / 2;
  const y = cy + d.size / 2;
  const t = trafficOf(g);
  const { grid } = g.map;
  const keepClear = g.mode === 'siege' ? clearance(g) : -1;
  let n = 0;
  for (let py = Math.max(0, Math.floor(y - range)); py <= Math.min(grid.rows - 1, y + range); py++) {
    for (let px = Math.max(0, Math.floor(x - range)); px <= Math.min(grid.cols - 1, x + range); px++) {
      const w = t[grid.index(px, py)]!;
      if (!w) continue;
      const edge = Math.hypot(Math.max(cx - px - 0.5, 0, px + 0.5 - cx - d.size), Math.max(cy - py - 0.5, 0, py + 0.5 - cy - d.size));
      if (edge < keepClear) return 0;
      const dist = Math.hypot(px + 0.5 - x, py + 0.5 - y);
      if (dist <= range && dist >= min) n += Math.min(w, 4);
    }
  }
  return n;
}

/** Siege mode, once the ring stands: guns go inside it. */
function insideRing(g: Game, def: TowerId, cx: number, cy: number): boolean {
  if (g.mode !== 'siege' || !g.fences.length) return true;
  const xs = g.map.goals.map((c) => c.x);
  const ys = g.map.goals.map((c) => c.y);
  return cx > Math.min(...xs) - RING && cy > Math.min(...ys) - RING && cx + TOWERS[def].size <= Math.max(...xs) + RING && cy + TOWERS[def].size <= Math.max(...ys) + RING;
}

function bestSpot(g: Game, def: TowerId): { cx: number; cy: number } | null {
  const spots: { cx: number; cy: number; score: number }[] = [];
  for (let cy = 0; cy < g.map.grid.rows; cy++) {
    for (let cx = 0; cx < g.map.grid.cols; cx++) {
      if (g.placementError(def, cx, cy) || !insideRing(g, def, cx, cy)) continue;
      const score = coverage(g, def, cx, cy);
      if (score > 0) spots.push({ cx, cy, score });
    }
  }
  // Best first; the (costly) check that the spot keeps the way open only for the leaders.
  spots.sort((a, b) => b.score - a.score);
  return spots.find((p) => g.canBuildAt(def, p.cx, p.cy)) ?? null;
}

/** Siege mode: the bot walls the goal in with a ring of fences this many tiles out. */
const RING = 6;

/** Siege mode: the cells of the fence ring round the goal (the map's own edges close it where it runs off). */
function ringCells(g: Game): { x: number; y: number }[] {
  const xs = g.map.goals.map((c) => c.x);
  const ys = g.map.goals.map((c) => c.y);
  const [x0, x1, y0, y1] = [Math.min(...xs) - RING, Math.max(...xs) + RING, Math.min(...ys) - RING, Math.max(...ys) + RING];
  const cells: { x: number; y: number }[] = [];
  for (let y = y0; y <= y1; y++) {
    for (let x = x0; x <= x1; x++) if ((x === x0 || x === x1 || y === y0 || y === y1) && g.map.grid.get(x, y) === 'build') cells.push({ x, y });
  }
  return cells;
}

/** Siege mode: close the ring, then make it stone, then steel, as money allows; returns whether it bought anything. */
function fortify(g: Game, upgrade: boolean): boolean {
  let bought = false;
  for (const c of ringCells(g)) {
    if (g.towerAt(c.x, c.y)) continue;
    const f = g.fenceAt(c.x, c.y);
    if (!f) bought = g.buildFence(c.x, c.y).ok || bought;
    else if (upgrade) {
      const cost = g.fenceUpgradeCost(f);
      if (cost !== null && g.money >= cost) bought = g.upgradeFence(f.id).ok || bought;
    }
  }
  return bought;
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
  // Siege: close (or repair) the ring first, once that still leaves money for a gun.
  const siege = g.mode === 'siege';
  if (siege) {
    const missing = ringCells(g).filter((c) => !g.towerAt(c.x, c.y) && !g.fenceAt(c.x, c.y)).length;
    // Worth it once the ring is a small part of the money (or it only needs repairs).
    if (missing * FENCE_LEVELS[0].cost * 3 <= g.money || g.fences.length) fortify(g, false);
  }
  for (let guard = 0; guard < 60; guard++) {
    const invested = (id: TowerId) => g.towers.filter((t) => t.def === id).reduce((s, t) => s + t.stats.invested, 0);
    const want = [...allowed].sort((a, b) => invested(a) / MIX[a] - invested(b) / MIX[b] || TOWERS[a].levels[0].cost - TOWERS[b].levels[0].cost)[0]!;
    const cost = TOWERS[want].levels[0].cost;
    const upgradable = g.towers
      .map((t) => ({ t, cost: g.upgradeCost(t) }))
      .filter((u): u is { t: (typeof g.towers)[number]; cost: number } => u.cost !== null && g.canRaise(u.t))
      .sort((a, b) => a.cost - b.cost)[0];
    // Alternate: every other purchase is an upgrade when one is affordable.
    if (upgradable && g.money >= upgradable.cost && g.towers.length >= 4 && guard % 2 === 1) {
      g.upgrade(upgradable.t.id);
      continue;
    }
    if (g.money >= cost) {
      const spot = bestSpot(g, want);
      if (spot && g.build(want, spot.cx, spot.cy).ok) continue;
      // Nowhere this gun is any use (or safe): stop wanting it and buy the next.
      if (!spot && allowed.length > 1) {
        allowed.splice(allowed.indexOf(want), 1);
        continue;
      }
    }
    // Can't afford the gun it wants yet: save up for it rather than upgrade.
    if (g.money < cost) break;
    if (upgradable && g.money >= upgradable.cost) {
      g.upgrade(upgradable.t.id);
      continue;
    }
    break;
  }
  // Money left over that buys no gun goes into stronger walls (in the base: not while a builder is only busy).
  if (siege && g.fences.length && g.freeBuilders() > 0) fortify(g, true);
}

export function run(g: Game, seconds: number): void {
  for (let i = 0; i < seconds / TICK; i++) g.step(TICK);
}

/** Play a whole game with the bot; returns per-wave lives for tuning. */
export function playOut(g: Game, only?: readonly TowerId[], onStep?: () => void): number[] {
  const lives: number[] = [];
  while (g.phase === 'build') {
    spend(g, only);
    g.startWave();
    for (let i = 0; i < 20000 && g.phase === 'wave'; i++) {
      g.step(TICK);
      onStep?.();
    }
    lives.push(g.lives);
  }
  return lives;
}
