import type { Targeting, TowerId } from './sim/content';

/** The targeting mode the player last set on each gun kind, kept between battles. */
const KEY = 'strelite.aim';

export function readAimPrefs(): Partial<Record<TowerId, Targeting>> {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? 'null') as unknown;
    return v && typeof v === 'object' ? (v as Partial<Record<TowerId, Targeting>>) : {};
  } catch {
    return {};
  }
}

export function writeAimPrefs(prefs: Partial<Record<TowerId, Targeting>>): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    // Not saved: this visit only.
  }
}
