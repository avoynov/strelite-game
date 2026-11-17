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

/**
 * Wave n is 1-based. Infantry come every wave in growing numbers (food for the
 * light gun), trucks join from wave 3, tanks from wave 5 (food for the heavy
 * gun). Health grows faster than gun damage so upgrades matter.
 */
export function waveSpec(n: number): WaveSpec {
  const grow = Math.pow(1.13, n - 1);
  const group = (enemy: EnemyId, count: number, interval: number, delay: number): WaveGroup => ({
    enemy,
    count,
    hp: Math.round(ENEMIES[enemy].baseHp * grow),
    interval,
    delay,
    reward: ENEMIES[enemy].baseReward,
  });

  const groups: WaveGroup[] = [group('infantry', 6 + 2 * n, Math.max(0.35, 0.9 - 0.035 * n), 0)];
  if (n >= 3) groups.push(group('truck', 1 + Math.floor(n / 2), 1.6, 4));
  if (n >= 5) groups.push(group('tank', 1 + Math.floor((n - 5) / 2) + (n % 5 === 0 ? 1 : 0), 5, 8));
  return { groups, clearBonus: 15 + 3 * n };
}
