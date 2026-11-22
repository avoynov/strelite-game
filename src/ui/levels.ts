import { t } from '../i18n';
import type { Mode } from '../sim/maps';
import { levelPages, LEVELS_PER_PAGE, levelWaves } from '../sim/levels';
import { starRow } from './hud';

/**
 * Level list in pages of 100: levels won, the next one to fight and the locked
 * rest of its page. The next page appears once the player reaches it.
 */

/** Missions from the muster; the base itself is not a level. */
const MODES: readonly Mode[] = ['path', 'arc'];

export interface LevelsCallbacks {
  /** Highest map level won (0 for none). */
  won(): number;
  /** Best stars on a level of the mode shown (0 when not won). */
  stars(level: number): number;
  /** Stars on all mission levels and medals earned. */
  totals(): { total: number; medals: number };
  /** The level being played now, or 0 when it is in the other mode. */
  current(): number;
  mode(): Mode;
  setMode(mode: Mode): void;
  play(level: number): void;
  close(): void;
}

export class LevelSelect {
  readonly el: HTMLElement;
  /** Page shown, 0-based. */
  private page = 0;

  constructor(private readonly cb: LevelsCallbacks) {
    this.el = document.createElement('div');
    this.el.className = 'levels';
    this.el.hidden = true;
    this.el.setAttribute('role', 'dialog');
    this.el.setAttribute('aria-modal', 'true');
    this.el.addEventListener('click', (ev) => {
      const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>('button[data-lv]');
      if (!btn || btn.disabled) return;
      if (btn.dataset.lv === 'close') {
        this.close();
        return;
      }
      const mode = MODES.find((m) => btn.dataset.lv === `mode-${m}`);
      if (mode) {
        this.cb.setMode(mode);
        this.page = levelPages(this.cb.won()) - 1;
        this.render();
        this.el.querySelector('.lv.next')?.scrollIntoView({ block: 'center' });
        return;
      }
      if (btn.dataset.lv === 'prev' || btn.dataset.lv === 'next') {
        this.page += btn.dataset.lv === 'next' ? 1 : -1;
        this.render();
        this.el.querySelector('.lv-list')?.scrollTo(0, 0);
        return;
      }
      const level = Number(btn.dataset.lv);
      this.el.hidden = true;
      this.cb.play(level);
    });
  }

  get isOpen(): boolean {
    return !this.el.hidden;
  }

  open(): void {
    // Start on the page of the next level to fight.
    this.page = levelPages(this.cb.won()) - 1;
    this.render();
    this.el.hidden = false;
    // Bring the next level to fight into view.
    this.el.querySelector('.lv.next')?.scrollIntoView({ block: 'center' });
  }

  close(): void {
    if (!this.isOpen) return;
    this.el.hidden = true;
    this.cb.close();
  }

  invalidate(): void {
    if (this.isOpen) this.render();
  }

  private render(): void {
    const won = this.cb.won();
    const current = this.cb.current();
    const totals = this.cb.totals();
    const pages = levelPages(won);
    this.page = Math.min(Math.max(0, this.page), pages - 1);
    const from = this.page * LEVELS_PER_PAGE + 1;
    const to = from + LEVELS_PER_PAGE - 1;
    const items: string[] = [];
    for (let n = from; n <= to; n++) {
      const state = n <= won ? 'won' : n === won + 1 ? 'next' : 'locked';
      items.push(`
        <li><button class="lv ${state}${n === current ? ' current' : ''}" data-lv="${n}" ${state === 'locked' ? 'disabled' : ''}>
          <span class="lv-num">${n}</span>
          <span class="lv-waves">${t('levels.waves', { n: levelWaves(n) })}</span>
          <span class="lv-tag">${state === 'won' ? starRow(this.cb.stars(n), 'stars lv-stars') : state === 'next' ? t('levels.next') : ''}</span>
        </button></li>`);
    }
    this.el.innerHTML = `
      <header class="lab-head">
        <div>
          <p class="lab-kicker">${t('building.muster')}</p>
          <h1 class="lab-title">${t('levels.title')}</h1>
          <p class="lv-total">${t('levels.stars', { n: totals.total, m: totals.medals })}</p>
        </div>
        <button class="win-x" data-lv="close" aria-label="${t('action.close')}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
      </header>
      <div class="lv-modes" role="tablist">
        ${MODES.map((m) => `<button class="lv-mode${this.cb.mode() === m ? ' on' : ''}" role="tab" aria-selected="${this.cb.mode() === m}" data-lv="mode-${m}"><b>${t(`mode.${m}`)}</b><span>${t(`mode.${m}.hint`)}</span></button>`).join('')}
      </div>
      ${pages > 1
        ? `<nav class="lv-pages">
            <button class="chip" data-lv="prev" ${this.page === 0 ? 'disabled' : ''} aria-label="${t('levels.prev')}">‹</button>
            <span>${t('levels.range', { from, to })}</span>
            <button class="chip" data-lv="next" ${this.page >= pages - 1 ? 'disabled' : ''} aria-label="${t('levels.nextPage')}">›</button>
          </nav>`
        : ''}
      <ol class="lv-list">${items.join('')}</ol>
      <footer class="lab-foot">
        <p class="lv-note">${t('levels.replay')}</p>
        <button class="btn" data-lv="close">${t('action.back')}</button>
      </footer>`;
  }
}
