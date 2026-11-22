import { beforeEach, describe, expect, it } from 'vitest';
import { TICK, gunHp } from '../src/sim/content';
import { BASE_MAP, newBase, sanitizeBase } from '../src/sim/base';
import { Game } from '../src/sim/game';
import { buildArcMap, buildPathMap } from '../src/sim/maps';
import { levelMap } from '../src/sim/levels';
import { victoryBonus } from '../src/sim/research';
import type { WaveSpec } from '../src/sim/waves';
import {
  advanceOrder,
  dayKey,
  daysBetween,
  demoted,
  medalGold,
  medalsFor,
  newOrderState,
  orderFor,
  orderForPlayer,
  orderReward,
  ORDER_KINDS,
  rankOf,
  RANKS,
  rollOrder,
  starGold,
  starsFor,
  stepsIfDone,
  toNextRank,
} from '../src/sim/progress';
import { ProgressStore } from '../src/progressStore';

/** A tiny in-memory localStorage for the store. */
function fakeStorage(): void {
  const m = new Map<string, string>();
  (globalThis as { localStorage?: unknown }).localStorage = {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    removeItem: (k: string) => void m.delete(k),
  };
}

describe('stars', () => {
  it('1 for the win, 2 with half the lives left, 3 with nothing through', () => {
    expect(starsFor(false, 20, 20)).toBe(0);
    expect(starsFor(true, 1, 20)).toBe(1);
    expect(starsFor(true, 9, 20)).toBe(1);
    expect(starsFor(true, 10, 20)).toBe(2);
    expect(starsFor(true, 19, 20)).toBe(2);
    expect(starsFor(true, 20, 20)).toBe(3);
  });

  it('each new star pays a quarter of the level reward; stars already held pay nothing', () => {
    expect(starGold(10, 0, 3)).toBe(Math.round(victoryBonus(10) * 0.75));
    expect(starGold(10, 2, 3)).toBe(Math.round(victoryBonus(10) * 0.25));
    expect(starGold(10, 3, 3)).toBe(0);
    expect(starGold(10, 3, 1)).toBe(0);
  });

  it('a medal every 25 stars, each worth more', () => {
    expect(medalsFor(24)).toBe(0);
    expect(medalsFor(25)).toBe(1);
    expect(medalsFor(74)).toBe(2);
    expect(medalGold(2)).toBeGreaterThan(medalGold(1));
  });

  it('the store keeps the best per level and pays medals once', () => {
    fakeStorage();
    const p = new ProgressStore(() => new Date(2026, 10, 22));
    expect(p.recordStars('path', 1, 2).gold).toBe(starGold(1, 0, 2));
    expect(p.recordStars('path', 1, 1).gold).toBe(0);
    expect(p.starsOf('path', 1)).toBe(2);
    let medals = 0;
    for (let lv = 2; lv <= 9; lv++) medals += p.recordStars('arc', lv, 3).medals.length;
    // 2 + 8×3 = 26 stars: one medal.
    expect(p.totalStars()).toBe(26);
    expect(medals).toBe(1);
    expect(p.medals).toBe(1);
    // Kept across visits.
    const again = new ProgressStore(() => new Date(2026, 10, 22));
    expect(again.totalStars()).toBe(26);
    expect(again.medals).toBe(1);
    expect(again.recordStars('arc', 9, 3).medals).toEqual([]);
  });

  it('a mission game knows its starting lives', () => {
    const g = new Game(buildPathMap(levelMap(1)), { level: 1 });
    expect(g.startLives).toBe(g.lives);
  });
});

describe('veterans', () => {
  it('ranks at 25, 100, 300 and 1000 kills, up to +12% damage and +20% health', () => {
    expect([0, 24, 25, 99, 100, 300, 999, 1000, 5000].map(rankOf)).toEqual([0, 0, 1, 1, 2, 3, 3, 4, 4]);
    expect(RANKS[4]).toMatchObject({ damage: 0.12, hp: 0.2 });
    expect(toNextRank(90)).toBe(10);
    expect(toNextRank(1000)).toBeNull();
  });

  it('a rebuilt wreck drops one rank', () => {
    expect(demoted(150)).toBe(25);
    expect(demoted(1200)).toBe(300);
    expect(demoted(30)).toBe(0);
    expect(demoted(10)).toBe(10);
  });

  const only = (count: number): WaveSpec => ({ groups: [{ enemy: 'infantry', count, hp: 5, interval: 0.5, delay: 0, reward: 1 }], clearBonus: 0 });

  it('base guns count kills across battles, rank up, hit harder and get sturdier', () => {
    const state = newBase();
    state.guns = state.guns.slice(0, 1);
    state.guns[0]!.kills = 24;
    const g = new Game(buildArcMap(BASE_MAP, 'siege'), { level: 1, base: { state, wallet: { gold: 0 }, now: () => 0 }, waves: () => only(4), totalWaves: 1 });
    const t = g.towers[0]!;
    const plain = g.levelStats(t.def, t.level).damage;
    expect(g.rank(t)).toBe(0);
    expect(g.levelOf(t).damage).toBe(plain);
    g.startWave();
    for (let i = 0; i < 120 / TICK && g.phase === 'wave'; i++) g.step(TICK);
    expect(t.stats.kills).toBeGreaterThan(0);
    expect(t.vet).toBe(24 + t.stats.kills);
    expect(g.rank(t)).toBe(1);
    expect(g.drainEvents().some((e) => e.type === 'rankUp')).toBe(true);
    expect(g.levelOf(t).damage).toBeCloseTo(plain * 1.03, 1);
    expect(t.maxHp).toBe(Math.round(gunHp(t.size, t.level) * 1.05));
    // Saved with the base and read back.
    const saved = g.snapshot().guns[0]!;
    expect(saved.kills).toBe(t.vet);
    const back = sanitizeBase(JSON.parse(JSON.stringify({ ...state, guns: [saved] })));
    expect(back.guns[0]!.kills).toBe(t.vet);
    expect(back.guns[0]!.hp).toBe(t.hp);
  });

  it('missions do not make veterans', () => {
    const g = new Game(buildPathMap(levelMap(1)), { level: 1 });
    const t = { vet: 500 } as Parameters<Game['rank']>[0];
    expect(g.rank(t)).toBe(0);
  });

  it('a wreck rebuilt by a builder comes back one rank lower', () => {
    const state = newBase();
    state.guns = [{ ...state.guns[0]!, hp: 0, kills: 150, job: { kind: 'repair', endsAt: 1000 } }];
    const clock = { ms: 0 };
    const g = new Game(buildArcMap(BASE_MAP, 'siege'), { level: 1, base: { state, wallet: { gold: 0 }, now: () => clock.ms } });
    const t = g.towers[0]!;
    expect(g.rank(t)).toBe(2);
    clock.ms = 2000;
    g.step(TICK);
    expect(t.hp).toBe(t.maxHp);
    expect(t.vet).toBe(25);
    expect(g.rank(t)).toBe(1);
    expect(t.maxHp).toBe(Math.round(gunHp(t.size, t.level) * 1.05));
  });
});

describe('daily order', () => {
  it('the same order for everyone on a day, and not the same kind two days running', () => {
    const days = Array.from({ length: 60 }, (_, i) => dayKey(new Date(2026, 0, 1 + i)));
    const orders = days.map(orderFor);
    expect(orders.map((o) => o.kind)).toEqual(days.map((d) => orderFor(d).kind));
    for (let i = 1; i < orders.length; i++) expect(orders[i]!.kind).not.toBe(orders[i - 1]!.kind);
    // Over two months every kind comes up.
    for (const k of ORDER_KINDS) expect(orders.some((o) => o.kind === k)).toBe(true);
    for (const o of orders.filter((o) => o.kind === 'kill')) expect(o.count).toBeGreaterThan(0);
  });

  it('local dates: a new order at local midnight', () => {
    expect(dayKey(new Date(2026, 10, 22, 23, 59))).toBe('2026-11-22');
    expect(dayKey(new Date(2026, 10, 23, 0, 0))).toBe('2026-11-23');
    expect(daysBetween('2026-12-31', '2027-01-02')).toBe(2);
  });

  it('a kill order names infantry until the player has met its enemy', () => {
    const o = { day: '2026-11-22', kind: 'kill' as const, enemy: 'tank' as const, count: 5 };
    expect(orderForPlayer(o, 1).enemy).toBe('infantry');
    expect(orderForPlayer(o, 10)).toEqual(o);
  });

  it('pays 1.5× the top level reward, +10% per day in a row up to +50%; a missed day drops a step', () => {
    expect(orderReward(10, 0)).toBe(Math.round(victoryBonus(10) * 1.5));
    expect(orderReward(10, 5)).toBe(Math.round(victoryBonus(10) * 1.5 * 1.5));
    expect(orderReward(10, 9)).toBe(orderReward(10, 5));
    const s = { ...newOrderState('2026-11-22'), steps: 3, lastDone: '2026-11-21' };
    expect(stepsIfDone(s, '2026-11-22')).toBe(4);
    expect(stepsIfDone({ ...s, steps: 5 }, '2026-11-22')).toBe(5);
    expect(stepsIfDone(s, '2026-11-23')).toBe(2);
    expect(stepsIfDone(s, '2026-11-30')).toBe(0);
    expect(stepsIfDone(newOrderState('2026-11-22'), '2026-11-22')).toBe(0);
  });

  it('what counts for each kind', () => {
    const s = newOrderState('d');
    const win = { type: 'win' as const, mode: 'path' as const, kinds: 3, leaked: true };
    expect(advanceOrder({ day: 'd', kind: 'twoKinds' }, s, win).done).toBe(false);
    expect(advanceOrder({ day: 'd', kind: 'twoKinds' }, s, { ...win, kinds: 2 }).done).toBe(true);
    expect(advanceOrder({ day: 'd', kind: 'noLeak' }, s, win).done).toBe(false);
    expect(advanceOrder({ day: 'd', kind: 'noLeak' }, s, { ...win, leaked: false }).done).toBe(true);
    expect(advanceOrder({ day: 'd', kind: 'winArc' }, s, win).done).toBe(false);
    expect(advanceOrder({ day: 'd', kind: 'winArc' }, s, { ...win, mode: 'arc' }).done).toBe(true);
    expect(advanceOrder({ day: 'd', kind: 'defend' }, s, { type: 'defend', clean: false }).done).toBe(false);
    expect(advanceOrder({ day: 'd', kind: 'defend' }, s, { type: 'defend', clean: true }).done).toBe(true);
    expect(advanceOrder({ day: 'd', kind: 'upgrade' }, s, { type: 'upgrade' }).done).toBe(true);
    const kill = { day: 'd', kind: 'kill' as const, enemy: 'moto' as const, count: 2 };
    expect(advanceOrder(kill, s, { type: 'kill', def: 'infantry' })).toEqual({ progress: 0, done: false });
    expect(advanceOrder(kill, s, { type: 'kill', def: 'moto' })).toEqual({ progress: 1, done: false });
    expect(advanceOrder(kill, { ...s, progress: 1 }, { type: 'kill', def: 'moto' })).toEqual({ progress: 2, done: true });
  });

  it('a new day seals a new order and keeps the streak', () => {
    const s = { ...newOrderState('2026-11-21'), done: true, read: true, steps: 2, lastDone: '2026-11-21' };
    const next = rollOrder(s, '2026-11-22');
    expect(next).toMatchObject({ day: '2026-11-22', done: false, read: false, progress: 0, steps: 2, lastDone: '2026-11-21' });
    expect(rollOrder(next, '2026-11-22')).toBe(next);
  });

  describe('the store', () => {
    let now = new Date(2026, 10, 22, 10);
    beforeEach(() => {
      fakeStorage();
      now = new Date(2026, 10, 22, 10);
    });

    /** An event that finishes whatever today's order is. */
    const finisher = (p: ProgressStore) => {
      const o = p.order(50);
      switch (o.kind) {
        case 'kill':
          for (let i = 1; i < (o.count ?? 1); i++) p.report({ type: 'kill', def: o.enemy! }, 50, 20);
          return { type: 'kill' as const, def: o.enemy! };
        case 'defend':
          return { type: 'defend' as const, clean: true };
        case 'upgrade':
          return { type: 'upgrade' as const };
        default:
          return { type: 'win' as const, mode: 'arc' as const, kinds: 1, leaked: false };
      }
    };

    it('pays once a day and builds the streak day by day', () => {
      const p = new ProgressStore(() => now);
      expect(p.state.read).toBe(false);
      p.markRead();
      expect(p.state.read).toBe(true);
      const first = p.report(finisher(p), 50, 20);
      expect(first).toEqual({ gold: orderReward(20, 0), steps: 0 });
      expect(p.report(finisher(p), 50, 20)).toBeNull();
      now = new Date(2026, 10, 23, 9);
      expect(p.state.read).toBe(false);
      expect(p.report(finisher(p), 50, 20)).toEqual({ gold: orderReward(20, 1), steps: 1 });
      // A day missed: one step back, not to zero.
      now = new Date(2026, 10, 25, 9);
      expect(p.reward(20).steps).toBe(0);
      now = new Date(2026, 10, 24, 9);
      expect(p.reward(20).steps).toBe(2);
    });
  });
});
