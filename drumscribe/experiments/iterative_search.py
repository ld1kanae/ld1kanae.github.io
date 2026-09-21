"""Iterative DrumScribe search.

For every candidate:
  drums.mp3 -> candidate transcription -> real .mid file -> re-parse .mid -> chart.mid scoring

The reference MIDI is never used during transcription. It is opened only after the
candidate MIDI has been written.

Shared musical constraints:
- crash: accepted only near the estimated measure head
- among snare/tom/hat/crash/ride, keep at most two simultaneous hits
- kick is exempt from that two-limb limit
"""
from __future__ import annotations
import copy, json, math
from collections import Counter
from pathlib import Path
import importlib.util
import numpy as np

ROOT=Path(".")
spec=importlib.util.spec_from_file_location("ev",ROOT/"drumscribe/experiments/evaluate_v2.py")
ev=importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
LIMITED={"snare","hat","tom","crash","ride"}
PITCH={"kick":36,"snare":38,"hat":42,"tom":45,"crash":49,"ride":51}
BASE_THRESH={"kick":.58,"snare":.70,"hat":.19,"tom":1.5,"cymbal":1.0}
BASE_DIST={"kick":.075,"snare":.075,"hat":.055,"tom":.09,"cymbal":.12}

def vlq(n):
    out=[n&127]
    while n>>7:
        n >>= 7; out.insert(0,(n&127)|128)
    return bytes(out)

def write_midi(path,events,bpm):
    ppq=480; tps=ppq*bpm/60; tempo=round(60_000_000/bpm)
    packets=[(0,0,bytes([255,81,3,(tempo>>16)&255,(tempo>>8)&255,tempo&255]))]
    for e in events:
        tick=max(0,round(e["time"]*tps)); pitch=PITCH[e["group"]]
        vel=max(1,min(127,round(72+18*math.log1p(max(0,e["confidence"])))))
        packets += [(tick,2,bytes([0x99,pitch,vel])),(tick+max(1,round(.07*tps)),1,bytes([0x89,pitch,0]))]
    packets.sort(key=lambda x:(x[0],x[1],x[2][1] if len(x[2])>1 else 0))
    body=bytearray(); prev=0
    for tick,_,data in packets:
        body += vlq(tick-prev)+data; prev=tick
    body += bytes([0,255,47,0])
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b"MThd"+(6).to_bytes(4,"big")+bytes([0,0,0,1,1,224])+b"MTrk"+len(body).to_bytes(4,"big")+body)

def peaks(signal,threshold,distance):
    out=[]; minimum=max(1,int(distance*ev.SR/ev.HOP))
    for t in range(2,len(signal)-2):
        if signal[t] <= signal[t-1] or signal[t] < signal[t+1] or signal[t] < threshold: continue
        if signal[t]-min(signal[t-2],signal[t+2]) < .07: continue
        if signal[t] < 2.4*ev.local_floor(signal,2.4)[t]: continue
        out.append(t)
    out.sort(key=lambda p:signal[p],reverse=True)
    kept=[]
    for p in out:
        if not any(abs(q-p)<minimum for q in kept): kept.append(p)
    return kept

def raw_candidates(band,sim):
    sig={"kick":band[0],"snare":band[1],"hat":band[3],"tom":band[1],"cymbal":band[2]}
    raw=[]
    for g in ["kick","snare","hat","tom","cymbal"]:
        s=sig[g]
        for p in peaks(s,BASE_THRESH[g],BASE_DIST[g]):
            if g=="kick" and band[0,p] < .48*band[1,p]: continue
            if g=="snare" and band[1,p] < .62*band[0,p]: continue
            if g=="tom" and (sim[3,p] < .44 or sim[3,p] < .85*max(sim[0,p],sim[1,p])): continue
            if g=="cymbal" and sim[4,p] < .39: continue
            if g=="kick":
                conf=float(s[p]/BASE_THRESH[g] + .45*sim[0,p])
            elif g=="snare":
                conf=float(s[p]/BASE_THRESH[g] + .45*sim[1,p])
            elif g=="tom":
                conf=float(s[p]/BASE_THRESH[g] + .6*sim[3,p])
            elif g=="cymbal":
                conf=float(s[p]/BASE_THRESH[g] + .7*sim[4,p])
            else:
                conf=float(s[p]/BASE_THRESH[g])
            raw.append({"time":p*ev.HOP/ev.SR,"frame":p,"group":g,"score":float(s[p]),"confidence":conf})
    return sorted(raw,key=lambda e:(e["time"],e["group"]))

def ks_arbitrate(raw,band,sim,p):
    out=[dict(e) for e in raw]
    kick=[(i,e) for i,e in enumerate(out) if e["group"]=="kick"]
    snare=[(i,e) for i,e in enumerate(out) if e["group"]=="snare"]
    dead=set(); used=set()
    for ki,k in kick:
        near=[(si,s) for si,s in snare if si not in used and abs(s["time"]-k["time"])<=p["ks_window"]]
        if not near: continue
        si,s=min(near,key=lambda z:abs(z[1]["time"]-k["time"])); used.add(si)
        fr=k["frame"]; b0=float(band[0,fr]); b1=float(band[1,fr])
        kr=b0/(b1+1e-7); sr=b1/(b0+1e-7); sk=float(sim[0,fr]); ss=float(sim[1,fr])
        layered=sk>=p["layer_k"] and ss>=p["layer_s"] and p["layer_ratio_lo"]<=kr<=p["layer_ratio_hi"]
        if layered: continue
        snare_strong=(sr>=p["snare_ratio"] and ss>=p["snare_sim"]) or (ss>=sk+p["snare_margin"] and sr>=p["snare_ratio2"])
        if snare_strong: dead.add(ki)
        else: dead.add(si)
    return [e for i,e in enumerate(out) if i not in dead]

def estimate_phase(events,bpm,num,den):
    beat=60/bpm*4/den; bar=beat*num; sigma=max(.035,beat*.11)
    best=(-1,0.)
    for i in range(128):
        ph=bar*i/128; score=0.
        for e in events:
            w=3.2 if e["group"]=="cymbal" else 1.8 if e["group"]=="kick" else .8 if e["group"]=="snare" else .1
            x=(e["time"]-ph)%bar; d=min(x,bar-x)
            score += w*e["confidence"]*math.exp(-.5*(d/sigma)**2)
        if score>best[0]:best=(score,ph)
    return best[1]

def bar_distance_beats(t,bpm,phase,num,den):
    beat=60/bpm*4/den; bar=beat*num
    x=(t-phase)%bar; d=min(x,bar-x)
    return d/beat

def periodic_support(times,i,bpm):
    if len(times)<3:return 0.
    t=times[i];best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        count=0
        for k in (-2,-1,1,2):
            target=t+k*step
            if any(abs(x-target)<=.07 for x in times):count+=1
        best=max(best,count/4)
    return best

def cymbal_split(events,band,sim,bpm,num,den,p):
    phase=estimate_phase(events,bpm,num,den)
    cym=[e for e in events if e["group"]=="cymbal"]
    rest=[dict(e) for e in events if e["group"]!="cymbal"]
    times=[e["time"] for e in cym]
    for i,e in enumerate(cym):
        fr=e["frame"]; dist=bar_distance_beats(e["time"],bpm,phase,num,den)
        per=periodic_support(times,i,bpm)
        # Hard musical prior requested by the user:
        # crash is never admitted outside the measure-head window.
        crash_ok=dist<=p["crash_window_beats"] and e["score"]>=p["crash_score"]
        # Ride is a separate repeating cymbal behavior and is not subject to
        # the crash-only measure-head restriction.
        high_ratio=float(band[3,fr]/(band[2,fr]+1e-7))
        ride_ok=per>=p["ride_periodic"] and high_ratio>=p["ride_high_ratio"] and e["score"]>=p["ride_score"]
        if crash_ok and (not ride_ok or dist<=p["crash_prefer_beats"]):
            x=dict(e);x["group"]="crash";x["confidence"]*=1+.45*(1-dist/max(p["crash_window_beats"],1e-6));rest.append(x)
        elif ride_ok:
            x=dict(e);x["group"]="ride";x["confidence"]*=1+.3*per;rest.append(x)
    return sorted(rest,key=lambda e:(e["time"],e["group"]))

def enforce_two_limb(events,p):
    evs=sorted([dict(e) for e in events],key=lambda e:e["time"])
    kept=[]; i=0
    while i<len(evs):
        start=evs[i]["time"]; j=i+1
        while j<len(evs) and evs[j]["time"]-start<=p["poly_window"]: j+=1
        cluster=evs[i:j]
        exempt=[e for e in cluster if e["group"] not in LIMITED]
        limited=[e for e in cluster if e["group"] in LIMITED]
        limited.sort(key=lambda e:(e["confidence"],e["score"]),reverse=True)
        kept += exempt + limited[:2]
        i=j
    return sorted(kept,key=lambda e:(e["time"],PITCH.get(e["group"],127)))

def transcribe(songdata,p):
    raw=raw_candidates(songdata["band"],songdata["sim"])
    stage=ks_arbitrate(raw,songdata["band"],songdata["sim"],p)
    stage=cymbal_split(stage,songdata["band"],songdata["sim"],songdata["bpm"],songdata["num"],songdata["den"],p)
    stage=enforce_two_limb(stage,p)
    return stage

def evaluate_candidate(name,p,data,outdir):
    result={"params":p,"songs":{}}; total=Counter()
    for song,d in data.items():
        pred=transcribe(d,p)
        mid=outdir/name/f"{song}.mid"; write_midi(mid,pred,d["bpm"])
        # IMPORTANT: score the real generated MIDI, not in-memory events.
        parsed=ev.midi_events(mid)
        truth=ev.midi_events(d["folder"]/"chart.mid")
        sc=ev.score(parsed,truth,d["shift"]); cf=ev.confusion(parsed,truth,d["shift"])
        sc["confusion"]=cf; sc["count_ratio"]=ev.count_ratios(sc)
        result["songs"][song]=sc
        total.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                     kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            total[f"{g}_tp"]+=x["tp"];total[f"{g}_pred"]+=x["predicted"];total[f"{g}_ref"]+=x["reference"]
    tp,n,m=total["tp"],total["predicted"],total["reference"]
    s={"tp":tp,"predicted":n,"reference":m,
       "precision":round(tp/n,4) if n else 0,"recall":round(tp/m,4) if m else 0,
       "f1":round(2*tp/(n+m),4) if n+m else 0,
       "kick_to_snare":total["kick_to_snare"],"snare_to_kick":total["snare_to_kick"],"by_group":{}}
    macro=[]
    for g in ["kick","snare","hat","tom","crash","ride"]:
        a,b,c=total[f"{g}_tp"],total[f"{g}_pred"],total[f"{g}_ref"]
        f=2*a/(b+c) if b+c else 0
        macro.append(f)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,
                          "precision":round(a/b,4) if b else 0,
                          "recall":round(a/c,4) if c else 0,
                          "f1":round(f,4),"count_ratio":round(b/c,4) if c else None}
    s["macro_f1"]=round(sum(macro)/len(macro),4)
    # Selection: maximize actual-note F1, but do not reward a candidate that
    # recreates the known kick->snare failure. Macro F1 is a secondary signal.
    ks_rate=total["kick_to_snare"]/max(1,total["kick_ref"])
    s["selection_score"]=round(s["f1"] + .10*s["macro_f1"] - .20*ks_rate,6)
    result["summary"]=s
    return result

def base_params():
    return {
      "ks_window":.040,"layer_k":.52,"layer_s":.56,"layer_ratio_lo":.72,"layer_ratio_hi":1.38,
      "snare_ratio":1.55,"snare_sim":.42,"snare_margin":.18,"snare_ratio2":1.15,
      "crash_window_beats":.14,"crash_prefer_beats":.055,"crash_score":1.0,
      "ride_periodic":.70,"ride_high_ratio":.55,"ride_score":1.0,
      "poly_window":.035
    }

def variants_cycle1():
    b=base_params(); out={}
    a=copy.deepcopy(b);a.update(crash_window_beats=.09,ride_periodic=.80,poly_window=.028,snare_ratio=1.65,snare_margin=.22);out["c1_strict"]=a
    a=copy.deepcopy(b);out["c1_balanced"]=a
    a=copy.deepcopy(b);a.update(crash_window_beats=.20,ride_periodic=.55,poly_window=.045,snare_ratio=1.45,snare_margin=.14);out["c1_recall"]=a
    return out

def derive_cycle2(best):
    out={}
    a=copy.deepcopy(best);a.update(snare_ratio=best["snare_ratio"]+.12,snare_margin=best["snare_margin"]+.05,poly_window=max(.025,best["poly_window"]-.005));out["c2_kick_guard"]=a
    a=copy.deepcopy(best);a.update(ride_periodic=max(.45,best["ride_periodic"]-.10),ride_high_ratio=max(.45,best["ride_high_ratio"]-.05),ride_score=max(.85,best["ride_score"]-.08));out["c2_ride_recover"]=a
    a=copy.deepcopy(best);a.update(crash_window_beats=max(.07,best["crash_window_beats"]-.035),crash_score=best["crash_score"]+.10,poly_window=best["poly_window"]+.005);out["c2_crash_precision"]=a
    return out

def derive_cycle3(best):
    out={}
    a=copy.deepcopy(best);a.update(poly_window=max(.025,best["poly_window"]-.005),snare_ratio=best["snare_ratio"]+.06,ride_periodic=min(.9,best["ride_periodic"]+.05));out["c3_precision"]=a
    a=copy.deepcopy(best);a.update(poly_window=min(.05,best["poly_window"]+.005),snare_margin=max(.10,best["snare_margin"]-.03),ride_periodic=max(.45,best["ride_periodic"]-.05));out["c3_balanced"]=a
    a=copy.deepcopy(best);a.update(crash_window_beats=max(.06,best["crash_window_beats"]-.02),crash_prefer_beats=max(.03,best["crash_prefer_beats"]-.01),ride_high_ratio=best["ride_high_ratio"]+.05);out["c3_cymbal_guard"]=a
    return out

def load_data():
    tm=ev.templates(ROOT/"DruMaster/assets/drums"); data={}
    for song in SONGS:
        folder=ROOT/"DruMaster/songs"/song; meta=json.loads((folder/"song.json").read_text())
        bpm=float(meta["bpm"]);ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
        shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
        x=ev.audio(folder/"drums.mp3");spec=ev.spectrum(x);band,sim=ev.features(spec,tm)
        data[song]={"folder":folder,"bpm":bpm,"num":int(ts.get("numerator",4)),"den":int(ts.get("denominator",4)),
                    "shift":shift,"band":band,"sim":sim}
        print("loaded",song,flush=True)
    return data

def choose(results):
    ranked=sorted(results.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)
    return ranked

def main():
    data=load_data(); root=ROOT/"drumscribe/experiments/generated-search"; report={"schema":1,"cycles":[]}
    cycles=[variants_cycle1]
    current=None
    for cycle in range(1,4):
        variants=variants_cycle1() if cycle==1 else derive_cycle2(current) if cycle==2 else derive_cycle3(current)
        results={}
        for name,p in variants.items():
            print("evaluate",cycle,name,flush=True)
            results[name]=evaluate_candidate(name,p,data,root/f"cycle{cycle}")
            print(name,results[name]["summary"],flush=True)
        ranked=choose(results); winner=ranked[0][0]; current=copy.deepcopy(results[winner]["params"])
        # Carry runner-up metadata when within 0.01 selection score.
        carry=[name for name,res in ranked if ranked[0][1]["summary"]["selection_score"]-res["summary"]["selection_score"]<=.01]
        report["cycles"].append({"cycle":cycle,"candidates":results,"ranking":[n for n,_ in ranked],"winner":winner,"carried_close":carry})
    report["final"]={"winner":report["cycles"][-1]["winner"],
                     "summary":report["cycles"][-1]["candidates"][report["cycles"][-1]["winner"]]["summary"],
                     "params":current}
    p=ROOT/"drumscribe/experiments/results-iterative-search.json"
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__": main()
