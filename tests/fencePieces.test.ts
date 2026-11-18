import { describe, expect, it } from 'vitest';
import { fencePieces, NX, NY, PX, PY } from '../src/render/fenceView';

describe('fence pieces', () => {
  it('joins a tile to each neighbouring fence, back pieces before the post, front ones after', () => {
    expect(fencePieces(PX | PY)).toEqual(['post', 'py', 'px']);
    expect(fencePieces(NX | NY | PX)).toEqual(['ny', 'nx', 'post', 'px']);
    expect(fencePieces(PX | NX | PY | NY)).toEqual(['ny', 'nx', 'post', 'py', 'px']);
  });

  it('a lone fence stands as a short wall along x', () => {
    expect(fencePieces(0)).toEqual(['nx', 'post', 'px']);
  });
});
