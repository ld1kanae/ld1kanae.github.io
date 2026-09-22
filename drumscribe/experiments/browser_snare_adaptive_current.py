"""Re-test song-adaptive snare supplementation on current browser output.

Base is current real-Chromium output (including ADTOF, hat filter, GMD pedal).
Supplement sources are previously materialized AUDIO-ONLY candidate streams:
- high recall snare stream
- conservative/repetition-supported snare stream

Prediction-time adaptation uses only disagreement between current and high
candidate counts plus current kick/snare/bar structure. chart.mid is scoring-only.

If this improves the current baseline, the next step is to port the candidate
generator itself into browser JS rather than depend on precomputed song files.
"""
from __future__ import annotations
import bisect,importlib.util,json,math
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
HIGH=EXP/"generated-search-best-fusion/cycle80/c80_snare_pattern"
SAFE=EXP/"generated-search-snare-additive/cycle114/c114_repeat3"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def current(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def source(path,song,g):
    return sorted(t for t,gg,*_ in ev.midi_events(path/f"{song}.mid") if gg==g)

def slot(t,phase,bar):
    x=(t-phase)%bar
    return int(round(x/bar*16))%16

def repeat_support(xs,t,phase,bar):
    s=slot(t,phase,bar);b=math.floor((t-phase)/bar);bars=set()
    for x in xs:
        bx=math.floor((x-phase)/bar)
        if abs(bx-b)<=6 and slot(x,phase,bar)==s:bars.add(bx)
    return len(bars)

def enforce(events):
    out=[]
    for g in sorted(set(g for _,g in events)):
        mind=.038 if g=="snare" else .035
        last=-999.
        for t,gg in sorted((t,gg) for t,gg in events if gg==g):
            if t-last>=mind:out.append((t,gg));last=t
    return sorted(out)

def build(song,cfg):
    base,side=current(song)
    bs=sorted(t for t,g in base if g=="snare");ks=sorted(t for t,g in base if g=="kick")
    hi=source(HIGH,song,"snare");safe=source(SAFE,song,"snare")
    ratio=len(hi)/max(1,len(bs))
    kickratio=len(bs)/max(1,len(ks))
    adaptive=ratio>=cfg["disagree"] and kickratio<=cfg["snareKickMax"]
    add=[]
    if adaptive:
        bpm=float(side["bpm"]);beat=60/bpm;bar=4*beat;phase=float(side["barPhaseSec"])
        pool=sorted(set(bs+hi+safe))
        for t in hi:
            if near(bs,t,.040):continue
            consensus=near(safe,t,cfg["safeWindow"])
            rep=repeat_support(pool,t,phase,bar)
            bb=slot(t,phase,bar) in (4,12)
            collision=near(ks,t,cfg["kickWindow"])
            if cfg["mode"]=="consensus":
                keep=consensus and not collision
            elif cfg["mode"]=="repeat":
                keep=(consensus or rep>=cfg["repNeed"]) and (not collision or (consensus and rep>=cfg["repNeed"]+1))
            else:
                keep=(consensus and not collision) or (bb and rep>=cfg["repNeed"] and (not collision or rep>=cfg["repNeed"]+1))
            if keep:add.append((t,"snare"))
    return enforce(base+add),{
      "base":len(bs),"high":len(hi),"safe":len(safe),"disagreement":ratio,
      "snareKick":kickratio,"adaptive":adaptive,"added":len(add)
    }

def evaluate(cfg):
    scores={};diag={};tot=Counter()
    for song in SONGS:
        pred,dd=build(song,cfg);diag[song]=dd
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        sc=ev.score([(t,g,0,0) for t,g in pred],truth,shift);scores[song]=sc
        tot.update(tp=sc["tp"],pred=sc["predicted"],ref=sc["reference"])
        for g,x in sc["by_group"].items():tot.update({f"{g}_tp":x["tp"],f"{g}_pred":x["predicted"],f"{g}_ref":x["reference"]})
    s={"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
       "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],
       "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return s,scores,diag

def main():
    basecfg={"disagree":99,"snareKickMax":0,"safeWindow":.055,"kickWindow":.045,"mode":"consensus","repNeed":2}
    baseline,_,bd=evaluate(basecfg);rows=[]
    for disagree in (1.20,1.30,1.45,1.70,2.00):
      for sk in (.28,.32,.38,.45):
       for kw in (.025,.045,.065):
        for sw in (.040,.055,.070):
         for mode in ("consensus","repeat","backbeat"):
          for rep in (2,3,4):
           cfg={"disagree":disagree,"snareKickMax":sk,"safeWindow":sw,"kickWindow":kw,"mode":mode,"repNeed":rep}
           s,songs,diag=evaluate(cfg);sn=s["by_group"]["snare"]
           eligible=s["f1"]>=baseline["f1"]-.001 and sn["precision"]>=baseline["by_group"]["snare"]["precision"]-.06
           obj=s["f1"]+.08*sn["f1"]+.01*min(1,sn["precision"])
           rows.append({"eligible":eligible,"objective":obj,"config":cfg,"summary":s,"diag":diag,
                        "songs":{k:{"f1":v["f1"],"snare":v["by_group"]["snare"]} for k,v in songs.items()}})
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)
    report={"schema":1,"description":"Current-browser adaptive snare supplement; chart scoring-only.",
      "baseline":baseline,"baselineDiag":bd,"top":rows[:50]}
    (EXP/"results-browser-snare-adaptive-current.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps({"f1":baseline["f1"],"snare":baseline["by_group"]["snare"],"diag":bd},ensure_ascii=False),flush=True)
    for z in report["top"][:15]:
        print("TOP",json.dumps({"cfg":z["config"],"f1":z["summary"]["f1"],"snare":z["summary"]["by_group"]["snare"],"diag":z["diag"],"songs":z["songs"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
