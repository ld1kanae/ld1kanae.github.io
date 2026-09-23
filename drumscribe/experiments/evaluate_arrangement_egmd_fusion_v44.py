from __future__ import annotations
import json, math
from collections import Counter
from pathlib import Path

import mido
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(".")
IN=ROOT/"drumscribe/experiments/results-arrangement-kst-candidates-v44.json"
PRIOR=ROOT/"drumscribe/models/gmd-kst/slot-prior-v1.json"
OUT=ROOT/"drumscribe/experiments/results-arrangement-egmd-fusion-v44.json"
MD=ROOT/"drumscribe/experiments/ARRANGEMENT_EGMD_FUSION_V44.md"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=("kick","snare","tom")
NOTE_TO_GROUP={}
for n in (35,36): NOTE_TO_GROUP[n]="kick"
for n in (37,38,39,40): NOTE_TO_GROUP[n]="snare"
for n in (41,43,45,47,48,50): NOTE_TO_GROUP[n]="tom"

FEATURES=[
  "confidence","score","broad_confidence",
  "egmd_probability","egmd_margin","egmd_accepted",
  "family_quality","support_rate","support_count","eligible_count",
  "gmd_lift","slot_sin","slot_cos","occurrence","repeat_similarity",
  "in_repeated_family","bar_index_clip","section_bars","residual_abs",
]

def parse_midi(path,shift):
    mid=mido.MidiFile(path);tempo=500000;sec=0.0;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=="set_tempo": tempo=msg.tempo
        elif msg.type=="note_on" and msg.velocity>0:
            g=NOTE_TO_GROUP.get(msg.note)
            if g: out.append({"time":sec+shift,"group":g})
    return out

def nearest(events,t,group,tol):
    return any(e["group"]==group and abs(float(e["time"])-t)<=tol for e in events)

def score_group(pred,truth,group,tol=.08):
    p=sorted(float(e["time"]) for e in pred if e["group"]==group)
    r=sorted(float(e["time"]) for e in truth if e["group"]==group)
    used=set();tp=0
    for t in p:
        opts=[(abs(t-x),i) for i,x in enumerate(r) if i not in used and abs(t-x)<=tol]
        if opts:
            _,i=min(opts);used.add(i);tp+=1
    pr=tp/len(p) if p else 0.0;rc=tp/len(r) if r else 0.0
    return {"tp":tp,"pred":len(p),"ref":len(r),"precision":pr,"recall":rc,
            "f1":2*tp/(len(p)+len(r)) if p or r else 0.0}

def score(pred,truth):
    by={g:score_group(pred,truth,g) for g in GROUPS}
    tp=sum(x["tp"] for x in by.values());p=sum(x["pred"] for x in by.values());r=sum(x["ref"] for x in by.values())
    return {"tp":tp,"pred":p,"ref":r,"precision":tp/p if p else 0.0,
            "recall":tp/r if r else 0.0,"f1":2*tp/(p+r) if p+r else 0.0,"by_group":by}

def merge_scores(rows):
    by={}
    for g in GROUPS:
        tp=sum(x["by_group"][g]["tp"] for x in rows)
        p=sum(x["by_group"][g]["pred"] for x in rows)
        r=sum(x["by_group"][g]["ref"] for x in rows)
        by[g]={"tp":tp,"pred":p,"ref":r,"precision":tp/p if p else 0.0,
               "recall":tp/r if r else 0.0,"f1":2*tp/(p+r) if p+r else 0.0}
    tp=sum(x["tp"] for x in by.values());p=sum(x["pred"] for x in by.values());r=sum(x["ref"] for x in by.values())
    return {"tp":tp,"pred":p,"ref":r,"precision":tp/p if p else 0.0,
            "recall":tp/r if r else 0.0,"f1":2*tp/(p+r) if p+r else 0.0,"by_group":by}

def section_for_time(sections,t):
    return next((s for s in sections if float(s["startSec"])<=t<float(s["endSec"])),None)

def family_quality(sections,group):
    fam=[s for s in sections if s["group"]==group]
    if len(fam)<2:return 0.0
    vals=[float(s.get("repeatSimilarity",1)) for s in fam if int(s.get("occurrence",1))>1]
    return sum(vals)/len(vals) if vals else 1.0

def slot_info(t,section,bar_sec):
    rel=max(0.0,t-float(section["startSec"]))
    bi=int(math.floor(rel/bar_sec+1e-8));inside=rel-bi*bar_sec
    slot=int(round(inside/bar_sec*16))
    if slot>=16:bi+=1;slot=0
    return bi,max(0,min(15,slot))

def family_support(t,group,section,sections,baseline,bar_sec):
    bi,slot=slot_info(t,section,bar_sec)
    others=[s for s in sections if s["group"]==section["group"] and s["index"]!=section["index"]]
    eligible=support=0
    for other in others:
        target=float(other["startSec"])+bi*bar_sec+slot/16*bar_sec
        if target>=float(other["endSec"])-.03:continue
        eligible+=1
        if nearest(baseline,target,group,.075):support+=1
    return bi,slot,support,eligible,(support/eligible if eligible else 0.0)

def unmatched_truth(baseline,truth,group,tol=.08):
    refs=[(float(e["time"]),i) for i,e in enumerate(truth) if e["group"]==group]
    used=set()
    for e in sorted((x for x in baseline if x["group"]==group),key=lambda z:z["time"]):
        t=float(e["time"])
        opts=[(abs(t-x),i) for x,i in refs if i not in used and abs(t-x)<=tol]
        if opts:used.add(min(opts)[1])
    return {i for _,i in refs if i not in used}

def build_rows(data,prior,truth):
    rows=[];baselines={}
    for song in SONGS:
        sr=data["songs"][song];baseline=[dict(e) for e in sr["finalKst"]];baselines[song]=baseline
        sections=sr["analyses"]["sensitive"]["sections"]
        bpm=float(sr["bpm"]);num=int(sr.get("numerator",4));den=int(sr.get("denominator",4))
        bar=(60/bpm*4/den)*num
        unmatched={g:unmatched_truth(baseline,truth[song],g) for g in GROUPS}
        for group in GROUPS:
            for c in (sr.get("candidates") or {}).get(group,[]):
                t=float(c["time"])
                if nearest(baseline,t,group,.055):continue
                conf=float(c.get("confidence") or 0)
                # Preserve v39 post-filter-origin safety.
                if group!="kick" and conf>=1.0:continue
                p=c.get("egmdProbability");thr=c.get("egmdModelThreshold")
                if p is None or thr is None:continue
                p=float(p);thr=float(thr)
                sec=section_for_time(sections,t)
                fq=0.0;bi=0;slot=0;sup=elig=0;rate=0.0;occ=1.0;rep=0.0;sec_bars=0.0;repeated=0.0
                if sec:
                    fq=family_quality(sections,sec["group"])
                    bi,slot,sup,elig,rate=family_support(t,group,sec,sections,baseline,bar)
                    occ=float(sec.get("occurrence",1) or 1)
                    rep=float(sec.get("repeatSimilarity",0) or 0)
                    sec_bars=max(0.0,(float(sec["endSec"])-float(sec["startSec"]))/bar)
                    repeated=1.0 if elig>=1 else 0.0
                gmd=float(prior["lift"][group][slot])
                residual=abs(float(c.get("residual") or 0))
                x=[
                  conf,float(c.get("score") or 0),float(c.get("broadConfidence") or 0),
                  p,p-thr,1.0 if p>=thr else 0.0,
                  fq,rate,float(sup),float(elig),gmd,
                  math.sin(2*math.pi*slot/16),math.cos(2*math.pi*slot/16),
                  min(4.0,occ),rep,repeated,min(16,max(0,bi))/16,sec_bars,residual
                ]
                y=0
                best=None
                for idx in unmatched[group]:
                    d=abs(float(truth[song][idx]["time"])-t)
                    if d<=.08 and (best is None or d<best[0]):best=(d,idx)
                if best is not None:y=1
                rows.append({
                  "song":song,"group":group,"time":t,"x":x,"y":y,
                  "confidence":conf,"egmd_probability":p,"egmd_threshold":thr,
                  "egmd_margin":p-thr,"family_quality":fq,"support_rate":rate,
                  "support":sup,"eligible":elig,"gmd_lift":gmd,"slot":slot,
                  "family":sec["group"] if sec else None,"label":sec.get("label") if sec else None,
                })
    return rows,baselines

def dedupe(items):
    out=[]
    for r,rank in sorted(items,key=lambda z:(z[0]["time"],z[0]["group"],-z[1])):
        old=next((x for x in out if x[0]["group"]==r["group"] and abs(x[0]["time"]-r["time"])<=.05),None)
        if old is None:out.append((r,rank))
        elif rank>old[1]:out[out.index(old)]=(r,rank)
    return out

def fixed_v39(rows,song):
    out=[]
    for r in rows:
        if r["song"]!=song:continue
        if r["eligible"]<1 or r["support"]<1 or r["support_rate"]<.5:continue
        if r["family_quality"]<.90 or r["confidence"]<.50 or r["gmd_lift"]<.80:continue
        rank=r["confidence"]+.35*r["support_rate"]+.12*min(2,r["gmd_lift"])+.08*r["family_quality"]
        out.append((r,rank))
    return dedupe(out)

def h1_egmd(rows,song):
    return dedupe([(r,r["egmd_probability"]) for r in rows
                   if r["song"]==song and r["egmd_probability"]>=r["egmd_threshold"]])

def h2_arrangement_egmd(rows,song):
    out=[]
    for r in rows:
        if r["song"]!=song:continue
        if r["eligible"]<1 or r["support"]<1 or r["support_rate"]<.5:continue
        if r["family_quality"]<.90 or r["confidence"]<.50 or r["gmd_lift"]<.80:continue
        if r["egmd_probability"]<r["egmd_threshold"]:continue
        out.append((r,r["egmd_probability"]+.25*r["support_rate"]+.1*r["family_quality"]))
    return dedupe(out)

def evaluate(adds,baselines,truth):
    scores={};detail={}
    for s in SONGS:
        a=adds.get(s,[])
        pred=[*baselines[s],*({"time":r["time"],"group":r["group"]} for r,_ in a)]
        sc=score(pred,truth[s]);base=score(baselines[s],truth[s])
        inc_pred=sc["pred"]-base["pred"];inc_tp=sc["tp"]-base["tp"]
        scores[s]=sc
        detail[s]={"added":inc_pred,"tp":inc_tp,"fp":inc_pred-inc_tp,
                   "rows":[{"time":r["time"],"group":r["group"],"egmdProbability":r["egmd_probability"],
                            "egmdThreshold":r["egmd_threshold"],"confidence":r["confidence"],
                            "supportRate":r["support_rate"],"familyQuality":r["family_quality"],
                            "gmdLift":r["gmd_lift"],"family":r["family"],"label":r["label"]} for r,_ in a]}
    return merge_scores(list(scores.values())),scores,detail

def model_for(kind):
    if kind=="logistic":
        return make_pipeline(StandardScaler(),LogisticRegression(C=.4,class_weight="balanced",max_iter=3000,random_state=923))
    return ExtraTreesClassifier(n_estimators=500,min_samples_leaf=2,max_features=.75,class_weight="balanced",random_state=923,n_jobs=-1)

def train(rows,kind,group):
    rr=[r for r in rows if r["group"]==group]
    y=np.asarray([r["y"] for r in rr],int)
    if len(rr)<16 or y.sum()<3 or (len(rr)-y.sum())<3:
        return None,{"rows":len(rr),"positive":int(y.sum()),"negative":int(len(rr)-y.sum()),"reason":"insufficient"}
    X=np.asarray([r["x"] for r in rr],float);m=model_for(kind);m.fit(X,y)
    return m,{"rows":len(rr),"positive":int(y.sum()),"negative":int(len(rr)-y.sum())}

def predictions(model,rows,group):
    rr=[r for r in rows if r["group"]==group]
    if model is None:return []
    p=model.predict_proba(np.asarray([r["x"] for r in rr],float))[:,1]
    return [(r,float(q)) for r,q in zip(rr,p)]

def aggregate_group(songs,baselines,truth,preds,threshold,group):
    rows=[];added=0
    for song in songs:
        a=dedupe([(r,p) for r,p in preds if r["song"]==song and p>=threshold])
        pred=[*baselines[song],*({"time":r["time"],"group":group} for r,_ in a)]
        rows.append(score_group(pred,truth[song],group));added+=len(a)
    tp=sum(x["tp"] for x in rows);pp=sum(x["pred"] for x in rows);ref=sum(x["ref"] for x in rows)
    return {"tp":tp,"pred":pp,"ref":ref,"f1":2*tp/(pp+ref) if pp+ref else 0.0,"added":added}

def choose_threshold(train_songs,baselines,truth,preds,group):
    base=aggregate_group(train_songs,baselines,truth,[],2.0,group)
    floor={"kick":.90,"snare":.85,"tom":.80}[group]
    best={"threshold":1.01,"delta":0.0,"added":0,"added_tp":0,"added_precision":None}
    for th in np.linspace(.15,.95,33):
        x=aggregate_group(train_songs,baselines,truth,preds,float(th),group)
        added=x["pred"]-base["pred"];tp=x["tp"]-base["tp"];prec=tp/added if added else None
        delta=x["f1"]-base["f1"]
        if added<=0 or tp<=0 or prec is None or prec<floor or delta<=0:continue
        key=(delta,prec,tp,-added,float(th))
        old=(best["delta"],best["added_precision"] or -1,best["added_tp"],-best["added"],best["threshold"])
        if key>old:best={"threshold":float(th),"delta":delta,"added":added,"added_tp":tp,"added_precision":prec}
    return best

def learned_loocv(rows,baselines,truth,kind):
    adds={s:[] for s in SONGS};folds={}
    for held in SONGS:
        train_songs=[s for s in SONGS if s!=held]
        tr=[r for r in rows if r["song"] in train_songs];te=[r for r in rows if r["song"]==held]
        folds[held]={"groups":{}}
        for g in GROUPS:
            m,meta=train(tr,kind,g);pp=predictions(m,tr,g)
            th=choose_threshold(train_songs,baselines,truth,pp,g) if m is not None else {"threshold":1.01,"delta":0.0}
            hp=predictions(m,te,g)
            chosen=dedupe([(r,p) for r,p in hp if p>=th["threshold"]]) if m is not None else []
            adds[held].extend(chosen)
            folds[held]["groups"][g]={"training":meta,"threshold":th,"heldoutCandidates":len(hp),"selected":len(chosen)}
        adds[held]=dedupe(adds[held])
    agg,scores,detail=evaluate(adds,baselines,truth)
    return {"aggregate":agg,"songs":scores,"detail":detail,"folds":folds}

def decorate(variant,baseline):
    x=variant["aggregate"];x["delta_f1"]=x["f1"]-baseline["f1"]
    for g in GROUPS:x["by_group"][g]["delta_f1"]=x["by_group"][g]["f1"]-baseline["by_group"][g]["f1"]
    return variant

def main():
    data=json.loads(IN.read_text());prior=json.loads(PRIOR.read_text())
    truth={}
    for s in SONGS:
        meta=json.loads((ROOT/"DruMaster"/"songs"/s/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        truth[s]=parse_midi(ROOT/"DruMaster"/"songs"/s/"chart.mid",shift)
    rows,baselines=build_rows(data,prior,truth)
    base_scores={s:score(baselines[s],truth[s]) for s in SONGS};baseline=merge_scores(list(base_scores.values()))

    variants={}
    for name,fn in [
      ("fixed_v39d",fixed_v39),
      ("H1_egmd_acoustic_only",h1_egmd),
      ("H2_arrangement_plus_egmd",h2_arrangement_egmd),
    ]:
        a={s:fn(rows,s) for s in SONGS}
        agg,scores,detail=evaluate(a,baselines,truth)
        variants[name]=decorate({"aggregate":agg,"songs":scores,"detail":detail},baseline)
    variants["H3_logistic_fusion_loocv"]=decorate(learned_loocv(rows,baselines,truth,"logistic"),baseline)
    variants["H4_extra_trees_fusion_loocv"]=decorate(learned_loocv(rows,baselines,truth,"extra_trees"),baseline)

    result={
      "schema":1,"date":"2026-09-23","experiment":"arrangement-egmd-fusion-v44",
      "reference_policy":"Browser candidate generation reads no chart.mid. H3/H4 use song-held-out training: held-out chart is scoring-only after model and threshold are fixed from the other four songs.",
      "external_egmd_model":"models/egmd-kst-reclassifier-v4.json",
      "external_training_candidate_counts":{"kick":4422,"snare":6580,"tom":7934,"total":18936},
      "features":FEATURES,
      "candidate_pool":{
        "rows":len(rows),
        "by_group":{g:{"rows":sum(r["group"]==g for r in rows),"positive":sum(r["group"]==g and r["y"] for r in rows)} for g in GROUPS}
      },
      "baseline":baseline,"variants":variants
    }
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")

    def f(x):return f"{x:.6f}"
    lines=["# Arrangement + E-GMD K/S/T fusion v44","",
      "Frozen E-GMD v4 acoustic probabilities are attached to fresh browser low-threshold K/S/T candidates, then combined with A/A' structural evidence.","",
      f"External E-GMD v4 training candidates: **18,936** (Kick 4,422 / Snare 6,580 / Tom 7,934).",
      f"Five-song transfer candidate pool after baseline/post-filter safety: **{len(rows)}**.",
      "",
      "| variant | KST F1 | delta | kick delta | snare delta | tom delta | added TP/FP |",
      "|---|---:|---:|---:|---:|---:|---:|"]
    order=["fixed_v39d","H1_egmd_acoustic_only","H2_arrangement_plus_egmd","H3_logistic_fusion_loocv","H4_extra_trees_fusion_loocv"]
    for name in order:
        v=variants[name];d=v["detail"];tp=sum(x["tp"] for x in d.values());fp=sum(x["fp"] for x in d.values())
        a=v["aggregate"]
        lines.append(f"| {name} | {f(a['f1'])} | {f(a['delta_f1'])} | {f(a['by_group']['kick']['delta_f1'])} | {f(a['by_group']['snare']['delta_f1'])} | {f(a['by_group']['tom']['delta_f1'])} | {tp}/{fp} |")
    lines += ["","Candidate pool by group:"]
    for g,x in result["candidate_pool"]["by_group"].items():lines.append(f"- {g}: {x['rows']} rows / {x['positive']} recoverable positives")
    lines += ["","Guardrails:",
      "- E-GMD model is frozen before DruMaster scoring.",
      "- H3/H4 are leave-one-song-out; held-out chart never tunes that fold.",
      "- Snare/Tom candidates with confidence >= 1 that were removed downstream remain excluded.",
      "- No note is copied from A to A'.",
      "- Production remains unchanged until a candidate beats fixed v39D and passes fresh rhythm-grid/MIDI/hand-constraint validation.",
      ""]
    MD.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__":main()
