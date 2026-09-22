"""Beat-phase benchmark from current predicted kick/snare events.

BPM comes from v3. This isolates continuous quarter-note phase from the
bar-level 1-vs-3 decision. chart/song metadata are scoring-only.
"""
from __future__ import annotations
import importlib.util,json,math
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
BASE=EXP/"generated-search-component-merge-v7/cycle194/c194_basecrash"

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
v1=loadmod("bpm1",EXP/"estimate_bpm.py")
v3=loadmod("bpm3",EXP/"estimate_bpm_v3.py")
repair=loadmod("repair",EXP/"iterative_search_overtrigger_repair.py")

def events(song):
    return [(t,g) for t,g,*_ in repair.ev.midi_events(BASE/f"{song}.mid")]

def circ(t,phase,p):
    x=(t-phase)%p
    return min(x,p-x)

def search_phase(evs,bpm,groups,sigma_frac,weights):
    p=60/bpm
    xs=[(t,weights.get(g,1.0)) for t,g in evs if g in groups]
    out=[]
    for q in range(512):
        ph=p*q/512
        score=sum(w*math.exp(-.5*(circ(t,ph,p)/(sigma_frac*p))**2) for t,w in xs)/max(1,sum(w for _,w in xs))
        out.append((score,ph))
    out.sort(reverse=True)
    return {"phase_sec":out[0][1],"score":out[0][0],"runner_up":out[1][0],"count":len(xs)}

def main():
    report={"schema":1,"songs":{}}
    modes={
      "kick":({"kick"},.10,{"kick":1}),
      "snare":({"snare"},.10,{"snare":1}),
      "kick_snare":({"kick","snare"},.10,{"kick":1,"snare":1}),
      "kick_weighted":({"kick","snare"},.08,{"kick":1.35,"snare":.75}),
      "tight":({"kick","snare"},.06,{"kick":1.2,"snare":1}),
    }
    totals={k:[] for k in modes}
    for song in SONGS:
        env,band=v1.onset_envelope(ROOT/"DruMaster/songs"/song/"drums.mp3")
        bpm=v3.estimate(env,band)["bpm"];evs=events(song)
        preds={k:search_phase(evs,bpm,*v) for k,v in modes.items()}
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        truth=float(meta["bpm"]);beat=60/truth
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        ref=shift%beat
        scored={}
        for k,p in preds.items():
            d=abs((p["phase_sec"]-ref)%beat);d=min(d,beat-d);eb=d/beat;totals[k].append(eb)
            scored[k]={"prediction":p,"error_sec":d,"error_beats":eb}
        report["songs"][song]={"bpm":bpm,"truth_bpm":truth,"reference_beat_phase_sec":ref,"methods":scored}
        print("BEATPH",song,json.dumps(report["songs"][song],ensure_ascii=False),flush=True)
    report["summary"]={k:{"mean_abs_beats":float(np.mean(v)),"max_abs_beats":float(np.max(v))} for k,v in totals.items()}
    (EXP/"results-beat-phase.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("SUMMARY",json.dumps(report["summary"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
