import type { EnemyId } from './content';

export interface WaveSpec {
  enemy: EnemyId;
  count: number;
  hp: number;
  /** Seconds between spawns. */
  spawnInterval: number;
  reward: number;
  /** Money paid when the wave is fully cleared. */
  clearBonus: number;
}

export const TOTAL_WAVES = 15;

/** Wave n is 1-based. Health grows faster than the gun's base damage so upgrades matter. */
export function waveSpec(n: number): WaveSpec {
  return {
    enemy: 'raider',
    count: 5 + 2 * n,
    hp: Math.round(20 * Math.pow(1.2, n - 1)),
    spawnInterval: Math.max(0.35, 0.9 - 0.035 * n),
    reward: 3 + Math.floor(n / 3),
    clearBonus: 10 + 2 * n,
  };
}
