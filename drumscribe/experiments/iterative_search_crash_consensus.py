"""Cycles 70-72: crash consensus with soft downbeat prior.

Prediction-time inputs are only audio-derived MIDI candidates and BPM/time
signature metadata. chart.mid is consulted only after each output MIDI is
written.

Cycle 70: strict source agreement vs downbeat-or-agreement vs gap-aware.
Cycle 71: three bar-phase estimators.
Cycle 72: three downbeat widths.
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
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

BASE=EXP/"generated-search-recall-repair/cycle63/c63_pedal_keep"
SOFT=EXP/"generated-search-separation/cycle40/c40_soft"
STRICT=EXP/"generated-search-composite-v2/cycle39/c39_crash_strict"
BAL=EXP/"generated-search-composite-v2/cycle39/c39_crash_balanced"

def rows(path,song):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]
def meta(song):return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)

def bar_spec(m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    return beat,bar

def phase_score(t,ph,bar,beat):
    x=(t-ph)%bar;d=min(x,bar-x)
    return math.exp(-.5*(d/max(.025,.11*beat))**2)

def infer_phase(base_events,soft,strong,m,kind):
    beat,bar=bar_spec(m);best=(-1,0.)
    for q in range(128):
        ph=bar*q/128;sc=0.
        if kind in ("kick","joint"):
            for t,g in base_events:
                if g=="kick":sc+=1.6*phase_score(t,ph,bar,beat)
                elif kind=="joint" and g=="snare":
                    # snare is weaker downbeat evidence.
                    sc+=.25*phase_score(t,ph,bar,beat)
        if kind in ("crash","joint"):
            for t in soft:
                w=1.7 if near(strong,t,.065) else .55
                sc+=w*phase_score(t,ph,bar,beat)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def enforce(events):
    ded=[]
    for g in GROUPS:
        arr=sorted(t for t,gg in events if gg==g);last=-999.;mind=.09 if g=="crash" else .035 if g in ("hat","snare","ride") else .045
        for t in arr:
            if t-last>=mind:ded.append((t,g));last=t
    ded=sorted(ded);out=[];i=0;pri={"snare":.9,"tom":.86,"crash":.84,"ride":.78,"hat":.6}
    while i<len(ded):
        t=ded[i][0];j=i
        while j<len(ded) and ded[j][0]-t<=.033:j+=1
        c=ded[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
    return sorted(out)

def choose(song,rule,phase_kind,width):
    b=rows(BASE,song);soft=[t for t,g in rows(SOFT,song) if g=="crash"];strict=[t for t,g in rows(STRICT,song) if g=="crash"];bal=[t for t,g in rows(BAL,song) if g=="crash"]
    strong=sorted(strict+bal);m=meta(song);ph,beat,bar=infer_phase(b,soft,strong,m,phase_kind)
    chosen=[]
    for i,t in enumerate(soft):
        agree=near(strong,t,.065)
        x=(t-ph)%bar;db=min(x,bar-x)/beat
        prev=t-soft[i-1] if i else 999.
        # Long crash gap is a section-boundary hint, not a sufficient condition.
        gap=prev>=2.0*beat
        if rule=="agreement":
            keep=agree
        elif rule=="downbeat_or_agreement":
            keep=agree or db<=width
        else:
            keep=agree or (db<=width and gap)
        if keep:chosen.append(t)
    # Rescue strict/balanced candidates only when they are at a measure head
    # and not already represented by the soft source.
    if rule!="agreement":
        for t in strong:
            if near(chosen,t,.065):continue
            x=(t-ph)%bar;db=min(x,bar-x)/beat
            if db<=width and not near(soft,t,.14):chosen.append(t)
    others=[e for e in b if e[1]!="crash"]
    return enforce(others+[(t,"crash") for t in chosen])

def write(path,events,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in events],bpm)

def evaluate(name,rule,phase_kind,width,outdir):
    result={"rule":rule,"phase_kind":phase_kind,"width":width,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rr=choose(song,rule,phase_kind,width);p=outdir/name/f"{song}.mid";write(p,rr,float(m["bpm"]))
        pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid");shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mr=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mr,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mr,4) if mr else 0,"f1":round(2*tp/(n+mr),4) if n+mr else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});ref=x.get("reference",0)
            if ref:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+ref) if x.get("predicted",0)+ref else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),
          "count_ratio":round(b/c,4) if c else None,"mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"]);ped=s["by_group"]["pedal_hat"]["f1"]
    s["selection_score"]=round(s["f1"]+.20*sum(parts)/len(parts)+.06*ped-.32*ks,6);result["summary"]=s
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    root=EXP/"generated-search-crash-consensus";report={"schema":1,"cycles":[]}
    res={}
    for name,rule in [("c70_agreement","agreement"),("c70_downbeat_or","downbeat_or_agreement"),("c70_gap","gap")]:
        res[name]=evaluate(name,rule,"joint",.18,root/"cycle70");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":70,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,pk in [("c71_kick","kick"),("c71_crash","crash"),("c71_joint","joint")]:
        res[name]=evaluate(name,best["rule"],pk,best["width"],root/"cycle71");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":71,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,w in [("c72_head10",.10),("c72_head18",.18),("c72_head28",.28)]:
        res[name]=evaluate(name,best["rule"],best["phase_kind"],w,root/"cycle72");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":72,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    # Do not force adoption: include original base as reference score externally.
    report["final"]={"winner":win,"summary":res[win]["summary"],"rule":res[win]["rule"],"phase_kind":res[win]["phase_kind"],"width":res[win]["width"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-crash-consensus.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
