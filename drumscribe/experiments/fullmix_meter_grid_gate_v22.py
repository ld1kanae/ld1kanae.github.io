import json, math
from pathlib import Path
from collections import defaultdict
import mido

ROOT=Path('.')
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
PITCH_GROUP={36:'kick',38:'snare',42:'hat',46:'hat',44:'pedal_hat',45:'tom',49:'crash',51:'ride'}

VARIANTS={
 'grid_gate_025': .25,
 'grid_gate_050': .50,
 'grid_gate_075': .75,
}
CFG=dict(penalty3=.46,switch=.62,head=1.0,pattern=.55,run_bonus=.16)

def midi_notes(path):
    mid=mido.MidiFile(path);tempo=500000;t=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        t+=mido.tick2second(msg.time,mid.ticks_per_beat,tempo)
        if msg.type=='set_tempo':tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0 and msg.note in PITCH_GROUP:
            out.append((t,PITCH_GROUP[msg.note],msg.velocity/127))
    return out

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
            if 0<=tm<=duration:bars.append({'time':tm,'numerator':n,'denominator':d,'beatSec':at(ti)[2]/1e6})
            t+=step
    return bars,ss

def beatthis_downbeats(song):
    if song=='arcaround':
        p=ROOT/'drumscribe/experiments/beatthis-v17/arcaround-fullmix.beats'
    else:
        p=ROOT/'drumscribe/experiments/beatthis-v18'/f'{song}-fullmix.beats'
    if not p.exists():return None
    out=[]
    for line in p.read_text().splitlines():
        if not line.strip():continue
        t,pos=line.split()[:2]
        if int(float(pos))==1:out.append(float(t))
    return out

def event_features(notes,phase,beat,duration):
    n=max(8,int(math.ceil((duration-phase)/beat))+4)
    f=[defaultdict(float) for _ in range(n)]
    rad=.20*beat
    for t,g,v in notes:
        i=round((t-phase)/beat)
        if i<0 or i>=n:continue
        d=abs(t-(phase+i*beat))
        if d>rad:continue
        w=v*math.exp(-.5*(d/(.10*beat+1e-9))**2)
        f[i][g]=max(f[i][g],w)
    for i,x in enumerate(f):
        x['head']=1.35*x['kick']+2.35*x['crash']+.55*x['tom']+.18*x['ride']-.62*x['snare']
        if i>0:x['head']+=.32*f[i-1]['tom']+.18*f[i-1]['snare']
    return f

def ext_support(t,downs,beat):
    if not downs:return 0.
    d=min(abs(x-t) for x in downs)
    return math.exp(-.5*(d/(.16*beat))**2)

def bar_score(f,i,L,cfg,phase,beat,downs,extw):
    if i<0 or i+L>=len(f):return -1e9
    head=f[i]['head']*cfg['head']+extw*ext_support(phase+i*beat,downs,beat)
    if L==4:
        patt=.52*(f[i+1]['snare']+f[i+3]['snare'])+.28*f[i+2]['kick']+.15*f[i]['kick']-.22*(f[i]['snare']+f[i+2]['snare'])
        prior=0
    else:
        patt=.42*max(f[i+1]['snare'],f[i+2]['snare'])+.16*f[i]['kick']-.24*f[i]['snare']
        prior=-cfg['penalty3']
    interior=sum(f[i+j]['head'] for j in range(1,L))/max(1,L-1)
    return head+cfg['pattern']*patt+.35*(f[i]['head']-interior)+prior

def fixed4_residual_median(downs,phase,beat):
    if not downs:return 0.
    bar=4*beat
    vals=[]
    for t in downs:
        k=round((t-phase)/bar)
        vals.append(abs(t-(phase+k*bar))/beat)
    vals.sort()
    return vals[len(vals)//2]

def infer(notes,phase,beat,duration,downs,extw,gate):
    f=event_features(notes,phase,beat,duration);n=len(f)
    residual_median=fixed4_residual_median(downs,phase,beat)
    variable_enabled=bool(downs) and residual_median>=gate
    allowed=(4,3) if variable_enabled else (4,)
    dp={(0,0):(0.,[])}
    for i in range(n):
        for (idx,last),(score,path) in [(k,v) for k,v in dp.items() if k[0]==i]:
            for L in allowed:
                j=i+L
                if j>=n:continue
                s=score+bar_score(f,i,L,CFG,phase,beat,downs,extw)
                if path:s+=CFG['run_bonus'] if L==last else -CFG['switch']
                # The next prospective bar head should also agree with structural audio.
                if downs:s+=.35*extw*ext_support(phase+j*beat,downs,beat)
                key=(j,L)
                if key not in dp or s>dp[key][0]:dp[key]=(s,path+[L])
    target=max(0,int((duration-phase)/beat))
    cand=[(abs(k[0]-target),-v[0],k,v) for k,v in dp.items() if k[0]>=max(0,target-6)]
    _,_,_,(score,path)=min(cand)
    bars=[];i=0
    for L in path:
        t=phase+i*beat
        if 0<=t<=duration:bars.append({'time':t,'numerator':L,'denominator':4,'beatIndex':i,'external':ext_support(t,downs,beat)})
        i+=L
    return bars,score,residual_median,variable_enabled

def score_bars(pred,ref):
    errs=[];tp=0;sig=0
    for r in ref:
        p=min(pred,key=lambda x:abs(x['time']-r['time'])) if pred else None
        e=abs(p['time']-r['time'])/r['beatSec'] if p else 99
        errs.append(e)
        if e<=.25:tp+=1
        if p and e<=.25 and p['numerator']==r['numerator']:sig+=1
    true3=[r for r in ref if r['numerator']==3]
    hit3=sum(any(abs(p['time']-r['time'])/r['beatSec']<=.25 and p['numerator']==3 for p in pred) for r in true3)
    false3=sum(1 for p in pred if p['numerator']==3 and all(abs(p['time']-r['time'])/r['beatSec']>.25 or r['numerator']!=3 for r in ref))
    return {'mean_abs_bar_error_beats':sum(errs)/len(errs),'p95_abs_bar_error_beats':sorted(errs)[int(.95*(len(errs)-1))],
      'max_abs_bar_error_beats':max(errs),'bar_recall_025':tp/len(ref),'signature_bar_accuracy_025':sig/len(ref),
      'three_four_recall':hit3/len(true3) if true3 else None,'false_three_four_bars':false3,
      'pred_three_four_bars':sum(p['numerator']==3 for p in pred),'ref_three_four_bars':len(true3)}

inputs={}
for song in SONGS:
    meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
    side=json.loads((ROOT/'drumscribe/experiments/generated-v2-browser'/f'{song}.json').read_text())
    notes=midi_notes(ROOT/'drumscribe/experiments/generated-v2-browser'/f'{song}.mid')
    exp=float(side.get('exportOffsetSec',0) or 0);notes=[(t-exp,g,v) for t,g,v in notes]
    beat=60/float(side['bpm']);phase=float(side['barPhaseSec']);duration=float(meta['duration'])
    shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
    ref,sigs=reference_bars(ROOT/'DruMaster/songs'/song/'chart.mid',shift,duration)
    inputs[song]=(notes,beat,phase,duration,ref,sigs,beatthis_downbeats(song))

out={'schema':3,'description':'Enable variable-meter drum DP only when BeatThis fullmix downbeats systematically disagree with fixed 4/4 grid; chart scoring-only.','variants':{}}
for name,gate in VARIANTS.items():
    w=.40
    songs={};agg=[]
    for song in SONGS:
        notes,beat,phase,duration,ref,sigs,downs=inputs[song]
        pred,raw,residual_median,variable_enabled=infer(notes,phase,beat,duration,downs,w,gate)
        sc=score_bars(pred,ref)
        sc['path_score']=raw;sc['external_downbeats']=len(downs) if downs else 0
        sc['fixed4_external_residual_median_beats']=residual_median
        sc['variable_meter_enabled']=variable_enabled
        sc['reference_signatures']=sigs
        songs[song]=sc;agg.append(sc)
    valid=[x for x in agg if x['three_four_recall'] is not None]
    out['variants'][name]={'external_weight':w,'grid_gate':gate,'songs':songs,'summary':{
      'mean_bar_error_beats':sum(x['mean_abs_bar_error_beats'] for x in agg)/len(agg),
      'mean_bar_recall_025':sum(x['bar_recall_025'] for x in agg)/len(agg),
      'mean_signature_accuracy_025':sum(x['signature_bar_accuracy_025'] for x in agg)/len(agg),
      'three_four_recall':sum(x['three_four_recall'] for x in valid)/len(valid) if valid else None,
      'false_three_four_bars':sum(x['false_three_four_bars'] for x in agg)
    }}
print(json.dumps(out,ensure_ascii=False,indent=2))
(ROOT/'drumscribe/experiments/results-fullmix-meter-grid-gate-v22.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
