import { describe, expect, it } from 'vitest';
import { FlowField } from '../src/sim/flowField';
import { buildPathMap, MEADOW } from '../src/sim/maps';

describe('path map + flow field', () => {
  const map = buildPathMap(MEADOW);
  const flow = new FlowField(map.grid, map.goals, (x, y) => map.grid.get(x, y) === 'path');

  it('reaches the goal from the spawn by following next()', () => {
    let c = map.spawns[0]!;
    let steps = 0;
    for (;;) {
      const n = flow.next(c.x, c.y);
      if (!n) break;
      c = n;
      if (++steps > 500) throw new Error('loop');
    }
    expect(c).toEqual(map.goals[0]);
    expect(steps).toBe(flow.distanceAt(map.spawns[0]!.x, map.spawns[0]!.y));
  });

  it('marks build cells as unreachable', () => {
    expect(map.grid.get(0, 0)).toBe('build');
    expect(map.grid.get(20, 0)).toBe('blocked');
    expect(flow.distanceAt(0, 0)).toBe(-1);
  });
});
