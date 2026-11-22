import { ACTS, RESEARCH } from '../../src/sim/research';

/**
 * The order a player researches in. Stage 0 is a new player (crossbow and
 * ZIS-3, gun levels 1–3 only); the first stages climb through act I a few
 * items at a time, then each stage is one whole act (II–IX): everything its
 * headquarters level brings into the tree.
 */
const ACT_ONE: string[][] = [
  [],
  ['boost.gold1'],
  ['boost.damage1', 'fx.crossbow'],
  ['gun.howitzer', 'fx.zis3'],
  ['boost.lives1', 'gun.scorpion', 'fx.howitzer'],
];
const actOf = (id: string) => RESEARCH.find((r) => r.id === id)?.hq ?? 1;

/** Items of an act, ordered so each comes after what it needs. */
function inOrder(ids: string[], before: Set<string>): string[] {
  const out: string[] = [];
  const done = new Set(before);
  let left = [...ids];
  while (left.length) {
    const ready = left.filter((id) => RESEARCH.find((r) => r.id === id)!.requires.every((q) => done.has(q)));
    if (!ready.length) throw new Error(`stages: cannot order ${left.join(', ')}`);
    for (const id of ready) {
      out.push(id);
      done.add(id);
    }
    left = left.filter((id) => !done.has(id));
  }
  return out;
}

export const STAGES: string[][] = (() => {
  const stages = ACT_ONE.map((s) => [...s]);
  const seen = new Set(stages.flat());
  stages[stages.length - 1]!.push(...inOrder(RESEARCH.filter((r) => actOf(r.id) === 1 && !seen.has(r.id)).map((r) => r.id), seen));
  for (const id of stages.flat()) seen.add(id);
  for (let act = 2; act <= ACTS; act++) {
    const items = inOrder(RESEARCH.filter((r) => actOf(r.id) === act).map((r) => r.id), seen);
    stages.push(items);
    for (const id of items) seen.add(id);
  }
  return stages;
})();

/** The stage at which act `act` (1..9) is complete. */
export const actStage = (act: number): number => ACT_ONE.length - 2 + act;

/** Every item of stages 0..k. */
export const upTo = (k: number): string[] => STAGES.slice(0, k + 1).flat();
