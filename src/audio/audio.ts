import { SAMPLE_RATE, SOUND_NAMES, type SoundName } from './synth';
import type { SynthReply, SynthRequest } from './synthWorker';

export interface AudioSettings {
  /** Everything off. */
  muted: boolean;
  /** 0..1 */
  music: number;
  /** 0..1 */
  sfx: number;
}

const KEY = 'strelite.audio';
const DEFAULTS: AudioSettings = { muted: false, music: 0.5, sfx: 0.8 };

/** How many takes of a sound are made; the frequent ones vary so a volley does not sound like a machine. */
const VARIANTS: Partial<Record<SoundName, number>> = {
  crossbow: 3, scorpion: 3, zis3: 3, howitzer: 2, trebuchet: 2, railgun: 2,
  burst: 3, impact: 4, deathSoft: 3, deathVehicle: 2, deathAir: 2, rifle: 3, ram: 2,
};

/** Shortest gap between two starts of one sound, in seconds: a volley still reads as a volley, not a buzz. */
const MIN_GAP: Partial<Record<SoundName, number>> = {
  crossbow: 0.045, scorpion: 0.06, zis3: 0.08, howitzer: 0.1, trebuchet: 0.12, railgun: 0.09,
  burst: 0.07, impact: 0.035, deathSoft: 0.05, deathVehicle: 0.08, deathAir: 0.1, deathBig: 0.2,
  rifle: 0.05, tankGun: 0.1, ram: 0.08, wrecked: 0.15, leak: 0.3, build: 0.1,
};

/** Loudness of each sound against the others. */
const LEVEL: Partial<Record<SoundName, number>> = {
  crossbow: 0.55, scorpion: 0.65, zis3: 0.8, howitzer: 0.9, trebuchet: 0.7, railgun: 0.75,
  burst: 0.7, impact: 0.45, deathSoft: 0.5, deathVehicle: 0.75, deathAir: 0.7, deathBig: 1,
  rifle: 0.4, tankGun: 0.75, ram: 0.6, wrecked: 0.85, leak: 0.7, click: 0.6, build: 0.7,
  waveStart: 0.8, waveClear: 0.7, won: 0.9, lost: 0.9,
};

/** Never more sounds than this at once; the rest are dropped (phones choke on many voices). */
const MAX_VOICES = 18;

export function loadAudioSettings(): AudioSettings {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? 'null') as Partial<AudioSettings> | null;
    const num = (v: unknown, d: number) => (typeof v === 'number' && v >= 0 && v <= 1 ? v : d);
    return { muted: raw?.muted === true, music: num(raw?.music, DEFAULTS.music), sfx: num(raw?.sfx, DEFAULTS.sfx) };
  } catch {
    return { ...DEFAULTS };
  }
}

/**
 * The game's sound: effects and a looping march, all synthesised on the
 * device (see synth.ts). Starts silent; the first tap or key unlocks it, as
 * browsers require. Everything is a no-op where Web Audio is missing.
 */
export class GameAudio {
  private s: AudioSettings = loadAudioSettings();
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private sfxBus: GainNode | null = null;
  private musicBus: GainNode | null = null;
  private readonly buffers = new Map<SoundName, AudioBuffer[]>();
  private readonly lastStart = new Map<SoundName, number>();
  private voices = 0;
  private loops = new Map<SoundName, { src: AudioBufferSourceNode; gain: GainNode }>();
  private musicStarted = false;
  private music: AudioBuffer | null = null;
  private paused = false;
  private hidden = false;

  constructor() {
    const unlock = () => this.unlock();
    window.addEventListener('pointerdown', unlock, { capture: true });
    window.addEventListener('keydown', unlock, { capture: true });
  }

  get settings(): AudioSettings {
    return this.s;
  }

  set(next: Partial<AudioSettings>): void {
    this.s = { ...this.s, ...next };
    try {
      localStorage.setItem(KEY, JSON.stringify(this.s));
    } catch {
      // Not saved: this visit only.
    }
    this.applyLevels();
  }

  /** The battle is paused: effects stop, the music drops low. */
  setPaused(p: boolean): void {
    this.paused = p;
    if (p) for (const name of this.loops.keys()) this.setLoop(name, 0);
    this.applyLevels();
  }

  /** The app went to the background (or came back): all sound stops (or resumes). */
  setHidden(h: boolean): void {
    this.hidden = h;
    if (!this.ctx) return;
    if (h) void this.ctx.suspend().catch(() => {});
    else void this.ctx.resume().catch(() => {});
  }

  /**
   * Play an effect. `pan` −1..1 places it left–right; `gain` scales it (far
   * away or off screen is quieter). Dropped when muted, paused, too soon after
   * the same sound, or with too many voices already sounding.
   */
  play(name: SoundName, pan = 0, gain = 1): void {
    const ctx = this.ctx;
    if (!ctx || !this.sfxBus || this.s.muted || this.s.sfx <= 0 || this.hidden || ctx.state !== 'running') return;
    if (this.paused && name !== 'click') return;
    const now = ctx.currentTime;
    const gap = MIN_GAP[name] ?? 0;
    if (now - (this.lastStart.get(name) ?? -1) < gap) return;
    if (this.voices >= MAX_VOICES && name !== 'click') return;
    const takes = this.takes(name);
    if (!takes.length) return;
    const buf = takes[Math.floor(Math.random() * takes.length)]!;
    this.lastStart.set(name, now);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    // A little pitch spread on top of the takes.
    src.playbackRate.value = 0.94 + Math.random() * 0.12;
    const g = ctx.createGain();
    g.gain.value = (LEVEL[name] ?? 0.7) * gain;
    let node: AudioNode = src;
    node.connect(g);
    node = g;
    if (pan !== 0 && typeof ctx.createStereoPanner === 'function') {
      const p = ctx.createStereoPanner();
      p.pan.value = Math.max(-1, Math.min(1, pan));
      node.connect(p);
      node = p;
    }
    node.connect(this.sfxBus);
    this.voices++;
    src.onended = () => {
      this.voices--;
      src.disconnect();
    };
    src.start();
  }

  /** A looping sound (the flamethrower) held at a level 0..1; eased so it swells and dies away. */
  setLoop(name: SoundName, level: number): void {
    const ctx = this.ctx;
    if (!ctx || !this.sfxBus || ctx.state !== 'running') return;
    let l = this.loops.get(name);
    const target = this.s.muted || this.paused ? 0 : level * (LEVEL[name] ?? 0.7);
    if (!l) {
      const buf = this.takes(name)[0];
      if (target <= 0 || !buf) return;
      const src = ctx.createBufferSource();
      src.buffer = buf;
      src.loop = true;
      const gain = ctx.createGain();
      gain.gain.value = 0;
      src.connect(gain).connect(this.sfxBus);
      src.start();
      l = { src, gain };
      this.loops.set(name, l);
    }
    l.gain.gain.setTargetAtTime(target, ctx.currentTime, target > l.gain.gain.value ? 0.05 : 0.2);
  }

  /** The takes made so far (sounds arrive from the worker one by one; until then the sound is skipped). */
  private takes(name: SoundName): AudioBuffer[] {
    return this.buffers.get(name) ?? [];
  }

  private toBuffer(data: Float32Array): AudioBuffer {
    const buf = this.ctx!.createBuffer(1, data.length, SAMPLE_RATE);
    buf.copyToChannel(data as Float32Array<ArrayBuffer>, 0);
    return buf;
  }

  private unlock(): void {
    if (!this.ctx) {
      const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) return;
      // iOS: mix with the player's own music and respect the silent switch.
      const session = (navigator as unknown as { audioSession?: { type: string } }).audioSession;
      if (session) session.type = 'ambient';
      try {
        this.ctx = new Ctor({ latencyHint: 'interactive' });
      } catch {
        return;
      }
      const ctx = this.ctx;
      this.master = ctx.createGain();
      // A gentle limiter so a big volley does not clip.
      const comp = ctx.createDynamicsCompressor();
      comp.threshold.value = -10;
      comp.knee.value = 8;
      comp.ratio.value = 6;
      comp.attack.value = 0.003;
      comp.release.value = 0.2;
      this.master.connect(comp).connect(ctx.destination);
      this.sfxBus = ctx.createGain();
      this.musicBus = ctx.createGain();
      this.sfxBus.connect(this.master);
      this.musicBus.connect(this.master);
      this.applyLevels();
      ctx.onstatechange = () => {
        if (ctx.state === 'running') this.startMusic();
      };
      this.makeSounds();
    }
    if (this.ctx.state !== 'running' && !this.hidden) void this.ctx.resume().catch(() => {});
    this.startMusic();
  }

  private applyLevels(): void {
    const ctx = this.ctx;
    if (!ctx || !this.master || !this.sfxBus || !this.musicBus) return;
    const t = ctx.currentTime;
    this.master.gain.setTargetAtTime(this.s.muted ? 0 : 1, t, 0.03);
    this.sfxBus.gain.setTargetAtTime(this.s.sfx * this.s.sfx, t, 0.03);
    this.musicBus.gain.setTargetAtTime(this.s.music * this.s.music * 0.55 * (this.paused ? 0.45 : 1), t, 0.15);
  }

  /**
   * Make every sound in a worker, the common ones first, then the march.
   * Without workers (very old browsers) the game stays silent.
   */
  private makeSounds(): void {
    let worker: Worker;
    try {
      worker = new Worker(new URL('./synthWorker.ts', import.meta.url), { type: 'module' });
    } catch {
      return;
    }
    const first: SoundName[] = ['click', 'crossbow', 'scorpion', 'impact', 'deathSoft', 'deathVehicle', 'burst', 'zis3', 'waveStart', 'waveClear', 'build'];
    const order = [...first, ...SOUND_NAMES.filter((n) => !first.includes(n))];
    let pending = 0;
    for (const name of order) {
      for (let take = 1; take <= (VARIANTS[name] ?? 1); take++) {
        worker.postMessage({ kind: 'sfx', name, take } satisfies SynthRequest);
        pending++;
      }
    }
    worker.postMessage({ kind: 'music' } satisfies SynthRequest);
    pending++;
    worker.onmessage = (ev: MessageEvent<SynthReply>) => {
      const r = ev.data;
      if (!this.ctx) return;
      if (r.kind === 'sfx') {
        const list = this.buffers.get(r.name) ?? [];
        list.push(this.toBuffer(r.data));
        this.buffers.set(r.name, list);
      } else {
        this.music = this.toBuffer(r.data);
        this.startMusic();
      }
      if (--pending === 0) worker.terminate();
    };
    worker.onerror = () => worker.terminate();
  }

  /** Loop the march, fading in. */
  private startMusic(): void {
    const ctx = this.ctx;
    if (this.musicStarted || !ctx || !this.musicBus || !this.music || ctx.state !== 'running') return;
    this.musicStarted = true;
    const src = ctx.createBufferSource();
    src.buffer = this.music;
    src.loop = true;
    const fade = ctx.createGain();
    fade.gain.value = 0;
    fade.gain.setTargetAtTime(1, ctx.currentTime, 1.5);
    src.connect(fade).connect(this.musicBus);
    src.start();
  }
}
