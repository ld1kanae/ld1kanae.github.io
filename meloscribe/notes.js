export const PPQ = 480;
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

export function segmentNotes(rows, settings = {}) {
  const minDuration = settings.minDuration ?? .085;
  const voiced = rows.map(r => r.midi > 0 && r.confidence >= .72 && r.rms >= .003 ? Math.round(r.midi) : 0);
  const smoothed = voiced.slice();
  for (let i = 2; i < voiced.length - 2; i++) {
    const around = voiced.slice(i - 2, i + 3).filter(Boolean).sort((a, b) => a - b);
    if (around.length >= 3) {
      const median = around[Math.floor(around.length / 2)];
      if (!voiced[i] || Math.abs(voiced[i] - median) <= 2 || Math.abs(Math.abs(voiced[i] - median) - 12) <= 1)
        smoothed[i] = median;
    }
  }
  // One or two unvoiced frames in a sustained tone are usually breath/noise.
  for (let i = 1; i < smoothed.length - 2; i++) {
    if (!smoothed[i] && smoothed[i - 1]) {
      const end = smoothed[i + 1] ? i + 1 : i + 2;
      if (smoothed[end] === smoothed[i - 1]) for (let j = i; j < end; j++) smoothed[j] = smoothed[i - 1];
    }
  }
  const notes = [];
  const step = rows.length > 1 ? rows[1].time - rows[0].time : .02;
  let start = 0;
  for (let i = 1; i <= smoothed.length; i++) {
    if (i < smoothed.length && smoothed[i] === smoothed[start]) continue;
    if (smoothed[start] && (i - start) * step >= minDuration) {
      const source = rows.slice(start, i).filter(r => r.midi > 0);
      const sorted = source.map(r => r.midi).sort((a, b) => a - b);
      const pitch = sorted.length ? Math.round(sorted[Math.floor(sorted.length / 2)]) : smoothed[start];
      const confidence = source.reduce((s, r) => s + r.confidence, 0) / Math.max(1, source.length);
      notes.push({start: Math.max(0, rows[start].time - step / 2), end: rows[i - 1].time + step / 2,
        pitch: clamp(pitch, 0, 127), confidence, velocity: 90});
    }
    start = i;
  }
  return notes;
}

export function quantizeNotes(notes, bpm, phase, subdivision = 4) {
  const beat = 60 / bpm, quantum = beat / subdivision;
  const snap = t => phase + Math.round((t - phase) / quantum) * quantum;
  return notes.map(n => {
    const start = Math.max(0, snap(n.start));
    const end = Math.max(start + quantum, snap(n.end));
    return {...n, start, end};
  }).sort((a, b) => a.start - b.start);
}

function u32(n) {return [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255];}
function vlq(n) {
  n = Math.max(0, Math.round(n)); const out = [n & 127];
  while ((n = Math.floor(n / 128))) out.unshift((n & 127) | 128);
  return out;
}

export function midiFile(notes, bpm, phase = 0, subdivision = 4) {
  if (!(bpm >= 30 && bpm <= 300)) throw new Error('BPMは30〜300で指定してください。');
  const beat = 60 / bpm, us = Math.round(60000000 / bpm);
  const initial = [], packets = [];
  for (const note of notes) {
    const start = Math.round((note.start - phase) / beat * PPQ / (PPQ / subdivision)) * (PPQ / subdivision);
    const end = Math.round((note.end - phase) / beat * PPQ / (PPQ / subdivision)) * (PPQ / subdivision);
    initial.push({start, end, pitch: clamp(Math.round(note.pitch), 0, 127), velocity: clamp(Math.round(note.velocity || 90), 1, 127)});
  }
  const minTick = Math.min(0, ...initial.map(n => n.start));
  const pad = minTick < 0 ? Math.ceil(-minTick / (4 * PPQ)) * 4 * PPQ : 0;
  for (const note of initial) {
    const start = note.start + pad, end = Math.max(start + PPQ / subdivision, note.end + pad);
    packets.push({tick: start, order: 2, data: [0x90, note.pitch, note.velocity]});
    packets.push({tick: end, order: 1, data: [0x80, note.pitch, 0]});
  }
  packets.push({tick: 0, order: 0, data: [255, 81, 3, (us >> 16) & 255, (us >> 8) & 255, us & 255]});
  packets.push({tick: 0, order: 0, data: [255, 88, 4, 4, 2, 24, 8]});
  packets.sort((a, b) => a.tick - b.tick || a.order - b.order || a.data[1] - b.data[1]);
  const track = []; let previous = 0;
  for (const p of packets) {track.push(...vlq(p.tick - previous), ...p.data); previous = p.tick;}
  track.push(0, 255, 47, 0);
  return new Uint8Array([77, 84, 104, 100, ...u32(6), 0, 0, 0, 1, 1, 224,
    77, 84, 114, 107, ...u32(track.length), ...track]);
}
