import { t } from '../i18n';
import { LEVELS_AHEAD, levelWaves } from '../sim/levels';

/**
 * Level list: every level won so far, the next one to fight, and a long run of
 * locked ones after it, so the list always seems to go on a while further.
 */

export interface LevelsCallbacks {
  /** Highest map level won (0 for none). */
  won(): number;
  /** The level being played now. */
  current(): number;
  play(level: number): void;
  close(): void;
}

export class LevelSelect {
  readonly el: HTMLElement;

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
      const level = Number(btn.dataset.lv);
      this.el.hidden = true;
      this.cb.play(level);
    });
  }

  get isOpen(): boolean {
    return !this.el.hidden;
  }

  open(): void {
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
    const last = won + 1 + LEVELS_AHEAD;
    const items: string[] = [];
    for (let n = 1; n <= last; n++) {
      const state = n <= won ? 'won' : n === won + 1 ? 'next' : 'locked';
      items.push(`
        <li><button class="lv ${state}${n === current ? ' current' : ''}" data-lv="${n}" ${state === 'locked' ? 'disabled' : ''}>
          <span class="lv-num">${n}</span>
          <span class="lv-waves">${t('levels.waves', { n: levelWaves(n) })}</span>
          <span class="lv-tag">${state === 'won' ? t('levels.won') : state === 'next' ? t('levels.next') : ''}</span>
        </button></li>`);
    }
    this.el.innerHTML = `
      <header class="lab-head">
        <div>
          <p class="lab-kicker">${t('levels.kicker')}</p>
          <h1 class="lab-title">${t('levels.title')}</h1>
        </div>
      </header>
      <ol class="lv-list">${items.join('')}</ol>
      <footer class="lab-foot">
        <p class="lv-note">${t('levels.replay')}</p>
        <button class="btn" data-lv="close">${t('action.back')}</button>
      </footer>`;
  }
}
