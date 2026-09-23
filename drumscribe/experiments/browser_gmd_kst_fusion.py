"""Fuse current browser ADTOF output with GMD structure + Magenta E-GMD predictions.

Three hypotheses are evaluated:
A) snare rescue from E-GMD, constrained by GMD kick/snare co-occurrence and repetition.
B) tom veto when current tom is unsupported by E-GMD and GMD says kick+tom is unlikely.
C) hybrid A+B.

DruMaster chart.mid is scoring-only. Prediction-time features come only from current
browser output, its audio-derived tempo/bar phase, the external E-GMD model output,
and a GMD train-split aggregate prior.
"""
from __future__ import annotations
import bisect,importlib.util,json,math
from collections import Counter
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
BASE=EXP/"generated-v2-browser"; EGMD=EXP/"generated-magenta-egmd"
PRIOR_PATH=ROOT/"drumscribe/models/gmd-kst-prior.json"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)
PRIOR=json.loads(PRIOR_PATH.read_text())

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def current(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    rows=[(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")]
    return rows,side

def egmd(song):
    p=EGMD/f"{song}.wav.midi"
    return [(t,g) for t,g,*_ in ev.midi_events(p)]

def slot16(t,bpm,phase):
    beat=60/bpm; bar=4*beat
    x=(t-phase)%bar
    return int(round(x/(beat/4)))%16

def bar_index(t,bpm,phase):
    bar=4*60/bpm
    return math.floor((t-phase)/bar)

def rep_support(xs,t,bpm,phase,window_bars=8):
    s=slot16(t,bpm,phase); b=bar_index(t,bpm,phase); seen=set()
    for x in xs:
        if abs(x-t)<=.035: continue
        bx=bar_index(x,bpm,phase)
        if abs(bx-b)<=window_bars and slot16(x,bpm,phase)==s:
            seen.add(bx)
    return len(seen)

def prior(group,slot,given=None,kind="all"):
    tab=PRIOR["groups"].get(kind) or PRIOR["groups"]["all"]
    if given:
        return float(tab["conditional"][given][str(slot)][group])
    return float(tab["slot16"][str(slot)][group])

def enforce(rows):
    out=[]
    for g in sorted(set(g for _,g in rows)):
        mind=.035 if g in ("kick","snare") else .045 if g=="tom" else .025
        last=-999.
        for t,gg in sorted((t,gg) for t,gg in rows if gg==g):
            if t-last>=mind:
                out.append((t,gg));last=t
    return sorted(out)

def build(song,cfg):
    base,side=current(song); alt=egmd(song)
    bpm=float(side["bpm"]); phase=float(side["barPhaseSec"])
    by={g:sorted(t for t,gg in base if gg==g) for g in ev.ORDER}
    altby={g:sorted(t for t,gg in alt if gg==g) for g in ev.ORDER}
    rows=list(base); added=[]; removed=[]

    if cfg["mode"] in ("snare","hybrid"):
        for t in altby["snare"]:
            if near(by["snare"],t,cfg["same_window"]): continue
            knear=near(by["kick"],t,cfg["kick_window"])
            if cfg["require_kick"] and not knear: continue
            sl=slot16(t,bpm,phase)
            ps=prior("snare",sl,"kick" if knear else None,cfg["prior_kind"])
            rep=rep_support(altby["snare"],t,bpm,phase)
            if ps<cfg["snare_prior_min"] or rep<cfg["snare_rep_min"]: continue
            rows.append((t,"snare")); added.append((t,"snare",ps,rep))

    if cfg["mode"] in ("tom","hybrid"):
        keep=[]
        for t,g in rows:
            if g!="tom":
                keep.append((t,g)); continue
            k=near(by["kick"],t,cfg["tom_kick_window"])
            if not k:
                keep.append((t,g)); continue
            alt_support=near(altby["tom"],t,cfg["tom_support_window"])
            sl=slot16(t,bpm,phase)
            pt=prior("tom",sl,"kick",cfg["prior_kind"])
            run=any(abs(x-t)>=.045 and abs(x-t)<=cfg["tom_run_window"] for x in by["tom"])
            veto=(not alt_support) and (not run) and pt<cfg["tom_prior_max"]
            if veto: removed.append((t,"tom",pt))
            else: keep.append((t,g))
        rows=keep

    return enforce(rows),{"added":added,"removed":removed}

def score_cfg(cfg):
    tot=Counter(); songs={};diag={}
    for song in SONGS:
        pred,dd=build(song,cfg);diag[song]=dd
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
        sc=ev.score([(t,g,0,0) for t,g in pred],truth,shift)
        songs[song]=sc
        tot.update(tp=sc["tp"],pred=sc["predicted"],ref=sc["reference"])
        for g,x in sc["by_group"].items():
            tot.update({f"{g}_tp":x["tp"],f"{g}_pred":x["predicted"],f"{g}_ref":x["reference"]})
    summary={"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
      "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],
      "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        summary["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return summary,songs,diag

def objective(s,base):
    k=s["by_group"]["kick"]; sn=s["by_group"]["snare"]; tom=s["by_group"]["tom"]
    # Structural priority: protect kick, then reward snare/tom.
    penalty=max(0,base["by_group"]["kick"]["f1"]-k["f1"])*3
    return .20*s["f1"]+.45*sn["f1"]+.35*tom["f1"]-penalty

def main():
    basecfg={"mode":"none","prior_kind":"all","same_window":.06,"kick_window":.05,
      "require_kick":True,"snare_prior_min":9,"snare_rep_min":99,
      "tom_kick_window":.03,"tom_support_window":.08,"tom_prior_max":-1,"tom_run_window":.24}
    baseline,_,_=score_cfg(basecfg)
    rows=[]

    # A: snare rescue.
    for kind in ("all","rock_family"):
      for pw in (.04,.08,.12,.18,.25,.35):
       for rep in (1,2,3,4):
        for kw in (.035,.05,.065):
         cfg={**basecfg,"mode":"snare","prior_kind":kind,"snare_prior_min":pw,"snare_rep_min":rep,"kick_window":kw}
         s,ss,d=score_cfg(cfg)
         eligible=s["by_group"]["kick"]["f1"]>=baseline["by_group"]["kick"]["f1"]-.0001 and s["by_group"]["snare"]["precision"]>=.88
         rows.append({"family":"A_snare_rescue","eligible":eligible,"objective":objective(s,baseline),"config":cfg,"summary":s,"songs":ss,"diag":d})

    # B: conservative tom veto.
    for kind in ("all","rock_family"):
      for pt in (.01,.02,.03,.05,.08,.12,.18):
       for sw in (.05,.08,.11):
        cfg={**basecfg,"mode":"tom","prior_kind":kind,"tom_prior_max":pt,"tom_support_window":sw}
        s,ss,d=score_cfg(cfg)
        eligible=s["by_group"]["kick"]["f1"]>=baseline["by_group"]["kick"]["f1"]-.0001 and s["by_group"]["tom"]["recall"]>=baseline["by_group"]["tom"]["recall"]-.03
        rows.append({"family":"B_tom_veto","eligible":eligible,"objective":objective(s,baseline),"config":cfg,"summary":s,"songs":ss,"diag":d})

    # C: combine top parameter grid directly (not cherry-picked from truth per song).
    for kind in ("all","rock_family"):
      for pw in (.08,.12,.18,.25):
       for rep in (1,2,3):
        for pt in (.02,.03,.05,.08):
         cfg={**basecfg,"mode":"hybrid","prior_kind":kind,"snare_prior_min":pw,"snare_rep_min":rep,
              "kick_window":.05,"tom_prior_max":pt,"tom_support_window":.08}
         s,ss,d=score_cfg(cfg)
         eligible=(s["by_group"]["kick"]["f1"]>=baseline["by_group"]["kick"]["f1"]-.0001
             and s["by_group"]["snare"]["precision"]>=.88
             and s["by_group"]["tom"]["recall"]>=baseline["by_group"]["tom"]["recall"]-.03)
         rows.append({"family":"C_hybrid","eligible":eligible,"objective":objective(s,baseline),"config":cfg,"summary":s,"songs":ss,"diag":d})

    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)
    best_by={}
    for x in rows:
        if x["family"] not in best_by: best_by[x["family"]]=x
    report={"schema":1,
      "description":"GMD KST symbolic prior + E-GMD second-model fusion; DruMaster charts scoring-only.",
      "baseline":baseline,
      "best_by_family":best_by,
      "top":rows[:40]}
    (EXP/"results-browser-gmd-kst-fusion.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    for k,v in best_by.items():
        print(k,json.dumps({"eligible":v["eligible"],"objective":v["objective"],"config":v["config"],
          "summary":v["summary"],"diag":v["diag"]},ensure_ascii=False),flush=True)

if __name__=="__main__": main()
