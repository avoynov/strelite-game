/// <reference lib="webworker" />
import { renderMusic, synth, type SoundName } from './synth';

/** Makes sounds off the main thread, so a slow phone never drops a frame for them. */
export type SynthRequest = { kind: 'sfx'; name: SoundName; take: number } | { kind: 'music' };
export type SynthReply = { kind: 'sfx'; name: SoundName; take: number; data: Float32Array } | { kind: 'music'; data: Float32Array };

const scope = self as unknown as DedicatedWorkerGlobalScope;
scope.onmessage = (ev: MessageEvent<SynthRequest>) => {
  const req = ev.data;
  const reply: SynthReply = req.kind === 'sfx' ? { ...req, data: synth(req.name, req.take) } : { kind: 'music', data: renderMusic() };
  scope.postMessage(reply, [reply.data.buffer]);
};
