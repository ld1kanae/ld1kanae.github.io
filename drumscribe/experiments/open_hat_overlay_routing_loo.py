"""Route high-confidence open-hat overlay candidates without creating a third hand.

Uses the frozen pre-overlay browser MIDI at commit 8ef45bf... so the experiment
does not feed its own later rescue output back into candidate generation.

Held-out protocol:
- base articulation + overlay classifier trained on other four songs + GMD,
- repeat gate uses held-song probabilities/BPM only,
- chart.mid is used only for final scoring.

Routing hypotheses:
 A add_safe             : current browser behavior; add GM46 only with a free hand
 B replace_ride_blocked : if both hands are occupied and a ride is present, convert ride->open
 C prefer_metal_replace : when selected, prefer ride/crash->open conversion; otherwise add with free hand

Kick/snare/tom are never removed.
"""
from __future__ import annotations
import importlib.util,json,subprocess,shutil
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
BASE_REF="8ef45bf10b97f4ae5e324b88376821c2f5f27fa5"
TMP=EXP/"_pre_overlay_browser"
BASE_THRESHOLD=.575
POLICIES=("add_safe","replace_ride_blocked","prefer_metal_replace")

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
sa=loadmod("openhat_route_selfadapt",EXP/"open_hat_overlay_selfadapt.py")
ov=sa.ov;oh=sa.oh

def materialize_base():
    if TMP.exists():shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    for s in SONGS:
        for ext in ("mid","json"):
            rel=f"drumscribe/experiments/generated-v2-browser/{s}.{ext}"
            data=subprocess.check_output(["git","show",f"{BASE_REF}:{rel}"])
            (TMP/f"{s}.{ext}").write_bytes(data)
    oh.BASE=TMP
    print("FROZEN_BASE",BASE_REF,flush=True)

def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        best=None
        for j,u in enumerate(ref):
            if j in used:continue
            d=abs(t-u)
            if d<=w and (best is None or d<best[0]):best=(d,j)
        if best is not None:used.add(best[1]);tp+=1
    return tp

def articulation(pred_open,pred_closed,refs):
    def met(p,r):
        tp=greedy(p,r);return {"tp":tp,"predicted":len(p),"reference":len(r),
          "precision":tp/len(p) if p else 0.,"recall":tp/len(r) if r else 0.,
          "f1":2*tp/(len(p)+len(r)) if len(p)+len(r) else 0.}
    return {"open":met(pred_open,refs[46]),"closed":met(pred_closed,refs[42])}

def aggregate_art(per):
    z=Counter()
    for m in per.values():
      for c in ("open","closed"):
        q=m[c];z[f"{c}t"]+=q["tp"];z[f"{c}p"]+=q["predicted"];z[f"{c}r"]+=q["reference"]
    out={}
    for c in ("open","closed"):
      tp,p,r=z[f"{c}t"],z[f"{c}p"],z[f"{c}r"]
      out[c]={"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
        "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.}
    out["macroF1"]=.5*(out["open"]["f1"]+out["closed"]["f1"]);return out

def overall_metrics(rows,truth):
    groups=("kick","snare","hat","tom","crash","ride","pedal_hat","other")
    by={};tp=predn=refn=0
    for g in groups:
        p=[t for t,gg,pitch in rows if gg==g];r=[t for t,gg,pitch in truth if gg==g]
        q=greedy(p,r);by[g]={"tp":q,"predicted":len(p),"reference":len(r)}
        tp+=q;predn+=len(p);refn+=len(r)
    return {"tp":tp,"predicted":predn,"reference":refn,
      "precision":tp/predn if predn else 0.,"recall":tp/refn if refn else 0.,
      "f1":2*tp/(predn+refn) if predn+refn else 0.,"by_group":by}

def route(rows,selected,policy):
    mutable=[list(r) for r in rows];removed=set();adds=[];stats=Counter()
    for t in selected:
        near=[(i,r) for i,r in enumerate(mutable) if i not in removed and abs(r[0]-t)<=.035]
        hands=[(i,r) for i,r in near if r[1] in ("snare","tom","hat","crash","ride")]
        ride=[(i,r) for i,r in near if r[1]=="ride"]
        crash=[(i,r) for i,r in near if r[1]=="crash"]
        target=None
        if policy=="prefer_metal_replace":
            target=(ride or crash)
            target=min(target,key=lambda z:abs(z[1][0]-t)) if target else None
        elif policy=="replace_ride_blocked" and len(hands)>=2 and ride:
            target=min(ride,key=lambda z:abs(z[1][0]-t))
        if target is not None:
            removed.add(target[0]);adds.append((t,"hat",46));stats["replaced_"+target[1][1]]+=1
        elif len(hands)<2:
            adds.append((t,"hat",46));stats["added"]+=1
        else:
            stats["blocked"]+=1
    out=[tuple(r) for i,r in enumerate(mutable) if i not in removed]+adds
    return sorted(out),dict(stats)

def fold(d,held,hx,hy,gx,gy,policy,seed):
    tr=[s for s in SONGS if s!=held]
    bm=ov.train_base(d,tr,hx,hy);om,tinfo=ov.train_overlay(d,tr,gx,gy,ov.FAMILIES and "C_metal_snare_kick",seed)
    hp=ov.probs(bm,d[held]["X"]["timbre_norm"])
    bo=[t for t,p in zip(d[held]["hats"],hp) if p>=BASE_THRESHOLD]
    bc=[t for t,p in zip(d[held]["hats"],hp) if p<BASE_THRESHOLD]
    oo=d[held]["overlay"];times=np.asarray([a[0] for a in oo["anchors"]],float);pp=ov.probs(om,oo["X"])
    bpm=float(d[held]["side"].get("bpm") or 0)
    mask,adapt=sa.select("repeat_gate",times,pp,bpm)
    selected=[float(t) for t,yes in zip(times,mask) if yes and not ov.near(bo,float(t),.060)]
    routed,rstats=route(d[held]["rows"],selected,policy)
    # Every successful add/replacement creates an open prediction at selected time.
    routed_open=[t for t,g,p in routed if p==46]
    # For held-out articulation, use base model's 42/46 predictions plus routed
    # structural GM46. Frozen MIDI's train-all 46 labels must not leak here.
    routed_added=[t for t,g,p in routed if p==46 and not any(abs(t-h)<=.060 for h in d[held]["hats"])]
    open_pred=sorted(bo+routed_added)
    art=articulation(open_pred,bc,d[held]["refs"])
    truth=oh.truth(held)
    overall=overall_metrics(routed,truth)
    diag={"selected":len(selected),"routing":rstats,"adapt":adapt,"train":tinfo,
      "trueOverlayDiagnostic":int(oo["y"].sum()),"selectedTpDiagnostic":sum(ov.near(d[held]["refs"][46],t,.080) for t in selected)}
    return art,overall,diag

def main():
    materialize_base();d=ov.local_prepare();hx,hy,gx,gy,manifest=ov.gmd_collect()
    base_art={};base_over={}
    for i,s in enumerate(SONGS):
        tr=[x for x in SONGS if x!=s];bm=ov.train_base(d,tr,hx,hy);hp=ov.probs(bm,d[s]["X"]["timbre_norm"])
        bo=[t for t,p in zip(d[s]["hats"],hp) if p>=BASE_THRESHOLD];bc=[t for t,p in zip(d[s]["hats"],hp) if p<BASE_THRESHOLD]
        base_art[s]=articulation(bo,bc,d[s]["refs"]);base_over[s]=overall_metrics(d[s]["rows"],oh.truth(s))
    baselineArt=aggregate_art(base_art)
    def agg_over(per):
        tp=sum(v["tp"] for v in per.values());p=sum(v["predicted"] for v in per.values());r=sum(v["reference"] for v in per.values())
        by={}
        for g in next(iter(per.values()))["by_group"]:
            by[g]={k:sum(v["by_group"][g][k] for v in per.values()) for k in ("tp","predicted","reference")}
        return {"tp":tp,"predicted":p,"reference":r,"precision":tp/p,"recall":tp/r,"f1":2*tp/(p+r),"by_group":by}
    baselineOverall=agg_over(base_over)
    out={"schema":1,"frozenBrowserRef":BASE_REF,"baselineArticulation":baselineArt,
      "baselineOverall":baselineOverall,"policies":{}}
    for pi,policy in enumerate(POLICIES):
        ap={};op={};folds={}
        for i,s in enumerate(SONGS):
            a,o,dg=fold(d,s,hx,hy,gx,gy,policy,500+i) # same model seed across routing policies
            ap[s]=a;op[s]=o;folds[s]={"articulation":a,"overall":o,"diag":dg}
        aa=aggregate_art(ap);oo=agg_over(op)
        eligible=(aa["open"]["f1"]>baselineArt["open"]["f1"] and
          aa["open"]["precision"]>=baselineArt["open"]["precision"]-.025 and
          oo["f1"]>=baselineOverall["f1"])
        out["policies"][policy]={"articulation":aa,"overall":oo,"folds":folds,"eligible":eligible}
        print("RESULT",policy,json.dumps({"eligible":eligible,"articulation":aa,"overall":oo}),flush=True)
    elig=[q|{"name":k} for k,q in out["policies"].items() if q["eligible"]]
    best=max(elig,key=lambda q:(q["overall"]["f1"],q["articulation"]["open"]["f1"])) if elig else None
    out["retained"]=best["name"] if best else "none"
    out["note"]="Development routing study. Constants/policies were selected on the five-song development set; future-song validation required."
    (EXP/"results-open-hat-overlay-routing-loo.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("RETAINED",out["retained"],flush=True)
if __name__=="__main__":main()
