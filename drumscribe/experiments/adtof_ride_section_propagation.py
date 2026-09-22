"""Ride-section propagation from low-threshold ADTOF metal candidates.

Prediction uses audio/browser output only:
1. low-threshold ADTOF hat + cymbal peaks;
2. estimated BPM/bar phase;
3. current browser crash/ride/hat/pedal output.

Ride is modeled as a multi-bar timekeeping state:
- seed bars need repeated/non-downbeat generic-cymbal activity or current ride;
- seed bars are grouped into persistent runs, optionally bridging one-bar gaps;
- within a run, only 16th-note positions repeated across multiple bars become
  ride pattern slots;
- low-threshold hat candidates at those repeated slots provide ride onsets;
- current pedal-hat/crash are preserved.

Reference chart.mid is scoring-only. Hyperparameters are evaluated both
globally and with nested leave-one-song-out selection.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import torch
from adtof_pytorch import calculate_n_bins,create_frame_rnn_model,get_default_weights_path,load_pytorch_weights,PeakPicker,LABELS_5
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
HAT_T=.04;CYM_T=.04

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def model():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    return load_pytorch_weights(m,get_default_weights_path(),strict=False).eval()

def infer(song,m,p):
    a=p.load_audio(str(ROOT/"DruMaster/songs"/song/"drums.mp3"))
    st=p.compute_stft(a);x=p.apply_filterbank(st).T.astype(np.float32)[...,None]
    with torch.no_grad():return m(torch.from_numpy(x[None,...])).cpu().numpy()

def pick(y):
    pp=PeakPicker(thresholds=[.22,.24,.32,HAT_T,CYM_T],fps=100)
    d=pp.pick(y,labels=LABELS_5,label_offset=0)[0]
    return sorted(map(float,d.get(42,[]))),sorted(map(float,d.get(49,[])))

def browser(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")],side

def truth_score(song,pred):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    return ev.score([(t,g,0,0) for t,g in pred],ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid"),shift)

def bslot(t,phase,beat):
    bar=4*beat;x=(t-phase)/bar;b=math.floor(x);within=(t-(phase+b*bar))/beat
    s=int(round(within*4))%16
    return b,s,within

def nearest(xs,t,w):
    if not xs:return None
    a=np.asarray(xs);i=int(np.argmin(np.abs(a-t)))
    return xs[i] if abs(xs[i]-t)<=w else None

def prepare(song,y):
    rows,side=browser(song);bpm=float(side["bpm"]);phase=float(side["barPhaseSec"]);beat=60/bpm;bar=4*beat
    hh,cy=pick(y)
    # candidate maps
    hmap=defaultdict(list);cmap=defaultdict(list)
    for t in hh:
        b,s,_=bslot(t,phase,beat);fr=max(0,min(y.shape[1]-1,int(round(t*100))))
        hmap[(b,s)].append((t,float(y[0,fr,3]),float(y[0,fr,4])))
    for t in cy:
        b,s,_=bslot(t,phase,beat);fr=max(0,min(y.shape[1]-1,int(round(t*100))))
        cmap[(b,s)].append((t,float(y[0,fr,4]),float(y[0,fr,3])))
    current=defaultdict(list)
    for t,g in rows:
        if g in ("hat","pedal_hat","ride","crash"):
            b,s,_=bslot(t,phase,beat);current[(b,s)].append((t,g))
    bars=sorted(set(b for b,s in hmap)|set(b for b,s in cmap)|set(b for b,s in current))
    feats={}
    for b in bars:
        hs=[s for (bb,s),z in hmap.items() if bb==b and z]
        cs=[s for (bb,s),z in cmap.items() if bb==b and z]
        nonhead=[s for s in cs if s not in (0,)]
        curRide=sum(g=="ride" for (bb,s),items in current.items() if bb==b for t,g in items)
        curCrash=sum(g=="crash" for (bb,s),items in current.items() if bb==b for t,g in items)
        feats[b]={
          "hatSlots":len(set(hs)),"cymSlots":len(set(cs)),
          "nonheadCym":len(set(nonhead)),
          "cymHatRatio":len(set(cs))/max(1,len(set(hs))),
          "currentRide":curRide,"currentCrash":curCrash,
        }
    return {"rows":rows,"side":side,"bpm":bpm,"phase":phase,"beat":beat,"bar":bar,
            "hh":hh,"cy":cy,"hmap":hmap,"cmap":cmap,"current":current,"bars":bars,"feats":feats}

def bridge_seed(seed,gap):
    if not seed:return set()
    x=set(seed)
    if gap>=1:
        lo,hi=min(x),max(x)
        for b in range(lo+1,hi):
            if b not in x and b-1 in x and b+1 in x:x.add(b)
    return x

def runs(seed,minrun):
    if not seed:return []
    xs=sorted(seed);out=[];cur=[xs[0]]
    for b in xs[1:]:
        if b==cur[-1]+1:cur.append(b)
        else:
            if len(cur)>=minrun:out.append(cur)
            cur=[b]
    if len(cur)>=minrun:out.append(cur)
    return out

def build(d,cfg):
    seed=set()
    for b,f in d["feats"].items():
        strong=(f["hatSlots"]>=cfg["minHatSlots"] and
                f["nonheadCym"]>=cfg["minNonhead"] and
                f["cymHatRatio"]>=cfg["minRatio"])
        if strong or f["currentRide"]>0:seed.add(b)
    rruns=runs(bridge_seed(seed,cfg["bridge"]),cfg["minRun"])
    ride_bars={b for r in rruns for b in r}
    ride_events=[];pattern_diag=[]
    for run in rruns:
        slot_count=Counter()
        for b in run:
            for s in range(16):
                if d["hmap"].get((b,s)):slot_count[s]+=1
        keep_slots={s for s,n in slot_count.items()
                    if n/len(run)>=cfg["slotFrac"] and n>=cfg["slotMinBars"]}
        # Require a timekeeping pattern, not a single accent slot.
        if len(keep_slots)<cfg["minPatternSlots"]:continue
        pattern_diag.append({"bars":run,"slots":sorted(keep_slots)})
        for b in run:
            for s in keep_slots:
                cand=d["hmap"].get((b,s),[])
                if not cand:continue
                # strongest hat activation at repeated rhythmic slot
                t,ha,ca=max(cand,key=lambda z:z[1])
                # do not convert/add on top of a current crash or pedal.
                cur=d["current"].get((b,s),[])
                if any(g in ("crash","pedal_hat") for _,g in cur):continue
                # Optional local cymbal evidence gate. 0 allows propagation
                # once section state is established.
                if ca<cfg["minCymAct"] and not any(g=="ride" for _,g in cur):
                    continue
                ride_events.append(t)

    pred=[];removed=0
    for t,g in d["rows"]:
        if g=="hat" and nearest(ride_events,t,cfg["replaceWindow"]) is not None:
            removed+=1;continue
        if g=="ride" and nearest(ride_events,t,.055) is not None:
            # existing ride replaced by reconstructed event below
            continue
        pred.append((t,g))
    for t in sorted(ride_events):
        if not any(g=="crash" and abs(x-t)<=.05 for x,g in pred):
            pred.append((t,"ride"))
    # class-wise de-dup
    out=[]
    for g in ev.ORDER:
        xs=sorted(t for t,gg in pred if gg==g);last=-999
        mind=.045 if g in ("ride","crash") else .035
        for t in xs:
            if t-last>=mind:out.append((t,g));last=t
    return sorted(out),{"seedBars":len(seed),"rideBars":len(ride_bars),"runs":pattern_diag,
                        "rideEvents":len(ride_events),"removedHat":removed}

def aggregate(scores):
    tot=Counter()
    for sc in scores.values():
        tot.update(tp=sc["tp"],pred=sc["predicted"],ref=sc["reference"])
        for g,z in sc["by_group"].items():
            tot.update({f"{g}_tp":z["tp"],f"{g}_pred":z["predicted"],f"{g}_ref":z["reference"]})
    out={"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
         "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],
         "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        out["by_group"][g]={"tp":a,"predicted":b,"reference":c,
          "precision":a/b if b else 0,"recall":a/c if c else 0,
          "f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return out

def objective(s):
    r=s["by_group"]["ride"];h=s["by_group"]["hat"];c=s["by_group"]["crash"]
    return s["f1"]+.10*r["f1"]+.02*h["f1"]+.015*c["f1"]-.02*max(0,(r["count_ratio"] or 0)-1.1)

def main():
    m=model();p=create_adtof_processor();data={}
    for song in SONGS:
        print("INFER",song,flush=True);data[song]=prepare(song,infer(song,m,p))
        print("BARFEAT",song,json.dumps(data[song]["feats"]),flush=True)
    base_scores={s:truth_score(s,data[s]["rows"]) for s in SONGS};baseline=aggregate(base_scores)
    configs=[];i=0
    for nh in (3,4,5):
     for nc in (1,2,3):
      for ratio in (.08,.15,.25,.35):
       for mr in (2,3,4):
        for sf in (.30,.45,.60,.75):
         for slots in (2,3,4):
          for mc in (0,.03,.06):
           configs.append({"id":i,"minHatSlots":nh,"minNonhead":nc,"minRatio":ratio,
             "bridge":1,"minRun":mr,"slotFrac":sf,"slotMinBars":2,"minPatternSlots":slots,
             "minCymAct":mc,"replaceWindow":.07});i+=1
    rows=[];cache={}
    for j,cfg in enumerate(configs):
        scores={};diag={}
        for s in SONGS:
            pred,dg=build(data[s],cfg);sc=truth_score(s,pred);scores[s]=sc;diag[s]=dg
        ag=aggregate(scores);cache[cfg["id"]]=scores
        eligible=ag["precision"]>=baseline["precision"]-.035 and ag["f1"]>=baseline["f1"]-.004
        rows.append({"id":cfg["id"],"eligible":eligible,"objective":objective(ag),"config":cfg,
                     "summary":ag,"diag":diag,
                     "songs":{s:{"f1":scores[s]["f1"],"hat":scores[s]["by_group"]["hat"],"ride":scores[s]["by_group"]["ride"],"crash":scores[s]["by_group"]["crash"]} for s in SONGS}})
        if j%500==0:print("CFG",j,len(configs),ag["f1"],flush=True)
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)

    held={};loo={}
    for h in SONGS:
        tr=[s for s in SONGS if s!=h];btr=aggregate({s:base_scores[s] for s in tr});rank=[]
        for z in rows:
            ag=aggregate({s:cache[z["id"]][s] for s in tr})
            valid=ag["precision"]>=btr["precision"]-.035 and ag["f1"]>=btr["f1"]-.004
            rank.append((valid,objective(ag),ag["f1"],z["id"]))
        rank.sort(reverse=True);bid=rank[0][3];z=next(x for x in rows if x["id"]==bid)
        sc=cache[bid][h];held[h]=sc
        loo[h]={"selectedId":bid,"config":z["config"],"heldF1":sc["f1"],
                "hat":sc["by_group"]["hat"],"ride":sc["by_group"]["ride"],"crash":sc["by_group"]["crash"],
                "diag":z["diag"][h]}
    lag=aggregate(held)
    out={"schema":1,"description":"Audio-only ride section propagation from low-threshold ADTOF; charts scoring-only.",
         "baseline":baseline,"top":rows[:60],"nestedLOO":{"aggregate":lag,"objective":objective(lag),"songs":loo}}
    (EXP/"results-adtof-ride-section-propagation.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(baseline,ensure_ascii=False),flush=True)
    print("TOP",json.dumps(rows[:10],ensure_ascii=False),flush=True)
    print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
