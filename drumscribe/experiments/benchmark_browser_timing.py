"""Benchmark browser-equivalent BPM/beat/downbeat timing.

Uses evaluate_v2 acoustic candidates and template similarities that are
available in transcribe.js. No chart/song metadata is read until scoring.

BPM: v3 audio-only estimator.
Beat phase: resolved kick onsets, 512-bin Gaussian phase search.
Bar head: crash-like raw cymbal anchors from crash/ride/hat template ratios,
optionally requiring a simultaneous kick.
"""
from __future__ import annotations
import importlib.util,json,math
from pathlib import Path
import numpy as np

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

ev=loadmod("ev",EXP/"evaluate_v2.py")
v1=loadmod("bpm1",EXP/"estimate_bpm.py")
v3=loadmod("bpm3",EXP/"estimate_bpm_v3.py")
IDX={g:i for i,g in enumerate(ev.ORDER)}

def circ(t,phase,p):
    x=(t-phase)%p
    return min(x,p-x)

def resolve_raw(raw,band,sim):
    keep=[True]*len(raw)
    kicks=[i for i,e in enumerate(raw) if e[1]=="kick"]
    snares=[i for i,e in enumerate(raw) if e[1]=="snare"]
    used=set()
    for ki in kicks:
        kt,_,_,kp=raw[ki]
        near=[si for si in snares if si not in used and abs(raw[si][0]-kt)<=.04]
        if not near: continue
        si=min(near,key=lambda j:abs(raw[j][0]-kt));used.add(si)
        st,_,_,sp=raw[si]
        b0=float(band[0,kp]);b1=float(band[1,sp])
        kr=b0/(b1+1e-7);sr=b1/(b0+1e-7)
        sk=float(sim[IDX["kick"],kp]);ss=float(sim[IDX["snare"],sp])
        layered=sk>=.52 and ss>=.56 and kr>=.72 and kr<=1.38
        if layered: continue
        snare_strong=(sr>=1.55 and ss>=.42) or (ss>=sk+.18 and sr>=1.15)
        if snare_strong:keep[ki]=False
        else:keep[si]=False
    return [e for i,e in enumerate(raw) if keep[i]]

def beat_phase(events,bpm):
    p=60/bpm
    xs=[t for t,g,*_ in events if g=="kick"]
    if not xs:
        xs=[t for t,g,*_ in events if g in ("kick","snare")]
    best=(-1,0)
    sig=.10*p
    for q in range(512):
        ph=p*q/512
        score=sum(math.exp(-.5*(circ(t,ph,p)/sig)**2) for t in xs)/max(1,len(xs))
        if score>best[0]:best=(score,ph)
    return best[1],best[0],len(xs)

def crash_anchors(events,sim,strength,ratio,hat_ratio,require_kick):
    kicks=[t for t,g,*_ in events if g=="kick"]
    out=[]
    for t,g,s,p in events:
        if g!="cymbal_raw":continue
        cs=float(sim[IDX["crash"],p]);rs=float(sim[IDX["ride"],p]);hs=float(sim[IDX["hat"],p])
        if cs<strength or cs<ratio*rs or cs<hat_ratio*hs:continue
        if require_kick and not any(abs(k-t)<=.055 for k in kicks):continue
        out.append((t,cs,rs,hs,s))
    return out

def bar_phase(beat_ph,bpm,anchors,kicks,mode):
    beat=60/bpm;bar=4*beat;sig=.14*beat
    opts=[]
    for off in range(4):
        ph=(beat_ph+off*beat)%bar
        ca=sum((.5+a[1])*math.exp(-.5*(circ(a[0],ph,bar)/sig)**2) for a in anchors)/max(1,len(anchors))
        ka=sum(math.exp(-.5*(circ(t,ph,bar)/(.18*beat))**2) for t in kicks)/max(1,len(kicks))
        score=ca if mode=="crash" else 1.8*ca+.28*ka
        opts.append((score,ph,ca,ka,off))
    opts.sort(reverse=True)
    center=opts[0][1]
    # continuous refine
    best=None
    for d in np.linspace(-.30*beat,.30*beat,121):
        ph=(center+d)%bar
        ca=sum((.5+a[1])*math.exp(-.5*(circ(a[0],ph,bar)/sig)**2) for a in anchors)/max(1,len(anchors))
        ka=sum(math.exp(-.5*(circ(t,ph,bar)/(.18*beat))**2) for t in kicks)/max(1,len(kicks))
        score=ca if mode=="crash" else 1.8*ca+.28*ka
        row=(score,ph,ca,ka)
        if best is None or row[0]>best[0]:best=row
    return best,opts

def features_for(song,tmpl):
    x=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3")
    spec=ev.spectrum(x)
    band,sim=ev.features(spec,tmpl)
    raw=ev.acoustic_candidates(band,sim)
    return band,sim,resolve_raw(raw,band,sim)

def truth(song):
    m=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    bpm=float(m["bpm"]);beat=60/bpm;bar=4*beat
    shift=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
    return bpm,shift%bar

def err(ph,ref,bar):
    d=abs((ph-ref)%bar);return min(d,bar-d)

def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    cache={}
    for song in SONGS:
        print("FEATURE",song,flush=True)
        band,sim,events=features_for(song,tmpl)
        env,_=v1.onset_envelope(ROOT/"DruMaster/songs"/song/"drums.mp3")
        bpm=v3.estimate(env,band)["bpm"]
        bph,bscore,bn=beat_phase(events,bpm)
        cache[song]=(band,sim,events,bpm,bph,bscore,bn)

    configs=[]
    for strength in (.30,.39,.48,.58):
      for ratio in (1.10,1.25,1.45,1.70):
       for hr in (.80,.95,1.10):
        for rk in (False,True):
         configs.append((strength,ratio,hr,rk))

    ranked=[]
    details={}
    for strength,ratio,hr,rk in configs:
        key=f"s{strength:.2f}_r{ratio:.2f}_h{hr:.2f}_k{int(rk)}"
        vals=[];rows={}
        for song in SONGS:
            band,sim,events,bpm,bph,bscore,bn=cache[song]
            anchors=crash_anchors(events,sim,strength,ratio,hr,rk)
            kicks=[t for t,g,*_ in events if g=="kick"]
            # no anchors -> kick-only four-position score is too ambiguous;
            # mark a large error for selection rather than using metadata.
            if anchors:
                best,opts=bar_phase(bph,bpm,anchors,kicks,"combined")
                ph=best[1]
            else:
                ph=bph
            tbpm,ref=truth(song);bar=4*60/tbpm
            eb=err(ph%bar,ref,bar)/(60/tbpm)
            vals.append(eb)
            rows[song]={"bpm":bpm,"beat_phase":bph,"beat_score":bscore,"kick_count":bn,
                        "anchors":len(anchors),"phase":ph,"error_beats":eb}
        mean=float(np.mean(vals));mx=float(np.max(vals))
        objective=mean+.55*mx
        ranked.append((objective,mean,mx,key))
        details[key]=rows
    ranked.sort()
    top=ranked[:20]
    report={"schema":1,"top":[{"key":k,"objective":o,"mean_abs_beats":m,"max_abs_beats":x,"songs":details[k]}
                              for o,m,x,k in top]}
    (EXP/"results-browser-timing-benchmark.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    for row in report["top"][:10]:
        print("TIMING",json.dumps(row,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
