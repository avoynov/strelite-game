import { ENEMIES, type EnemyId } from './content';
import { levelWaves } from './levels';

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

/** Enemy health grows by this factor each step of strength… */
export const HP_GROWTH = 1.16;
/** Infantry, riders and drones grow slower: they come in larger numbers instead. */
export const SWARM_HP_GROWTH = 1.07;
const SWARM = new Set<EnemyId>(['infantry', 'moto', 'drone', 'rider', 'glider', 'sapper']);
/**
 * The main difficulty dials, tuned with the bot (see tests/balance.test.ts).
 * `hpScale`: every enemy's health is this many times its base.
 * `firstStrength`: strength of level 1's first wave.
 * `strengthStep`: each map level starts this much stronger than the one before,
 * up to `maxFirstStrength`.
 */
export const TUNING = { hpScale: 1.7, firstStrength: 4, strengthStep: 0.125, maxFirstStrength: 10 };
/** …and by this fraction of the base for each map level above the first… */
export const LEVEL_HP_GROWTH = 0.04;
/** …up to this map level… */
export const LEVEL_HP_CAP = 20;
/** …then by this fraction ("Средно") for each map level up to LATE_HP_CAP; past it only the number of waves keeps growing. */
export const LATE_HP_GROWTH = 0.03;
export const LATE_HP_CAP = 80;

/**
 * The bot's fit: a correction to enemy health on each act's check map (map
 * level, factor), log-interpolated between them and held past the last. It
 * puts every check map between what the act before it can hold and what the
 * act itself can (see tests/balance.test.ts). `probe` is for that search only.
 */
export const DIFFICULTY = {
  fit: [
    [1, 1],
    [5, 0.96],
    [10, 0.92],
    [16, 0.84],
    [23, 0.81],
    [31, 0.565],
    [40, 0.48],
    [51, 0.9],
    [64, 0.58],
    [80, 0.84],
  ] as Array<[level: number, factor: number]>,
  probe: 1,
};

function fitAt(level: number): number {
  const f = DIFFICULTY.fit;
  if (level <= f[0]![0]) return f[0]![1];
  for (let i = 1; i < f.length; i++) {
    const [l1, v1] = f[i]!;
    const [l0, v0] = f[i - 1]!;
    if (level <= l1) return Math.exp(Math.log(v0) + ((Math.log(v1) - Math.log(v0)) * (level - l0)) / (l1 - l0));
  }
  return f[f.length - 1]![1];
}

/** Every enemy's health on a map level, relative to its base (before the wave's own growth). */
export function levelHpScale(level: number): number {
  const plan = TUNING.hpScale * (1 + LEVEL_HP_GROWTH * (Math.min(level, LEVEL_HP_CAP) - 1) + LATE_HP_GROWTH * Math.max(0, Math.min(level, LATE_HP_CAP) - LEVEL_HP_CAP));
  return plan * fitAt(level) * DIFFICULTY.probe;
}
/** Gold per kill grows by this fraction of the base each step of strength. */
export const REWARD_GROWTH = 0.08;
/** No wave gets stronger than this; longer levels repeat their strongest. */
export const MAX_STRENGTH = 18;

/** The map level at which an enemy first attacks. */
export function enemyUnlocked(enemy: EnemyId, level: number): boolean {
  return level >= ENEMIES[enemy].unlockLevel;
}

/** How strong wave n (1-based) of a map level is, up to MAX_STRENGTH. */
export function waveStrength(n: number, level = 1): number {
  const first = Math.min(TUNING.maxFirstStrength, TUNING.firstStrength + Math.round(TUNING.strengthStep * (level - 1)));
  return Math.min(MAX_STRENGTH, first + n - 1);
}

/**
 * Wave n of map level `level` (both 1-based), of `total` waves. Its make-up
 * follows its strength k (see waveStrength): infantry every wave in growing
 * numbers; riders from k 2, trucks and drones from 3, APCs from 4, tanks from
 * 5, each once its map level lets it attack. The eight newer units join one
 * per act from map 10 (see NEWER), and the older seven thin out evenly so the
 * wave weighs the same. From map 5 the last wave brings the boss: the
 * fortress, from map 80 the dreadnought (with the fortress then a regular on
 * every second strong wave). Health grows faster than gun damage so upgrades
 * matter, and a little with each map level.
 */
export function waveSpec(n: number, level = 1, hq = 0, total = levelWaves(level)): WaveSpec {
  return waveOfStrength(waveStrength(n, level), level, hq, { boss: n === total, even: n % 2 === 0 });
}

/**
 * The player's base: per headquarters level (0-based) above the first,
 * `count` more of every unit (a share), each kind of unit joins the waves
 * `earlier` steps of strength sooner, and kinds open as if the attack were
 * `unlock` attacks further on. Tuned with the base bot (tests/base.test.ts).
 */
export const HQ_WAVES = { count: 0.2, earlier: 1, unlock: 2 };

/** A wave's weight: health, armour counting extra, and speed (what it takes to stop it). */
const WEIGHT_ARMOUR = 0.08;
export function groupWeight(g: Pick<WaveGroup, 'enemy' | 'count' | 'hp'>): number {
  const e = ENEMIES[g.enemy];
  return g.count * g.hp * (1 + WEIGHT_ARMOUR * e.armor) * e.speed;
}

/**
 * The newer units: from which strength each comes (on and after its own map
 * level), how many (by strength), how they come in, and after how long.
 */
interface Newer {
  enemy: EnemyId;
  from: number;
  count: (k: number) => number;
  interval: number;
  delay: number;
  /** A second band this many seconds later from strength 14. */
  second?: number;
}
const NEWER: readonly Newer[] = [
  { enemy: 'wagon', from: 6, count: (k) => (k < 14 ? 1 : 2), interval: 3, delay: 7.5 },
  { enemy: 'rider', from: 6, count: (k) => (k <= 11 ? 6 : k <= 15 ? 7 : 8), interval: 0.25, delay: 2, second: 9 },
  { enemy: 'glider', from: 6, count: (k) => (k < 12 ? 5 : k < 15 ? 6 : k < 17 ? 7 : 8), interval: 0.3, delay: 6 },
  { enemy: 'armorcar', from: 8, count: (k) => (k < 14 ? 1 : 2), interval: 3, delay: 6 },
  { enemy: 'sapper', from: 8, count: (k) => 3 + Math.min(2, Math.floor((k - 8) / 4)), interval: 1.25, delay: 5, second: 9 },
  { enemy: 'shield', from: 10, count: (k) => (k < 17 ? 1 : 2), interval: 6, delay: 6.5 },
  { enemy: 'boat', from: 10, count: (k) => (k < 16 ? 1 : 2), interval: 6, delay: 9 },
];
/** The dreadnought's escort that comes with it (more come out as it breaks up). */
const ESCORT = ENEMIES.dreadnought.escort.units;

/** Builds a wave's groups on a map level: health, bounty and the headquarters' extra numbers. */
function groupMaker(k: number, level: number, hq: number) {
  const levelScale = levelHpScale(level);
  // Light units grow mostly in numbers, so overkill keeps biting late in the game.
  const grow = (enemy: EnemyId) => Math.pow(SWARM.has(enemy) ? SWARM_HP_GROWTH : HP_GROWTH, k - 1) * levelScale;
  const more = 1 + HQ_WAVES.count * hq;
  const group = (enemy: EnemyId, count: number, interval: number, delay: number, hpScale = grow(enemy)): WaveGroup => ({
    enemy,
    // A kind brought in early by the headquarters still comes at least once.
    count: Math.max(1, Math.round(count * more)),
    hp: Math.round(ENEMIES[enemy].baseHp * hpScale),
    interval,
    delay,
    // Later waves pay more per unit, so the bigger guns stay affordable.
    reward: Math.round(ENEMIES[enemy].baseReward * (1 + REWARD_GROWTH * (k - 1))),
  });
  const opens = (enemy: EnemyId) => enemyUnlocked(enemy, level + HQ_WAVES.unlock * hq);
  const has = (enemy: EnemyId, from: number) => opens(enemy) && k >= from - HQ_WAVES.earlier * hq;
  // The boss grows more gently than the waves around it: it is already huge.
  const bossScale = (1 + 0.1 * Math.max(0, k - 10)) * levelScale;
  return { group, opens, has, bossScale };
}

/** The older seven units of a wave of strength k, before they thin out for the newcomers. */
export function olderGroups(k: number, level: number, hq = 0): WaveGroup[] {
  const { group, has } = groupMaker(k, level, hq);
  const old: WaveGroup[] = [group('infantry', 10 + 4 * k, Math.max(0.2, 0.6 - 0.03 * k), 0)];
  if (has('moto', 2)) old.push(group('moto', 3 + k, 1.1, 3));
  if (has('truck', 3)) old.push(group('truck', 1 + Math.floor(k / 2), 1.6, 4));
  if (has('drone', 3)) old.push(group('drone', 1 + Math.floor(k / 3), 1.2, 6));
  if (has('apc', 4)) old.push(group('apc', 1 + Math.floor((k - 4) / 3), 3, 7));
  if (has('tank', 5)) old.push(group('tank', 1 + Math.floor((k - 5) / 3) + (k % 5 === 0 ? 1 : 0), 5, 8));
  return old;
}

/** A wave of strength k on a map level (see waveSpec); `hq` is the base's headquarters level, 0-based. */
export function waveOfStrength(k: number, level: number, hq = 0, opts: { boss?: boolean; even?: boolean } = {}): WaveSpec {
  const { group, opens, has, bossScale } = groupMaker(k, level, hq);
  const old = olderGroups(k, level, hq);
  const target = old.reduce((s, g) => s + groupWeight(g), 0);

  const newer: WaveGroup[] = [];
  for (const n of NEWER) {
    if (!has(n.enemy, n.from)) continue;
    const kk = Math.max(k, n.from);
    newer.push(group(n.enemy, n.count(kk), n.interval, n.delay));
    if (n.second && k >= 14 - HQ_WAVES.earlier * hq) newer.push(group(n.enemy, n.count(kk), n.interval, n.delay + n.second));
  }
  const bosses: WaveGroup[] = [];
  const late = opens('dreadnought');
  if (opts.boss && opens('fortress')) {
    if (late) {
      bosses.push(group('dreadnought', 1, 1, 12, bossScale));
      for (const u of ESCORT) bosses.push(group(u.enemy as EnemyId, u.count, 0.5, 12));
    } else bosses.push(group('fortress', 1, 1, 12, bossScale));
  }
  if (late && opts.even && k >= 15) bosses.push(group('fortress', 1, 1, 10, bossScale));

  // The older seven thin out evenly so the newcomers and the boss do not make the wave heavier.
  const keep = Math.max(0, Math.min(1, (target - [...newer, ...bosses].reduce((s, g) => s + groupWeight(g), 0)) / target));
  if (keep < 1) for (const g of old) g.count = Math.max(1, Math.round(g.count * keep));
  return { groups: [...old, ...newer, ...bosses], clearBonus: 15 + 3 * k };
}

/** Gold a wave pays: every unit's bounty and the bonus for clearing it. */
export function waveGold(w: WaveSpec): number {
  return w.groups.reduce((s, g) => s + g.count * g.reward, 0) + w.clearBonus;
}

/**
 * Gold a player would have taken from the weaker waves before a level's first
 * one (strengths 1 .. k−1). A level that starts strong starts rich in step,
 * as if those waves had been fought.
 */
export function goldBefore(level: number): number {
  let sum = 0;
  for (let k = TUNING.firstStrength; k < waveStrength(1, level); k++) sum += waveGold(waveOfStrength(k, level));
  return sum;
}
