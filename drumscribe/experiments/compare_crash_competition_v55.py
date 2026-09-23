from __future__ import annotations
import importlib.util,json
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
VARIANTS=["legacy","competition-open-state","competition-template","competition-hybrid"]
D=EXP/"generated-crash-competition-v55"
spec=importlib.util.spec_from_file_location("ev55",EXP/"evaluate_v2.py")
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
    return {"tp":tp,"predicted":p,"reference":r,
      "precision":tp/p if p else 0.,"recall":tp/r if r else 0.,
      "f1":2*tp/(p+r) if p+r else 0.,"falsePositive":p-tp}
def times(events,notes,shift=0.):
    return sorted(t+shift for t,g,n in events if n in notes)
def aggregate(rows,key):
    tp=sum(r[key]["tp"] for r in rows);p=sum(r[key]["predicted"] for r in rows);ref=sum(r[key]["reference"] for r in rows)
    return {"tp":tp,"predicted":p,"reference":ref,
      "precision":tp/p if p else 0.,"recall":tp/ref if ref else 0.,
      "f1":2*tp/(p+ref) if p+ref else 0.,"falsePositive":p-tp}
def near_equal(a,b,tol=.002):
    return len(a)==len(b) and all(abs(x-y)<=tol for x,y in zip(a,b))

report={"schema":1,"date":"2026-09-23","experiment":"crash-vs-hat competition v55",
 "referencePolicy":"chart.mid used only after each fresh Chromium prediction.","variants":{}}
raw={}
for variant in VARIANTS:
    rows=[];raw[variant]={}
    for song in SONGS:
        side=json.loads((D/variant/f"{song}.json").read_text())
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        export=float(side.get("exportOffsetSec",0) or 0)
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        pred=ev.midi_events(D/variant/f"{song}.mid"); truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        row={"song":song}
        defs={
          "crash":({49},{49,52,55,57}),
          "ride":({51},{51,53,59}),
          "hatFamily":({42,46},{42,46}),
          "metalCollapsed":({42,46,49,51},{42,46,49,51,52,53,55,57,59}),
          "kick":({36},{35,36}),"snare":({38},{37,38,39,40}),"tom":({45},{41,43,45,47,48,50})
        }
        for k,(pn,rn) in defs.items():row[k]=metric(times(pred,pn,-export),times(truth,rn,shift))
        comp=side.get("adtofInfo",{}).get("cymbalPolicy",{}).get("crashCompetition",{})
        row["competition"]={k:comp.get(k) for k in ("enabled","variant","collisions","removed","kept","rawSupported","openStateWins","templateWins","hybridWins")}
        rows.append(row)
        raw[variant][song]={k:times(pred,n,-export) for k,n in {"kick":{36},"snare":{38},"tom":{45}}.items()}
    summary={k:aggregate(rows,k) for k in ("crash","ride","hatFamily","metalCollapsed","kick","snare","tom")}
    ktp=sum(summary[k]["tp"] for k in ("kick","snare","tom"));kp=sum(summary[k]["predicted"] for k in ("kick","snare","tom"));kr=sum(summary[k]["reference"] for k in ("kick","snare","tom"))
    summary["kst"]={"tp":ktp,"predicted":kp,"reference":kr,"precision":ktp/kp if kp else 0.,"recall":ktp/kr if kr else 0.,"f1":2*ktp/(kp+kr) if kp+kr else 0.}
    summary["competition"]={k:sum(int(r["competition"].get(k) or 0) for r in rows) for k in ("collisions","removed","kept","rawSupported","openStateWins","templateWins","hybridWins")}
    report["variants"][variant]={"summary":summary,"songs":rows}

base=report["variants"]["legacy"]["summary"]
for variant in VARIANTS:
    s=report["variants"][variant]["summary"]
    exact=True
    for song in SONGS:
        for k in ("kick","snare","tom"): exact=exact and near_equal(raw["legacy"][song][k],raw[variant][song][k])
    report["variants"][variant]["deltaVsLegacy"]={
      "crashF1":s["crash"]["f1"]-base["crash"]["f1"],
      "crashPrecision":s["crash"]["precision"]-base["crash"]["precision"],
      "crashRecall":s["crash"]["recall"]-base["crash"]["recall"],
      "crashFalsePositive":s["crash"]["falsePositive"]-base["crash"]["falsePositive"],
      "metalCollapsedF1":s["metalCollapsed"]["f1"]-base["metalCollapsed"]["f1"],
      "hatFamilyF1":s["hatFamily"]["f1"]-base["hatFamily"]["f1"],
      "kstF1":s["kst"]["f1"]-base["kst"]["f1"],
      "kstEventsExact2ms":exact
    }
eligible=[v for v in VARIANTS if report["variants"][v]["deltaVsLegacy"]["kstEventsExact2ms"]]
report["ranking"]=sorted(eligible,key=lambda v:(
 report["variants"][v]["summary"]["crash"]["f1"],
 report["variants"][v]["summary"]["crash"]["precision"],
 report["variants"][v]["summary"]["metalCollapsed"]["f1"]),reverse=True)
(EXP/"results-crash-competition-v55.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({v:{"summary":report["variants"][v]["summary"],"delta":report["variants"][v]["deltaVsLegacy"]} for v in VARIANTS},ensure_ascii=False,indent=2))
print("RANKING",report["ranking"])
