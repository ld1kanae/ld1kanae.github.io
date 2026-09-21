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

    hat_fdr=float((by.get("hat") or {}).get("false_discovery_rate") or 0)
    pedal_fdr=float((by.get("pedal_hat") or {}).get("false_discovery_rate") or 0)
    crash_fdr=float((by.get("crash") or {}).get("false_discovery_rate") or 0)
    ride_fdr=float((by.get("ride") or {}).get("false_discovery_rate") or 0)

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
