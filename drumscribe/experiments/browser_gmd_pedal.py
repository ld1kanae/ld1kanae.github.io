"""GMD-only pedal-hi-hat decoder for current browser hats.

Prediction uses:
- current audio-derived browser hats/kick/snare/tom
- browser BPM/bar phase
- fixed GMD train-split symbolic prior
- audio temporal decay and fixed reference pedal/hat template similarity

DruMaster chart.mid is scoring-only.
"""
from __future__ import annotations
import importlib.util,json,bisect,math
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GMD=json.loads((ROOT/"drumscribe/models/gmd-metal-prior.json").read_text())

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py")
dec=loadmod("dec",EXP/"browser_cymbal_decay_search.py")
H=ev.ORDER.index("hat");P=ev.ORDER.index("pedal_hat")

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def slot16(t,bpm,phase):
    beat=60/bpm;bar=4*beat
    x=(t-phase)%bar
    return int(round(x/(beat/4)))%16

def match(pred,truth,tol=.08):
    pred=sorted(pred);truth=sorted(truth);used=set();tp=0
    for x in pred:
        j=bisect.bisect_left(truth,x)
        opts=[k for k in (j-1,j,j+1) if 0<=k<len(truth) and k not in used]
        if not opts:continue
        k=min(opts,key=lambda q:abs(x-truth[q]))
        if abs(x-truth[k])<=tol:used.add(k);tp+=1
    return tp

def prepare(song,tmpl):
    rows,side=browser_rows(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"]);beat=60/bpm
    audio=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3");sp=ev.spectrum(audio);band,sim=ev.features(sp,tmpl)
    hats=sorted(t for t,g in rows if g=="hat")
    kicks=sorted(t for t,g in rows if g=="kick")
    snares=sorted(t for t,g in rows if g=="snare")
    toms=sorted(t for t,g in rows if g=="tom")
    feats=[]
    for t in hats:
        fr=max(0,min(sim.shape[1]-1,int(round(t*ev.SR/ev.HOP))))
        sl=slot16(t,bpm,phase)
        ctx=[]
        if near(kicks,t,.045):ctx.append("kick")
        if near(snares,t,.045):ctx.append("snare")
        if near(toms,t,.045):ctx.append("tom")
        ctxkey="+".join(ctx) if ctx else "none"
        prior=GMD["context"].get(f"{sl}|{ctxkey}") or GMD["slot16"].get(str(sl)) or GMD["globalProb"]
        phat=max(1e-6,prior.get("hat",1e-6));pped=max(1e-6,prior.get("pedal_hat",1e-6))
        d=dec.env_features(sp,t)
        hs=float(sim[H,fr]);ps=float(sim[P,fr])
        # neighboring predicted hand-hat pattern, independent of truth.
        near8=near([x for x in hats if abs(x-t)>.035],t-beat/2,.055) or near([x for x in hats if abs(x-t)>.035],t+beat/2,.055)
        near16=near([x for x in hats if abs(x-t)>.035],t-beat/4,.05) or near([x for x in hats if abs(x-t)>.035],t+beat/4,.05)
        feats.append({
          "t":t,"slot":sl,"ctx":ctxkey,
          "prior_logodds":math.log(pped/phat),
          "pedal_ratio":ps/(abs(hs)+1e-4),"pedal_margin":ps-hs,
          "tail1":d["tail1"],"tail2":d["tail2"],"tail3":d["tail3"],"upper_tail":d["upper_tail"],
          "near8":int(near8),"near16":int(near16)
        })

    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth_by={g:sorted(t+shift for t,gg,*_ in truth if gg==g) for g in ev.ORDER}
    fixed={g:sorted(t for t,gg in rows if gg==g) for g in ev.ORDER if g not in ("hat","pedal_hat")}
    return {"rows":rows,"hats":hats,"features":feats,"truth":truth_by,"fixed":fixed}

def score_feature(f,cfg):
    # log-space prior plus bounded audio/rhythm evidence.
    tail3=min(f["tail3"],3.0);tail2=min(f["tail2"],3.0);tail1=min(f["tail1"],2.0)
    short_score=cfg["t1_w"]*min(tail1,1.0)-cfg["t2_w"]*tail2-cfg["t3_w"]*tail3
    templ=cfg["templ_w"]*math.log(max(.1,min(3.0,f["pedal_ratio"])))
    neigh=cfg["near8_w"]*f["near8"]+cfg["near16_w"]*f["near16"]
    return cfg["prior_w"]*f["prior_logodds"]+short_score+templ+neigh

def evaluate(data,cfg):
    tot=Counter();songs={}
    for song,d in data.items():
        pedal=sorted(f["t"] for f in d["features"] if score_feature(f,cfg)>=cfg["threshold"])
        hand=[t for t in d["hats"] if not near(pedal,t,.025)]
        htp=match(hand,d["truth"]["hat"]);ptp=match(pedal,d["truth"]["pedal_hat"])
        fixedtp=fixedpred=fixedref=0
        for g,pp in d["fixed"].items():
            tt=d["truth"][g];a=match(pp,tt);fixedtp+=a;fixedpred+=len(pp);fixedref+=len(tt)
        tp=fixedtp+htp+ptp;pred=fixedpred+len(hand)+len(pedal);ref=fixedref+len(d["truth"]["hat"])+len(d["truth"]["pedal_hat"])
        songs[song]={"f1":2*tp/(pred+ref),"pedal_count":len(pedal),"pedal_tp":ptp,"hat_count":len(hand),"hat_tp":htp}
        tot.update(tp=tp,pred=pred,ref=ref,hat_tp=htp,hat_pred=len(hand),hat_ref=len(d["truth"]["hat"]),
                   ped_tp=ptp,ped_pred=len(pedal),ped_ref=len(d["truth"]["pedal_hat"]))
    def st(a,b,c):
        return {"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0}
    return {
      "tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
      "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],"f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),
      "hat":st(tot["hat_tp"],tot["hat_pred"],tot["hat_ref"]),
      "pedal_hat":st(tot["ped_tp"],tot["ped_pred"],tot["ped_ref"]),"songs":songs
    }

def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    data={s:prepare(s,tmpl) for s in SONGS}
    basecfg={"prior_w":0,"t1_w":0,"t2_w":0,"t3_w":0,"templ_w":0,"near8_w":0,"near16_w":0,"threshold":999}
    baseline=evaluate(data,basecfg)
    rows=[]
    for pw in (.5,1.0,1.5,2.0):
      for t1 in (0,.25,.5):
       for t2 in (0,.15,.35,.65):
        for t3 in (.15,.35,.65,1.0):
         for tw in (0,.25,.5):
          for n8 in (-.25,0,.25):
           for n16 in (-.20,0,.20):
            for th in (-1.2,-.8,-.4,0,.4,.8):
             cfg={"prior_w":pw,"t1_w":t1,"t2_w":t2,"t3_w":t3,"templ_w":tw,"near8_w":n8,"near16_w":n16,"threshold":th}
             sc=evaluate(data,cfg)
             hatdrop=baseline["hat"]["f1"]-sc["hat"]["f1"]
             useful=sum(v["pedal_tp"]>0 for v in sc["songs"].values())
             eligible=sc["f1"]>=baseline["f1"]-.004 and hatdrop<=.045
             obj=sc["f1"]+.09*sc["pedal_hat"]["f1"]+.0025*useful-.025*max(0,hatdrop)
             rows.append({"eligible":eligible,"objective":obj,"config":cfg,"summary":sc})
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)
    report={"schema":1,"description":"GMD-only pedal decoder; DruMaster charts scoring-only.","baseline":baseline,"top":rows[:60],
      "feature_diagnostics":{s:{
        "n":len(d["features"]),
        "prior_logodds_q":[float(np.quantile([f["prior_logodds"] for f in d["features"]],q)) for q in (.1,.25,.5,.75,.9)] if d["features"] else [],
        "tail3_q":[float(np.quantile([min(f["tail3"],3) for f in d["features"]],q)) for q in (.1,.25,.5,.75,.9)] if d["features"] else []
      } for s,d in data.items()}}
    (EXP/"results-browser-gmd-pedal.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    for x in report["top"][:15]:print("TOP",json.dumps(x,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
