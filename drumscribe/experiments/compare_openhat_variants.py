"""Compare v40 hi-hat variants in real Chromium.

Reference chart.mid is used only after browser transcription has completed.
GM42 and GM46 are scored separately at +/-80 ms. K/S/T are re-scored as a
non-regression guard; the articulation variants must not alter their classes.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
VARIANTS=["base","decay","gmd-rescue","decay-rescue","ride-open","ride-acoustic","ride-decay"]
spec=importlib.util.spec_from_file_location("ev_open_browser",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        cand=[(abs(t-u),j) for j,u in enumerate(ref) if j not in used and abs(t-u)<=w]
        if cand:
            _,j=min(cand);used.add(j);tp+=1
    return tp

def metric(pred,ref):
    tp=greedy(pred,ref);p=tp/len(pred) if pred else 0.;r=tp/len(ref) if ref else 0.
    return {"tp":tp,"predicted":len(pred),"reference":len(ref),
            "precision":p,"recall":r,
            "f1":2*tp/(len(pred)+len(ref)) if len(pred)+len(ref) else 0.}

def note_times(events,notes,shift=0.):
    return sorted(t+shift for t,g,p in events if p in notes)

def aggregate(rows,name):
    tp=sum(r[name]["tp"] for r in rows);p=sum(r[name]["predicted"] for r in rows);ref=sum(r[name]["reference"] for r in rows)
    return {"tp":tp,"predicted":p,"reference":ref,
            "precision":tp/p if p else 0.,"recall":tp/ref if ref else 0.,
            "f1":2*tp/(p+ref) if p+ref else 0.}

def main():
    report={"schema":1,"experiment":"open-hat v40 real-browser variants",
            "toleranceSec":.080,"variants":{}}
    for variant in VARIANTS:
        rows=[]
        for song in SONGS:
            d=EXP/"generated-openhat-v40"/variant
            side=json.loads((d/f"{song}.json").read_text())
            meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
            export=float(side.get("exportOffsetSec",0) or 0)
            shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
            pred=ev.midi_events(d/f"{song}.mid")
            truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
            row={"song":song}
            row["closed"]=metric(note_times(pred,{42},-export),note_times(truth,{42},shift))
            row["open"]=metric(note_times(pred,{46},-export),note_times(truth,{46},shift))
            row["kick"]=metric(note_times(pred,{36},-export),note_times(truth,{35,36},shift))
            row["snare"]=metric(note_times(pred,{38},-export),note_times(truth,{37,38,39,40},shift))
            row["tom"]=metric(note_times(pred,{45},-export),note_times(truth,{41,43,45,47,48,50},shift))
            row["openHatInfo"]=side.get("adtofInfo",{}).get("openHat",{})
            rows.append(row)
        summary={k:aggregate(rows,k) for k in ("closed","open","kick","snare","tom")}
        summary["macroHatF1"]=(summary["closed"]["f1"]+summary["open"]["f1"])/2
        report["variants"][variant]={"summary":summary,"songs":rows}
    base=report["variants"]["base"]["summary"]
    for variant,v in report["variants"].items():
        s=v["summary"]
        v["deltaVsBase"]={
            "macroHatF1":s["macroHatF1"]-base["macroHatF1"],
            "closedF1":s["closed"]["f1"]-base["closed"]["f1"],
            "openF1":s["open"]["f1"]-base["open"]["f1"],
            "kickF1":s["kick"]["f1"]-base["kick"]["f1"],
            "snareF1":s["snare"]["f1"]-base["snare"]["f1"],
            "tomF1":s["tom"]["f1"]-base["tom"]["f1"],
        }
    (EXP/"results-openhat-v40.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:{"summary":v["summary"],"delta":v["deltaVsBase"]}
                      for k,v in report["variants"].items()},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
