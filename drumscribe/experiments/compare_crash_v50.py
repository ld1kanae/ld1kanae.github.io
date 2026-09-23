from __future__ import annotations
import importlib.util,json
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
VARIANTS=["confidence-115","confidence-125","confidence-135"]
D=EXP/"generated-crash-v50"
spec=importlib.util.spec_from_file_location("ev_crash50",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        cand=[(abs(t-u),j) for j,u in enumerate(ref) if j not in used and abs(t-u)<=w]
        if cand:
            _,j=min(cand);used.add(j);tp+=1
    return tp
def metric(pred,ref):
    tp=greedy(pred,ref);p=len(pred);r=len(ref)
    return {"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
            "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.,"falsePositive":p-tp}
def times(events,notes,shift=0.):
    return sorted(t+shift for t,g,n in events if n in notes)
def aggregate(rows,key):
    tp=sum(x[key]["tp"] for x in rows);p=sum(x[key]["predicted"] for x in rows);r=sum(x[key]["reference"] for x in rows)
    return {"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,
            "recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.,"falsePositive":p-tp}

baseline=json.loads((EXP/"results-crash-v49.json").read_text())["variants"]["legacy"]["summary"]
out={"schema":1,"date":"2026-09-23","experiment":"crash confidence sweep v50",
     "referencePolicy":"chart.mid used only after fresh Chromium prediction.","baselineLegacy":baseline,"variants":{}}
for variant in VARIANTS:
    rows=[]
    for song in SONGS:
        side=json.loads((D/variant/f"{song}.json").read_text())
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        export=float(side.get("exportOffsetSec",0) or 0)
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        pred=ev.midi_events(D/variant/f"{song}.mid");truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        row={"song":song}
        defs={"crash":({49},{49,52,55,57}),"hatFamily":({42,46},{42,46}),
              "kick":({36},{35,36}),"snare":({38},{37,38,39,40}),"tom":({45},{41,43,45,47,48,50})}
        for k,(pn,rn) in defs.items():row[k]=metric(times(pred,pn,-export),times(truth,rn,shift))
        row["policy"]=side.get("adtofInfo",{}).get("cymbalPolicy",{}).get("crashPostGate",{})
        rows.append(row)
    summary={k:aggregate(rows,k) for k in ("crash","hatFamily","kick","snare","tom")}
    ktp=sum(summary[k]["tp"] for k in ("kick","snare","tom"));kp=sum(summary[k]["predicted"] for k in ("kick","snare","tom"));kr=sum(summary[k]["reference"] for k in ("kick","snare","tom"))
    summary["kst"]={"tp":ktp,"predicted":kp,"reference":kr,"precision":ktp/kp,"recall":ktp/kr,"f1":2*ktp/(kp+kr)}
    out["variants"][variant]={"summary":summary,"songs":rows,"deltaVsLegacy":{
      "crashF1":summary["crash"]["f1"]-baseline["crash"]["f1"],
      "crashPrecision":summary["crash"]["precision"]-baseline["crash"]["precision"],
      "crashRecall":summary["crash"]["recall"]-baseline["crash"]["recall"],
      "crashFalsePositive":summary["crash"]["falsePositive"]-baseline["crash"]["falsePositive"],
      "kstF1":summary["kst"]["f1"]-baseline["kst"]["f1"],
      "hatFamilyF1":summary["hatFamily"]["f1"]-baseline["hatFamily"]["f1"]
    }}
out["ranking"]=sorted(VARIANTS,key=lambda v:(out["variants"][v]["summary"]["crash"]["f1"],out["variants"][v]["summary"]["crash"]["precision"]),reverse=True)
(EXP/"results-crash-v50.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False,indent=2))
