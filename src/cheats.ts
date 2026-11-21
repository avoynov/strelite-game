/**
 * Testing switches in the pause screen (temporary): endless gold, and no
 * waiting for research or builders. Kept in the browser between visits.
 */
export interface Cheats {
  gold: boolean;
  instant: boolean;
}

const KEY = 'strelite.cheats';
/** Gold kept on hand while endless gold is on. */
export const CHEAT_GOLD = 1_000_000;

export function readCheats(): Cheats {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? 'null') as Partial<Cheats> | null;
    return { gold: v?.gold === true, instant: v?.instant === true };
  } catch {
    return { gold: false, instant: false };
  }
}

export function writeCheats(c: Cheats): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(c));
  } catch {
    // Not saved: this visit only.
  }
}
