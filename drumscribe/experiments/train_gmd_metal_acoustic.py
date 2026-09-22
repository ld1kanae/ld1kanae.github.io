"""Train a compact metal-hit acoustic classifier from GMD audio+MIDI.

The GMD full archive is accessed with HTTP range requests; only a bounded
rock-family subset of WAV files is fetched. Source audio/MIDI is not committed.

Features intentionally match information available in the browser pipeline:
- per-song normalized 4-band spectral flux
- fixed DruMaster reference-sample similarities (hat/pedal/ride/crash etc.)
- local temporal means/maxima around the onset
- high-frequency decay features
- coarse normalized spectral-rise shape

Output is a small standardized multinomial logistic model in JSON, plus an
external GMD validation report. No DruMaster chart.mid is used in training.
"""
from __future__ import annotations
import argparse,csv,io,json,math,random,zipfile
from pathlib import Path
from collections import Counter

import mido
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report,confusion_matrix
from sklearn.preprocessing import StandardScaler

import importlib.util
ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
specm=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(specm);specm.loader.exec_module(ev)
LABELS=("hat","pedal_hat","ride","crash")
PITCH={}
for g in LABELS:
    for p in ev.GROUPS[g]:PITCH[p]=g

def midi_notes(path):
    mid=mido.MidiFile(path);tpb=mid.ticks_per_beat;tick=0;tempo=500000;sec=0.;out=[]
    # GMD files have stable tempo; merged delta ticks -> seconds.
    for msg in mido.merge_tracks(mid.tracks):
        dt=msg.time
        sec+=mido.tick2second(dt,tpb,tempo)
        if msg.type=="set_tempo":tempo=msg.tempo
        if msg.type=="note_on" and msg.velocity>0 and int(msg.note) in PITCH:
            out.append((sec,PITCH[int(msg.note)]))
    return out

def mono_resample(raw,sr):
    x=raw.astype(np.float32)
    if np.issubdtype(raw.dtype,np.integer):
        x/=max(abs(np.iinfo(raw.dtype).min),np.iinfo(raw.dtype).max)
    if x.ndim>1:x=x.mean(axis=1)
    if sr!=ev.SR:
        g=math.gcd(int(sr),ev.SR);x=resample_poly(x,ev.SR//g,int(sr)//g).astype("f4")
    return x

def rise_shape(spec,fr,n=16):
    prev=max(0,fr-2)
    r=np.maximum(spec[:,fr]-spec[:,prev],0)
    freqs=np.arange(len(r))*ev.SR/ev.FFT
    lo,hi=350,5500
    edges=np.geomspace(lo,hi,n+1)
    vals=[]
    for a,b in zip(edges[:-1],edges[1:]):
        z=float(r[(freqs>=a)&(freqs<b)].sum())
        vals.append(math.log1p(z))
    v=np.asarray(vals,dtype=np.float32)
    v=(v-v.mean())/(v.std()+1e-5)
    return v.tolist()

def decay(spec,fr):
    freqs=np.arange(spec.shape[0])*ev.SR/ev.FFT
    hi=spec[(freqs>=1800)&(freqs<=5400)].sum(axis=0);n=len(hi)
    def mean(a,b):
        aa=max(0,fr+a);bb=min(n,fr+b)
        return float(np.mean(hi[aa:bb])) if bb>aa else 0.
    def mx(a,b):
        aa=max(0,fr+a);bb=min(n,fr+b)
        return float(np.max(hi[aa:bb])) if bb>aa else 0.
    pre=mean(-12,-3);on=mx(-1,3);amp=max(on-pre,1e-7)
    return [max(0,mean(4,11)-pre)/amp,max(0,mean(11,21)-pre)/amp,max(0,mean(21,36)-pre)/amp]

def feature(spec,band,sim,t):
    fr=max(0,min(spec.shape[1]-1,int(round(t*ev.SR/ev.HOP))))
    vals=[float(band[i,fr]) for i in range(4)]
    vals += [float(sim[i,fr]) for i in range(min(8,sim.shape[0]))]
    while len(vals)<12:vals.append(0.)
    # metal template relationships
    h=float(sim[ev.ORDER.index("hat"),fr]);p=float(sim[ev.ORDER.index("pedal_hat"),fr])
    r=float(sim[ev.ORDER.index("ride"),fr]);c=float(sim[ev.ORDER.index("crash"),fr])
    vals += [p-h,r-h,c-h,p/(abs(h)+1e-4),r/(abs(h)+1e-4),c/(abs(h)+1e-4)]
    for radius in (2,5,10,20):
        a=max(0,fr-radius);b=min(band.shape[1],fr+radius+1)
        for bi in (2,3):
            z=band[bi,a:b];vals += [float(np.mean(z)),float(np.max(z))]
    vals += decay(spec,fr)
    vals += rise_shape(spec,fr,16)
    return np.asarray(vals,dtype=np.float32)

def resolve_local(root,rel):
    p=root/rel
    if p.exists():return p
    m=list(root.rglob(Path(rel).name))
    return m[0] if m else None

def isolated(notes,i,w=.035):
    t,g=notes[i]
    return not any(j!=i and abs(x-t)<=w for j,(x,gg) in enumerate(notes) if gg in LABELS)

def load_remote_wav(rz,audio_rel):
    # Archive has a top-level groove/ directory; match by suffix robustly.
    suffix=audio_rel.replace("\\","/")
    names=[n for n in rz.namelist() if n.endswith(suffix)]
    if not names:raise KeyError(suffix)
    data=rz.read(names[0])
    sr,raw=wavfile.read(io.BytesIO(data))
    return mono_resample(raw,sr)

def collect(rows,root,rz,tmpl,max_files,seed):
    rng=random.Random(seed);rows=list(rows);rng.shuffle(rows);X=[];y=[];used=0;counts=Counter()
    for row in rows:
        if used>=max_files:break
        mp=resolve_local(root,row["midi_filename"])
        if mp is None:continue
        try:
            x=load_remote_wav(rz,row["audio_filename"])
            notes=midi_notes(mp)
            sp=ev.spectrum(x);band,sim=ev.features(sp,tmpl)
        except Exception as e:
            print("SKIP",row.get("id"),type(e).__name__,str(e)[:120],flush=True);continue
        local=0
        for i,(t,g) in enumerate(notes):
            # isolate metal-on-metal mixtures during training; kick/snare overlap remains.
            if not isolated(notes,i):continue
            X.append(feature(sp,band,sim,t));y.append(g);counts[g]+=1;local+=1
        if local:
            used+=1
            print("FILE",used,row.get("split"),row.get("style"),local,dict(counts),flush=True)
    return np.stack(X) if X else np.zeros((0,1),dtype=np.float32),np.asarray(y),used,counts

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--midi-root",required=True);ap.add_argument("--url",required=True)
    ap.add_argument("--train-files",type=int,default=70);ap.add_argument("--val-files",type=int,default=25)
    ap.add_argument("--output",default="drumscribe/models/gmd-metal-acoustic-logreg.json")
    a=ap.parse_args()
    from remotezip import RemoteZip
    root=Path(a.midi_root);info=next(iter(root.rglob("info.csv")))
    rows=list(csv.DictReader(info.open(newline="",encoding="utf-8")))
    def rock(r):
        primary=(r.get("style") or "").split("/")[0]
        return primary in ("rock","punk") and r.get("time_signature") in ("4-4","4/4")
    tr=[r for r in rows if r.get("split")=="train" and rock(r)]
    va=[r for r in rows if r.get("split")=="validation" and rock(r)]
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    with RemoteZip(a.url) as rz:
        X,y,ntr,ctr=collect(tr,root,rz,tmpl,a.train_files,117)
        V,vy,nv,cva=collect(va,root,rz,tmpl,a.val_files,223)
    if len(set(y))<4:raise SystemExit(f"missing classes: {Counter(y)}")
    scaler=StandardScaler().fit(X);Xs=scaler.transform(X)
    clf=LogisticRegression(max_iter=1000,class_weight="balanced",C=.55,solver="lbfgs").fit(Xs,y)
    pred=clf.predict(scaler.transform(V)) if len(V) else np.array([])
    report={
      "trainFiles":ntr,"validationFiles":nv,"trainCounts":dict(ctr),"validationCounts":dict(cva),
      "classes":clf.classes_.tolist(),
      "validationReport":classification_report(vy,pred,labels=clf.classes_,output_dict=True,zero_division=0) if len(V) else {},
      "validationConfusion":confusion_matrix(vy,pred,labels=clf.classes_).tolist() if len(V) else [],
    }
    model={
      "schema":1,
      "source":{"dataset":"Groove MIDI Dataset v1.0.0","split":"train","style":"rock+punk","license":"CC BY 4.0"},
      "featureDim":int(X.shape[1]),"classes":clf.classes_.tolist(),
      "mean":scaler.mean_.tolist(),"scale":scaler.scale_.tolist(),
      "coef":clf.coef_.tolist(),"intercept":clf.intercept_.tolist(),
      "training":report
    }
    op=Path(a.output);op.parent.mkdir(parents=True,exist_ok=True);op.write_text(json.dumps(model,indent=2)+"\n")
    (EXP/"results-gmd-metal-acoustic.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
