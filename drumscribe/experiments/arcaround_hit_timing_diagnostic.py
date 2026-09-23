import json
from pathlib import Path
import mido, numpy as np

ROOT=Path('.'); SONG='arcaround'
GROUPS={
 'kick':{35,36},'snare':{37,38,39,40},'hat':{42,46},'pedal_hat':{44},
 'tom':{41,43,45,47,48,50},'crash':{49,52,55,57},'ride':{51,53,59}
}
def group(note):
    return next((g for g,s in GROUPS.items() if note in s),None)

def notes(path):
    mid=mido.MidiFile(path);tempo=500000;t=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        t+=mido.tick2second(msg.time,mid.ticks_per_beat,tempo)
        if msg.type=='set_tempo':tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0:
            g=group(msg.note)
            if g:out.append((t,g,msg.note))
    return out

meta=json.loads((ROOT/'DruMaster/songs'/SONG/'song.json').read_text())
side=json.loads((ROOT/'drumscribe/experiments/generated-v2-browser'/f'{SONG}.json').read_text())
pred=notes(ROOT/'drumscribe/experiments/generated-v2-browser'/f'{SONG}.mid')
exp=float(side.get('exportOffsetSec',0) or 0)
pred=[(t-exp,g,n) for t,g,n in pred]
truth=notes(ROOT/'DruMaster/songs'/SONG/'chart.mid')
shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
truth=[(t+shift,g,n) for t,g,n in truth]
duration=float(meta['duration'])

# One-to-one same-group matching with a wider diagnostic tolerance. This measures
# whether timing error grows with song time independently of class precision.
used=set();pairs=[]
for pi,(pt,pg,pn) in enumerate(pred):
    opts=[(abs(pt-tt),j,tt) for j,(tt,tg,tn) in enumerate(truth)
          if j not in used and tg==pg and abs(pt-tt)<=.15]
    if not opts:continue
    d,j,tt=min(opts)
    used.add(j);pairs.append((pt,pg,pt-tt))

bins=[(0,60),(60,120),(120,180),(180,240),(240,duration+1)]
rows=[]
for a,b in bins:
    xs=[x for x in pairs if a<=x[0]<b]
    e=np.array([x[2] for x in xs],float)
    pred_n=sum(a<=t<b for t,_,_ in pred)
    truth_n=sum(a<=t<b for t,_,_ in truth)
    rows.append({
      'range_sec':[a,b],
      'matched':len(xs),'predicted':pred_n,'reference':truth_n,
      'median_signed_ms':float(np.median(e)*1000) if len(e) else None,
      'mean_signed_ms':float(np.mean(e)*1000) if len(e) else None,
      'mean_abs_ms':float(np.mean(np.abs(e))*1000) if len(e) else None,
      'p95_abs_ms':float(np.percentile(np.abs(e),95)*1000) if len(e) else None,
    })
by_group={}
for g in GROUPS:
    xs=[x for x in pairs if x[1]==g]
    e=np.array([x[2] for x in xs],float)
    by_group[g]={
      'matched':len(xs),
      'median_signed_ms':float(np.median(e)*1000) if len(e) else None,
      'mean_abs_ms':float(np.mean(np.abs(e))*1000) if len(e) else None,
    }
out={
 'song':SONG,'estimated_bpm':side['bpm'],'reference_bpm':meta['bpm'],
 'shift_sec':shift,'export_offset_sec':exp,
 'total_pairs':len(pairs),'time_bins':rows,'by_group':by_group
}
print(json.dumps(out,ensure_ascii=False,indent=2))
(ROOT/'drumscribe/experiments/arcaround-hit-timing-diagnostic.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
