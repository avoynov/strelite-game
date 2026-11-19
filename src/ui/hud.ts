import { t, type MessageKey } from '../i18n';
import { TOWER_IDS, type TowerDef, type TowerId, type TowerLevel } from '../sim/content';
import { isWreck, type ActionResult, type Building, type Game, type Structure } from '../sim/game';
import type { Armed, Selection } from '../render/boardRenderer';
import { BASE_RULES, builders, HQ_LEVELS, jobError, jobPrice, LAB_LEVELS, TREASURY_LEVELS, type BaseState, type BuildingKind, type JobError } from '../sim/base';
import { formatDuration } from './lab';

/** How an attack on the base (or the battle to win the headquarters back) ended. */
export interface BaseResult {
  kind: 'won' | 'broken' | 'fell' | 'retakeWon' | 'retakeLost';
  /** Gold the defence added to the treasury. */
  bonus: number;
  /** Units holding the headquarters, or the level it came back at (1-based). */
  n: number;
}

/** What the HUD needs of the player's base (the game's hub). */
export interface BaseHud {
  /** The saved base: attack number, building jobs, the buildings' levels. */
  state(): BaseState;
  startJob(what: BuildingKind): JobError | null;
  /** Rough strength of the defence and of the coming attack. */
  strength(): { you: number; enemy: number };
  /** Once the battle is over: how it went. */
  result(): BaseResult | null;
  /** Building timers run this many times faster (testing builds). */
  speed: number;
  /** The next level of each mission kind (the muster). */
  missions(): { path: number; arc: number };
  startMission(mode: 'path' | 'arc', level: number): void;
  openLevels(): void;
  /** The attack was provoked: the raid rides out. */
  provoked(): void;
}

const JOB_ERR: Record<JobError, MessageKey> = { maxLevel: 'reason.maxLevel', running: 'reason.running', noBuilder: 'reason.noBuilder', noGold: 'reason.noMoney', occupied: 'reason.occupiedHq' };

/** Icons drawn in line with the HUD's own (24×24, stroked). */
const ICON = {
  gear: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/></svg>',
  arsenal: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="7"/><path d="M12 2v5M12 17v5M2 12h5M17 12h5"/></svg>',
  pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>',
};

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
  /** Start over, on the given map level (default: the current one); in the base, the base as it stands. */
  restart(level?: number): void;
  openArsenal(): void;
  openLab(): void;
  /** Back to the base from a mission. */
  toBase(): void;
  /** Gold this battle has put in the research treasury so far. */
  banked(): number;
  /** The player's base, when this battle is fought at it. */
  base(): BaseHud | null;
  /** Stop the battle and open the pause screen (sound, graphics, language, install); in the base, the settings. */
  pause(): void;
  /** A build, upgrade or repair went through. */
  done?(): void;
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
    // Something no render produces, so the next update redraws (and hides an empty end screen).
    this.lastTop = this.lastPanel = this.lastEnd = '\0';
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
    if (r.ok) {
      this.cb.done?.();
      return;
    }
    const key: Partial<Record<typeof r.reason, MessageKey>> = { noMoney: 'reason.noMoney', maxLevel: 'reason.maxLevel', levelLocked: 'reason.levelLocked', blocks: 'reason.blocks', notBuildable: 'hint.notBuildable', occupied: 'reason.occupied', noBuilder: 'reason.noBuilder', busy: 'reason.busy', noArsenal: 'reason.noArsenal', wreck: 'reason.wreck' };
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
    const base = this.cb.base();
    const fighting = g.phase === 'wave' || (g.wave > 0 && g.phase === 'build') || g.raidTime !== null;
    let top: string;
    if (base) {
      const st = base.state();
      const free = Math.max(0, g.freeBuilders());
      const where = g.retake ? t('building.hq') : t('base.attack', { n: g.level });
      top = `
        <button class="stat" data-action="sel" data-def="treasury" title="${t('building.treasury')}"><span class="ico ico-gold" aria-hidden="true"></span><b>${g.money}</b></button>
        <div class="stat" title="${t('base.builders', { free, total: builders(st) })}"><span class="ico ico-hammer" aria-hidden="true"></span><b>${free}/${builders(st)}</b></div>
        ${fighting ? `<div class="stat wave"><span>${where}</span><span>${g.raidTime !== null && g.wave <= 1 && g.phase !== 'wave' ? t('hud.raid') : t('hud.wave', { n: g.wave, total: g.totalWaves })}</span></div>` : ''}
        <div class="spacer"></div>
        ${fighting ? `<button class="chip" data-action="speed" aria-label="${t('action.speed')}">${speed}×</button>` : ''}
        <button class="chip chip-ico" data-action="pause" aria-label="${t('action.settings')}" title="${t('action.settings')}">${ICON.gear}</button>`;
    } else {
      top = `
        <div class="stat" title="${t('hud.money')}"><span class="ico ico-gold" aria-hidden="true"></span><b>${g.money}</b></div>
        <div class="stat" title="${t('hud.lives')}"><span class="ico ico-heart" aria-hidden="true"></span><b>${g.lives}</b></div>
        <div class="stat wave"><span>${t(g.mode === 'arc' ? 'mission.arc' : 'mission.path', { n: g.level })}</span><span>${t('hud.wave', { n: g.wave, total: g.totalWaves })}</span></div>
        <div class="spacer"></div>
        ${g.phase === 'build' ? `<button class="chip chip-ico" data-action="arsenal" aria-label="${t('arsenal.title')}" title="${t('arsenal.title')}">${ICON.arsenal}</button>` : ''}
        <button class="chip" data-action="speed" aria-label="${t('action.speed')}">${speed}×</button>
        <button class="chip chip-ico pause-btn" data-action="pause" aria-label="${t('action.pause')}" title="${t('action.pause')}">${ICON.pause}</button>`;
    }
    if (top !== this.lastTop) {
      this.top.innerHTML = top;
      this.lastTop = top;
    }

    const panel = this.panelHtml();
    if (panel !== this.lastPanel) {
      this.panel.innerHTML = panel;
      this.lastPanel = panel;
    }

    const result = base?.result() ?? null;
    let end = '';
    if (base && result && (g.phase === 'won' || g.phase === 'lost')) {
      const head: Record<BaseResult['kind'], string> = {
        won: t('end.baseWon'),
        broken: t('end.baseBroken'),
        fell: t('end.baseLost'),
        retakeWon: t('end.retakeWon'),
        retakeLost: t('end.retakeLost'),
      };
      const text: Record<BaseResult['kind'], string> = {
        won: t('end.summary', { n: g.wave }),
        broken: t('end.baseBrokenText'),
        fell: t('end.hqHeld', { n: result.n }),
        retakeWon: t('end.retakeWonText', { n: result.n }),
        retakeLost: t('end.retakeLostText', { n: result.n }),
      };
      end = `<div class="end-card">
           <h2>${head[result.kind]}</h2>
           <p>${text[result.kind]}</p>
           ${result.bonus > 0 ? `<p class="end-banked"><span class="ico ico-gold" aria-hidden="true"></span>${t('end.baseBonus', { n: result.bonus })}</p>` : ''}
           <button class="btn primary" data-action="restart">${t('action.toBase')}</button>
         </div>`;
    } else if (!base && (g.phase === 'won' || g.phase === 'lost')) {
      end = `<div class="end-card">
           <h2>${t(g.phase === 'won' ? 'end.won' : 'end.lost')}</h2>
           <p>${t('end.summary', { n: g.phase === 'won' ? g.wave : Math.max(0, g.wave - 1) })}</p>
           <p class="end-banked"><span class="ico ico-gold" aria-hidden="true"></span>${t('end.banked', { n: this.cb.banked() })}</p>
           ${g.phase === 'won' ? `<button class="btn primary" data-action="next">${t(g.mode === 'arc' ? 'mission.arc' : 'mission.path', { n: g.level + 1 })}</button>` : ''}
           <button class="btn${g.phase === 'won' ? '' : ' primary'}" data-action="restart">${t(g.phase === 'won' ? 'action.restart' : 'action.retry')}</button>
           <button class="btn" data-action="toBase">${t('action.toBase')}</button>
         </div>`;
    }
    if (end !== this.lastEnd) {
      this.endScreen.innerHTML = end;
      this.endScreen.hidden = !end;
      this.lastEnd = end;
    }
  }

  private panelHtml(): string {
    const g = this.game;
    const base = this.cb.base();
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
            <button class="btn primary" data-action="build" ${ok && g.money >= g.buildCost(sel.def) ? '' : 'disabled'}>
              ${t('action.build')}<span class="cost"><span class="ico ico-gold"></span>${g.buildCost(sel.def)}</span>
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
            ${this.repairHtml(f)}
            <button class="btn" data-action="fenceSell">${t('action.sell')}<span class="cost">+${g.fenceSellValue(f)}</span></button>
          </div>
        </div>`;
    } else if (sel?.kind === 'building' && g.building(sel.what)) {
      body = this.buildingHtml(g.building(sel.what)!);
    } else if (sel?.kind === 'tower' && g.towerById(sel.id) && isWreck(g.towerById(sel.id)!)) {
      const tower = g.towerById(sel.id)!;
      const cost = g.rebuildCost(tower);
      body = `
        <div class="row">
          <div class="info">
            <div class="title">${escapeHtml(t(`tower.${tower.def}`))} · ${t('tower.level', { n: tower.level + 1 })} · ${t('stat.wreck')}</div>
            ${tower.job ? `<div class="stats job"><span>${t('building.inWork', { time: formatDuration((tower.job.endsAt - Date.now()) / 1000) })}</span></div>` : ''}
          </div>
          <div class="actions">
            ${tower.job ? '' : `<button class="btn primary" data-action="rebuildGun" ${g.money < cost ? 'disabled' : ''}>${t('building.rebuildIt')}<span class="cost"><span class="ico ico-gold"></span>${cost}</span></button>`}
            <button class="btn" data-action="sell">${t('action.sell')}<span class="cost">+${g.sellValue(tower)}</span></button>
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
            ${tower.job ? `<div class="stats job"><span>${t(tower.job.kind === 'build' ? 'job.build' : 'job.upgrade', { n: tower.level + 2, time: formatDuration((tower.job.endsAt - Date.now()) / 1000) })}</span></div>` : ''}
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
              : tower.job
              ? `<button class="btn" disabled>${t('action.upgrade')}</button>`
              : !g.canRaise(tower)
              ? `<button class="btn" data-action="lab">${t('tower.levelLocked', { n: tower.level + 2 })}</button>`
              : `<button class="btn primary" data-action="upgrade" ${g.money < up ? 'disabled' : ''}>${t('action.upgrade')}<span class="cost"><span class="ico ico-gold"></span>${up}</span></button>`}
            ${this.repairHtml(tower)}
            <button class="btn" data-action="sell">${t('action.sell')}<span class="cost">+${g.sellValue(tower)}</span></button>
          </div>
        </div>`;
    } else if (base) {
      // The base: no build bar; the arsenal sends guns and fences. A picked one is placed with a tap.
      const mend = g.repairAllCost();
      const hint = armed === 'fence' ? t('hint.fence', { cost: g.fenceCost() }) : armed ? t('hint.place', { name: t(`tower.${armed}`) }) : t('hint.tapBuilding');
      const lost = g.phase === 'wave' ? `<span class="strength">${t('base.lost', { n: Math.round(g.lostShare() * 100), max: Math.round(BASE_RULES.lossShare * 100) })}</span>` : '';
      body = `<div class="picker base-idle">
        <div class="base-row">
          <p class="hint">${escapeHtml(hint)}</p>
          ${armed ? `<button class="chip" data-action="cancel">${t('action.cancel')}</button>` : ''}
        </div>
        ${mend > 0 || lost ? `<div class="base-row">${lost}${mend > 0 && g.phase !== 'won' && g.phase !== 'lost' ? `<button class="chip" data-action="repairAll" ${g.money <= 0 ? 'disabled' : ''}>${t('action.repairAll')}<span class="cost"><span class="ico ico-gold"></span>${mend}</span></button>` : ''}</div>` : ''}
      </div>`;
    } else {
      // Build menu: one card per gun; the picked one stays armed for placing.
      // Only the guns this map level allows.
      const cards = TOWER_IDS.filter((id) => g.isUnlocked(id)).map((id) => {
        const cost = g.buildCost(id);
        return `
          <button class="card${armed === id ? ' armed' : ''}${g.money < cost ? ' poor' : ''}" data-action="pick" data-def="${id}" aria-pressed="${armed === id}">
            ${this.iconHtml(id)}
            <span class="card-name">${escapeHtml(t(`tower.${id}`))}</span>
            <span class="cost"><span class="ico ico-gold"></span>${cost}</span>
          </button>`;
      }).join('');
      const hint = armed && armed !== 'fence' ? t('hint.place', { name: t(`tower.${armed}`) }) : t('hint.pick');
      body = `<div class="picker"><div class="cards">${cards}</div><p class="hint">${escapeHtml(hint)}</p></div>`;
    }

    // In the base the attack is provoked (or the headquarters retaken) from the headquarters; the button only runs the waves after.
    const waveBtn = base && (g.wave === 0 || g.phase === 'won' || g.phase === 'lost')
      ? ''
      : g.phase === 'build' && g.raidTime === null
      ? `<button class="btn go" data-action="wave">${t('action.startWave', { n: g.wave + 1 })}</button>`
      : `<button class="btn go" disabled>${t('action.waveRunning')}</button>`;
    return `<div class="panel-body">${body}</div>${waveBtn}`;
  }

  /** Base mode: a repair button for a damaged part. */
  private repairHtml(s: Structure): string {
    const cost = this.game.repairCost(s);
    if (cost <= 0) return '';
    return `<button class="btn" data-action="repair" ${this.game.money < cost ? 'disabled' : ''}>${t('action.repair')}<span class="cost"><span class="ico ico-gold"></span>${cost}</span></button>`;
  }

  /** Base mode: a building's sheet: what it does, what it opens, raising it, mending or rebuilding it. */
  private buildingHtml(b: Building): string {
    const g = this.game;
    const base = this.cb.base()!;
    const st = base.state();
    const what = b.kind;
    // The saved base knows the level being built towards.
    const level = st.buildings[what].level;
    const ruined = b.hp <= 0;
    const job = st.jobs.find((j) => j.what === what);
    const price = jobPrice(st, what);
    const peace = g.phase === 'build' && g.wave === 0 && g.raidTime === null;
    let jobBtn = '';
    if (job) jobBtn = `<button class="btn" disabled>${t('building.inWork', { time: formatDuration((job.endsAt - Date.now()) / 1000) })}</button>`;
    else if (price) {
      const err = jobError(st, what, g.money);
      const label = price.kind === 'rebuild' ? t(price.cost ? 'building.rebuildIt' : 'building.rebuildFree') : t('building.upgrade', { n: level + 2 });
      jobBtn = `<button class="btn${ruined ? ' primary' : ''}" data-action="job" data-def="${what}" ${err && err !== 'noBuilder' ? 'disabled' : ''}>${label}${price.cost ? `<span class="cost"><span class="ico ico-gold"></span>${price.cost}</span>` : ''}<span class="lab-time">${formatDuration(price.seconds / base.speed)}</span></button>`;
    } else if (!ruined) jobBtn = `<button class="btn" disabled>${t('building.max')}</button>`;
    let fx = '';
    let main = '';
    if (ruined) fx = t(`ruin.${what}`);
    else if (what === 'hq') fx = t('building.hqFx', { r: HQ_LEVELS[level]!.radius, g: HQ_LEVELS[level]!.maxGun });
    else if (what === 'lab') fx = t('building.labFx', { n: level + 1, slots: LAB_LEVELS[level]!.slots, b: LAB_LEVELS[level]!.builders });
    else if (what === 'treasury') fx = t('building.treasuryFx', { n: TREASURY_LEVELS[level]!.protect });
    else fx = t(`building.${what}Fx`);
    if (what === 'hq' && st.occupied) {
      // Held by the enemy: build guns round it, then win it back.
      const guns = g.towers.some((x) => !isWreck(x) && x.job?.kind !== 'build');
      fx = t('base.occupiedFx', { n: st.occupied.length });
      if (peace) main = `<button class="btn primary" data-action="liberate" ${guns ? '' : 'disabled'}>${t('action.liberate')}</button>${guns ? '' : `<span class="muted-note">${t('base.needGuns')}</span>`}`;
    } else if (what === 'hq' && !ruined && peace) {
      const s = base.strength();
      main = `<span class="strength${s.you >= s.enemy ? ' ahead' : ''}">${t('base.strength', { a: s.you, b: s.enemy })}</span>
        <button class="btn primary" data-action="provoke" title="${escapeHtml(t('base.provokeHint'))}">${t('action.provoke')}</button>`;
    } else if (what === 'muster' && !ruined && peace) {
      const m = base.missions();
      main = `<button class="btn primary" data-action="mission" data-def="path">${t('mission.path', { n: m.path })}</button>
        <button class="btn primary" data-action="mission" data-def="arc">${t('mission.arc', { n: m.arc })}</button>
        <button class="btn" data-action="levels">${t('action.allLevels')}</button>`;
    } else if (what === 'arsenal' && !ruined && g.phase !== 'won' && g.phase !== 'lost') {
      main = `<button class="btn primary" data-action="arsenal">${t('action.guns')}</button>
        <button class="btn" data-action="pick" data-def="fence">${t('fence.name')}<span class="cost"><span class="ico ico-gold"></span>${g.fenceCost()}</span></button>`;
    } else if (what === 'lab') {
      main = `<button class="btn${ruined ? '' : ' primary'}" data-action="lab">${t('action.research')}</button>`;
    }
    const hp = ruined ? `<span>${t('building.ruins')}</span>` : `<span>${t('stat.hp')} <b>${Math.ceil(b.hp)}/${b.maxHp}</b></span>`;
    return `
        <div class="row building-sheet">
          <div class="info">
            <div class="title">${t(`building.${what}`)} · ${t('tower.level', { n: level + 1 })}</div>
            <div class="stats">${hp}<span>${escapeHtml(fx)}</span></div>
          </div>
          <div class="actions">
            ${main}
            ${what === 'hq' && st.occupied ? '' : jobBtn}
            ${this.repairHtml(b)}
          </div>
        </div>`;
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
          this.cb.setSelection(null);
          break;
        }
        const id = TOWER_IDS.find((d) => d === def);
        if (!id) break;
        this.cb.setArmed(this.cb.getArmed() === id ? null : id);
        if (g.money < g.buildCost(id) && this.cb.getArmed()) this.showToast(t('reason.noMoney'));
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
      case 'job': {
        const base = this.cb.base();
        const what = g.buildings.find((b) => b.kind === def)?.kind;
        if (!base || !what) break;
        const err = base.startJob(what);
        if (err) this.showToast(t(JOB_ERR[err]));
        else this.cb.done?.();
        break;
      }
      case 'repair': {
        const s: Structure | undefined =
          sel?.kind === 'tower' ? g.towerById(sel.id) : sel?.kind === 'fence' ? g.fenceById(sel.id) : sel?.kind === 'building' ? (g.building(sel.what) ?? undefined) : undefined;
        if (s) this.showResult(g.repair(s));
        break;
      }
      case 'repairAll':
        this.showResult(g.repairAll());
        break;
      case 'rebuildGun':
        if (sel?.kind === 'tower') this.showResult(g.rebuildGun(sel.id));
        break;
      case 'sel': {
        const b = g.buildings.find((x) => x.kind === def);
        if (b) this.cb.setSelection({ kind: 'building', what: b.kind });
        break;
      }
      case 'provoke': {
        const r = g.provoke();
        this.showResult(r);
        if (r.ok) {
          this.cb.setSelection(null);
          this.cb.base()?.provoked();
        }
        break;
      }
      case 'liberate': {
        const r = g.startWave();
        this.showResult(r);
        if (r.ok) this.cb.setSelection(null);
        break;
      }
      case 'mission': {
        const base = this.cb.base();
        if (!base || (def !== 'path' && def !== 'arc')) break;
        base.startMission(def, base.missions()[def]);
        return;
      }
      case 'toBase':
        this.cb.toBase();
        return;
      case 'speed': {
        const i = SPEEDS.indexOf(this.cb.getSpeed());
        this.cb.setSpeed(SPEEDS[(i + 1) % SPEEDS.length]!);
        break;
      }
      case 'pause':
        this.cb.pause();
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
        this.cb.base()?.openLevels();
        break;
    }
    this.update();
  }
}
