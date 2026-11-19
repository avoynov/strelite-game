/** Chrome / Edge / Samsung: the install prompt the browser offers once the game is installable. */
interface InstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export type InstallWay =
  /** The browser's own dialog can be opened. */
  | 'prompt'
  /** iPhone / iPad: only by hand, through Share → Add to Home Screen. */
  | 'ios'
  /** Already installed, or this browser cannot install it. */
  | null;

let deferred: InstallPromptEvent | null = null;
let installed = false;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((fn) => fn());

// Registered when the module loads, before the game starts, so the early event is not missed.
window.addEventListener('beforeinstallprompt', (ev) => {
  ev.preventDefault(); // we show our own button instead of the browser's banner
  deferred = ev as InstallPromptEvent;
  notify();
});
window.addEventListener('appinstalled', () => {
  installed = true;
  deferred = null;
  notify();
});

/** Running as the installed app (home screen icon), not in a browser tab. */
export function isStandalone(): boolean {
  return window.matchMedia?.('(display-mode: standalone)').matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
}

export function isIos(): boolean {
  const ua = navigator.userAgent;
  // iPadOS reports itself as a Mac; touch gives it away.
  return /iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1);
}

/** How the game can be installed here, if at all. */
export function installWay(): InstallWay {
  if (installed || isStandalone()) return null;
  if (deferred) return 'prompt';
  if (isIos()) return 'ios';
  return null;
}

/** Open the browser's install dialog; true when the player accepted. */
export async function promptInstall(): Promise<boolean> {
  const ev = deferred;
  if (!ev) return false;
  deferred = null; // the event can be used once
  await ev.prompt();
  const { outcome } = await ev.userChoice;
  notify();
  return outcome === 'accepted';
}

export function onInstallChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
