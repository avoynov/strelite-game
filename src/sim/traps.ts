import { HQ_LEVELS } from './base';

/**
 * Traps: cheap one-shot devices on the enemy's way. Only ground units set them
 * off; the enemy neither sees nor avoids them. A spent trap is re-armed between
 * waves for part of its price. How many may lie on a map grows with the
 * headquarters, and each kind comes with its own headquarters level.
 */
export type TrapId = 'mine' | 'pit' | 'leg' | 'tar';

export interface TrapDef {
  id: TrapId;
  /** Headquarters level (1-based) that brings it. */
  hq: number;
  cost: number;
  /** Gold to re-arm it once spent. */
  recharge: number;
  /** Damage it deals (to each in the blast, or once to each in the tar). */
  damage: number;
  /** Share of armour it ignores. */
  pierce: number;
  /** Mine: blast radius; tar: radius of the patch (tiles). */
  radius?: number;
  /** Leg trap: seconds it holds a unit on foot; machines (any armour) half as long; bosses not at all. */
  hold?: number;
  /** Tar: share of speed taken off, and seconds the patch lies. */
  slow?: number;
  seconds?: number;
}

export const TRAPS: Record<TrapId, TrapDef> = {
  /** Blast over a small area with high pierce: crowds of infantry, trucks. */
  mine: { id: 'mine', hq: 2, cost: 60, recharge: 30, damage: 250, pierce: 0.6, radius: 1 },
  /** Heavy damage to the first unit that falls in: riders, APCs. */
  pit: { id: 'pit', hq: 4, cost: 70, recharge: 35, damage: 600, pierce: 0.5 },
  /** Holds one unit in place and wounds it: fast targets. */
  leg: { id: 'leg', hq: 6, cost: 60, recharge: 30, damage: 150, pierce: 0.3, hold: 3 },
  /** A patch that slows everyone in it and wounds them a little: dense columns. */
  tar: { id: 'tar', hq: 8, cost: 50, recharge: 25, damage: 40, pierce: 0.3, radius: 1.5, slow: 0.5, seconds: 6 },
};

export const TRAP_IDS: readonly TrapId[] = ['mine', 'pit', 'leg', 'tar'];

/** Burning tar (research): damage a second to everyone in a lit patch, at the trap's research strength. */
export const TAR_BURN = { dps: 30, pierce: 0.5 };

export function isTrapId(v: unknown): v is TrapId {
  return typeof v === 'string' && (TRAP_IDS as readonly string[]).includes(v);
}

/** Traps that may lie on a map at this headquarters level (0-based, as in the base). */
export function trapCap(hqLevel: number): number {
  return HQ_LEVELS[Math.max(0, Math.min(HQ_LEVELS.length - 1, hqLevel))]!.traps;
}

/** Whether the headquarters (0-based level) has brought this kind of trap. */
export function trapOpen(kind: TrapId, hqLevel: number): boolean {
  return hqLevel + 1 >= TRAPS[kind].hq;
}
