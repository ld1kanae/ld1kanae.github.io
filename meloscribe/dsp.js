export function fft(re, im, inverse = false) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      [re[i], re[j]] = [re[j], re[i]];
      [im[i], im[j]] = [im[j], im[i]];
    }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const angle = (inverse ? 2 : -2) * Math.PI / len;
    const wr0 = Math.cos(angle), wi0 = Math.sin(angle);
    for (let i = 0; i < n; i += len) {
      let wr = 1, wi = 0;
      for (let j = 0; j < len / 2; j++) {
        const a = i + j, b = a + len / 2;
        const tr = wr * re[b] - wi * im[b], ti = wr * im[b] + wi * re[b];
        re[b] = re[a] - tr; im[b] = im[a] - ti;
        re[a] += tr; im[a] += ti;
        const next = wr * wr0 - wi * wi0;
        wi = wr * wi0 + wi * wr0; wr = next;
      }
    }
  }
  if (inverse) for (let i = 0; i < n; i++) { re[i] /= n; im[i] /= n; }
}

export function monoAt11025(buffer) {
  const rate = 11025, count = Math.ceil(buffer.duration * rate);
  const output = new Float32Array(count), channels = [];
  for (let c = 0; c < buffer.numberOfChannels; c++) channels.push(buffer.getChannelData(c));
  const ratio = buffer.sampleRate / rate;
  for (let i = 0; i < count; i++) {
    const start = Math.floor(i * ratio), end = Math.min(buffer.length, Math.max(start + 1, Math.floor((i + 1) * ratio)));
    let sum = 0;
    for (let j = start; j < end; j++) for (const ch of channels) sum += ch[j];
    output[i] = sum / ((end - start) * channels.length);
  }
  return output;
}

function percentile(values, q) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(q * (sorted.length - 1)))];
}

function peaks(values, hop) {
  const threshold = percentile(values, .78), candidates = [];
  for (let i = 2; i < values.length - 2; i++) {
    if (values[i] > threshold && values[i] > values[i - 1] && values[i] >= values[i + 1] &&
        values[i] - Math.min(values[i - 2], values[i + 2]) > .05) candidates.push(i);
  }
  candidates.sort((a, b) => values[b] - values[a]);
  const kept = [];
  for (const p of candidates) {
    if (kept.every(x => Math.abs(x - p) >= 5)) kept.push(p);
    if (kept.length >= 1200) break;
  }
  return kept.map(i => ({time: i * hop / 11025, weight: Math.max(.001, values[i])}));
}

export function estimateBeat(instrumental) {
  const n = 1024, hop = 220, frameCount = Math.ceil(instrumental.length / hop);
  const low = new Float32Array(frameCount), mid = new Float32Array(frameCount);
  const re = new Float64Array(n), im = new Float64Array(n);
  let prevLow = new Float64Array(10), prevMid = new Float64Array(71);
  for (let frame = 0; frame < frameCount; frame++) {
    const pos = frame * hop - n / 2;
    for (let i = 0; i < n; i++) {
      re[i] = (instrumental[pos + i] || 0) * (.5 - .5 * Math.cos(2 * Math.PI * i / (n - 1)));
      im[i] = 0;
    }
    fft(re, im);
    let lo = 0, mi = 0;
    for (let k = 3; k <= 83; k++) {
      const mag = Math.log1p(100 * Math.hypot(re[k], im[k]) / n);
      if (k <= 12) {lo += Math.max(0, mag - prevLow[k - 3]); prevLow[k - 3] = mag;}
      else {mi += Math.max(0, mag - prevMid[k - 13]); prevMid[k - 13] = mag;}
    }
    low[frame] = lo / 10; mid[frame] = mi / 71;
  }
  const normalized = signal => {
    const median = percentile(signal, .5), scale = Math.max(1e-8, percentile(signal, .95) - median);
    return Float32Array.from(signal, x => (x - median) / scale);
  };
  const lp = peaks(normalized(low), hop), mp = peaks(normalized(mid), hop);
  if (lp.length < 12 || mp.length < 12) throw new Error('拍の手がかりが足りません。BPMを手入力してください。');
  function coherence(events, bpm) {
    let real = 0, imag = 0, weight = 0;
    for (const e of events) {
      const a = 2 * Math.PI * bpm / 60 * e.time;
      real += e.weight * Math.cos(a); imag += e.weight * Math.sin(a); weight += e.weight;
    }
    return Math.hypot(real, imag) / weight;
  }
  let best = {bpm: 120, score: -1};
  for (let b = 60; b <= 220.001; b += .1) {
    const score = .68 * coherence(mp, b) + .32 * coherence(lp, b);
    if (score > best.score) best = {bpm: b, score};
  }
  for (let b = best.bpm - .12; b <= best.bpm + .12; b += .005) {
    const score = .68 * coherence(mp, b) + .32 * coherence(lp, b);
    if (score > best.score) best = {bpm: b, score};
  }
  let real = 0, imag = 0;
  for (const e of mp) {
    const a = 2 * Math.PI * best.bpm / 60 * e.time;
    real += e.weight * Math.cos(a); imag += e.weight * Math.sin(a);
  }
  const beat = 60 / best.bpm;
  let phase = Math.atan2(imag, real) / (2 * Math.PI) * beat;
  if (phase >= beat / 2) phase -= beat;
  if (phase < -beat / 2) phase += beat;
  return {bpm: Math.round(best.bpm * 1000) / 1000, phase, confidence: best.score,
    alternatives: [best.bpm / 2, best.bpm * 2].filter(b => b >= 30 && b <= 300)};
}
