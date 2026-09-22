"""Style/fill-conditioned GMD pedal-hi-hat decoder benchmark.

Prediction uses only current audio-derived browser events, audio features,
browser BPM/bar phase, and fixed GMD aggregate priors. DruMaster chart.mid is
scoring-only.

Compared with browser_gmd_pedal.py, the symbolic prior can be:
- all: original all-style context/slot prior
- rock: rock-family slot prior + all-style context
- rock_fill: rock-family beat/fill slot prior selected by audio-derived
  preceding tom/snare density + all-style context

Reports global search and nested leave-one-song-out hyperparameter selection.
"""
from __future__ import annotations
import bisect,importlib.util,json,math
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GMD=json.loads((ROOT/"drumscribe/models/gmd-metal-prior.json").read_text())
STYLE=json.loads((ROOT/"drumscribe/models/gmd-metal-style-prior.json").read_text())

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
    beat=60/bpm;bar=4*beat;x=(t-phase)%bar
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

def prior_for(mode,slot,ctx,fillish):
    context=GMD["context"].get(f"{slot}|{ctx}") or GMD["slot16"].get(str(slot)) or GMD["globalProb"]
    if mode=="all":return context
    scope="rock_family"
    if mode=="rock_fill":
        scope=f"rock_family|{'fill' if fillish else 'beat'}"
        if scope not in STYLE["groups"]:scope="rock_family"
    s=(STYLE["groups"].get(scope,{}).get("slot16",{}).get(str(slot))
       or STYLE["groups"].get("rock_family",{}).get("slot16",{}).get(str(slot))
       or context)
    # geometric blend preserves body-context information from GMD full prior.
    out={}
    for g in ("hat","pedal_hat","ride","crash"):
        out[g]=math.sqrt(max(1e-8,float(context.get(g,1e-8)))*max(1e-8,float(s.get(g,1e-8))))
    z=sum(out.values())
    return {g:v/z for g,v in out.items()}

def prepare(song,tmpl):
    rows,side=browser_rows(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"]);beat=60/bpm
    audio=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3");sp=ev.spectrum(audio);band,sim=ev.features(sp,tmpl)
    hats=sorted(t for t,g in rows if g=="hat")
    kicks=sorted(t for t,g in rows if g=="kick");snares=sorted(t for t,g in rows if g=="snare");toms=sorted(t for t,g in rows if g=="tom")
    feats=[]
    for t in hats:
        fr=max(0,min(sim.shape[1]-1,int(round(t*ev.SR/ev.HOP))));sl=slot16(t,bpm,phase)
        ctx=[]
        if near(kicks,t,.045):ctx.append("kick")
        if near(snares,t,.045):ctx.append("snare")
        if near(toms,t,.045):ctx.append("tom")
        ctxkey="+".join(ctx) if ctx else "none"
        # audio-derived fill proxy: >=2 toms or >=2 snares in prior beat.
        a=t-beat
        fillish=(sum(a<=x<t for x in toms)>=2 or sum(a<=x<t for x in snares)>=2)
        env=dec.env_features(sp,t);hs=float(sim[H,fr]);ps=float(sim[P,fr])
        others=[x for x in hats if abs(x-t)>.035]
        near8=near(others,t-beat/2,.055) or near(others,t+beat/2,.055)
        near16=near(others,t-beat/4,.05) or near(others,t+beat/4,.05)
        feats.append({"t":t,"slot":sl,"ctx":ctxkey,"fillish":fillish,
          "pedal_ratio":ps/(abs(hs)+1e-4),
          "tail1":env["tail1"],"tail2":env["tail2"],"tail3":env["tail3"],
          "near8":int(near8),"near16":int(near16)})
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth_by={g:sorted(t+shift for t,gg,*_ in truth if gg==g) for g in ev.ORDER}
    fixed={g:sorted(t for t,gg in rows if gg==g) for g in ev.ORDER if g not in ("hat","pedal_hat")}
    return {"hats":hats,"features":feats,"truth":truth_by,"fixed":fixed}

def fscore(f,cfg):
    pr=prior_for(cfg["mode"],f["slot"],f["ctx"],f["fillish"])
    ph=max(1e-6,pr.get("hat",1e-6));pp=max(1e-6,pr.get("pedal_hat",1e-6))
    short=cfg["t1"]*min(f["tail1"],1)-cfg["t2"]*min(f["tail2"],3)-cfg["t3"]*min(f["tail3"],3)
    templ=cfg["templ"]*math.log(max(.1,min(3.,f["pedal_ratio"])))
    neigh=cfg["n8"]*f["near8"]+cfg["n16"]*f["near16"]
    return cfg["prior"]*math.log(pp/ph)+short+templ+neigh

def evaluate(data,cfg):
    tot=Counter();scores={}
    for song,d in data.items():
        pedal=sorted(f["t"] for f in d["features"] if fscore(f,cfg)>=cfg["thr"])
        hand=[t for t in d["hats"] if not near(pedal,t,.025)]
        htp=match(hand,d["truth"]["hat"]);ptp=match(pedal,d["truth"]["pedal_hat"])
        ftp=fp=fr=0
        for g,pp in d["fixed"].items():
            tt=d["truth"][g];a=match(pp,tt);ftp+=a;fp+=len(pp);fr+=len(tt)
        tp=ftp+htp+ptp;pred=fp+len(hand)+len(pedal);ref=fr+len(d["truth"]["hat"])+len(d["truth"]["pedal_hat"])
        scores[song]={"tp":tp,"pred":pred,"ref":ref,"f1":2*tp/(pred+ref),
          "hat":(htp,len(hand),len(d["truth"]["hat"])),"ped":(ptp,len(pedal),len(d["truth"]["pedal_hat"]))}
        tot.update(tp=tp,pred=pred,ref=ref,htp=htp,hp=len(hand),hr=len(d["truth"]["hat"]),ptp=ptp,pp=len(pedal),pr=len(d["truth"]["pedal_hat"]))
    def st(a,b,c):return {"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0}
    return {"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
      "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],"f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),
      "hat":st(tot["htp"],tot["hp"],tot["hr"]),"pedal_hat":st(tot["ptp"],tot["pp"],tot["pr"]),"songs":scores}

def objective(s):return s["f1"]+.10*s["pedal_hat"]["f1"]+.02*s["hat"]["f1"]

def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums");data={s:prepare(s,tmpl) for s in SONGS}
    base={"mode":"all","prior":0,"t1":0,"t2":0,"t3":0,"templ":0,"n8":0,"n16":0,"thr":999}
    baseline=evaluate(data,base)
    configs=[];i=0
    for mode in ("all","rock","rock_fill"):
      for pw in (1.0,1.5,2.0):
       for t2 in (.15,.35,.55):
        for t3 in (.25,.35,.55,.75):
         for templ in (0,.25):
          for n8 in (-.35,-.25,-.10,0):
           for th in (.15,.3,.4,.5,.65):
            configs.append({"id":i,"mode":mode,"prior":pw,"t1":0,"t2":t2,"t3":t3,"templ":templ,"n8":n8,"n16":0,"thr":th});i+=1
    rows=[];cache={}
    for cfg in configs:
        s=evaluate(data,cfg);cache[cfg["id"]]=s
        eligible=s["f1"]>=baseline["f1"]-.002 and s["hat"]["f1"]>=baseline["hat"]["f1"]-.035
        rows.append({"id":cfg["id"],"eligible":eligible,"objective":objective(s),"config":cfg,"summary":s})
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)
    # nested LOO config selection
    held={};sel={}
    for h in SONGS:
        tr=[s for s in SONGS if s!=h];rank=[]
        for row in rows:
            rs=cache[row["id"]]["songs"];tp=sum(rs[s]["tp"] for s in tr);pr=sum(rs[s]["pred"] for s in tr);rf=sum(rs[s]["ref"] for s in tr)
            # use aggregate F1 as selection objective; pedal-weighted global ranking already reported separately
            val=2*tp/(pr+rf)
            rank.append((val,row["objective"],row["id"]))
        rank.sort(reverse=True);bid=rank[0][2];held[h]=cache[bid]["songs"][h];sel[h]=next(r for r in rows if r["id"]==bid)["config"]
    tp=sum(x["tp"] for x in held.values());pr=sum(x["pred"] for x in held.values());rf=sum(x["ref"] for x in held.values())
    out={"schema":1,"description":"Style/fill conditioned GMD-only pedal decoder; charts scoring-only.",
      "baseline":baseline,"top":rows[:50],"nestedLOO":{"f1":2*tp/(pr+rf),"precision":tp/pr,"recall":tp/rf,"selection":sel,"songs":held}}
    (EXP/"results-browser-gmd-pedal-style.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    print("TOP",json.dumps(rows[:10],ensure_ascii=False),flush=True)
    print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
