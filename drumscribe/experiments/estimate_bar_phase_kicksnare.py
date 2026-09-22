"""Benchmark bar phase from browser-equivalent kick/snare events only.

No metadata is used before prediction. Tests the historical crash-context phase
search and several musically structured variants using BPM v3.
"""
from __future__ import annotations
import importlib.util,json,math
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
v1=loadmod("bpm1",EXP/"estimate_bpm.py")
v3=loadmod("bpm3",EXP/"estimate_bpm_v3.py")

def circ(t,phase,p):
    x=(t-phase)%p;return min(x,p-x)

def resolve(raw,band,sim):
    idx={g:i for i,g in enumerate(ev.ORDER)}
    keep=[True]*len(raw);ks=[i for i,e in enumerate(raw) if e[1]=="kick"];ss=[i for i,e in enumerate(raw) if e[1]=="snare"];used=set()
    for ki in ks:
        kt,_,_,kp=raw[ki];near=[si for si in ss if si not in used and abs(raw[si][0]-kt)<=.04]
        if not near:continue
        si=min(near,key=lambda j:abs(raw[j][0]-kt));used.add(si);_,_,_,sp=raw[si]
        b0=float(band[0,kp]);b1=float(band[1,sp]);kr=b0/(b1+1e-7);sr=b1/(b0+1e-7)
        sk=float(sim[idx["kick"],kp]);sn=float(sim[idx["snare"],sp])
        if sk>=.52 and sn>=.56 and .72<=kr<=1.38:continue
        if (sr>=1.55 and sn>=.42) or (sn>=sk+.18 and sr>=1.15):keep[ki]=False
        else:keep[si]=False
    return [e for i,e in enumerate(raw) if keep[i]]

def score_phase(events,bpm,phase,mode):
    beat=60/bpm;bar=4*beat;sig=max(.025,.10*beat)
    total=0.;den=0.
    for t,g,s,p in events:
        if g not in ("kick","snare"):continue
        pos=(t-phase)%bar
        if mode=="legacy":
            target=[0.0];w=1.8 if g=="kick" else .75
        elif mode=="roles":
            target=[0,2*beat] if g=="kick" else [beat,3*beat];w=1.25 if g=="kick" else 1.0
        elif mode=="headkick":
            target=[0] if g=="kick" else [beat,3*beat];w=1.55 if g=="kick" else .75
        elif mode=="headkick_backbeat":
            if g=="kick":target=[0,2*beat];w=1.0
            else:target=[beat,3*beat];w=.75
        else: # weighted_head: all canonical roles plus extra reward at beat 1
            target=[0,2*beat] if g=="kick" else [beat,3*beat];w=1.0 if g=="kick" else .75
        d=min(circ(pos,z,bar) for z in target)
        value=w*min(2.2,math.sqrt(max(s,0)))*math.exp(-.5*(d/sig)**2)
        if mode=="weighted_head" and g=="kick":
            dh=circ(pos,0,bar)
            value+=.42*min(2.2,math.sqrt(max(s,0)))*math.exp(-.5*(dh/(.14*beat))**2)
        total+=value;den+=w
    return total/max(1e-9,den)

def estimate(events,bpm,mode):
    beat=60/bpm;bar=4*beat
    best=(-1,0)
    for q in range(512):
        ph=bar*q/512;sc=score_phase(events,bpm,ph,mode)
        if sc>best[0]:best=(sc,ph)
    # refine
    center=best[1]
    for d in np.linspace(-.10*beat,.10*beat,81):
        ph=(center+d)%bar;sc=score_phase(events,bpm,ph,mode)
        if sc>best[0]:best=(sc,ph)
    return {"phase":best[1],"score":best[0]}

def err(a,b,p):
    d=abs((a-b)%p);return min(d,p-d)

def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    modes=["legacy","roles","headkick","headkick_backbeat","weighted_head"]
    totals={m:[] for m in modes};report={"schema":1,"songs":{}}
    for song in SONGS:
        x=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3");spec=ev.spectrum(x);band,sim=ev.features(spec,tmpl)
        raw=ev.acoustic_candidates(band,sim);events=resolve(raw,band,sim)
        env,_=v1.onset_envelope(ROOT/"DruMaster/songs"/song/"drums.mp3");bpm=v3.estimate(env,band)["bpm"]
        preds={m:estimate(events,bpm,m) for m in modes}
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text());tbpm=float(meta["bpm"]);beat=60/tbpm;bar=4*beat
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0));ref=shift%bar
        rows={}
        for m,p in preds.items():
            eb=err(p["phase"],ref,bar)/beat;totals[m].append(eb);rows[m]={**p,"error_beats":eb}
        report["songs"][song]={"bpm":bpm,"ref":ref,"methods":rows}
        print("BARPH",song,json.dumps(report["songs"][song],ensure_ascii=False),flush=True)
    report["summary"]={m:{"mean":float(np.mean(v)),"max":float(np.max(v))} for m,v in totals.items()}
    (EXP/"results-bar-phase-kicksnare.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("SUMMARY",json.dumps(report["summary"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
