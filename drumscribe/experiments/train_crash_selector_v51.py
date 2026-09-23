from __future__ import annotations
import importlib.util,json,math
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
D=EXP/"generated-crash-diagnostics-v51"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
spec=importlib.util.spec_from_file_location("ev_crash51",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def truth_times(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    return sorted(t+shift for t,g,n in truth if n in {49,52,55,57})

def assign_labels(times,refs,w=.080):
    used=set();labels=[0]*len(times)
    order=sorted(range(len(times)),key=lambda i:times[i])
    for i in order:
        cand=[(abs(times[i]-u),j) for j,u in enumerate(refs) if j not in used and abs(times[i]-u)<=w]
        if cand:
            _,j=min(cand);used.add(j);labels[i]=1
    return labels

def feat(c):
    cs=float(c.get("crashSimilarity",0));hs=float(c.get("hatSimilarity",0));rs=float(c.get("rideSimilarity",0))
    bm=float(c.get("bandMid",0));bb=float(c.get("bandBody",0));bh=float(c.get("bandHigh",0));bl=float(c.get("bandLow",0))
    eps=1e-4; den=bm+bb+bh+eps
    return {
      "confidence":float(c.get("baseConfidence",0)),
      "crashSim":cs,"hatSim":hs,"rideSim":rs,
      "marginHat":cs-hs,"marginMax":cs-max(hs,rs),
      "ratioHat":cs/(abs(hs)+eps),"ratioMax":cs/(max(abs(hs),abs(rs))+eps),
      "bodyHigh":(bm+bb)/(abs(bh)+.05),
      "highShare":bh/den,"bodyShare":(bm+bb)/den,"lowShare":bl/(bl+den+eps),
      "periodic":float(c.get("periodicSupport",0)),
      "headDistance":float(c.get("headDistance",9)),
      "hatSupport":1.0 if c.get("hatSupport") else 0.0
    }

data={}
for song in SONGS:
    side=json.loads((D/f"{song}.json").read_text())
    cand=side.get("adtofInfo",{}).get("cymbalPolicy",{}).get("crashCandidates",[])
    refs=truth_times(song);times=[float(c["time"]) for c in cand];labels=assign_labels(times,refs)
    rows=[]
    for c,y in zip(cand,labels):
        f=feat(c);eligible=float(c.get("headDistance",9))<=.30 and not bool(c.get("crashSupport"))
        rows.append({"time":float(c["time"]),"y":int(y),"eligible":eligible,"f":f})
    data[song]={"rows":rows,"refs":len(refs)}

def score_song(song,keep):
    rows=data[song]["rows"];tp=sum(r["y"] for r,k in zip(rows,keep) if k);p=sum(1 for k in keep if k);ref=data[song]["refs"]
    return {"tp":tp,"predicted":p,"reference":ref,"precision":tp/p if p else 0.,"recall":tp/ref if ref else 0.,"f1":2*tp/(p+ref) if p+ref else 0.,"falsePositive":p-tp}
def aggregate(scores):
    tp=sum(x["tp"] for x in scores);p=sum(x["predicted"] for x in scores);r=sum(x["reference"] for x in scores)
    return {"tp":tp,"predicted":p,"reference":r,"precision":tp/p if p else 0.,"recall":tp/r if r else 0.,"f1":2*tp/(p+r) if p+r else 0.,"falsePositive":p-tp}

baseline=aggregate([score_song(s,[True]*len(data[s]["rows"])) for s in SONGS])

def threshold_candidates(values):
    u=sorted(set(float(x) for x in values))
    if not u:return [-1e9]
    mids=[(a+b)/2 for a,b in zip(u,u[1:])]
    return [u[0]-1e-9]+u+mids+[u[-1]+1e-9]

def choose_simple(train_songs,key,direction="ge"):
    vals=[r["f"][key] for s in train_songs for r in data[s]["rows"] if r["eligible"]]
    best=None
    for th in threshold_candidates(vals):
        scores=[]
        for s in train_songs:
            keep=[(not r["eligible"]) or ((r["f"][key]>=th) if direction=="ge" else (r["f"][key]<=th)) for r in data[s]["rows"]]
            scores.append(score_song(s,keep))
        a=aggregate(scores);rank=(a["f1"],a["precision"],a["recall"])
        if best is None or rank>best[0]:best=(rank,th)
    return best[1]

FEATURES=["confidence","crashSim","hatSim","rideSim","marginHat","marginMax","ratioHat","ratioMax","bodyHigh","highShare","bodyShare","lowShare","periodic","headDistance","hatSupport"]
def fit_logistic(train_songs):
    rows=[r for s in train_songs for r in data[s]["rows"] if r["eligible"]]
    X=np.array([[r["f"][k] for k in FEATURES] for r in rows],dtype=float);y=np.array([r["y"] for r in rows],dtype=int)
    scaler=StandardScaler().fit(X);Z=scaler.transform(X)
    model=LogisticRegression(C=.5,class_weight="balanced",max_iter=2000,random_state=0).fit(Z,y)
    probs=model.predict_proba(Z)[:,1]
    best=None
    for th in threshold_candidates(probs):
        scores=[];off=0
        for s in train_songs:
            keep=[]
            for r in data[s]["rows"]:
                if not r["eligible"]:keep.append(True)
                else:
                    z=scaler.transform(np.array([[r["f"][k] for k in FEATURES]],float))
                    keep.append(float(model.predict_proba(z)[0,1])>=th)
            scores.append(score_song(s,keep))
        a=aggregate(scores);rank=(a["f1"],a["precision"],a["recall"])
        if best is None or rank>best[0]:best=(rank,th)
    return scaler,model,best[1]

methods={"template_margin":[],"body_high":[],"logistic":[]}
for held in SONGS:
    train=[s for s in SONGS if s!=held]
    th=choose_simple(train,"marginMax","ge")
    keep=[(not r["eligible"]) or r["f"]["marginMax"]>=th for r in data[held]["rows"]]
    methods["template_margin"].append({"held":held,"threshold":th,"score":score_song(held,keep)})

    th2=choose_simple(train,"bodyHigh","ge")
    keep2=[(not r["eligible"]) or r["f"]["bodyHigh"]>=th2 for r in data[held]["rows"]]
    methods["body_high"].append({"held":held,"threshold":th2,"score":score_song(held,keep2)})

    scaler,model,th3=fit_logistic(train)
    keep3=[]
    for r in data[held]["rows"]:
        if not r["eligible"]:keep3.append(True)
        else:
            z=scaler.transform(np.array([[r["f"][k] for k in FEATURES]],float))
            keep3.append(float(model.predict_proba(z)[0,1])>=th3)
    methods["logistic"].append({"held":held,"threshold":th3,"score":score_song(held,keep3)})

for name,folds in methods.items():
    methods[name]={"folds":folds,"aggregate":aggregate([x["score"] for x in folds])}

# Train/export all-song logistic for a possible lightweight runtime candidate.
scaler,model,th=fit_logistic(SONGS)
export={"schema":1,"name":"crash-selector-v1-logistic","features":FEATURES,
        "mean":scaler.mean_.tolist(),"scale":scaler.scale_.tolist(),
        "coef":model.coef_[0].tolist(),"intercept":float(model.intercept_[0]),
        "threshold":float(th),"eligibility":{"headDistanceMax":.30,"rawCrashSupportAlwaysKeep":True}}
(EXP/"crash-selector-v51-logistic.json").write_text(json.dumps(export,ensure_ascii=False,indent=2)+"\n")

out={"schema":1,"date":"2026-09-23","experiment":"crash acoustic selector v51",
     "referencePolicy":"chart.mid used only after fresh browser prediction; LOO held song never used for threshold/model fitting.",
     "baseline":baseline,"methods":methods,
     "best":max(methods,key=lambda k:(methods[k]["aggregate"]["f1"],methods[k]["aggregate"]["precision"])),
     "candidateCounts":{s:{"predicted":len(data[s]["rows"]),"eligible":sum(r["eligible"] for r in data[s]["rows"]),"reference":data[s]["refs"]} for s in SONGS},
     "logisticExport":"crash-selector-v51-logistic.json"}
(EXP/"results-crash-v51.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False,indent=2))
