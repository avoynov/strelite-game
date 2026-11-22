import { getLang, setLang, t, type Lang } from '../i18n';
import type { AudioSettings } from '../audio/audio';
import type { QualityChoice } from '../perf';
import type { InstallWay } from '../pwa/install';
import type { Cheats } from '../cheats';

export interface PauseCallbacks {
  audio(): AudioSettings;
  setAudio(s: Partial<AudioSettings>): void;
  quality(): QualityChoice;
  setQuality(q: QualityChoice): void;
  installWay(): InstallWay;
  install(): void;
  /** In the base the menu is the settings; in a mission it also leads back to the base. */
  inBase(): boolean;
  toBase(): void;
  /** Testing switches (temporary). */
  cheats(): Cheats;
  setCheats(c: Partial<Cheats>): void;
  /** The menu closed: play on. */
  resume(): void;
}

const QUALITIES: readonly QualityChoice[] = ['auto', 'high', 'low'];
const LANGS: readonly Lang[] = ['bg', 'en'];

/** iOS Share icon (square with an arrow), as Safari draws it. */
const SHARE_ICON = '<svg class="pm-share" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7.5 7.5 12 3l4.5 4.5"/><path d="M8 10H6a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-9a1 1 0 0 0-1-1h-2"/></svg>';
const ADD_ICON = '<svg class="pm-share" viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M12 8.5v7M8.5 12h7"/></svg>';

/**
 * The pause screen: play on, sound, graphics, language, and installing the
 * game. Opens from the pause button and by itself when the player leaves the app.
 */
export class PauseMenu {
  readonly el: HTMLElement;
  private iosHelp = false;

  constructor(private readonly cb: PauseCallbacks) {
    this.el = document.createElement('div');
    this.el.className = 'pause';
    this.el.hidden = true;
    this.el.setAttribute('role', 'dialog');
    this.el.setAttribute('aria-modal', 'true');
    this.el.addEventListener('click', (ev) => {
      // A tap on the dimmed backdrop plays on.
      if (ev.target === this.el) {
        this.close();
        return;
      }
      const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>('button[data-pm]');
      if (!btn || btn.disabled) return;
      const [what, value] = btn.dataset.pm!.split(':');
      switch (what) {
        case 'resume':
          this.close();
          return;
        case 'mute':
          this.cb.setAudio({ muted: !this.cb.audio().muted });
          break;
        case 'quality':
          this.cb.setQuality(value as QualityChoice);
          break;
        case 'lang':
          setLang(value as Lang);
          break;
        case 'install':
          if (this.cb.installWay() === 'ios') this.iosHelp = !this.iosHelp;
          else this.cb.install();
          break;
        case 'cheat': {
          const key = value as keyof Cheats;
          this.cb.setCheats({ [key]: !this.cb.cheats()[key] });
          break;
        }
        case 'toBase':
          this.el.hidden = true;
          this.cb.toBase();
          return;
      }
      this.render();
    });
    // Sliders set the level while dragging; the screen is not redrawn under the finger.
    this.el.addEventListener('input', (ev) => {
      const input = ev.target as HTMLInputElement;
      if (input.dataset.vol === 'music' || input.dataset.vol === 'sfx') this.cb.setAudio({ [input.dataset.vol]: Number(input.value) / 100, muted: false });
      const out = this.el.querySelector(`[data-out="${input.dataset.vol}"]`);
      if (out) out.textContent = `${input.value}%`;
    });
  }

  get isOpen(): boolean {
    return !this.el.hidden;
  }

  open(): void {
    this.iosHelp = false;
    this.render();
    this.el.hidden = false;
    this.el.querySelector<HTMLElement>('[data-pm="resume"]')?.focus({ preventScroll: true });
  }

  close(): void {
    if (this.el.hidden) return;
    this.el.hidden = true;
    this.cb.resume();
  }

  invalidate(): void {
    if (this.isOpen) this.render();
  }

  private render(): void {
    const a = this.cb.audio();
    const q = this.cb.quality();
    const way = this.cb.installWay();
    const pct = (v: number) => Math.round(v * 100);
    const slider = (key: 'music' | 'sfx') => `
      <label class="pm-slider${a.muted ? ' off' : ''}">
        <span>${t(`pause.${key}`)}</span>
        <input type="range" min="0" max="100" step="5" value="${pct(a[key])}" data-vol="${key}" aria-label="${t(`pause.${key}`)}" />
        <output data-out="${key}">${pct(a[key])}%</output>
      </label>`;
    const install = way
      ? `<section class="pm-install">
          <button class="btn primary pm-install-btn" data-pm="install">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 21h14"/></svg>
            ${t('install.button')}
          </button>
          <p class="pm-note">${t('install.why')}</p>
          ${way === 'ios' && this.iosHelp
            ? `<ol class="pm-ios">
                <li>${t('install.ios1', { icon: SHARE_ICON })}</li>
                <li>${t('install.ios2', { icon: ADD_ICON })}</li>
                <li>${t('install.ios3')}</li>
              </ol>`
            : ''}
        </section>`
      : '';
    const base = this.cb.inBase();
    this.el.innerHTML = `
      <div class="pm-card">
        <header class="pm-head">
          <p class="lab-kicker">${t(base ? 'pause.settingsKicker' : 'pause.kicker')}</p>
          <h1 class="lab-title">${t(base ? 'pause.settings' : 'pause.title')}</h1>
        </header>
        <button class="btn primary pm-resume" data-pm="resume">
          ${base ? t('action.back') : `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>${t('pause.resume')}`}
        </button>
        <section class="pm-group">
          <div class="pm-row">
            <h2>${t('pause.sound')}</h2>
            <button class="pm-toggle${a.muted ? '' : ' on'}" data-pm="mute" role="switch" aria-checked="${!a.muted}" aria-label="${t('pause.sound')}">
              <span>${t(a.muted ? 'pause.off' : 'pause.on')}</span><i></i>
            </button>
          </div>
          ${slider('music')}
          ${slider('sfx')}
        </section>
        <section class="pm-group">
          <h2>${t('pause.quality')}</h2>
          <div class="pm-seg" role="radiogroup">
            ${QUALITIES.map((v) => `<button class="${q === v ? 'on' : ''}" role="radio" aria-checked="${q === v}" data-pm="quality:${v}">${t(`quality.${v}`)}</button>`).join('')}
          </div>
          <p class="pm-note">${t(`quality.${q}.hint`)}</p>
        </section>
        <section class="pm-group">
          <h2>${t('pause.language')}</h2>
          <div class="pm-seg" role="radiogroup">
            ${LANGS.map((l) => `<button class="${getLang() === l ? 'on' : ''}" role="radio" aria-checked="${getLang() === l}" data-pm="lang:${l}">${t(`lang.${l}`)}</button>`).join('')}
          </div>
        </section>
        ${install}
        <section class="pm-group pm-test">
          <h2>${t('cheat.title')}</h2>
          ${(['gold', 'instant'] as const)
            .map((k) => {
              const on = this.cb.cheats()[k];
              return `<div class="pm-row">
                <span>${t(`cheat.${k}`)}</span>
                <button class="pm-toggle${on ? ' on' : ''}" data-pm="cheat:${k}" role="switch" aria-checked="${on}" aria-label="${t(`cheat.${k}`)}">
                  <span>${t(on ? 'pause.on' : 'pause.off')}</span><i></i>
                </button>
              </div>`;
            })
            .join('')}
        </section>
        ${base ? '' : `<footer class="pm-foot"><button class="btn" data-pm="toBase">${t('action.toBase')}</button></footer>`}
      </div>`;
  }
}
