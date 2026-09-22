"""Fast exact-equivalent low-threshold GMD pedal extension.

Same candidate thresholds, fixed score formula, policies and nested LOO as
browser_gmd_pedal_lowcand.py. Optimization only:
- peak sets are computed once per threshold;
- high-band envelope is computed once per song;
- decay features are cached once per unique candidate time.
"""
from __future__ import annotations
import bisect,importlib.util,json,math
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
spec=importlib.util.spec_from_file_location("slow",EXP/"browser_gmd_pedal_lowcand.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

THRS=(.04,.06,.08,.10,.14,.18)

def near(xs,t,w):
    i=bisect.bisect_left(xs,t-w)
    return i<len(xs) and xs[i]<=t+w

def envelope(sp):
    freqs=np.arange(sp.shape[0])*b.ev.SR/b.ev.FFT
    return sp[(freqs>=1800)&(freqs<=5400)].sum(axis=0)

def decay_at(high,t):
    fr=int(round(t*b.ev.SR/b.ev.HOP));n=len(high)
    def mean(a,c):
        aa=max(0,fr+a);bb=min(n,fr+c)
        return float(np.mean(high[aa:bb])) if bb>aa else 0.
    def mx(a,c):
        aa=max(0,fr+a);bb=min(n,fr+c)
        return float(np.max(high[aa:bb])) if bb>aa else 0.
    pre=mean(-12,-3);on=mx(-1,3);amp=max(on-pre,1e-7)
    return max(0,mean(11,21)-pre)/amp,max(0,mean(21,36)-pre)/amp

def make_cache(d):
    sets={thr:b.pick_hat(d["y"],thr) for thr in THRS}
    union=sorted(set(round(t,5) for xs in sets.values() for t in xs))
    high=envelope(d["sp"]);static={}
    kicks=d["by"]["kick"];snares=d["by"]["snare"];toms=d["by"]["tom"]
    for tr in union:
        t=float(tr);sl=b.slot16(t,d["bpm"],d["phase"]);ctx=[]
        if near(kicks,t,.045):ctx.append("kick")
        if near(snares,t,.045):ctx.append("snare")
        if near(toms,t,.045):ctx.append("tom")
        ck="+".join(ctx) if ctx else "none"
        prior=b.GMD["context"].get(f"{sl}|{ck}") or b.GMD["slot16"].get(str(sl)) or b.GMD["globalProb"]
        ph=max(1e-6,float(prior.get("hat",1e-6)));pp=max(1e-6,float(prior.get("pedal_hat",1e-6)))
        t2,t3=decay_at(high,t)
        static[tr]=(1.5*math.log(pp/ph)-.35*min(t2,3)-.35*min(t3,3),sl,ck,t2,t3)
    out={}
    for thr,xs0 in sets.items():
        xs=sorted(float(t) for t in xs0);rows=[]
        for t in xs:
            key=round(t,5);base,sl,ck,t2,t3=static[key]
            others=xs
            # Exclude self implicitly because targets are half-beat away.
            n8=near(others,t-d["beat"]/2,.055) or near(others,t+d["beat"]/2,.055)
            score=base-.25*(1 if n8 else 0)
            fr=max(0,min(d["y"].shape[1]-1,int(round(t*100))))
            rows.append({"t":t,"score":score,"activation":float(d["y"][0,fr,3]),
                         "slot":sl,"ctx":ck,"tail2":t2,"tail3":t3,"near8":bool(n8)})
        out[thr]=rows
    return out

def main():
    m=b.model();proc=b.create_adtof_processor();data={}
    for s in b.SONGS:
        print("INFER",s,flush=True);data[s]=b.prepare(s,b.infer(s,m,proc))
    cand={s:make_cache(data[s]) for s in b.SONGS}
    base={s:b.score(s,data[s]["rows"]) for s in b.SONGS};bag=b.aggregate(base)

    fixed=[]
    for cfg in [
      {"name":"h08_s08_both","hatThr":.08,"scoreThr":.8,"mode":"both","hatWindow":.045},
      {"name":"h10_s10_both","hatThr":.10,"scoreThr":1.0,"mode":"both","hatWindow":.045},
      {"name":"h14_s12_both","hatThr":.14,"scoreThr":1.2,"mode":"both","hatWindow":.045},
      {"name":"h10_s10_add","hatThr":.10,"scoreThr":1.0,"mode":"add","hatWindow":.045},
    ]:
        scores={};diag={}
        for s in b.SONGS:
            pred,dg=b.build(data[s],cfg,cand[s]);scores[s]=b.score(s,pred);diag[s]=dg
        a=b.aggregate(scores);fixed.append({"config":cfg,"objective":b.objective(a),"summary":a,"diag":diag})

    cfgs=[];i=0
    for ht in THRS:
      for st in (.4,.6,.8,1.0,1.2,1.5,1.8,2.2):
       for mode in ("add","reclass","both"):
        cfgs.append({"id":i,"hatThr":ht,"scoreThr":st,"mode":mode,"hatWindow":.045});i+=1
    rows=[];cache={}
    for cfg in cfgs:
        scores={};diag={}
        for s in b.SONGS:
            pred,dg=b.build(data[s],cfg,cand[s]);scores[s]=b.score(s,pred);diag[s]=dg
        a=b.aggregate(scores);cache[cfg["id"]]=scores;p=a["by_group"]["pedal_hat"]
        eligible=(a["f1"]>=bag["f1"]-.002 and a["precision"]>=bag["precision"]-.025 and p["precision"]>=.48)
        rows.append({"id":cfg["id"],"eligible":eligible,"objective":b.objective(a),"config":cfg,"summary":a,"diag":diag})
    rows.sort(key=lambda z:(z["eligible"],z["objective"],z["summary"]["f1"]),reverse=True)

    held={};loo={}
    for h in b.SONGS:
        tr=[s for s in b.SONGS if s!=h];btr=b.aggregate({s:base[s] for s in tr});rank=[]
        for z in rows:
            a=b.aggregate({s:cache[z["id"]][s] for s in tr});p=a["by_group"]["pedal_hat"]
            valid=(a["f1"]>=btr["f1"]-.002 and a["precision"]>=btr["precision"]-.025 and p["precision"]>=.48)
            rank.append((valid,b.objective(a),a["f1"],z["id"]))
        rank.sort(reverse=True);bid=rank[0][3];z=next(q for q in rows if q["id"]==bid)
        sc=cache[bid][h];held[h]=sc
        loo[h]={"selectedId":bid,"config":z["config"],"heldF1":sc["f1"],
                "pedal_hat":sc["by_group"]["pedal_hat"],"hat":sc["by_group"]["hat"],"diag":z["diag"][h]}
    la=b.aggregate(held)
    out={"schema":1,"description":"Cached exact-equivalent low-candidate GMD pedal extension; charts scoring-only.",
         "baseline":bag,"fixed":fixed,"top":rows[:50],
         "nestedLOO":{"aggregate":la,"objective":b.objective(la),"songs":loo},
         "candidateCounts":{s:{str(k):len(v) for k,v in cand[s].items()} for s in b.SONGS}}
    (EXP/"results-browser-gmd-pedal-lowcand-fast.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BASE",json.dumps(bag,ensure_ascii=False),flush=True)
    print("FIXED",json.dumps(fixed,ensure_ascii=False),flush=True)
    print("TOP",json.dumps(rows[:10],ensure_ascii=False),flush=True)
    print("LOO",json.dumps(out["nestedLOO"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
