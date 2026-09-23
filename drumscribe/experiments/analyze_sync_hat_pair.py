#!/usr/bin/env python3
"""Analyze a fully synchronized drum WAV/MIDI pair for hi-hat articulation.

This is an offline diagnostic. It never participates in prediction. The paired
MIDI is ground truth used to measure acoustic differences after synchronization.

Example:
  python analyze_sync_hat_pair.py pair.wav pair.mid --out result.json
"""
from __future__ import annotations
import argparse,bisect,hashlib,json,math
from collections import Counter
from pathlib import Path
import mido,numpy as np
from scipy.io import wavfile
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix,precision_recall_fscore_support
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HATS={42,44,46}
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):h.update(block)
    return h.hexdigest()

def timed_notes(path):
    mid=mido.MidiFile(path)
    tick=0; notes=[]; tempos=[(0,500000)]
    for msg in mido.merge_tracks(mid.tracks):
        tick+=msg.time
        if msg.type=="set_tempo":tempos.append((tick,msg.tempo))
        elif msg.type=="note_on" and msg.velocity>0:notes.append((tick,msg.note,msg.velocity))
    tmp=[]
    for t,v in sorted(tempos):
        if tmp and tmp[-1][0]==t:tmp[-1]=(t,v)
        else:tmp.append((t,v))
    tempos=tmp; seg=[];sec=0.;pt,tempo=tempos[0]
    seg.append((pt,sec,tempo))
    for t,newtempo in tempos[1:]:
        sec+=mido.tick2second(t-pt,mid.ticks_per_beat,tempo)
        seg.append((t,sec,newtempo));pt=t;tempo=newtempo
    ticks=[x[0] for x in seg]
    def tosec(t):
        i=max(0,bisect.bisect_right(ticks,t)-1);st,ss,tempo=seg[i]
        return ss+mido.tick2second(t-st,mid.ticks_per_beat,tempo)
    return mid,[(tosec(t),n,v,t) for t,n,v in notes],len(tempos)

def band_rms(x,sr,a,b,lo=5000,hi=18000):
    ia=max(0,int(a*sr));ib=min(len(x),int(b*sr))
    y=x[ia:ib]
    if len(y)<32:return float("nan")
    y=y*np.hanning(len(y));X=np.fft.rfft(y);f=np.fft.rfftfreq(len(y),1/sr)
    p=np.abs(X)**2
    return float(np.sqrt(p[(f>=lo)&(f<=hi)].sum())/(len(y)+1e-12))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("wav",type=Path);ap.add_argument("midi",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    mid,notes,tempo_count=timed_notes(a.midi)
    sr,audio=wavfile.read(a.wav)
    x=audio.astype(np.float32)
    if x.ndim>1:x=x.mean(axis=1)
    scale=float(np.iinfo(audio.dtype).max) if np.issubdtype(audio.dtype,np.integer) else 1.
    x/=max(scale,1.)
    count=Counter(n for _,n,_,_ in notes)
    hats=sorted(e for e in notes if e[1] in HATS)
    nxt=Counter();gaps=[]
    for i,e in enumerate(hats[:-1]):
        if e[1]!=46:continue
        nxt[hats[i+1][1]]+=1;gaps.append(hats[i+1][0]-e[0])
    decay={}
    rows=[]
    for note in (42,44,46):
        midv=[];latev=[]
        for s,n,_,_ in hats:
            if n!=note:continue
            onset=band_rms(x,sr,s,s+.025)
            if not np.isfinite(onset) or onset<=0:continue
            midv.append(band_rms(x,sr,s+.080,s+.140)/onset)
            latev.append(band_rms(x,sr,s+.150,s+.220)/onset)
            if note in (42,46):
                f=[]
                for lo,hi in ((.025,.060),(.060,.120),(.120,.180),(.180,.230)):
                    f.append(math.log1p(band_rms(x,sr,s+lo,s+hi)/onset))
                rows.append((s,int(note==46),f))
        decay[str(note)]={"n":len(midv),"mid80to140Median":float(np.median(midv)),
                          "late150to220Median":float(np.median(latev))}
    rows.sort();times=np.array([r[0] for r in rows]);y=np.array([r[1] for r in rows]);X=np.array([r[2] for r in rows])
    edges=np.linspace(times.min(),times.max()+1e-6,6);pred=np.full(len(y),-1)
    for k in range(5):
        te=(times>=edges[k])&(times<edges[k+1]);tr=~te
        if te.sum()==0 or len(np.unique(y[tr]))<2:continue
        model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,class_weight="balanced"))
        model.fit(X[tr],y[tr]);pred[te]=model.predict(X[te])
    ok=pred>=0;p,r,f,_=precision_recall_fscore_support(y[ok],pred[ok],average="binary",zero_division=0)
    tn,fp,fn,tp=confusion_matrix(y[ok],pred[ok],labels=[0,1]).ravel()
    out={
      "schema":1,"source":{"wav":a.wav.name,"midi":a.midi.name,
        "wavSha256":sha256(a.wav),"midiSha256":sha256(a.midi)},
      "audio":{"sampleRate":int(sr),"channels":int(audio.shape[1] if audio.ndim>1 else 1),
        "durationSec":len(audio)/sr},
      "midi":{"ppq":mid.ticks_per_beat,"tracks":len(mid.tracks),"tempoEvents":tempo_count,
        "noteCounts":{str(n):count[n] for n in sorted(count)}},
      "openTransitions":{"openEvents":count[46],
        "nextHatArticulation":{str(n):nxt[n] for n in (42,44,46)},
        "medianGapSec":float(np.median(gaps)) if gaps else None},
      "highBandDecay":{"bandHz":[5000,18000],"byNote":decay},
      "blockedTimeCv":{"folds":5,"task":"GM42 vs GM46","precisionOpen":p,"recallOpen":r,"f1Open":f,
        "confusionMatrix":{"tn":int(tn),"fp":int(fp),"fn":int(fn),"tp":int(tp)}},
      "limitations":["This is a single-song synchronized diagnostic.",
        "If nextHatArticulation.46 is zero, this pair contains no open->open teacher example."]
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
