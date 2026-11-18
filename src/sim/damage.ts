/**
 * The two damage rules.
 *
 * Overkill: damage above the target's remaining health is lost. Heavy, slow
 * guns waste much of their damage on small targets, fast light guns waste little.
 *
 * Armour: every hit loses a fixed amount, `armor × (1 − pierce)`, but always
 * keeps at least a tenth of its damage. Light, fast guns lose most of their
 * damage on armoured targets; heavy guns barely notice. Together the two rules
 * make every gun strong at one end of the roster and weak at the other.
 */
export interface DamageResult {
  /** Health left after the hit (never below 0). */
  hpAfter: number;
  /** Damage that actually reduced health. */
  dealt: number;
  /** Damage lost because the target had less health than the hit. */
  overkill: number;
  /** Damage stopped by armour. */
  blocked: number;
}

/** A hit always keeps at least this fraction of its damage, however thick the armour. */
export const MIN_DAMAGE_FRACTION = 0.1;

/** Damage left after armour: `damage − armor × (1 − pierce)`, at least 10 % of `damage`. */
export function afterArmor(damage: number, armor = 0, pierce = 0): number {
  if (damage <= 0) return 0;
  const p = Math.min(1, Math.max(0, pierce));
  return Math.max(damage - armor * (1 - p), damage * MIN_DAMAGE_FRACTION);
}

export function applyDamage(hp: number, damage: number, armor = 0, pierce = 0): DamageResult {
  const through = afterArmor(damage, armor, pierce);
  const blocked = Math.max(0, damage) - through;
  if (through <= 0 || hp <= 0) {
    return { hpAfter: Math.max(0, hp), dealt: 0, overkill: through, blocked };
  }
  const dealt = Math.min(hp, through);
  return { hpAfter: hp - dealt, dealt, overkill: through - dealt, blocked };
}
