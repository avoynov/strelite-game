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
  /** Blast radius in tiles; shells and rockets. */
  splash?: number;
  /** Flash: seconds a full flash stuns. */
  stun?: number;
  /** Disc: enemies it bounces on to after the first. */
  bounces?: number;
  /** Lens: share of the target's health now, per second. Harpoon: share of its full health, per hit. */
  pct?: number;
  /** Darts: how many one burst looses (the burst is followed by the `fireInterval` pause). */
  darts?: number;
}

/**
 * `direct`: a fast round that follows its target and hits only it.
 * `shell`: a lobbed round aimed at where the target will be; it bursts on the
 * ground and damages everything inside `splash`.
 * `beam`: a continuous flame on one target; its damage per second ramps up the
 * longer it stays on the same target.
 * `rail`: an instant slug along a straight line through everything on it.
 * `flash`: a blinding flash over a cone in front; stuns, no damage.
 * `rocket`: a wobbling firework that follows a flyer and bursts among flyers.
 * `disc`: a round that bounces on from its target to the nearest others.
 * `lens`: a beam of gathered sunlight taking a share of the target's health now.
 * `darts`: a burst of small darts, each picking its own target.
 * A harpoon is a `direct` round whose hit is a share of the target's full health (`pct`).
 */
export type ProjectileKind = 'direct' | 'shell' | 'beam' | 'rail' | 'flash' | 'rocket' | 'disc' | 'lens' | 'darts';

/**
 * Which enemy a gun picks. A gun keeps its target until it dies or leaves
 * range; when nothing matches its priority it takes the first on the path.
 * `first`: closest to the goal. `airFast`: flying, then the fastest.
 * `armored`: the most armour up to `maxArmor`. `crowd`: the one with most
 * others inside the blast. `strongest`: highest health now.
 * `line`: the direction whose line holds the most total health.
 * `weakest`: the most vulnerable, the one with the least health left; a
 * mode research opens, which the player sets per gun.
 * `rear`: the furthest from the goal (the tail of the wave).
 * `cone`: the way with most enemies inside the flash's cone.
 * `airCrowd`: the flyer with most other flyers inside the burst.
 * `sureKill`: the toughest it can still kill before it leaves range, else the one it brings closest to death.
 * `bounce`: the one with most others within a bounce of it.
 * `lens`: the first it sees, later the one with most health now.
 * `biggest`: the most full health, if it has at least a hit's worth left.
 * `swarm`: each dart its own, at random: nearer more likely, armoured less, never one already doomed.
 */
export type Targeting = 'first' | 'airFast' | 'armored' | 'crowd' | 'strongest' | 'line' | 'weakest' | 'rear' | 'cone' | 'airCrowd' | 'sureKill' | 'bounce' | 'lens' | 'biggest' | 'swarm';

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
  /** Shoots only at flyers. */
  airOnly?: boolean;
  /** Flash: half-angle of the cone, radians. */
  cone?: number;
  /** Disc: how far it reaches for the next enemy after a hit, tiles. */
  bounceReach?: number;
  /** Disc: share of the damage lost on each bounce. */
  bounceLoss?: number;
  /** Lens: seconds it takes to focus on a new target (no damage meanwhile). */
  focus?: number;
  /** Lens: every so many seconds it moves on to the enemy with most health now. */
  retarget?: number;
  /** Lens: below this many damage a second it drops its target for another. */
  plateau?: number;
  /** Rear: switch target once it is this share of its way through range and a further one came in. */
  switchShare?: number;
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
  /** Weaves from side to side across its way, this many tiles each side, so guns that lead their target often miss. */
  weave?: number;
  /** Units it drops when destroyed. */
  dropsOnDeath?: { enemy: string; count: number };
  /** First map level on which it attacks. */
  unlockLevel: number;
  /** A boss: takes half the share-of-health damage and half the stun. */
  boss?: boolean;
  /** Walks over spike pits and leg traps as if they were not there. */
  trapProof?: boolean;
  /** A machine (not a soldier): leg traps hold it half as long; repair wagons mend it. */
  machine?: boolean;
  /** Repair wagon: mends machines within `reach` tiles by `share` of their full health every `every` seconds (bosses half). */
  heal?: { share: number; every: number; reach: number };
  /** Shield-bearer: other ground units within `reach` tiles take this much more armour (not stacking), and those close behind it never pass it. */
  aura?: { armor: number; reach: number };
  /** Sapper: seconds it needs to disarm a trap in its way (it never sets one off). */
  disarm?: number;
  /** Base mode: a flyer that lands by its goal and lets out this unit. */
  lands?: string;
  /** Boss: lets out an escort when its health falls to each of these shares. */
  escort?: { at: readonly number[]; units: ReadonlyArray<{ enemy: string; count: number }> };
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
  /** `bomb`: a flyer drops bombs on what is under it. `blast`: sappers blow up their charge (and themselves) by it. */
  kind: 'shoot' | 'ram' | 'bomb' | 'blast';
  damage: number;
  /** Seconds between blows. */
  interval: number;
  /** Tiles from the unit to the nearest edge of the gun. */
  range: number;
}

const deg = (d: number) => (d * Math.PI) / 180;

/** Level 5 hits ×5.5 (not ×4.6), to answer the enemies that keep growing up to map 80. */
export const DAMAGE_GROWTH = [1, 1.5, 2.2, 3.2, 5.5];
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

/** Five levels with some numbers set per level instead of grown (`per[i]` overrides level i+1). */
function levelsWith(l1: TowerLevel, per: ReadonlyArray<Partial<TowerLevel>>, rangeStep = 0.5): [TowerLevel, ...TowerLevel[]] {
  const ls = levels(l1, rangeStep);
  const [first, ...rest] = ls.map((l, i) => ({ ...l, ...(per[i] ?? {}) }));
  return [first!, ...rest];
}

/** Ordered by when the laboratory opens them. */
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
  /** Заднопер: a spear thrower aimed up; it hunts the tail of the wave, which nobody has hit yet. */
  zadnoper: {
    id: 'zadnoper',
    size: 2,
    turnRate: deg(90),
    projectile: 'direct',
    targeting: 'rear',
    pierce: 0.4,
    hitsAir: false,
    switchShare: 0.75,
    levels: levels({ cost: 120, damage: 110, fireInterval: 3, range: 9, projectileSpeed: 11 }),
  },
  /** Шеметофар: a flash lamp; it stuns everything in its cone and deals no damage. */
  flasher: {
    id: 'flasher',
    size: 2,
    turnRate: deg(160),
    projectile: 'flash',
    targeting: 'cone',
    pierce: 0,
    hitsAir: true,
    cone: deg(30),
    levels: levelsWith({ cost: 110, damage: 0, fireInterval: 4, range: 4.5, projectileSpeed: 0, stun: 0.8 }, [{}, { stun: 1, fireInterval: 3.8 }, { stun: 1.2, fireInterval: 3.6 }, { stun: 1.4, fireInterval: 3.4 }, { stun: 1.6, fireInterval: 3.2 }]),
  },
  /** Ракети: a barrel of fireworks for the air; the rockets wobble, then burst among the flyers. */
  rockets: {
    id: 'rockets',
    size: 2,
    turnRate: deg(200),
    projectile: 'rocket',
    targeting: 'airCrowd',
    pierce: 0.15,
    hitsAir: true,
    airOnly: true,
    levels: levels({ cost: 100, damage: 30, fireInterval: 1.2, range: 8, projectileSpeed: 9, splash: 0.8 }),
  },
  /** Таркански топ: light balls, fast; it takes only kills it is sure of, so it wastes little. */
  tarkan: {
    id: 'tarkan',
    size: 2,
    turnRate: deg(240),
    projectile: 'direct',
    targeting: 'sureKill',
    pierce: 0.3,
    hitsAir: false,
    levels: levels({ cost: 85, damage: 28, fireInterval: 0.45, range: 6, projectileSpeed: 20 }),
  },
  /** Рикошетен топ: a heavy disc that bounces on from enemy to enemy. */
  ricochet: {
    id: 'ricochet',
    size: 3,
    turnRate: deg(100),
    projectile: 'disc',
    targeting: 'bounce',
    pierce: 0.35,
    hitsAir: false,
    bounceReach: 3,
    bounceLoss: 0.15,
    levels: levelsWith({ cost: 230, damage: 140, fireInterval: 3.2, range: 4.5, projectileSpeed: 12, bounces: 2 }, [{}, { bounces: 2 }, { bounces: 3 }, { bounces: 3 }, { bounces: 4 }]),
  },
  /** Дяволско стъкло: sunlight through a lens; it burns a share of the health its target has now, through any armour. */
  glass: {
    id: 'glass',
    size: 2,
    turnRate: deg(120),
    projectile: 'lens',
    targeting: 'lens',
    pierce: 1,
    hitsAir: true,
    focus: 0.5,
    retarget: 10,
    plateau: 15,
    levels: levelsWith({ cost: 260, damage: 0, fireInterval: 0.5, range: 5.5, projectileSpeed: 0, pct: 0.04 }, [{}, { pct: 0.05 }, { pct: 0.06 }, { pct: 0.07 }, { pct: 0.08 }]),
  },
  /** Душевадица: a whaling harpoon; each hit tears a share of the target's full health, through any armour. */
  harpoon: {
    id: 'harpoon',
    size: 2,
    turnRate: deg(80),
    projectile: 'direct',
    targeting: 'biggest',
    pierce: 1,
    hitsAir: true,
    levels: levelsWith({ cost: 280, damage: 0, fireInterval: 3.5, range: 7.5, projectileSpeed: 16, pct: 0.06 }, [{}, { pct: 0.07 }, { pct: 0.08 }, { pct: 0.09 }, { pct: 0.1 }]),
  },
  /** Стоманени пчели: a burst of whistling darts, each on an enemy nobody else will kill first. */
  bees: {
    id: 'bees',
    size: 3,
    turnRate: deg(360),
    projectile: 'darts',
    targeting: 'swarm',
    pierce: 0.25,
    hitsAir: true,
    levels: levelsWith({ cost: 340, damage: 30, fireInterval: 3.5, range: 9.5, projectileSpeed: 13, darts: 12 }, [{}, { darts: 13 }, { darts: 14 }, { darts: 16 }, { darts: 18 }]),
  },
} as const satisfies Record<string, TowerDef>;

export type TowerId = keyof typeof TOWERS;
/** In the order the laboratory opens them (the order the arsenal and the build menu show). */
export const TOWER_IDS: TowerId[] = ['crossbow', 'zis3', 'howitzer', 'scorpion', 'zadnoper', 'trebuchet', 'flasher', 'rockets', 'tarkan', 'greekfire', 'ricochet', 'railgun', 'glass', 'harpoon', 'bees'];

/** The doc's enemy roster: health and armour spread wide so both overkill and armour bite. */
export const ENEMIES = {
  infantry: { id: 'infantry', baseHp: 20, armor: 0, speed: 1.0, leakDamage: 1, radius: 0.3, baseReward: 1, unlockLevel: 1, assault: { kind: 'shoot', damage: 2, interval: 1, range: 2 }, detour: 8 },
  moto: { id: 'moto', baseHp: 40, armor: 0, speed: 2.2, leakDamage: 1, radius: 0.35, baseReward: 2, weave: 0.7, unlockLevel: 2 },
  drone: { id: 'drone', baseHp: 45, armor: 0, speed: 1.8, leakDamage: 1, radius: 1.0, baseReward: 3, air: true, unlockLevel: 3 },
  truck: { id: 'truck', baseHp: 130, armor: 3, speed: 1.6, leakDamage: 2, radius: 0.7, baseReward: 4, unlockLevel: 1, machine: true },
  apc: { id: 'apc', baseHp: 300, armor: 7, speed: 1.1, leakDamage: 3, radius: 0.95, baseReward: 8, machine: true, dropsOnDeath: { enemy: 'infantry', count: 4 }, unlockLevel: 2, assault: { kind: 'ram', damage: 30, interval: 2, range: 0.4 }, detour: 4 },
  tank: { id: 'tank', baseHp: 800, armor: 14, speed: 0.6, leakDamage: 5, radius: 0.8, baseReward: 14, unlockLevel: 4, machine: true, assault: { kind: 'shoot', damage: 25, interval: 2.5, range: 3.5 }, detour: 3 },
  fortress: { id: 'fortress', baseHp: 5000, armor: 22, speed: 0.35, leakDamage: 10, radius: 1.85, baseReward: 80, unlockLevel: 5, boss: true, machine: true, assault: { kind: 'shoot', damage: 60, interval: 3, range: 4 }, detour: 1 },
  // The new eight, one per act from II: they join the waves on these map levels (see waveOfStrength).
  /** Repair wagon: follows the armour and mends it; never drives faster than the machine ahead. */
  wagon: { id: 'wagon', baseHp: 160, armor: 4, speed: 1.0, leakDamage: 2, radius: 0.73, baseReward: 5, unlockLevel: 10, machine: true, heal: { share: 0.02, every: 2, reach: 2 } },
  /** Riders: fast packs on horseback. */
  rider: { id: 'rider', baseHp: 55, armor: 1, speed: 1.9, leakDamage: 1, radius: 0.32, baseReward: 2, unlockLevel: 16 },
  /** Gliders: flocks of light flyers; in the base they land and let a soldier out. */
  glider: { id: 'glider', baseHp: 35, armor: 0, speed: 2.3, leakDamage: 1, radius: 0.69, baseReward: 2, air: true, unlockLevel: 23, lands: 'infantry' },
  /** Armoured car: fast, with a machine gun it fires on the move. */
  armorcar: { id: 'armorcar', baseHp: 200, armor: 5, speed: 1.7, leakDamage: 2, radius: 0.64, baseReward: 10, unlockLevel: 31, machine: true, assault: { kind: 'shoot', damage: 4, interval: 0.5, range: 3 }, detour: 4 },
  /** Sappers: slow soldiers who disarm traps and lay charges at fences. */
  sapper: { id: 'sapper', baseHp: 40, armor: 3, speed: 0.8, leakDamage: 1, radius: 0.3, baseReward: 1, unlockLevel: 40, disarm: 1.5, assault: { kind: 'shoot', damage: 12, interval: 1.5, range: 0.6 }, detour: 8 },
  /** Shield-bearer: a slow wall on wheels; what follows close behind it is armoured too and keeps behind it. */
  shield: { id: 'shield', baseHp: 700, armor: 18, speed: 0.5, leakDamage: 4, radius: 0.8, baseReward: 18, unlockLevel: 51, machine: true, aura: { armor: 6, reach: 1.5 }, assault: { kind: 'ram', damage: 40, interval: 2.5, range: 0.4 }, detour: 3 },
  /** Flying boat: a slow armoured flyer that bombs what is under it. */
  boat: { id: 'boat', baseHp: 1000, armor: 12, speed: 0.45, leakDamage: 5, radius: 1.8, baseReward: 20, air: true, unlockLevel: 64 },
  /** Dreadnought: the last boss, from map 80; lets out an escort as it breaks up; pits and leg traps do nothing to it. */
  dreadnought: {
    id: 'dreadnought',
    baseHp: 12000,
    armor: 26,
    speed: 0.3,
    leakDamage: 20,
    radius: 2.0,
    baseReward: 150,
    unlockLevel: 80,
    boss: true,
    trapProof: true,
    machine: true,
    escort: { at: [2 / 3, 1 / 3], units: [{ enemy: 'armorcar', count: 1 }, { enemy: 'infantry', count: 4 }] },
    assault: { kind: 'shoot', damage: 90, interval: 3, range: 5 },
    detour: 0,
  },
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

/** What a unit goes for in the player's base. */
export type BaseGoal = 'nearest' | 'treasury' | 'gun' | 'fence' | 'hq';

export interface BaseRole {
  goal: BaseGoal;
  /** How it strikes in the base (units that only pass by elsewhere get one here). */
  assault: Assault;
  /** As EnemyDef.detour. */
  detour: number;
  /** `blast` only: tiles round the charge it damages. */
  splash?: number;
  /** Blows it has before it falls back to an infantryman's role. */
  charges?: number;
}

/**
 * The base: every enemy goes for something. Infantry the nearest thing,
 * bikers plunder the treasury, airships bomb the guns over the fences, trucks
 * carry sappers who blow up the fences, armour hunts the guns and the fortress
 * makes for the headquarters. With its goal gone a unit makes for the nearest
 * building or gun.
 */
export const BASE_ROLES: Record<EnemyId, BaseRole> = {
  infantry: { goal: 'nearest', assault: { kind: 'shoot', damage: 1, interval: 1, range: 1.8 }, detour: ENEMIES.infantry.detour },
  moto: { goal: 'treasury', assault: { kind: 'shoot', damage: 4, interval: 0.8, range: 1.2 }, detour: 24 },
  drone: { goal: 'gun', assault: { kind: 'bomb', damage: 28, interval: 2.4, range: 0.6 }, detour: 0 },
  truck: { goal: 'fence', assault: { kind: 'blast', damage: 260, interval: 1, range: 0.3 }, detour: 0, splash: 1.6 },
  // Armour hunting guns hits softer than armour shooting them in passing: it gets to every one of them.
  apc: { goal: 'gun', assault: { kind: 'ram', damage: 18, interval: 2, range: 0.4 }, detour: ENEMIES.apc.detour },
  tank: { goal: 'gun', assault: { kind: 'shoot', damage: 12, interval: 2.5, range: 3 }, detour: ENEMIES.tank.detour },
  fortress: { goal: 'hq', assault: ENEMIES.fortress.assault, detour: ENEMIES.fortress.detour },
  wagon: { goal: 'gun', assault: { kind: 'ram', damage: 8, interval: 2, range: 0.4 }, detour: 4 },
  rider: { goal: 'treasury', assault: { kind: 'shoot', damage: 3, interval: 0.8, range: 1.2 }, detour: 24 },
  glider: { goal: 'nearest', assault: { kind: 'bomb', damage: 6, interval: 3, range: 0.6 }, detour: 0 },
  armorcar: { goal: 'gun', assault: ENEMIES.armorcar.assault, detour: ENEMIES.armorcar.detour },
  // Four charges at the fences, then it fights on as a soldier.
  sapper: { goal: 'fence', assault: ENEMIES.sapper.assault, detour: 0, charges: 4 },
  shield: { goal: 'gun', assault: ENEMIES.shield.assault, detour: ENEMIES.shield.detour },
  boat: { goal: 'gun', assault: { kind: 'bomb', damage: 40, interval: 3, range: 0.8 }, detour: 0 },
  dreadnought: { goal: 'hq', assault: ENEMIES.dreadnought.assault, detour: 0 },
};

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
