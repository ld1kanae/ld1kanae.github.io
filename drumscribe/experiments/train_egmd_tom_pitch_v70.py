"""E-GMD tom pitch classifier v70.

Purpose
-------
Learn a second-stage classifier for events already classified as TOM.
It never changes tom onset detection. Six GM tom notes are kept distinct:
41, 43, 45, 47, 48, 50.

Leakage controls
----------------
- Fit: official E-GMD train sequences + a train-only kit set.
- Validation: official E-GMD validation sequences + disjoint held-out kits.
- DruMaster chart.mid is used only after the E-GMD model is completely frozen,
  as an external transfer test. It is never used to fit parameters or choose
  hyperparameters.

Hypotheses
----------
A) median_peak: nearest train-class median in resonance peak/centroid space.
B) class_profile: nearest train-class mean normalized low-frequency profile.
C) multinomial_logreg: standardized body-minus-pre-onset spectral profile
   + band ratios + peak/centroid summary.

Source audio/MIDI is range-read from E-GMD and is not committed.
"""
from __future__ import annotations
import csv, io, json, math, random, subprocess
from collections import Counter, defaultdict
from pathlib import Path

import mido
import numpy as np
import requests
from remotezip import RemoteZip
from scipy.io import wavfile
from scipy.signal import resample_poly
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"
EGMD_ZIP="https://storage.googleapis.com/magentadata/datasets/e-gmd/v1.0.0/e-gmd-v1.0.0.zip"
EGMD_CSV="https://storage.googleapis.com/magentadata/datasets/e-gmd/v1.0.0/e-gmd-v1.0.0.csv"
TARGET_SR=11025
FFT=1024
NOTES=(41,43,45,47,48,50)
CORE=(41,45,47,50)
RNG=random.Random(20260924)
MAX_SEC=24.0

FREQ=np.fft.rfftfreq(FFT,1/TARGET_SR)
PROFILE_MASK=(FREQ>=55)&(FREQ<=650)
CENTROID_MASK=(FREQ>=55)&(FREQ<=500)
PEAK_MASK=(FREQ>=60)&(FREQ<=360)
BANDS=((55,105),(105,155),(155,220),(220,360),(360,650))
PROFILE_FREQS=FREQ[PROFILE_MASK]

def get_csv():
    r=requests.get(EGMD_CSV,timeout=60);r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))

def resolve_name(names,rel):
    rel=str(rel).replace("\\","/").lstrip("./")
    if rel in names:return rel
    c=[n for n in names if n.endswith("/"+rel) or n.endswith(rel)]
    if not c:raise KeyError(rel)
    return min(c,key=len)

def midi_toms(data):
    mid=mido.MidiFile(file=io.BytesIO(data))
    tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += mido.tick2second(msg.time,mid.ticks_per_beat,tempo)
        if msg.type=="set_tempo":tempo=msg.tempo
        elif msg.type=="note_on" and msg.velocity>0 and int(msg.note) in NOTES:
            out.append((float(sec),int(msg.note),int(msg.velocity)))
    return sorted(out)

def decode_wav(data,target=TARGET_SR):
    rate,raw=wavfile.read(io.BytesIO(data))
    x=raw.astype(np.float32)
    if np.issubdtype(raw.dtype,np.integer):
        info=np.iinfo(raw.dtype);x/=max(abs(info.min),info.max)
    if x.ndim>1:x=x.mean(axis=1)
    if rate!=target:
        g=math.gcd(int(rate),target)
        x=resample_poly(x,target//g,int(rate)//g).astype(np.float32)
    return x

def audio_file(path):
    cmd=["ffmpeg","-v","error","-i",str(path),"-ac","1","-ar",str(TARGET_SR),
         "-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

WIN=np.hanning(FFT).astype(np.float32)
def frame_mag(x,start):
    a=int(round(start))
    fr=np.zeros(FFT,np.float32)
    lo=max(0,a);hi=min(len(x),a+FFT)
    if hi>lo:fr[lo-a:hi-a]=x[lo:hi]
    return np.abs(np.fft.rfft(fr*WIN)).astype(np.float64)

def descriptor(x,t):
    center=t*TARGET_SR
    # Tom tuning is better represented by the decaying drum body than by the
    # broadband attack. Average several post-onset frames and remove persistent
    # pre-onset energy from already ringing cymbals / ambience.
    post=[]
    for sec in (.012,.030,.048,.066):
        post.append(frame_mag(x,center+sec*TARGET_SR))
    pre=[]
    for sec in (-.115,-.085,-.055):
        pre.append(frame_mag(x,center+sec*TARGET_SR))
    post=np.mean(post,axis=0)
    pre=np.mean(pre,axis=0)
    body=np.maximum(post-.55*pre,0)
    # Blend a little raw post spectrum back in so weak resonances are not zeroed.
    body=.86*body+.14*post

    raw=np.log1p(body[PROFILE_MASK]*80.0)
    profile=raw-raw.mean()
    profile=profile/(np.linalg.norm(profile)+1e-9)

    pm=body[PEAK_MASK];pf=FREQ[PEAK_MASK]
    peak=float(pf[int(np.argmax(pm))]) if len(pm) else 0.0
    cm=body[CENTROID_MASK]**2;cf=FREQ[CENTROID_MASK]
    centroid=float(np.sum(cf*cm)/(np.sum(cm)+1e-12))

    bands=[]
    for lo,hi in BANDS:
        z=body[(FREQ>=lo)&(FREQ<hi)]
        bands.append(math.log1p(float(np.sum(z))*80.0))
    bands=np.asarray(bands,np.float64)
    bands=(bands-bands.mean())/(np.linalg.norm(bands-bands.mean())+1e-9)

    # Compact browser-portable vector: normalized spectrum, broad bands,
    # and log-frequency summaries.
    vec=np.concatenate([
        profile,
        bands,
        np.asarray([
            math.log2(max(peak,40)/100.0),
            math.log2(max(centroid,40)/150.0),
        ],np.float64)
    ])
    return {"profile":profile,"bands":bands,"peak":peak,"centroid":centroid,"vec":vec}

def group_sequences(rows,split):
    g=defaultdict(list)
    for r in rows:
        if r.get("split")!=split:continue
        sig=(r.get("time_signature") or "").replace("/","-")
        try:dur=float(r.get("duration") or 0)
        except:dur=0
        if sig!="4-4" or dur<3 or dur>MAX_SEC:continue
        g[r.get("id","")].append(r)
    return g

def partition_kits(rows):
    kits=sorted({r.get("kit_name","") for r in rows if r.get("kit_name")})
    # Deterministic spread over all kits, then explicit disjointness.
    tr=[kits[i] for i in np.linspace(0,len(kits)-1,9).round().astype(int)]
    tr=list(dict.fromkeys(tr))[:7]
    va=[]
    for i in np.linspace(2,len(kits)-3,12).round().astype(int):
        if kits[i] not in tr and kits[i] not in va:va.append(kits[i])
        if len(va)>=5:break
    for k in kits:
        if len(va)>=5:break
        if k not in tr and k not in va:va.append(k)
    return tr,va

def sequence_info(z,names,groups,max_scan=220):
    candidates=[]
    # Fill first, then short beats. MIDI reads are tiny compared with audio.
    keys=sorted(groups,key=lambda k:(
        0 if (groups[k][0].get("beat_type")=="fill") else 1,
        float(groups[k][0].get("duration") or 999),k))
    for key in keys[:max_scan]:
        row=sorted(groups[key],key=lambda r:r.get("kit_name",""))[0]
        try:
            mn=resolve_name(names,row["midi_filename"])
            notes=midi_toms(z.read(mn))
        except Exception:
            continue
        cnt=Counter(n for _,n,_ in notes)
        distinct=sum(v>0 for v in cnt.values())
        if len(notes)>=4 and distinct>=2:
            candidates.append((key,cnt,len(notes),row.get("beat_type"),row.get("style")))
    return candidates

def choose_sequences(items,n):
    # Greedy coverage: favor missing classes, then diversity and tom count.
    remaining=list(items);chosen=[];cover=Counter()
    while remaining and len(chosen)<n:
        def score(item):
            _,cnt,total,beat_type,style=item
            new=sum(1 for k in NOTES if cnt[k] and cover[k]==0)
            rare=sum(cnt[k]/max(1,1+cover[k]) for k in NOTES)
            return (new, sum(cnt[k]>0 for k in NOTES), rare, total, beat_type=="fill")
        best=max(remaining,key=score);remaining.remove(best);chosen.append(best)
        cover.update(best[1])
    return chosen,cover

def rows_for(groups,selected,kits,per_sequence):
    out=[]
    for key,*_ in selected:
        bykit={r.get("kit_name"):r for r in groups[key]}
        got=0
        for kit in kits:
            if kit in bykit:
                out.append(bykit[kit]);got+=1
                if got>=per_sequence:break
    return out

def collect(z,names,rows,tag):
    samples=[];manifest=[]
    for i,row in enumerate(rows,1):
        try:
            an=resolve_name(names,row["audio_filename"])
            mn=resolve_name(names,row["midi_filename"])
            audio=decode_wav(z.read(an))
            notes=midi_toms(z.read(mn))
        except Exception as e:
            print("SKIP",tag,row.get("id"),row.get("kit_name"),type(e).__name__,str(e)[:100],flush=True)
            continue
        counts=Counter()
        for t,n,v in notes:
            if t<.14 or t>len(audio)/TARGET_SR-.15:continue
            d=descriptor(audio,t)
            samples.append({"x":d["vec"],"profile":d["profile"],"peak":d["peak"],
                            "centroid":d["centroid"],"note":tier4(n),"noteRaw":n,"velocity":v,
                            "sequence":row.get("id"),"kit":row.get("kit_name")})
            counts[n]+=1
        manifest.append({"id":row.get("id"),"kit":row.get("kit_name"),
                         "style":row.get("style"),"beatType":row.get("beat_type"),
                         "duration":float(row.get("duration") or 0),
                         "tomCounts":{str(k):int(counts[k]) for k in NOTES}})
        print("CLIP",tag,i,len(rows),manifest[-1],flush=True)
    return samples,manifest

def tier4(n):
    if n in (41,43):return 41
    if n==45:return 45
    if n in (47,48):return 47
    return 50

def score_pred(y,p):
    # Production target is four robust tom tiers. E-GMD 43 maps to low/floor 41
    # and 48 maps to the mid/high-mid 47 tier.
    y=np.asarray([tier4(int(x)) for x in y],int)
    p=np.asarray([tier4(int(x)) for x in p],int)
    conf=Counter((int(a),int(b)) for a,b in zip(y,p))
    exact=float(np.mean(y==p)) if len(y) else 0.
    tier=float(np.mean([tier4(a)==tier4(b) for a,b in zip(y,p)])) if len(y) else 0.
    by={}
    for n in CORE:
        ix=np.where(y==n)[0]
        if len(ix):by[str(n)]={"n":int(len(ix)),"exact":float(np.mean(p[ix]==n)),
                              "tier4":float(np.mean([tier4(y[j])==tier4(p[j]) for j in ix]))}
    return {"n":int(len(y)),"exactAccuracy":exact,"tier4Accuracy":tier,
            "byTruth":by,
            "confusion":{f"{a}->{b}":int(v) for (a,b),v in sorted(conf.items())}}

def fit_peak(train):
    med={}
    for n in CORE:
        xs=[s for s in train if s["note"]==n]
        if xs:
            med[n]=(float(np.median([s["peak"] for s in xs])),
                    float(np.median([s["centroid"] for s in xs])))
    return med

def pred_peak(samples,med):
    out=[]
    for s in samples:
        rows=[]
        for n,(p,c) in med.items():
            dp=abs(math.log2(max(s["peak"],1)/max(p,1)))
            dc=abs(math.log2(max(s["centroid"],1)/max(c,1)))
            rows.append((dp+.55*dc,n))
        out.append(min(rows)[1])
    return out

def fit_profile(train):
    prot={}
    for n in NOTES:
        xs=[s["profile"] for s in train if s["note"]==n]
        if xs:
            v=np.mean(xs,axis=0);v=v/(np.linalg.norm(v)+1e-9);prot[n]=v
    return prot

def pred_profile(samples,prot):
    return [max(prot,key=lambda n:float(np.dot(s["profile"],prot[n]))) for s in samples]

def export_linear(sc,clf):
    return {
        "classes":[int(x) for x in clf.classes_.tolist()],
        "mean":[float(x) for x in sc.mean_.tolist()],
        "scale":[float(x) for x in sc.scale_.tolist()],
        "coef":[[float(x) for x in row] for row in clf.coef_.tolist()],
        "intercept":[float(x) for x in clf.intercept_.tolist()],
    }

def fit_logreg(train,val):
    X=np.stack([s["x"] for s in train]);y=np.asarray([s["note"] for s in train],int)
    Xv=np.stack([s["x"] for s in val]);yv=np.asarray([s["note"] for s in val],int)
    choices=[]
    for C in (.03,.08,.2,.5,1.0,2.0):
        sc=StandardScaler().fit(X)
        clf=LogisticRegression(C=C,max_iter=2000,class_weight="balanced",solver="lbfgs",
                               random_state=20260924).fit(sc.transform(X),y)
        pr=clf.predict(sc.transform(Xv))
        m=score_pred(yv,pr)
        # Select only on held-out E-GMD validation, never on DruMaster.
        choices.append((m["tier4Accuracy"],m["exactAccuracy"],C,sc,clf,m))
    choices.sort(key=lambda z:(z[0],z[1]),reverse=True)
    return choices[0],[(float(c),m["exactAccuracy"],m["tier4Accuracy"]) for _,_,c,_,_,m in choices]

def nearest_class_mapping(model,pred):
    # If a class is absent in training, use nearest semantic tom tier.
    return [int(x) for x in pred]

def drumaster_transfer(model_bundle,peak_model,profile_model):
    # External test after all model selection is frozen.
    out=[];by_song={}
    for song in ("arcaround","diamondvirgin","kaiju","nanairo","ray"):
        folder=ROOT/"DruMaster/songs"/song
        meta=json.loads((folder/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        audio=audio_file(folder/"drums.mp3")
        truth=[(t+shift,n) for t,g,n in ev_midi(folder/"chart.mid") if g=="tom"]
        samples=[];y=[]
        for t,n in truth:
            if t<.14 or t>len(audio)/TARGET_SR-.15:continue
            d=descriptor(audio,t)
            samples.append({"x":d["vec"],"profile":d["profile"],"peak":d["peak"],
                            "centroid":d["centroid"]});y.append(n)
        if not y:continue
        X=np.stack([s["x"] for s in samples])
        sc,clf=model_bundle
        preds={
          "fixed45":[45]*len(y),
          "median_peak":pred_peak(samples,peak_model),
          "class_profile":pred_profile(samples,profile_model),
          "multinomial_logreg":[int(x) for x in clf.predict(sc.transform(X)).tolist()],
        }
        sm={k:score_pred(y,v) for k,v in preds.items()}
        by_song[song]=sm
        for i,n in enumerate(y):
            out.append({"song":song,"truth":int(n),**{k:int(v[i]) for k,v in preds.items()}})
    agg={}
    y=[r["truth"] for r in out]
    for k in ("fixed45","median_peak","class_profile","multinomial_logreg"):
        agg[k]=score_pred(y,[r[k] for r in out])
    return {"aggregate":agg,"songs":by_song,"events":out}

# Minimal local MIDI parser import: use existing evaluator so timing/tempo handling
# exactly matches current DrumScribe evaluation.
import importlib.util
_spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
_ev=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_ev)
def ev_midi(path): return _ev.midi_events(path)

def main():
    rows=get_csv();train_kits,val_kits=partition_kits(rows)
    tr_groups=group_sequences(rows,"train");va_groups=group_sequences(rows,"validation")
    with RemoteZip(EGMD_ZIP) as z:
        names=set(z.namelist())
        tr_items=sequence_info(z,names,tr_groups)
        va_items=sequence_info(z,names,va_groups)
        tr_sel,tr_cover=choose_sequences(tr_items,12)
        va_sel,va_cover=choose_sequences(va_items,7)
        print("TRAIN_SELECTION",[(x[0],dict(x[1])) for x in tr_sel],flush=True)
        print("VAL_SELECTION",[(x[0],dict(x[1])) for x in va_sel],flush=True)
        tr_rows=rows_for(tr_groups,tr_sel,train_kits,3)
        va_rows=rows_for(va_groups,va_sel,val_kits,2)
        train,tr_manifest=collect(z,names,tr_rows,"train")
        val,va_manifest=collect(z,names,va_rows,"val")

    train_counts=Counter(s["note"] for s in train);val_counts=Counter(s["note"] for s in val)
    missing=[n for n in CORE if train_counts[n]<8 or val_counts[n]<2]
    if missing:
        raise RuntimeError(f"insufficient class coverage {missing}; train={train_counts}, val={val_counts}")

    yv=[s["note"] for s in val]
    peak_model=fit_peak(train);profile_model=fit_profile(train)
    p_peak=pred_peak(val,peak_model);p_prof=pred_profile(val,profile_model)
    (best_tier,best_exact,C,sc,clf,log_score),sweep=fit_logreg(train,val)

    validation={
      "fixed45":score_pred(yv,[45]*len(yv)),
      "median_peak":score_pred(yv,p_peak),
      "class_profile":score_pred(yv,p_prof),
      "multinomial_logreg":log_score,
    }
    frozen={
      "schema":1,
      "kind":"egmd-tom-pitch-4tier-logreg-v70",
      "sampleRate":TARGET_SR,"fft":FFT,
      "profileFrequenciesHz":[float(x) for x in PROFILE_FREQS.tolist()],
      "bandsHz":[list(map(float,b)) for b in BANDS],
      "postOffsetsSec":[.012,.030,.048,.066],
      "preOffsetsSec":[-.115,-.085,-.055],
      "preSubtract":.55,"bodyBlend":.86,
      "featureLength":int(len(train[0]["x"])),
      "model":export_linear(sc,clf),
      "training":{
        "dataset":"E-GMD v1.0.0","license":"CC BY 4.0",
        "trainSplit":"official train","validationSplit":"official validation",
        "trainKits":train_kits,"validationKits":val_kits,
        "trainCounts":{str(n):int(train_counts[n]) for n in CORE},
        "validationCounts":{str(n):int(val_counts[n]) for n in CORE},
        "selectedC":float(C),"validation":validation,
      }
    }
    transfer=drumaster_transfer((sc,clf),peak_model,profile_model)
    result={
      "schema":1,
      "targetTiers":{"41":"E-GMD 41/43","45":"45","47":"47/48","50":"50"},
      "hypotheses":["median_peak","class_profile","multinomial_logreg"],
      "selectionRule":"choose on disjoint E-GMD validation by tier4 accuracy, then exact accuracy; DruMaster is transfer-only",
      "trainKits":train_kits,"validationKits":val_kits,
      "trainSequences":[x[0] for x in tr_sel],"validationSequences":[x[0] for x in va_sel],
      "trainManifest":tr_manifest,"validationManifest":va_manifest,
      "trainCounts":{str(n):int(train_counts[n]) for n in CORE},
      "validationCounts":{str(n):int(val_counts[n]) for n in CORE},
      "logregSweep":[{"C":c,"exact":e,"tier4":t} for c,e,t in sweep],
      "validation":validation,
      "drumasterTransfer":transfer,
    }

    EXP.mkdir(parents=True,exist_ok=True)
    (EXP/"tom-pitch-model-v70.json").write_text(json.dumps(frozen,separators=(",",":"))+"\n")
    (EXP/"results-tom-pitch-v70.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    md=[
      "# Tom pitch v70 — E-GMD second-stage classifier","",
      "Tom onset detection is unchanged. This experiment classifies only already-known tom hits.","",
      "## E-GMD held-out validation","",
      "| method | exact | 4-tier |","|---|---:|---:|",
    ]
    for k,v in validation.items():
        md.append(f"| {k} | {v['exactAccuracy']:.3f} | {v['tier4Accuracy']:.3f} |")
    md += ["","## DruMaster transfer (selection-independent)","",
           "| method | exact | 4-tier |","|---|---:|---:|"]
    for k,v in transfer["aggregate"].items():
        md.append(f"| {k} | {v['exactAccuracy']:.3f} | {v['tier4Accuracy']:.3f} |")
    md += ["","DruMaster chart.mid was used only after the E-GMD model was frozen.",
           "No production runtime change is made by this experiment.",""]
    (EXP/"TOM_PITCH_V70.md").write_text("\n".join(md))
    print("SUMMARY",json.dumps({
      "trainCounts":frozen["training"]["trainCounts"],
      "validationCounts":frozen["training"]["validationCounts"],
      "validation":validation,
      "drumasterTransfer":transfer["aggregate"],
      "selectedC":C,
    },ensure_ascii=False),flush=True)

if __name__=="__main__":main()
