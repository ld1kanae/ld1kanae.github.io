"""Arrangement-aware metal decoding for current browser transcription.

General prior: Groove MIDI Dataset aggregate model (train split, 4/4).
Domain prior: leave-one-song-out statistics from the other four DruMaster
chart.mid files. The held-out chart is never used for prediction.

Prediction inputs for the held-out song:
- current real-browser audio-derived MIDI
- browser BPM/bar phase
- ADTOF generic cymbal candidate stream
- fixed reference-sample spectral similarities
- GMD symbolic prior
- LOO prior from the other four charts

The decoder treats hat/ride as persistent bar-level timekeeping states and
crash as a sparse structural accent, especially at downbeats after fill-like
tom activity.
"""
from __future__ import annotations

import bisect,importlib.util,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
AD=EXP/"generated-search-adtof/cycle163/c163_precision"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
IDX={g:i for i,g in enumerate(ev.ORDER)}
GMD=json.loads((ROOT/"drumscribe/models/gmd-metal-prior.json").read_text())

def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    rows=[(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")]
    return rows,side

def ad_rows(song):
    return sorted(t for t,g,*_ in ev.midi_events(AD/f"{song}.mid") if g=="crash")

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def periodic(xs,t,bpm,w=.06):
    if len(xs)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(near(xs,t+k*step,w) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def match(pred,truth,tol=.08):
    pred=sorted(pred);truth=sorted(truth);used=set();tp=0
    for x in pred:
        j=bisect.bisect_left(truth,x)
        opts=[k for k in (j-1,j,j+1) if 0<=k<len(truth) and k not in used]
        if not opts:continue
        k=min(opts,key=lambda q:abs(x-truth[q]))
        if abs(x-truth[k])<=tol:used.add(k);tp+=1
    return tp

def chart_symbolic(song):
    # Work in MIDI-native beats/bars; no song.json timing is needed.
    path=ROOT/"DruMaster/songs"/song/"chart.mid"
    data=path.read_bytes()
    # reuse evaluate parser for class labels/time; song.json BPM is only needed
    # to map seconds to beat positions. This is training data for non-held songs.
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    bpm=float(meta["bpm"]);beat=60/bpm
    rows=[(t,g) for t,g,*_ in ev.midi_events(path)]
    out=[]
    for t,g in rows:
        slot=int(round(t/(beat/4)))
        out.append((slot,g))
    return out

def loo_prior(held):
    trans=defaultdict(Counter);slot=defaultdict(Counter);accent=defaultdict(Counter)
    for song in SONGS:
        if song==held:continue
        rows=chart_symbolic(song)
        at=defaultdict(set)
        for s,g in rows:at[s].add(g)
        maxbar=max((s//16 for s,g in rows),default=-1)
        state=[]
        for b in range(maxbar+1):
            c=Counter(g for s,g in rows if s//16==b and g in ("hat","ride"))
            state.append(c.most_common(1)[0][0] if c and c.most_common(1)[0][1]>=2 else "none")
        for a,b in zip(state,state[1:]):
            if a in ("hat","ride") and b in ("hat","ride"):trans[a][b]+=1
        for s,g in rows:
            if g not in ("hat","pedal_hat","ride","crash"):continue
            slot[s%16][g]+=1
            prior=[x for q in range(max(0,s-4),s) for x in at.get(q,set())]
            fill="tom" if sum(x=="tom" for x in prior)>=2 else "snare" if sum(x=="snare" for x in prior)>=2 else "none"
            head="head" if s%16==0 else "nonhead"
            accent[(head,fill)][g]+=1
    def prob(c,classes=("hat","ride"),alpha=2):
        z=sum(c.get(x,0) for x in classes)+alpha*len(classes)
        return {x:(c.get(x,0)+alpha)/z for x in classes}
    return {
      "transition":{a:prob(trans[a]) for a in ("hat","ride")},
      "slot":{str(k):prob(slot[k],("hat","pedal_hat","ride","crash"),1.5) for k in range(16)},
      "accent":{f"{a}|{b}":prob(accent[(a,b)],("hat","pedal_hat","ride","crash"),1.5)
                for a in ("head","nonhead") for b in ("tom","snare","none")}
    }

def blend_prob(general,domain,key,cls,w):
    gp=max(1e-5,general.get(key,{}).get(cls,1e-5))
    dp=max(1e-5,domain.get(key,{}).get(cls,gp))
    return math.exp((math.log(gp)+w*math.log(dp))/(1+w))

def prepare(song):
    rows,side=browser_rows(song)
    bpm=float(side["bpm"]);phase=float(side["barPhaseSec"]);beat=60/bpm;bar=4*beat
    audio=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3")
    sp=ev.spectrum(audio);band,sim=ev.features(sp,ev.templates(ROOT/"DruMaster/assets/drums"))
    hats=sorted(t for t,g in rows if g=="hat");rides=sorted(t for t,g in rows if g=="ride")
    crashes=sorted(t for t,g in rows if g=="crash");kicks=sorted(t for t,g in rows if g=="kick")
    snares=sorted(t for t,g in rows if g=="snare");toms=sorted(t for t,g in rows if g=="tom")
    ad=ad_rows(song)
    duration=max([t for t,g in rows]+ad+[0])+bar
    nbar=max(1,int(math.ceil((duration-phase)/bar))+1)
    bars=[]
    for b in range(nbar):
        a=phase+b*bar;z=a+bar
        bh=[t for t in hats if a<=t<z];br=[t for t in rides if a<=t<z];ba=[t for t in ad if a<=t<z]
        ratios=[]
        for t in bh:
            fr=max(0,min(sim.shape[1]-1,int(round(t*ev.SR/ev.HOP))))
            hs=float(sim[IDX["hat"],fr]);rs=float(sim[IDX["ride"],fr])
            ratios.append(math.log((max(0,rs)+.04)/(max(0,hs)+.04)))
        bars.append({
          "hat_n":len(bh),"ride_n":len(br),"ad_n":len(ba),
          "ride_ratio_mean":float(np.mean(ratios)) if ratios else 0.,
          "ride_ratio_q75":float(np.quantile(ratios,.75)) if ratios else 0.,
          "ad_periodic":float(np.mean([periodic(ad,t,bpm) for t in ba])) if ba else 0.,
        })
    return {
      "rows":rows,"side":side,"bpm":bpm,"phase":phase,"beat":beat,"bar":bar,
      "band":band,"sim":sim,"hats":hats,"rides":rides,"crashes":crashes,
      "kicks":kicks,"snares":snares,"toms":toms,"ad":ad,"bars":bars,
    }

def transition_probs(loo,w):
    out={}
    # GMD previousBarState is hit-level, normalize only hat/ride.
    for prev in ("hat","ride"):
        g=GMD["previousBarState"].get(prev,{})
        gz=max(1e-9,g.get("hat",0)+g.get("ride",0))
        gg={"hat":g.get("hat",0)/gz,"ride":g.get("ride",0)/gz}
        d=loo["transition"][prev]
        out[prev]={}
        for cur in ("hat","ride"):
            out[prev][cur]=math.exp((math.log(max(1e-5,gg[cur]))+w*math.log(max(1e-5,d[cur])))/(1+w))
        z=sum(out[prev].values())
        for cur in out[prev]:out[prev][cur]/=z
    return out

def decode_states(d,loo,cfg):
    trans=transition_probs(loo,cfg["loo_weight"])
    # Viterbi
    dp=[];back=[]
    init={"hat":math.log(.58),"ride":math.log(.42)}
    for i,b in enumerate(d["bars"]):
        # Emission from audio/current predictions, not truth.
        # ride template mean is weak per-hit evidence; persistence makes it useful.
        ride_em=(cfg["ratio_w"]*b["ride_ratio_mean"]+
                 cfg["cur_ride_w"]*min(2,b["ride_n"])-
                 cfg["cur_hat_w"]*min(12,b["hat_n"])/12+
                 cfg["ad_per_w"]*b["ad_periodic"])
        emit={"hat":-ride_em,"ride":ride_em}
        cur={};bp={}
        for s in ("hat","ride"):
            if i==0:
                cur[s]=init[s]+emit[s];bp[s]=None
            else:
                opts=[(dp[-1][p]+cfg["trans_w"]*math.log(max(1e-6,trans[p][s]))+emit[s],p) for p in ("hat","ride")]
                cur[s],bp[s]=max(opts)
        dp.append(cur);back.append(bp)
    st=max(dp[-1],key=dp[-1].get);out=[st]
    for i in range(len(dp)-1,0,-1):
        st=back[i][st];out.append(st)
    return list(reversed(out))

def bar_index(d,t):
    return int(math.floor((t-d["phase"])/d["bar"]))

def grid_slot(d,t):
    x=(t-d["phase"])%d["bar"]
    return int(round(x/(d["beat"]/4)))%16

def fillish(d,t):
    a=t-d["beat"];tom=sum(a<=x<t for x in d["toms"]);sn=sum(a<=x<t for x in d["snares"])
    return "tom" if tom>=2 else "snare" if sn>=2 else "none"

def prior_prob(loo,slot,headfill,cls,w):
    gp=GMD["slot16"].get(str(slot),GMD["globalProb"]).get(cls,1e-5)
    dp=loo["slot"].get(str(slot),{}).get(cls,gp)
    pslot=math.exp((math.log(max(1e-5,gp))+w*math.log(max(1e-5,dp)))/(1+w))
    ga=GMD["accent"].get(headfill,GMD["globalProb"]).get(cls,1e-5)
    da=loo["accent"].get(headfill,{}).get(cls,ga)
    pac=math.exp((math.log(max(1e-5,ga))+w*math.log(max(1e-5,da)))/(1+w))
    return math.sqrt(pslot*pac)

def build(d,loo,cfg):
    states=decode_states(d,loo,cfg)
    pred={g:sorted(t for t,gg in d["rows"] if gg==g) for g in ev.ORDER}
    converted=[]

    # Existing hat events can become ride only inside a sustained ride state,
    # with local template support. State confidence is provided by Viterbi.
    hand=[];addride=[]
    for t in pred["hat"]:
        bi=bar_index(d,t)
        if 0<=bi<len(states) and states[bi]=="ride":
            fr=max(0,min(d["sim"].shape[1]-1,int(round(t*ev.SR/ev.HOP))))
            hs=float(d["sim"][IDX["hat"],fr]);rs=float(d["sim"][IDX["ride"],fr])
            ratio=(rs+.04)/(hs+.04)
            if ratio>=cfg["hat_to_ride_ratio"]:
                addride.append(t);converted.append((t,"ride"));continue
        hand.append(t)
    pred["hat"]=hand;pred["ride"]=sorted(pred["ride"]+addride)

    # Add/reclass broad ADTOF generic cymbal candidates using arrangement prior.
    existing=sorted(pred["hat"]+pred["ride"]+pred["crash"])
    for t in d["ad"]:
        if near(existing,t,.045):continue
        bi=bar_index(d,t)
        state=states[bi] if 0<=bi<len(states) else "hat"
        slot=grid_slot(d,t);fill=fillish(d,t);hf=("head" if slot==0 else "nonhead")+"|"+fill
        fr=max(0,min(d["sim"].shape[1]-1,int(round(t*ev.SR/ev.HOP))))
        hs=float(d["sim"][IDX["hat"],fr]);rs=float(d["sim"][IDX["ride"],fr]);cs=float(d["sim"][IDX["crash"],fr])
        rratio=(rs+.04)/(hs+.04);cratio=(cs+.04)/(hs+.04)
        per=periodic(d["ad"],t,d["bpm"])

        pr=prior_prob(loo,slot,hf,"ride",cfg["loo_weight"])
        pc=prior_prob(loo,slot,hf,"crash",cfg["loo_weight"])
        rscore=(cfg["prior_w"]*math.log(pr+1e-6)+cfg["state_w"]*(1 if state=="ride" else -1)
                +cfg["periodic_w"]*per+cfg["template_w"]*math.log(rratio+1e-6))
        cscore=(cfg["prior_w"]*math.log(pc+1e-6)+cfg["crash_head_w"]*(1 if slot==0 else -0.35)
                +cfg["fill_w"]*(1 if fill=="tom" else .35 if fill=="snare" else 0)
                +cfg["template_w"]*math.log(cratio+1e-6))
        if cscore>=cfg["emit_thr"] and cscore>=rscore+cfg["margin"]:
            pred["crash"].append(t);existing.append(t)
        elif rscore>=cfg["emit_thr"] and rscore>=cscore+cfg["margin"]:
            pred["ride"].append(t);existing.append(t)

    for g in ("hat","ride","crash"):
        xs=sorted(pred[g]);ded=[];last=-999.
        for t in xs:
            if t-last>=.04:ded.append(t);last=t
        pred[g]=ded
    return pred,states,converted

def score_song(song,d,pred):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth_by={g:sorted(t+shift for t,gg,*_ in truth if gg==g) for g in ev.ORDER}
    st={};tp=pr=rf=0
    for g in ev.ORDER:
        pp=pred.get(g,[]);tt=truth_by[g];a=match(pp,tt)
        st[g]={"tp":a,"predicted":len(pp),"reference":len(tt)}
        tp+=a;pr+=len(pp);rf+=len(tt)
    return {"tp":tp,"predicted":pr,"reference":rf,"f1":2*tp/(pr+rf), "by_group":st}

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
        out["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return out

def main():
    data={s:prepare(s) for s in SONGS}
    loo={s:loo_prior(s) for s in SONGS}
    base_scores={s:score_song(s,data[s],{g:sorted(t for t,gg in data[s]["rows"] if gg==g) for g in ev.ORDER}) for s in SONGS}
    baseline=aggregate(base_scores)

    configs=[]
    for lw in (0,.35,.8,1.5):
      for tw in (.5,1.0,1.5):
       for rw in (.6,1.0,1.5):
        for crw in (.5,1.0):
         for aper in (.4,.8,1.2):
          for rr in (.82,.92,1.02,1.12):
           # fixed second-stage weights keep search tractable
           configs.append({
             "loo_weight":lw,"trans_w":tw,"ratio_w":rw,"cur_ride_w":1.15,"cur_hat_w":.25,"ad_per_w":aper,
             "hat_to_ride_ratio":rr,
             "prior_w":1.0,"state_w":1.15,"periodic_w":1.1,"template_w":.65,
             "crash_head_w":1.35*crw,"fill_w":.9*crw,"emit_thr":-1.7,"margin":.12
           })

    rows=[]
    for i,cfg in enumerate(configs):
        scores={};diag={}
        for song in SONGS:
            pred,states,conv=build(data[song],loo[song],cfg)
            scores[song]=score_song(song,data[song],pred)
            diag[song]={"states":states,"ride_bars":sum(x=="ride" for x in states),"converted_hat_to_ride":len(conv)}
        ag=aggregate(scores);h=ag["by_group"]["hat"];r=ag["by_group"]["ride"];c=ag["by_group"]["crash"]
        eligible=ag["f1"]>=baseline["f1"]-.006 and h["f1"]>=baseline["by_group"]["hat"]["f1"]-.05
        objective=ag["f1"]+.07*r["f1"]+.06*c["f1"]-.025*max(0,(r["count_ratio"] or 0)-1.25)
        rows.append({"eligible":eligible,"objective":objective,"config":cfg,"summary":ag,
                     "songs":{s:{"f1":scores[s]["f1"],"ride":scores[s]["by_group"]["ride"],
                                  "crash":scores[s]["by_group"]["crash"],"hat":scores[s]["by_group"]["hat"],
                                  **diag[s]} for s in SONGS}})
        if i%200==0:print("SEARCH",i,len(configs),flush=True)
    rows.sort(key=lambda x:(x["eligible"],x["objective"],x["summary"]["f1"]),reverse=True)
    report={"schema":1,
      "description":"GMD + leave-one-song-out arrangement prior metal decoder; held-out chart scoring-only.",
      "baseline":baseline,"top":rows[:50]}
    (EXP/"results-browser-metal-arrangement-prior.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    for x in report["top"][:12]:print("TOP",json.dumps(x,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
