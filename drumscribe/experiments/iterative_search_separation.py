"""Cycles 40-42: source-separated drum transcription search.

This is the first search that explicitly separates drums.mp3 into instrument
spectrogram streams before transcription. Reference MIDI is used only after
real candidate MIDI files are written.

Separation is template-conditioned soft masking (browser-portable), not Demucs.
It creates kick/snare/tom/hat/cymbal spectrogram streams, then the existing
leave-one-song-out classifiers and musical constraints operate on separated
features.
"""
from __future__ import annotations
import copy, importlib.util, json, math
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter

ROOT=Path(".")
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

comp=loadmod("comp","drumscribe/experiments/iterative_search_composite_v2.py")
ev=comp.ev;base=comp.base;ps=comp.ps
GROUPS=list(ev.GROUPS)
SONGS=base.SONGS

FUNC_GROUPS={
    "kick":["kick"],
    "snare":["snare"],
    "tom":["tom"],
    "hat":["hat","pedal_hat"],
    "cymbal":["crash","ride","other"],
}

def template_bank(tmpl):
    idx={g:i for i,g in enumerate(ev.ORDER)}
    bank={}
    for k,groups in FUNC_GROUPS.items():
        cols=[tmpl[:,idx[g]] for g in groups if g in idx]
        x=np.mean(cols,axis=0)
        x=np.maximum(x,1e-8)
        x/=np.sum(x)+1e-8
        bank[k]=x.astype("f4")
    return bank

def base_activation(spec,tmpl):
    # Same rise/whitening family as the original detector, but only used to
    # estimate source activity before masking.
    rise=np.maximum(spec-np.pad(spec[:,:-2],((0,0),(2,0))),0)
    whitening=np.maximum(np.mean(spec,axis=1),np.percentile(np.mean(spec,axis=1),35))
    whitening=np.maximum(whitening,1e-3)**.6
    A=rise/whitening[:,None]
    B=tmpl/whitening[:,None]
    B/=np.linalg.norm(B,axis=0,keepdims=True)+1e-8
    sim=B.T@A
    sim/=np.linalg.norm(A,axis=0,keepdims=True)+1e-8
    return np.maximum(sim,0)

def separated_features(spec,tmpl,mode):
    idx={g:i for i,g in enumerate(ev.ORDER)}
    bank=template_bank(tmpl)
    sim0=base_activation(spec,tmpl)

    cfg={
      "soft":dict(mask_power=1.15,act_power=.85,smooth=1,temp=.18),
      "sharp":dict(mask_power=2.20,act_power=1.35,smooth=1,temp=.07),
      "smooth":dict(mask_power=1.55,act_power=1.05,smooth=9,temp=.12),
    }[mode]

    activ={}
    for k,groups in FUNC_GROUPS.items():
        vals=[sim0[idx[g]] for g in groups if g in idx]
        a=np.maximum.reduce(vals) if vals else np.zeros(spec.shape[1],dtype="f4")
        if cfg["smooth"]>1:
            a=median_filter(a,size=cfg["smooth"],mode="nearest")
        activ[k]=np.maximum(a,cfg["temp"])

    names=["kick","snare","tom","hat","cymbal"]
    estimates=[]
    for k in names:
        spectral=(bank[k][:,None]+1e-8)**cfg["mask_power"]
        temporal=(activ[k][None,:]+1e-8)**cfg["act_power"]
        estimates.append(spectral*temporal)
    E=np.stack(estimates,axis=0)
    denom=np.sum(E,axis=0)+1e-12
    masks=E/denom[None,:,:]
    streams={k:(spec*masks[i]).astype("f4") for i,k in enumerate(names)}

    # Extract onset strength from each separated stream.
    def onset_energy(S,lo,hi):
        rise=np.maximum(S-np.pad(S[:,:-2],((0,0),(2,0))),0)
        freqs=np.arange(S.shape[0])*ev.SR/ev.FFT
        x=rise[(freqs>=lo)&(freqs<hi)].sum(axis=0)
        x=np.maximum(x-.55*median_filter(x,size=101),0)
        q=np.percentile(x,98)+1e-7
        return (x/q).astype("f4")

    kick=onset_energy(streams["kick"],35,900)
    snare=onset_energy(streams["snare"],100,3000)
    tom=onset_energy(streams["tom"],60,1800)
    hat=onset_energy(streams["hat"],1800,5500)
    cym=onset_energy(streams["cymbal"],900,5500)

    # Existing pipelines expect four band channels:
    # low, mid, cymbal-ish, high-hat-ish.
    band=np.stack([
        kick,
        np.maximum(snare,.78*tom),
        cym,
        hat
    ]).astype("f4")

    # Compute each class similarity against its separated functional stream.
    out_sim=np.zeros((len(ev.ORDER),spec.shape[1]),dtype="f4")
    group_stream={
      "kick":"kick","snare":"snare","tom":"tom",
      "hat":"hat","pedal_hat":"hat",
      "crash":"cymbal","ride":"cymbal","other":"cymbal",
    }
    for g in ev.ORDER:
        k=group_stream.get(g,"cymbal")
        S=streams[k]
        rise=np.maximum(S-np.pad(S[:,:-2],((0,0),(2,0))),0)
        white=np.maximum(np.mean(S,axis=1),np.percentile(np.mean(S,axis=1),35))
        white=np.maximum(white,1e-4)**.6
        A=rise/white[:,None]
        b=tmpl[:,idx[g]]/white
        b=b/(np.linalg.norm(b)+1e-8)
        s=b@A
        s/=np.linalg.norm(A,axis=0)+1e-8
        out_sim[idx[g]]=np.nan_to_num(s).astype("f4")

    diagnostics={
      "mean_mask":{k:float(np.mean(masks[i])) for i,k in enumerate(names)},
      "mode":mode
    }
    return band,out_sim,diagnostics

def prepare_mode(mode):
    data=comp.anc.load()
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    for song,d in data.items():
        x=ev.audio(d["folder"]/"drums.mp3")
        spec=ev.spectrum(x)
        band,sim,diag=separated_features(spec,tmpl,mode)
        d["band"]=band;d["sim"]=sim;d["separation"]=diag
    # Rebuild every supervised dataset from the separated features.
    comp.ml.build_dataset(data,True)
    comp.tom.build_tom(data)
    comp.ped.build(data)
    comp.sec.build_windows(data,2)
    return data

def params():
    p=comp.params()
    # Start from the reviewed corrected-taxonomy winner, but suppress the two
    # review-dominant failure modes: spurious kick/snare swaps and ride spam.
    p.update({
      "snare_ratio":1.80,"snare_margin":.30,
      "crash_prob":.50,"crash_window_beats":.18,
      "pedal_prob":.80,"pedal_periodic":.50,
      "ride_mode":"off",
      "review_gate_mode":"none",
      "hat_grid_tol":.18,"kick_grid_tol":.20,
      "hat_min_conf":1.0,"kick_min_conf":1.0
    })
    return p

def beat_dist(t,bpm,den,division):
    beat=60/bpm*4/den
    step=beat/division
    x=t%step
    return min(x,step-x)/step

def review_gate(events,d,p):
    mode=p.get("review_gate_mode","none")
    if mode=="none":return events

    out=[]
    for e in events:
        g=e["group"];keep=True
        if g=="kick":
            # Review says nanairo has too many kicks. Keep off-grid kicks only
            # when acoustic confidence is substantially stronger.
            div=4 if mode=="moderate" else 2
            bd=beat_dist(e["time"],d["bpm"],d["den"],div)
            if bd>p["kick_grid_tol"] and e.get("confidence",1)<(1.40 if mode=="moderate" else 1.65):
                keep=False
        elif g=="hat":
            # Review repeatedly reports absurd hat bursts. Preserve 8th/16th
            # patterns, remove weak unstructured in-between hits.
            div=4
            bd=beat_dist(e["time"],d["bpm"],d["den"],div)
            if bd>p["hat_grid_tol"] and e.get("confidence",1)<(1.32 if mode=="moderate" else 1.55):
                keep=False
        if keep:out.append(e)

    # De-duplicate near-simultaneous same-class noise after source separation.
    mind={"kick":.045,"snare":.038,"hat":.040,"pedal_hat":.05,"tom":.055,"crash":.14,"ride":.05}
    final=[]
    for g in GROUPS:
        arr=sorted([e for e in out if e["group"]==g],key=lambda e:e["time"])
        last=-999.
        for e in arr:
            if e["time"]-last<mind.get(g,.04):continue
            final.append(e);last=e["time"]
    return sorted(final,key=lambda e:e["time"])

def transcribe(d,held,data,tm,pm,cm,sm,p):
    pred,phase=comp.transcribe(d,held,data,tm,pm,cm,sm,p)
    # comp.enforce_two_limb already ran. Review gate only removes events.
    return review_gate(pred,d,p),phase

def evaluate(name,p,data,outdir):
    result={"params":p,"songs":{}};tot=Counter()
    for held in SONGS:
        tm=comp.tom.train_tom(data,held,"rf")
        pm=comp.ped.train(data,held,"logistic")
        cm=comp.ml.train_fold(data,held,"rf")[0]
        sm=comp.sec.train_section(data,held,"extra")
        pred,phase=transcribe(data[held],held,data,tm,pm,cm,sm,p)
        mid=outdir/name/f"{held}.mid";base.write_midi(mid,pred,data[held]["bpm"])
        parsed=ev.midi_events(mid);truth=ev.midi_events(data[held]["folder"]/"chart.mid")
        sc=ev.score(parsed,truth,data[held]["shift"]);cf=ev.confusion(parsed,truth,data[held]["shift"])
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc)
        sc["two_limb_violations"]=ps.poly_violations(parsed,p["poly_window"])
        sc["separation"]=data[held]["separation"]
        result["songs"][held]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                   kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],
                   poly=sc["two_limb_violations"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":m,
       "precision":round(tp/n,4) if n else 0,"recall":round(tp/m,4) if m else 0,
       "f1":round(2*tp/(n+m),4) if n+m else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":tot["poly"],"by_group":{}}
    macro=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        f=2*a/(b+c) if b+c else 0;macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,
          "f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/len(macro),4)

    # Review-weighted selector: heavily penalize the exact human complaints.
    k_ratio=s["by_group"]["kick"]["count_ratio"] or 1
    h_ratio=s["by_group"]["hat"]["count_ratio"] or 1
    excess=max(0,k_ratio-1.10)+max(0,h_ratio-1.15)
    snare_recall=s["by_group"]["snare"]["recall"]
    tom_f1=s["by_group"]["tom"]["f1"]
    crash_f1=s["by_group"]["crash"]["f1"]
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(
      s["f1"]+.14*s["macro_f1"]+.13*tom_f1+.10*crash_f1+.10*snare_recall
      -.30*ks-.08*excess,6)
    result["summary"]=s
    return result

def rank(x):
    return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    report={"schema":1,"method":"explicit spectrogram source separation before transcription","cycles":[]}
    root=ROOT/"drumscribe/experiments/generated-search-separation"

    # Cycle 40: three source-separation masks.
    res={};data_by={}
    for mode in ("soft","sharp","smooth"):
        print("PREPARE",mode,flush=True)
        data=prepare_mode(mode);data_by[mode]=data
        name="c40_"+mode;p=params();p["separation_mode"]=mode
        res[name]=evaluate(name,p,data,root/"cycle40")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);winner=rr[0][0];best_mode=winner.replace("c40_","")
    bestp=copy.deepcopy(res[winner]["params"])
    report["cycles"].append({"cycle":40,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,
      "carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    # Cycle 41: review-driven anti-burst choices on the winning separated data.
    data=data_by[best_mode];res={}
    for name,mode,kt,ht in [
      ("c41_no_gate","none",.20,.18),
      ("c41_moderate","moderate",.24,.22),
      ("c41_strict","strict",.18,.16)
    ]:
        p=copy.deepcopy(bestp);p["review_gate_mode"]=mode;p["kick_grid_tol"]=kt;p["hat_grid_tol"]=ht
        res[name]=evaluate(name,p,data,root/"cycle41")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);winner=rr[0][0];bestp=copy.deepcopy(res[winner]["params"])
    report["cycles"].append({"cycle":41,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,
      "carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    # Cycle 42: snare recall vs false-snare tradeoff, specifically from review.
    res={}
    for name,ratio,margin in [
      ("c42_snare_guard",1.95,.36),
      ("c42_snare_balanced",1.75,.26),
      ("c42_snare_roll_recall",1.55,.16)
    ]:
        p=copy.deepcopy(bestp);p["snare_ratio"]=ratio;p["snare_margin"]=margin
        res[name]=evaluate(name,p,data,root/"cycle42")
        print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);winner=rr[0][0];bestp=copy.deepcopy(res[winner]["params"])
    report["cycles"].append({"cycle":42,"candidates":res,"ranking":[n for n,_ in rr],"winner":winner,
      "carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    report["final"]={"winner":winner,"separation_mode":best_mode,"summary":res[winner]["summary"],"params":bestp}
    (ROOT/"drumscribe/experiments/results-iterative-separation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
