/**
 * Every sound in the game is synthesised here from noise and oscillators, so
 * there are no audio files to download, license or keep in one style. Each
 * recipe returns mono samples in [-1, 1] at SAMPLE_RATE. Pure functions:
 * the same name and seed always give the same sound.
 */

export const SAMPLE_RATE = 24000;

export type SoundName =
  | 'crossbow'
  | 'scorpion'
  | 'zis3'
  | 'howitzer'
  | 'greekfire'
  | 'trebuchet'
  | 'railgun'
  | 'burst'
  | 'impact'
  | 'deathSoft'
  | 'deathVehicle'
  | 'deathAir'
  | 'deathBig'
  | 'rifle'
  | 'tankGun'
  | 'ram'
  | 'wrecked'
  | 'leak'
  | 'click'
  | 'build'
  | 'waveStart'
  | 'waveClear'
  | 'won'
  | 'lost';

export const SOUND_NAMES: readonly SoundName[] = [
  'crossbow', 'scorpion', 'zis3', 'howitzer', 'greekfire', 'trebuchet', 'railgun',
  'burst', 'impact', 'deathSoft', 'deathVehicle', 'deathAir', 'deathBig',
  'rifle', 'tankGun', 'ram', 'wrecked', 'leak', 'click', 'build',
  'waveStart', 'waveClear', 'won', 'lost',
];

// ---- building blocks --------------------------------------------------------

/** Small fast seeded generator (mulberry32). */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const n = (seconds: number) => Math.max(1, Math.round(seconds * SAMPLE_RATE));
const TAU = Math.PI * 2;

function white(len: number, r: () => number): Float32Array {
  const out = new Float32Array(len);
  for (let i = 0; i < len; i++) out[i] = r() * 2 - 1;
  return out;
}

/** Biquad filter (RBJ cookbook), in place. `freq` may change over time. */
function biquad(buf: Float32Array, type: 'lp' | 'hp' | 'bp', freq: number | ((t: number) => number), q = 0.707): Float32Array {
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  let b0 = 0, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
  const set = (f: number) => {
    const w = (TAU * Math.min(Math.max(f, 10), SAMPLE_RATE * 0.45)) / SAMPLE_RATE;
    const cos = Math.cos(w);
    const alpha = Math.sin(w) / (2 * q);
    const a0 = 1 + alpha;
    if (type === 'lp') {
      b0 = (1 - cos) / 2 / a0; b1 = (1 - cos) / a0; b2 = b0;
    } else if (type === 'hp') {
      b0 = (1 + cos) / 2 / a0; b1 = -(1 + cos) / a0; b2 = b0;
    } else {
      b0 = alpha / a0; b1 = 0; b2 = -alpha / a0;
    }
    a1 = (-2 * cos) / a0;
    a2 = (1 - alpha) / a0;
  };
  const varying = typeof freq === 'function';
  if (!varying) set(freq);
  for (let i = 0; i < buf.length; i++) {
    if (varying && (i & 31) === 0) set(freq(i / SAMPLE_RATE));
    const x = buf[i]!;
    const y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
    x2 = x1; x1 = x; y2 = y1; y1 = y;
    buf[i] = y;
  }
  return buf;
}

/** Multiply by an envelope: instant-ish attack, exponential decay with time constant `tau`. */
function decay(buf: Float32Array, tau: number, attack = 0.002, delay = 0): Float32Array {
  for (let i = 0; i < buf.length; i++) {
    const t = i / SAMPLE_RATE - delay;
    buf[i]! *= t < 0 ? 0 : t < attack ? t / attack : Math.exp(-(t - attack) / tau);
  }
  return buf;
}

/** A sine whose frequency follows `f(t)`, with an exponential decay. */
function tone(len: number, f: (t: number) => number, tau: number, shape: 'sin' | 'saw' | 'tri' = 'sin', attack = 0.003): Float32Array {
  const out = new Float32Array(len);
  let ph = 0;
  for (let i = 0; i < len; i++) {
    const t = i / SAMPLE_RATE;
    ph += f(t) / SAMPLE_RATE;
    const p = ph - Math.floor(ph);
    const v = shape === 'sin' ? Math.sin(TAU * p) : shape === 'saw' ? 2 * p - 1 : 1 - 4 * Math.abs(p - 0.5);
    out[i] = v * (t < attack ? t / attack : Math.exp(-(t - attack) / tau));
  }
  return out;
}

/** Add `src` into `dst` at `at` seconds, scaled. */
function mix(dst: Float32Array, src: Float32Array, gain = 1, at = 0): Float32Array {
  const o = Math.round(at * SAMPLE_RATE);
  for (let i = 0; i < src.length && i + o < dst.length; i++) if (i + o >= 0) dst[i + o]! += src[i]! * gain;
  return dst;
}

/** Tape-like saturation: rounds off peaks, adds the grit of a real report. */
function drive(buf: Float32Array, amount: number): Float32Array {
  const k = Math.tanh(amount);
  for (let i = 0; i < buf.length; i++) buf[i] = Math.tanh(buf[i]! * amount) / k;
  return buf;
}

/** Scale to the given peak; short fades at both ends so nothing clicks. */
export function finish(buf: Float32Array, peak = 0.9): Float32Array {
  let max = 0;
  for (let i = 0; i < buf.length; i++) max = Math.max(max, Math.abs(buf[i]!));
  const g = max > 0 ? peak / max : 0;
  const fade = Math.min(n(0.004), buf.length >> 2);
  for (let i = 0; i < buf.length; i++) {
    let v = buf[i]! * g;
    if (i < fade) v *= i / fade;
    const left = buf.length - 1 - i;
    if (left < fade * 4) v *= left / (fade * 4);
    buf[i] = v;
  }
  return buf;
}

/** Sparse crackle: random clicks, denser at the start. */
function crackle(len: number, r: () => number, rate: number, tau: number): Float32Array {
  const out = new Float32Array(len);
  for (let i = 0; i < len; i++) {
    const t = i / SAMPLE_RATE;
    if (r() < (rate / SAMPLE_RATE) * Math.exp(-t / tau)) {
      // Each crack is a tiny burst of noise. (Alternating-sign clicks would sit at the Nyquist
      // frequency and leave a high whine after the sound.)
      const amp = r() * 0.7 + 0.3;
      const l = 12 + Math.floor(r() * 60);
      for (let j = 0; j < l && i + j < len; j++) out[i + j]! += amp * (r() * 2 - 1) * Math.exp(-j / (l / 4));
    }
  }
  // Keep the grit in the 1–5 kHz band, nothing up near the top.
  return biquad(out, 'lp', 5000);
}

/** A metal body ringing: inharmonic partials. */
function ring(len: number, base: number, tau: number, r: () => number): Float32Array {
  const out = new Float32Array(len);
  for (const [ratio, g] of [[1, 1], [2.76, 0.6], [5.4, 0.35], [8.93, 0.2]] as const) {
    const f = base * ratio * (0.98 + r() * 0.04);
    if (f > 6000) continue; // very high partials ring on as a whistle
    mix(out, tone(len, () => f, tau / Math.sqrt(ratio)), g);
  }
  return out;
}

// ---- recipes ---------------------------------------------------------------

/** A gun's report: crack + low body + rumbling tail. */
function cannon(r: () => number, o: { len: number; crack: number; body: number; bodyTo: number; tail: number; drive: number }): Float32Array {
  const len = n(o.len);
  const out = new Float32Array(len);
  // The supersonic crack: bright noise, very short.
  mix(out, decay(biquad(white(len, r), 'hp', 900), o.crack), 1.0);
  // The blast: mid noise, a little longer.
  mix(out, decay(biquad(white(len, r), 'lp', (t) => 2400 * Math.exp(-t * 12) + 300), o.crack * 3), 1.2);
  // The body: a falling thump.
  mix(out, tone(len, (t) => o.bodyTo + (o.body - o.bodyTo) * Math.exp(-t * 18), o.tail * 0.35), 1.1);
  // The tail: low rumble rolling off.
  mix(out, decay(biquad(biquad(white(len, r), 'lp', 220), 'lp', 180), o.tail, 0.02), 1.6);
  return drive(out, o.drive);
}

/** A tensioned string or bow arm let go: twang + wooden knock + swish. */
function bow(r: () => number, o: { len: number; pitch: number; knock: number; heavy: number }): Float32Array {
  const len = n(o.len);
  const out = new Float32Array(len);
  const f = o.pitch * (0.97 + r() * 0.06);
  mix(out, tone(len, (t) => f * (1 + 0.25 * Math.exp(-t * 40)), 0.07 + o.heavy * 0.05, 'tri'), 0.5);
  mix(out, tone(len, (t) => f * 2.01 * (1 + 0.2 * Math.exp(-t * 40)), 0.04), 0.25);
  // The knock of the stock / slider.
  mix(out, decay(biquad(white(len, r), 'bp', o.knock, 2.5), 0.012 + o.heavy * 0.01), 1.4);
  mix(out, tone(len, (t) => 90 + 120 * Math.exp(-t * 30), 0.04 + o.heavy * 0.04), 0.6 + o.heavy * 0.5);
  // The bolt leaving: a swish.
  const sw = biquad(white(len, r), 'bp', (t) => 3500 - t * 5000, 1.2);
  mix(out, decay(sw, 0.06, 0.02, 0.01), 0.35);
  return drive(out, 1.5);
}

function explosion(r: () => number, size: number): Float32Array {
  const len = n(0.8 + size * 0.9);
  const out = new Float32Array(len);
  mix(out, decay(biquad(white(len, r), 'lp', (t) => 3000 * Math.exp(-t * 6) + 150), 0.12 + size * 0.15), 1.4);
  mix(out, tone(len, (t) => 32 + 50 * Math.exp(-t * 10), 0.18 + size * 0.2), 1.2);
  mix(out, decay(biquad(white(len, r), 'lp', 140), 0.3 + size * 0.4, 0.03), 1.5 + size);
  mix(out, biquad(crackle(len, r, 220, 0.25 + size * 0.2), 'hp', 1500), 0.35);
  return drive(out, 2.2);
}

function horn(notes: Array<[number, number, number]>, len: number, r: () => number, bright = 1400): Float32Array {
  // Brass: a pair of slightly detuned saws through a lowpass that opens with the attack.
  const out = new Float32Array(n(len));
  for (const [freq, at, dur] of notes) {
    const l = n(dur + 0.4);
    const v = new Float32Array(l);
    for (const det of [0.997, 1.003]) {
      const vib = r() * TAU;
      mix(v, tone(l, (t) => freq * det * (1 + 0.004 * Math.sin(TAU * 5.2 * t + vib)), 99, 'saw', 0.04), 0.5);
    }
    biquad(v, 'lp', (t) => 300 + bright * Math.min(1, t / 0.08) * Math.exp(-t * 1.2), 0.9);
    for (let i = 0; i < l; i++) {
      const t = i / SAMPLE_RATE;
      v[i]! *= t < dur ? 1 : Math.exp(-(t - dur) / 0.08);
    }
    mix(out, v, 1, at);
  }
  return out;
}

function drum(len: number, r: () => number, at: number, dst: Float32Array, gain = 1): void {
  const l = n(len);
  const d = tone(l, (t) => 55 + 90 * Math.exp(-t * 25), 0.25);
  mix(d, decay(biquad(white(l, r), 'lp', 900), 0.03), 0.6);
  mix(dst, d, gain, at);
}

/** One sound. `seed` picks among small variations of the same recipe. */
export function synth(name: SoundName, seed = 1): Float32Array {
  const r = rng(seed * 7919 + name.length * 104729 + name.charCodeAt(0));
  switch (name) {
    case 'crossbow':
      return finish(bow(r, { len: 0.32, pitch: 210, knock: 1400, heavy: 0 }), 0.7);
    case 'scorpion':
      return finish(bow(r, { len: 0.5, pitch: 120, knock: 800, heavy: 1 }), 0.8);
    case 'zis3':
      return finish(cannon(r, { len: 1.1, crack: 0.012, body: 160, bodyTo: 48, tail: 0.32, drive: 2.5 }), 0.9);
    case 'howitzer':
      return finish(cannon(r, { len: 1.8, crack: 0.018, body: 110, bodyTo: 32, tail: 0.55, drive: 3 }), 0.95);
    case 'tankGun':
      return finish(cannon(r, { len: 1.2, crack: 0.014, body: 140, bodyTo: 40, tail: 0.4, drive: 2.8 }), 0.8);
    case 'rifle':
      return finish(cannon(r, { len: 0.35, crack: 0.006, body: 400, bodyTo: 140, tail: 0.06, drive: 2 }), 0.5);
    case 'greekfire': {
      // Siphon roar: a rushing hiss with a guttural flutter; loops seamlessly.
      const len = n(1.6);
      const out = new Float32Array(len);
      const roar = biquad(white(len, r), 'bp', 700, 0.6);
      const low = biquad(biquad(white(len, r), 'lp', 260), 'lp', 260);
      for (let i = 0; i < len; i++) {
        const t = i / SAMPLE_RATE;
        const flutter = 0.7 + 0.3 * Math.sin(TAU * 11 * t) * Math.sin(TAU * 1.25 * t);
        out[i] = roar[i]! * flutter + low[i]! * 2.2;
      }
      mix(out, biquad(crackle(len, r, 60, 99), 'hp', 2000), 0.25);
      // Crossfade the ends so it loops without a seam.
      const x = n(0.15);
      for (let i = 0; i < x; i++) {
        const k = i / x;
        out[i] = out[i]! * k + out[len - x + i]! * (1 - k);
      }
      return finish(drive(out.subarray(0, len - x).slice(), 1.4), 0.7);
    }
    case 'trebuchet': {
      const len = n(1.0);
      const out = new Float32Array(len);
      // Timber creak: a rough low buzz whose pitch wavers.
      const creak = tone(len, (t) => 70 + 25 * Math.sin(TAU * 3 * t) + 40 * r(), 0.12, 'saw', 0.03);
      mix(out, biquad(creak, 'bp', 600, 3), 1.2);
      // The arm swinging through: a falling whoosh.
      mix(out, decay(biquad(white(len, r), 'bp', (t) => 900 - t * 600, 1.5), 0.18, 0.12, 0.05), 0.9);
      // The beam slamming the stop.
      mix(out, tone(len, (t) => 60 + 40 * Math.exp(-t * 20), 0.2), 1.2, 0.32);
      mix(out, decay(biquad(white(len, r), 'lp', 600), 0.04), 0.9, 0.32);
      return finish(drive(out, 1.6), 0.85);
    }
    case 'railgun': {
      const len = n(1.0);
      const out = new Float32Array(len);
      // Capacitors whining up.
      const charge = tone(n(0.16), (t) => 300 + 9000 * t * t * 40, 99, 'saw', 0.05);
      for (let i = 0; i < charge.length; i++) charge[i]! *= i / charge.length;
      mix(out, biquad(charge, 'lp', 4000), 0.25);
      // The discharge: a hard electric crack and a metallic ring.
      mix(out, decay(biquad(white(len, r), 'hp', 2500), 0.03), 1.2, 0.16);
      mix(out, ring(len, 1180, 0.14, r), 0.35, 0.16);
      // Mains buzz of the coils, dying away.
      mix(out, decay(biquad(tone(len, () => 100, 99, 'saw'), 'lp', 1600), 0.18), 0.5, 0.16);
      // The slug's sonic boom far down range.
      mix(out, decay(biquad(white(len, r), 'lp', 400), 0.2, 0.01, 0.2), 0.8);
      return finish(drive(out, 2), 0.85);
    }
    case 'burst':
      return finish(explosion(r, 0.5), 0.9);
    case 'deathBig':
      return finish(explosion(r, 1.2), 0.95);
    case 'impact': {
      const len = n(0.22);
      const out = decay(biquad(white(len, r), 'lp', 1200), 0.025);
      mix(out, tone(len, (t) => 120 + 80 * Math.exp(-t * 40), 0.05), 0.6);
      mix(out, ring(len, 2200 + r() * 600, 0.03, r), 0.15);
      return finish(drive(out, 1.5), 0.45);
    }
    case 'deathSoft': {
      // A body hitting the dirt and gear rattling.
      const len = n(0.35);
      const out = decay(biquad(white(len, r), 'lp', 500), 0.05, 0.01);
      mix(out, decay(biquad(white(len, r), 'bp', 2400, 2), 0.04, 0.005, 0.06), 0.4);
      mix(out, tone(len, (t) => 80 + 60 * Math.exp(-t * 30), 0.06), 0.6);
      return finish(out, 0.45);
    }
    case 'deathVehicle': {
      const len = n(1.1);
      const out = explosion(r, 0.6);
      // Twisting steel.
      mix(out, ring(len, 320 + r() * 120, 0.35, r), 0.25, 0.05);
      mix(out, decay(biquad(white(len, r), 'bp', 1800, 4), 0.2, 0.01, 0.08), 0.5);
      return finish(out, 0.9);
    }
    case 'deathAir': {
      const len = n(1.2);
      const out = explosion(r, 0.4);
      // A gas bag going up: a soft whump and a falling tear.
      mix(out, tone(len, (t) => 70 + 50 * Math.exp(-t * 4), 0.4, 'sin', 0.05), 0.8);
      mix(out, decay(biquad(white(len, r), 'bp', (t) => 1500 - t * 1000, 2), 0.35, 0.05, 0.1), 0.5);
      return finish(out, 0.85);
    }
    case 'ram': {
      const len = n(0.5);
      const out = ring(len, 210 + r() * 40, 0.2, r);
      mix(out, decay(biquad(white(len, r), 'lp', 900), 0.05), 1.4);
      mix(out, tone(len, (t) => 70 + 50 * Math.exp(-t * 25), 0.1), 1);
      return finish(drive(out, 2), 0.75);
    }
    case 'wrecked': {
      const len = n(1.4);
      const out = explosion(r, 0.8);
      mix(out, ring(len, 260, 0.4, r), 0.2, 0.04);
      mix(out, biquad(crackle(len, r, 400, 0.5), 'bp', 1200, 1), 0.6, 0.1);
      return finish(out, 0.95);
    }
    case 'leak': {
      // A dull alarm bell: the enemy got through.
      const len = n(1.2);
      const out = ring(len, 392, 0.5, r);
      mix(out, ring(len, 392, 0.5, r), 0.6, 0.18);
      return finish(out, 0.55);
    }
    case 'click': {
      const len = n(0.07);
      const out = tone(len, () => 1700, 0.012);
      mix(out, decay(biquad(white(len, r), 'bp', 4000, 2), 0.004), 0.6);
      mix(out, tone(len, () => 420, 0.02), 0.4);
      return finish(out, 0.35);
    }
    case 'build': {
      // Two hammer blows on iron.
      const len = n(0.55);
      const out = new Float32Array(len);
      for (const at of [0, 0.17]) {
        mix(out, ring(n(0.35), 880 + r() * 60, 0.09, r), 0.5, at);
        mix(out, decay(biquad(white(n(0.1), r), 'lp', 2500), 0.01), 0.9, at);
      }
      return finish(drive(out, 1.4), 0.5);
    }
    case 'waveStart': {
      // A war horn over a drum.
      const out = horn([[110, 0, 0.9], [146.8, 0.55, 0.7]], 1.8, r, 1100);
      drum(0.6, r, 0, out, 1.4);
      drum(0.6, r, 0.55, out, 1.2);
      return finish(out, 0.7);
    }
    case 'waveClear':
      return finish(horn([[293.7, 0, 0.18], [440, 0.2, 0.45]], 1.0, r, 1800), 0.55);
    case 'won': {
      const out = horn([[293.7, 0, 0.2], [370, 0.22, 0.2], [440, 0.44, 0.2], [587.3, 0.66, 0.9]], 2.0, r, 2000);
      drum(0.6, r, 0, out);
      drum(0.6, r, 0.66, out, 1.3);
      return finish(out, 0.7);
    }
    case 'lost': {
      const out = horn([[220, 0, 0.5], [207.7, 0.5, 0.5], [146.8, 1.0, 1.2]], 2.6, r, 700);
      drum(0.8, r, 1.0, out, 1.5);
      return finish(out, 0.7);
    }
  }
}

// ---- music -----------------------------------------------------------------

export const MUSIC_BPM = 84;
const BEAT = 60 / MUSIC_BPM;
export const MUSIC_BARS = 16;

/** D minor: i – VI – III – VII, twice, then iv – VI – v – V. Roots in Hz (octave 2). */
const PROGRESSION = [73.42, 58.27, 87.31, 65.41, 73.42, 58.27, 87.31, 65.41, 98.0, 58.27, 110.0, 110.0, 73.42, 58.27, 65.41, 110.0];
/** Third above each root (minor or major as the chord wants). */
const THIRDS = [1.189, 1.26, 1.26, 1.26, 1.189, 1.26, 1.26, 1.26, 1.189, 1.26, 1.189, 1.26, 1.189, 1.26, 1.26, 1.26];
/** Melody: [bar, beat, semitones above D4, beats long]. Plays in the second half. */
const MELODY: Array<[number, number, number, number]> = [
  [8, 0, 0, 1.5], [8, 1.5, 3, 0.5], [8, 2, 5, 2],
  [9, 0, 3, 1], [9, 1, 1, 1], [9, 2, 0, 2],
  [10, 0, 7, 1.5], [10, 1.5, 5, 0.5], [10, 2, 3, 1], [10, 3, 5, 1],
  [11, 0, 4, 3],
  [12, 0, 0, 1.5], [12, 1.5, 3, 0.5], [12, 2, 7, 2],
  [13, 0, 8, 1], [13, 1, 7, 1], [13, 2, 5, 2],
  [14, 0, 3, 1.5], [14, 1.5, 2, 0.5], [14, 2, 0, 2],
  [15, 0, -1, 3],
];

/**
 * One bar of the march: low strings, a field drum and (later bars) a lone
 * brass line. Rendered bar by bar so the loop is built without stalling a frame.
 */
export function musicBar(bar: number): Float32Array {
  const r = rng(9001 + bar * 31);
  const len = n(BEAT * 4 + 1.0); // ring-out past the bar, mixed into the next
  const out = new Float32Array(len);
  const root = PROGRESSION[bar]!;
  // Strings pad: root, fifth, third an octave up; slow swell.
  for (const [f, g] of [[root, 0.5], [root * 1.5, 0.3], [root * 2 * THIRDS[bar]!, 0.22], [root * 2, 0.25]] as const) {
    for (const det of [0.996, 1.004]) {
      const pad = tone(len, () => f * det, 99, 'saw', 0.6);
      for (let i = 0; i < len; i++) {
        const t = i / SAMPLE_RATE;
        pad[i]! *= t < BEAT * 4 ? 1 : Math.exp(-(t - BEAT * 4) / 0.25);
      }
      mix(out, biquad(pad, 'lp', 520, 0.8), g * 0.5);
    }
  }
  // Field drum: a snare-like rattle on the off-beats, a big drum on 1 (and on 3 in the second half).
  for (let b = 0; b < 4; b++) {
    if (b === 0 || (b === 2 && bar >= 8)) drum(0.5, r, b * BEAT, out, 1.1);
    const roll = bar % 4 === 3 && b === 3;
    for (const sub of roll ? [0, 0.25, 0.5, 0.75] : [0.5]) {
      const l = n(0.18);
      const s = decay(biquad(white(l, r), 'bp', 2200, 0.8), 0.035);
      mix(s, tone(l, () => 190, 0.03), 0.4);
      mix(out, s, roll ? 0.25 + sub * 0.3 : 0.28, (b + sub) * BEAT);
    }
  }
  // Brass line.
  for (const [mb, beat, semi, dur] of MELODY) {
    if (mb !== bar) continue;
    const f = 293.66 * Math.pow(2, semi / 12);
    mix(out, horn([[f, 0, dur * BEAT * 0.92]], dur * BEAT + 0.4, r, 900), 0.18, beat * BEAT);
  }
  return out;
}

/** Length in samples of one bar (without its ring-out). */
export const MUSIC_BAR_SAMPLES = n(BEAT * 4);

/** The whole march as one seamless loop: each bar's ring-out wraps into the next (the last into the first). */
export function renderMusic(): Float32Array {
  const total = MUSIC_BAR_SAMPLES * MUSIC_BARS;
  const data = new Float32Array(total);
  for (let bar = 0; bar < MUSIC_BARS; bar++) {
    const b = musicBar(bar);
    for (let i = 0; i < b.length; i++) data[(bar * MUSIC_BAR_SAMPLES + i) % total]! += b[i]!;
  }
  // Scale only: fades at the ends would dip at every turn of the loop.
  let peak = 0;
  for (let i = 0; i < total; i++) peak = Math.max(peak, Math.abs(data[i]!));
  if (peak > 0) for (let i = 0; i < total; i++) data[i]! *= 0.8 / peak;
  return data;
}
