import { t, type MessageKey } from '../i18n';
import type { GunPortrait } from '../render/towers/spriteTowerView';
import { TOWERS, type TowerId } from '../sim/content';
import {
  completeSets,
  inTree,
  itemCost,
  RESEARCH,
  setItems,
  itemSeconds,
  labSlots,
  MASTERY_DAMAGE,
  MASTERY_GOLD,
  RESEARCH_SETS,
  researchItem,
  setOf,
  setProgress,
  startError,
  status,
  suggestNext,
  treeProgress,
  type LabInfo,
  type ResearchItem,
  type ResearchSet,
  type ResearchState,
  type SetId,
  type StartError,
} from '../sim/research';
import { PanZoom } from './panZoom';

/**
 * "Лаборатория": the research tree as eight sets to complete. Each gun is a
 * row (the gun, levels IV and V, its effect); the Fortress (boosts) closes the
 * list. A full row earns a medal and a small bonus. Lines show what leads to
 * what: the guns down the left, the effects down the right.
 */

export interface LabCallbacks {
  state(): ResearchState;
  /** The laboratory in the base: its level and whether it stands. */
  lab(): LabInfo;
  start(id: string): StartError | null;
  /** Timers run this many times faster than listed (testing builds). */
  speed: number;
  /** A clean picture of a gun at a level. */
  portrait(def: TowerId, level: number): GunPortrait | undefined;
  /** Calls back when more gun art has loaded; returns an unsubscribe. */
  onArt?(fn: () => void): () => void;
  /** A set was just completed. */
  celebrate?(): void;
  close(): void;
}

const ERR: Record<StartError, MessageKey> = { busy: 'lab.busy', noGold: 'lab.noGold', locked: 'lab.lockedHint', done: 'lab.done', noLab: 'lab.noLab', hqLevel: 'lab.hqLevelHint', labLevel: 'lab.labLevelHint' };

const pct = (v: number) => Math.round(v * 100);
const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX'];
const SEEN_KEY = 'strelite.lab.seen';
const MEDALS_KEY = 'strelite.lab.medals';

/** "2 ч 15 мин", "3 д 4 ч", "45 сек": the two largest units. */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds));
  const parts: [number, MessageKey][] = [
    [Math.floor(s / 86400), 'unit.day'],
    [Math.floor((s % 86400) / 3600), 'unit.hour'],
    [Math.floor((s % 3600) / 60), 'unit.min'],
    [s % 60, 'unit.sec'],
  ];
  const first = parts.findIndex(([n]) => n > 0);
  if (first < 0) return `0 ${t('unit.sec')}`;
  return parts
    .slice(first, first + 2)
    .filter(([n]) => n > 0)
    .map(([n, k]) => `${n} ${t(k)}`)
    .join(' ');
}

export function itemName(item: ResearchItem): string {
  const e = item.effect;
  if (e.kind === 'gun') return t(`tower.${e.gun}` as MessageKey);
  if (e.kind === 'maxLevel') return t('lab.levelName', { gun: t(`tower.${e.gun}` as MessageKey), n: e.level });
  if (e.kind === 'trap') return t('lab.trapLevel', { trap: t(`trap.${e.trap}` as MessageKey), n: ROMAN[e.level]! });
  return t(`research.${item.id}` as MessageKey);
}

/** What the item does, in words, built from its numbers. */
export function itemEffect(item: ResearchItem): string {
  const e = item.effect;
  switch (e.kind) {
    case 'gun':
      return t('lab.fx.gun');
    case 'maxLevel':
      return t('lab.fx.level', { n: e.level });
    case 'damage':
      return t('lab.fx.damage', { n: pct(e.add) });
    case 'reload':
      return t('lab.fx.reload', { n: pct(1 - e.mul) });
    case 'startGold':
      return t('lab.fx.startGold', { n: e.add });
    case 'lives':
      return t('lab.fx.lives', { n: e.add });
    case 'aim':
      return t('lab.fx.aim', { gun: t(`tower.${e.gun}` as MessageKey), mode: t(`target.${e.mode}` as MessageKey) });
    case 'trap':
      return t('lab.fx.trap', { trap: t(`trap.${e.trap}` as MessageKey), n: pct(e.add) });
    case 'burningTar':
      return t('lab.fx.burningTar');
    case 'gunMod': {
      const m = e.mods;
      const parts: string[] = [];
      if (m.pierce) parts.push(t('lab.fx.pierce', { n: pct(m.pierce) }));
      if (m.passThrough) parts.push(t('lab.fx.passThrough', { n: m.passThrough }));
      if (m.splash) parts.push(t('lab.fx.splash', { n: m.splash }));
      if (m.range) parts.push(t('lab.fx.range', { n: m.range }));
      if (m.reload) parts.push(t('lab.fx.reload', { n: pct(1 - m.reload) }));
      if (m.rampTime) parts.push(t('lab.fx.ramp', { n: Math.round(1 / m.rampTime) }));
      if (m.damage) parts.push(t('lab.fx.damage', { n: pct(m.damage - 1) }));
      if (m.stun) parts.push(t('lab.fx.stun', { n: pct(m.stun - 1) }));
      if (m.cone) parts.push(t('lab.fx.cone', { n: Math.round(((TOWERS.flasher.cone + m.cone) * 360) / Math.PI) }));
      if (m.flashDamage) parts.push(t('lab.fx.flashDamage'));
      if (m.bigEvery) parts.push(t('lab.fx.bigEvery', { n: m.bigEvery }));
      if (m.bounces) parts.push(t('lab.fx.bounces', { n: m.bounces }));
      if (m.bounceLoss) parts.push(t('lab.fx.bounceLoss', { n: pct(TOWERS.ricochet.bounceLoss + m.bounceLoss) }));
      if (m.killGold) parts.push(t('lab.fx.killGold', { n: pct(m.killGold) }));
      if (m.retarget) parts.push(t('lab.fx.retarget', { n: m.retarget }));
      if (m.spool) parts.push(t('lab.fx.spool', { n: 40, s: 1.5 }));
      if (m.darts) parts.push(t('lab.fx.darts', { n: m.darts }));
      return `${t(`tower.${e.gun}` as MessageKey)}: ${parts.join(', ')}`;
    }
  }
}

export function setName(id: SetId): string {
  return id === 'fortress' ? t('lab.set.fortress') : id === 'traps' ? t('lab.set.traps') : t(`tower.${id}` as MessageKey);
}

/** The bonus a full set gives, in words. */
export function setBonus(id: SetId): string {
  if (id === 'traps') return t('lab.bonus.traps', { n: pct(MASTERY_DAMAGE) });
  return id === 'fortress' ? t('lab.bonus.fortress', { n: pct(MASTERY_GOLD) }) : t('lab.bonus.gun', { n: pct(MASTERY_DAMAGE), gun: setName(id) });
}

const esc = (s: string) => s.replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]!);

/** How a node looks: research status, refined by whether it can start right now. */
type NodeState = 'done' | 'active' | 'go' | 'ready' | 'lab' | 'locked';

// ------------------------------------------------------------------ shapes

/** Node outlines in a 56×56 box, each starting at the top so a progress stroke fills clockwise from 12 o'clock. */
const SHAPE = {
  oct: 'M28 4.5H37.7L51.5 18.3V37.7L37.7 51.5H18.3L4.5 37.7V18.3L18.3 4.5Z',
  circle: 'M28 3.5a24.5 24.5 0 1 1 0 49a24.5 24.5 0 1 1 0-49Z',
  hex: 'M28 3L49.7 15.5V40.5L28 53L6.3 40.5V15.5Z',
} as const;
type Shape = keyof typeof SHAPE;

const ICON = {
  spark: '<svg class="fill" viewBox="0 0 24 24"><path d="M12 2.5l2.1 6.3 6.4 2.2-6.4 2.2L12 19.5l-2.1-6.3-6.4-2.2 6.4-2.2z"/></svg>',
  coins: '<svg viewBox="0 0 24 24"><ellipse cx="12" cy="7" rx="7" ry="3"/><path d="M5 7v5c0 1.7 3.1 3 7 3s7-1.3 7-3V7"/><path d="M5 12v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5"/></svg>',
  shell: '<svg viewBox="0 0 24 24"><path d="M12 2.5c2.8 2.6 4 5.6 4 8.5v8.5H8V11c0-2.9 1.2-5.9 4-8.5z"/><path d="M8 15.5h8M10 19.5v2M14 19.5v2"/></svg>',
  shield: '<svg viewBox="0 0 24 24"><path d="M12 3l7 3v6c0 4.4-3 7.4-7 9-4-1.6-7-4.6-7-9V6z"/><path d="M9 12l2 2 4-4"/></svg>',
  reload: '<svg viewBox="0 0 24 24"><path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5v4h-4"/><path d="M12 8.5V12l2.5 1.5"/></svg>',
  lock: '<svg viewBox="0 0 24 24"><rect x="6" y="11" width="12" height="9" rx="2"/><path d="M9 11V8a3 3 0 0 1 6 0v3"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l2.5 1.5"/></svg>',
  flask: '<svg viewBox="0 0 24 24"><path d="M9.5 3h5M10.5 3v5.5L5 18.5A1.7 1.7 0 0 0 6.5 21h11a1.7 1.7 0 0 0 1.5-2.5L13.5 8.5V3"/><path d="M7.5 15h9"/></svg>',
  sight: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="7.5"/><circle cx="12" cy="12" r="1.6" class="dot"/><path d="M12 2.5v5M12 16.5v5M2.5 12h5M16.5 12h5"/></svg>',
  trap: '<svg viewBox="0 0 24 24"><path d="M3 15.5h18"/><path d="M5 15.5l2.2-6 2.2 6M9.6 15.5l2.4-7 2.4 7M14.6 15.5l2.2-6 2.2 6"/><path d="M4 19.5h16"/></svg>',
  castle:
    '<svg viewBox="0 0 24 24"><path d="M3.5 21V8.5h3V11h2.5V8.5h3V11h2.5V8.5h3V11h3V21z"/><path d="M10 21v-4.5a2 2 0 0 1 4 0V21"/><path d="M3.5 21h17"/></svg>',
} as const;

function shapeOf(item: ResearchItem): Shape {
  const k = item.effect.kind;
  return k === 'maxLevel' || k === 'trap' ? 'oct' : k === 'gunMod' || k === 'aim' || k === 'burningTar' ? 'circle' : 'hex';
}

function glyphOf(item: ResearchItem): string {
  const e = item.effect;
  switch (e.kind) {
    case 'maxLevel':
      return ROMAN[e.level] ?? String(e.level);
    case 'gunMod':
      return ICON.spark;
    case 'startGold':
      return ICON.coins;
    case 'damage':
      return ICON.shell;
    case 'lives':
      return ICON.shield;
    case 'reload':
      return ICON.reload;
    case 'gun':
      return ICON.flask;
    case 'aim':
      return ICON.sight;
    case 'trap':
      return ROMAN[e.level] ?? String(e.level);
    case 'burningTar':
      return ICON.spark;
  }
}

/** The outline of a node: fill, rim, and (while it runs) a progress stroke. */
function shapeSvg(d: string, active: boolean, ends = 0, total = 1, box = '0 0 56 56'): string {
  const prog = active ? `<path class="p" d="${d}" pathLength="100" stroke-dasharray="0 100" data-ends="${ends}" data-total="${total}"/>` : '';
  return `<svg class="sh" viewBox="${box}" aria-hidden="true"><path class="f" d="${d}"/><path class="r" d="${d}"/>${prog}</svg>`;
}

/** Each set's colour, as "r, g, b": wood, olive, steel, bronze, stone, ember, arc light, brass. */
const SET_TINT: Record<SetId, string> = {
  crossbow: '196, 140, 82',
  zis3: '138, 160, 96',
  howitzer: '128, 150, 176',
  scorpion: '182, 132, 92',
  trebuchet: '176, 162, 132',
  greekfire: '214, 108, 62',
  railgun: '96, 184, 222',
  zadnoper: '150, 120, 84',
  flasher: '236, 214, 120',
  rockets: '214, 82, 72',
  tarkan: '160, 140, 112',
  ricochet: '170, 176, 184',
  glass: '244, 196, 92',
  harpoon: '170, 196, 200',
  bees: '200, 200, 210',
  fortress: '211, 168, 92',
  traps: '150, 132, 104',
};

const CARD = 'M14 1.5H60A12.5 12.5 0 0 1 72.5 14V70A12.5 12.5 0 0 1 60 82.5H14A12.5 12.5 0 0 1 1.5 70V14A12.5 12.5 0 0 1 14 1.5Z';

function readList(key: string): string[] | null {
  try {
    const v = JSON.parse(localStorage.getItem(key) ?? 'null') as unknown;
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : null;
  } catch {
    return null;
  }
}

function writeList(key: string, list: Iterable<string>): void {
  try {
    localStorage.setItem(key, JSON.stringify([...list]));
  } catch {
    // Not saved: this visit only.
  }
}

/** Draw a gun picture into a box `w`×`h`, centred. */
function paintGun(el: HTMLElement, p: GunPortrait | undefined, w: number, h: number, zoom: number): void {
  if (!p) {
    el.textContent = '';
    return;
  }
  const [hx, hy] = p.half ?? [p.reach, p.reach];
  // The picture's box holds the gun at every heading; one heading fills less of it, so zoom in.
  const k = Math.min(w / (2 * hx), h / (2 * hy)) * zoom;
  const [fx, fy, fw, fh] = p.frame;
  let img = el.firstElementChild as HTMLElement | null;
  if (!img) {
    img = document.createElement('span');
    el.appendChild(img);
  }
  img.style.cssText =
    `width:${fw}px;height:${fh}px;background-image:url('${p.url}');` +
    `background-position:-${fx}px -${fy}px;background-size:${p.sheetSize[0]}px ${p.sheetSize[1]}px;` +
    `transform:scale(${k.toFixed(4)}) translate(${p.offset[0]}px,${p.offset[1]}px)`;
}

export class Lab {
  readonly el: HTMLElement;
  private readonly scroller: HTMLElement;
  private readonly page: HTMLElement;
  private readonly foot: HTMLElement;
  private readonly sheet: HTMLElement;
  private readonly cele: HTMLElement;
  private timer = 0;
  private pageKey = '';
  private sheetKey = '';
  private footKey = '';
  /** The node whose details are open. */
  private openId: string | null = null;
  private note = '';
  /** Finished items the player has seen on this screen; the rest show as new. */
  private seen = new Set<string>();
  /** Sets whose medal was already handed out. */
  private medals = new Set<string>();
  /** New items whose arrival animation has played on this visit. */
  private readonly stamped = new Set<string>();
  private celebrating: SetId | null = null;
  private readonly reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  private offArt: (() => void) | null = null;
  /** One finger moves the tree, two zoom it (the tree grows past one screen). */
  private readonly pz: PanZoom;
  private readonly resize =
    typeof ResizeObserver === 'function'
      ? new ResizeObserver(() => {
          this.pz.refit();
          this.drawWires();
        })
      : null;

  constructor(private readonly cb: LabCallbacks) {
    this.el = document.createElement('div');
    this.el.className = 'lab lt';
    this.el.hidden = true;
    this.el.setAttribute('role', 'dialog');
    this.el.setAttribute('aria-modal', 'true');
    this.el.innerHTML = `
      <svg class="lt-defs" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id="lt-brass" x1="0" y1="0" x2="0.4" y2="1">
            <stop offset="0" stop-color="#fbe3a3"/><stop offset="0.45" stop-color="#d9a24a"/><stop offset="1" stop-color="#8a5a1c"/>
          </linearGradient>
        </defs>
      </svg>
      <div class="lt-scroll"><div class="lt-page"></div></div>
      <footer class="lab-foot lt-foot"></footer>
      <div class="lt-sheet-wrap"></div>
      <div class="lt-cele-wrap"></div>`;
    this.scroller = this.el.querySelector('.lt-scroll')!;
    this.page = this.el.querySelector('.lt-page')!;
    this.foot = this.el.querySelector('.lt-foot')!;
    this.sheet = this.el.querySelector('.lt-sheet-wrap')!;
    this.cele = this.el.querySelector('.lt-cele-wrap')!;
    this.pz = new PanZoom(this.scroller, this.page);
    this.resize?.observe(this.page);
    this.resize?.observe(this.scroller);
    this.el.addEventListener('click', (ev) => this.onClick(ev));
    this.el.addEventListener('keydown', (ev) => {
      const pan = { ArrowUp: 60, ArrowDown: -60, PageUp: 400, PageDown: -400 }[ev.key];
      if (pan && !this.openId && !this.celebrating) {
        this.pz.panBy(0, pan);
        ev.preventDefault();
        return;
      }
      if (ev.key === '+' || ev.key === '-') {
        this.pz.zoomAt(this.scroller.clientWidth / 2, this.scroller.clientHeight / 2, ev.key === '+' ? 1.2 : 1 / 1.2);
        return;
      }
      if (ev.key !== 'Escape') return;
      if (this.celebrating) this.dismissCelebration();
      else if (this.openId) this.closeSheet();
      else this.close();
    });
  }

  get isOpen(): boolean {
    return !this.el.hidden;
  }

  open(): void {
    this.note = '';
    this.openId = null;
    const done = this.cb.state().done;
    // The first visit since this screen existed: nothing is new, no medal is owed.
    const seen = readList(SEEN_KEY);
    const medals = readList(MEDALS_KEY);
    this.seen = new Set(seen ?? done);
    this.medals = new Set(medals ?? this.medalKeys(done));
    if (!seen) writeList(SEEN_KEY, this.seen);
    if (!medals) writeList(MEDALS_KEY, this.medals);
    this.stamped.clear();
    this.el.hidden = false;
    this.pageKey = '';
    this.render();
    this.pz.reset();
    window.clearInterval(this.timer);
    this.timer = window.setInterval(() => this.render(), 1000);
    this.offArt?.();
    this.offArt = this.cb.onArt?.(() => [this.page, this.sheet, this.cele].forEach((root) => this.paintPictures(root))) ?? null;
  }

  close(): void {
    if (!this.isOpen) return;
    window.clearInterval(this.timer);
    this.offArt?.();
    this.offArt = null;
    // What was on screen is no longer new.
    this.seen = new Set(this.cb.state().done);
    writeList(SEEN_KEY, this.seen);
    this.openId = null;
    this.celebrating = null;
    this.sheet.innerHTML = '';
    this.cele.innerHTML = '';
    this.sheetKey = '';
    this.el.hidden = true;
    this.cb.close();
  }

  invalidate(): void {
    this.pageKey = '';
    this.sheetKey = '';
    this.footKey = '';
    if (this.isOpen) this.render();
  }

  // ------------------------------------------------------------- events

  private onClick(ev: MouseEvent): void {
    const target = ev.target as HTMLElement;
    const btn = target.closest<HTMLElement>('[data-lt]');
    if (!btn) return;
    const id = btn.dataset.id;
    switch (btn.dataset.lt) {
      case 'close':
        this.close();
        return;
      case 'node':
        if (id) this.openSheet(id);
        return;
      case 'scrim':
        this.closeSheet();
        return;
      case 'start': {
        if (!id || btn.getAttribute('aria-disabled') === 'true') return;
        const err = this.cb.start(id);
        this.note = err ? t(ERR[err]) : '';
        if (!err) this.openId = null;
        this.render();
        return;
      }
      case 'goto': {
        const set = btn.dataset.set;
        if (set) this.scrollToSet(set);
        return;
      }
      case 'cele':
        this.dismissCelebration();
        return;
    }
  }

  private openSheet(id: string): void {
    this.openId = id;
    this.note = '';
    this.render();
    this.sheet.querySelector<HTMLElement>('.lt-sheet')?.focus({ preventScroll: true });
  }

  private closeSheet(): void {
    this.openId = null;
    this.note = '';
    this.render();
  }

  private scrollToSet(id: string): void {
    const lane = this.page.querySelector<HTMLElement>(`.lt-set[data-set="${id}"]`);
    if (!lane) return;
    const y = (lane.getBoundingClientRect().top - this.page.getBoundingClientRect().top) / this.pz.scale;
    this.pz.showY(y, 12, !this.reduceMotion);
    lane.classList.remove('flash');
    void lane.offsetWidth;
    lane.classList.add('flash');
  }

  private dismissCelebration(): void {
    if (this.celebrating) this.medals.add(this.medalKey(this.celebrating));
    writeList(MEDALS_KEY, this.medals);
    this.celebrating = null;
    this.cele.innerHTML = '';
    this.render();
  }

  // ------------------------------------------------------------- state

  /**
   * A medal's ceremony is once per set and headquarters level: when a higher
   * headquarters widens the tree, finishing the set again earns it again.
   */
  private medalKey(id: SetId): string {
    const hq = this.cb.lab().hq;
    return hq === undefined ? id : `${id}@${hq}`;
  }

  private medalKeys(done: readonly string[]): string[] {
    return completeSets(done, this.cb.lab()).map((id) => this.medalKey(id));
  }

  private nodeState(s: ResearchState, lab: LabInfo, id: string): NodeState {
    const st = status(s, id);
    if (st !== 'ready') return st;
    const err = startError(s, id, lab);
    return err === null ? 'go' : err === 'labLevel' ? 'lab' : 'ready';
  }

  /** The gun shown on a set's card: the highest level researched, or level 1 while locked. */
  private gunLevel(gun: TowerId, s: ResearchState): number {
    for (let n = TOWERS[gun].levels.length; n > 3; n--) if (s.done.includes(`lvl${n}.${gun}`)) return n;
    return 3;
  }

  private now(s: ResearchState): number {
    return s.pausedAt ?? Date.now();
  }

  // ------------------------------------------------------------- render

  render(): void {
    const s = this.cb.state();
    const lab = this.cb.lab();
    // A set just completed: its medal ceremony, once.
    if (!this.celebrating) {
      const owed = completeSets(s.done, lab).find((id) => !this.medals.has(this.medalKey(id)));
      if (owed) {
        this.celebrating = owed;
        this.cele.innerHTML = this.celebrationHtml(owed);
        this.paintPictures(this.cele);
        this.cb.celebrate?.();
        this.cele.querySelector<HTMLElement>('[data-lt="cele"]')?.focus({ preventScroll: true });
      }
    }
    const next = suggestNext(s, lab);
    const key = JSON.stringify([s.done, s.active.map((a) => a.id), s.gold, lab, s.pausedAt !== null, next, [...this.seen].length, this.medals.size, document.documentElement.lang]);
    if (key !== this.pageKey) {
      this.pageKey = key;
      this.page.innerHTML = this.pageHtml(s, lab, next);
      this.paintPictures(this.page);
      this.pz.refit();
      requestAnimationFrame(() => this.drawWires());
    }
    const sheetKey = this.openId ? JSON.stringify([key, this.openId, this.note]) : '';
    if (sheetKey !== this.sheetKey) {
      this.sheetKey = sheetKey;
      this.sheet.innerHTML = this.openId ? this.sheetHtml(s, lab, this.openId) : '';
      this.paintPictures(this.sheet);
    }
    const footKey = `${s.gold}|${document.documentElement.lang}`;
    if (footKey !== this.footKey) {
      this.footKey = footKey;
      this.foot.innerHTML = `
        <div class="lab-treasury" title="${t('lab.treasury')}"><span class="ico ico-gold" aria-hidden="true"></span><b>${s.gold}</b></div>
        <button class="btn primary" data-lt="close"><span class="not-base">${t('lab.close')}</span><span class="base-only">${t('action.close')}</span></button>`;
    }
    this.tick(s);
    // Fonts and pictures can shift the layout after it was drawn.
    this.drawWires();
  }

  /** Move the clocks and progress strokes without rebuilding anything. */
  private tick(s: ResearchState): void {
    const now = this.now(s);
    this.el.querySelectorAll<HTMLElement | SVGElement>('[data-ends]').forEach((el) => {
      const left = (Number(el.dataset.ends) - now) / 1000;
      const total = Number(el.dataset.total) || 1;
      const done = Math.min(1, Math.max(0, 1 - left / total));
      if (el instanceof SVGElement) el.setAttribute('stroke-dasharray', `${(done * 100).toFixed(2)} 100`);
      else if (el.classList.contains('lt-bar')) (el.firstElementChild as HTMLElement).style.width = `${(done * 100).toFixed(1)}%`;
      else el.textContent = formatDuration(left);
    });
  }

  private paintPictures(root: HTMLElement): void {
    root.querySelectorAll<HTMLElement>('[data-pic]').forEach((el) => {
      paintGun(el, this.cb.portrait(el.dataset.pic as TowerId, Number(el.dataset.lv) || 1), Number(el.dataset.w) || 60, Number(el.dataset.h) || 60, Number(el.dataset.z) || 1.4);
    });
  }

  private pageHtml(s: ResearchState, lab: LabInfo, next: string | null): string {
    const tree = treeProgress(s.done, lab);
    const won = new Set(completeSets(s.done, lab));
    const shown = RESEARCH_SETS.filter((set) => setItems(set, lab, s.done).length > 0);
    const ratio = tree.done / tree.total;
    const C = 2 * Math.PI * 22;
    const medals = shown.map((set) => {
      const ok = won.has(set.id);
      const name = setName(set.id);
      const pic =
        set.id === 'fortress' || set.id === 'traps'
          ? `<span class="lt-medal-ico">${set.id === 'traps' ? ICON.trap : ICON.castle}</span>`
          : `<span class="lt-pic" data-pic="${set.id}" data-lv="${ok ? 5 : 3}" data-w="34" data-h="34" data-z="1.7"></span>`;
      return `<li><button class="lt-medal${ok ? ' won' : ''}" data-lt="goto" data-set="${set.id}" aria-label="${esc(name)}${ok ? `: ${t('lab.medal')}` : ''}" title="${esc(name)}">${pic}</button></li>`;
    }).join('');
    return `
      <header class="lab-head">
        <div>
          <p class="lab-kicker">${t('lab.kicker')}</p>
          <h1 class="lab-title">${t('lab.title')}</h1>
        </div>
        <button class="win-x" data-lt="close" aria-label="${t('action.close')}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
      </header>
      <section class="lt-summary${tree.done === tree.total ? ' all' : ''}">
        <div class="lt-sum-top">
          <div class="lt-ring" aria-hidden="true">
            <svg viewBox="0 0 52 52"><circle class="track" cx="26" cy="26" r="22"/><circle class="val" cx="26" cy="26" r="22" stroke-dasharray="${(ratio * C).toFixed(1)} ${C.toFixed(1)}"/></svg>
            <b>${pct(ratio)}%</b>
          </div>
          <div class="lt-sum-text">
            <strong>${t('lab.progress', { n: tree.done, total: tree.total })}</strong>
            <span>${tree.done === tree.total ? t('lab.allDone') : t('lab.medals', { n: won.size, total: shown.length })}</span>
          </div>
        </div>
        <ol class="lt-medals">${medals}</ol>
      </section>
      <div class="lt-status">${this.statusHtml(s, lab, next)}</div>
      <div class="lt-tree">
        <svg class="lt-wires" aria-hidden="true"></svg>
        ${shown.map((set) => this.setHtml(set, s, lab, won.has(set.id))).join('')}
      </div>
      ${this.growHtml(s, lab)}`;
  }

  /** What the next headquarters level adds to the tree. */
  private growHtml(s: ResearchState, lab: LabInfo): string {
    if (lab.hq === undefined) return '';
    const next = lab.hq + 2;
    const more = RESEARCH.filter((r) => !inTree(r.id, lab, s.done) && (r.hq ?? 1) === next).length;
    if (!more) return '';
    return `<p class="lt-grow">${ICON.castle}<span>${t('lab.grow', { n: next, k: more })}</span></p>`;
  }

  /** What runs now, and what to do next. */
  private statusHtml(s: ResearchState, lab: LabInfo, next: string | null): string {
    if (!lab.standing) return `<p class="lt-banner down">${t('lab.destroyed')}</p>`;
    const now = this.now(s);
    const runs = s.active.map((a) => {
      const item = researchItem(a.id)!;
      const total = itemSeconds(item, this.cb.speed, this.cb.state());
      return `
        <button class="lt-run" data-lt="node" data-id="${item.id}">
          ${this.miniHtml(item, 'active')}
          <span class="lt-run-body">
            <span class="lt-run-kicker">${t('lab.inProgress')}</span>
            <span class="lt-run-name">${esc(itemName(item))}</span>
            <span class="lt-bar" data-ends="${a.endsAt}" data-total="${total}"><i></i></span>
          </span>
          <span class="lt-run-time" data-ends="${a.endsAt}" data-total="${total}">${formatDuration((a.endsAt - now) / 1000)}</span>
        </button>`;
    });
    const free = s.active.length < labSlots(lab);
    let nextHtml = '';
    if (next && free) {
      const item = researchItem(next)!;
      const err = startError(s, next, lab);
      const set = setOf(next);
      const p = set ? setProgress(set, s.done, lab) : null;
      const toMedal = p ? p.total - p.done : 0;
      const why = err === 'noGold' ? `<span class="lt-run-sub poor">${t('lab.needGold', { n: itemCost(item, this.cb.state()) - s.gold })}</span>` : p ? `<span class="lt-run-sub">${esc(setName(set!.id))} ${p.done}/${p.total} · ${t('lab.toMedal', { n: toMedal })}</span>` : '';
      nextHtml = `
        <div class="lt-next">
          <button class="lt-next-main" data-lt="node" data-id="${item.id}">
            ${this.miniHtml(item, err ? 'ready' : 'go')}
            <span class="lt-run-body">
              <span class="lt-run-kicker">${t('lab.next')}</span>
              <span class="lt-run-name">${esc(itemName(item))}</span>
              ${why}
            </span>
          </button>
          <button class="btn primary lt-go" data-lt="start" data-id="${item.id}" ${err ? 'aria-disabled="true"' : ''}>
            <span>${t('lab.start')}</span>
            <span class="lt-go-meta"><span class="cost${err === 'noGold' ? ' poor' : ''}"><span class="ico ico-gold"></span>${itemCost(item, this.cb.state())}</span> · ${formatDuration(itemSeconds(item, this.cb.speed, this.cb.state()))}</span>
          </button>
        </div>`;
    }
    const slots = `<p class="lt-slots">${t('lab.building', { n: lab.level + 1, slots: labSlots(lab) })}</p>`;
    return runs.join('') + nextHtml + slots;
  }

  private setHtml(set: ResearchSet, s: ResearchState, lab: LabInfo, complete: boolean): string {
    const p = setProgress(set, s.done, lab);
    const name = setName(set.id);
    const left = p.total - p.done;
    const pips = Array.from({ length: p.total }, (_, i) => `<i${i < p.done ? ' class="on"' : ''}></i>`).join('');
    const tail = complete ? `<span class="lt-won"><i></i>${t('lab.medal')}</span>` : '';
    // One piece short: name the reward, the strongest pull to finish.
    const foot = complete
      ? `<p class="lt-bonus">${esc(setBonus(set.id))}</p>`
      : left === 1
        ? `<p class="lt-bonus near"><b>${t('lab.toMedal', { n: 1 })}</b> · ${esc(setBonus(set.id))}</p>`
        : '';
    const head = `
      <header class="lt-set-head">
        <h2>${esc(name)}</h2>
        <span class="lt-count" aria-label="${esc(t('lab.setOf', { name, n: p.done, total: p.total }))}">${p.done}/${p.total}</span>
        <span class="lt-pips" aria-hidden="true">${pips}</span>
        ${tail}
      </header>`;
    if (set.id === 'fortress' || set.id === 'traps') {
      // The boosts (and the traps) snake: four across, then back, and so on.
      const at = (i: number) => {
        const row = Math.floor(i / 4) + 1;
        return { col: row % 2 ? (i % 4) + 1 : 4 - (i % 4), row };
      };
      const nodes = set.items.map((id, i) => this.slotHtml(researchItem(id)!, s, lab, `grid-column:${at(i).col};grid-row:${at(i).row}`)).join('');
      const ico = set.id === 'traps' ? ICON.trap : ICON.castle;
      return `
        <section class="lt-set fortress${complete ? ' complete' : ''}" data-set="${set.id}" style="--tint:${SET_TINT[set.id]}">
          <span class="lt-set-bg" aria-hidden="true"><span class="lt-ghost">${ico}</span></span>
          <div class="lt-card lt-emblem${complete ? ' st-done' : ''}" aria-hidden="true">${shapeSvg(CARD, false, 0, 1, '0 0 74 84')}<span class="lt-emblem-ico">${ico}</span></div>
          ${head}
          <div class="lt-nodes snake">${nodes}</div>
          ${foot}
        </section>`;
    }
    const gun = set.id as TowerId;
    const unlock = set.starter ? null : researchItem(`gun.${gun}`)!;
    const lv4 = researchItem(`lvl4.${gun}`)!;
    const lv5 = researchItem(`lvl5.${gun}`)!;
    // Levels past V (few guns): on the row below, back from under V.
    const more = set.items.map((id) => researchItem(id)!).filter((it) => it.effect.kind === 'maxLevel' && it.effect.level > 5);
    // Effects: the first beside the levels, any more on the row below, back from the right.
    const effects = set.items.filter((id) => researchItem(id)?.effect.kind === 'gunMod');
    // Aiming modes: a second row, under the level each grows from.
    const aims = set.items
      .filter((id) => researchItem(id)?.effect.kind === 'aim')
      .map((id, i) => this.slotHtml(researchItem(id)!, s, lab, `grid-column:${1 + i};grid-row:2`))
      .join('');
    return `
      <section class="lt-set${complete ? ' complete' : ''}" data-set="${gun}" style="--tint:${SET_TINT[gun]}">
        <span class="lt-set-bg" aria-hidden="true"><span class="lt-pic" data-pic="${gun}" data-lv="${this.gunLevel(gun, s)}" data-w="190" data-h="150" data-z="1.3"></span></span>
        ${this.cardHtml(gun, unlock, s, lab)}
        ${head}
        <div class="lt-nodes">
          ${this.slotHtml(lv4, s, lab, 'grid-column:1')}
          ${this.slotHtml(lv5, s, lab, 'grid-column:2')}
          ${more.map((it, i) => this.slotHtml(it, s, lab, `grid-column:${2 - i};grid-row:2`)).join('')}
          <span class="lt-split" aria-hidden="true"></span>
          ${effects.map((id, i) => this.slotHtml(researchItem(id)!, s, lab, i === 0 ? 'grid-column:4' : `grid-column:${5 - i};grid-row:2`)).join('')}
          ${aims}
        </div>
        ${foot}
      </section>`;
  }

  /** The gun's own card: its picture, and the node that unlocks it. */
  private cardHtml(gun: TowerId, unlock: ResearchItem | null, s: ResearchState, lab: LabInfo): string {
    const st: NodeState = unlock ? this.nodeState(s, lab, unlock.id) : 'done';
    const known = st === 'done';
    const name = t(`tower.${gun}` as MessageKey);
    const active = unlock ? s.active.find((a) => a.id === unlock.id) : undefined;
    const total = unlock ? itemSeconds(unlock, this.cb.speed, this.cb.state()) : 1;
    const fresh = unlock ? this.freshClass(unlock.id, st) : '';
    let strip = '';
    if (!unlock) strip = `<span class="lt-strip starter">${t('lab.starter')}</span>`;
    else if (st === 'active' && active) strip = `<span class="lt-strip time" data-ends="${active.endsAt}" data-total="${total}">${formatDuration((active.endsAt - this.now(s)) / 1000)}</span>`;
    else if (st === 'lab') strip = `<span class="lt-strip gate">${t('lab.labShort', { n: ROMAN[unlock.hq ?? 1]! })}</span>`;
    else if (!known) strip = `<span class="lt-strip${st === 'go' ? ' go' : ''}${st === 'ready' && s.gold < itemCost(unlock, this.cb.state()) ? ' poor' : ''}"><span class="ico ico-gold"></span>${itemCost(unlock, this.cb.state())}</span>`;
    const label = `${name}. ${t(`lab.state.${st}` as MessageKey)}`;
    const attrs = unlock ? `data-lt="node" data-id="${unlock.id}"` : 'disabled';
    return `
      <button class="lt-card st-${st}${known ? '' : ' veiled'}${fresh}" ${attrs} aria-label="${esc(label)}">
        ${shapeSvg(CARD, st === 'active', active?.endsAt, total, '0 0 74 84')}
        <span class="lt-pic" data-pic="${gun}" data-lv="${known ? this.gunLevel(gun, s) : 1}" data-w="66" data-h="54" data-z="1.45"></span>
        ${known ? '' : `<span class="lt-lock">${ICON.lock}</span>`}
        ${known && unlock ? `<span class="lt-check">${ICON.check}</span>` : ''}
        ${fresh ? `<span class="lt-new">${t('lab.new')}</span>` : ''}
        ${strip}
      </button>`;
  }

  /** One research node and the line under it (time, price or what it waits for). */
  private slotHtml(item: ResearchItem, s: ResearchState, lab: LabInfo, place: string): string {
    // Not in the tree yet: the headquarters will add it.
    if (!inTree(item.id, lab, s.done)) return '';
    const st = this.nodeState(s, lab, item.id);
    const active = s.active.find((a) => a.id === item.id);
    const total = itemSeconds(item, this.cb.speed, this.cb.state());
    const fresh = this.freshClass(item.id, st);
    let cap: string;
    if (st === 'active' && active) cap = `<span class="lt-cap time" data-ends="${active.endsAt}" data-total="${total}">${formatDuration((active.endsAt - this.now(s)) / 1000)}</span>`;
    else if (st === 'lab') cap = `<span class="lt-cap gate">${t('lab.labShort', { n: ROMAN[item.hq ?? 1]! })}</span>`;
    else if (st !== 'done') cap = `<span class="lt-cap${st === 'go' ? ' go' : ''}${st === 'ready' && s.gold < itemCost(item, this.cb.state()) ? ' poor' : ''}"><span class="ico ico-gold"></span>${itemCost(item, this.cb.state())}</span>`;
    else cap = '<span class="lt-cap"></span>';
    const label = `${itemName(item)}. ${t(`lab.state.${st}` as MessageKey)}`;
    return `
      <div class="lt-slot" style="${place}">
        <button class="lt-node shape-${shapeOf(item)} st-${st}${fresh}" data-lt="node" data-id="${item.id}" aria-label="${esc(label)}">
          ${shapeSvg(SHAPE[shapeOf(item)], st === 'active', active?.endsAt, total)}
          <span class="lt-glyph">${st === 'locked' && shapeOf(item) !== 'oct' ? ICON.lock : glyphOf(item)}</span>
          ${st === 'done' ? `<span class="lt-check">${ICON.check}</span>` : ''}
          ${fresh ? `<span class="lt-new">${t('lab.new')}</span>` : ''}
        </button>
        ${cap}
      </div>`;
  }

  /** A small copy of a node, for the status cards and the sheet. */
  private miniHtml(item: ResearchItem, st: NodeState): string {
    if (item.effect.kind === 'gun') {
      return `<span class="lt-mini lt-mini-gun st-${st}"><span class="lt-pic" data-pic="${item.effect.gun}" data-lv="1" data-w="40" data-h="36"></span></span>`;
    }
    const shape = shapeOf(item);
    return `<span class="lt-mini lt-node shape-${shape} st-${st}">${shapeSvg(SHAPE[shape], false)}<span class="lt-glyph">${glyphOf(item)}</span></span>`;
  }

  /** "fresh" for an item finished since the player last looked; "stamp" the first time it is drawn. */
  private freshClass(id: string, st: NodeState): string {
    if (st !== 'done' || this.seen.has(id)) return '';
    if (this.stamped.has(id)) return ' fresh';
    this.stamped.add(id);
    return ' fresh stamp';
  }

  private sheetHtml(s: ResearchState, lab: LabInfo, id: string): string {
    const item = researchItem(id);
    if (!item) return '';
    const st = this.nodeState(s, lab, id);
    const err = startError(s, id, lab);
    const set = setOf(id);
    const p = set ? setProgress(set, s.done, lab) : null;
    const reqs = item.requires.map((r) => {
      const ok = s.done.includes(r);
      return `<li class="${ok ? 'ok' : 'no'}">${ok ? ICON.check : ICON.lock}${esc(itemName(researchItem(r)!))}</li>`;
    });
    if ((item.hq ?? 1) > 1) {
      const ok = inTree(id, lab, s.done);
      reqs.push(`<li class="${ok ? 'ok' : 'no'}">${ok ? ICON.check : ICON.lock}${esc(t('lab.hqLevelReq', { n: item.hq! }))}</li>`);
      const labOk = item.hq! <= lab.level + 1;
      reqs.push(`<li class="${labOk ? 'ok' : 'no'}">${labOk ? ICON.check : ICON.lock}${esc(t('lab.labLevelReq', { n: item.hq! }))}</li>`);
    }
    const active = s.active.find((a) => a.id === id);
    const total = itemSeconds(item, this.cb.speed, this.cb.state());
    let action: string;
    if (st === 'done') action = `<p class="lt-sheet-state done">${ICON.check}${t('lab.done')}</p>`;
    else if (st === 'active' && active)
      action = `<p class="lt-sheet-state active">${ICON.clock}${t('lab.inProgress')} · <span data-ends="${active.endsAt}" data-total="${total}">${formatDuration((active.endsAt - this.now(s)) / 1000)}</span></p>`;
    else {
      const reason = err && err !== 'noGold' ? `<p class="lt-sheet-why">${esc(t(ERR[err]))}</p>` : err === 'noGold' ? `<p class="lt-sheet-why">${t('lab.needGold', { n: itemCost(item, this.cb.state()) - s.gold })}</p>` : '';
      action = `${reason}
        <button class="btn primary lt-go wide" data-lt="start" data-id="${id}" ${err ? 'aria-disabled="true"' : ''}>
          <span>${t('lab.start')}</span>
          <span class="lt-go-meta"><span class="cost${err === 'noGold' ? ' poor' : ''}"><span class="ico ico-gold"></span>${itemCost(item, this.cb.state())}</span> · ${formatDuration(total)}</span>
        </button>`;
    }
    const setLine = set && p
      ? `<p class="lt-sheet-set">${esc(t('lab.ofSet', { name: setName(set.id), n: p.done, total: p.total }))} · ${esc(t('lab.setBonus', { bonus: setBonus(set.id) }))}</p>`
      : '';
    return `
      <div class="lt-scrim" data-lt="scrim"></div>
      <section class="lt-sheet" role="dialog" aria-modal="true" tabindex="-1" aria-label="${esc(itemName(item))}">
        <div class="lt-sheet-top">
          ${this.miniHtml(item, st)}
          <div>
            <p class="lab-kicker">${t(`lab.branch.${item.branch}` as MessageKey)}</p>
            <h2 class="lt-sheet-title">${esc(itemName(item))}</h2>
          </div>
        </div>
        <p class="lt-sheet-fx">${esc(itemEffect(item))}</p>
        ${reqs.length ? `<p class="lt-sheet-h">${t('lab.needs')}</p><ul class="lt-reqs">${reqs.join('')}</ul>` : ''}
        ${setLine}
        ${this.note ? `<p class="lt-sheet-why" role="status">${esc(this.note)}</p>` : ''}
        ${action}
      </section>`;
  }

  private celebrationHtml(id: SetId): string {
    const pic = id === 'fortress' || id === 'traps' ? `<span class="lt-medal-ico big">${id === 'traps' ? ICON.trap : ICON.castle}</span>` : `<span class="lt-pic" data-pic="${id}" data-lv="5" data-w="104" data-h="96" data-z="1.35"></span>`;
    return `
      <div class="lt-cele" role="dialog" aria-modal="true" aria-label="${esc(t('lab.cele.kicker'))}">
        <div class="lt-cele-card">
          <div class="lt-cele-medal"><span class="lt-cele-rays" aria-hidden="true"></span><span class="lt-cele-disc">${pic}</span></div>
          <p class="lab-kicker">${t('lab.cele.kicker')}</p>
          <h2 class="lt-cele-title">${esc(setName(id))}</h2>
          <p class="lt-cele-bonus">${esc(setBonus(id))}</p>
          <button class="btn primary" data-lt="cele">${t('lab.cele.ok')}</button>
        </div>
      </div>`;
  }

  // ------------------------------------------------------------- wires

  /**
   * The lines between nodes, measured from where the nodes landed: each row
   * left to right, the guns down the left, the effects down the right, and the
   * Fortress snake. Lit brass where done, moving where it leads to the next step.
   */
  private drawWires(): void {
    const svg = this.page.querySelector<SVGSVGElement>('.lt-wires');
    if (!svg || this.el.hidden) return;
    const tree = svg.parentElement!;
    const base = tree.getBoundingClientRect();
    // Measured on screen, drawn in the tree's own (unzoomed) pixels.
    const k = tree.offsetWidth ? base.width / tree.offsetWidth : 1;
    const box = (id: string) => {
      const el = tree.querySelector<HTMLElement>(`[data-id="${id}"], [data-set="${id}"] .lt-card`);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      const l = (r.left - base.left) / k;
      const t = (r.top - base.top) / k;
      const w = r.width / k;
      const h = r.height / k;
      return { l, r: l + w, t, b: t + h, cx: l + w / 2, cy: t + h / 2 };
    };
    const s = this.cb.state();
    const lab = this.cb.lab();
    const stateOf = (id: string): NodeState => (researchItem(id) ? this.nodeState(s, lab, id) : 'done');
    const cls = (from: string, to: string) => {
      const a = stateOf(from);
      const b = stateOf(to);
      if (a === 'done' && b === 'done') return 'lit';
      if (a === 'done' && (b === 'active' || b === 'go')) return 'flow';
      if (a === 'done') return 'dim';
      return 'dash';
    };
    const paths: string[] = [];
    const line = (from: string, to: string, kind: string) => {
      const a = box(from);
      const b = box(to);
      if (!a || !b) return;
      let d: string;
      if (Math.abs(a.cx - b.cx) < 3) d = `M${a.cx} ${a.cy}V${b.cy}`;
      else if (b.cy >= a.t && b.cy <= a.b) d = `M${a.cx} ${b.cy}H${b.cx}`;
      else d = `M${a.cx} ${a.cy}V${(a.cy + b.cy) / 2}H${b.cx}V${b.cy}`;
      if (kind === 'lit') paths.push(`<path class="w-glow" d="${d}"/>`);
      paths.push(`<path class="w-${kind}" d="${d}"/>`);
    };
    const gunKey = (set: ResearchSet) => (set.starter ? set.id : `gun.${set.id}`);
    const guns = RESEARCH_SETS.filter((set) => set.id !== 'fortress' && set.id !== 'traps');
    guns.forEach((set, i) => {
      const g = gunKey(set);
      line(g, `lvl4.${set.id}`, cls(g, `lvl4.${set.id}`));
      line(`lvl4.${set.id}`, `lvl5.${set.id}`, cls(`lvl4.${set.id}`, `lvl5.${set.id}`));
      for (let n = 6; researchItem(`lvl${n}.${set.id}`); n++) line(`lvl${n - 1}.${set.id}`, `lvl${n}.${set.id}`, cls(`lvl${n - 1}.${set.id}`, `lvl${n}.${set.id}`));
      for (const id of set.items) {
        const it = researchItem(id);
        const from = it?.effect.kind === 'aim' ? it.requires[0] : undefined;
        if (from) line(from, id, cls(from, id));
        // An effect leans on the effect before it (its own gun's, or the previous gun's).
        if (it?.effect.kind === 'gunMod') for (const r of it.requires) if (r.startsWith('fx.')) line(r, id, cls(r, id));
      }
      const after = guns[i + 1];
      if (after) line(g, gunKey(after), cls(g, gunKey(after)));
    });
    for (const sid of ['fortress', 'traps'] as const) {
      const items = RESEARCH_SETS.find((set) => set.id === sid)!.items;
      for (let i = 1; i < items.length; i++) line(items[i - 1]!, items[i]!, cls(items[i - 1]!, items[i]!));
    }
    // Only when something moved, so the moving dashes do not restart.
    const html = paths.join('');
    const view = `0 0 ${tree.offsetWidth} ${tree.offsetHeight}`;
    if (svg.getAttribute('viewBox') !== view) svg.setAttribute('viewBox', view);
    if (svg.dataset.d !== html) {
      svg.dataset.d = html;
      svg.innerHTML = html;
    }
  }
}
