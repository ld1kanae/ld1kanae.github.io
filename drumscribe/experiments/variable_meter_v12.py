import json, math
from pathlib import Path
from collections import defaultdict
import mido

ROOT=Path('.')
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
PITCH_GROUP={36:'kick',38:'snare',42:'hat',46:'hat',44:'pedal_hat',45:'tom',49:'crash',51:'ride'}

VARIANTS={
 'meter_dp_conservative': dict(penalty3=.78,switch=.95,head=1.0,pattern=.42,run_bonus=.10),
 'meter_dp_balanced': dict(penalty3=.46,switch=.62,head=1.0,pattern=.55,run_bonus=.16),
 'meter_dp_sensitive': dict(penalty3=.22,switch=.42,head=1.0,pattern=.70,run_bonus=.22),
}

def midi_notes(path):
    mid=mido.MidiFile(path); tempo=500000; t=0.0; out=[]
    merged=mido.merge_tracks(mid.tracks)
    for msg in merged:
        t += mido.tick2second(msg.time,mid.ticks_per_beat,tempo)
        if msg.type=='set_tempo': tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0 and msg.note in PITCH_GROUP:
            out.append((t,PITCH_GROUP[msg.note],msg.velocity/127))
    return out

def reference_bars(path,shift,duration):
    mid=mido.MidiFile(path); ppq=mid.ticks_per_beat
    tempos={0:500000}; sigs={0:(4,4)}; last=0
    for tr in mid.tracks:
        tick=0
        for msg in tr:
            tick+=msg.time; last=max(last,tick)
            if msg.type=='set_tempo': tempos[tick]=msg.tempo
            elif msg.type=='time_signature': sigs[tick]=(msg.numerator,msg.denominator)
    te=sorted(tempos.items())
    seg=[]; sec=0.; prev=0; tempo=500000
    for tick,new in te:
        sec+=(tick-prev)*tempo/1e6/ppq
        seg.append((tick,sec,new)); prev=tick; tempo=new
    def tick_sec(tick):
        x=seg[0]
        for y in seg[1:]:
            if y[0]>tick: break
            x=y
        return x[1]+(tick-x[0])*x[2]/1e6/ppq
    def beat_sec_at(tick):
        x=seg[0]
        for y in seg[1:]:
            if y[0]>tick: break
            x=y
        return x[2]/1e6
    sig=sorted((t,*v) for t,v in sigs.items())
    bars=[]
    for ix,(start,n,d) in enumerate(sig):
        end=sig[ix+1][0] if ix+1<len(sig) else last+ppq*16
        step=ppq*n*4/d
        t=float(start)
        while t<end-1e-6:
            ti=int(round(t)); sec=tick_sec(ti)+shift
            if 0<=sec<=duration:
                bars.append({'time':sec,'numerator':n,'denominator':d,'beatSec':beat_sec_at(ti),'tick':ti})
            t+=step
    return bars, sig, te

def event_features(notes,phase,beat,duration):
    n=max(8,int(math.ceil((duration-phase)/beat))+4)
    groups=['kick','snare','hat','pedal_hat','tom','crash','ride']
    f=[defaultdict(float) for _ in range(n)]
    rad=.20*beat
    # assign each note to nearest beat if close enough
    for t,g,v in notes:
        i=round((t-phase)/beat)
        if i<0 or i>=n: continue
        d=abs(t-(phase+i*beat))
        if d>rad: continue
        w=v*math.exp(-.5*(d/(.10*beat+1e-9))**2)
        f[i][g]=max(f[i][g],w)
    for i,x in enumerate(f):
        x['head']=1.35*x['kick']+2.35*x['crash']+.55*x['tom']+.18*x['ride']-.62*x['snare']
        if i>0: x['head']+=.32*f[i-1]['tom']+.18*f[i-1]['snare']
    return f

def bar_score(f,i,L,cfg):
    if i<0 or i+L>=len(f): return -1e9
    head=f[i]['head']*cfg['head']
    if L==4:
        patt=(.52*(f[i+1]['snare']+f[i+3]['snare'])+
              .28*f[i+2]['kick']+.15*f[i]['kick']-
              .22*(f[i]['snare']+f[i+2]['snare']))
        prior=0
    else:
        # 3/4 rock passages vary; reward a clear head and a non-downbeat snare
        # without imposing one exact backbeat location.
        patt=.42*max(f[i+1]['snare'],f[i+2]['snare'])+.16*f[i]['kick']-.24*f[i]['snare']
        prior=-cfg['penalty3']
    # A candidate head should be stronger than the average interior beat.
    interior=sum(f[i+j]['head'] for j in range(1,L))/max(1,L-1)
    contrast=.35*(f[i]['head']-interior)
    return head+cfg['pattern']*patt+contrast+prior

def infer_bars(notes,phase,beat,duration,cfg):
    f=event_features(notes,phase,beat,duration)
    n=len(f)
    # DP state (beat index,last meter) -> (score,path)
    dp={(0,4):(0.0,[]),(0,3):(-.25,[])}
    # allow an initial 4-beat bar before phase to be outside reference; phase is a downbeat
    for i in range(n):
        states=[(k,v) for k,v in dp.items() if k[0]==i]
        for (idx,last),(score,path) in states:
            for L in (4,3):
                j=i+L
                if j>=n: continue
                s=score+bar_score(f,i,L,cfg)
                if path:
                    s += cfg['run_bonus'] if L==last else -cfg['switch']
                key=(j,L)
                if key not in dp or s>dp[key][0]:
                    dp[key]=(s,path+[L])
    # best state reaching close to duration
    target=max(0,int((duration-phase)/beat))
    candidates=[(abs(k[0]-target),-v[0],k,v) for k,v in dp.items() if k[0]>=max(0,target-6)]
    _,_,key,(score,path)=min(candidates)
    bars=[]; i=0
    for L in path:
        t=phase+i*beat
        if t>=0 and t<=duration: bars.append({'time':t,'numerator':L,'denominator':4,'beatIndex':i})
        i+=L
    return bars,score,f

def score_bars(pred,ref):
    if not ref: return {}
    errs=[]; tp=0; sig_ok=0
    for r in ref:
        p=min(pred,key=lambda x:abs(x['time']-r['time'])) if pred else None
        e=abs(p['time']-r['time'])/r['beatSec'] if p else 99
        errs.append(e)
        if e<=.25: tp+=1
        if p and e<=.25 and p['numerator']==r['numerator']: sig_ok+=1
    p95=sorted(errs)[int(.95*(len(errs)-1))]
    false3=sum(1 for p in pred if p['numerator']==3 and all(abs(p['time']-r['time'])/r['beatSec']>.25 or r['numerator']!=3 for r in ref))
    true3=sum(1 for r in ref if r['numerator']==3)
    hit3=sum(1 for r in ref if r['numerator']==3 and any(abs(p['time']-r['time'])/r['beatSec']<=.25 and p['numerator']==3 for p in pred))
    return {
      'mean_abs_bar_error_beats':sum(errs)/len(errs),
      'p95_abs_bar_error_beats':p95,
      'max_abs_bar_error_beats':max(errs),
      'bar_recall_025':tp/len(ref),
      'signature_bar_accuracy_025':sig_ok/len(ref),
      'three_four_recall':hit3/true3 if true3 else None,
      'false_three_four_bars':false3,
      'pred_bars':len(pred),'ref_bars':len(ref)
    }

out={'schema':1,'description':'Audio-output-only variable meter hypotheses; chart MIDI is scoring-only','variants':{}}
for name,cfg in VARIANTS.items():
    agg=[]; songs={}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
        side=json.loads((ROOT/'drumscribe/experiments/generated-v2-browser'/f'{song}.json').read_text())
        notes=midi_notes(ROOT/'drumscribe/experiments/generated-v2-browser'/f'{song}.mid')
        exp=float(side.get('exportOffsetSec',0) or 0)
        notes=[(t-exp,g,v) for t,g,v in notes]
        beat=60/float(side['bpm'])
        phase=float(side['barPhaseSec'])
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        ref,sigs,tempos=reference_bars(ROOT/'DruMaster/songs'/song/'chart.mid',shift,float(meta['duration']))
        pred,rawscore,_=infer_bars(notes,phase,beat,float(meta['duration']),cfg)
        sc=score_bars(pred,ref)
        sc['path_score']=rawscore
        sc['pred_three_four_bars']=sum(p['numerator']==3 for p in pred)
        sc['ref_three_four_bars']=sum(r['numerator']==3 for r in ref)
        sc['reference_signatures']=sigs
        songs[song]=sc
        agg.append(sc)
    valid3=[x for x in agg if x['three_four_recall'] is not None]
    out['variants'][name]={
      'config':cfg,
      'songs':songs,
      'summary':{
        'mean_bar_error_beats':sum(x['mean_abs_bar_error_beats'] for x in agg)/len(agg),
        'mean_bar_recall_025':sum(x['bar_recall_025'] for x in agg)/len(agg),
        'mean_signature_accuracy_025':sum(x['signature_bar_accuracy_025'] for x in agg)/len(agg),
        'three_four_recall':sum(x['three_four_recall'] for x in valid3)/len(valid3) if valid3 else None,
        'false_three_four_bars':sum(x['false_three_four_bars'] for x in agg)
      }
    }

# Baseline: fixed 4/4
base={}
agg=[]
for song in SONGS:
    meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
    side=json.loads((ROOT/'drumscribe/experiments/generated-v2-browser'/f'{song}.json').read_text())
    beat=60/float(side['bpm']); phase=float(side['barPhaseSec'])
    pred=[];t=phase
    while t<=float(meta['duration'])+beat*4:
        if t>=0: pred.append({'time':t,'numerator':4,'denominator':4})
        t+=4*beat
    shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
    ref,_,_=reference_bars(ROOT/'DruMaster/songs'/song/'chart.mid',shift,float(meta['duration']))
    sc=score_bars(pred,ref);base[song]=sc;agg.append(sc)
out['baseline_fixed_4_4']={'songs':base,'summary':{
 'mean_bar_error_beats':sum(x['mean_abs_bar_error_beats'] for x in agg)/len(agg),
 'mean_bar_recall_025':sum(x['bar_recall_025'] for x in agg)/len(agg),
 'mean_signature_accuracy_025':sum(x['signature_bar_accuracy_025'] for x in agg)/len(agg),
 'false_three_four_bars':0
}}
print(json.dumps(out,ensure_ascii=False,indent=2))
(ROOT/'drumscribe/experiments/results-variable-meter-v12.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
