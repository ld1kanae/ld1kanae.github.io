"""Event-level metal sequence decoder with GMD arrangement prior.

Labels each merged browser/ADTOF metal candidate as:
  hat, pedal_hat, ride, crash, or none

General symbolic probabilities come from GMD train/4-4 aggregate statistics.
A small domain prior from the other four DruMaster chart.mid files is optionally
blended in leave-one-song-out mode. The held-out chart is scoring-only.

Compared with the previous bar-state experiment, this keeps mixed hat/ride
bars possible and uses event-to-event transition probabilities learned from
real MIDI instead of painting an entire bar with one state.
"""
from __future__ import annotations
import bisect,importlib.util,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
AD=EXP/"generated-search-adtof/cycle163/c163_precision"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
LABELS=("hat","pedal_hat","ride","crash","none")
METAL=("hat","pedal_hat","ride","crash")

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
IDX={g:i for i,g in enumerate(ev.ORDER)}
GMD=json.loads((ROOT/"drumscribe/models/gmd-metal-prior.json").read_text())

def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def ad_rows(song):
    return sorted(t for t,g,*_ in ev.midi_events(AD/f"{song}.mid") if g=="crash")

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def match(pred,truth,tol=.08):
    pred=sorted(pred);truth=sorted(truth);used=set();tp=0
    for x in pred:
        j=bisect.bisect_left(truth,x)
        opts=[k for k in (j-1,j,j+1) if 0<=k<len(truth) and k not in used]
        if not opts:continue
        k=min(opts,key=lambda q:abs(x-truth[q]))
        if abs(x-truth[k])<=tol:used.add(k);tp+=1
    return tp

def chart_rows(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    beat=60/float(meta["bpm"])
    return [(int(round(t/(beat/4))),g) for t,g,*_ in ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")]

def smooth(c,classes=METAL,alpha=1.5):
    z=sum(c.get(x,0) for x in classes)+alpha*len(classes)
    return {x:(c.get(x,0)+alpha)/z for x in classes}

def build_loo(held):
    slot=defaultdict(Counter);context=defaultdict(Counter);accent=defaultdict(Counter);trans=defaultdict(Counter)
    for song in SONGS:
        if song==held:continue
        rows=chart_rows(song);at=defaultdict(set)
        for s,g in rows:at[s].add(g)
        metal=sorted((s,g) for s,g in rows if g in METAL)
        prev=None
        for s,g in metal:
            pos=s%16;ctx="+".join(x for x in ("kick","snare","tom") if x in at[s]) or "none"
            slot[str(pos)][g]+=1;context[f"{pos}|{ctx}"][g]+=1
            prior=[x for q in range(max(0,s-4),s) for x in at.get(q,set())]
            fill="tom" if sum(x=="tom" for x in prior)>=2 else "snare" if sum(x=="snare" for x in prior)>=2 else "none"
            accent[f"{'head' if pos==0 else 'nonhead'}|{fill}"][g]+=1
            if prev is not None:
                ps,pg=prev;delta=min(16,max(0,s-ps));trans[f"{pg}|d{delta}"][g]+=1
            prev=(s,g)
    return {
      "slot":{k:smooth(v) for k,v in slot.items()},
      "context":{k:smooth(v) for k,v in context.items()},
      "accent":{k:smooth(v) for k,v in accent.items()},
      "transition":{k:smooth(v) for k,v in trans.items()},
    }

def blend_table(gtab,dtab,key,label,w,fallback):
    gp=max(1e-5,gtab.get(key,{}).get(label,fallback))
    dp=max(1e-5,dtab.get(key,{}).get(label,gp))
    return math.exp((math.log(gp)+w*math.log(dp))/(1+w))

def periodic(xs,t,bpm,w=.06):
    if len(xs)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(near(xs,t+k*step,w) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def prepare(song):
    rows,side=browser_rows(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"])
    beat=60/bpm;bar=4*beat
    audio=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3")
    sp=ev.spectrum(audio);band,sim=ev.features(sp,ev.templates(ROOT/"DruMaster/assets/drums"))
    ad=ad_rows(song)
    base_by={g:sorted(t for t,gg in rows if gg==g) for g in ev.ORDER}
    fixed=[(t,g) for t,g in rows if g not in METAL]
    kicks=base_by["kick"];snares=base_by["snare"];toms=base_by["tom"]

    # Merge all current metal predictions + generic ADTOF cymbal candidates.
    raw=[]
    for g in METAL:
        for t in base_by[g]:raw.append((t,g))
    for t in ad:raw.append((t,"ad_cymbal"))
    raw.sort()
    cand=[]
    for t,src in raw:
        if cand and t-cand[-1]["t"]<=.040:
            c=cand[-1];c["sources"].add(src)
            # weighted average time: current browser event wins over generic AD
            if src!="ad_cymbal":c["t"]=t
        else:cand.append({"t":t,"sources":{src}})

    metal_times=[c["t"] for c in cand]
    for c in cand:
        t=c["t"];fr=max(0,min(sim.shape[1]-1,int(round(t*ev.SR/ev.HOP))))
        x=(t-phase)%bar;slot=int(round(x/(beat/4)))%16
        ctx="+".join(name for name,xs in (("kick",kicks),("snare",snares),("tom",toms)) if near(xs,t,.055)) or "none"
        a=t-beat
        fill="tom" if sum(a<=x<t for x in toms)>=2 else "snare" if sum(a<=x<t for x in snares)>=2 else "none"
        c.update({
          "slot":slot,"ctx":ctx,"accent":f"{'head' if slot==0 else 'nonhead'}|{fill}",
          "frame":fr,
          "sim":{g:float(sim[IDX[g],fr]) for g in METAL},
          "periodic":periodic(metal_times,t,bpm),
        })
    return {"rows":rows,"fixed":fixed,"base_by":base_by,"bpm":bpm,"phase":phase,"beat":beat,"bar":bar,
            "band":band,"sim":sim,"ad":ad,"cand":cand}

def local_score(c,label,loo,cfg):
    if label=="none":
        s=cfg["none_bias"]
        if any(x in c["sources"] for x in METAL):s-=cfg["drop_penalty"]
        if "ad_cymbal" in c["sources"] and len(c["sources"])==1:s+=cfg["ad_none_bonus"]
        return s

    fallback=GMD["globalProb"].get(label,.05)
    ps=blend_table(GMD["slot16"],loo["slot"],str(c["slot"]),label,cfg["loo_weight"],fallback)
    pc=blend_table(GMD["context"],loo["context"],f"{c['slot']}|{c['ctx']}",label,cfg["loo_weight"],fallback)
    pa=blend_table(GMD["accent"],loo["accent"],c["accent"],label,cfg["loo_weight"],fallback)
    prior=(ps*pc*pa)**(1/3)
    s=cfg["prior_w"]*math.log(prior+1e-6)

    # Source likelihoods. Current browser class is useful but not absolute.
    if label in c["sources"]:s+=cfg["current_w"]
    if "ad_cymbal" in c["sources"]:
        if label in ("ride","crash"):s+=cfg["ad_metal_w"]
        else:s-=cfg["ad_hat_penalty"]

    # Fixed one-shot templates are weak evidence; sequence prior can accumulate.
    sims=c["sim"];mx=max(.02,max(sims.values()))
    rel=(max(.001,sims[label])+.03)/(mx+.03)
    s+=cfg["template_w"]*math.log(rel+1e-6)

    # Explicit structural cues, still prediction-only.
    if label=="ride":s+=cfg["ride_per_w"]*c["periodic"]
    if label=="crash":
        if c["slot"]==0:s+=cfg["crash_head_w"]
        if c["accent"].endswith("|tom"):s+=cfg["fill_w"]
        elif c["accent"].endswith("|snare"):s+=.35*cfg["fill_w"]
    if label=="pedal_hat":
        # GMD shows pedal strongly favors recurrent quarter/eighth positions.
        if c["slot"] in (0,4,8,12):s+=cfg["pedal_quarter_w"]
    return s

def trans_score(prev,cur,delta,loo,cfg):
    if prev=="none" or cur=="none":return 0.
    key=f"{prev}|d{min(16,max(0,delta))}"
    fallback=GMD["globalProb"].get(cur,.05)
    p=blend_table(GMD["transition"],loo["transition"],key,cur,cfg["loo_weight"],fallback)
    return cfg["trans_w"]*math.log(p+1e-6)

def decode(d,loo,cfg):
    cs=d["cand"]
    if not cs:return []
    dp=[];back=[]
    for i,c in enumerate(cs):
        cur={};bp={}
        for lab in LABELS:
            loc=local_score(c,lab,loo,cfg)
            if i==0:
                cur[lab]=loc;bp[lab]=None
            else:
                delta=int(round((c["t"]-cs[i-1]["t"])/(d["beat"]/4)))
                opts=[(dp[-1][p]+trans_score(p,lab,delta,loo,cfg)+loc,p) for p in LABELS]
                cur[lab],bp[lab]=max(opts)
        dp.append(cur);back.append(bp)
    lab=max(dp[-1],key=dp[-1].get);labs=[lab]
    for i in range(len(cs)-1,0,-1):
        lab=back[i][lab];labs.append(lab)
    labs=list(reversed(labs))
    return [(c["t"],lab,c) for c,lab in zip(cs,labs)]

def build(d,loo,cfg):
    dec=decode(d,loo,cfg)
    pred=defaultdict(list)
    for t,g in d["fixed"]:pred[g].append(t)
    for t,g,c in dec:
        if g!="none":pred[g].append(t)
    for g in ev.ORDER:
        xs=sorted(pred[g]);ded=[];last=-999.
        for t in xs:
            if t-last>=.04:ded.append(t);last=t
        pred[g]=ded
    return pred,dec

def score_song(song,pred):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth_by={g:sorted(t+shift for t,gg,*_ in truth if gg==g) for g in ev.ORDER}
    st={};tp=pr=rf=0
    for g in ev.ORDER:
        pp=pred.get(g,[]);tt=truth_by[g];a=match(pp,tt)
        st[g]={"tp":a,"predicted":len(pp),"reference":len(tt)}
        tp+=a;pr+=len(pp);rf+=len(tt)
    return {"tp":tp,"predicted":pr,"reference":rf,"f1":2*tp/(pr+rf),"by_group":st}

def aggregate(scores):
    tot=Counter()
    for sc in scores.values():
        tot.update(tp=sc["tp"],pred=sc["predicted"],ref=sc["reference"])
        for g,x in sc["by_group"].items():
            tot.update({f"{g}_tp":x["tp"],f"{g}_pred":x["predicted"],f"{g}_ref":x["reference"]})
    out={"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
         "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],
         "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        out["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,
          "recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return out

def main():
    data={s:prepare(s) for s in SONGS};loo={s:build_loo(s) for s in SONGS}
    base={}
    for s,d in data.items():
        pred={g:list(v) for g,v in d["base_by"].items()}
        base[s]=score_song(s,pred)
    baseline=aggregate(base)

    configs=[]
    for lw in (0,.35,.8,1.5):
     for cw in (.65,1.0,1.4):
      for aw in (.35,.70,1.1):
       for tw in (.25,.55,.9):
        for pw in (.45,.8,1.15):
         for tmp in (.25,.55):
          for none in (-.4,0,.4):
           configs.append({
             "loo_weight":lw,"current_w":cw,"ad_metal_w":aw,"ad_hat_penalty":.15,
             "trans_w":tw,"prior_w":pw,"template_w":tmp,
             "ride_per_w":.55,"crash_head_w":.75,"fill_w":.65,"pedal_quarter_w":.25,
             "none_bias":none,"drop_penalty":1.8,"ad_none_bonus":.45
           })

    results=[]
    for i,cfg in enumerate(configs):
        scores={};diag={}
        for song in SONGS:
            pred,dec=build(data[song],loo[song],cfg)
            scores[song]=score_song(song,pred)
            counts=Counter(g for _,g,_ in dec)
            diag[song]={"decoded":dict(counts),"candidates":len(dec)}
        ag=aggregate(scores)
        h=ag["by_group"]["hat"];p=ag["by_group"]["pedal_hat"];r=ag["by_group"]["ride"];c=ag["by_group"]["crash"]
        eligible=(ag["f1"]>=baseline["f1"]-.004 and
                  h["f1"]>=baseline["by_group"]["hat"]["f1"]-.05 and
                  ag["precision"]>=baseline["precision"]-.04)
        macro=.25*(h["f1"]+p["f1"]+r["f1"]+c["f1"])
        obj=ag["f1"]+.08*macro+.035*r["f1"]+.025*c["f1"]+.025*p["f1"]
        results.append({"eligible":eligible,"objective":obj,"config":cfg,"summary":ag,
          "songs":{s:{"f1":scores[s]["f1"],
                      "hat":scores[s]["by_group"]["hat"],"pedal_hat":scores[s]["by_group"]["pedal_hat"],
                      "ride":scores[s]["by_group"]["ride"],"crash":scores[s]["by_group"]["crash"],
                      **diag[s]} for s in SONGS}})
        if i%300==0:print("SEARCH",i,len(configs),flush=True)
    results.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)
    report={"schema":1,"description":"Event Viterbi metal decoder: GMD + LOO symbolic sequence prior; held-out chart scoring-only.",
            "baseline":baseline,"top":results[:60]}
    (EXP/"results-browser-metal-sequence-decoder.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    for x in report["top"][:15]:print("TOP",json.dumps(x,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
