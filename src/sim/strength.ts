import { ENEMIES } from './content';
import { arcHpFactor, levelWaves } from './levels';
import { baseHpFactor } from './base';
import type { Game } from './game';
import { waveSpec, type WaveSpec } from './waves';

/**
 * Base mode, before an attack: a rough strength for each side, shown so the
 * player sees how the fight is likely to go. It ignores the layout (where the
 * guns stand, how the fences run), so it is a hint, not a forecast.
 *
 * The defence is the damage its finished guns deal per second; the attack is
 * the toughness of its hardest wave (health, armour counting extra) spread
 * over the seconds a wave is under fire. Both use the same unit, so equal
 * numbers mean an even fight (tuned with the bot in tests/base.test.ts).
 */
export const STRENGTH = {
  /** Seconds a wave spends under fire, on average. */
  exposure: 30,
  /** Each point of armour makes a unit this much tougher. */
  armour: 0.08,
  /** Faster units spend less time under fire: toughness grows with speed to this power. */
  speed: 1,
  /** Shown numbers are this many times the raw ones (nicer to read). */
  scale: 10,
};

export function defenceStrength(g: Game): number {
  let dps = 0;
  for (const t of g.towers) {
    if (t.job?.kind === 'build') continue;
    const l = g.levelOf(t);
    dps += (l.damage / l.fireInterval) * (1 + (l.splash ?? 0));
  }
  return Math.round(dps * STRENGTH.scale);
}

export function attackStrength(attack: number, waves: (n: number, level: number) => WaveSpec = waveSpec, total = levelWaves(attack)): number {
  const hpFactor = arcHpFactor(attack) * baseHpFactor(attack);
  let hardest = 0;
  for (let n = 1; n <= total; n++) {
    let toughness = 0;
    for (const grp of waves(n, attack).groups) {
      const e = ENEMIES[grp.enemy];
      toughness += grp.count * grp.hp * hpFactor * (1 + STRENGTH.armour * e.armor) * e.speed ** STRENGTH.speed;
    }
    hardest = Math.max(hardest, toughness);
  }
  return Math.round((hardest / STRENGTH.exposure) * STRENGTH.scale);
}
