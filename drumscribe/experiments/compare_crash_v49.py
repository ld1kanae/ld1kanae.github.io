from __future__ import annotations
import importlib.util,json
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
VARIANTS=["legacy","raw-gated","confidence-gated","hat-veto"]
D=EXP/"generated-crash-v49"

spec=importlib.util.spec_from_file_location("ev_crash",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)

def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        cand=[(abs(t-u),j) for j,u in enumerate(ref) if j not in used and abs(t-u)<=w]
        if cand:
            _,j=min(cand);used.add(j);tp+=1
    return tp

def metric(pred,ref):
    tp=greedy(pred,ref); p=len(pred); r=len(ref)
    return {"tp":tp,"predicted":p,"reference":r,
            "precision":tp/p if p else 0.,"recall":tp/r if r else 0.,
            "f1":2*tp/(p+r) if p+r else 0.,
            "falsePositive":p-tp}

def times(events,notes,shift=0.):
    return sorted(t+shift for t,g,n in events if n in notes)

def aggregate(rows,key):
    tp=sum(x[key]["tp"] for x in rows); p=sum(x[key]["predicted"] for x in rows); r=sum(x[key]["reference"] for x in rows)
    return {"tp":tp,"predicted":p,"reference":r,
            "precision":tp/p if p else 0.,"recall":tp/r if r else 0.,
            "f1":2*tp/(p+r) if p+r else 0.,
            "falsePositive":p-tp}

report={"schema":1,"date":"2026-09-23","experiment":"crash precision post-gate v49",
        "referencePolicy":"chart.mid used only after fresh Chromium prediction.","variants":{}}
raw_pred={}
for variant in VARIANTS:
    rows=[]; raw_pred[variant]={}
    for song in SONGS:
        side=json.loads((D/variant/f"{song}.json").read_text())
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        export=float(side.get("exportOffsetSec",0) or 0)
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        pred=ev.midi_events(D/variant/f"{song}.mid")
        truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        row={"song":song}
        defs={
          "crash":({49},{49,52,55,57}),
          "ride":({51},{51,53,59}),
          "hatFamily":({42,46},{42,46}),
          "kick":({36},{35,36}),
          "snare":({38},{37,38,39,40}),
          "tom":({45},{41,43,45,47,48,50}),
        }
        for key,(pn,rn) in defs.items():
            row[key]=metric(times(pred,pn,-export),times(truth,rn,shift))
        row["crashPolicy"]=side.get("adtofInfo",{}).get("cymbalPolicy",{}).get("crashPostGate",{})
        rows.append(row)
        raw_pred[variant][song]={k:times(pred,n,-export) for k,n in {
          "kick":{36},"snare":{38},"tom":{45}
        }.items()}
    summary={k:aggregate(rows,k) for k in ("crash","ride","hatFamily","kick","snare","tom")}
    k_tp=sum(summary[k]["tp"] for k in ("kick","snare","tom"))
    k_p=sum(summary[k]["predicted"] for k in ("kick","snare","tom"))
    k_r=sum(summary[k]["reference"] for k in ("kick","snare","tom"))
    summary["kst"]={"tp":k_tp,"predicted":k_p,"reference":k_r,
                    "precision":k_tp/k_p if k_p else 0.,"recall":k_tp/k_r if k_r else 0.,
                    "f1":2*k_tp/(k_p+k_r) if k_p+k_r else 0.}
    report["variants"][variant]={"summary":summary,"songs":rows}

legacy=report["variants"]["legacy"]["summary"]
for variant in VARIANTS:
    s=report["variants"][variant]["summary"]
    exact=True; diffs={}
    for song in SONGS:
        d={}
        for k in ("kick","snare","tom"):
            a=raw_pred["legacy"][song][k]; b=raw_pred[variant][song][k]
            same=len(a)==len(b) and all(abs(x-y)<1e-6 for x,y in zip(a,b))
            d[k]=0 if same else max(len(a),len(b))
            exact=exact and same
        diffs[song]=d
    report["variants"][variant]["deltaVsLegacy"]={
      "crashF1":s["crash"]["f1"]-legacy["crash"]["f1"],
      "crashPrecision":s["crash"]["precision"]-legacy["crash"]["precision"],
      "crashRecall":s["crash"]["recall"]-legacy["crash"]["recall"],
      "crashFalsePositive":s["crash"]["falsePositive"]-legacy["crash"]["falsePositive"],
      "hatFamilyF1":s["hatFamily"]["f1"]-legacy["hatFamily"]["f1"],
      "kstF1":s["kst"]["f1"]-legacy["kst"]["f1"],
      "kstEventsExact":exact,
      "kstEventDiff":diffs
    }

# Candidate ranking: exact KST first, then crash F1, then precision.
ranked=sorted(VARIANTS,key=lambda v:(
    bool(report["variants"][v]["deltaVsLegacy"]["kstEventsExact"]),
    report["variants"][v]["summary"]["crash"]["f1"],
    report["variants"][v]["summary"]["crash"]["precision"]
),reverse=True)
report["ranking"]=ranked
(EXP/"results-crash-v49.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({v:{
  "summary":report["variants"][v]["summary"],
  "delta":report["variants"][v]["deltaVsLegacy"]
} for v in VARIANTS},ensure_ascii=False,indent=2))
print("RANKING",ranked)
