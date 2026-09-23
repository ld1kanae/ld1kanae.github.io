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

def score(downs,beats,positions,ref):
    errs=[];rec=0
    for r in ref:
        d=min(abs(t-r['time']) for t in downs)/r['beat'] if downs else 99
        errs.append(d);rec+=d<=.25
    used=set();prec=0
    for t in downs:
        opts=[(abs(t-r['time'])/r['beat'],i) for i,r in enumerate(ref) if i not in used]
        if opts:
            d,i=min(opts)
            if d<=.25:prec+=1;used.add(i)

    # Infer bar lengths from number of beats between downbeats using beat list.
    meter=[]
    for d in downs[:-1]:
        nxt=downs[downs.index(d)+1]
        n=sum(d-0.08<=b<nxt-0.08 for b in beats)
        if n: meter.append((d,n))
    true3=[r for r in ref if r['numerator']==3]
    pred3=[t for t,n in meter if n==3]
    hit3=sum(any(abs(t-r['time'])/r['beat']<=.25 for t in pred3) for r in true3)
    false3=sum(all(abs(t-r['time'])/r['beat']>.25 for r in true3) for t in pred3)
    return {
      'downbeats':len(downs),'reference_bars':len(ref),
      'precision_025':prec/len(downs) if downs else 0,
      'recall_025':rec/len(ref) if ref else 0,
      'mean_abs_error_beats':float(np.mean(errs)),
      'p95_abs_error_beats':float(np.percentile(errs,95)),
      'max_abs_error_beats':float(np.max(errs)),
      'three_four_recall':hit3/len(true3) if true3 else None,
      'false_three_four_bars':false3,
      'predicted_meter_counts':{str(k):sum(n==k for _,n in meter) for k in sorted(set(n for _,n in meter))}
    }

meta=json.loads((ROOT/'DruMaster/songs'/SONG/'song.json').read_text())
shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
ref=reference_bars(ROOT/'DruMaster/songs'/SONG/'chart.mid',shift,float(meta['duration']))
out={}
for source in ['offvocal','fullmix']:
    j=json.loads((ROOT/'drumscribe/experiments/allin1-v15'/source/f'{source}.json').read_text())
    out[source]={'reported_bpm':j.get('bpm'),**score(j.get('downbeats',[]),j.get('beats',[]),j.get('beat_positions',[]),ref)}
print(json.dumps(out,ensure_ascii=False,indent=2))
(ROOT/'drumscribe/experiments/results-allin1-v15.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
