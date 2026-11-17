import type { GunPortrait } from './towers/spriteTowerView';

/**
 * Clean gun portraits for HTML menus (public/art/portraits.json, made by
 * art/pipeline/render_portraits.sh): the gun alone on a transparent background,
 * no soil patch or fortifications. Cell i aims at game angle i * 2π / directions.
 */
interface PortraitLevel {
  level: number;
  image: string;
  cell: [number, number];
  cols: number;
  size: [number, number];
  anchor: [number, number];
}

interface PortraitManifest {
  version: number;
  directions: number;
  guns: Record<string, { levels: PortraitLevel[] }>;
}

export class PortraitArt {
  private constructor(
    private readonly manifest: PortraitManifest,
    private readonly baseUrl: string,
  ) {}

  static async load(baseUrl: string): Promise<PortraitArt | null> {
    try {
      const res = await fetch(`${baseUrl}/portraits.json`);
      return res.ok ? new PortraitArt((await res.json()) as PortraitManifest, baseUrl) : null;
    } catch {
      return null;
    }
  }

  has(gun: string): boolean {
    return !!this.manifest.guns[gun]?.levels.length;
  }

  /** Warm the browser cache so slides do not pop in. */
  preload(): void {
    for (const g of Object.values(this.manifest.guns)) for (const l of g.levels) new Image().src = `${this.baseUrl}/${l.image}`;
  }

  /**
   * `frame` counts in `directions` steps (the towers' 32); the nearest cell is used.
   * Falls back to the nearest lower level that has a portrait.
   */
  portrait(gun: string, level: number, frame: number, directions: number): GunPortrait | undefined {
    const levels = this.manifest.guns[gun]?.levels ?? [];
    let lv: PortraitLevel | undefined;
    for (const l of levels) if (l.level <= level && (!lv || l.level > lv.level)) lv = l;
    lv ??= levels[0];
    if (!lv) return undefined;
    const n = this.manifest.directions;
    const i = ((Math.round((frame * n) / directions) % n) + n) % n;
    const [cw, ch] = lv.cell;
    return {
      url: `${this.baseUrl}/${lv.image}`,
      sheetSize: lv.size,
      frame: [(i % lv.cols) * cw, Math.floor(i / lv.cols) * ch, cw, ch],
      // Centre the cell (the union of every heading), not the ground point, so the
      // long shadow does not push the gun off-centre; the gun still turns in place.
      offset: [-cw / 2, -ch / 2],
      reach: Math.max(cw, ch) / 2,
      half: [cw / 2, ch / 2],
    };
  }
}
