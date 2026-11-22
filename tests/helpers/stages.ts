/**
 * The order a player researches in. Stage 0 is a new player (crossbow and
 * ZIS-3, gun levels 1–3 only); each stage adds a few items.
 */
export const STAGES: string[][] = [
  [],
  ['boost.gold1'],
  ['boost.damage1', 'fx.crossbow'],
  ['gun.howitzer', 'lvl4.crossbow', 'lvl4.zis3'],
  ['boost.lives1', 'fx.zis3', 'gun.scorpion'],
  ['boost.damage2', 'fx.howitzer', 'lvl4.howitzer'],
  ['gun.trebuchet', 'lvl5.crossbow', 'lvl5.zis3', 'boost.reload1'],
  ['gun.greekfire', 'fx.scorpion', 'lvl4.scorpion', 'boost.gold2'],
  ['fx.trebuchet', 'lvl4.trebuchet', 'lvl5.howitzer', 'boost.damage3'],
  ['gun.railgun', 'fx.greekfire', 'lvl4.greekfire', 'lvl5.scorpion'],
  ['fx.railgun', 'lvl4.railgun', 'lvl5.trebuchet', 'lvl5.greekfire', 'lvl5.railgun', 'aim.crossbow'],
];

/** Every item of stages 0..k. */
export const upTo = (k: number): string[] => STAGES.slice(0, k + 1).flat();
