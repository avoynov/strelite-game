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

/** Enemy health grows by this factor each step of strength… */
export const HP_GROWTH = 1.16;
/** Infantry, riders and drones grow slower: they come in larger numbers instead. */
export const SWARM_HP_GROWTH = 1.07;
const SWARM = new Set<EnemyId>(['infantry', 'moto', 'drone']);
/**
 * The main difficulty dials, tuned with the bot (see tests/balance.test.ts).
 * `hpScale`: every enemy's health is this many times its base.
 * `firstStrength`: strength of level 1's first wave.
 * `strengthStep`: each map level starts this much stronger than the one before,
 * up to `maxFirstStrength`.
 */
export const TUNING = { hpScale: 1.7, firstStrength: 4, strengthStep: 0.5, maxFirstStrength: 10 };
/** …and by this fraction of the base for each map level above the first… */
export const LEVEL_HP_GROWTH = 0.04;
/** …up to this map level; past it only the number of waves keeps growing. */
export const LEVEL_HP_CAP = 20;
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
 * Wave n of map level `level` (both 1-based). Its make-up follows its strength
 * k (see waveStrength): infantry every wave in growing numbers; riders from
 * k 2, trucks and drones from 3, APCs from 4, tanks from 5, and a fortress
 * closes every tenth step, each once its map level lets it attack. Health grows
 * faster than gun damage so upgrades matter, and a little with each map level.
 */
export function waveSpec(n: number, level = 1, hq = 0): WaveSpec {
  return waveOfStrength(waveStrength(n, level), level, hq);
}

/**
 * The player's base: per headquarters level (0-based) above the first,
 * `count` more of every unit (a share), each kind of unit joins the waves
 * `earlier` steps of strength sooner, and kinds open as if the attack were
 * `unlock` attacks further on. Tuned with the base bot (tests/base.test.ts).
 */
export const HQ_WAVES = { count: 0.2, earlier: 1, unlock: 2 };

/** A wave of strength k on a map level (see waveSpec); `hq` is the base's headquarters level, 0-based. */
export function waveOfStrength(k: number, level: number, hq = 0): WaveSpec {
  const levelScale = TUNING.hpScale * (1 + LEVEL_HP_GROWTH * (Math.min(level, LEVEL_HP_CAP) - 1));
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
  const has = (enemy: EnemyId, from: number) => enemyUnlocked(enemy, level + HQ_WAVES.unlock * hq) && k >= from - HQ_WAVES.earlier * hq;

  const groups: WaveGroup[] = [group('infantry', 10 + 4 * k, Math.max(0.2, 0.6 - 0.03 * k), 0)];
  if (has('moto', 2)) groups.push(group('moto', 3 + k, 1.1, 3));
  if (has('truck', 3)) groups.push(group('truck', 1 + Math.floor(k / 2), 1.6, 4));
  if (has('drone', 3)) groups.push(group('drone', 1 + Math.floor(k / 3), 1.2, 6));
  if (has('apc', 4)) groups.push(group('apc', 1 + Math.floor((k - 4) / 3), 3, 7));
  if (has('tank', 5)) groups.push(group('tank', 1 + Math.floor((k - 5) / 3) + (k % 5 === 0 ? 1 : 0), 5, 8));
  // The boss grows more gently than the waves around it: it is already huge.
  const bossScale = (1 + 0.1 * Math.max(0, k - 10)) * levelScale;
  if (has('fortress', 10) && k % 10 === 0) groups.push(group('fortress', 1, 1, 12, bossScale));
  return { groups, clearBonus: 15 + 3 * k };
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
