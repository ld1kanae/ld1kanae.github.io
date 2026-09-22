import json, math
from pathlib import Path
import mido

ROOT=Path('.')
SONG='arcaround'
folder=ROOT/'DruMaster/songs'/SONG
meta=json.loads((folder/'song.json').read_text())
side=json.loads((ROOT/'drumscribe/experiments/generated-v2-browser'/f'{SONG}.json').read_text())
mid=mido.MidiFile(folder/'chart.mid')
tpq=mid.ticks_per_beat

# collect tempo/time-signature changes in absolute ticks
tempo_events=[(0,500000)]
sig_events=[(0,4,4)]
abs_tick=0
for track in mid.tracks:
    t=0
    for msg in track:
        t+=msg.time
        if msg.type=='set_tempo':
            tempo_events.append((t,msg.tempo))
        elif msg.type=='time_signature':
            sig_events.append((t,msg.numerator,msg.denominator))
# de-duplicate by tick, last event wins
te={}
for t,v in tempo_events: te[t]=v
tempo_events=sorted(te.items())
se={}
for t,n,d in sig_events: se[t]=(n,d)
sig_events=sorted((t,*v) for t,v in se.items())

# tick->seconds using tempo map
segments=[]
sec=0.0
prev_tick=0
tempo=500000
for t,newtempo in tempo_events:
    if t<prev_tick: continue
    sec+=(t-prev_tick)*tempo/1e6/tpq
    segments.append((t,sec,newtempo))
    prev_tick=t
    tempo=newtempo
if not segments or segments[0][0]!=0:
    segments.insert(0,(0,0.0,500000))

def tick_to_sec(tick):
    seg=segments[0]
    for s in segments[1:]:
        if s[0]>tick: break
        seg=s
    st,ss,temp=seg
    return ss+(tick-st)*temp/1e6/tpq

# Build bar boundaries from time-signature map. All current songs are expected 4/4,
# but do not assume it when creating the reference.
last_tick=max(sum(m.time for m in tr) for tr in mid.tracks)
bar_ticks=[]
idx=0
while idx < len(sig_events):
    start_tick,n,d=sig_events[idx]
    end_tick=sig_events[idx+1][0] if idx+1<len(sig_events) else last_tick+tpq*16
    ticks_per_bar=tpq*n*4/d
    t=float(start_tick)
    while t<=end_tick+1e-9:
        bar_ticks.append(t)
        t+=ticks_per_bar
    idx+=1
bar_ticks=sorted(set(int(round(x)) for x in bar_ticks))

shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
duration=float(meta['duration'])
ref_bars=[]
for tick in bar_ticks:
    t=tick_to_sec(tick)+shift
    if 0<=t<=duration:
        # local quarter-note length at this tick
        seg=segments[0]
        for s in segments[1:]:
            if s[0]>tick: break
            seg=s
        beat=seg[2]/1e6
        ref_bars.append((t,beat,tick))

pred_bpm=float(side['bpm'])
pred_beat=60/pred_bpm
pred_bar=float(side.get('barSec') or pred_beat*4)
phase=float(side['barPhaseSec'])
# produce predicted bar heads spanning song
k0=math.floor((0-phase)/pred_bar)-2
k1=math.ceil((duration-phase)/pred_bar)+2
pred=[phase+k*pred_bar for k in range(k0,k1+1)]

def nearest(x):
    y=min(pred,key=lambda p:abs(p-x))
    return y,y-x

rows=[]
for t,beat,tick in ref_bars:
    y,e=nearest(t)
    rows.append({'ref':t,'pred':y,'err_sec':e,'err_beats':e/beat,'tick':tick})

# fixed-BPM phase alias used by old evaluator
truth_bpm=float(meta['bpm'])
truth_beat=60/truth_bpm
truth_bar=truth_beat*4
old_ref_phase=shift%truth_bar
old_err=min(abs((phase-old_ref_phase)%truth_bar),truth_bar-abs((phase-old_ref_phase)%truth_bar))/truth_beat

chunks={}
N=len(rows)
for name,a,b in [('head',0,min(16,N)),('middle',max(0,N//2-8),min(N,N//2+8)),('tail',max(0,N-16),N)]:
    z=rows[a:b]
    chunks[name]={
      'count':len(z),
      'mean_abs_beats':sum(abs(r['err_beats']) for r in z)/len(z) if z else None,
      'max_abs_beats':max((abs(r['err_beats']) for r in z),default=None),
      'first':z[0] if z else None,
      'last':z[-1] if z else None,
    }

vals=[abs(r['err_beats']) for r in rows]
out={
 'song':SONG,
 'song_json_bpm':truth_bpm,
 'generated_bpm':pred_bpm,
 'tempo_event_count':len(tempo_events),
 'tempo_bpms':[round(60_000_000/us,6) for _,us in tempo_events],
 'tempo_bpm_min':min(60_000_000/us for _,us in tempo_events),
 'tempo_bpm_max':max(60_000_000/us for _,us in tempo_events),
 'time_signatures':sig_events,
 'shift_sec':shift,
 'pred_phase_sec':phase,
 'old_single_phase_error_beats':old_err,
 'reference_bar_count':len(rows),
 'dynamic_mean_abs_bar_error_beats':sum(vals)/len(vals) if vals else None,
 'dynamic_p95_abs_bar_error_beats':sorted(vals)[int(.95*(len(vals)-1))] if vals else None,
 'dynamic_max_abs_bar_error_beats':max(vals) if vals else None,
 'chunks':chunks,
 'sample_rows': rows[:8]+rows[max(0,N//2-4):min(N,N//2+4)]+rows[-8:],
}
print(json.dumps(out,ensure_ascii=False,indent=2))
(ROOT/'drumscribe/experiments/arcaround-bar-diagnostic.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
