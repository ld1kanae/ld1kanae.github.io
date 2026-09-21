"""Cycles 61-63: targeted recall repair for snare/tom/pedal-hat.

Prerequisites:
- hybrid result (optionally pattern-consensus winner)
- generated-round4-ml MIDI export

Cycle 61: three snare supplementation policies
Cycle 62: three tom supplementation policies
Cycle 63: three pedal-hat policies

All supplementation sources originate from drums.mp3 predictions. chart.mid is
used only after the new candidate MIDI is written.
"""
from __future__ import annotations
import importlib.util, json, math, statistics
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
ev=loadmod("ev",EXP/"evaluate_v2.py")
detail=loadmod("detail",EXP/"detailed_metrics.py")
base=loadmod("base",EXP/"iterative_search.py")
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
HANDS={"snare","hat","tom","crash","ride"}

ML=EXP/"generated-round4-ml"
DSP_SNARE=EXP/"generated-search-drumsep-rate/cycle47/c47_precision"
SEP_TOM=EXP/"generated-search-separation/cycle42/c42_snare_roll_recall"
DSP_TOM=EXP/"generated-search-drumsep-rate/cycle47/c47_precision"

def winner_dir(result_file,root,cycle):
    o=json.loads((EXP/result_file).read_text());w=o["final"]["winner"]
    return EXP/root/f"cycle{cycle}"/w,w

def base_dir():
    p=EXP/"results-iterative-pattern-consensus.json"
    if p.exists():return winner_dir("results-iterative-pattern-consensus.json","generated-search-pattern-consensus",57)
    return winner_dir("results-iterative-component-hybrid.json","generated-search-component-hybrid",54)

def events(path,song):
    return [(t,g) for t,g,*_ in ev.midi_events(path/f"{song}.mid")]

def near(times,t,w):
    return any(abs(x-t)<=w for x in times)

def meta(song):
    return json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())

def phase(rows,m):
    bpm=float(m["bpm"]);ts=m.get("timeSignature") or {"numerator":4,"denominator":4}
    beat=60/bpm*4/int(ts.get("denominator",4));bar=beat*int(ts.get("numerator",4))
    best=(-1,0.)
    for q in range(96):
        ph=bar*q/96;sc=0.
        for t,g in rows:
            if g not in ("kick","snare"):continue
            w=1.7 if g=="kick" else .8;x=(t-ph)%bar;d=min(x,bar-x)
            sc+=w*math.exp(-.5*(d/max(.025,.10*beat))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1],beat,bar

def slot(t,ph,bar):
    x=((t-ph)%bar)/bar
    return int(round(x*16))%16

def repeat_support(times,t,ph,bar,window_bars=4):
    s=slot(t,ph,bar);b=math.floor((t-ph)/bar);bars=set()
    for x in times:
        bx=math.floor((x-ph)/bar)
        if abs(bx-b)<=window_bars and slot(x,ph,bar)==s:bars.add(bx)
    return len(bars)

def fill_bars(rows,ph,bar):
    cnt=Counter(math.floor((t-ph)/bar) for t,g in rows if g in HANDS)
    tom=Counter(math.floor((t-ph)/bar) for t,g in rows if g=="tom")
    med=statistics.median(cnt.values()) if cnt else 0
    return {b for b,n in cnt.items() if n>=med+5 or tom[b]>=2}

def enforce(rows):
    rows=sorted(set((round(t,6),g) for t,g in rows));out=[];i=0
    while i<len(rows):
        t=rows[i][0];j=i
        while j<len(rows) and rows[j][0]-t<=.033:j+=1
        c=rows[i:j];ex=[x for x in c if x[1] not in HANDS];h=[x for x in c if x[1] in HANDS]
        pri={"snare":.9,"tom":.86,"crash":.82,"ride":.78,"hat":.60}
        h=sorted(h,key=lambda x:pri.get(x[1],.5),reverse=True)[:2]
        out.extend(ex+h);i=j
    return sorted(out)

def supplement_snare(rows,song,mode):
    base_times=[t for t,g in rows if g=="snare"]
    ml=[t for t,g in events(ML,song) if g=="snare"]
    dsp=[t for t,g in events(DSP_SNARE,song) if g=="snare"]
    m=meta(song);ph,beat,bar=phase(rows,m)
    all_pattern=sorted(base_times+ml)
    add=[]
    for t in ml:
        if near(base_times,t,.045):continue
        if mode=="raw":keep=True
        elif mode=="consensus":keep=near(dsp,t,.060)
        else:
            keep=near(dsp,t,.060) or repeat_support(all_pattern,t,ph,bar,4)>=2
        if keep:add.append((t,"snare"))
    return enforce(rows+add)

def supplement_tom(rows,song,mode):
    sep=[t for t,g in events(SEP_TOM,song) if g=="tom"]
    dsp=[t for t,g in events(DSP_TOM,song) if g=="tom"]
    current=[t for t,g in rows if g=="tom"];m=meta(song);ph,beat,bar=phase(rows,m);fills=fill_bars(rows,ph,bar)
    add=[]
    for t in sep:
        if near(current,t,.055):continue
        b=math.floor((t-ph)/bar)
        if mode=="raw":keep=True
        elif mode=="consensus":keep=near(dsp,t,.070)
        else:keep=(b in fills) and (near(dsp,t,.070) or len([x for x in sep if abs(x-t)<=.7])>=2)
        if keep:add.append((t,"tom"))
    return enforce(rows+add)

def pedal_policy(rows,song,mode):
    if mode=="keep":return rows
    ped=[t for t,g in rows if g=="pedal_hat"];others=[x for x in rows if x[1]!="pedal_hat"]
    if mode=="off":return others
    m=meta(song);bpm=float(m["bpm"])
    def per(t):
        best=0.
        for step in (30/bpm,60/bpm,120/bpm):
            n=sum(any(abs(x-(t+k*step))<=.065 for x in ped) for k in (-2,-1,1,2))
            best=max(best,n/4)
        return best
    kept=[]
    for t in ped:
        local=sum(abs(x-t)<=4*60/bpm for x in ped)
        if per(t)>=.5 and local>=4:kept.append((t,"pedal_hat"))
    return others+kept

def write(path,rows,bpm):
    base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in rows],bpm)

def evaluate(name,basedir,snare_mode,tom_mode,pedal_mode,outdir):
    result={"base":str(basedir),"snare_mode":snare_mode,"tom_mode":tom_mode,"pedal_mode":pedal_mode,"songs":{}};tot=Counter()
    for song in SONGS:
        m=meta(song);rows=events(basedir,song)
        if snare_mode!="base":rows=supplement_snare(rows,song,snare_mode)
        if tom_mode!="base":rows=supplement_tom(rows,song,tom_mode)
        rows=pedal_policy(rows,song,pedal_mode);rows=enforce(rows)
        path=outdir/name/f"{song}.mid";write(path,rows,float(m["bpm"]))
        pred=ev.midi_events(path);truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=m["playback"]["stemOffsetSec"]+m["playback"].get("midiOffsetSec",0)
        sc=ev.score(pred,truth,shift);cf=ev.confusion(pred,truth,shift);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][song]=sc
        tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,x in sc["by_group"].items():tot[f"{g}_tp"]+=x["tp"];tot[f"{g}_pred"]+=x["predicted"];tot[f"{g}_ref"]+=x["reference"]
    tp,n,mref=tot["tp"],tot["predicted"],tot["reference"]
    s={"tp":tp,"predicted":n,"reference":mref,"precision":round(tp/n,4) if n else 0,"recall":round(tp/mref,4) if mref else 0,"f1":round(2*tp/(n+mref),4) if n+mref else 0,
       "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"by_group":{}}
    parts=[]
    for g in GROUPS:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];f=2*a/(b+c) if b+c else 0
        sf=[]
        for song in SONGS:
            x=result["songs"][song]["by_group"].get(g,{});rr=x.get("reference",0)
            if rr:sf.append(2*x.get("tp",0)/(x.get("predicted",0)+rr) if x.get("predicted",0)+rr else 0)
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":round(a/b,4) if b else 0,"recall":round(a/c,4) if c else 0,"f1":round(f,4),"count_ratio":round(b/c,4) if c else None,
          "mean_song_f1":round(sum(sf)/len(sf),4) if sf else None,"worst_song_f1":round(min(sf),4) if sf else None}
        if g in ("kick","snare","hat","tom","crash","ride"):parts.append(f)
    ks=tot["kick_to_snare"]/max(1,tot["kick_ref"])
    s["selection_score"]=round(s["f1"]+.20*sum(parts)/len(parts)-.25*ks,6);result["summary"]=s
    result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def rank(x):return sorted(x.items(),key=lambda kv:(kv[1]["summary"]["selection_score"],kv[1]["summary"]["f1"]),reverse=True)

def main():
    bd,bn=base_dir();root=EXP/"generated-search-recall-repair";report={"schema":1,"base_winner":bn,"cycles":[]}

    res={}
    for name,sm in [("c61_snare_raw","raw"),("c61_snare_consensus","consensus"),("c61_snare_pattern","pattern")]:
        res[name]=evaluate(name,bd,sm,"base","keep",root/"cycle61");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":61,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,tm in [("c62_tom_raw","raw"),("c62_tom_consensus","consensus"),("c62_tom_fill","fill")]:
        res[name]=evaluate(name,bd,best["snare_mode"],tm,"keep",root/"cycle62");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0];best=res[win]
    report["cycles"].append({"cycle":62,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})

    res={}
    for name,pm in [("c63_pedal_keep","keep"),("c63_pedal_periodic","periodic"),("c63_pedal_off","off")]:
        res[name]=evaluate(name,bd,best["snare_mode"],best["tom_mode"],pm,root/"cycle63");print("SUMMARY",name,json.dumps(res[name]["summary"],ensure_ascii=False),flush=True)
    rr=rank(res);win=rr[0][0]
    report["cycles"].append({"cycle":63,"candidates":res,"ranking":[n for n,_ in rr],"winner":win,"carried_close":[n for n,r in rr if rr[0][1]["summary"]["selection_score"]-r["summary"]["selection_score"]<=.01]})
    report["final"]={"winner":win,"summary":res[win]["summary"],"snare_mode":res[win]["snare_mode"],"tom_mode":res[win]["tom_mode"],"pedal_mode":res[win]["pedal_mode"],"detailed":res[win]["detailed"]}
    (EXP/"results-iterative-recall-repair.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
