import json
from pathlib import Path
import mido, numpy as np

ROOT=Path('.');SONG='arcaround'
def reference_bars(path,shift,duration):
    mid=mido.MidiFile(path);ppq=mid.ticks_per_beat
    tempos={0:500000};sigs={0:(4,4)};last=0
    for tr in mid.tracks:
        tick=0
        for msg in tr:
            tick+=msg.time;last=max(last,tick)
            if msg.type=='set_tempo':tempos[tick]=msg.tempo
            elif msg.type=='time_signature':sigs[tick]=(msg.numerator,msg.denominator)
    seg=[];sec=0.;prev=0;us=500000
    for tick,new in sorted(tempos.items()):
        sec+=(tick-prev)*us/1e6/ppq;seg.append((tick,sec,new));prev=tick;us=new
    def at(t):
        x=seg[0]
        for y in seg[1:]:
            if y[0]>t:break
            x=y
        return x
    def sec_at(t):
        x=at(t);return x[1]+(t-x[0])*x[2]/1e6/ppq
    ss=sorted((t,*v) for t,v in sigs.items());bars=[]
    for i,(start,n,d) in enumerate(ss):
        end=ss[i+1][0] if i+1<len(ss) else last+ppq*16
        step=ppq*n*4/d;t=float(start)
        while t<end-1e-6:
            ti=int(round(t));tm=sec_at(ti)+shift
            if 0<=tm<=duration:bars.append({'time':tm,'numerator':n,'beat':at(ti)[2]/1e6})
            t+=step
    return bars

def load_beats(path):
    rows=[]
    for line in Path(path).read_text().splitlines():
        if not line.strip():continue
        a,b=line.split()[:2]
        rows.append((float(a),int(float(b))))
    return rows

def score(rows,ref):
    downs=[t for t,n in rows if n==1]
    errs=[];tp=0
    for r in ref:
        if not downs:continue
        d=min(abs(t-r['time']) for t in downs)/r['beat']
        errs.append(d)
        if d<=.25:tp+=1
    # one-to-one precision at same tolerance
    used=set();matched=0
    for t in downs:
        opts=[(abs(t-r['time'])/r['beat'],i) for i,r in enumerate(ref) if i not in used]
        if not opts:continue
        d,i=min(opts)
        if d<=.25:matched+=1;used.add(i)
    # Count beats between consecutive detected downbeats: this reveals whether
    # the model is actually allowing variable meter.
    meter_counts=[]
    for i in range(len(rows)-1):
        if rows[i][1]!=1:continue
        j=i+1
        while j<len(rows) and rows[j][1]!=1:j+=1
        if j<len(rows):meter_counts.append((rows[i][0],j-i))
    true3=[r for r in ref if r['numerator']==3]
    # A predicted 3-beat bar is correct only if its downbeat is near a true 3/4 bar.
    pred3=[t for t,c in meter_counts if c==3]
    hit3=sum(any(abs(t-r['time'])/r['beat']<=.25 for t in pred3) for r in true3)
    false3=sum(all(abs(t-r['time'])/r['beat']>.25 for r in true3) for t in pred3)
    return {
      'downbeats':len(downs),'reference_bars':len(ref),
      'precision_025':matched/len(downs) if downs else 0,
      'recall_025':tp/len(ref) if ref else 0,
      'mean_abs_error_beats':float(np.mean(errs)) if errs else None,
      'p95_abs_error_beats':float(np.percentile(errs,95)) if errs else None,
      'max_abs_error_beats':float(np.max(errs)) if errs else None,
      'predicted_meter_counts':{str(k):sum(c==k for _,c in meter_counts) for k in sorted(set(c for _,c in meter_counts))},
      'three_four_recall':hit3/len(true3) if true3 else None,
      'false_three_four_bars':false3,
    }

meta=json.loads((ROOT/'DruMaster/songs'/SONG/'song.json').read_text())
shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
ref=reference_bars(ROOT/'DruMaster/songs'/SONG/'chart.mid',shift,float(meta['duration']))
out={}
for source in ['offvocal','fullmix']:
    rows=load_beats(ROOT/'drumscribe/experiments/beatthis-v17'/f'arcaround-{source}.beats')
    out[source]=score(rows,ref)
print(json.dumps(out,ensure_ascii=False,indent=2))
(ROOT/'drumscribe/experiments/results-beatthis-v17.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
