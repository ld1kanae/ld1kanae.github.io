"""Cycles 64-66: snare recall with kick-confusion suppression.

Starts from the best all-part recall-repair candidate (cycle63).
Uses only previously generated audio-derived predictions during filtering:
- base snare/kick
- LOSO ML snare
- DSP-separated snare
- rhythm repetition estimated from predicted events
Reference chart.mid is used only after candidate MIDI has been written.

Cycle 64: three supplement/conflict rules.
Cycle 65: three kick-veto windows.
Cycle 66: three repetition-support thresholds.
"""
from __future__ import annotations
import importlib.util, json, math
from collections import Counter
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

BASE=EXP/"generated-search-recall-repair/cycle63/c63_pedal_keep"
ML=EXP/"generated-round4-ml"
DSP=EXP/"generated-search-drumsep-rate/cycle47/c47_precision"

def rows(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def song_meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def near(xs,t,w):
    return any(abs(x-t)<=w for x in xs)

def phase(events,m):
    bpm=float(m["bpm"]); ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4)); bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96; sc=0.
        for t,g in events:
            if g not in ("kick","snare"): continue
            w=1.7 if g=="kick" else .8
            x=(t-ph)%bar; d=min(x,bar-x)
            sc+=w*math.exp(-.5*(d/max(.025,.10*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def slot(t,ph,bar):
    x=((t-ph)%bar)/bar
    return int(round(x*16))%16

def support(times,t,ph,bar,window=6):
    target=slot(t,ph,bar); b=math.floor((t-ph)/bar); bars=set()
    for x in times:
        bx=math.floor((x-ph)/bar)
        if abs(bx-b)<=window and slot(x,ph,bar)==target:
            bars.add(bx)
    return len(bars)

def backbeat(t,ph,bar):
    # 4/4 slots around beats 2 and 4 on a 16-slot bar.
    s=slot(t,ph,bar)
    return s in (4,12)

def enforce(events):
    # de-duplicate same group, then enforce max two hand-played notes.
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g); last=-999.
        mind=.035 if g in ("snare","hat","ride") else .045
        for t in arr:
            if t-last>=mind: ded.append((t,g)); last=t
    ded=sorted(ded); out=[]; i=0
    pri={"snare":.92,"tom":.86,"crash":.82,"ride":.78,"hat":.60}
    while i<len(ded):
        t=ded[i][0]; j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j]; ex=[x for x in c if x[1] not in HANDS]; h=[x for x in c if x[1] in HANDS]
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2]
        out.extend(ex+h); i=j
    return sorted(out)

def apply_rule(song,rule,kick_window,repeat_need):
    b=rows(BASE,song); ml=rows(ML,song); dsp=rows(DSP,song)
    base_sn=[t for t,g in b if g=="snare"]; kicks=[t for t,g in b if g=="kick"]
    ml_sn=[t for t,g in ml if g=="snare"]; dsp_sn=[t for t,g in dsp if g=="snare"]
    m=song_meta(song); ph,beat,bar=phase(b,m)
    pool=sorted(set(round(t,4) for t in base_sn+ml_sn+dsp_sn))
    add=[]
    for t in ml_sn:
        if near(base_sn,t,.040):continue
        k=near(kicks,t,kick_window)
        d=near(dsp_sn,t,.060)
        rep=support(pool,t,ph,bar)
        bb=backbeat(t,ph,bar)
        if rule=="consensus_veto":
            keep=d and (not k or (bb and rep>=repeat_need))
        elif rule=="pattern_veto":
            keep=(d or rep>=repeat_need) and (not k or (d and bb and rep>=repeat_need))
        elif rule=="backbeat_rescue":
            keep=(d and not k) or (bb and rep>=repeat_need) or ((not k) and rep>=repeat_need+1)
        else:
            keep=False
        if keep:add.append((t,"snare"))
    return enforce(b+add)

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,rule,kick_window,repeat_need,outdir):
    result={"rule":rule,"kick_window":kick_window,"repeat_need":repeat_need,"songs":{}}; tot=Counter()
    for song in SONGS:
        m=song_meta(song); predrows=apply_rule(song,rule,kick_window,repeat_need)
        p=outdir/name/f"{song}.mid";write(p,predrows,float(m["bpm"]))
        pred=ev.midi_events(p); truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift); cf=ev.confusion(pred,truth,shift)
        sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():
            tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mref,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mref,4) if mref else 0,
       "f1":round(2*tp/(n+mref),4) if n+mref else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    part=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,
          "f1":round(f,4),"count_ratio":round(b/c,4) if c else None,
          "mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):part.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]); pedal=s["by_group"]["pedal_hat"]["f1"]
    # Reward all-part quality; specifically penalize kick->snare because it was
    # the user's major audible failure mode.
    s["selection_score"]=round(s["f1"]+.20*sum(part)/len(part)+.06*pedal-.32*ks,6)
    result["summary"]=s;result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-snare-veto"; report={"schema":1,"cycles":[]}
    res={}
    for name,rule in [("c64_consensus_veto","consensus_veto"),("c64_pattern_veto","pattern_veto"),("c64_backbeat_rescue","backbeat_rescue")]:
        res[name]=evaluate(name,rule,.045,2,root/"cycle64");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":64,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,w in [("c65_veto25",.025),("c65_veto45",.045),("c65_veto65",.065)]:
        res[name]=evaluate(name,best["rule"],w,best["repeat_need"],root/"cycle65");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":65,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,k in [("c66_repeat1",1),("c66_repeat2",2),("c66_repeat3",3)]:
        res[name]=evaluate(name,best["rule"],best["kick_window"],k,root/"cycle66");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":66,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"rule":res[win]["rule"],"kick_window":res[win]["kick_window"],"repeat_need":res[win]["repeat_need"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-snare-veto.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
