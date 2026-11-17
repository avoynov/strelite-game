import { t, tMaybe } from '../i18n';
import { TOWER_IDS, TOWERS, type TowerDef, type TowerId, type TowerLevel } from '../sim/content';
import type { GunPortrait } from '../render/towers/spriteTowerView';

/**
 * "Arsenal": the screen before a level starts. One slide per gun in TOWERS,
 * swiped sideways (touch or mouse drag, arrow buttons, keyboard arrows). Every
 * number, bar and tag is derived from the tower definitions, so a gun added to
 * content.ts shows up here with no extra work; a `tower.<id>.role` text is the
 * only optional extra.
 */

export interface ArsenalCallbacks {
  /** One gun frame for a level, or undefined while its art is not loaded (or there is none). */
  portrait(def: TowerId, level: number, frame: number): GunPortrait | undefined;
  /** Subscribe to "more art has loaded"; returns an unsubscribe. */
  onArt(fn: () => void): () => void;
  /** Aim frames per gun (32). */
  directions: number;
  /** Player closed the screen with this gun selected. */
  close(def: TowerId): void;
}

/**
 * Fields the new roster adds to TowerDef (gameplay thread). Read optionally so the
 * screen works with both the old and the new content.ts.
 */
interface RosterFields {
  targeting?: string;
  /** 'armored' ignores enemies above this armor. */
  maxArmor?: number;
  /** Share of armor ignored, 0..1, per gun. */
  pierce?: number;
  hitsAir?: boolean;
  /** Enemies a bolt passes through after the first. */
  passThrough?: number;
  projectile: string;
}
type ArsenalDef = TowerDef & RosterFields;

interface StatSpec {
  key: string;
  label: () => string;
  unit?: () => string;
  value: (lvl: TowerLevel, def: ArsenalDef) => number | undefined;
  format: (v: number) => string;
  /** sqrt keeps a 12-damage gun visible next to a 400-damage one. */
  curve: 'linear' | 'sqrt';
}

const fmt = (v: number) => (Math.abs(v - Math.round(v)) < 1e-6 ? String(Math.round(v)) : v < 1 ? v.toFixed(2) : v.toFixed(1));

const STATS: StatSpec[] = [
  { key: 'damage', label: () => t('stat.damage'), value: (l) => l.damage, format: fmt, curve: 'sqrt' },
  { key: 'rate', label: () => t('stat.rateLong'), unit: () => t('unit.shots'), value: (l) => 1 / l.fireInterval, format: fmt, curve: 'linear' },
  { key: 'dps', label: () => t('stat.dpsLong'), value: (l) => l.damage / l.fireInterval, format: (v) => v.toFixed(1), curve: 'sqrt' },
  { key: 'range', label: () => t('stat.rangeLong'), unit: () => t('unit.tiles'), value: (l) => l.range, format: fmt, curve: 'linear' },
  { key: 'splash', label: () => t('stat.splashLong'), unit: () => t('unit.tiles'), value: (l) => l.splash, format: fmt, curve: 'linear' },
  { key: 'pierce', label: () => t('stat.pierce'), value: (_, d) => d.pierce, format: (v) => `${Math.round(v * 100)}%`, curve: 'linear' },
];

const SEGMENTS = 12;
/** Idle turntable speed, aim frames per second. */
const SPIN_FPS = 7;
/** Frame shown when not spinning: barrel to the right, side profile. */
const REST_FRAME = 28;

const pad2 = (n: number) => String(n).padStart(2, '0');

export class Arsenal {
  readonly el: HTMLElement;
  private track: HTMLElement;
  private index = 0;
  /** Level previewed per gun, 1-based. */
  private readonly levels = new Map<TowerId, number>();
  private readonly max = new Map<string, number>();
  private spinFrame = REST_FRAME;
  private spinAcc = 0;
  private raf = 0;
  private lastT = 0;
  private offArt: (() => void) | null = null;
  private drag: { id: number; x0: number; y0: number; dx: number; t0: number; active: boolean } | null = null;
  private suppressClick = false;
  private readonly reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

  constructor(private readonly cb: ArsenalCallbacks) {
    for (const s of STATS) {
      let m = 0;
      for (const id of TOWER_IDS) for (const l of (TOWERS[id] as TowerDef).levels) m = Math.max(m, s.value(l, TOWERS[id] as ArsenalDef) ?? 0);
      this.max.set(s.key, m);
    }
    this.el = document.createElement('div');
    this.el.className = 'arsenal';
    this.el.hidden = true;
    this.el.setAttribute('role', 'dialog');
    this.el.setAttribute('aria-modal', 'true');
    this.el.innerHTML = this.shellHtml();
    this.track = this.el.querySelector('.ars-track')!;
    this.bind();
  }

  get isOpen(): boolean {
    return !this.el.hidden;
  }

  open(def?: TowerId): void {
    if (def) this.index = Math.max(0, TOWER_IDS.indexOf(def));
    this.render();
    this.el.hidden = false;
    this.el.classList.remove('leaving');
    requestAnimationFrame(() => this.el.classList.add('shown'));
    this.offArt ??= this.cb.onArt(() => this.refreshGuns());
    this.lastT = performance.now();
    cancelAnimationFrame(this.raf);
    this.raf = requestAnimationFrame((now) => this.tick(now));
  }

  close(): void {
    if (!this.isOpen) return;
    cancelAnimationFrame(this.raf);
    this.offArt?.();
    this.offArt = null;
    this.el.classList.remove('shown');
    this.el.classList.add('leaving');
    const done = () => {
      this.el.hidden = true;
      this.el.classList.remove('leaving');
    };
    if (this.reduceMotion) done();
    else window.setTimeout(done, 320);
    this.cb.close(TOWER_IDS[this.index]!);
  }

  /** Re-render text (language switch). */
  invalidate(): void {
    this.el.innerHTML = this.shellHtml();
    this.track = this.el.querySelector('.ars-track')!;
    if (this.isOpen) this.render();
  }

  // ---------------------------------------------------------------- markup

  private shellHtml(): string {
    const many = TOWER_IDS.length > 1;
    return `
      <div class="ars-bg" aria-hidden="true"></div>
      <header class="ars-head">
        <div>
          <p class="ars-kicker">${t('arsenal.kicker')}</p>
          <h1 class="ars-title">${t('arsenal.title')}</h1>
        </div>
        <p class="ars-count" aria-live="polite"><b class="ars-count-now">01</b><span>/ ${pad2(TOWER_IDS.length)}</span></p>
      </header>
      <div class="ars-viewport">
        <div class="ars-track"></div>
        ${many ? `
        <button class="ars-arrow prev" data-ars="prev" aria-label="${t('arsenal.prev')}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg></button>
        <button class="ars-arrow next" data-ars="next" aria-label="${t('arsenal.next')}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg></button>` : ''}
      </div>
      <footer class="ars-foot">
        ${many ? `<div class="ars-dots" role="tablist">${TOWER_IDS.map((id, i) => `<button class="ars-dot" role="tab" data-ars="goto" data-i="${i}" aria-label="${t(`tower.${id}`)}"></button>`).join('')}</div>
        <p class="ars-hint">${t('arsenal.swipe')}</p>` : ''}
        <button class="btn go ars-start" data-ars="start">${t('arsenal.start')}<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg></button>
      </footer>`;
  }

  private render(): void {
    this.track.innerHTML = TOWER_IDS.map((id, i) => this.slideHtml(id, i)).join('');
    this.refreshGuns();
    this.place(0, false);
  }

  private slideHtml(id: TowerId, i: number): string {
    const def = TOWERS[id] as TowerDef;
    const lvN = this.levels.get(id) ?? 1;
    const lvl = def.levels[lvN - 1]!;
    const base = def.levels[0]!;
    const role = tMaybe(`tower.${id}.role`);
    const traits = this.traits(def as ArsenalDef);

    const rows = STATS.filter((s) => TOWER_IDS.some((tid) => (TOWERS[tid] as TowerDef).levels.some((l) => s.value(l, TOWERS[tid] as ArsenalDef) !== undefined))).map((s) => {
      const v = s.value(lvl, def as ArsenalDef);
      const v0 = s.value(base, def as ArsenalDef);
      const max = this.max.get(s.key) || 1;
      const norm = (x: number | undefined) => (x === undefined ? 0 : s.curve === 'sqrt' ? Math.sqrt(x / max) : x / max);
      const on = Math.max(v ? 1 : 0, Math.round(norm(v) * SEGMENTS));
      const was = lvN > 1 ? Math.max(v0 ? 1 : 0, Math.round(norm(v0) * SEGMENTS)) : on;
      const segs = Array.from({ length: SEGMENTS }, (_, k) => `<i class="${k < was ? 'on' : k < on ? 'up' : ''}"></i>`).join('');
      const delta = lvN > 1 && v !== undefined && v0 !== undefined && Math.abs(v - v0) > 1e-6 ? `<span class="ars-delta">+${s.format(v - v0)}</span>` : '';
      return `
        <div class="ars-stat${v === undefined ? ' none' : ''}">
          <dt>${s.label()}</dt>
          <dd class="ars-bar" aria-hidden="true">${segs}</dd>
          <dd class="ars-val">${v === undefined ? '—' : `<b>${s.format(v)}</b>${s.unit ? `<small>${s.unit()}</small>` : ''}`}${delta}</dd>
        </div>`;
    }).join('');

    const lvButtons = def.levels.map((_, k) => `<button class="ars-lv${k + 1 === lvN ? ' sel' : ''}" data-ars="level" data-def="${id}" data-lv="${k + 1}" aria-pressed="${k + 1 === lvN}">${k + 1}</button>`).join('');
    const cost = lvN === 1 ? lvl.cost : def.levels.slice(0, lvN).reduce((a, l) => a + l.cost, 0);

    return `
      <article class="ars-slide" data-i="${i}" aria-roledescription="slide" aria-label="${t(`tower.${id}`)}">
        <div class="ars-stage">
          <span class="ars-num" aria-hidden="true">${pad2(i + 1)}</span>
          <div class="ars-ring" aria-hidden="true"></div>
          <div class="ars-gun" data-def="${id}" data-lv="${lvN}"></div>
        </div>
        <div class="ars-info">
          <ul class="ars-tags">${traits.map((x) => `<li>${x}</li>`).join('')}</ul>
          <h2 class="ars-name">${t(`tower.${id}`)}</h2>
          ${role ? `<p class="ars-role">${role}</p>` : ''}
          ${this.targetHtml(def as ArsenalDef)}
          <div class="ars-levels">
            <span class="ars-lv-label">${t('arsenal.level')}</span>
            <div class="ars-lv-group">${lvButtons}</div>
            <span class="ars-cost"><span class="ico ico-gold" aria-hidden="true"></span><b>${cost}</b></span>
          </div>
          <dl class="ars-stats">${rows}</dl>
        </div>
      </article>`;
  }

  /** Short tags derived from the definition, so a new gun gets them for free. */
  private traits(def: ArsenalDef): string[] {
    const out = [tMaybe(`trait.${def.projectile}`) ?? t('trait.direct')];
    if (def.hitsAir !== undefined) out.push(t(def.hitsAir ? 'trait.air' : 'trait.groundOnly'));
    if (def.passThrough) out.push(t('trait.passThrough', { n: def.passThrough }));
    const l1 = def.levels[0]!;
    if (l1.splash) out.push(t('trait.splash'));
    if (def.minRange) out.push(t('trait.minRange', { n: fmt(def.minRange) }));
    out.push(t('trait.size', { n: def.size }));
    return out;
  }

  /** Which enemy the gun picks; every gun falls back to the first on the path. */
  private targetHtml(def: ArsenalDef): string {
    if (!def.targeting) return '';
    const text = tMaybe(`target.${def.targeting}`, { n: def.maxArmor ?? '' }) ?? def.targeting;
    const fallback = def.targeting === 'first' ? '' : `<small>${t('target.fallback')}</small>`;
    return `<p class="ars-target"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg><span><span class="ars-target-label">${t('target.label')}</span> <b>${text}</b>${fallback}</span></p>`;
  }

  /** Draw (or redraw) every gun picture at the current turntable frame. */
  private refreshGuns(): void {
    this.track.querySelectorAll<HTMLElement>('.ars-gun').forEach((el, i) => {
      const id = el.dataset.def as TowerId;
      const frame = i === this.index ? this.spinFrame : REST_FRAME;
      this.drawGun(el, id, Number(el.dataset.lv), Math.round(frame));
    });
  }

  private drawGun(el: HTMLElement, id: TowerId, level: number, frame: number): void {
    const p = this.cb.portrait(id, level, frame);
    el.classList.toggle('none', !p);
    if (!p) {
      el.innerHTML = '';
      return;
    }
    const [hx, hy] = p.half ?? [p.reach, p.reach];
    const k = Math.min((el.clientWidth || 300) / (2 * hx), (el.clientHeight || 220) / (2 * hy));
    let img = el.firstElementChild as HTMLElement | null;
    if (!img) {
      img = document.createElement('span');
      el.appendChild(img);
    }
    const [fx, fy, fw, fh] = p.frame;
    img.style.cssText =
      `width:${fw}px;height:${fh}px;background-image:url('${p.url}');` +
      `background-position:-${fx}px -${fy}px;background-size:${p.sheetSize[0]}px ${p.sheetSize[1]}px;` +
      `transform:scale(${k.toFixed(4)}) translate(${p.offset[0]}px,${p.offset[1]}px)`;
  }

  // ---------------------------------------------------------------- motion

  /** Move the track to the current slide plus a drag offset in px. */
  private place(dx: number, animate: boolean): void {
    const w = this.track.clientWidth || window.innerWidth;
    this.track.classList.toggle('snapping', animate && !this.reduceMotion);
    this.track.style.transform = `translate3d(${-this.index * w + dx}px,0,0)`;
    // Per-slide distance from centre (-1…1) drives the parallax in CSS.
    this.track.querySelectorAll<HTMLElement>('.ars-slide').forEach((s, i) => {
      const p = Math.max(-1.5, Math.min(1.5, i - this.index + dx / w));
      s.style.setProperty('--p', p.toFixed(3));
      s.classList.toggle('current', i === this.index);
      s.setAttribute('aria-hidden', String(i !== this.index));
    });
    const now = this.el.querySelector('.ars-count-now');
    if (now) now.textContent = pad2(this.index + 1);
    this.el.querySelectorAll<HTMLElement>('.ars-dot').forEach((d, i) => d.setAttribute('aria-selected', String(i === this.index)));
    const prev = this.el.querySelector<HTMLButtonElement>('[data-ars="prev"]');
    const next = this.el.querySelector<HTMLButtonElement>('[data-ars="next"]');
    if (prev) prev.disabled = this.index === 0;
    if (next) next.disabled = this.index === TOWER_IDS.length - 1;
  }

  private go(i: number): void {
    const n = Math.max(0, Math.min(TOWER_IDS.length - 1, i));
    if (n !== this.index) {
      // The gun we leave settles back to its profile; the new one starts turning from there.
      this.spinFrame = REST_FRAME;
      this.index = n;
      this.refreshGuns();
    }
    this.place(0, true);
  }

  private tick(now: number): void {
    const dt = Math.min(0.1, (now - this.lastT) / 1000);
    this.lastT = now;
    if (!this.reduceMotion && !this.drag?.active) {
      this.spinAcc += dt * SPIN_FPS;
      if (this.spinAcc >= 1) {
        const steps = Math.floor(this.spinAcc);
        this.spinAcc -= steps;
        this.spinFrame = (this.spinFrame + steps) % this.cb.directions;
        const el = this.track.querySelectorAll<HTMLElement>('.ars-gun')[this.index];
        if (el) this.drawGun(el, el.dataset.def as TowerId, Number(el.dataset.lv), this.spinFrame);
      }
    }
    this.raf = requestAnimationFrame((t2) => this.tick(t2));
  }

  // ---------------------------------------------------------------- input

  private bind(): void {
    const vp = () => this.el.querySelector<HTMLElement>('.ars-viewport')!;

    this.el.addEventListener('pointerdown', (ev) => {
      if (!(ev.target as HTMLElement).closest('.ars-viewport') || (ev.target as HTMLElement).closest('.ars-arrow')) return;
      if (ev.button !== 0) return;
      this.drag = { id: ev.pointerId, x0: ev.clientX, y0: ev.clientY, dx: 0, t0: performance.now(), active: false };
    });
    this.el.addEventListener('pointermove', (ev) => {
      const d = this.drag;
      if (!d || d.id !== ev.pointerId) return;
      const dx = ev.clientX - d.x0;
      const dy = ev.clientY - d.y0;
      if (!d.active) {
        if (Math.abs(dx) < 8 || Math.abs(dx) < Math.abs(dy)) return;
        d.active = true;
        vp().setPointerCapture(ev.pointerId);
        this.el.classList.add('dragging');
      }
      // Resist past the first and last gun.
      const atEdge = (dx > 0 && this.index === 0) || (dx < 0 && this.index === TOWER_IDS.length - 1);
      d.dx = atEdge ? dx * 0.3 : dx;
      this.place(d.dx, false);
    });
    const end = (ev: PointerEvent) => {
      const d = this.drag;
      if (!d || d.id !== ev.pointerId) return;
      this.drag = null;
      if (!d.active) return;
      this.el.classList.remove('dragging');
      this.suppressClick = true;
      window.setTimeout(() => (this.suppressClick = false), 0);
      const w = this.track.clientWidth || window.innerWidth;
      const v = d.dx / Math.max(1, performance.now() - d.t0); // px per ms
      const flick = Math.abs(v) > 0.45 && Math.abs(d.dx) > 24;
      if (d.dx < -w * 0.18 || (flick && d.dx < 0)) this.go(this.index + 1);
      else if (d.dx > w * 0.18 || (flick && d.dx > 0)) this.go(this.index - 1);
      else this.place(0, true);
    };
    this.el.addEventListener('pointerup', end);
    this.el.addEventListener('pointercancel', end);

    this.el.addEventListener('click', (ev) => {
      if (this.suppressClick) {
        ev.stopPropagation();
        ev.preventDefault();
        return;
      }
      const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>('button[data-ars]');
      if (!btn || btn.disabled) return;
      switch (btn.dataset.ars) {
        case 'prev': this.go(this.index - 1); break;
        case 'next': this.go(this.index + 1); break;
        case 'goto': this.go(Number(btn.dataset.i)); break;
        case 'start': this.close(); break;
        case 'level': {
          const id = btn.dataset.def as TowerId;
          this.levels.set(id, Number(btn.dataset.lv));
          const i = TOWER_IDS.indexOf(id);
          const old = this.track.children[i] as HTMLElement | undefined;
          if (!old) break;
          const tmp = document.createElement('div');
          tmp.innerHTML = this.slideHtml(id, i);
          const fresh = tmp.firstElementChild as HTMLElement;
          fresh.style.cssText = old.style.cssText;
          fresh.className = old.className;
          old.replaceWith(fresh);
          fresh.classList.add('relevel');
          this.refreshGuns();
          break;
        }
      }
    });

    window.addEventListener('keydown', (ev) => {
      if (!this.isOpen) return;
      if (ev.key === 'ArrowRight') this.go(this.index + 1);
      else if (ev.key === 'ArrowLeft') this.go(this.index - 1);
      else if (ev.key === 'Escape' || (ev.key === 'Enter' && !(ev.target as HTMLElement).closest?.('button'))) this.close();
      else return;
      ev.preventDefault();
    });
    window.addEventListener('resize', () => {
      if (!this.isOpen) return;
      this.place(0, false);
      this.refreshGuns();
    });
  }
}
