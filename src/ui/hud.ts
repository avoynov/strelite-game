import { getLang, setLang, t, type MessageKey } from '../i18n';
import { FENCE_LEVELS, TOWER_IDS, TOWERS, type TowerDef, type TowerId, type TowerLevel } from '../sim/content';
import type { ActionResult, Game } from '../sim/game';
import type { Armed, Selection } from '../render/boardRenderer';

export interface HudCallbacks {
  getSelection(): Selection | null;
  setSelection(sel: Selection | null): void;
  /** Gun (or, in siege mode, fence) picked in the build menu, if any. */
  getArmed(): Armed | null;
  setArmed(def: Armed | null): void;
  /** CSS for a small picture of a gun, or '' when there is no art for it. */
  towerIcon(def: TowerId): string;
  getSpeed(): number;
  setSpeed(speed: number): void;
  /** Start over, on the given map level (default: the current one). */
  restart(level?: number): void;
  openArsenal(): void;
  openLab(): void;
  openLevels(): void;
  /** Gold this battle has put in the research treasury so far. */
  banked(): number;
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
      if (btn && !btn.disabled) this.onAction(btn.dataset.action!, btn.dataset.def);
    });
  }

  /** Start the given map level (from the level list). */
  restartAt(level: number): void {
    this.cb.restart(level);
    this.update();
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
    const key: Partial<Record<typeof r.reason, MessageKey>> = { noMoney: 'reason.noMoney', maxLevel: 'reason.maxLevel', levelLocked: 'reason.levelLocked', blocks: 'reason.blocks', notBuildable: 'hint.notBuildable', occupied: 'reason.occupied' };
    if (r.reason === 'locked') {
      this.showToast(t('reason.locked'));
      return;
    }
    const k = key[r.reason];
    if (k) this.showToast(t(k));
  }

  update(): void {
    const g = this.game;
    const speed = this.cb.getSpeed();
    const top = `
      <div class="stat" title="${t('hud.money')}"><span class="ico ico-gold" aria-hidden="true"></span><b>${g.money}</b></div>
      <div class="stat" title="${t('hud.lives')}"><span class="ico ico-heart" aria-hidden="true"></span><b>${g.lives}</b></div>
      <button class="stat wave" data-action="levels" title="${t('action.levels')}"><span>${g.mode !== 'path' ? `${t(`mode.${g.mode}`)} · ` : ''}${t('hud.level', { n: g.level })}</span><span>${t('hud.wave', { n: g.wave, total: g.totalWaves })}</span></button>
      <div class="spacer"></div>
      ${g.phase === 'build' ? `<button class="chip chip-ico" data-action="arsenal" aria-label="${t('arsenal.title')}" title="${t('arsenal.title')}"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="7"/><path d="M12 2v5M12 17v5M2 12h5M17 12h5"/></svg></button>` : ''}
      <button class="chip chip-ico" data-action="lab" aria-label="${t('action.lab')}" title="${t('action.lab')}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3"/><path d="M7.5 15h9"/></svg></button>
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
           <p class="end-banked"><span class="ico ico-gold" aria-hidden="true"></span>${t('end.banked', { n: this.cb.banked() })}</p>
           ${g.phase === 'won' ? `<button class="btn primary" data-action="next">${t('action.nextLevel', { n: g.level + 1 })}</button>` : ''}
           <button class="btn${g.phase === 'won' ? '' : ' primary'}" data-action="restart">${t(g.phase === 'won' ? 'action.restart' : 'action.retry')}</button>
           <button class="btn" data-action="lab">${t('action.lab')}</button>
           <button class="btn" data-action="levels">${t('action.levels')}</button>
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
    const armed = this.cb.getArmed();
    let body: string;

    if (sel?.kind === 'place') {
      const lvl: TowerLevel = g.levelStats(sel.def, 0);
      const ok = g.canBuildAt(sel.def, sel.cx, sel.cy);
      body = `
        <div class="row">
          ${this.iconHtml(sel.def)}
          <div class="info">
            <div class="title">${escapeHtml(t(`tower.${sel.def}`))}</div>
            ${this.statsHtml(g.defOf(sel.def), lvl)}
          </div>
          <div class="actions">
            <button class="btn primary" data-action="build" ${ok && g.money >= lvl.cost ? '' : 'disabled'}>
              ${t('action.build')}<span class="cost"><span class="ico ico-gold"></span>${lvl.cost}</span>
            </button>
            <button class="btn" data-action="cancel">${t('action.cancel')}</button>
          </div>
        </div>`;
    } else if (sel?.kind === 'fence' && g.fenceById(sel.id)) {
      const f = g.fenceById(sel.id)!;
      const up = g.fenceUpgradeCost(f);
      body = `
        <div class="row">
          <span class="gun-ico fence-ico fence-${f.level}" aria-hidden="true"></span>
          <div class="info">
            <div class="title">${escapeHtml(t(`fence.${f.level}` as MessageKey))}</div>
            <div class="stats"><span>${t('stat.hp')} <b>${Math.ceil(f.hp)}/${f.maxHp}</b></span></div>
          </div>
          <div class="actions">
            ${up === null
              ? `<button class="btn" disabled>${t('fence.max')}</button>`
              : `<button class="btn primary" data-action="fenceUp" ${g.money < up ? 'disabled' : ''}>${escapeHtml(t(`fence.${f.level + 1}` as MessageKey))}<span class="cost"><span class="ico ico-gold"></span>${up}</span></button>`}
            <button class="btn" data-action="fenceSell">${t('action.sell')}<span class="cost">+${g.fenceSellValue(f)}</span></button>
          </div>
        </div>`;
    } else if (sel?.kind === 'tower' && g.towerById(sel.id)) {
      const tower = g.towerById(sel.id)!;
      const lvl = g.levelOf(tower);
      const up = g.upgradeCost(tower);
      const s = tower.stats;
      const total = s.dealt + s.wasted;
      const wastedPct = total > 0 ? Math.round((s.wasted / total) * 100) : 0;
      body = `
        <div class="row">
          <div class="info">
            <div class="title">${escapeHtml(t(`tower.${tower.def}`))} · ${t('tower.level', { n: tower.level + 1 })}</div>
            ${this.statsHtml(g.defOf(tower.def), lvl)}
            <div class="stats muted">
              ${g.mode === 'siege' ? `<span>${t('stat.hp')} ${Math.ceil(tower.hp)}/${tower.maxHp}</span>` : ''}
              <span>${t('stat.dealt')} ${Math.round(s.dealt)}</span>
              <span>${t('stat.wasted')} ${Math.round(s.wasted)} (${wastedPct}%)</span>
              <span>${t('stat.kills')} ${s.kills}</span>
            </div>
          </div>
          <div class="actions">
            ${up === null
              ? `<button class="btn" disabled>${t('tower.maxLevel')}</button>`
              : !g.canRaise(tower)
              ? `<button class="btn" data-action="lab">${t('tower.levelLocked', { n: tower.level + 2 })}</button>`
              : `<button class="btn primary" data-action="upgrade" ${g.money < up ? 'disabled' : ''}>${t('action.upgrade')}<span class="cost"><span class="ico ico-gold"></span>${up}</span></button>`}
            <button class="btn" data-action="sell">${t('action.sell')}<span class="cost">+${g.sellValue(tower)}</span></button>
          </div>
        </div>`;
    } else {
      // Build menu: one card per gun; the picked one stays armed for placing.
      // Only the guns this map level allows.
      const cards = TOWER_IDS.filter((id) => g.isUnlocked(id)).map((id) => {
        const cost = TOWERS[id].levels[0].cost;
        return `
          <button class="card${armed === id ? ' armed' : ''}${g.money < cost ? ' poor' : ''}" data-action="pick" data-def="${id}" aria-pressed="${armed === id}">
            ${this.iconHtml(id)}
            <span class="card-name">${escapeHtml(t(`tower.${id}`))}</span>
            <span class="cost"><span class="ico ico-gold"></span>${cost}</span>
          </button>`;
      }).join('');
      const fenceCost = FENCE_LEVELS[0].cost;
      const fence = g.mode === 'siege'
        ? `
          <button class="card${armed === 'fence' ? ' armed' : ''}${g.money < fenceCost ? ' poor' : ''}" data-action="pick" data-def="fence" aria-pressed="${armed === 'fence'}">
            <span class="gun-ico fence-ico fence-0" aria-hidden="true"></span>
            <span class="card-name">${escapeHtml(t('fence.name'))}</span>
            <span class="cost"><span class="ico ico-gold"></span>${fenceCost}</span>
          </button>`
        : '';
      const hint = armed === 'fence' ? t('hint.fence', { cost: fenceCost }) : armed ? t('hint.place', { name: t(`tower.${armed}`) }) : t('hint.pick');
      // The fence card leads, so it is in view however many guns follow.
      body = `<div class="picker"><div class="cards">${fence}${cards}</div><p class="hint">${escapeHtml(hint)}</p></div>`;
    }

    const waveBtn = g.phase === 'build'
      ? `<button class="btn go" data-action="wave">${t('action.startWave', { n: g.wave + 1 })}</button>`
      : `<button class="btn go" disabled>${t('action.waveRunning')}</button>`;
    return `<div class="panel-body">${body}</div>${waveBtn}`;
  }

  private iconHtml(def: TowerId): string {
    const css = this.cb.towerIcon(def);
    return css ? `<span class="gun-ico"><span style="${css}"></span></span>` : `<span class="gun-ico gun-ico-none"></span>`;
  }

  private statsHtml(def: TowerDef, lvl: TowerLevel): string {
    const rate = 1 / lvl.fireInterval;
    // A flame has no shots: show how hot it starts and how hot it gets.
    const fire = def.projectile === 'beam'
      ? `<span>${t('stat.flame')} <b>${Math.round((def.rampFrom ?? lvl.damage) * (lvl.damage / def.levels[0].damage))}–${lvl.damage}</b></span>`
      : `<span>${t('stat.damage')} <b>${lvl.damage}</b></span>
      <span>${t('stat.rate')} <b>${rate.toFixed(rate < 1 ? 2 : 1)}</b></span>
      <span>${t('stat.dps')} <b>${(lvl.damage * rate).toFixed(1)}</b></span>`;
    return `<div class="stats">
      ${fire}
      <span>${t('stat.range')} <b>${lvl.range}</b></span>
      ${lvl.splash ? `<span>${t('stat.splash')} <b>${lvl.splash}</b></span>` : ''}
    </div>`;
  }

  private onAction(action: string, def?: string): void {
    const g = this.game;
    const sel = this.cb.getSelection();
    switch (action) {
      case 'pick': {
        if (def === 'fence') {
          this.cb.setArmed(this.cb.getArmed() === 'fence' ? null : 'fence');
          break;
        }
        const id = TOWER_IDS.find((d) => d === def);
        if (!id) break;
        this.cb.setArmed(this.cb.getArmed() === id ? null : id);
        if (g.money < TOWERS[id].levels[0].cost && this.cb.getArmed()) this.showToast(t('reason.noMoney'));
        break;
      }
      case 'build':
        if (sel?.kind === 'place') {
          const r = g.build(sel.def, sel.cx, sel.cy);
          this.showResult(r);
          // Stay armed so several guns of a kind can be placed in a row.
          if (r.ok) this.cb.setSelection(null);
        }
        break;
      case 'cancel':
        this.cb.setSelection(null);
        this.cb.setArmed(null);
        break;
      case 'upgrade':
      case 'sell': {
        const tower = sel?.kind === 'tower' ? g.towerById(sel.id) : undefined;
        if (!tower) break;
        if (action === 'upgrade') this.showResult(g.upgrade(tower.id));
        else {
          g.sell(tower.id);
          this.cb.setSelection(null);
        }
        break;
      }
      case 'fenceUp':
      case 'fenceSell': {
        const f = sel?.kind === 'fence' ? g.fenceById(sel.id) : undefined;
        if (!f) break;
        if (action === 'fenceUp') this.showResult(g.upgradeFence(f.id));
        else {
          g.sellFence(f.id);
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
      case 'next':
        this.cb.restart(g.level + 1);
        break;
      case 'arsenal':
        this.cb.openArsenal();
        break;
      case 'lab':
        this.cb.openLab();
        break;
      case 'levels':
        this.cb.openLevels();
        break;
    }
    this.update();
  }
}
