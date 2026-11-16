/**
 * Game content data. Display names live in the i18n files under the
 * `tower.<id>` / `enemy.<id>` keys; only ids and numbers live here.
 * Distances are in grid cells, times in seconds.
 */

export interface TowerLevel {
  /** Cost to build (level 1) or to upgrade into this level. */
  cost: number;
  damage: number;
  /** Seconds between shots. */
  fireInterval: number;
  range: number;
  projectileSpeed: number;
}

export interface TowerDef {
  id: string;
  levels: TowerLevel[];
}

export interface EnemyDef {
  id: string;
  baseHp: number;
  speed: number;
  /** Lives lost when it reaches the goal. */
  leakDamage: number;
  /** Visual radius in cells. */
  radius: number;
}

export const TOWERS = {
  crossbow: {
    id: 'crossbow',
    levels: [
      { cost: 50, damage: 5, fireInterval: 0.45, range: 2.5, projectileSpeed: 11 },
      { cost: 45, damage: 8, fireInterval: 0.4, range: 2.75, projectileSpeed: 12 },
      { cost: 90, damage: 13, fireInterval: 0.35, range: 3, projectileSpeed: 13 },
    ],
  },
} as const satisfies Record<string, TowerDef>;

export type TowerId = keyof typeof TOWERS;

export const ENEMIES = {
  raider: { id: 'raider', baseHp: 20, speed: 1.2, leakDamage: 1, radius: 0.22 },
} as const satisfies Record<string, EnemyDef>;

export type EnemyId = keyof typeof ENEMIES;

export const ECONOMY = {
  startMoney: 120,
  startLives: 20,
  /** Fraction of total invested money returned on sell. */
  sellRefund: 0.7,
};

/** Fixed simulation step in seconds. */
export const TICK = 1 / 30;
