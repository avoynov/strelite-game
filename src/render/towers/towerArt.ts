/**
 * Rendered tower art (style В, photoreal): manifest types and the few numbers the
 * game needs to place it. The files live in public/art and are produced by
 * art/pipeline (see art/README.md). Nothing here depends on the renderer.
 */

export interface TowerArtLevel {
  level: number;
  /** Spritesheet path without the "@1x.json" / "@2x.json" suffix, relative to the art folder. */
  sheet: string;
  /** Frame name of the static layer: ground patch, fortifications, crates. */
  base: string;
  /** Prefix of the aim frames: `${aim}_00` … `${aim}_31`. */
  aim: string;
  /** All static art stays inside this radius (metres) around the tower's ground point. */
  footprintRadiusM: number;
  /** The gun turns inside this radius (metres). */
  sweepRadiusM: number;
  /** Per aim frame: muzzle offset from the ground point in @1x pixels (x right, y down). */
  muzzlePx: [number, number][];
  /** Per aim frame: muzzle in metres: grid x, grid y, height above the ground. */
  muzzleM: [number, number, number][];
}

export interface TowerArtDef {
  name: { bg: string; en: string };
  /** True while the gun is a stand-in for the final roster. */
  placeholder: boolean;
  levels: TowerArtLevel[];
}

export interface GroundArtDef {
  /** Image path without the "@1x.webp" / "@2x.webp" suffix, relative to the art folder. */
  image: string;
  sizePx1x: [number, number];
  /** Side of the repeating square of ground, in metres. */
  metres: number;
}

export interface TowerArtManifest {
  version: number;
  /** Pixels per metre along screen x; along screen y the ground is squashed to half. */
  pxPerMetre: { '@1x': number; '@2x': number };
  suggestedMetresPerTile: number;
  /** Number of aim frames per tower level. */
  directions: number;
  towers: Record<string, TowerArtDef>;
  ground?: Record<string, GroundArtDef>;
}

/**
 * Aim frame for a firing direction. `aim` is the angle the simulation already
 * uses: atan2(dy, dx) in grid cells (0 = +x). Frame 0 aims along +x.
 */
export function frameForAim(aim: number, directions: number): number {
  const step = (2 * Math.PI) / directions;
  return ((Math.round(aim / step) % directions) + directions) % directions;
}

/**
 * Like frameForAim, but keeps the current frame until the aim has moved
 * `margin` (a fraction of one step) past the boundary, so a target sitting on
 * the line between two frames does not make the gun flicker.
 */
export function stickyFrameForAim(aim: number, directions: number, current: number, margin = 0.15): number {
  const step = (2 * Math.PI) / directions;
  let off = (aim / step - current) % directions;
  if (off > directions / 2) off -= directions;
  else if (off < -directions / 2) off += directions;
  return Math.abs(off) <= 0.5 + margin ? current : frameForAim(aim, directions);
}

export function aimFrameName(level: TowerArtLevel, aim: number, directions: number): string {
  return `${level.aim}_${String(frameForAim(aim, directions)).padStart(2, '0')}`;
}

/**
 * Scale for a tower sprite (in @1x units) so that it matches the board.
 * `cellPx` is the width of one tile's diamond on screen, `metresPerTile` the
 * side of a tile in real metres: a tile is a diamond `metresPerTile * √2` wide.
 */
export function spriteScale(cellPx: number, metresPerTile: number, pxPerMetre1x: number): number {
  return cellPx / (metresPerTile * Math.SQRT2 * pxPerMetre1x);
}
