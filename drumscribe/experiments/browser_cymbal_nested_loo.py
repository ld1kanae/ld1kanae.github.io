"""Nested-LOO cymbal candidate classifier using supplied MIDI as domain data.

Outer held-out song is never used for training or hyperparameter selection.

Candidate generation:
- ADTOF generic cymbal stream at broad thresholds 0.04 / 0.06 / 0.08.

Features available at prediction time:
- ADTOF cymbal activation
- browser BPM/bar phase and 16th-note position
- candidate repetition / same-slot-across-bars support
- current browser metal label near the candidate
- kick/snare/tom context and preceding fill density
- fixed sample template similarities and spectral bands
- GMD all-style + rock-family symbolic priors
- current predicted metal token one slot / one bar earlier

Target for training songs only:
- crash / ride if the broad candidate matches chart.mid within 80 ms
- none otherwise

Final transcription preserves current crash/ride. It may add missing cymbals and,
optionally, reclassify a current hat/pedal event when the LOO-trained classifier
is sufficiently confident.

Nested CV chooses candidate threshold, class weighting, probability threshold,
margin, and add-vs-reclass mode using only the four non-held songs.
"""
from __future__ import annotations
import bisect,importlib.util,json,math
from collections import Counter,defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from adtof_pytorch import (
    calculate_n_bins,create_frame_rnn_model,get_default_weights_path,
    load_pytorch_weights,PeakPicker,LABELS_5
)
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
METAL=("hat","pedal_hat","ride","crash")
CAND_THR=(.04,.06,.08)
STYLE=json.loads((ROOT/"drumscribe/models/gmd-metal-style-prior.json").read_text())
GMD=json.loads((ROOT/"drumscribe/models/gmd-metal-prior.json").read_text())

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
IDX={g:i for i,g in enumerate(ev.ORDER)}

def adtof_model():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    m=load_pytorch_weights(m,get_default_weights_path(),strict=False)
    return m.eval()

def adtof_acts(song,m,p):
    a=p.load_audio(str(ROOT/"DruMaster/songs"/song/"drums.mp3"))
    st=p.compute_stft(a);x=p.apply_filterbank(st).T.astype(np.float32)[...,None]
    with torch.no_grad():return m(torch.from_numpy(x[None,...])).cpu().numpy()

def pick(y,thr):
    pp=PeakPicker(thresholds=[.22,.24,.32,.22,thr],fps=100)
    o=pp.pick(y,labels=LABELS_5,label_offset=0)[0]
    return sorted(float(t) for t in o.get(49,[]))

def rows(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def truth(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    sh=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    rr=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    return {g:sorted(t+sh for t,gg,*_ in rr if gg==g) for g in ev.ORDER}

def near_index(xs,t,w):
    if not xs:return None
    j=bisect.bisect_left(xs,t)
    opts=[k for k in (j-1,j,j+1) if 0<=k<len(xs)]
    if not opts:return None
    k=min(opts,key=lambda q:abs(xs[q]-t))
    return k if abs(xs[k]-t)<=w else None

def nearest_label(truth_by,t,w=.08):
    best=(1e9,"none")
    for g in ("crash","ride"):
        xs=truth_by[g];k=near_index(xs,t,w)
        if k is not None and abs(xs[k]-t)<best[0]:best=(abs(xs[k]-t),g)
    return best[1]

def circ_slot(t,phase,beat):
    bar=4*beat;x=(t-phase)%bar
    slot=int(round(x/(beat/4)))%16
    head=min(x,bar-x)/beat
    q=min((x%beat),beat-(x%beat))/beat
    return slot,head,q

def rep_support(xs,t,step,w=.06):
    if not xs:return 0.
    return sum(any(abs(x-(t+k*step))<=w for x in xs) for k in (-2,-1,1,2))/4

def same_slot(xs,t,phase,beat):
    bar=4*beat;slot,_h,_q=circ_slot(t,phase,beat);b=math.floor((t-phase)/bar);seen=set()
    for x in xs:
        bx=math.floor((x-phase)/bar)
        if abs(bx-b)>4 or bx==b:continue
        sx,_a,_b=circ_slot(x,phase,beat)
        if sx==slot:seen.add(bx)
    return min(1,len(seen)/4)

def onehot(label,values):
    return [1.0 if label==v else 0.0 for v in values]

def prepare_song(song,acts,processor,tmpl):
    rr,side=rows(song);tr=truth(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"]);beat=60/bpm;bar=4*beat
    audio=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3");sp=ev.spectrum(audio);band,sim=ev.features(sp,tmpl)
    by={g:sorted(t for t,gg in rr if gg==g) for g in ev.ORDER}
    metal_events=sorted((t,g) for t,g in rr if g in METAL)
    slot_label={}
    for t,g in metal_events:
        s=int(round((t-phase)/(beat/4)))
        # structural cymbals > pedal > hat if simultaneous
        pri={"crash":4,"ride":3,"pedal_hat":2,"hat":1}
        if s not in slot_label or pri[g]>pri[slot_label[s]]:slot_label[s]=g

    all_candidates={th:pick(acts,th) for th in CAND_THR}
    data={}
    rock=STYLE["groups"]["rock_family"];allstyle=STYLE["groups"]["all"]

    for th,cands in all_candidates.items():
        feats=[];labels=[];times=[];meta_rows=[]
        for t in cands:
            fr=max(0,min(sim.shape[1]-1,int(round(t*ev.SR/ev.HOP))))
            af=max(0,min(acts.shape[1]-1,int(round(t*100))))
            activation=float(acts[0,af,4])
            slot,head,qdist=circ_slot(t,phase,beat)
            current="none";current_t=None
            if metal_events:
                mt=[x for x,g in metal_events];k=near_index(mt,t,.055)
                if k is not None:current_t,current=metal_events[k]

            ctx=[]
            for g in ("kick","snare","tom"):
                if near_index(by[g],t,.055) is not None:ctx.append(g)
            ctxkey="+".join(ctx) if ctx else "none"
            a=t-beat
            tom_n=sum(a<=x<t for x in by["tom"]);sn_n=sum(a<=x<t for x in by["snare"])
            fill="tom" if tom_n>=2 else "snare" if sn_n>=2 else "none"

            gp=GMD["accent"].get(("head" if slot==0 else "nonhead")+"|"+fill,GMD["globalProb"])
            rs=rock["slot16"].get(str(slot),rock["global"])
            als=allstyle["slot16"].get(str(slot),allstyle["global"])

            sidx=int(round((t-phase)/(beat/4)))
            prev=slot_label.get(sidx-1,"none");prevbar=slot_label.get(sidx-16,"none")

            hs=float(sim[IDX["hat"],fr]);ps=float(sim[IDX["pedal_hat"],fr])
            ris=float(sim[IDX["ride"],fr]);cs=float(sim[IDX["crash"],fr])
            b0,b1,b2,b3=[float(band[i,fr]) for i in range(4)]
            f=[
              activation,head,qdist,
              rep_support(cands,t,beat/2),rep_support(cands,t,beat),rep_support(cands,t,2*beat),
              same_slot(cands,t,phase,beat),
              min(2.0,sum(abs(x-t)<=bar for x in cands)/16),
              tom_n/4,sn_n/4,
              b0,b1,b2,b3,b3/(b2+.04),b3/(b0+b1+.05),
              hs,ps,ris,cs,ris-hs,cs-hs,ris/(abs(hs)+.04),cs/(abs(hs)+.04),
              math.log(max(1e-5,rs.get("ride",1e-5))),
              math.log(max(1e-5,rs.get("crash",1e-5))),
              math.log(max(1e-5,als.get("ride",1e-5))),
              math.log(max(1e-5,als.get("crash",1e-5))),
              math.log(max(1e-5,gp.get("ride",1e-5))),
              math.log(max(1e-5,gp.get("crash",1e-5))),
            ]
            f+=onehot(current,("none","hat","pedal_hat","ride","crash"))
            f+=onehot(prev,("none","hat","pedal_hat","ride","crash"))
            f+=onehot(prevbar,("none","hat","pedal_hat","ride","crash"))
            f+=onehot(ctxkey,("none","kick","snare","tom","kick+snare","kick+tom","snare+tom","kick+snare+tom"))
            feats.append(f);labels.append(nearest_label(tr,t));times.append(t)
            meta_rows.append({"time":t,"current":current,"currentTime":current_t})
        data[th]={"X":np.asarray(feats,dtype=np.float32),"y":np.asarray(labels),"times":times,"meta":meta_rows}
    return {"rows":rr,"side":side,"truth":tr,"data":data}

def fit_predict(train_parts,test_part,weight_mode):
    X=np.concatenate([z["X"] for z in train_parts],axis=0);y=np.concatenate([z["y"] for z in train_parts])
    cw="balanced" if weight_mode=="balanced" else None
    clf=make_pipeline(StandardScaler(),LogisticRegression(max_iter=400,C=.8,class_weight=cw,solver="lbfgs"))
    clf.fit(X,y);probs=clf.predict_proba(test_part["X"]);classes=clf[-1].classes_
    return probs,classes

def decide(prob,classes,pthr,margin):
    ci={g:i for i,g in enumerate(classes)}
    vals={g:(float(prob[ci[g]]) if g in ci else 0.) for g in ("none","crash","ride")}
    order=sorted(vals,key=vals.get,reverse=True);best,second=order[:2]
    if best in ("crash","ride") and vals[best]>=pthr and vals[best]-vals[second]>=margin:return best,vals
    return "none",vals

def build_final(songdata,testpart,probs,classes,cfg):
    rr=list(songdata["rows"]);remove=set();adds=[]
    current_metal=[(i,t,g) for i,(t,g) in enumerate(rr) if g in METAL]
    current_times=[t for i,t,g in current_metal]
    crri=[t for t,g in rr if g in ("crash","ride")]
    changed=Counter()
    for row,prob in zip(testpart["meta"],probs):
        lab,vals=decide(prob,classes,cfg["prob"],cfg["margin"])
        if lab=="none":continue
        t=row["time"]
        if near_index(crri,t,.055) is not None:continue
        if row["current"] in ("hat","pedal_hat"):
            if cfg["mode"]!="reclass":continue
            # find nearest corresponding row index
            opts=[z for z in current_metal if z[2]==row["current"] and abs(z[1]-t)<=.055]
            if not opts:continue
            idx,ct,cg=min(opts,key=lambda z:abs(z[1]-t))
            if idx in remove:continue
            remove.add(idx);adds.append((ct,lab));crri.append(ct);changed[cg+"->"+lab]+=1
        elif row["current"]=="none":
            adds.append((t,lab));crri.append(t);changed["add_"+lab]+=1
    out=[e for i,e in enumerate(rr) if i not in remove]+adds
    # per-class de-dup
    final=[]
    for g in ev.ORDER:
        xs=sorted(t for t,gg in out if gg==g);last=-999
        mind=.05 if g in ("crash","ride") else .035
        for t in xs:
            if t-last>=mind:final.append((t,g));last=t
    return sorted(final),dict(changed)

def score(song,pred):
    tr=truth(song);tot=Counter();by={}
    for g in ev.ORDER:
        pp=sorted(t for t,gg in pred if gg==g);tt=tr[g];used=set();tp=0
        for t in pp:
            k=near_index(tt,t,.08)
            if k is not None and k not in used:used.add(k);tp+=1
        by[g]={"tp":tp,"predicted":len(pp),"reference":len(tt)}
        tot.update(tp=tp,pred=len(pp),ref=len(tt))
    return {"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
            "precision":tot["tp"]/tot["pred"] if tot["pred"] else 0,
            "recall":tot["tp"]/tot["ref"] if tot["ref"] else 0,
            "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]) if tot["pred"]+tot["ref"] else 0,
            "by_group":by}

def aggregate(scores):
    tot=Counter()
    for sc in scores.values():
        tot.update(tp=sc["tp"],pred=sc["predicted"],ref=sc["reference"])
        for g,z in sc["by_group"].items():tot.update({f"{g}_tp":z["tp"],f"{g}_pred":z["predicted"],f"{g}_ref":z["reference"]})
    out={"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
         "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],
         "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        out["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0}
    return out

def obj(ag):
    return ag["f1"]+.09*ag["by_group"]["ride"]["f1"]+.07*ag["by_group"]["crash"]["f1"]

def configs():
    return [{"cand":ct,"weight":w,"prob":p,"margin":m,"mode":mode}
      for ct in CAND_THR for w in ("none","balanced")
      for p in (.45,.55,.65,.75) for m in (0,.10,.20)
      for mode in ("add","reclass")]

def main():
    m=adtof_model();proc=create_adtof_processor();tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    data={}
    for song in SONGS:
        print("INFER",song,flush=True);acts=adtof_acts(song,m,proc);data[song]=prepare_song(song,acts,proc,tmpl)
    baseline_scores={s:score(s,data[s]["rows"]) for s in SONGS};baseline=aggregate(baseline_scores)
    cfgs=configs();outer={};held_scores={}
    for held in SONGS:
        pool=[s for s in SONGS if s!=held]
        cfg_metrics=[]
        for cfg in cfgs:
            inner_scores={};valid=True
            for val in pool:
                train=[s for s in pool if s!=val]
                try:
                    probs,classes=fit_predict([data[s]["data"][cfg["cand"]] for s in train],data[val]["data"][cfg["cand"]],cfg["weight"])
                except Exception:
                    valid=False;break
                pred,_=build_final(data[val],data[val]["data"][cfg["cand"]],probs,classes,cfg)
                inner_scores[val]=score(val,pred)
            if not valid:continue
            ag=aggregate(inner_scores)
            # preserve inner overall precision and F1 while rewarding metal gains
            cfg_metrics.append((obj(ag),ag["f1"],ag["precision"],cfg,ag))
        cfg_metrics.sort(key=lambda z:(z[0],z[1],z[2]),reverse=True)
        # first candidate that does not materially damage inner aggregate
        base_inner=aggregate({s:baseline_scores[s] for s in pool})
        chosen=next((z for z in cfg_metrics if z[4]["f1"]>=base_inner["f1"]-.004 and z[4]["precision"]>=base_inner["precision"]-.04),cfg_metrics[0])
        cfg=chosen[3]
        probs,classes=fit_predict([data[s]["data"][cfg["cand"]] for s in pool],data[held]["data"][cfg["cand"]],cfg["weight"])
        pred,diag=build_final(data[held],data[held]["data"][cfg["cand"]],probs,classes,cfg)
        sc=score(held,pred);held_scores[held]=sc
        outer[held]={"config":cfg,"inner":{"objective":chosen[0],"summary":chosen[4]},"held":sc,"diag":diag}
        print("HELD",held,json.dumps({"config":cfg,"held":sc,"diag":diag},ensure_ascii=False),flush=True)
    agg=aggregate(held_scores)
    report={"schema":1,"description":"Nested LOO broad-cymbal classifier; supplied MIDI training without held-song leakage.",
            "baseline":baseline,"outer":outer,"aggregate":agg,"objective":obj(agg)}
    (EXP/"results-browser-cymbal-nested-loo.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    print("FINAL",json.dumps({"aggregate":agg,"objective":report["objective"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
