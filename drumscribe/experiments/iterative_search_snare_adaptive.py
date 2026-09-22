"""Cycles 148-150: song-adaptive snare supplementation on fusion-v6.

Prediction-time proxy:
  high-recall snare count / balanced snare count
Only songs with unusually large disagreement receive extra snare candidates.
Supplement candidates are filtered by kick collision and repetition/backbeat.

No chart.mid data is used until generated MIDI is written.

Cycle 148: disagreement ratio threshold 1.15 / 1.30 / 1.45
Cycle 149: kick-veto window 25 / 45 / 65 ms
Cycle 150: rescue support = consensus / repeat2 / backbeat+repeat
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")
sel=loadmod("sel",EXP/"selection_policy.py")

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}
BASE=EXP/"generated-search-fusion-v6/cycle144/c144_adaptive"
HIGH=EXP/"generated-search-best-fusion/cycle80/c80_snare_pattern"
SAFE=EXP/"generated-search-snare-additive/cycle114/c114_repeat3"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def phase(events,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;sc=0.
        for t,g in events:
            if g not in ("kick","snare"):continue
            w=1.7 if g=="kick" else .8;x=(t-ph)%bar;d=min(x,bar-x)
            sc+=w*math.exp(-.5*(d/max(.025,.1*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def slot(t,ph,bar):return int(round((((t-ph)%bar)/bar)*16))%16

def repeat_support(xs,t,ph,bar):
    s=slot(t,ph,bar);b=math.floor((t-ph)/bar);bars=set()
    for x in xs:
        bx=math.floor((x-ph)/bar)
        if abs(bx-b)<=6 and slot(x,ph,bar)==s:bars.add(bx)
    return len(bars)

def enforce(events):
    mins={"kick":.045,"snare":.038,"hat":.035,"pedal_hat":.045,"tom":.050,"crash":.090,"ride":.045,"other":.040}
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.
        for t in arr:
            if t-last>=mins.get(g,.04):ded.append((t,g));last=t
    ded.sort();out=[];i=0;pri={"snare":.93,"tom":.88,"crash":.86,"ride":.84,"hat":.60}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[e for e in c if e[1] not in HANDS];h=[e for e in c if e[1] in HANDS]
        h=sorted(h,key=lambda e:pri.get(e[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def adaptive_snare(song,ratio_thr,kick_window,rescue):
    b=rows(BASE,song);base_sn=[t for t,g in b if g=="snare"];kicks=[t for t,g in b if g=="kick"]
    high=[t for t,g in rows(HIGH,song) if g=="snare"];safe=[t for t,g in rows(SAFE,song) if g=="snare"]
    ratio=len(high)/max(1,len(base_sn))
    if ratio<ratio_thr:
        return b,{"base":len(base_sn),"high":len(high),"safe":len(safe),"ratio":ratio,"mode":"base","added":0}
    m=meta(song);ph,beat,bar=phase(b,m);pool=sorted(set(base_sn+high+safe));add=[]
    for t in high:
        if near(base_sn,t,.040):continue
        collision=near(kicks,t,kick_window)
        consensus=near(safe,t,.055)
        rep=repeat_support(pool,t,ph,bar)
        bb=slot(t,ph,bar) in (4,12)
        if rescue=="consensus":
            keep=consensus and not collision
        elif rescue=="repeat2":
            keep=(consensus or rep>=2) and (not collision or (consensus and rep>=3))
        else:
            keep=(consensus and not collision) or (bb and rep>=2 and (not collision or rep>=3))
        if keep:add.append((t,"snare"))
    return enforce(b+add),{"base":len(base_sn),"high":len(high),"safe":len(safe),"ratio":ratio,"mode":"adaptive","added":len(add)}

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,ratio_thr,kick_window,rescue,outdir):
    result={"ratio_threshold":ratio_thr,"kick_window":kick_window,"rescue":rescue,"song_decisions":{},"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr,diag=adaptive_snare(song,ratio_thr,kick_window,rescue);result["song_decisions"][song]=diag
        p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":tp/n if n else 0,"recall":tp/mr if mr else 0,"f1":2*tp/(n+mr) if n+mr else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":0,"by_group":{}}
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];gf=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":gf,
          "false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,"count_ratio":b/c if c else None,
          "mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
    result["summary"]=s;result["canonical_score"]=sel.score(s);result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def choose(res,baseline):
    d=sel.select(res,baseline["summary"],target_parts=("snare",),max_part_drop=.02,target_tolerance=.006)
    for n in res:res[n]["guard"]=d["guards"][n]
    return d

def main():
    root=EXP/"generated-search-snare-adaptive";report={"schema":1,"cycles":[]}
    baseline=evaluate("baseline",99,.045,"consensus",root/"baseline")

    res={}
    for name,r in [("c148_r115",1.15),("c148_r130",1.30),("c148_r145",1.45)]:
        res[name]=evaluate(name,r,.045,"repeat2",root/"cycle148");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,baseline);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":148,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    res={}
    for name,w in [("c149_k25",.025),("c149_k45",.045),("c149_k65",.065)]:
        res[name]=evaluate(name,best["ratio_threshold"],w,best["rescue"],root/"cycle149");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":149,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})

    res={}
    for name,x in [("c150_consensus","consensus"),("c150_repeat2","repeat2"),("c150_backbeat","backbeat")]:
        res[name]=evaluate(name,best["ratio_threshold"],best["kick_window"],x,root/"cycle150");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    d=choose(res,best);win=d["winner"] or d["ranking"][0];best=res[win]
    report["cycles"].append({"cycle":150,"candidates":res,"ranking":d["ranking"],"winner":win,"guards":d["guards"]})
    report["final"]={"winner":win,"summary":best["summary"],"canonical_score":best["canonical_score"],"guard":best["guard"],
      "ratio_threshold":best["ratio_threshold"],"kick_window":best["kick_window"],"rescue":best["rescue"],
      "song_decisions":best["song_decisions"],"detailed":best["detailed"]}
    (EXP/"results-iterative-snare-adaptive.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
