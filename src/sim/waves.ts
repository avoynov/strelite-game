import { ENEMIES, type EnemyId } from './content';

export interface WaveGroup {
  enemy: EnemyId;
  count: number;
  hp: number;
  /** Seconds between spawns inside the group. */
  interval: number;
  /** Seconds after the wave starts before the group's first spawn. */
  delay: number;
  reward: number;
}

export interface WaveSpec {
  groups: WaveGroup[];
  /** Money paid when the wave is fully cleared. */
  clearBonus: number;
}

export const TOTAL_WAVES = 15;
/** Enemy health grows by this factor each wave… */
export const HP_GROWTH = 1.16;
/** Infantry, riders and drones grow slower: they come in larger numbers instead. */
export const SWARM_HP_GROWTH = 1.07;
const SWARM = new Set<EnemyId>(['infantry', 'moto', 'drone']);
/** …and by this fraction of the base for each map level above the first. */
export const LEVEL_HP_GROWTH = 0.04;
/** Gold per kill grows by this fraction of the base each wave. */
export const REWARD_GROWTH = 0.08;

/** The map level at which an enemy first attacks. */
export function enemyUnlocked(enemy: EnemyId, level: number): boolean {
  return level >= ENEMIES[enemy].unlockLevel;
}

/**
 * Wave n is 1-based, on map level `level` (1-based). Infantry come every wave
 * in growing numbers. Each other kind joins on the map level of the gun that
 * counters it, and from a set wave on: trucks from wave 3, riders from 2, APCs
 * from 4, drones from 3, tanks from 5; a fortress closes waves 10 and 15 (every
 * fifth wave from level 8). Health grows faster than gun damage so upgrades
 * matter, and a little with each map level.
 */
export function waveSpec(n: number, level = 1): WaveSpec {
  const levelScale = 1 + LEVEL_HP_GROWTH * (level - 1);
  // Light units grow mostly in numbers, so overkill keeps biting late in the game.
  const grow = (enemy: EnemyId) => Math.pow(SWARM.has(enemy) ? SWARM_HP_GROWTH : HP_GROWTH, n - 1) * levelScale;
  const group = (enemy: EnemyId, count: number, interval: number, delay: number, hpScale = grow(enemy)): WaveGroup => ({
    enemy,
    count,
    hp: Math.round(ENEMIES[enemy].baseHp * hpScale),
    interval,
    delay,
    // Later waves pay more per unit, so the bigger guns stay affordable.
    reward: Math.round(ENEMIES[enemy].baseReward * (1 + REWARD_GROWTH * (n - 1))),
  });
  const has = (enemy: EnemyId, fromWave: number) => enemyUnlocked(enemy, level) && n >= fromWave;

  const groups: WaveGroup[] = [group('infantry', 10 + 4 * n, Math.max(0.2, 0.6 - 0.03 * n), 0)];
  if (has('moto', 2)) groups.push(group('moto', 3 + n, 1.1, 3));
  if (has('truck', 3)) groups.push(group('truck', 1 + Math.floor(n / 2), 1.6, 4));
  if (has('drone', 3)) groups.push(group('drone', 1 + Math.floor(n / 3), 1.2, 6));
  if (has('apc', 4)) groups.push(group('apc', 1 + Math.floor((n - 4) / 3), 3, 7));
  if (has('tank', 5)) groups.push(group('tank', 1 + Math.floor((n - 5) / 3) + (n % 5 === 0 ? 1 : 0), 5, 8));
  const fortressWave = level >= 8 ? n === 10 || n === 15 : n === 15;
  // The boss grows more gently than the waves around it: it is already huge.
  const bossScale = (1 + 0.1 * Math.max(0, n - 10)) * levelScale;
  if (enemyUnlocked('fortress', level) && fortressWave) groups.push(group('fortress', 1, 1, 12, bossScale));
  return { groups, clearBonus: 15 + 3 * n };
}
