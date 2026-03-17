/**
 * Synthesized UI sound engine — Web Audio API, no external files.
 * All sounds are programmatically generated to match the Matrix/terminal aesthetic.
 *
 * Sounds:
 *   play("update")          → data-sync sweep (refreshing)
 *   play("scan")            → sonar radar ping (searching)
 *   play("analyze")         → neural ignition (3 synaptic bursts)
 *   play("execute")         → trade confirmed (decisive stamp)
 *   play("scanComplete")    → radar lock acquired (3 converging pings → chord)
 *   play("analyzeComplete") → AI awakening (ascending major arpeggio)
 */

let _ctx: AudioContext | null = null;

function ctx(): AudioContext {
  if (!_ctx) _ctx = new AudioContext();
  if (_ctx.state === "suspended") _ctx.resume();
  return _ctx;
}

/** Sine oscillator with ADSR envelope */
function tone(
  ac: AudioContext,
  freq: number,
  startT: number,
  duration: number,
  vol: number,
  type: OscillatorType = "sine",
  dest: AudioNode = ac.destination,
) {
  const osc = ac.createOscillator();
  const g = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, startT);
  g.gain.setValueAtTime(0, startT);
  g.gain.linearRampToValueAtTime(vol, startT + 0.008);
  g.gain.exponentialRampToValueAtTime(0.0001, startT + duration);
  osc.connect(g);
  g.connect(dest);
  osc.start(startT);
  osc.stop(startT + duration + 0.05);
}

/** Frequency sweep (chirp) */
function sweep(
  ac: AudioContext,
  freqStart: number,
  freqEnd: number,
  startT: number,
  duration: number,
  vol: number,
  type: OscillatorType = "sine",
) {
  const osc = ac.createOscillator();
  const g = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freqStart, startT);
  osc.frequency.exponentialRampToValueAtTime(freqEnd, startT + duration);
  g.gain.setValueAtTime(0, startT);
  g.gain.linearRampToValueAtTime(vol, startT + 0.006);
  g.gain.exponentialRampToValueAtTime(0.0001, startT + duration);
  osc.connect(g);
  g.connect(ac.destination);
  osc.start(startT);
  osc.stop(startT + duration + 0.05);
}

/** Filtered noise burst */
function noiseBurst(
  ac: AudioContext,
  startT: number,
  duration: number,
  vol: number,
  filterFreq: number,
) {
  const bufferSize = ac.sampleRate * duration;
  const buffer = ac.createBuffer(1, bufferSize, ac.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;

  const source = ac.createBufferSource();
  source.buffer = buffer;

  const filter = ac.createBiquadFilter();
  filter.type = "bandpass";
  filter.frequency.setValueAtTime(filterFreq, startT);
  filter.Q.setValueAtTime(1.5, startT);

  const g = ac.createGain();
  g.gain.setValueAtTime(0, startT);
  g.gain.linearRampToValueAtTime(vol, startT + 0.004);
  g.gain.exponentialRampToValueAtTime(0.0001, startT + duration);

  source.connect(filter);
  filter.connect(g);
  g.connect(ac.destination);
  source.start(startT);
  source.stop(startT + duration + 0.05);
}

// ─── Sound Definitions ────────────────────────────────────────────────────────

const sounds: Record<string, () => void> = {

  /** UPDATE — data sync: quick filtered noise rush + clean digital ping */
  update() {
    const ac = ctx();
    const t = ac.currentTime;
    // Noise rush (like data being pulled)
    noiseBurst(ac, t, 0.08, 0.18, 1200);
    noiseBurst(ac, t + 0.04, 0.06, 0.10, 2400);
    // Clean confirmation ping
    tone(ac, 880, t + 0.09, 0.18, 0.22, "sine");
    tone(ac, 1760, t + 0.12, 0.10, 0.08, "sine");
  },

  /** SCAN — sonar radar: deep thud + rising chirp with tail */
  scan() {
    const ac = ctx();
    const t = ac.currentTime;
    // Deep sonar thud
    tone(ac, 80, t, 0.12, 0.35, "sine");
    tone(ac, 55, t, 0.08, 0.25, "triangle");
    // Rising chirp
    sweep(ac, 220, 1400, t + 0.06, 0.35, 0.28, "sine");
    // Echo tail
    sweep(ac, 220, 1400, t + 0.22, 0.30, 0.10, "sine");
  },

  /** ANALYZE — neural ignition: 3 synaptic bursts firing in sequence */
  analyze() {
    const ac = ctx();
    const t = ac.currentTime;
    const freqs = [220, 330, 528];
    freqs.forEach((freq, i) => {
      const at = t + i * 0.085;
      tone(ac, freq, at, 0.18, 0.20, "sine");
      tone(ac, freq * 2, at + 0.01, 0.10, 0.07, "triangle");
      noiseBurst(ac, at, 0.04, 0.06, freq * 1.5);
    });
    // Final flourish
    tone(ac, 660, t + 0.28, 0.22, 0.14, "sine");
  },

  /** EXECUTE — trade confirmed: decisive low thud → sharp high confirmation */
  execute() {
    const ac = ctx();
    const t = ac.currentTime;
    // Power thud
    tone(ac, 100, t, 0.07, 0.55, "triangle");
    tone(ac, 60, t, 0.05, 0.40, "sine");
    noiseBurst(ac, t, 0.06, 0.22, 300);
    // Sharp confirmation ping (like a stamp)
    sweep(ac, 800, 1200, t + 0.06, 0.06, 0.35, "square");
    tone(ac, 1318, t + 0.10, 0.25, 0.28, "sine");
    tone(ac, 1760, t + 0.13, 0.18, 0.14, "sine");
  },

  /** SCAN COMPLETE — radar lock: 3 converging pings → sustained lock chord */
  scanComplete() {
    const ac = ctx();
    const t = ac.currentTime;
    // Three converging pings
    const pings = [600, 800, 1000];
    pings.forEach((freq, i) => {
      tone(ac, freq, t + i * 0.10, 0.20, 0.22, "sine");
    });
    // Lock chord — all three sustained simultaneously
    const lockT = t + 0.38;
    [600, 800, 1000, 1200].forEach(freq => {
      tone(ac, freq, lockT, 0.55, 0.12, "sine");
    });
    // Noise confirmation
    noiseBurst(ac, lockT, 0.05, 0.12, 900);
  },

  /** ANALYZE COMPLETE — AI awakening: ascending C major arpeggio → resolution */
  analyzeComplete() {
    const ac = ctx();
    const t = ac.currentTime;
    // Ascending arpeggio: C4 E4 G4 B4 C5
    const notes = [261.63, 329.63, 392.00, 493.88, 523.25];
    notes.forEach((freq, i) => {
      const at = t + i * 0.095;
      tone(ac, freq, at, 0.28, 0.18, "sine");
      tone(ac, freq * 2, at + 0.01, 0.14, 0.05, "sine");
    });
    // Resolution chord — full C major
    const resolveT = t + notes.length * 0.095 + 0.04;
    [261.63, 329.63, 392.00, 523.25].forEach(freq => {
      tone(ac, freq, resolveT, 0.6, 0.10, "sine");
    });
    // Shimmer
    tone(ac, 1046.5, resolveT, 0.4, 0.08, "sine");
  },
};

export function play(sound: keyof typeof sounds) {
  try {
    sounds[sound]?.();
  } catch (e) {
    // Audio not available (e.g., no user interaction yet) — fail silently
    console.debug("[sounds] playback skipped:", e);
  }
}
