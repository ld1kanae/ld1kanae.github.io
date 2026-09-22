"""Downbeat estimator v2 using current audio-only transcription events.

Uses BPM v3 and the current best transcribed MIDI (itself generated from audio,
not chart.mid). Crash events are treated as bar-head anchors only when their
4-beat concentration has a useful margin. Otherwise kick/snare structure
provides the fallback. The selected phase is refined continuously +/-0.3 beat.

song.json/chart timing is scoring-only.
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

def rows(song):
    return [(t,g) for t,g,*_ in repair.ev.midi_events(BASE/f"{song}.mid")]

def cd(t,phase,period):
    x=(t-phase)%period
    return min(x,period-x)

def gauss_dist(t,phase,period,sigma):
    d=cd(t,phase,period)
    return math.exp(-.5*(d/max(1e-6,sigma))**2)

def event_grid_score(events,phase,bpm):
    p=60/bpm;bar=4*p
    kick=[t for t,g in events if g=="kick"]
    snare=[t for t,g in events if g=="snare"]
    crash=[t for t,g in events if g=="crash"]

    sig=.14*p
    crash_align=sum(gauss_dist(t,phase,bar,sig) for t in crash)/max(1,len(crash))
    kick1=sum(gauss_dist(t,phase,bar,.18*p) for t in kick)/max(1,len(kick))
    kick3=sum(gauss_dist(t,phase+2*p,bar,.18*p) for t in kick)/max(1,len(kick))
    sn2=sum(gauss_dist(t,phase+p,bar,.17*p) for t in snare)/max(1,len(snare))
    sn4=sum(gauss_dist(t,phase+3*p,bar,.17*p) for t in snare)/max(1,len(snare))
    snback=.5*(sn2+sn4)

    # Long gaps before a crash make it a stronger structural marker.
    gapw=0.;ws=0.
    last=None
    for t in crash:
        gap=8*p if last is None else min(8*p,max(0,t-last))
        w=.35+.65*min(1,gap/(4*p))
        gapw+=w*gauss_dist(t,phase,bar,sig);ws+=w;last=t
    crash_gap=gapw/max(1e-9,ws)

    return {"crash":crash_align,"crash_gap":crash_gap,"kick1":kick1,"kick3":kick3,
            "snare_back":snback,
            "combined":1.65*crash_align+.65*crash_gap+.55*kick1+.20*kick3+.36*snback}

def estimate(song,env,band,bpm,beat,mode):
    events=rows(song)
    # beat phase comes from BPM v3's robust full-song grid fit
    p=60/bpm;bar=4*p
    opts=[]
    for off in range(4):
        ph=(beat+off*p)%bar
        s=event_grid_score(events,ph,bpm)
        opts.append({"offset":off,"phase":ph,**s})
    key="crash_gap" if mode=="crash" else "combined"
    opts.sort(key=lambda r:r[key],reverse=True)
    top=opts[0];second=opts[1]
    crash_margin=top["crash"]-second["crash"]
    crash_n=sum(g=="crash" for _,g in events)

    if mode=="adaptive":
        # Trust crash only if it forms a distinct bar-position cluster.
        if crash_n>=6 and crash_margin>=.055:
            chosen=top;source="crash_margin"
        else:
            # fallback score discounts crash and emphasizes kick position;
            # compare all four choices again.
            fb=sorted(opts,key=lambda r:.72*r["kick1"]+.22*r["kick3"]+.40*r["snare_back"]+.30*r["crash"],reverse=True)
            chosen=fb[0];source="fallback"
    else:
        chosen=top;source=mode

    # Continuous phase refinement around selected beat position.
    center=chosen["phase"]
    candidates=[]
    for d in np.linspace(-.30*p,.30*p,121):
        ph=(center+d)%bar
        s=event_grid_score(events,ph,bpm)
        if source=="fallback":
            val=.72*s["kick1"]+.22*s["kick3"]+.40*s["snare_back"]+.30*s["crash"]
        elif source=="crash_margin" or mode=="crash":
            val=1.8*s["crash"]+.7*s["crash_gap"]+.28*s["kick1"]+.15*s["snare_back"]
        else:
            val=s["combined"]
        candidates.append((val,ph,s))
    val,phase,s=max(candidates,key=lambda z:z[0])
    return {"bpm":bpm,"beat_phase":beat,"bar_phase_sec":phase,"source":source,
            "crash_count":crash_n,"crash_margin":crash_margin,"coarse":chosen,
            "refined_score":float(val),"refined_features":s,"offset_candidates":opts}

def circ(a,b,p):
    d=abs((a-b)%p);return min(d,p-d)

def main():
    report={"schema":2,"description":"Downbeat v2 with transcription crash anchors and reliability fallback.","songs":{}}
    totals={m:[] for m in ("crash","combined","adaptive")}
    for song in SONGS:
        env,band=v1.onset_envelope(ROOT/"DruMaster/songs"/song/"drums.mp3")
        bpm_info=v3.estimate(env,band)
        bpm=bpm_info["bpm"]
        beat=float(bpm_info["grid_fit"]["phase_sec"])
        preds={m:estimate(song,env,band,bpm,beat,m) for m in totals}

        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        truth=float(meta["bpm"]);ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
        beat=60/truth*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        ref=shift%bar
        out={}
        for m,pred in preds.items():
            e=circ(pred["bar_phase_sec"]%bar,ref,bar);eb=e/beat;totals[m].append(eb)
            out[m]={"prediction":pred,"error_sec":e,"error_beats":eb}
        report["songs"][song]={"truth_bpm":truth,"predicted_bpm":bpm,"reference_bar_phase_sec":ref,"methods":out}
        print("DOWN2",song,json.dumps(report["songs"][song],ensure_ascii=False),flush=True)
    report["summary"]={m:{"mean_abs_beats":float(np.mean(v)),"max_abs_beats":float(np.max(v))}
                       for m,v in totals.items()}
    (EXP/"results-downbeat-estimation-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("SUMMARY",json.dumps(report["summary"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
