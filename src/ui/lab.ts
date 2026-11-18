import { t, type MessageKey } from '../i18n';
import { itemSeconds, labSlots, RESEARCH, researchItem, status, startError, type Branch, type LabInfo, type ResearchItem, type ResearchState, type StartError } from '../sim/research';

/**
 * "Лаборатория": the research tree. Three columns (guns, boosts, effects), each
 * a chain of items; one item researches at a time on a real-time countdown.
 */

export interface LabCallbacks {
  state(): ResearchState;
  /** The laboratory in the base: its level and whether it stands. */
  lab(): LabInfo;
  start(id: string): StartError | null;
  /** Timers run this many times faster than listed (testing builds). */
  speed: number;
  close(): void;
}

const BRANCHES: Branch[] = ['guns', 'levels', 'boosts', 'effects'];
const ERR: Record<StartError, MessageKey> = { busy: 'lab.busy', noGold: 'lab.noGold', locked: 'lab.lockedHint', done: 'lab.done', noLab: 'lab.noLab', labLevel: 'lab.labLevelHint' };

const pct = (v: number) => Math.round(v * 100);

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
      return `${t(`tower.${e.gun}` as MessageKey)}: ${parts.join(', ')}`;
    }
  }
}

const esc = (s: string) => s.replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]!);

export class Lab {
  readonly el: HTMLElement;
  private timer = 0;
  private last = '';
  private note = '';

  constructor(private readonly cb: LabCallbacks) {
    this.el = document.createElement('div');
    this.el.className = 'lab';
    this.el.hidden = true;
    this.el.setAttribute('role', 'dialog');
    this.el.setAttribute('aria-modal', 'true');
    this.el.addEventListener('click', (ev) => {
      const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>('button[data-lab]');
      if (!btn) return;
      if (btn.dataset.lab === 'close') this.close();
      else if (btn.dataset.lab === 'start' && btn.dataset.id) {
        const err = this.cb.start(btn.dataset.id);
        this.note = err ? t(ERR[err]) : '';
        this.render();
      }
    });
  }

  get isOpen(): boolean {
    return !this.el.hidden;
  }

  open(): void {
    this.note = '';
    this.el.hidden = false;
    this.render();
    window.clearInterval(this.timer);
    this.timer = window.setInterval(() => this.render(), 1000);
  }

  close(): void {
    if (!this.isOpen) return;
    window.clearInterval(this.timer);
    this.el.hidden = true;
    this.cb.close();
  }

  invalidate(): void {
    this.last = '';
    if (this.isOpen) this.render();
  }

  render(): void {
    const s = this.cb.state();
    const html = `
      <header class="lab-head">
        <div>
          <p class="lab-kicker">${t('lab.kicker')}</p>
          <h1 class="lab-title">${t('lab.title')}</h1>
        </div>
        <div class="lab-treasury" title="${t('lab.treasury')}"><span class="ico ico-gold" aria-hidden="true"></span><b>${s.gold}</b></div>
      </header>
      ${this.activeHtml(s)}
      <div class="lab-branches">
        ${BRANCHES.map((b) => this.branchHtml(b, s)).join('')}
      </div>
      <footer class="lab-foot">
        <p class="lab-note" role="status">${esc(this.note)}</p>
        <button class="btn primary" data-lab="close">${t('lab.close')}</button>
      </footer>`;
    if (html !== this.last) {
      this.el.innerHTML = html;
      this.last = html;
    }
  }

  private activeHtml(s: ResearchState): string {
    const lab = this.cb.lab();
    const head = `<p class="lab-idle">${t('lab.building', { n: lab.level + 1, slots: labSlots(lab) })}</p>`;
    if (!lab.standing) return `<p class="lab-idle lab-down">${t('lab.destroyed')}</p>`;
    if (!s.active.length) return `${head}<p class="lab-idle">${t('lab.idle')}</p>`;
    const now = s.pausedAt ?? Date.now();
    return head + s.active.map((a) => {
      const item = researchItem(a.id)!;
      const left = (a.endsAt - now) / 1000;
      const total = itemSeconds(item, lab, this.cb.speed);
      const done = Math.min(1, Math.max(0, 1 - left / total));
      return `
      <div class="lab-active">
        <div class="lab-active-row"><span>${t('lab.inProgress')}: <b>${esc(itemName(item))}</b></span><span class="lab-left">${formatDuration(left)}</span></div>
        <div class="lab-bar"><i style="width:${(done * 100).toFixed(1)}%"></i></div>
      </div>`;
    }).join('');
  }

  private branchHtml(branch: Branch, s: ResearchState): string {
    const items = RESEARCH.filter((r) => r.branch === branch);
    return `
      <section class="lab-branch">
        <h2>${t(`lab.branch.${branch}` as MessageKey)}</h2>
        <ol>${items.map((r) => this.itemHtml(r, s)).join('')}</ol>
      </section>`;
  }

  private itemHtml(item: ResearchItem, s: ResearchState): string {
    const st = status(s, item.id);
    const lab = this.cb.lab();
    const err = startError(s, item.id, lab);
    const seconds = itemSeconds(item, lab, this.cb.speed);
    let foot: string;
    if (st === 'done') foot = `<span class="lab-tag done">${t('lab.done')}</span>`;
    else if (st === 'active') foot = `<span class="lab-tag active">${t('lab.inProgress')}</span>`;
    else if (st === 'locked') {
      const need = item.requires.filter((r) => !s.done.includes(r)).map((r) => itemName(researchItem(r)!));
      foot = `<span class="lab-need">${esc(t('lab.requires', { list: need.join(', ') }))}</span>`;
    } else if (err === 'labLevel') {
      foot = `<span class="lab-need">${esc(t('lab.needsLab', { n: item.lab ?? 1 }))}</span>`;
    } else {
      foot = `<button class="btn primary lab-go" data-lab="start" data-id="${item.id}" ${err ? 'aria-disabled="true"' : ''}>
        ${t('lab.start')}
        <span class="cost${err === 'noGold' ? ' poor' : ''}"><span class="ico ico-gold"></span>${item.cost}</span>
        <span class="lab-time">${formatDuration(seconds)}</span>
      </button>`;
    }
    return `
      <li class="lab-item ${st}">
        <div class="lab-name">${esc(itemName(item))}</div>
        <div class="lab-desc">${esc(itemEffect(item))}</div>
        <div class="lab-foot-row">${foot}${st === 'locked' || err === 'labLevel' ? `<span class="lab-meta"><span class="ico ico-gold"></span>${item.cost} · ${formatDuration(seconds)}</span>` : ''}</div>
      </li>`;
  }
}
