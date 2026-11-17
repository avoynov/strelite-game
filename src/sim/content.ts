/**
 * Game content data. Display names live in the i18n files under the
 * `tower.<id>` / `enemy.<id>` keys; only ids and numbers live here.
 * Distances are in grid cells (tiles), times in seconds, angles in radians.
 *
 * The roster is a stand-in until the final list of guns and enemies is decided;
 * adding or changing one is a data change here plus two i18n lines.
 */

/**
 * Side of one tile in real metres. The rendered art is real size, so this one
 * number sets how big every gun is drawn on the board.
 */
export const METRES_PER_TILE = 4;

export interface TowerLevel {
  /** Cost to build (level 1) or to upgrade into this level. */
  cost: number;
  damage: number;
  /** Seconds between shots. */
  fireInterval: number;
  range: number;
  projectileSpeed: number;
  /** Blast radius in tiles; shells only. */
  splash?: number;
}

/**
 * `direct`: a fast round that follows its target and hits only it.
 * `shell`: a lobbed round aimed at where the target will be; it bursts on the
 * ground and damages everything inside `splash`.
 */
export type ProjectileKind = 'direct' | 'shell';

export interface TowerDef {
  id: string;
  /** The gun occupies size x size tiles. */
  size: number;
  /** How fast the gun turns, radians per second. */
  turnRate: number;
  projectile: ProjectileKind;
  /** Shells cannot be dropped closer than this, in tiles. */
  minRange?: number;
  levels: TowerLevel[];
}

export interface EnemyDef {
  id: string;
  baseHp: number;
  /** Tiles per second. */
  speed: number;
  /** Lives lost when it reaches the goal. */
  leakDamage: number;
  /** Half the length of the unit in tiles (real size: a tank is about 7 m long). */
  radius: number;
  baseReward: number;
}

const deg = (d: number) => (d * Math.PI) / 180;

export const TOWERS = {
  /** 76 mm field gun: light, quick, wastes little damage on small targets. */
  zis3: {
    id: 'zis3',
    size: 2,
    turnRate: deg(150),
    projectile: 'direct',
    levels: [
      { cost: 60, damage: 12, fireInterval: 1.0, range: 5.5, projectileSpeed: 26 },
      { cost: 55, damage: 19, fireInterval: 0.9, range: 6, projectileSpeed: 28 },
      { cost: 110, damage: 30, fireInterval: 0.8, range: 6.5, projectileSpeed: 30 },
    ],
  },
  /** 155 mm howitzer: slow, heavy, bursts over an area; made for tanks and crowds. */
  howitzer: {
    id: 'howitzer',
    size: 3,
    turnRate: deg(70),
    projectile: 'shell',
    minRange: 2.5,
    levels: [
      { cost: 150, damage: 160, fireInterval: 4.6, range: 9.5, projectileSpeed: 9, splash: 1.3 },
      { cost: 130, damage: 250, fireInterval: 4.2, range: 10.5, projectileSpeed: 9.5, splash: 1.45 },
      { cost: 260, damage: 400, fireInterval: 3.8, range: 11.5, projectileSpeed: 10, splash: 1.6 },
    ],
  },
} as const satisfies Record<string, TowerDef>;

export type TowerId = keyof typeof TOWERS;
export const TOWER_IDS = Object.keys(TOWERS) as TowerId[];

export const ENEMIES = {
  infantry: { id: 'infantry', baseHp: 16, speed: 1.0, leakDamage: 1, radius: 0.3, baseReward: 1 },
  truck: { id: 'truck', baseHp: 60, speed: 1.7, leakDamage: 2, radius: 0.7, baseReward: 4 },
  tank: { id: 'tank', baseHp: 420, speed: 0.6, leakDamage: 5, radius: 0.8, baseReward: 14 },
} as const satisfies Record<string, EnemyDef>;

export type EnemyId = keyof typeof ENEMIES;

export const ECONOMY = {
  startMoney: 200,
  startLives: 20,
  /** Fraction of total invested money returned on sell. */
  sellRefund: 0.7,
};

/** Fixed simulation step in seconds. */
export const TICK = 1 / 30;
