"""Cycles 163-165: ADTOF baseline and independent-confirmation fusion.

Cycle 163:
  ADTOF-pytorch standalone at recall/default/precision thresholds.
Cycle 164:
  Use ADTOF hi-hat peaks as an independent confirmation/replacement component
  on top of the current c159 base.
Cycle 165:
  Use ADTOF cymbal peaks as an independent confirmation gate for current
  crash/ride candidates.

ADTOF outputs 5 broad classes (kick/snare/tom/hat/cymbal), so standalone
evaluation also records a collapsed cymbal-family metric. chart.mid is used
only after prediction for scoring/selection.
"""
from __future__ import annotations

import importlib.util
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from adtof_pytorch import (
    calculate_n_bins,
    create_frame_rnn_model,
    load_audio_for_model,
    load_pytorch_weights,
    get_default_weights_path,
    PeakPicker,
    FRAME_RNN_THRESHOLDS,
    LABELS_5,
)

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

repair=loadmod("repair",EXP/"iterative_search_overtrigger_repair.py")
ev=repair.ev; sel=repair.sel; detail=repair.detail; base=repair.base

SONGS=repair.SONGS; GROUPS=repair.GROUPS
BASE=EXP/"generated-search-metal-reclass/cycle159/c159_crash_recall"
MAP={35:"kick",38:"snare",47:"tom",42:"hat",49:"crash"}

def rows(path,song): return repair.rows(path,song)
def meta(song): return repair.meta(song)
def near(xs,t,w): return any(abs(x-t)<=w for x in xs)

def infer_all():
    n_bins=calculate_n_bins()
    model=create_frame_rnn_model(n_bins)
    wp=get_default_weights_path()
    if wp and Path(wp).exists():
        model=load_pytorch_weights(model,wp,strict=False)
    model.eval().to("cpu")
    out={}
    with torch.no_grad():
        for song in SONGS:
            audio=ROOT/"DruMaster/songs"/song/"drums.mp3"
            print("ADTOF INFER",song,flush=True)
            x=load_audio_for_model(str(audio)).to("cpu")
            out[song]=model(x).cpu().numpy()
            del x
    return out

def peaks(acts,scale):
    th=[float(x)*scale for x in FRAME_RNN_THRESHOLDS]
    picker=PeakPicker(thresholds=th,fps=100)
    p=picker.pick(acts,labels=LABELS_5,label_offset=0)[0]
    return sorted((float(t),MAP[int(pitch)]) for pitch,times in p.items() for t in times)

def family_match(pred,truth,shift,pred_groups,truth_groups,tol=.08):
    a=sorted(t for t,g,*_ in pred if g in pred_groups)
    b=sorted(t+shift for t,g,*_ in truth if g in truth_groups)
    used=set();tp=0
    for x in a:
        opts=[i for i,y in enumerate(b) if i not in used and abs(x-y)<=tol]
        if opts:
            k=min(opts,key=lambda i:abs(x-b[i]));used.add(k);tp+=1
    p=tp/len(a) if a else 0.;r=tp/len(b) if b else 0.;f=2*tp/(len(a)+len(b)) if a or b else 0.
    return {"tp":tp,"predicted":len(a),"reference":len(b),"precision":p,"recall":r,"f1":f}

def adtof_events_for_song(pk):
    return pk

def current_events(song):
    return rows(BASE,song)

def phase(song,events):
    return repair.timing(song,events)

def replace_hat(song,current,ad_hat,mode):
    if mode=="base":return current
    hats=sorted(t for t,g in current if g=="hat")
    if mode=="replace":
        chosen=list(ad_hat)
    else:
        _,ph,_,bar=phase(song,current)
        chosen=[]
        for t in hats:
            rep=repair.rep_support(hats,t,ph,bar)
            if mode=="confirm_loose":
                keep=near(ad_hat,t,.060) or rep>=3
            elif mode=="confirm_balanced":
                keep=near(ad_hat,t,.050) or rep>=4
            else:
                keep=near(ad_hat,t,.040) or rep>=5
            if keep:chosen.append(t)
    return repair.enforce([e for e in current if e[1]!="hat"]+[(t,"hat") for t in chosen])

def gate_cymbal(song,current,ad_cym,mode):
    if mode=="base":return current
    _,ph,beat,bar=phase(song,current)
    crashes=sorted(t for t,g in current if g=="crash")
    rides=sorted(t for t,g in current if g=="ride")
    out=[e for e in current if e[1] not in ("crash","ride")]
    for g,arr in (("crash",crashes),("ride",rides)):
        for t in arr:
            support=near(ad_cym,t,.070 if mode=="loose" else .055 if mode=="balanced" else .045)
            if g=="crash":
                down=repair.downbeat_strength(t,ph,beat,bar)
                rescue=down>=(.55 if mode=="loose" else .70 if mode=="balanced" else .82)
            else:
                rep=repair.rep_support(arr,t,ph,bar)
                rescue=rep>=(3 if mode=="loose" else 4 if mode=="balanced" else 5)
            if support or rescue:out.append((t,g))
    return repair.enforce(out)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def summarize(result):
    tot=Counter()
    for sc in result["songs"].values():
        cf=sc["confusion"]
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,ref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":ref,"precision":tp/n if n else 0,"recall":tp/ref if ref else 0,
       "f1":2*tp/(n+ref) if n+ref else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
       "two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
        for sc in result["songs"].values():
            x=sc["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,
          "count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    return s

def evaluate(name,event_fn,outdir):
    result={"songs":{}}
    fam=Counter()
    for song in SONGS:
        m=meta(song);events=event_fn(song)
        p=outdir/name/f"{song}.mid";write(p,events,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc)
        cy=family_match(pred,truth,shift,{"crash"},{"crash","ride"})
        hf=family_match(pred,truth,shift,{"hat"},{"hat","pedal_hat"})
        sc["families"]={"cymbal":cy,"hat":hf};result["songs"][song]=sc
        fam.update(cym_tp=cy["tp"],cym_pred=cy["predicted"],cym_ref=cy["reference"],hat_tp=hf["tp"],hat_pred=hf["predicted"],hat_ref=hf["reference"])
    result["summary"]=summarize(result)
    def fs(tp,p,r):return {"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0,"recall":tp/r if r else 0,"f1":2*tp/(p+r) if p+r else 0}
    result["families"]={"cymbal":fs(fam["cym_tp"],fam["cym_pred"],fam["cym_ref"]),"hat":fs(fam["hat_tp"],fam["hat_pred"],fam["hat_ref"])}
    result["canonical_score"]=sel.score(result["summary"])
    return result

def choose_integrated(res,baseline,targets):
    d=sel.select(res,baseline["summary"],target_parts=targets,max_part_drop=.035,target_tolerance=.012)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    acts=infer_all()
    scales={"recall":.85,"default":1.0,"precision":1.15}
    peaksets={k:{song:peaks(acts[song],scale) for song in SONGS} for k,scale in scales.items()}
    root=EXP/"generated-search-adtof";report={"schema":1,"cycles":[]}

    # 163 standalone ADTOF. Select the operating point using the four direct
    # classes plus collapsed cymbal-family F1, not aggregate all-part F1.
    res={}
    for label in ("recall","default","precision"):
        name="c163_"+label
        res[name]=evaluate(name,lambda song,l=label:adtof_events_for_song(peaksets[l][song]),root/"cycle163")
        by=res[name]["summary"]["by_group"];cy=res[name]["families"]["cymbal"]["f1"]
        comp=np.mean([by[g]["f1"] for g in ("kick","snare","hat","tom")]+[cy])
        res[name]["component_score"]=float(comp);res[name]["threshold_scale"]=scales[label]
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"parts":by,"families":res[name]["families"],"component_score":comp},ensure_ascii=False),flush=True)
    ranking=sorted(res,key=lambda n:(res[n]["component_score"],res[n]["summary"]["f1"]),reverse=True)
    win=ranking[0];best_adtof=res[win];scale=best_adtof["threshold_scale"]
    report["cycles"].append({"cycle":163,"candidates":res,"ranking":ranking,"winner":win})

    baseline=evaluate("baseline",current_events,root/"baseline")

    # 164 hat component.
    adlabel=min(scales,key=lambda k:abs(scales[k]-scale))
    res={}
    configs=[("c164_base","base"),("c164_replace","replace"),("c164_loose","confirm_loose"),("c164_balanced","confirm_balanced"),("c164_strict","confirm_strict")]
    for name,mode in configs:
        def fn(song,m=mode):
            cur=current_events(song);ah=[t for t,g in peaksets[adlabel][song] if g=="hat"]
            return replace_hat(song,cur,ah,m)
        res[name]=evaluate(name,fn,root/"cycle164");res[name]["hat_mode"]=mode
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose_integrated(res,baseline,("hat",));win=d["winner"] or "c164_base";best=res[win]
    report["cycles"].append({"cycle":164,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    # 165 cymbal confirmation on the winning hat mode.
    res={}
    for name,cmode in [("c165_base","base"),("c165_loose","loose"),("c165_balanced","balanced"),("c165_strict","strict")]:
        def fn(song,c=cmode):
            cur=current_events(song);ah=[t for t,g in peaksets[adlabel][song] if g=="hat"]
            cur=replace_hat(song,cur,ah,best["hat_mode"])
            ac=[t for t,g in peaksets[adlabel][song] if g=="crash"]
            return gate_cymbal(song,cur,ac,c)
        res[name]=evaluate(name,fn,root/"cycle165");res[name]["hat_mode"]=best["hat_mode"];res[name]["cymbal_mode"]=cmode
        print("SUMMARY",name,json.dumps({"overall":res[name]["summary"]["f1"],"crash":res[name]["summary"]["by_group"]["crash"],"ride":res[name]["summary"]["by_group"]["ride"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
    d=choose_integrated(res,best,("crash","ride"));win=d["winner"] or "c165_base";best2=res[win]
    report["cycles"].append({"cycle":165,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    report["final"]={"winner":win,"adtof_threshold_scale":scale,"hat_mode":best2["hat_mode"],"cymbal_mode":best2["cymbal_mode"],
      "summary":best2["summary"],"families":best2["families"],"canonical_score":best2["canonical_score"],
      "detailed":detail.compare_dir(root/"cycle165"/win,win)["aggregate"]}
    (EXP/"results-iterative-adtof.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    main()
