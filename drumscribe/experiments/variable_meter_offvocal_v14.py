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
 'offvocal_gate45': dict(penalty3=.46,switch=.62,head=1.0,pattern=.55,run_bonus=.16,min3=4,audio_gate=.45,audio_head=.20,switch_relief=.55),
 'offvocal_gate60': dict(penalty3=.46,switch=.62,head=1.0,pattern=.55,run_bonus=.16,min3=4,audio_gate=.60,audio_head=.28,switch_relief=.72),
 'offvocal_gate75': dict(penalty3=.46,switch=.62,head=1.0,pattern=.55,run_bonus=.16,min3=4,audio_gate=.75,audio_head=.34,switch_relief=.88),
}

def midi_notes(path):
    mid=mido.MidiFile(path); tempo=500000; t=0.0; out=[]
    for msg in mido.merge_tracks(mid.tracks):
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
        step=ppq*n*4/d; t=float(start)
        while t<end-1e-6:
            ti=int(round(t)); sec=tick_sec(ti)+shift
            if 0<=sec<=duration:
                bars.append({'time':sec,'numerator':n,'denominator':d,'beatSec':beat_sec_at(ti),'tick':ti})
            t+=step
    return bars, sig

def robust01(x):
    x=np.asarray(x,dtype=float)
    if not len(x): return x
    lo=np.percentile(x,20); hi=np.percentile(x,90)
    return np.clip((x-lo)/(hi-lo+1e-9),0,1)

def offvocal_features(path,phase,beat,duration):
    y,sr=librosa.load(path,sr=22050,mono=True)
    # Separate harmonic and percussive information because downbeats are often
    # supported by both a harmonic landing and a transient/bass landing.
    harm,perc=librosa.effects.hpss(y)
    hop=512
    chroma=librosa.feature.chroma_cqt(y=harm,sr=sr,hop_length=hop)
    onset=librosa.onset.onset_strength(y=perc,sr=sr,hop_length=hop)
    S=librosa.feature.melspectrogram(y=y,sr=sr,n_fft=2048,hop_length=hop,n_mels=48,fmin=30,fmax=8000,power=2)
    low=np.log1p(S[:10]).mean(axis=0)
    rms=librosa.feature.rms(y=y,frame_length=2048,hop_length=hop)[0]

    n=max(8,int(math.ceil((duration-phase)/beat))+4)
    bt=phase+np.arange(n)*beat
    frames=np.clip(librosa.time_to_frames(bt,sr=sr,hop_length=hop),0,chroma.shape[1]-1)

    chroma_nov=np.zeros(n)
    low_land=np.zeros(n)
    perc_land=np.zeros(n)
    rms_flux=np.zeros(n)
    for i,fr in enumerate(frames):
        a=max(0,fr-2); b=min(chroma.shape[1],fr+3)
        cur=np.mean(chroma[:,a:b],axis=1)
        prev_a=max(0,fr-int(round(beat*sr/hop))-2)
        prev_b=min(chroma.shape[1],prev_a+5)
        prv=np.mean(chroma[:,prev_a:prev_b],axis=1) if prev_b>prev_a else cur
        den=np.linalg.norm(cur)*np.linalg.norm(prv)+1e-9
        chroma_nov[i]=1-float(np.dot(cur,prv)/den)
        oa=max(0,min(len(onset)-1,fr))
        low_land[i]=low[min(len(low)-1,oa)]
        perc_land[i]=onset[oa]
        pf=max(0,oa-int(round(beat*sr/hop)))
        rms_flux[i]=max(0,float(rms[min(len(rms)-1,oa)]-rms[min(len(rms)-1,pf)]))

    c=robust01(chroma_nov)
    l=robust01(low_land)
    o=robust01(perc_land)
    r=robust01(rms_flux)
    # Structure score: harmonic change is strongest, with low-frequency and
    # transient support. No reference MIDI is used here.
    section=np.clip(.48*c+.24*l+.20*o+.08*r,0,1)
    head=np.clip(.30*c+.32*l+.30*o+.08*r,0,1)
    return {
      'section':section.tolist(),
      'head':head.tolist(),
      'summary':{
        'section_p50':float(np.percentile(section,50)),
        'section_p75':float(np.percentile(section,75)),
        'section_p90':float(np.percentile(section,90)),
      }
    }

def event_features(notes,phase,beat,duration,audio):
    n=max(8,int(math.ceil((duration-phase)/beat))+4)
    f=[defaultdict(float) for _ in range(n)]
    rad=.20*beat
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
        if i<len(audio['section']): x['audio_section']=audio['section'][i]
        if i<len(audio['head']): x['audio_head']=audio['head'][i]
    return f

def bar_score(f,i,L,cfg):
    if i<0 or i+L>=len(f): return -1e9
    head=f[i]['head']*cfg['head'] + cfg['audio_head']*f[i]['audio_head']
    if L==4:
        patt=(.52*(f[i+1]['snare']+f[i+3]['snare'])+
              .28*f[i+2]['kick']+.15*f[i]['kick']-
              .22*(f[i]['snare']+f[i+2]['snare']))
        prior=0
    else:
        patt=.42*max(f[i+1]['snare'],f[i+2]['snare'])+.16*f[i]['kick']-.24*f[i]['snare']
        prior=-cfg['penalty3']
    interior=sum(f[i+j]['head'] for j in range(1,L))/max(1,L-1)
    contrast=.35*(f[i]['head']-interior)
    return head+cfg['pattern']*patt+contrast+prior

def infer_bars(notes,phase,beat,duration,cfg,audio):
    f=event_features(notes,phase,beat,duration,audio); n=len(f)
    dp={(0,0,0):(0.0,[])}
    for i in range(n):
        states=[(k,v) for k,v in dp.items() if k[0]==i]
        for (idx,last,run),(score,path) in states:
            for L in (4,3):
                switching=bool(path and L!=last)
                if last==3 and switching and run<cfg['min3']: continue
                # Meter changes must coincide with a substantial non-drum
                # structural cue from the instrumental mix.
                if switching and f[i]['audio_section']<cfg['audio_gate']:
                    continue
                j=i+L
                if j>=n: continue
                s=score+bar_score(f,i,L,cfg)
                if path:
                    if L==last:
                        s+=cfg['run_bonus']
                    else:
                        s-=cfg['switch']*(1-cfg['switch_relief']*f[i]['audio_section'])
                newrun=run+1 if L==last else 1
                key=(j,L,newrun)
                if key not in dp or s>dp[key][0]:
                    dp[key]=(s,path+[L])
    target=max(0,int((duration-phase)/beat))
    candidates=[]
    for k,v in dp.items():
        if k[0]<max(0,target-6): continue
        if k[1]==3 and k[2]<cfg['min3']: continue
        candidates.append((abs(k[0]-target),-v[0],k,v))
    if not candidates:
        candidates=[(abs(k[0]-target),-v[0],k,v) for k,v in dp.items() if k[0]>=max(0,target-8)]
    _,_,key,(score,path)=min(candidates)
    bars=[]; i=0
    for L in path:
        t=phase+i*beat
        if 0<=t<=duration: bars.append({'time':t,'numerator':L,'denominator':4,'beatIndex':i,'audioSection':f[i]['audio_section']})
        i+=L
    return bars,score,f

def score_bars(pred,ref):
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

cache={}
def song_inputs(song):
    meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
    side=json.loads((ROOT/'drumscribe/experiments/generated-v2-browser'/f'{song}.json').read_text())
    notes=midi_notes(ROOT/'drumscribe/experiments/generated-v2-browser'/f'{song}.mid')
    exp=float(side.get('exportOffsetSec',0) or 0)
    notes=[(t-exp,g,v) for t,g,v in notes]
    beat=60/float(side['bpm']); phase=float(side['barPhaseSec']); duration=float(meta['duration'])
    shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
    ref,sigs=reference_bars(ROOT/'DruMaster/songs'/song/'chart.mid',shift,duration)
    audio=offvocal_features(ROOT/'DruMaster/songs'/song/'offvocal.mp3',phase,beat,duration)
    return meta,side,notes,beat,phase,duration,ref,sigs,audio

out={'schema':1,'description':'Off-vocal harmonic/low-frequency/section cues fused with drum-only meter DP; chart MIDI is scoring-only','variants':{}}
inputs={s:song_inputs(s) for s in SONGS}
for name,cfg in VARIANTS.items():
    agg=[]; songs={}
    for song in SONGS:
        meta,side,notes,beat,phase,duration,ref,sigs,audio=inputs[song]
        pred,rawscore,_=infer_bars(notes,phase,beat,duration,cfg,audio)
        sc=score_bars(pred,ref)
        sc.update({
          'path_score':rawscore,
          'pred_three_four_bars':sum(p['numerator']==3 for p in pred),
          'ref_three_four_bars':sum(r['numerator']==3 for r in ref),
          'reference_signatures':sigs,
          'audio_feature_summary':audio['summary'],
          'meter_switches':[p for i,p in enumerate(pred) if i and p['numerator']!=pred[i-1]['numerator']]
        })
        songs[song]=sc; agg.append(sc)
    valid3=[x for x in agg if x['three_four_recall'] is not None]
    out['variants'][name]={
      'config':cfg,'songs':songs,
      'summary':{
        'mean_bar_error_beats':sum(x['mean_abs_bar_error_beats'] for x in agg)/len(agg),
        'mean_bar_recall_025':sum(x['bar_recall_025'] for x in agg)/len(agg),
        'mean_signature_accuracy_025':sum(x['signature_bar_accuracy_025'] for x in agg)/len(agg),
        'three_four_recall':sum(x['three_four_recall'] for x in valid3)/len(valid3) if valid3 else None,
        'false_three_four_bars':sum(x['false_three_four_bars'] for x in agg)
      }
    }

print(json.dumps(out,ensure_ascii=False,indent=2))
(ROOT/'drumscribe/experiments/results-variable-meter-offvocal-v14.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
