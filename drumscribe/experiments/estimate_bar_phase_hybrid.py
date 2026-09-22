"""Hybrid browser bar phase: kick/snare hypotheses + crash tie-break.

Two independent kick/snare scorers usually agree; if they differ by about two
beats, raw crash-template evidence is allowed to choose only between those two
hypotheses. This prevents cymbal false positives from selecting arbitrary
quarter-note positions.

No metadata before scoring.
"""
from __future__ import annotations
import importlib.util,json,math
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py");v1=loadmod("bpm1",EXP/"estimate_bpm.py");v3=loadmod("bpm3",EXP/"estimate_bpm_v3.py")
barbase=loadmod("barbase",EXP/"estimate_bar_phase_kicksnare.py")
IDX={g:i for i,g in enumerate(ev.ORDER)}

def circ(t,ph,p):
    x=(t-ph)%p;return min(x,p-x)

def anchors(events,sim,strength,ratio,hat_ratio):
    out=[]
    for t,g,s,p in events:
        if g!="cymbal_raw":continue
        cs=float(sim[IDX["crash"],p]);rs=float(sim[IDX["ride"],p]);hs=float(sim[IDX["hat"],p])
        if cs>=strength and cs>=ratio*rs and cs>=hat_ratio*hs:
            out.append((t,cs))
    return out

def anchor_score(xs,phase,bpm):
    beat=60/bpm;bar=4*beat;sig=.16*beat
    if not xs:return 0.
    return sum((.5+s)*math.exp(-.5*(circ(t,phase,bar)/sig)**2) for t,s in xs)/len(xs)

def phase_dist_beats(a,b,bpm):
    bar=4*60/bpm;d=circ(a,b,bar);return d/(60/bpm)

def truth(song):
    m=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text());b=float(m["bpm"]);beat=60/b;bar=4*beat
    shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
    return b,shift%bar

def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    cache={}
    for song in SONGS:
        x=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3");sp=ev.spectrum(x);band,sim=ev.features(sp,tmpl)
        raw=ev.acoustic_candidates(band,sim);events=barbase.resolve(raw,band,sim)
        env,_=v1.onset_envelope(ROOT/"DruMaster/songs"/song/"drums.mp3");bpm=v3.estimate(env,band)["bpm"]
        legacy=barbase.estimate(events,bpm,"legacy");roles=barbase.estimate(events,bpm,"roles")
        cache[song]=(sim,events,bpm,legacy,roles)

    ranked=[];details={}
    for strength in (.30,.39,.48,.58,.68):
      for ratio in (1.10,1.25,1.45,1.70,2.0):
       for hr in (.80,.95,1.10,1.30):
        for margin in (0,.02,.05,.10,.20):
         key=f"s{strength:.2f}_r{ratio:.2f}_h{hr:.2f}_m{margin:.2f}"
         vals=[];rows={}
         for song,(sim,events,bpm,legacy,roles) in cache.items():
            xs=anchors(events,sim,strength,ratio,hr)
            dlr=phase_dist_beats(legacy["phase"],roles["phase"],bpm)
            sl=anchor_score(xs,legacy["phase"],bpm);sr=anchor_score(xs,roles["phase"],bpm)
            if dlr<.45:
                chosen=legacy["phase"];source="agree"
            elif xs and sr>sl+margin:
                chosen=roles["phase"];source="roles_crash"
            else:
                chosen=legacy["phase"];source="legacy"
            tb,ref=truth(song);beat=60/tb;bar=4*beat
            e=circ(chosen,ref,bar)/beat;vals.append(e)
            rows[song]={"legacy":legacy["phase"],"roles":roles["phase"],"hyp_dist":dlr,
                        "anchors":len(xs),"legacy_anchor":sl,"roles_anchor":sr,
                        "chosen":chosen,"source":source,"error_beats":e}
         mean=float(np.mean(vals));mx=float(np.max(vals));obj=mean+.7*mx
         ranked.append((obj,mean,mx,key));details[key]=rows
    ranked.sort()
    report={"schema":1,"top":[{"key":k,"objective":o,"mean":m,"max":x,"songs":details[k]} for o,m,x,k in ranked[:20]]}
    (EXP/"results-bar-phase-hybrid.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    for r in report["top"][:10]:print("HYBRID",json.dumps(r,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
