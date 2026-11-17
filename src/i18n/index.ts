import { bg, type MessageKey } from './bg';
import { en } from './en';

export type Lang = 'bg' | 'en';
export type { MessageKey };

const tables: Record<Lang, Record<MessageKey, string>> = { bg, en };
const STORAGE_KEY = 'strelite.lang';

function loadLang(): Lang {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === 'bg' || v === 'en') return v;
  } catch {
    // storage unavailable (private mode etc.): fall back to default
  }
  return 'bg';
}

let current: Lang = loadLang();
const listeners = new Set<() => void>();

export function getLang(): Lang {
  return current;
}

export function setLang(lang: Lang): void {
  current = lang;
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // ignore
  }
  document.documentElement.lang = lang;
  listeners.forEach((fn) => fn());
}

export function onLangChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Translate a key, replacing `{name}` placeholders from params. */
export function t(key: MessageKey, params?: Record<string, string | number>): string {
  const s = tables[current][key];
  if (!params) return s;
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in params ? String(params[k]) : m));
}

/** Translate a key built at run time, or undefined when no such text exists (e.g. a new gun's blurb). */
export function tMaybe(key: string, params?: Record<string, string | number>): string | undefined {
  return key in tables[current] ? t(key as MessageKey, params) : undefined;
}
