/**
 * Overkill damage model.
 *
 * Damage above the target's remaining health is lost ("overkill"). This is the
 * core balancing rule of the game: heavy, slow guns waste much of their damage
 * on small targets, fast light guns waste little.
 */
export interface DamageResult {
  /** Health left after the hit (never below 0). */
  hpAfter: number;
  /** Damage that actually reduced health. */
  dealt: number;
  /** Damage lost because the target had less health than the hit. */
  overkill: number;
}

export function applyDamage(hp: number, damage: number): DamageResult {
  if (damage <= 0 || hp <= 0) {
    return { hpAfter: Math.max(0, hp), dealt: 0, overkill: Math.max(0, damage) };
  }
  const dealt = Math.min(hp, damage);
  return { hpAfter: hp - dealt, dealt, overkill: damage - dealt };
}
