"""Train a compact metal classifier on frozen ADTOF GRU embeddings.

Training data:
- Groove MIDI Dataset v1.0.0 audio + MIDI
- official train split for fitting, validation split for external evaluation
- rock/punk 4/4 subset
- bounded number of range-streamed WAV files

No DruMaster chart.mid or audio is used for fitting.

Feature per isolated metal onset:
- frozen ADTOF final bidirectional-GRU state (120 dims)
- ADTOF five output activations at the onset (5 dims)
- local mean of GRU state +/- 2 frames (120 dims)
- local mean/max of ADTOF activations +/- 2 frames (10 dims)

Output is a standardized multinomial logistic model stored as JSON so it can
later be ported to the browser without another neural runtime.
"""
from __future__ import annotations

import argparse,csv,io,json,math,random
from collections import Counter
from pathlib import Path

import mido
import numpy as np
import torch
from scipy.io import wavfile
from scipy.signal import resample_poly
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report,confusion_matrix
from sklearn.preprocessing import StandardScaler

from adtof_pytorch import calculate_n_bins,create_frame_rnn_model,get_default_weights_path,load_pytorch_weights
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
LABELS=("hat","pedal_hat","ride","crash")
PITCH={42:"hat",22:"hat",46:"hat",26:"hat",44:"pedal_hat",
       51:"ride",53:"ride",59:"ride",49:"crash",52:"crash",55:"crash",57:"crash"}

def midi_notes(path):
    mid=mido.MidiFile(path);tpb=mid.ticks_per_beat;tick=0;tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec+=mido.tick2second(msg.time,tpb,tempo);tick+=msg.time
        if msg.type=="set_tempo":tempo=msg.tempo
        if msg.type=="note_on" and msg.velocity>0 and int(msg.note) in PITCH:
            out.append((sec,PITCH[int(msg.note)]))
    return out

def mono_resample(raw,sr,target=44100):
    x=raw.astype(np.float32)
    if np.issubdtype(raw.dtype,np.integer):
        x/=max(abs(np.iinfo(raw.dtype).min),np.iinfo(raw.dtype).max)
    if x.ndim>1:x=x.mean(axis=1)
    if sr!=target:
        g=math.gcd(int(sr),target);x=resample_poly(x,target//g,int(sr)//g).astype("f4")
    return x

def resolve(root,rel):
    p=root/rel
    if p.exists():return p
    q=list(root.rglob(Path(rel).name));return q[0] if q else None

def remote_wav(rz,rel):
    suffix=rel.replace("\\","/")
    names=[n for n in rz.namelist() if n.endswith(suffix)]
    if not names:raise KeyError(suffix)
    sr,raw=wavfile.read(io.BytesIO(rz.read(names[0])))
    return mono_resample(raw,sr)

def frozen_model():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    m=load_pytorch_weights(m,get_default_weights_path(),strict=False).eval()
    return m

def hidden_and_output(model,x_np):
    x=torch.from_numpy(x_np[None,...]).float()
    with torch.no_grad():
        B,T,F,C=x.shape
        z=x.permute(0,3,1,2)
        for block in model.cnn_blocks:z=block(z)
        z=z.permute(0,2,3,1).reshape(B,T,-1)
        if getattr(model,"context_layer",None) is not None:z=model.context_layer(z)
        for gru in model.gru_layers:z,_=gru(z)
        logits=model.output_layer(z)
        out=torch.sigmoid(logits)
    return z[0].cpu().numpy().astype(np.float32),out[0].cpu().numpy().astype(np.float32)

def isolated(notes,i,w=.035):
    t,g=notes[i]
    return not any(j!=i and abs(x-t)<=w for j,(x,gg) in enumerate(notes))

def feature(h,a,fr):
    fr=max(0,min(len(h)-1,fr));lo=max(0,fr-2);hi=min(len(h),fr+3)
    return np.concatenate([
        h[fr],
        a[fr],
        h[lo:hi].mean(axis=0),
        a[lo:hi].mean(axis=0),
        a[lo:hi].max(axis=0),
    ]).astype(np.float32)

def collect(rows,root,rz,model,processor,max_files,seed):
    rng=random.Random(seed);rows=list(rows);rng.shuffle(rows)
    X=[];y=[];used=0;counts=Counter()
    for row in rows:
        if used>=max_files:break
        mp=resolve(root,row["midi_filename"])
        if mp is None:continue
        try:
            audio=remote_wav(rz,row["audio_filename"])
            st=processor.compute_stft(audio)
            fx=processor.apply_filterbank(st).T.astype(np.float32)[...,None]
            h,a=hidden_and_output(model,fx)
            notes=midi_notes(mp)
        except Exception as e:
            print("SKIP",row.get("id"),type(e).__name__,str(e)[:100],flush=True);continue
        n=0
        for i,(t,g) in enumerate(notes):
            if not isolated(notes,i):continue
            fr=max(0,min(len(h)-1,int(round(t*100))))
            X.append(feature(h,a,fr));y.append(g);counts[g]+=1;n+=1
        if n:
            used+=1
            print("FILE",used,row.get("split"),row.get("style"),n,dict(counts),flush=True)
    return np.stack(X),np.asarray(y),used,counts

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--midi-root",required=True)
    ap.add_argument("--url",required=True)
    ap.add_argument("--train-files",type=int,default=45)
    ap.add_argument("--val-files",type=int,default=16)
    ap.add_argument("--output",default="drumscribe/models/gmd-adtof-metal-logreg.json")
    args=ap.parse_args()

    from remotezip import RemoteZip
    root=Path(args.midi_root);info=next(iter(root.rglob("info.csv")))
    rows=list(csv.DictReader(info.open(newline="",encoding="utf-8")))
    def eligible(r):
        primary=(r.get("style") or "").split("/")[0]
        return primary in ("rock","punk") and r.get("time_signature") in ("4-4","4/4")
    tr=[r for r in rows if r.get("split")=="train" and eligible(r)]
    va=[r for r in rows if r.get("split")=="validation" and eligible(r)]

    model=frozen_model();processor=create_adtof_processor()
    with RemoteZip(args.url) as rz:
        X,y,ntr,ctr=collect(tr,root,rz,model,processor,args.train_files,911)
        V,vy,nv,cva=collect(va,root,rz,model,processor,args.val_files,1223)

    scaler=StandardScaler().fit(X)
    clf=LogisticRegression(max_iter=1500,class_weight="balanced",C=.40,solver="lbfgs").fit(scaler.transform(X),y)
    pred=clf.predict(scaler.transform(V))
    rep=classification_report(vy,pred,labels=clf.classes_,output_dict=True,zero_division=0)
    report={
      "trainFiles":ntr,"validationFiles":nv,
      "trainCounts":dict(ctr),"validationCounts":dict(cva),
      "classes":clf.classes_.tolist(),
      "featureDim":int(X.shape[1]),
      "validationReport":rep,
      "validationConfusion":confusion_matrix(vy,pred,labels=clf.classes_).tolist(),
      "validationAccuracy":float(np.mean(pred==vy)),
    }
    out={
      "schema":1,
      "source":{"dataset":"Groove MIDI Dataset v1.0.0","split":"train","style":"rock+punk","license":"CC BY 4.0",
                "embedding":"frozen ADTOF final BiGRU"},
      "classes":clf.classes_.tolist(),"featureDim":int(X.shape[1]),
      "mean":scaler.mean_.tolist(),"scale":scaler.scale_.tolist(),
      "coef":clf.coef_.tolist(),"intercept":clf.intercept_.tolist(),
      "training":report
    }
    op=Path(args.output);op.parent.mkdir(parents=True,exist_ok=True)
    op.write_text(json.dumps(out,indent=2)+"\n")
    (EXP/"results-gmd-adtof-metal-logreg.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
