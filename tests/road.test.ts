import { describe, expect, it } from 'vitest';
import { roadCentreLines, stripOutline } from '../src/render/road';
import { Game } from '../src/sim/game';
import { buildPathMap, MEADOW } from '../src/sim/maps';

describe('road shape', () => {
  it('follows the map corners and runs on past both ends', () => {
    const [line] = roadCentreLines(new Game(buildPathMap(MEADOW)), 10);
    const corners = MEADOW.waypoints.map(([x, y]) => ({ x: x + 0.5, y: y + 0.5 }));
    expect(line).toEqual([{ x: -9.5, y: 6.5 }, ...corners.slice(1, -1), { x: 26.5, y: 39.5 }]);
  });

  it('outlines a strip with square corners', () => {
    // An L: right 4, then down 3, one unit wide.
    const outline = stripOutline([{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 3 }], 0.5);
    expect(outline).toEqual([
      { x: 0, y: 0.5 }, { x: 3.5, y: 0.5 }, { x: 3.5, y: 3 },
      { x: 4.5, y: 3 }, { x: 4.5, y: -0.5 }, { x: 0, y: -0.5 },
    ]);
  });
});
