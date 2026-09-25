import {fft} from './dsp.js';
import {detectVocalOnsets} from './onsets.js';

// Autocorrelation formulation of YIN's cumulative mean normalized difference.
const RATE = 11025, SIZE = 2048, FFT_SIZE = 4096, HOP = 220;
const MIN_LAG = 12, MAX_LAG = 185;

self.onmessage = async ({data}) => {
  const samples = new Float32Array(data.samples);
  const onsets = detectVocalOnsets(samples);
  const rows = [];
  const re = new Float64Array(FFT_SIZE), im = new Float64Array(FFT_SIZE);
  const prefix = new Float64Array(SIZE), diff = new Float64Array(MAX_LAG + 1);
  const total = Math.ceil(samples.length / HOP);
  for (let frame = 0; frame < total; frame++) {
    const center = frame * HOP, start = center - SIZE / 2;
    let avg = 0;
    for (let i = 0; i < SIZE; i++) avg += samples[start + i] || 0;
    avg /= SIZE;
    let sum = 0;
    for (let i = 0; i < SIZE; i++) {
      const v = (samples[start + i] || 0) - avg;
      re[i] = v; im[i] = 0; sum += v * v; prefix[i] = sum;
    }
    re.fill(0, SIZE); im.fill(0, SIZE);
    const rms = Math.sqrt(sum / SIZE);
    if (rms < .0015) {rows.push({time: center / RATE, midi: 0, confidence: 0, rms}); continue;}
    fft(re, im);
    for (let i = 0; i < FFT_SIZE; i++) {const p = re[i] * re[i] + im[i] * im[i]; re[i] = p; im[i] = 0;}
    fft(re, im, true);
    let cumulative = 0, bestLag = MIN_LAG, best = 1, first = 0;
    for (let lag = 1; lag <= MAX_LAG; lag++) {
      const d = Math.max(0, prefix[SIZE - lag - 1] + sum - prefix[lag - 1] - 2 * re[lag]);
      cumulative += d;
      diff[lag] = d / Math.max(1e-10, cumulative / lag);
    }
    for (let lag = MIN_LAG; lag < MAX_LAG; lag++) {
      const value = diff[lag];
      if (value < best) {best = value; bestLag = lag;}
      if (!first && value < .18 && value <= diff[lag - 1] && value <= diff[lag + 1]) first = lag;
    }
    const lag = first || bestLag;
    const a = diff[lag - 1], b = diff[lag], c = diff[lag + 1];
    const sub = Math.abs(a - 2 * b + c) > 1e-9 ? Math.max(-.5, Math.min(.5, .5 * (a - c) / (a - 2 * b + c))) : 0;
    const confidence = Math.max(0, 1 - b);
    const midi = confidence >= .72 && rms >= .003 ? 69 + 12 * Math.log2(RATE / (lag + sub) / 440) : 0;
    rows.push({time: center / RATE, midi, confidence, rms});
    if (frame % 200 === 0) {self.postMessage({progress: frame / total}); await new Promise(resolve => setTimeout(resolve, 0));}
  }
  self.postMessage({rows, onsets, progress: 1});
};
