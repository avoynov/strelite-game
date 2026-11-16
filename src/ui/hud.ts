import { getLang, setLang, t, type MessageKey } from '../i18n';
import { TOWERS, type TowerId } from '../sim/content';
import type { ActionResult, Game } from '../sim/game';
import type { Selection } from '../render/boardRenderer';

export interface HudCallbacks {
  getSelection(): Selection | null;
  setSelection(sel: Selection | null): void;
  getSpeed(): number;
  setSpeed(speed: number): void;
  restart(): void;
}

const SPEEDS = [1, 2, 3];

const escapeHtml = (s: string) => s.replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]!);

/**
 * DOM overlay: top bar (gold, lives, wave, speed, language) and a bottom sheet
 * whose content follows the current selection. DOM keeps text crisp and
 * accessible on phones; the canvas only draws the board.
 */
export class Hud {
  private readonly top: HTMLElement;
  private readonly panel: HTMLElement;
  private readonly toast: HTMLElement;
  private readonly endScreen: HTMLElement;
  private lastTop = '';
  private lastPanel = '';
  private lastEnd = '';
  private toastTimer = 0;
  /** Default tower for the build button; Phase 5 adds a picker. */
  private buildDef: TowerId = 'crossbow';

  constructor(
    root: HTMLElement,
    private game: Game,
    private readonly cb: HudCallbacks,
  ) {
    root.innerHTML = `
      <header class="hud-top" id="hud-top"></header>
      <div class="toast" id="toast" role="status" aria-live="polite"></div>
      <section class="hud-panel" id="hud-panel"></section>
      <div class="end-screen" id="end-screen" hidden></div>`;
    this.top = root.querySelector('#hud-top')!;
    this.panel = root.querySelector('#hud-panel')!;
    this.toast = root.querySelector('#toast')!;
    this.endScreen = root.querySelector('#end-screen')!;
    root.addEventListener('click', (ev) => {
      const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>('button[data-action]');
      if (btn && !btn.disabled) this.onAction(btn.dataset.action!);
    });
  }

  setGame(game: Game): void {
    this.game = game;
    this.invalidate();
  }

  invalidate(): void {
    this.lastTop = this.lastPanel = this.lastEnd = '';
  }

  /** Height in CSS px the HUD covers at the top and bottom; the board fits between. */
  insets(): { top: number; bottom: number } {
    return { top: this.top.getBoundingClientRect().bottom, bottom: window.innerHeight - this.panel.getBoundingClientRect().top };
  }

  showToast(text: string): void {
    this.toast.textContent = text;
    this.toast.classList.add('show');
    window.clearTimeout(this.toastTimer);
    this.toastTimer = window.setTimeout(() => this.toast.classList.remove('show'), 1800);
  }

  showResult(r: ActionResult): void {
    if (r.ok) return;
    const key: Partial<Record<typeof r.reason, MessageKey>> = { noMoney: 'reason.noMoney', maxLevel: 'reason.maxLevel', notBuildable: 'hint.notBuildable' };
    const k = key[r.reason];
    if (k) this.showToast(t(k));
  }

  update(): void {
    const g = this.game;
    const speed = this.cb.getSpeed();
    const top = `
      <div class="stat" title="${t('hud.money')}"><span class="ico ico-gold" aria-hidden="true"></span><b>${g.money}</b></div>
      <div class="stat" title="${t('hud.lives')}"><span class="ico ico-heart" aria-hidden="true"></span><b>${g.lives}</b></div>
      <div class="stat wave">${t('hud.wave', { n: g.wave, total: g.totalWaves })}</div>
      <div class="spacer"></div>
      <button class="chip" data-action="speed" aria-label="${t('action.speed')}">${speed}×</button>
      <button class="chip" data-action="lang">${t('lang.switch')}</button>`;
    if (top !== this.lastTop) {
      this.top.innerHTML = top;
      this.lastTop = top;
    }

    const panel = this.panelHtml();
    if (panel !== this.lastPanel) {
      this.panel.innerHTML = panel;
      this.lastPanel = panel;
    }

    const end = g.phase === 'won' || g.phase === 'lost'
      ? `<div class="end-card">
           <h2>${t(g.phase === 'won' ? 'end.won' : 'end.lost')}</h2>
           <p>${t('end.summary', { n: g.phase === 'won' ? g.wave : Math.max(0, g.wave - 1) })}</p>
           <button class="btn primary" data-action="restart">${t('action.restart')}</button>
         </div>`
      : '';
    if (end !== this.lastEnd) {
      this.endScreen.innerHTML = end;
      this.endScreen.hidden = !end;
      this.lastEnd = end;
    }
  }

  private panelHtml(): string {
    const g = this.game;
    const sel = this.cb.getSelection();
    let body = `<p class="hint">${t('hint.tapCell')}</p>`;

    if (sel?.kind === 'cell') {
      const def = TOWERS[this.buildDef];
      const lvl = def.levels[0];
      const name = escapeHtml(t(`tower.${this.buildDef}`));
      body = `
        <div class="row">
          <div class="info">
            <div class="title">${name}</div>
            ${this.statsHtml(lvl.damage, lvl.fireInterval, lvl.range)}
          </div>
          <button class="btn primary" data-action="build" ${g.money < lvl.cost ? 'disabled' : ''}>
            ${t('action.build', { name })}<span class="cost"><span class="ico ico-gold"></span>${lvl.cost}</span>
          </button>
        </div>`;
    } else if (sel?.kind === 'tower') {
      const tower = g.towerAt(sel.x, sel.y);
      if (tower) {
        const lvl = g.levelOf(tower);
        const up = g.upgradeCost(tower);
        const s = tower.stats;
        const total = s.dealt + s.wasted;
        const wastedPct = total > 0 ? Math.round((s.wasted / total) * 100) : 0;
        body = `
          <div class="row">
            <div class="info">
              <div class="title">${escapeHtml(t(`tower.${tower.def}`))} · ${t('tower.level', { n: tower.level + 1 })}</div>
              ${this.statsHtml(lvl.damage, lvl.fireInterval, lvl.range)}
              <div class="stats muted">
                <span>${t('stat.dealt')} ${Math.round(s.dealt)}</span>
                <span>${t('stat.wasted')} ${Math.round(s.wasted)} (${wastedPct}%)</span>
                <span>${t('stat.kills')} ${s.kills}</span>
              </div>
            </div>
            <div class="actions">
              ${up === null
                ? `<button class="btn" disabled>${t('tower.maxLevel')}</button>`
                : `<button class="btn primary" data-action="upgrade" ${g.money < up ? 'disabled' : ''}>${t('action.upgrade')}<span class="cost"><span class="ico ico-gold"></span>${up}</span></button>`}
              <button class="btn" data-action="sell">${t('action.sell')}<span class="cost">+${g.sellValue(tower)}</span></button>
            </div>
          </div>`;
      }
    }

    const waveBtn = g.phase === 'build'
      ? `<button class="btn go" data-action="wave">${t('action.startWave', { n: g.wave + 1 })}</button>`
      : `<button class="btn go" disabled>${t('action.waveRunning')}</button>`;
    return `<div class="panel-body">${body}</div>${waveBtn}`;
  }

  private statsHtml(damage: number, interval: number, range: number): string {
    const rate = 1 / interval;
    return `<div class="stats">
      <span>${t('stat.damage')} <b>${damage}</b></span>
      <span>${t('stat.rate')} <b>${rate.toFixed(1)}</b></span>
      <span>${t('stat.dps')} <b>${(damage * rate).toFixed(1)}</b></span>
      <span>${t('stat.range')} <b>${range}</b></span>
    </div>`;
  }

  private onAction(action: string): void {
    const g = this.game;
    const sel = this.cb.getSelection();
    switch (action) {
      case 'build':
        if (sel?.kind === 'cell') {
          const r = g.build(this.buildDef, sel.x, sel.y);
          this.showResult(r);
          if (r.ok) this.cb.setSelection({ kind: 'tower', x: sel.x, y: sel.y });
        }
        break;
      case 'upgrade':
      case 'sell': {
        const tower = sel?.kind === 'tower' ? g.towerAt(sel.x, sel.y) : undefined;
        if (!tower) break;
        if (action === 'upgrade') this.showResult(g.upgrade(tower.id));
        else {
          g.sell(tower.id);
          this.cb.setSelection(null);
        }
        break;
      }
      case 'wave':
        g.startWave();
        break;
      case 'speed': {
        const i = SPEEDS.indexOf(this.cb.getSpeed());
        this.cb.setSpeed(SPEEDS[(i + 1) % SPEEDS.length]!);
        break;
      }
      case 'lang':
        setLang(getLang() === 'bg' ? 'en' : 'bg');
        break;
      case 'restart':
        this.cb.restart();
        break;
    }
    this.update();
  }
}
