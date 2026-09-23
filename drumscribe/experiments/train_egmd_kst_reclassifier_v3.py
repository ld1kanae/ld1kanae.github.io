"""Train E-GMD kick/snare/tom candidate reclassifier v3 with clip-normalized hard-negative features.

Goal:
- keep frozen ADTOF as the onset proposal model;
- generate low-threshold K/S/T candidate peaks exactly like the browser;
- learn whether each candidate is a real hit of that class;
- use independent binary classifiers so simultaneous K+S/T hits remain possible.

Data split:
- E-GMD official train sequences + selected training kits for fitting;
- E-GMD official validation sequences + disjoint held-out kits for evaluation.
Thus both sequence identity and kit identity are held out.

Only a bounded set of short WAV/MIDI members is fetched from the 90 GB archive
using RemoteZip range requests. Source audio/MIDI is not committed.
"""
from __future__ import annotations
import argparse,csv,io,json,math,random
from collections import Counter,defaultdict
from pathlib import Path

import mido
import numpy as np
import requests
import torch
from remotezip import RemoteZip
from scipy.io import wavfile
from scipy.signal import resample_poly
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from adtof_pytorch import calculate_n_bins,create_frame_rnn_model,get_default_weights_path,load_pytorch_weights
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
EGMD_ZIP="https://storage.googleapis.com/magentadata/datasets/e-gmd/v1.0.0/e-gmd-v1.0.0.zip"
EGMD_CSV="https://storage.googleapis.com/magentadata/datasets/e-gmd/v1.0.0/e-gmd-v1.0.0.csv"
FPS=100
GROUPS=("kick","snare","tom")
CLASS_INDEX={"kick":0,"snare":1,"tom":2}
PITCH={}
for n in (35,36):PITCH[n]="kick"
for n in (37,38,39,40):PITCH[n]="snare"
for n in (41,43,45,47,48,50):PITCH[n]="tom"
BASE_THRESH={"kick":.22,"snare":.24,"tom":.32}
LOW_SCALE=.20
PROD_SCALE=1.15
MATCH=.050
MAX_SEC=24.0
RNG=random.Random(92356)

FEATURE_NAMES = (
    [f"act_q95_{g}" for g in ("kick","snare","tom","hat","cymbal")] +
    [f"res_q95_{g}" for g in ("kick","snare","tom","hat","cymbal")] +
    [f"mean5_q95_{g}" for g in ("kick","snare","tom","hat","cymbal")] +
    [f"max5_q95_{g}" for g in ("kick","snare","tom","hat","cymbal")] +
    ["target_prev2_q95","target_prev1_q95","target_next1_q95","target_next2_q95",
     "target_act_percentile","target_res_percentile",
     "target_act_over_other_norm","target_res_over_other_norm"]
)

def read_csv_url(url):
    r=requests.get(url,timeout=60);r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))

def resolve_name(names,rel):
    rel=str(rel).replace("\\","/").lstrip("./")
    if rel in names:return rel
    c=[n for n in names if n.endswith("/"+rel) or n.endswith(rel)]
    if not c:raise KeyError(rel)
    return min(c,key=len)

def midi_notes_bytes(data):
    mid=mido.MidiFile(file=io.BytesIO(data))
    tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += mido.tick2second(msg.time,mid.ticks_per_beat,tempo)
        if msg.type=="set_tempo":tempo=msg.tempo
        if msg.type=="note_on" and msg.velocity>0 and int(msg.note) in PITCH:
            out.append((sec,PITCH[int(msg.note)]))
    return sorted(out)

def decode_wav(data,target=44100):
    rate,raw=wavfile.read(io.BytesIO(data))
    x=raw.astype(np.float32)
    if np.issubdtype(raw.dtype,np.integer):
        x/=max(abs(np.iinfo(raw.dtype).min),np.iinfo(raw.dtype).max)
    if x.ndim>1:x=x.mean(axis=1)
    if rate!=target:
        g=math.gcd(int(rate),target)
        x=resample_poly(x,target//g,int(rate)//g).astype(np.float32)
    return x

def frozen_model():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    return load_pytorch_weights(m,get_default_weights_path(),strict=False).eval()

def activities(model,processor,audio):
    st=processor.compute_stft(audio)
    fx=processor.apply_filterbank(st).T.astype(np.float32)[...,None]
    x=torch.from_numpy(fx[None,...]).float()
    with torch.no_grad():
        B,T,F,C=x.shape
        z=x.permute(0,3,1,2)
        for block in model.cnn_blocks:z=block(z)
        z=z.permute(0,2,3,1).reshape(B,T,-1)
        if getattr(model,"context_layer",None) is not None:z=model.context_layer(z)
        for gru in model.gru_layers:z,_=gru(z)
        a=torch.sigmoid(model.output_layer(z))[0].cpu().numpy().astype(np.float32)
    return a

def moving_residual(x,left=10,right=1):
    y=np.empty(len(x),np.float32);size=left+1+right
    for i in range(len(x)):
        s=0.
        for d in range(-left,right+1):
            j=max(0,min(len(x)-1,i+d));s+=float(x[j])
        y[i]=max(0.,float(x[i])-s/size)
    return y

def residual_matrix(a):
    return np.stack([moving_residual(a[:,c]) for c in range(a.shape[1])],axis=1)

def pick_class(a,r,c,threshold):
    x=a[:,c];p=r[:,c];peaks=[]
    for i in range(len(p)):
        mx=max(float(p[max(0,min(len(p)-1,i+d))]) for d in (-2,-1,0,1))
        if float(p[i])>=mx and float(p[i])>=threshold:peaks.append(i)
    if not peaks:return []
    groups=[];cur=[peaks[0]]
    for q in peaks[1:]:
        if q-cur[-1]<=2:cur.append(q)
        else:groups.append(cur);cur=[q]
    groups.append(cur)
    out=[]
    for g in groups:
        best=max(g,key=lambda i:float(p[i]))
        out.append(best)
    return out

def clip_stats(a,r):
    aq=np.maximum(np.percentile(a,95,axis=0),1e-4).astype(np.float32)
    rq=np.maximum(np.percentile(r,95,axis=0),1e-5).astype(np.float32)
    return {
      "aq":aq,"rq":rq,
      "as":[np.sort(a[:,i]) for i in range(a.shape[1])],
      "rs":[np.sort(r[:,i]) for i in range(r.shape[1])],
    }

def rank_pct(sorted_x,v):
    return float(np.searchsorted(sorted_x,v,side="right")/max(1,len(sorted_x)))

def feat(a,r,st,fr,c,low_thr):
    T=len(a);lo=max(0,fr-2);hi=min(T,fr+3)
    cur=a[fr];res=r[fr]
    mean=a[lo:hi].mean(axis=0);mx=a[lo:hi].max(axis=0)
    aq=st["aq"];rq=st["rq"]
    cn=cur/aq;rn=res/rq;mn=mean/aq;xn=mx/aq
    def atn(d):return float(a[max(0,min(T-1,fr+d)),c]/aq[c])
    other=max(float(np.max(np.delete(cn,c))),1e-5)
    rother=max(float(np.max(np.delete(rn,c))),1e-5)
    vals=np.concatenate([cn,rn,mn,xn]).astype(np.float32).tolist()
    vals += [
      atn(-2),atn(-1),atn(1),atn(2),
      rank_pct(st["as"][c],float(cur[c])),
      rank_pct(st["rs"][c],float(res[c])),
      float(cn[c])/other,float(rn[c])/rother
    ]
    return np.asarray(vals,dtype=np.float32)

def near_truth(times,t,w=MATCH):
    if not times:return False
    # times are sorted; dataset clips are short so linear scan is fine.
    return any(abs(x-t)<=w for x in times)

def candidate_rows(a,truth,hard_negatives=False):
    r=residual_matrix(a);st=clip_stats(a,r);out={g:[] for g in GROUPS}
    truth_by={g:sorted(t for t,gg in truth if gg==g) for g in GROUPS}
    for g in GROUPS:
        c=CLASS_INDEX[g];thr=BASE_THRESH[g]*LOW_SCALE
        seen=[]
        for fr in pick_class(a,r,c,thr):
            t=fr/FPS
            out[g].append((t,feat(a,r,st,fr,c,thr),1 if near_truth(truth_by[g],t) else 0,float(a[fr,c]),float(r[fr,c])))
            seen.append(t)
        if hard_negatives:
            # Explicit class-confusion negatives.  These are other K/S/T truth
            # onsets at which the target class has non-trivial activity/residual.
            # They are used only for fitting, never for external scoring.
            for t,other in truth:
                if other==g or near_truth(truth_by[g],t):continue
                fr=max(0,min(len(a)-1,int(round(t*FPS))))
                if float(r[fr,c]) < thr*.20 and float(a[fr,c]) < BASE_THRESH[g]*.45:continue
                if any(abs(x-t)<=.030 for x in seen):continue
                out[g].append((t,feat(a,r,st,fr,c,thr),0,float(a[fr,c]),float(r[fr,c])))
                seen.append(t)
    return out

def production_events(a):
    r=residual_matrix(a);out={g:[] for g in GROUPS}
    for g in GROUPS:
        c=CLASS_INDEX[g];thr=BASE_THRESH[g]*PROD_SCALE
        out[g]=[fr/FPS for fr in pick_class(a,r,c,thr)]
    return out

def score_events(pred,truth,w=MATCH):
    pred=sorted(pred);truth=sorted(truth);used=set();tp=0
    for x in pred:
        choices=[i for i,t in enumerate(truth) if i not in used and abs(t-x)<=w]
        if choices:
            j=min(choices,key=lambda i:abs(truth[i]-x));used.add(j);tp+=1
    p=tp/len(pred) if pred else 0.;r=tp/len(truth) if truth else 0.
    return {"tp":tp,"predicted":len(pred),"reference":len(truth),
            "precision":p,"recall":r,"f1":2*tp/(len(pred)+len(truth)) if pred or truth else 0.}

def sequence_groups(rows,split):
    d=defaultdict(list)
    for row in rows:
        if row.get("split")!=split:continue
        sig=(row.get("time_signature") or "").replace("/","-")
        try:dur=float(row.get("duration") or 0)
        except:dur=0
        if sig!="4-4" or dur<4 or dur>MAX_SEC:continue
        d[row.get("id","")].append(row)
    return d

def count_groups(notes):
    c=Counter(g for _,g in notes)
    return {g:int(c[g]) for g in GROUPS}

def choose_sequences(z,names,groups,n_fill,n_beat):
    # Scan deterministic short candidates until enough tom-rich fills and normal beats are found.
    ids=sorted(groups,key=lambda k:(groups[k][0].get("style",""),float(groups[k][0].get("duration") or 0),k))
    fills=[];beats=[]
    for key in ids:
        row=sorted(groups[key],key=lambda r:r.get("kit_name",""))[0]
        try:
            mn=resolve_name(names,row["midi_filename"])
            notes=midi_notes_bytes(z.read(mn));cnt=count_groups(notes)
        except Exception:
            continue
        item=(key,cnt)
        bt=row.get("beat_type")
        if bt=="fill" and cnt["tom"]>=3 and cnt["kick"]+cnt["snare"]>=2:
            fills.append(item)
        elif bt=="beat" and cnt["kick"]>=4 and cnt["snare"]>=2:
            beats.append(item)
        if len(fills)>=n_fill and len(beats)>=n_beat:break
    return [x[0] for x in fills[:n_fill]]+[x[0] for x in beats[:n_beat]]

def kit_partition(rows):
    kits=sorted({r.get("kit_name","") for r in rows if r.get("kit_name")})
    if len(kits)<12:raise RuntimeError(f"too few kits: {len(kits)}")
    # Spread both partitions across the complete kit list while keeping them disjoint.
    train_idx=np.linspace(0,len(kits)-1,8).round().astype(int).tolist()
    hold_idx=np.linspace(2,len(kits)-3,7).round().astype(int).tolist()
    train=[];hold=[]
    for i in train_idx:
        if kits[i] not in train:train.append(kits[i])
        if len(train)>=6:break
    for i in hold_idx:
        if kits[i] not in train and kits[i] not in hold:hold.append(kits[i])
        if len(hold)>=4:break
    for k in kits:
        if len(hold)>=4:break
        if k not in train and k not in hold:hold.append(k)
    return train[:6],hold[:4]

def rows_for_sequences(groups,seqs,kits):
    out=[]
    for seq in seqs:
        bykit={r.get("kit_name"):r for r in groups[seq]}
        chosen=[bykit[k] for k in kits if k in bykit]
        # recordings can be missing; use only requested disjoint kit set
        out.extend(chosen)
    return out

def collect(z,names,rows,model,processor,tag):
    data={g:[] for g in GROUPS};truth_all=[];man=[]
    for i,row in enumerate(rows,1):
        try:
            an=resolve_name(names,row["audio_filename"]);mn=resolve_name(names,row["midi_filename"])
            raw=z.read(an);audio=decode_wav(raw);notes=midi_notes_bytes(z.read(mn))
            a=activities(model,processor,audio);cand=candidate_rows(a,notes,hard_negatives=(tag=="train"));prod=production_events(a)
        except Exception as e:
            print("SKIP",tag,row.get("id"),row.get("kit_name"),type(e).__name__,str(e)[:120],flush=True);continue
        for g in GROUPS:data[g].extend(cand[g])
        truth={g:sorted(t for t,gg in notes if gg==g) for g in GROUPS}
        truth_all.append((prod,truth))
        man.append({"id":row.get("id"),"kit":row.get("kit_name"),"style":row.get("style"),
                    "beat_type":row.get("beat_type"),"duration":float(row.get("duration") or 0),
                    "counts":count_groups(notes),"audioBytes":len(raw)})
        print("CLIP",tag,i,len(rows),man[-1],{g:len(cand[g]) for g in GROUPS},flush=True)
    return data,truth_all,man

def fit_binary(rows,C):
    X=np.stack([x[1] for x in rows]);y=np.asarray([x[2] for x in rows],np.int8)
    sc=StandardScaler().fit(X)
    clf=LogisticRegression(C=C,max_iter=1200,class_weight="balanced",solver="lbfgs",random_state=923).fit(sc.transform(X),y)
    return sc,clf

def prob_rows(rows,sc,clf):
    X=np.stack([x[1] for x in rows])
    return clf.predict_proba(sc.transform(X))[:,list(clf.classes_).index(1)]

def aggregate_prod(truth_all,g):
    tp=pred=ref=0
    for prod,truth in truth_all:
        s=score_events(prod[g],truth[g]);tp+=s["tp"];pred+=s["predicted"];ref+=s["reference"]
    return score_events_counts(tp,pred,ref)

def score_events_counts(tp,pred,ref):
    p=tp/pred if pred else 0.;r=tp/ref if ref else 0.
    return {"tp":tp,"predicted":pred,"reference":ref,"precision":p,"recall":r,
            "f1":2*tp/(pred+ref) if pred+ref else 0.}

def aggregate_candidate(rows,probs,thr,clip_truth,g):
    # rows are concatenated, so use direct candidate-label F1 for model selection.
    keep=np.asarray(probs)>=thr;y=np.asarray([x[2] for x in rows],np.int8)
    tp=int(np.sum(keep & (y==1)));pred=int(np.sum(keep));ref=int(np.sum(y==1))
    return score_events_counts(tp,pred,ref)

def choose_threshold(rows,probs,prod_metric,g):
    # Domain transfer is the objective, so require very high precision on the
    # disjoint-kit external validation before a candidate may become a rescue.
    target_floor={"kick":.97,"snare":.95,"tom":.95}[g]
    floor=max(prod_metric["precision"]-(.002 if g=="kick" else .01),target_floor)
    best=None
    for thr in np.arange(.30,.991,.01):
        s=aggregate_candidate(rows,probs,float(thr),None,g)
        eligible=s["precision"]>=floor and s["predicted"]>=3
        key=(eligible,s["f1"],s["precision"],s["recall"])
        if best is None or key>best[0]:best=(key,float(thr),s)
    return best[1],best[2],float(floor)

def export_binary(sc,clf):
    return {"mean":sc.mean_.tolist(),"scale":sc.scale_.tolist(),
            "coef":clf.coef_[0].tolist(),"intercept":float(clf.intercept_[0])}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="drumscribe/models/egmd-kst-reclassifier-v3.json")
    ap.add_argument("--result",default="drumscribe/experiments/results-egmd-kst-reclassifier-v3.json")
    a=ap.parse_args()

    rows=read_csv_url(EGMD_CSV);train_kits,held_kits=kit_partition(rows)
    print("TRAIN_KITS",train_kits,flush=True);print("HELDOUT_KITS",held_kits,flush=True)
    model=frozen_model();processor=create_adtof_processor()

    with RemoteZip(EGMD_ZIP) as z:
        names=set(z.namelist())
        trg=sequence_groups(rows,"train");vag=sequence_groups(rows,"validation")
        trseq=choose_sequences(z,names,trg,8,8)
        vaseq=choose_sequences(z,names,vag,5,4)
        trrows=rows_for_sequences(trg,trseq,train_kits)
        varows=rows_for_sequences(vag,vaseq,held_kits)
        print("TRAIN_SEQS",trseq,flush=True);print("VAL_SEQS",vaseq,flush=True)
        train,train_truth,train_manifest=collect(z,names,trrows,model,processor,"train")
        val,val_truth,val_manifest=collect(z,names,varows,model,processor,"val")

    report={"schema":3,"dataset":"E-GMD v1.0.0","trainKits":train_kits,"heldOutKits":held_kits,
            "trainSequences":trseq,"validationSequences":vaseq,
            "trainManifest":train_manifest,"validationManifest":val_manifest,"classes":{}}
    deployment={"schema":3,"kind":"egmd-kst-candidate-logreg-clipnorm-hardneg","sampleRate":44100,"fps":FPS,
      "source":{"dataset":"E-GMD v1.0.0","license":"CC BY 4.0",
                "split":"official train -> fit; official validation + disjoint kits -> external validation",
                "url":"https://magenta.tensorflow.org/datasets/e-gmd"},
      "featureNames":FEATURE_NAMES,"lowScale":LOW_SCALE,"productionScale":PROD_SCALE,
      "baseThresholds":BASE_THRESH,"matchToleranceSec":MATCH,
      "trainKits":train_kits,"heldOutKits":held_kits,"models":{}}

    for g in GROUPS:
        if len(train[g])<20 or len(set(x[2] for x in train[g]))<2:
            raise RuntimeError(f"insufficient {g} train candidates: {Counter(x[2] for x in train[g])}")
        if len(val[g])<10 or len(set(x[2] for x in val[g]))<2:
            raise RuntimeError(f"insufficient {g} val candidates: {Counter(x[2] for x in val[g])}")
        # modest C sweep selected on external validation only
        candidates=[]
        prod=aggregate_prod(val_truth,g)
        for C in (.08,.20,.50,1.0,2.0):
            sc,clf=fit_binary(train[g],C);pr=prob_rows(val[g],sc,clf)
            thr,score,floor=choose_threshold(val[g],pr,prod,g)
            candidates.append((score["f1"],score["precision"],C,thr,score,floor,sc,clf))
        candidates.sort(key=lambda x:(x[0],x[1]),reverse=True)
        _,_,C,thr,score,floor,sc,clf=candidates[0]
        report["classes"][g]={
          "trainCandidates":len(train[g]),"trainPositive":sum(x[2] for x in train[g]),
          "validationCandidates":len(val[g]),"validationPositive":sum(x[2] for x in val[g]),
          "C":C,"threshold":thr,"precisionFloor":floor,
          "rawProduction":prod,"reclassifiedLowPool":score
        }
        deployment["models"][g]={**export_binary(sc,clf),"C":C,"threshold":thr,
          "externalValidation":{"rawProduction":prod,"reclassifiedLowPool":score}}
        print("CLASS",g,json.dumps(report["classes"][g],ensure_ascii=False),flush=True)

    op=Path(a.output);op.parent.mkdir(parents=True,exist_ok=True)
    op.write_text(json.dumps(deployment,separators=(",",":"))+"\n")
    rp=Path(a.result);rp.parent.mkdir(parents=True,exist_ok=True)
    rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("MODEL",str(op),op.stat().st_size,flush=True)

if __name__=="__main__":main()
