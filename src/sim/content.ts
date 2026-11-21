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
  /** Damage per hit; for a flame (`beam`) the top damage per second. */
  damage: number;
  /** Seconds between shots (charge time for the railgun). */
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
 * `beam`: a continuous flame on one target; its damage per second ramps up the
 * longer it stays on the same target.
 * `rail`: an instant slug along a straight line through everything on it.
 */
export type ProjectileKind = 'direct' | 'shell' | 'beam' | 'rail';

/**
 * Which enemy a gun picks. A gun keeps its target until it dies or leaves
 * range; when nothing matches its priority it takes the first on the path.
 * `first`: closest to the goal. `airFast`: flying, then the fastest.
 * `armored`: the most armour up to `maxArmor`. `crowd`: the one with most
 * others inside the blast. `strongest`: highest health now.
 * `line`: the direction whose line holds the most total health.
 * `weakest`: the most vulnerable, the one with the least health left; a
 * mode research opens, which the player sets per gun.
 */
export type Targeting = 'first' | 'airFast' | 'armored' | 'crowd' | 'strongest' | 'line' | 'weakest';

export interface TowerDef {
  id: string;
  /** The gun occupies size x size tiles. */
  size: number;
  /** How fast the gun turns, radians per second. */
  turnRate: number;
  projectile: ProjectileKind;
  targeting: Targeting;
  /** `armored` targeting: ignore armour above this. */
  maxArmor?: number;
  /** Fraction of the target's armour the gun ignores, 0..1. */
  pierce: number;
  /** Can shoot at flying enemies. */
  hitsAir: boolean;
  /** Extra enemies a direct round passes on into after its target. */
  passThrough?: number;
  /** Beam: damage per second when the flame first reaches a target, ramping to `damage`. */
  rampFrom?: number;
  /** Beam: seconds to ramp from `rampFrom` to full damage. */
  rampTime?: number;
  /** Shells cannot be dropped closer than this, in tiles. */
  minRange?: number;
  /** Level 1 first; always at least one. */
  levels: readonly [TowerLevel, ...TowerLevel[]];
}

export interface EnemyDef {
  id: string;
  baseHp: number;
  /** Damage taken off every hit (see damage.ts). */
  armor: number;
  /** Tiles per second. */
  speed: number;
  /** Lives lost when it reaches the goal. */
  leakDamage: number;
  /** Half the length of the unit in tiles (real size: a tank is about 7 m long). */
  radius: number;
  baseReward: number;
  /** Flies straight to the goal, over everything; only some guns can hit it. */
  air?: boolean;
  /** Surges and brakes at random, so guns that lead their target often miss. */
  swerve?: number;
  /** Units it drops when destroyed. */
  dropsOnDeath?: { enemy: string; count: number };
  /** First map level on which it attacks. */
  unlockLevel: number;
  /** Siege mode: how it attacks guns and fences; units without one only pass by. */
  assault?: Assault;
  /**
   * Siege mode: the longest way round, in tiles, it takes to a gap rather than
   * break through a fence. Only units with an assault break through.
   */
  detour?: number;
}

/**
 * Siege mode. `shoot`: fires at a gun within `range` as it passes.
 * `ram`: drives into a gun or fence it touches. Either way it attacks
 * whatever fence or gun stands in its way. Damage grows with the unit's health
 * (the square root of how far its wave raised it).
 */
export interface Assault {
  kind: 'shoot' | 'ram';
  damage: number;
  /** Seconds between blows. */
  interval: number;
  /** Tiles from the unit to the nearest edge of the gun. */
  range: number;
}

const deg = (d: number) => (d * Math.PI) / 180;

const DAMAGE_GROWTH = [1, 1.5, 2.2, 3.2, 4.6];
const INTERVAL_GROWTH = [1, 0.95, 0.9, 0.85, 0.8];
const COST_GROWTH = [1, 0.9, 1.6, 2.6, 4];

/** Five levels from the level-1 numbers: more damage, a little faster and further. */
function levels(l1: TowerLevel, rangeStep = 0.5): [TowerLevel, ...TowerLevel[]] {
  const [first, ...rest] = DAMAGE_GROWTH.map((k, i): TowerLevel => ({
    ...l1,
    cost: Math.round((l1.cost * COST_GROWTH[i]!) / 5) * 5,
    damage: Math.round(l1.damage * k * 10) / 10,
    fireInterval: Math.round(l1.fireInterval * INTERVAL_GROWTH[i]! * 100) / 100,
    range: l1.range + rangeStep * i,
    ...(l1.splash ? { splash: Math.round((l1.splash + 0.1 * i) * 100) / 100 } : {}),
  }));
  return [first!, ...rest];
}

/** Ordered from the fastest, lightest gun to the slowest, heaviest. */
export const TOWERS = {
  /** Repeating crossbow: a hail of bolts; clears infantry, useless against armour, hits drones. */
  crossbow: {
    id: 'crossbow',
    size: 2,
    turnRate: deg(360),
    projectile: 'direct',
    targeting: 'first',
    pierce: 0,
    hitsAir: true,
    levels: levels({ cost: 45, damage: 6, fireInterval: 0.2, range: 5, projectileSpeed: 22 }),
  },
  /** Scorpion: long-range bolt thrower; hunts drones and fast riders, the bolt goes through two. */
  scorpion: {
    id: 'scorpion',
    size: 2,
    turnRate: deg(220),
    projectile: 'direct',
    targeting: 'airFast',
    pierce: 0.3,
    hitsAir: true,
    passThrough: 1,
    levels: levels({ cost: 90, damage: 40, fireInterval: 1.8, range: 7, projectileSpeed: 30 }),
  },
  /** 76 mm field gun: the middle of the range; best against trucks and APCs. */
  zis3: {
    id: 'zis3',
    size: 2,
    turnRate: deg(150),
    projectile: 'direct',
    targeting: 'armored',
    maxArmor: 10,
    pierce: 0.5,
    hitsAir: false,
    levels: levels({ cost: 90, damage: 45, fireInterval: 1.3, range: 6, projectileSpeed: 28 }),
  },
  /** 155 mm howitzer: bursts over an area; made for crowds and columns. */
  howitzer: {
    id: 'howitzer',
    size: 3,
    turnRate: deg(70),
    projectile: 'shell',
    targeting: 'crowd',
    pierce: 0.3,
    hitsAir: false,
    minRange: 2.5,
    levels: levels({ cost: 170, damage: 170, fireInterval: 4.5, range: 10, projectileSpeed: 7, splash: 1.3 }),
  },
  /** Greek fire siphon: short range; the flame grows hotter the longer it holds one target. */
  greekfire: {
    id: 'greekfire',
    size: 2,
    turnRate: deg(120),
    projectile: 'beam',
    targeting: 'strongest',
    pierce: 0.5,
    hitsAir: false,
    rampFrom: 10,
    rampTime: 2,
    levels: levels({ cost: 160, damage: 70, fireInterval: 0.5, range: 3.5, projectileSpeed: 0 }, 0.25),
  },
  /** Trebuchet: the heaviest blow and the slowest stone; for tanks and fortresses. */
  trebuchet: {
    id: 'trebuchet',
    size: 3,
    turnRate: deg(45),
    projectile: 'shell',
    targeting: 'strongest',
    pierce: 0,
    hitsAir: false,
    minRange: 3,
    levels: levels({ cost: 200, damage: 520, fireInterval: 7.5, range: 12, projectileSpeed: 5, splash: 0.6 }),
  },
  /** Railgun: charges, then a slug through everything on a straight line; ignores armour. */
  railgun: {
    id: 'railgun',
    size: 3,
    turnRate: deg(40),
    projectile: 'rail',
    targeting: 'line',
    pierce: 1,
    hitsAir: false,
    levels: levels({ cost: 400, damage: 1200, fireInterval: 9, range: 14, projectileSpeed: 0 }),
  },
} as const satisfies Record<string, TowerDef>;

export type TowerId = keyof typeof TOWERS;
export const TOWER_IDS = Object.keys(TOWERS) as TowerId[];

/** The doc's enemy roster: health and armour spread wide so both overkill and armour bite. */
export const ENEMIES = {
  infantry: { id: 'infantry', baseHp: 20, armor: 0, speed: 1.0, leakDamage: 1, radius: 0.3, baseReward: 1, unlockLevel: 1, assault: { kind: 'shoot', damage: 2, interval: 1, range: 2 }, detour: 8 },
  moto: { id: 'moto', baseHp: 40, armor: 0, speed: 2.2, leakDamage: 1, radius: 0.35, baseReward: 2, swerve: 0.8, unlockLevel: 2 },
  drone: { id: 'drone', baseHp: 45, armor: 0, speed: 1.8, leakDamage: 1, radius: 1.0, baseReward: 3, air: true, unlockLevel: 3 },
  truck: { id: 'truck', baseHp: 130, armor: 3, speed: 1.6, leakDamage: 2, radius: 0.7, baseReward: 4, unlockLevel: 1 },
  apc: { id: 'apc', baseHp: 300, armor: 7, speed: 1.1, leakDamage: 3, radius: 0.95, baseReward: 8, dropsOnDeath: { enemy: 'infantry', count: 4 }, unlockLevel: 2, assault: { kind: 'ram', damage: 30, interval: 2, range: 0.4 }, detour: 4 },
  tank: { id: 'tank', baseHp: 800, armor: 14, speed: 0.6, leakDamage: 5, radius: 0.8, baseReward: 14, unlockLevel: 4, assault: { kind: 'shoot', damage: 25, interval: 2.5, range: 3.5 }, detour: 3 },
  fortress: { id: 'fortress', baseHp: 5000, armor: 22, speed: 0.35, leakDamage: 10, radius: 1.85, baseReward: 80, unlockLevel: 5, assault: { kind: 'shoot', damage: 60, interval: 3, range: 4 }, detour: 1 },
} as const satisfies Record<string, EnemyDef>;

export type EnemyId = keyof typeof ENEMIES;
export const ENEMY_IDS = Object.keys(ENEMIES) as EnemyId[];

/**
 * Siege mode: a gun's health. It grows with the gun's size and level; an
 * upgrade adds the difference, it does not repair.
 */
export const GUN_HP = { perTile: 70, levelGrowth: 0.5 };

export function gunHp(size: number, level: number): number {
  return Math.round(GUN_HP.perTile * size * (1 + GUN_HP.levelGrowth * level));
}

/** Siege mode: fence levels, one tile each: wood, stone, steel. `cost` builds or upgrades into it. */
export const FENCE_LEVELS = [
  { cost: 10, hp: 150 },
  { cost: 20, hp: 400 },
  { cost: 40, hp: 1000 },
] as const;

/** Siege mode: a unit with no assault stuck at a wall leans on it this hard (per second), so no wave can stall. */
export const PUSH_DPS = 2;

export const ECONOMY = {
  startMoney: 160,
  /** Extra starting gold per map level above the first, up to `startMoneyLevelCap`. */
  startMoneyPerLevel: 60,
  startMoneyLevelCap: 20,
  /** Share of the gold of the weaker waves before a level's first one given as extra starting gold. */
  headStart: 1,
  startLives: 20,
  /** Fraction of total invested money returned on sell. */
  sellRefund: 0.7,
};

/** Fixed simulation step in seconds. */
export const TICK = 1 / 30;
