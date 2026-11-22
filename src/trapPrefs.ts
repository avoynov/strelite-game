const KEY = 'strelite.trapAuto';

/** Spent traps re-arm themselves between waves unless the player turned it off. */
export function readTrapAuto(): boolean {
  try {
    return localStorage.getItem(KEY) !== '0';
  } catch {
    return true;
  }
}

export function writeTrapAuto(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? '1' : '0');
  } catch {
    // Private mode or blocked storage: it just is not remembered.
  }
}
