/**
 * How the game shows one tower, independent of how it is drawn.
 *
 * The board talks to a tower's picture only through this interface, in grid
 * cells, radians and metres. Today it is implemented with rendered sprites
 * (SpriteTowerView) and a drawn stand-in (PlaceholderTowerView). If the game
 * later moves to real 3D, a view that drives the GLB models (nodes `turret`,
 * `elevating`, `recoil`, exported by art/pipeline/export_gltf.py) implements
 * the same methods and nothing else in the game has to change.
 */
export interface TowerView {
  /** Put the tower's ground point at this position, in grid cells. */
  place(gx: number, gy: number): void;
  /** Aim at an angle: atan2(dy, dx) in grid cells, as in the simulation. */
  setAim(aim: number): void;
  /** Switch to an upgrade level (1-based). */
  setLevel(level: number): void;
  /** The gun has just fired: play flash, recoil, smoke. */
  fire(): void;
  /** Advance the view's own animations by `dt` seconds. */
  update(dt: number): void;
  /** Where shots leave the barrel at the current aim: grid cells and metres above the ground. */
  muzzle(): { gx: number; gy: number; heightM: number };
  destroy(): void;
}

/** Describes a tower to a view factory; plain data, no renderer types. */
export interface TowerViewSpec {
  /** Tower id, as in the simulation's content and the art manifest. */
  tower: string;
  /** 1-based upgrade level. */
  level: number;
  /** Footprint side in tiles. */
  size: number;
}
