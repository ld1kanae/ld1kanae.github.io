"""Canonical candidate selection policy for DrumScribe PDCA.

This does not replace raw metrics. It produces a single ordering only after
recording all per-song/per-part metrics, and explicitly includes worst-song
performance so one-song failures cannot be hidden by aggregate F1.
"""
from __future__ import annotations

PARTS=("kick","snare","hat","pedal_hat","tom","crash","ride")
CORE=("kick","snare","hat","tom","crash","ride")

def score(summary:dict)->dict:
    by=summary.get("by_group") or {}
    overall=float(summary.get("f1") or 0)
    part_f1=[float((by.get(g) or {}).get("f1") or 0) for g in PARTS]
    core_f1=[float((by.get(g) or {}).get("f1") or 0) for g in CORE]
    worst=[]
    hard_fail=[]
    for g in PARTS:
        x=by.get(g) or {}
        ref=int(x.get("reference") or 0)
        pred=int(x.get("predicted") or 0)
        w=x.get("worst_song_f1")
        if ref>0:
            worst.append(float(w or 0))
            if pred==0:hard_fail.append(g)
    kref=max(1,int((by.get("kick") or {}).get("reference") or 0))
    k2s=float(summary.get("kick_to_snare") or 0)/kref

    def fdr(part):
        x=by.get(part) or {}
        if x.get("false_discovery_rate") is not None:
            return float(x.get("false_discovery_rate") or 0)
        pred=float(x.get("predicted") or 0);tp=float(x.get("tp") or 0)
        return max(0.0,(pred-tp)/pred) if pred else 0.0
    hat_fdr=fdr("hat")
    pedal_fdr=fdr("pedal_hat")
    crash_fdr=fdr("crash")
    ride_fdr=fdr("ride")

    mean_parts=sum(part_f1)/len(part_f1)
    mean_core=sum(core_f1)/len(core_f1)
    mean_worst=sum(worst)/len(worst) if worst else 0

    # Overall timing/classification quality remains important, but every part
    # and the worst song are first-class. False hat/cymbal floods and
    # kick->snare confusion get explicit penalties.
    total=(
        .46*overall
        +.18*mean_parts
        +.12*mean_core
        +.14*mean_worst
        -.06*hat_fdr
        -.025*pedal_fdr
        -.035*crash_fdr
        -.035*ride_fdr
        -.18*k2s
    )
    return {
      "score":round(total,6),
      "overall_f1":round(overall,6),
      "mean_part_f1":round(mean_parts,6),
      "mean_core_f1":round(mean_core,6),
      "mean_worst_song_f1":round(mean_worst,6),
      "kick_to_snare_rate":round(k2s,6),
      "hard_failed_parts":hard_fail,
      "penalties":{
        "hat_fdr":round(hat_fdr,6),"pedal_hat_fdr":round(pedal_fdr,6),
        "crash_fdr":round(crash_fdr,6),"ride_fdr":round(ride_fdr,6)
      }
    }


def part_f1(summary:dict,part:str)->float:
    return float(((summary or {}).get("by_group") or {}).get(part,{}).get("f1",0) or 0)

def eligibility(candidate_summary:dict,baseline_summary:dict,target_parts=(),
                target_tolerance=.01,max_part_drop=.05,meaningful_floor=.10)->dict:
    """Hard non-regression gate before score ordering.

    A candidate that gets a better aggregate score by deleting a hard
    instrument cannot become the new all-part base. It can still be retained
    in the component bank.
    """
    reasons=[]
    for part in target_parts:
        b=part_f1(baseline_summary,part);v=part_f1(candidate_summary,part)
        if v+target_tolerance<b:
            reasons.append(f"target_regression:{part}:{b:.4f}->{v:.4f}")
    for part in PARTS:
        b=part_f1(baseline_summary,part);v=part_f1(candidate_summary,part)
        if b>=meaningful_floor and v<=0:
            reasons.append(f"part_collapsed:{part}:{b:.4f}->0")
        elif b>=meaningful_floor and b-v>max_part_drop:
            reasons.append(f"part_drop:{part}:{b:.4f}->{v:.4f}")
    bviol=baseline_summary.get("two_limb_violations")
    vviol=candidate_summary.get("two_limb_violations")
    if bviol==0 and vviol not in (None,0):
        reasons.append(f"two_limb_regression:0->{vviol}")
    return {"eligible":not reasons,"reasons":reasons}

def select(candidates:dict,baseline_summary:dict,target_parts=(),**guard_kwargs)->dict:
    scored=[]
    guards={}
    for name,obj in candidates.items():
        summary=obj.get("summary",obj)
        guard=eligibility(summary,baseline_summary,target_parts,**guard_kwargs)
        guards[name]=guard
        scored.append((guard["eligible"],score(summary)["score"],name))
    scored.sort(reverse=True)
    winner=next((name for ok,_,name in scored if ok),None)
    return {"winner":winner,"ranking":[x[2] for x in scored],"guards":guards}
