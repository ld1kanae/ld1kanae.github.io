import {monoAt11025, estimateBeat} from './dsp.js';
import {segmentNotes, quantizeNotes, midiFile} from './notes.js?v=20260926-onsets-v2';
import {notesFromOnsets, suggestKeys} from './onsets.js?v=20260926-onsets-v2';

const $ = id => document.getElementById(id);
const state = {raw: [], notes: [], duration: 0, bpm: 120, phase: 0, view: 0, worker: null, audio: null, url: null};
const canvas = $('roll'), ctx = canvas.getContext('2d');
const span = 12, low = 45, high = 84, keyHeight = 12;
const fmt = t => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
const sub = () => Number($('subdivision').value);
const bpm = () => Number($('bpm').value);
const phase = () => Number($('phase').value);

for (const id of ['vocal', 'inst', 'mix']) $(id).addEventListener('change', () => {
  $(id + 'Name').textContent = $(id).files[0]?.name || 'ファイルを選ぶ';
});

function resize() {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(canvas.clientWidth * dpr); canvas.height = Math.round(canvas.clientHeight * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); draw();
}
const width = () => canvas.clientWidth;
const xAt = t => (t - state.view) / span * width();
const timeAt = x => state.view + x / width() * span;
const yAt = pitch => (high - pitch) * keyHeight + 10;
const pitchAt = y => Math.max(0, Math.min(127, high - Math.round((y - 10) / keyHeight)));

function draw() {
  const w = width(), h = canvas.clientHeight;
  ctx.clearRect(0, 0, w, h); ctx.fillStyle = '#101925'; ctx.fillRect(0, 0, w, h);
  for (let pitch = low; pitch <= high; pitch++) {
    const y = yAt(pitch), black = [1, 3, 6, 8, 10].includes(pitch % 12);
    if (black) {ctx.fillStyle = '#162433'; ctx.fillRect(0, y, w, keyHeight);}
    ctx.strokeStyle = pitch % 12 === 0 ? '#425c65' : '#263648'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, y + keyHeight); ctx.lineTo(w, y + keyHeight); ctx.stroke();
    if (pitch % 12 === 0) {ctx.fillStyle = '#78909a'; ctx.font = '11px sans-serif'; ctx.fillText(`C${Math.floor(pitch / 12) - 1}`, 6, y + 10);}
  }
  const beat = 60 / state.bpm, first = Math.floor((state.view - state.phase) / beat);
  for (let k = first; k < first + Math.ceil(span / beat) + 2; k++) {
    const t = state.phase + k * beat, x = xAt(t);
    if (x < 0 || x > w) continue;
    ctx.strokeStyle = k % 4 === 0 ? '#6a8577' : '#344a56'; ctx.lineWidth = k % 4 === 0 ? 1.5 : 1;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    if (k % 4 === 0) {ctx.fillStyle = '#b0c2b4'; ctx.font = '11px sans-serif'; ctx.fillText(`${Math.floor(k / 4) + 1}小節`, x + 4, 17);}
  }
  for (const note of state.notes) {
    const x = xAt(note.start), right = xAt(note.end), y = yAt(note.pitch);
    if (right < 0 || x > w || y < 0 || y > h) continue;
    ctx.fillStyle = note.confidence < .78 ? '#d7aa68' : '#cbf271';
    ctx.fillRect(x + 1, y + 1, Math.max(3, right - x - 2), keyHeight - 2);
    ctx.fillStyle = '#456441'; ctx.fillRect(right - 5, y + 2, 2, keyHeight - 4);
  }
  if (state.audio) {
    const x = xAt(state.audio.currentTime);
    if (x >= 0 && x <= w) {ctx.strokeStyle = '#ff7589'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();}
  }
}

function refresh() {
  $('download').disabled = !state.notes.length;
  $('stats').textContent = state.notes.length ? `${state.notes.length}音符 · ${state.bpm.toFixed(3)} BPM · ${state.duration.toFixed(1)}秒 · 低信頼の音符はオレンジ` : '音符は検出されませんでした。';
  draw();
}

async function decode(file, context) {return context.decodeAudioData(await file.arrayBuffer());}

$('analyze').addEventListener('click', async () => {
  const vocalFile = $('vocal').files[0], instFile = $('inst').files[0], mixFile = $('mix').files[0];
  if (!vocalFile && !(mixFile && instFile)) {$('status').textContent = 'ボーカル、または原曲＋インストを選んでください。'; return;}
  $('analyze').disabled = true; $('download').disabled = true;
  if (state.worker) state.worker.terminate();
  const context = new AudioContext();
  try {
    $('status').textContent = '音源を読み込み中…';
    const vocalBuffer = vocalFile ? await decode(vocalFile, context) : null;
    const instBuffer = instFile ? await decode(instFile, context) : null;
    const mixBuffer = !vocalBuffer && mixFile ? await decode(mixFile, context) : null;
    let vocal = vocalBuffer ? monoAt11025(vocalBuffer) : null;
    if (!vocal && mixBuffer && instBuffer) {
      if (Math.abs(mixBuffer.duration - instBuffer.duration) > .03) throw new Error('原曲とインストの長さが異なります。同じ位置のステムを使ってください。');
      const mix = monoAt11025(mixBuffer), inst = monoAt11025(instBuffer);
      vocal = Float32Array.from(mix, (v, i) => v - (inst[i] || 0));
    }
    state.duration = vocal.length / 11025;
    if (instBuffer) {
      $('status').textContent = '伴奏から拍を推定中…';
      try {
        const result = estimateBeat(monoAt11025(instBuffer));
        state.bpm = result.bpm; state.phase = result.phase;
        $('bpm').value = result.bpm; $('phase').value = result.phase.toFixed(4);
        $('beatInfo').textContent = `推定 ${result.bpm.toFixed(3)} BPM · 拍位置 ${result.phase.toFixed(3)}秒 · 拍の周期性 ${result.confidence.toFixed(2)}。70/140など半拍・倍拍の解釈は耳で確認してください。`;
      } catch (err) {$('beatInfo').textContent = err.message;}
    } else {state.bpm = bpm(); state.phase = phase();}
    const playback = mixFile || vocalFile;
    if (state.url) URL.revokeObjectURL(state.url);
    state.url = playback ? URL.createObjectURL(playback) : null;
    if (state.audio) state.audio.pause();
    state.audio = state.url ? new Audio(state.url) : null;
    $('scroll').max = Math.max(0, Math.round((state.duration - span) * 10)); $('scroll').value = 0; state.view = 0;
    $('status').textContent = '歌声の音高を解析中…';
    state.worker = new Worker('./pitch-worker.js?v=20260926-onsets-v2', {type: 'module'});
    state.worker.onmessage = ({data}) => {
      if (data.rows) {
        const onsetNotes = notesFromOnsets(data.rows, data.onsets || []);
        state.raw = onsetNotes.length >= 10 ? onsetNotes : segmentNotes(data.rows);
        state.notes = quantizeNotes(state.raw, state.bpm, state.phase, sub());
        state.view = Math.max(0, Math.min(state.duration - span, (state.notes[0]?.start || 0) - 2));
        $('scroll').value = Math.round(state.view * 10);
        const keys = suggestKeys(state.raw);
        $('keyInfo').textContent = keys.length ? `音高分布からのキー候補：${keys.slice(0, 2).map(x => x.name).join(' / ')}（調性の断定ではありません。臨時記号を消す処理には使用しません）` : '';
        $('status').textContent = `完了：${state.notes.length}音符。ピアノロールで確認してください。`;
        $('analyze').disabled = false; state.worker.terminate(); state.worker = null; refresh();
      } else $('status').textContent = `歌声の音高を解析中… ${Math.round(data.progress * 100)}%`;
    };
    state.worker.onerror = error => { $('status').textContent = `解析に失敗しました：${error.message}`; $('analyze').disabled = false; state.worker = null; };
    state.worker.postMessage({samples: vocal.buffer}, [vocal.buffer]);
  } catch (error) { $('status').textContent = `読み込みに失敗しました：${error.message}`; $('analyze').disabled = false; }
  finally {await context.close();}
});

$('requantize').addEventListener('click', () => {
  if (!(bpm() >= 30 && bpm() <= 300) || !Number.isFinite(phase())) {$('status').textContent = 'BPMと拍位置を確認してください。'; return;}
  state.bpm = bpm(); state.phase = phase();
  state.notes = quantizeNotes(state.raw, state.bpm, state.phase, sub()); refresh();
});
$('download').addEventListener('click', () => {
  try {
    const data = midiFile(state.notes, state.bpm, state.phase, sub());
    const url = URL.createObjectURL(new Blob([data], {type: 'audio/midi'}));
    const link = document.createElement('a'); link.href = url; link.download = 'meloscribe-melody.mid'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  } catch (error) {$('status').textContent = error.message;}
});
$('play').addEventListener('click', async () => {
  if (!state.audio) return;
  if (state.audio.paused) {await state.audio.play(); $('play').textContent = 'Ⅱ 一時停止';}
  else {state.audio.pause(); $('play').textContent = '▶ 再生';}
});
$('seek').addEventListener('input', () => {if (state.audio) state.audio.currentTime = state.duration * Number($('seek').value) / 1000;});
$('scroll').addEventListener('input', () => {state.view = Number($('scroll').value) / 10; draw();});

let drag = null;
function pointer(event) {const rect = canvas.getBoundingClientRect(); return {x: event.clientX - rect.left, y: event.clientY - rect.top};}
function hit(pos) {
  for (let i = state.notes.length - 1; i >= 0; i--) {
    const n = state.notes[i], y = yAt(n.pitch);
    if (pos.y >= y && pos.y <= y + keyHeight && pos.x >= xAt(n.start) - 3 && pos.x <= xAt(n.end) + 3) return i;
  }
  return -1;
}
canvas.addEventListener('contextmenu', event => event.preventDefault());
canvas.addEventListener('pointerdown', event => {
  if (!state.duration) return;
  const pos = pointer(event), index = hit(pos);
  if (index >= 0 && (event.shiftKey || event.button === 2)) {state.notes.splice(index, 1); refresh(); return;}
  if (event.button !== 0) return;
  const step = 60 / state.bpm / sub();
  if (index < 0) {
    const t = state.phase + Math.round((timeAt(pos.x) - state.phase) / step) * step;
    state.notes.push({start: Math.max(0, t), end: Math.max(0, t) + step, pitch: pitchAt(pos.y), confidence: 1, velocity: 90});
    drag = {index: state.notes.length - 1, mode: 'end', x: pos.x, original: {...state.notes.at(-1)}};
  } else {
    const n = state.notes[index]; const mode = Math.abs(pos.x - xAt(n.end)) < 9 ? 'end' : Math.abs(pos.x - xAt(n.start)) < 9 ? 'start' : 'move';
    drag = {index, mode, x: pos.x, y: pos.y, original: {...n}};
  }
  canvas.setPointerCapture(event.pointerId); refresh();
});
canvas.addEventListener('pointermove', event => {
  if (!drag) return;
  const pos = pointer(event), n = state.notes[drag.index], o = drag.original;
  const step = 60 / state.bpm / sub(), delta = Math.round((pos.x - drag.x) / width() * span / step) * step;
  if (drag.mode === 'move') {
    n.start = Math.max(0, o.start + delta); n.end = n.start + (o.end - o.start);
    n.pitch = Math.max(0, Math.min(127, o.pitch - Math.round((pos.y - drag.y) / keyHeight)));
  } else if (drag.mode === 'start') n.start = Math.max(0, Math.min(o.end - step, o.start + delta));
  else n.end = Math.max(n.start + step, o.end + delta);
  draw();
});
canvas.addEventListener('pointerup', () => {drag = null; state.notes.sort((a, b) => a.start - b.start); refresh();});
setInterval(() => {
  if (!state.audio) return;
  $('clock').textContent = `${fmt(state.audio.currentTime)} / ${fmt(state.duration)}`;
  $('seek').value = Math.round(1000 * state.audio.currentTime / state.duration);
  if (state.audio.ended) $('play').textContent = '▶ 再生';
  draw();
}, 100);
window.addEventListener('resize', resize); resize();
