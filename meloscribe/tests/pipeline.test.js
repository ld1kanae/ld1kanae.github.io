import test from 'node:test';
import assert from 'node:assert/strict';
import {segmentNotes, quantizeNotes, midiFile} from '../notes.js';
import {fft} from '../dsp.js';
import {notesFromOnsets} from '../onsets.js';

test('FFT round trip preserves waveform', () => {
  const re = Float64Array.from({length: 32}, (_, i) => Math.sin(i * .8));
  const original = [...re], im = new Float64Array(32);
  fft(re, im); fft(re, im, true);
  assert.ok(re.every((x, i) => Math.abs(x - original[i]) < 1e-10));
});

test('pitch worker follows two known tones and silence', async () => {
  const sampleRate = 11025, samples = new Float32Array(sampleRate * 2);
  for (let i = 0; i < samples.length; i++) {
    const time = i / sampleRate;
    const hz = time < 1 ? 220 : 329.6276;
    samples[i] = .2 * Math.sin(2 * Math.PI * hz * time);
  }
  const prior = globalThis.self;
  let finish;
  const result = new Promise(resolve => finish = resolve);
  globalThis.self = {postMessage(data) {if (data.rows) finish(data.rows);}};
  try {
    await import('../pitch-worker.js');
    await self.onmessage({data: {samples: samples.buffer}});
    const rows = await result;
    const median = array => array.sort((a, b) => a - b)[Math.floor(array.length / 2)];
    assert.ok(Math.abs(median(rows.filter(r => r.time > .2 && r.time < .8).map(r => r.midi)) - 57) < .25);
    assert.ok(Math.abs(median(rows.filter(r => r.time > 1.2 && r.time < 1.8).map(r => r.midi)) - 64) < .25);
  } finally {globalThis.self = prior;}
});

test('note starts and ends land on the requested beat grid in MIDI', () => {
  const rows = Array.from({length: 40}, (_, i) => ({time: i * .02, midi: i < 5 || i >= 25 ? 0 : 60,
    confidence: .95, rms: .1}));
  const notes = segmentNotes(rows);
  assert.equal(notes.length, 1);
  const quantized = quantizeNotes(notes, 120, 0, 4);
  assert.equal(quantized[0].start, .125);
  assert.equal(quantized[0].end, .5);
  const midi = midiFile(quantized, 120, 0, 4);
  assert.equal(new TextDecoder().decode(midi.subarray(0, 4)), 'MThd');
  assert.ok(midi.includes(0x90));
  assert.ok(midi.includes(0x80));
});

test('separate vocal attacks retain repeated notes at the same pitch', () => {
  const rows = Array.from({length: 50}, (_, i) => ({time: i * .02,
    midi: i >= 8 && i < 40 ? 62 : 0, confidence: .94, rms: .1}));
  const notes = notesFromOnsets(rows, [{time: .16, strength: 2}, {time: .42, strength: 2}]);
  assert.equal(notes.length, 2);
  assert.equal(notes[0].pitch, 62);
  assert.equal(notes[1].pitch, 62);
  assert.ok(notes[0].end <= notes[1].start);
});
