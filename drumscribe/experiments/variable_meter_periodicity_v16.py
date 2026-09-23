import json, math
from pathlib import Path
from collections import defaultdict
import numpy as np
import librosa
import mido

ROOT=Path('.')
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
PITCH_GROUP={36:'kick',38:'snare',42:'hat',46:'hat',44:'pedal_hat',45:'tom',49:'crash',51:'ride'}

VARIANTS={
 'periodicity_soft': dict(penalty3=.46,switch=.62,head=1.0,pattern=.55,run_bonus=.16,meter_weight=.7,smooth=9),
 'periodicity_mid': dict(penalty3=.46,switch=.62,head=1.0,pattern=.55,run_bonus=.16,meter_weight=1.15,smooth=13),
 'periodicity_strong': dict(penalty3=.46,switch=.62,head=1.0,pattern=.55,run_bonus=.16,meter_weight=1.7,smooth=17),
}

def midi_notes(path):
    mid=mido.MidiFile(path); tempo=500000; t=0.; out=[]
    for msg in mido.merge_tracks(mid.tracks):
        t+=mido.tick2second(msg.time,mid.ticks_per_beat,tempo)
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
    seg=[];sec=0.;prev=0;tempo=500000
    for tick,new in sorted(tempos.items()):
        sec+=(tick-prev)*tempo/1e6/ppq; seg.append((tick,sec,new)); prev=tick; tempo=new
    def at(tick):
        x=seg[0]
        for y in seg[1:]:
            if y[0]>tick:break
            x=y
        return x
    def tick_sec(tick):
        x=at(tick); return x[1]+(tick-x[0])*x[2]/1e6/ppq
    sig=sorted((t,*v) for t,v in sigs.items());bars=[]
    for ix,(start,n,d) in enumerate(sig):
        end=sig[ix+1][0] if ix+1<len(sig) else last+ppq*16
        step=ppq*n*4/d;t=float(start)
        while t<end-1e-6:
            ti=int(round(t));sec=tick_sec(ti)+shift
            if 0<=sec<=duration:
                bars.append({'time':sec,'numerator':n,'denominator':d,'beatSec':at(ti)[2]/1e6,'tick':ti})
            t+=step
    return bars,sig

def zrob(x):
    x=np.asarray(x,float)
    med=np.median(x); mad=np.median(np.abs(x-med))*1.4826+1e-8
    return np.clip((x-med)/mad,-3,3)

def audio_meter_features(path,phase,beat,duration,smooth):
    y,sr=librosa.load(path,sr=22050,mono=True)
    harm,perc=librosa.effects.hpss(y)
    hop=512
    chroma=librosa.feature.chroma_cens(y=harm,sr=sr,hop_length=hop)
    onset=librosa.onset.onset_strength(y=perc,sr=sr,hop_length=hop)
    mel=librosa.feature.melspectrogram(y=y,sr=sr,n_fft=2048,hop_length=hop,n_mels=40,fmin=30,fmax=6000,power=2)
    low=np.log1p(mel[:9]).mean(axis=0)
    n=max(12,int(math.ceil((duration-phase)/beat))+5)
    times=phase+np.arange(n)*beat
    frames=np.clip(librosa.time_to_frames(times,sr=sr,hop_length=hop),0,chroma.shape[1]-1)

    feat=np.zeros((n,15),float)
    for i,fr in enumerate(frames):
        a=max(0,fr-2);b=min(chroma.shape[1],fr+3)
        c=np.mean(chroma[:,a:b],axis=1)
        c=c/(np.linalg.norm(c)+1e-9)
        feat[i,:12]=c
        feat[i,12]=onset[min(len(onset)-1,fr)]
        feat[i,13]=low[min(len(low)-1,fr)]
        # harmonic novelty gives phrase landing context but is only one dimension
        if i:
            feat[i,14]=1-float(np.dot(feat[i,:12],feat[i-1,:12])/(np.linalg.norm(feat[i,:12])*np.linalg.norm(feat[i-1,:12])+1e-9))
    feat[:,12]=zrob(feat[:,12]);feat[:,13]=zrob(feat[:,13]);feat[:,14]=zrob(feat[:,14])

    # Compare repetition at lag 3 vs lag 4 over a local beat window.
    evidence=np.zeros(n,float)
    half=max(4,smooth//2)
    for i in range(n):
        a=max(0,i-half);b=min(n,i+half+1)
        vals3=[];vals4=[]
        for t in range(a,b):
            for lag,arr in ((3,vals3),(4,vals4)):
                if t+lag>=n: continue
                x=feat[t];z=feat[t+lag]
                # emphasize chroma and bass/onset periodicity
                sim=float(np.dot(x[:12],z[:12])/(np.linalg.norm(x[:12])*np.linalg.norm(z[:12])+1e-9))
                accent=math.exp(-.22*abs(x[12]-z[12]))*.55+math.exp(-.22*abs(x[13]-z[13]))*.45
                arr.append(.72*sim+.28*accent)
        s3=sum(vals3)/len(vals3) if vals3 else 0
        s4=sum(vals4)/len(vals4) if vals4 else 0
        evidence[i]=s3-s4
    evidence=zrob(evidence)
    # squash so a single extreme frame cannot dominate DP
    evidence=np.tanh(evidence*.65)
    return evidence.tolist()

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

def bar_score(f,i,L,cfg,meter):
    if i<0 or i+L>=len(f):return -1e9
    head=f[i]['head']*cfg['head']
    if L==4:
        patt=.52*(f[i+1]['snare']+f[i+3]['snare'])+.28*f[i+2]['kick']+.15*f[i]['kick']-.22*(f[i]['snare']+f[i+2]['snare'])
        prior=0
        meter_prior=-cfg['meter_weight']*meter[i]
    else:
        patt=.42*max(f[i+1]['snare'],f[i+2]['snare'])+.16*f[i]['kick']-.24*f[i]['snare']
        prior=-cfg['penalty3']
        meter_prior=cfg['meter_weight']*meter[i]
    interior=sum(f[i+j]['head'] for j in range(1,L))/max(1,L-1)
    return head+cfg['pattern']*patt+.35*(f[i]['head']-interior)+prior+meter_prior

def infer(notes,phase,beat,duration,cfg,meter):
    f=event_features(notes,phase,beat,duration);n=len(f)
    if len(meter)<n:meter=meter+[0.]*(n-len(meter))
    dp={(0,0):(0.,[])}
    for i in range(n):
        for (idx,last),(score,path) in [(k,v) for k,v in dp.items() if k[0]==i]:
            for L in (4,3):
                j=i+L
                if j>=n:continue
                s=score+bar_score(f,i,L,cfg,meter)
                if path:s+=cfg['run_bonus'] if L==last else -cfg['switch']
                key=(j,L)
                if key not in dp or s>dp[key][0]:dp[key]=(s,path+[L])
    target=max(0,int((duration-phase)/beat))
    cand=[(abs(k[0]-target),-v[0],k,v) for k,v in dp.items() if k[0]>=max(0,target-6)]
    _,_,_,(score,path)=min(cand)
    bars=[];i=0
    for L in path:
        t=phase+i*beat
        if 0<=t<=duration:bars.append({'time':t,'numerator':L,'denominator':4,'beatIndex':i,'meterEvidence':meter[i]})
        i+=L
    return bars,score

def score(pred,ref):
    errs=[];tp=0;sigok=0
    for r in ref:
        p=min(pred,key=lambda x:abs(x['time']-r['time']))
        e=abs(p['time']-r['time'])/r['beatSec'];errs.append(e)
        if e<=.25:tp+=1
        if e<=.25 and p['numerator']==r['numerator']:sigok+=1
    false3=sum(1 for p in pred if p['numerator']==3 and all(abs(p['time']-r['time'])/r['beatSec']>.25 or r['numerator']!=3 for r in ref))
    t3=[r for r in ref if r['numerator']==3]
    h3=sum(any(abs(p['time']-r['time'])/r['beatSec']<=.25 and p['numerator']==3 for p in pred) for r in t3)
    return {'mean_abs_bar_error_beats':sum(errs)/len(errs),'p95_abs_bar_error_beats':sorted(errs)[int(.95*(len(errs)-1))],
      'max_abs_bar_error_beats':max(errs),'bar_recall_025':tp/len(ref),'signature_bar_accuracy_025':sigok/len(ref),
      'three_four_recall':h3/len(t3) if t3 else None,'false_three_four_bars':false3,'pred_bars':len(pred),'ref_bars':len(ref)}

inputs={}
for song in SONGS:
    meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
    side=json.loads((ROOT/'drumscribe/experiments/generated-v2-browser'/f'{song}.json').read_text())
    notes=midi_notes(ROOT/'drumscribe/experiments/generated-v2-browser'/f'{song}.mid')
    exp=float(side.get('exportOffsetSec',0) or 0);notes=[(t-exp,g,v) for t,g,v in notes]
    beat=60/float(side['bpm']);phase=float(side['barPhaseSec']);duration=float(meta['duration'])
    shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
    ref,sigs=reference_bars(ROOT/'DruMaster/songs'/song/'chart.mid',shift,duration)
    inputs[song]=(notes,beat,phase,duration,ref,sigs)

out={'schema':1,'description':'Beat-synchronous offvocal 3-vs-4 periodicity fused with drum meter DP; chart MIDI scoring-only','variants':{}}
for name,cfg in VARIANTS.items():
    songs={};agg=[]
    for song in SONGS:
        notes,beat,phase,duration,ref,sigs=inputs[song]
        meter=audio_meter_features(ROOT/'DruMaster/songs'/song/'offvocal.mp3',phase,beat,duration,cfg['smooth'])
        pred,raw=infer(notes,phase,beat,duration,cfg,meter)
        sc=score(pred,ref)
        sc['path_score']=raw
        sc['pred_three_four_bars']=sum(p['numerator']==3 for p in pred)
        sc['ref_three_four_bars']=sum(r['numerator']==3 for r in ref)
        sc['reference_signatures']=sigs
        sc['meter_switches']=[p for i,p in enumerate(pred) if i and p['numerator']!=pred[i-1]['numerator']]
        songs[song]=sc;agg.append(sc)
    valid=[x for x in agg if x['three_four_recall'] is not None]
    out['variants'][name]={'config':cfg,'songs':songs,'summary':{
      'mean_bar_error_beats':sum(x['mean_abs_bar_error_beats'] for x in agg)/len(agg),
      'mean_bar_recall_025':sum(x['bar_recall_025'] for x in agg)/len(agg),
      'mean_signature_accuracy_025':sum(x['signature_bar_accuracy_025'] for x in agg)/len(agg),
      'three_four_recall':sum(x['three_four_recall'] for x in valid)/len(valid) if valid else None,
      'false_three_four_bars':sum(x['false_three_four_bars'] for x in agg)
    }}
print(json.dumps(out,ensure_ascii=False,indent=2))
(ROOT/'drumscribe/experiments/results-variable-meter-periodicity-v16.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
