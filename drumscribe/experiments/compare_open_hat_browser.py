"""Score real-browser closed/open hi-hat articulation separately.

This complements compare_browser.py, whose 'hat' group intentionally merges
MIDI 42 and 46. Predictions are returned from exported MIDI to audio time using
the browser export offset, then matched to reference 42/46 within 80 ms.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev_open_browser",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def greedy(pred,ref,w=.080):
    used=set();tp=0;errors=[]
    for t in sorted(pred):
        cand=[(abs(t-u),j) for j,u in enumerate(ref) if j not in used and abs(t-u)<=w]
        if cand:
            d,j=min(cand);used.add(j);tp+=1;errors.append(d)
    return tp,errors

def metrics(pred,ref):
    tp,err=greedy(pred,ref)
    p=tp/len(pred) if pred else 0.
    r=tp/len(ref) if ref else 0.
    return {"tp":tp,"predicted":len(pred),"reference":len(ref),
      "precision":p,"recall":r,"f1":2*tp/(len(pred)+len(ref)) if len(pred)+len(ref) else 0.,
      "mean_abs_error_sec":sum(err)/len(err) if err else None}

def main():
    per={};tot=Counter()
    for song in SONGS:
        side=json.loads((EXP/"generated-v2-browser"/f"{song}.json").read_text())
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        export=float(side.get("exportOffsetSec",0) or 0)
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))

        pred=ev.midi_events(EXP/"generated-v2-browser"/f"{song}.mid")
        truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        pc=sorted(t-export for t,g,p in pred if p==42)
        po=sorted(t-export for t,g,p in pred if p==46)
        rc=sorted(t+shift for t,g,p in truth if p==42)
        ro=sorted(t+shift for t,g,p in truth if p==46)

        cm=metrics(pc,rc);om=metrics(po,ro)
        per[song]={"closed":cm,"open":om,
          "predictedHatTotal":len(pc)+len(po),"referenceHatTotal":len(rc)+len(ro),
          "openSharePredicted":len(po)/(len(pc)+len(po)) if len(pc)+len(po) else 0.,
          "openShareReference":len(ro)/(len(rc)+len(ro)) if len(rc)+len(ro) else 0.}
        for name,m in (("closed",cm),("open",om)):
            tot[f"{name}_tp"]+=m["tp"];tot[f"{name}_p"]+=m["predicted"];tot[f"{name}_r"]+=m["reference"]

    summary={}
    for name in ("closed","open"):
        tp,p,r=tot[f"{name}_tp"],tot[f"{name}_p"],tot[f"{name}_r"]
        summary[name]={"tp":tp,"predicted":p,"reference":r,
          "precision":tp/p if p else 0.,"recall":tp/r if r else 0.,
          "f1":2*tp/(p+r) if p+r else 0.}
    summary["macroF1"]=.5*(summary["closed"]["f1"]+summary["open"]["f1"])
    report={"schema":1,"source":"real Chromium generated MIDI","toleranceSec":.080,
      "summary":summary,"songs":per}
    (EXP/"results-v2-browser-open-hat.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
