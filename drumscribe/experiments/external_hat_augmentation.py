"""External open/closed hi-hat augmentation using Magenta GMD / E-GMD.

The goal is deliberately narrow: improve the already-working open-hat promoter
without changing hat onset detection.

Conditions compared on the same held-out DruMaster folds:
  A) songs_only        : current five-song training only
  B) songs_plus_gmd    : + aligned GMD audio/MIDI examples
  C) songs_plus_egmd   : + the same kind of examples across multiple E-GMD kits
  D) songs_plus_both   : + both external sources

For every held-out DruMaster song, its chart.mid is excluded from model fitting.
The external examples are CC BY 4.0 and are used only as training augmentation.

To avoid downloading E-GMD's 90 GB archive, RemoteZip HTTP range requests fetch
only selected short WAV/MIDI members.
"""
from __future__ import annotations

import csv
import io
import importlib.util
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import requests
from remotezip import RemoteZip
from scipy.io import wavfile
from scipy.signal import resample_poly
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
SR=44100
THRESHOLD=.55
MAX_EXT_PER_CLASS=700
MAX_CLIP_SEC=35.0
TARGET_GMD_SEQS=10
TARGET_EGMD_SEQS=5
TARGET_EGMD_KITS=6
RNG=random.Random(56046)

GMD_ZIP="https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0.zip"
EGMD_ZIP="https://storage.googleapis.com/magentadata/datasets/e-gmd/v1.0.0/e-gmd-v1.0.0.zip"
EGMD_CSV="https://storage.googleapis.com/magentadata/datasets/e-gmd/v1.0.0/e-gmd-v1.0.0.csv"

OPEN_PITCHES={26,46}
CLOSED_PITCHES={22,42}


def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

sn=loadmod("openhat_external_base",EXP/"open_hat_songnorm_loo.py")
oh=sn.oh


def variable(data,i):
    value=0
    while True:
        b=data[i];i+=1;value=(value<<7)|(b&127)
        if not b&128:return value,i


def midi_notes_bytes(data: bytes):
    """Return (sec,pitch,velocity) for percussion channel from a standard MIDI."""
    assert data[:4]==b"MThd"
    division=int.from_bytes(data[12:14],"big")
    pos=8+int.from_bytes(data[4:8],"big")
    tracks=[]
    while pos+8<=len(data) and data[pos:pos+4]==b"MTrk":
        size=int.from_bytes(data[pos+4:pos+8],"big")
        end=pos+8+size;i=pos+8;tick=0;running=0;notes=[];tempos=[]
        while i<end:
            delta,i=variable(data,i);tick+=delta
            status=data[i]
            if status&128:i+=1;running=status
            else:status=running
            if status==255:
                typ=data[i];i+=1;n,i=variable(data,i)
                if typ==81 and n==3:tempos.append((tick,int.from_bytes(data[i:i+3],"big")))
                i+=n;continue
            if status in (240,247):
                n,i=variable(data,i);i+=n;continue
            op=status&240;ch=status&15
            n=1 if op in (192,208) else 2
            pitch=data[i];vel=data[i+1] if n==2 else 0;i+=n
            if op==144 and vel>0:notes.append((tick,pitch,vel,ch))
        tracks.append((notes,tempos));pos=end
    tempos=sorted([x for _,tt in tracks for x in tt] or [(0,500000)])
    if tempos[0][0]!=0:tempos.insert(0,(0,500000))
    starts=[0.0]
    for (t,us),(t2,_) in zip(tempos,tempos[1:]):
        starts.append(starts[-1]+(t2-t)*us/1e6/division)
    allnotes=[n for ns,_ in tracks for n in ns]
    channels=Counter(c for _,p,v,c in allnotes if 22<=p<=59)
    use=9 if channels[9] else (channels.most_common(1)[0][0] if channels else 9)
    tt=[t for t,_ in tempos]
    out=[]
    for tick,pitch,vel,ch in allnotes:
        if ch!=use:continue
        j=int(np.searchsorted(tt,tick,side="right")-1)
        sec=starts[j]+(tick-tempos[j][0])*tempos[j][1]/1e6/division
        out.append((sec,pitch,vel))
    return sorted(out)


def decode_wav(data: bytes):
    rate,raw=wavfile.read(io.BytesIO(data))
    was_integer=np.issubdtype(raw.dtype,np.integer)
    if was_integer:
        info=np.iinfo(raw.dtype);scale=max(abs(info.min),abs(info.max))
    x=raw.astype(np.float64)
    if x.ndim>1:x=x.mean(axis=1)
    if was_integer:
        x=x/scale
    else:
        peak=max(1.0,float(np.max(np.abs(x))) if len(x) else 1.0);x=x/peak
    if rate!=SR:
        g=math.gcd(int(rate),SR);x=resample_poly(x,SR//g,int(rate)//g)
    return np.asarray(x,dtype=np.float32)


def resolve_name(names,rel):
    rel=str(rel).replace("\\","/").lstrip("./")
    if rel in names:return rel
    suffix="/"+rel
    candidates=[n for n in names if n.endswith(suffix) or n.endswith(rel)]
    if not candidates:
        raise KeyError(f"archive member not found: {rel}")
    return min(candidates,key=len)


def read_csv_bytes(data: bytes):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def robust_rows(X):
    X=np.asarray(X,dtype=np.float32)
    if not len(X):return X
    med=np.median(X,axis=0);q1=np.percentile(X,25,axis=0);q3=np.percentile(X,75,axis=0)
    scale=np.maximum(q3-q1,1e-3)
    return np.clip((X-med)/scale,-8,8).astype(np.float32)


def acoustic_rows(audio,notes):
    hats=[(t,1 if p in OPEN_PITCHES else 0) for t,p,v in notes if p in OPEN_PITCHES|CLOSED_PITCHES]
    if len(hats)<4:return np.zeros((0,26),np.float32),np.zeros(0,np.int8)
    w=oh.workspace() if hasattr(oh,"workspace") else None
    # Python reference feature implementation lives in open_hat_loo.py.
    X=np.stack([oh.timbre_features(audio,t) for t,_ in hats])
    y=np.asarray([label for _,label in hats],dtype=np.int8)
    return robust_rows(X),y


def balanced_cap(X,y,limit=MAX_EXT_PER_CLASS,seed=0):
    rng=np.random.default_rng(seed);pick=[]
    for cls in (0,1):
        ids=np.flatnonzero(y==cls)
        if len(ids)>limit:ids=rng.choice(ids,limit,replace=False)
        pick.extend(map(int,ids))
    pick=np.asarray(sorted(pick),dtype=int)
    return X[pick],y[pick]


def counts(notes):
    return {
      "open":sum(p in OPEN_PITCHES for _,p,_ in notes),
      "closed":sum(p in CLOSED_PITCHES for _,p,_ in notes),
      "pedal":sum(p==44 for _,p,_ in notes)
    }


def suitable(row):
    try:duration=float(row.get("duration") or 0)
    except:duration=0
    sig=(row.get("time_signature") or "").replace("/","-")
    return row.get("split")=="train" and duration>2 and duration<=MAX_CLIP_SEC and sig in ("4-4","")


def select_gmd():
    print("OPEN GMD REMOTE ZIP",flush=True)
    with RemoteZip(GMD_ZIP) as z:
        names=z.namelist();name_set=set(names)
        info_name=min([n for n in names if n.endswith("info.csv")],key=len)
        rows=read_csv_bytes(z.read(info_name))
        candidates=[r for r in rows if suitable(r) and (r.get("beat_type") or "")=="beat"]
        # deterministic style diversity
        candidates.sort(key=lambda r:((r.get("style") or ""),float(r.get("duration") or 0),r.get("id") or ""))
        chosen=[];seen_styles=set()
        for r in candidates:
            style=(r.get("style") or "").split("/")[0]
            midi_name=resolve_name(name_set,r["midi_filename"])
            notes=midi_notes_bytes(z.read(midi_name));c=counts(notes)
            if c["open"]>=4 and c["closed"]>=8 and (style not in seen_styles or len(chosen)>=6):
                chosen.append((r,notes,midi_name));seen_styles.add(style)
            if len(chosen)>=TARGET_GMD_SEQS:break
        Xs=[];ys=[];manifest=[]
        for idx,(r,notes,midi_name) in enumerate(chosen):
            audio_name=resolve_name(name_set,r["audio_filename"])
            raw=z.read(audio_name);audio=decode_wav(raw)
            X,y=acoustic_rows(audio,notes)
            Xs.append(X);ys.append(y)
            manifest.append({"id":r.get("id"),"style":r.get("style"),"duration":r.get("duration"),
                             "midi":midi_name,"audio":audio_name,"bytes":len(raw),"labels":dict(Counter(map(int,y)))})
            print("GMD",idx+1,len(chosen),manifest[-1],flush=True)
    if not Xs:raise RuntimeError("no usable GMD examples")
    X=np.concatenate(Xs);y=np.concatenate(ys)
    return (*balanced_cap(X,y,seed=101),manifest)


def egmd_metadata():
    r=requests.get(EGMD_CSV,timeout=60);r.raise_for_status()
    return read_csv_bytes(r.content)


def choose_egmd_sequence_rows(rows,z,name_set):
    candidates=[r for r in rows if suitable(r) and (r.get("beat_type") or "")=="beat"]
    by_id=defaultdict(list)
    for r in candidates:by_id[r.get("id","")].append(r)
    keys=sorted(by_id,key=lambda k:(by_id[k][0].get("style",""),float(by_id[k][0].get("duration") or 0),k))
    chosen=[]
    for key in keys:
        group=by_id[key]
        probe=sorted(group,key=lambda r:r.get("kit_name",""))[0]
        try:
            midi_name=resolve_name(name_set,probe["midi_filename"])
            notes=midi_notes_bytes(z.read(midi_name))
        except Exception as e:
            print("EGMD MIDI SKIP",key,e,flush=True);continue
        c=counts(notes)
        if c["open"]>=4 and c["closed"]>=8:
            chosen.append(group)
        if len(chosen)>=TARGET_EGMD_SEQS:break
    return chosen


def select_egmd():
    rows=egmd_metadata()
    kits=sorted({r.get("kit_name","") for r in rows if r.get("kit_name")})
    if len(kits)<TARGET_EGMD_KITS:chosen_kits=kits
    else:
        ids=np.linspace(0,len(kits)-1,TARGET_EGMD_KITS).round().astype(int)
        chosen_kits=[kits[i] for i in ids]
    print("EGMD KITS",chosen_kits,flush=True)
    with RemoteZip(EGMD_ZIP) as z:
        names=z.namelist();name_set=set(names)
        seqs=choose_egmd_sequence_rows(rows,z,name_set)
        Xs=[];ys=[];manifest=[]
        for si,group in enumerate(seqs):
            bykit={r.get("kit_name"):r for r in group}
            kit_rows=[bykit[k] for k in chosen_kits if k in bykit]
            if len(kit_rows)<max(2,TARGET_EGMD_KITS//2):
                # Fall back to deterministic available kits for this sequence.
                kit_rows=sorted(group,key=lambda r:r.get("kit_name",""))[:TARGET_EGMD_KITS]
            for r in kit_rows:
                midi_name=resolve_name(name_set,r["midi_filename"])
                notes=midi_notes_bytes(z.read(midi_name))
                audio_name=resolve_name(name_set,r["audio_filename"])
                raw=z.read(audio_name);audio=decode_wav(raw)
                X,y=acoustic_rows(audio,notes)
                Xs.append(X);ys.append(y)
                item={"sequence":r.get("id"),"style":r.get("style"),"kit":r.get("kit_name"),
                      "duration":r.get("duration"),"midi":midi_name,"audio":audio_name,
                      "bytes":len(raw),"labels":dict(Counter(map(int,y)))}
                manifest.append(item);print("EGMD",len(manifest),item,flush=True)
    if not Xs:raise RuntimeError("no usable E-GMD examples")
    X=np.concatenate(Xs);y=np.concatenate(ys)
    return (*balanced_cap(X,y,seed=202),manifest)


def train_model(data,held,extra):
    X=[data[s]["X"]["timbre_norm"] for s in SONGS if s!=held]
    y=[(data[s]["y"]==1).astype(np.int8) for s in SONGS if s!=held]
    if extra is not None:
        X.append(extra[0]);y.append(extra[1])
    X=np.concatenate(X);y=np.concatenate(y)
    model=ExtraTreesClassifier(n_estimators=320,max_depth=13,min_samples_leaf=4,
        class_weight="balanced",random_state=560,n_jobs=-1).fit(X,y)
    return model


def score_song(data,s,model):
    X=data[s]["X"]["timbre_norm"]
    p=model.predict_proba(X)[:,list(model.classes_).index(1)]
    op=[t for t,v in zip(data[s]["hats"],p) if v>=THRESHOLD]
    cl=[t for t,v in zip(data[s]["hats"],p) if v<THRESHOLD]
    return oh.articulation_metrics(op,cl,data[s]["refs"]),p


def aggregate(per):
    z=Counter()
    for m in per.values():
        for c in ("open","closed"):
            q=m[c];z[f"{c}t"]+=q["tp"];z[f"{c}p"]+=q["predicted"];z[f"{c}r"]+=q["reference"]
    out={}
    for c in ("open","closed"):
        tp,p,r=z[f"{c}t"],z[f"{c}p"],z[f"{c}r"]
        out[c]={"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
                "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"])
    return out


def evaluate(data,name,extra):
    per={};probs={}
    for held in SONGS:
        model=train_model(data,held,extra)
        per[held],probs[held]=score_song(data,held,model)
    return {"name":name,"summary":aggregate(per),"songs":per}


def main():
    data=sn.prepare()
    gX,gY,gManifest=select_gmd()
    eX,eY,eManifest=select_egmd()
    bothX=np.concatenate([gX,eX]);bothY=np.concatenate([gY,eY])
    # Keep combined external source from swamping DruMaster.
    bothX,bothY=balanced_cap(bothX,bothY,limit=MAX_EXT_PER_CLASS,seed=303)
    variants={}
    for name,extra in [
      ("songs_only",None),
      ("songs_plus_gmd",(gX,gY)),
      ("songs_plus_egmd",(eX,eY)),
      ("songs_plus_both",(bothX,bothY)),
    ]:
        q=evaluate(data,name,extra);variants[name]=q
        print("RESULT",name,json.dumps(q["summary"],ensure_ascii=False),flush=True)
    base=variants["songs_only"]["summary"]
    # Deployment guard: external candidate may replace base only if open precision
    # does not fall > .02, closed F1 does not fall > .01, and macro F1 improves.
    def eligible(v):
        s=v["summary"]
        return (s["open"]["precision"]>=base["open"]["precision"]-.02 and
                s["closed"]["f1"]>=base["closed"]["f1"]-.01 and
                s["macroF1"]>base["macroF1"])
    winners=[v for k,v in variants.items() if k!="songs_only" and eligible(v)]
    best=max(winners,key=lambda v:v["summary"]["macroF1"]) if winners else variants["songs_only"]
    result={
      "schema":1,
      "threshold":THRESHOLD,
      "externalCapPerClass":MAX_EXT_PER_CLASS,
      "sources":{
        "gmd":{"license":"CC BY 4.0","url":GMD_ZIP,"rows":len(gY),"open":int(gY.sum()),"closed":int((gY==0).sum()),"clips":gManifest},
        "egmd":{"license":"CC BY 4.0","url":EGMD_ZIP,"rows":len(eY),"open":int(eY.sum()),"closed":int((eY==0).sum()),"clips":eManifest}
      },
      "variants":variants,
      "guard":{
        "base":"songs_only","maxOpenPrecisionDrop":.02,"maxClosedF1Drop":.01,
        "requireMacroF1Improvement":True
      },
      "retained":best["name"],
      "retainedSummary":best["summary"]
    }
    (EXP/"results-open-hat-external-augmentation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("RETAINED",best["name"],json.dumps(best["summary"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
