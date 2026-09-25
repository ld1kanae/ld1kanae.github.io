import {fft} from './dsp.js';

const RATE = 11025, N = 512, HOP = 110;

function percentile(values, q) {
  const a = [...values].sort((x, y) => x - y);
  return a[Math.min(a.length - 1, Math.floor(q * (a.length - 1)))] || 0;
}

export function detectVocalOnsets(samples) {
  const size = Math.ceil(samples.length / HOP), flux = new Float32Array(size);
  const re = new Float64Array(N), im = new Float64Array(N), prev = new Float64Array(163);
  for (let frame = 0; frame < size; frame++) {
    const origin = frame * HOP - N / 2;
    for (let j = 0; j < N; j++) {
      re[j] = (samples[origin + j] || 0) * (.5 - .5 * Math.cos(2 * Math.PI * j / (N - 1)));
      im[j] = 0;
    }
    fft(re, im);
    let lo = 0, hi = 0;
    for (let k = 5; k < 163; k++) {
      const m = Math.log1p(200 * Math.hypot(re[k], im[k]) / (N / 2));
      const delta = Math.max(0, m - prev[k]); prev[k] = m;
      if (k < 24) lo += delta;
      else hi += delta;
    }
    flux[frame] = lo / 19 + 1.5 * hi / 139;
  }
  const median = percentile(flux, .5), scale = Math.max(1e-8, percentile(flux, .95) - median);
  const normalized = Float32Array.from(flux, x => (x - median) / scale);
  const candidates = [];
  for (let i = 2; i < size - 2; i++) {
    const s = normalized[i];
    if (s < .4 || s <= normalized[i - 1] || s < normalized[i + 1] ||
        s - Math.min(normalized[i - 2], normalized[i + 2]) < .25) continue;
    candidates.push({time: i * HOP / RATE, strength: s});
  }
  candidates.sort((a, b) => b.strength - a.strength);
  const selected = [];
  for (const p of candidates) if (selected.every(x => Math.abs(x.time - p.time) >= .075)) selected.push(p);
  return selected.sort((a, b) => a.time - b.time);
}

function medianPitch(rows, start, end) {
  const valid = rows.filter(r => r.time >= start && r.time <= end && r.midi > 0 && r.confidence >= .75);
  if (valid.length < 3) return null;
  const values = valid.map(r => r.midi).sort((a, b) => a - b);
  const pitch = Math.round(values[Math.floor(values.length / 2)]);
  const support = valid.filter(r => Math.abs(r.midi - pitch) < .8);
  if (support.length < 3) return null;
  return {pitch, support: support.length, confidence: support.reduce((a, r) => a + r.confidence, 0) / support.length};
}

export function notesFromOnsets(rows, onsets) {
  const viable = [];
  for (let i = 0; i < onsets.length; i++) {
    const onset = onsets[i];
    const nextPeak = onsets[i + 1]?.time ?? Infinity;
    const early = medianPitch(rows, onset.time + .015, Math.min(onset.time + .22, nextPeak - .012));
    if (!early) continue;
    // Short phoneme noise may have a periodic tail from the previous note.
    const prior = medianPitch(rows, onset.time - .10, onset.time - .025);
    if (prior?.pitch === early.pitch && onset.strength < .75 &&
        viable.length && onset.time - viable.at(-1).start < .22) continue;
    viable.push({start: onset.time, pitch: early.pitch, confidence: early.confidence,
      strength: onset.strength, velocity: 90});
  }
  const notes = [];
  for (let i = 0; i < viable.length; i++) {
    const n = viable[i], next = viable[i + 1]?.start ?? Infinity;
    const cap = Math.min(n.start + 1.4, next);
    let last = n.start + .08, gaps = 0;
    for (const row of rows) {
      if (row.time < n.start + .04) continue;
      if (row.time > cap) break;
      if (row.midi > 0 && Math.abs(row.midi - n.pitch) < 1.15 && row.confidence >= .7) {
        last = row.time; gaps = 0;
      } else if (++gaps > 8 && row.time > last + .08) break;
    }
    const end = Math.max(n.start + .09, Math.min(next - .005, last + .025));
    if (end - n.start < .08) continue;
    notes.push({start: n.start, end, pitch: n.pitch, confidence: n.confidence, velocity: n.velocity});
  }
  return notes;
}

// Display-only estimate. Relative major and minor keys share pitch classes;
// the strongest profile is not treated as a hard constraint on notes.
export function suggestKeys(notes) {
  const hist = Array(12).fill(0);
  for (const n of notes) hist[n.pitch % 12] += Math.min(.8, n.end - n.start) * n.confidence;
  const profiles = {major: [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88],
    minor: [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]};
  const names = ['C','C♯','D','E♭','E','F','F♯','G','A♭','A','B♭','B'];
  const results = [];
  for (let tonic = 0; tonic < 12; tonic++) for (const [mode, profile] of Object.entries(profiles)) {
    let score = 0, aa = 0, bb = 0;
    const hmean = hist.reduce((a, b) => a + b, 0) / 12;
    const pmean = profile.reduce((a, b) => a + b, 0) / 12;
    for (let k = 0; k < 12; k++) {
      const a = hist[(tonic + k) % 12] - hmean, b = profile[k] - pmean;
      score += a * b; aa += a * a; bb += b * b;
    }
    results.push({name: `${names[tonic]} ${mode}`, score: score / Math.sqrt(aa * bb || 1)});
  }
  return results.sort((a, b) => b.score - a.score).slice(0, 3);
}
