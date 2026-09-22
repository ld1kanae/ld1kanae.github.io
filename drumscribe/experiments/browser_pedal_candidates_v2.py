"""Browser pedal-hi-hat candidate search v2.

Prediction uses only:
- current real-browser MIDI (audio-derived)
- audio spectral bands/template similarities
- estimated BPM from browser sidecar

Reference chart.mid is scoring-only.

Unlike v1, this generates new pedal candidates from high-band onsets rather
than only converting existing hand-hat notes.
"""
from __future__ import annotations
import importlib.util,json,math,bisect
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
HIDX=ev.ORDER.index("hat");PIDX=ev.ORDER.index("pedal_hat")

def near(xs,t,w):
    if not xs:return False
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def browser_rows(song):
    side=json.loads((BASE/f"{song}.json").read_text())
    off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")]

def peaks(signal,thr,distance=.04,prom=.035):
    d=max(1,int(distance*ev.SR/ev.HOP))
    pp,_=find_peaks(signal,distance=d,prominence=prom)
    return [int(p) for p in pp if signal[p]>=thr]

def periodic(times,t,bpm,w=.055):
    if len(times)<3:return 0.
    best=0.
    for step in (30/bpm,60/bpm,120/bpm):
        n=sum(near(times,t+k*step,w) for k in (-2,-1,1,2))
        best=max(best,n/4)
    return best

def slot_support(times,t,bpm):
    beat=60/bpm
    # repeated same half-beat/beat phase in a +/-4-beat neighborhood
    vals=[]
    for div in (1,2,4):
        step=beat/div
        phase=(t%step)
        n=0
        for x in times:
            if abs(x-t)>4*beat or abs(x-t)<.035:continue
            d=abs(((x-phase+step/2)%step)-step/2)
            if d<=.045:n+=1
        vals.append(min(1,n/4))
    return max(vals)

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
    side=json.loads((BASE/f"{song}.json").read_text())
    bpm=float(side["bpm"]);events=browser_rows(song)
    audio=ev.audio(ROOT/"DruMaster/songs"/song/"drums.mp3")
    sp=ev.spectrum(audio);band,sim=ev.features(sp,tmpl)
    hats=sorted(t for t,g in events if g=="hat")
    occupied=sorted(t for t,g in events if g in ("kick","snare","tom","crash","ride"))
    # loose high-band pool, independent of truth.
    fs=peaks(band[3],.06,.035,.025)
    times=[f*ev.HOP/ev.SR for f in fs]
    rows=[]
    for fr,t in zip(fs,times):
        hs=float(sim[HIDX,fr]);ps=float(sim[PIDX,fr])
        b0,b1,b2,b3=[float(band[i,fr]) for i in range(4)]
        rows.append({
          "t":t,"frame":fr,"high":b3,
          "mid":b2,"body":b0+b1,
          "high_mid":b3/(b2+.04),
          "high_body":b3/(b0+b1+.05),
          "pedal_margin":ps-hs,
          "pedal_ratio":ps/(abs(hs)+1e-4),
          "near_hat":near(hats,t,.035),
          "near_body":near(occupied,t,.035),
        })
    cand_times=[r["t"] for r in rows]
    for r in rows:
        r["periodic"]=periodic(cand_times,r["t"],bpm)
        r["slot"]=slot_support(cand_times,r["t"],bpm)

    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth_by={g:sorted(t+shift for t,gg,*_ in truth if gg==g) for g in ev.ORDER}
    fixed_tp=fixed_pred=fixed_ref=0
    for g in ev.ORDER:
        if g in ("hat","pedal_hat"):continue
        pp=sorted(t for t,gg in events if gg==g)
        tt=truth_by[g]
        fixed_tp+=match(pp,tt);fixed_pred+=len(pp);fixed_ref+=len(tt)
    return dict(song=song,bpm=bpm,events=events,hats=hats,rows=rows,truth=truth_by,
                fixed_tp=fixed_tp,fixed_pred=fixed_pred,fixed_ref=fixed_ref)

def select(d,cfg):
    chosen=[]
    for r in d["rows"]:
        if r["high"]<cfg["high"]:continue
        if r["high_mid"]<cfg["high_mid"]:continue
        if r["high_body"]<cfg["high_body"]:continue
        if r["periodic"]<cfg["periodic"]:continue
        if r["slot"]<cfg["slot"]:continue
        if cfg["mode"]=="new" and r["near_hat"]:continue
        if cfg["mode"]=="convert" and not r["near_hat"]:continue
        if cfg["body_veto"] and r["near_body"]:continue
        # Template gate is deliberately weak; v1 showed templates overlap.
        if r["pedal_margin"]<cfg["margin"]:continue
        chosen.append(r["t"])
    # de-duplicate
    chosen.sort();out=[];last=-999.
    for t in chosen:
        if t-last>=.04:out.append(t);last=t
    return out

def evaluate(data,cfg):
    tot=Counter();songs={}
    for song,d in data.items():
        ped=select(d,cfg)
        if cfg["mode"]=="convert":
            hand=[t for t in d["hats"] if not near(ped,t,.035)]
        else:
            hand=list(d["hats"])
            # avoid exact duplicates with hand hats
            ped=[t for t in ped if not near(hand,t,.030)]
        htp=match(hand,d["truth"]["hat"]);ptp=match(ped,d["truth"]["pedal_hat"])
        tp=d["fixed_tp"]+htp+ptp;pred=d["fixed_pred"]+len(hand)+len(ped)
        ref=d["fixed_ref"]+len(d["truth"]["hat"])+len(d["truth"]["pedal_hat"])
        songs[song]={
          "pedal_count":len(ped),"pedal_tp":ptp,"hand_count":len(hand),"hand_tp":htp,
          "overall_f1":2*tp/(pred+ref) if pred+ref else 0
        }
        tot.update(tp=tp,pred=pred,ref=ref,hat_tp=htp,hat_pred=len(hand),hat_ref=len(d["truth"]["hat"]),
                   ped_tp=ptp,ped_pred=len(ped),ped_ref=len(d["truth"]["pedal_hat"]))
    def stat(a,b,c):
        return {"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,
                "recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0}
    return {
      "tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
      "precision":tot["tp"]/tot["pred"] if tot["pred"] else 0,
      "recall":tot["tp"]/tot["ref"] if tot["ref"] else 0,
      "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]) if tot["pred"]+tot["ref"] else 0,
      "hat":stat(tot["hat_tp"],tot["hat_pred"],tot["hat_ref"]),
      "pedal_hat":stat(tot["ped_tp"],tot["ped_pred"],tot["ped_ref"]),
      "songs":songs,
    }

def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")
    data={s:prepare(s,tmpl) for s in SONGS}
    base=evaluate(data,{"mode":"new","high":99,"high_mid":99,"high_body":99,
      "periodic":1,"slot":1,"body_veto":True,"margin":99})
    results=[]
    for mode in ("new","convert"):
      for high in (.08,.12,.18,.25):
       for hm in (.65,.9,1.2,1.6):
        for hb in (.55,.8,1.1,1.5):
         for per in (.25,.50,.75,1.0):
          for slot in (0,.25,.50,.75):
           for veto in (False,True):
            for margin in (-.08,-.04,0,.04):
             cfg={"mode":mode,"high":high,"high_mid":hm,"high_body":hb,
                  "periodic":per,"slot":slot,"body_veto":veto,"margin":margin}
             sc=evaluate(data,cfg)
             hat_drop=base["hat"]["f1"]-sc["hat"]["f1"]
             # overall cannot drop >.3pt; favor pedal F1 and cross-song usefulness
             song_f=[2*v["pedal_tp"]/(v["pedal_count"]+len(data[s]["truth"]["pedal_hat"]))
                     if v["pedal_count"]+len(data[s]["truth"]["pedal_hat"]) else 0
                     for s,v in sc["songs"].items()]
             useful=sum(v["pedal_tp"]>0 for v in sc["songs"].values())
             eligible=sc["f1"]>=base["f1"]-.003 and hat_drop<=.025
             objective=sc["f1"]+.11*sc["pedal_hat"]["f1"]+.025*np.mean(song_f)+.003*useful
             results.append({"eligible":eligible,"objective":float(objective),"config":cfg,"summary":sc})
    results.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)
    report={
      "schema":2,"description":"Prediction-only high-band pedal candidate search; chart scoring-only.",
      "baseline":base,"top":results[:80],
      "candidate_diagnostics":{s:{
        "count":len(d["rows"]),
        "high_q":[float(np.quantile([r["high"] for r in d["rows"]],q)) for q in (.25,.5,.75,.9)] if d["rows"] else [],
        "periodic_q":[float(np.quantile([r["periodic"] for r in d["rows"]],q)) for q in (.25,.5,.75,.9)] if d["rows"] else [],
      } for s,d in data.items()}
    }
    (EXP/"results-browser-pedal-candidates-v2.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(base,ensure_ascii=False),flush=True)
    for x in report["top"][:15]:print("TOP",json.dumps(x,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
