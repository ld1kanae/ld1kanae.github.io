from __future__ import annotations
import importlib.util,json
from pathlib import Path
ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";D=EXP/"generated-crash-v52"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"];VARIANTS=["hat-accent-080","hat-accent-100","hat-accent-120"]
spec=importlib.util.spec_from_file_location("ev52",EXP/"evaluate_v2.py");ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        c=[(abs(t-u),j) for j,u in enumerate(ref) if j not in used and abs(t-u)<=w]
        if c:_,j=min(c);used.add(j);tp+=1
    return tp
def metric(pred,ref):
    tp=greedy(pred,ref);p=len(pred);r=len(ref)
    return {"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,"recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.,"falsePositive":p-tp}
def times(events,notes,shift=0):return sorted(t+shift for t,g,n in events if n in notes)
def agg(rows,k):
    tp=sum(r[k]["tp"] for r in rows);p=sum(r[k]["predicted"] for r in rows);ref=sum(r[k]["reference"] for r in rows)
    return {"tp":tp,"predicted":p,"reference":ref,"precision":tp/p if p else 0.,"recall":tp/ref if ref else 0.,"f1":2*tp/(p+ref) if p+ref else 0.,"falsePositive":p-tp}
legacy=json.loads((EXP/"results-crash-v49.json").read_text())["variants"]["legacy"]["summary"]
out={"schema":1,"date":"2026-09-23","experiment":"local hat-accent crash veto v52","baselineLegacy":legacy,"variants":{}}
for v in VARIANTS:
    rows=[]
    for song in SONGS:
        side=json.loads((D/v/f"{song}.json").read_text());meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        export=float(side.get("exportOffsetSec",0) or 0);shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        pred=ev.midi_events(D/v/f"{song}.mid");truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        row={"song":song}
        for k,pn,rn in [("crash",{49},{49,52,55,57}),("kick",{36},{35,36}),("snare",{38},{37,38,39,40}),("tom",{45},{41,43,45,47,48,50})]:
            row[k]=metric(times(pred,pn,-export),times(truth,rn,shift))
        row["policy"]=side.get("adtofInfo",{}).get("cymbalPolicy",{}).get("crashPostGate",{})
        rows.append(row)
    s={k:agg(rows,k) for k in ("crash","kick","snare","tom")}
    ktp=sum(s[k]["tp"] for k in ("kick","snare","tom"));kp=sum(s[k]["predicted"] for k in ("kick","snare","tom"));kr=sum(s[k]["reference"] for k in ("kick","snare","tom"))
    s["kst"]={"tp":ktp,"predicted":kp,"reference":kr,"precision":ktp/kp,"recall":ktp/kr,"f1":2*ktp/(kp+kr)}
    out["variants"][v]={"summary":s,"songs":rows,"deltaVsLegacy":{
      "crashF1":s["crash"]["f1"]-legacy["crash"]["f1"],"crashPrecision":s["crash"]["precision"]-legacy["crash"]["precision"],
      "crashRecall":s["crash"]["recall"]-legacy["crash"]["recall"],"crashFalsePositive":s["crash"]["falsePositive"]-legacy["crash"]["falsePositive"],
      "kstF1":s["kst"]["f1"]-legacy["kst"]["f1"]}}
out["ranking"]=sorted(VARIANTS,key=lambda v:(out["variants"][v]["summary"]["crash"]["f1"],out["variants"][v]["summary"]["crash"]["precision"]),reverse=True)
(EXP/"results-crash-v52.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False,indent=2))
