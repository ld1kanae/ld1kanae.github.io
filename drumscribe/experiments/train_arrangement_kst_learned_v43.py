from __future__ import annotations

import json, math
from collections import Counter, defaultdict
from pathlib import Path

import mido
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(".")
CAND=ROOT/"drumscribe/experiments/results-arrangement-kst-candidates-v38.json"
PRIOR=ROOT/"drumscribe/models/gmd-kst/slot-prior-v1.json"
OUT=ROOT/"drumscribe/experiments/results-arrangement-kst-learned-v43.json"
MD=ROOT/"drumscribe/experiments/ARRANGEMENT_KST_LEARNED_V43.md"
MODEL_OUT=ROOT/"drumscribe/models/arrangement-kst/learned-rescore-v43.json"
DATASET_OUT=ROOT/"drumscribe/models/arrangement-kst/training-candidates-v43.json"

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=("kick","snare","tom")
NOTE_TO_GROUP={}
for n in (35,36): NOTE_TO_GROUP[n]="kick"
for n in (37,38,39,40): NOTE_TO_GROUP[n]="snare"
for n in (41,43,45,47,48,50): NOTE_TO_GROUP[n]="tom"

FEATURES=[
    "confidence","score","broad_confidence","family_quality","support_rate",
    "support_count","eligible_count","gmd_lift","slot_sin","slot_cos",
    "occurrence","repeat_similarity","bar_index_clip","section_bars","residual_abs",
]

ALGOS=("logistic","extra_trees","random_forest")

def parse_midi(path,shift):
    mid=mido.MidiFile(path)
    tempo=500000; sec=0.0; out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=="set_tempo":
            tempo=msg.tempo
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
    return {"tp":tp,"pred":len(p),"ref":len(r),
            "precision":tp/len(p) if p else 0.0,
            "recall":tp/len(r) if r else 0.0,
            "f1":2*tp/(len(p)+len(r)) if p or r else 0.0}

def score(pred,truth):
    by={g:score_group(pred,truth,g) for g in GROUPS}
    tp=sum(x["tp"] for x in by.values());p=sum(x["pred"] for x in by.values());r=sum(x["ref"] for x in by.values())
    return {"tp":tp,"pred":p,"ref":r,
            "precision":tp/p if p else 0.0,"recall":tp/r if r else 0.0,
            "f1":2*tp/(p+r) if p+r else 0.0,"by_group":by}

def merge_scores(rows):
    by={}
    for g in GROUPS:
        tp=sum(x["by_group"][g]["tp"] for x in rows)
        p=sum(x["by_group"][g]["pred"] for x in rows)
        r=sum(x["by_group"][g]["ref"] for x in rows)
        by[g]={"tp":tp,"pred":p,"ref":r,
               "precision":tp/p if p else 0.0,"recall":tp/r if r else 0.0,
               "f1":2*tp/(p+r) if p+r else 0.0}
    tp=sum(x["tp"] for x in by.values());p=sum(x["pred"] for x in by.values());r=sum(x["ref"] for x in by.values())
    return {"tp":tp,"pred":p,"ref":r,
            "precision":tp/p if p else 0.0,"recall":tp/r if r else 0.0,
            "f1":2*tp/(p+r) if p+r else 0.0,"by_group":by}

def family_quality(sections,group):
    fam=[s for s in sections if s["group"]==group]
    if len(fam)<2:return 0.0
    vals=[float(s.get("repeatSimilarity",1)) for s in fam if int(s.get("occurrence",1))>1]
    return sum(vals)/len(vals) if vals else 1.0

def section_for_time(sections,t):
    return next((s for s in sections if float(s["startSec"])<=t<float(s["endSec"])),None)

def slot_info(t,section,bar_sec):
    rel=max(0.0,t-float(section["startSec"]))
    bar_idx=int(math.floor(rel/bar_sec+1e-8))
    inbar=rel-bar_idx*bar_sec
    slot=int(round(inbar/bar_sec*16))
    if slot>=16: bar_idx+=1;slot=0
    return bar_idx,max(0,min(15,slot))

def family_support(t,group,section,sections,baseline,bar_sec):
    bar_idx,slot=slot_info(t,section,bar_sec)
    others=[s for s in sections if s["group"]==section["group"] and s["index"]!=section["index"]]
    eligible=support=0
    for other in others:
        target=float(other["startSec"])+bar_idx*bar_sec+slot/16*bar_sec
        if target>=float(other["endSec"])-.03: continue
        eligible+=1
        if nearest(baseline,target,group,.075): support+=1
    return bar_idx,slot,support,eligible,(support/eligible if eligible else 0.0)

def unmatched_truth_indices(baseline,truth,group,tol=.08):
    p=sorted((float(e["time"]),i) for i,e in enumerate(baseline) if e["group"]==group)
    r=[(float(e["time"]),i) for i,e in enumerate(truth) if e["group"]==group]
    used=set()
    for t,_ in p:
        opts=[(abs(t-x),idx) for x,idx in r if idx not in used and abs(t-x)<=tol]
        if opts: used.add(min(opts)[1])
    return {idx for _,idx in r if idx not in used}

def build_rows(data,prior,truth_by_song):
    rows=[]
    baselines={}
    for song in SONGS:
        sr=data["songs"][song]
        baseline=[dict(e) for e in sr["finalKst"]]
        baselines[song]=baseline
        sections=sr["analyses"]["sensitive"]["sections"]
        bpm=float(sr["bpm"]);num=int(sr.get("numerator",4));den=int(sr.get("denominator",4))
        bar_sec=(60/bpm*4/den)*num
        unmatched={g:unmatched_truth_indices(baseline,truth_by_song[song],g) for g in GROUPS}
        truth=truth_by_song[song]
        for group in GROUPS:
            for c in (sr.get("candidates") or {}).get(group,[]):
                t=float(c["time"])
                if nearest(baseline,t,group,.055): continue
                # Preserve the v39 safety lesson: arrangement learning is for
                # threshold misses, not for overriding downstream Snare/Tom vetoes.
                conf=float(c.get("confidence") or 0)
                if group!="kick" and conf>=1.0: continue
                sec=section_for_time(sections,t)
                if not sec: continue
                fq=family_quality(sections,sec["group"])
                bi,slot,sup,elig,rate=family_support(t,group,sec,sections,baseline,bar_sec)
                # v43 widens the training population: a candidate only needs to
                # belong to a structural family that has another occurrence.
                # support==0 is retained as an informative negative/weak-evidence
                # example instead of being removed before learning.
                if elig<1: continue
                gmd=float(prior["lift"][group][slot])
                repeat=float(sec.get("repeatSimilarity",1) or 1)
                occurrence=int(sec.get("occurrence",1) or 1)
                duration=max(.001,float(sec["endSec"])-float(sec["startSec"]))
                residual=abs(float(c.get("residual") or 0))
                x=[
                    conf,float(c.get("score") or 0),float(c.get("broadConfidence") or 0),
                    fq,rate,float(sup),float(elig),gmd,
                    math.sin(2*math.pi*slot/16),math.cos(2*math.pi*slot/16),
                    float(min(4,occurrence)),repeat,float(min(16,max(0,bi)))/16,
                    duration/bar_sec,residual,
                ]
                # Positive only if this candidate can recover a reference event
                # not already claimed by the baseline.
                y=0
                best=None
                for idx in unmatched[group]:
                    e=truth[idx]
                    d=abs(float(e["time"])-t)
                    if d<=.08 and (best is None or d<best[0]): best=(d,idx)
                if best is not None: y=1
                rows.append({
                    "song":song,"group":group,"time":t,"x":x,"y":y,
                    "confidence":conf,"family":sec["group"],"label":sec.get("label",sec["group"]),
                    "family_quality":fq,"support_rate":rate,"support":sup,"eligible":elig,
                    "slot":slot,"gmd_lift":gmd,
                })
    return rows,baselines

def make_model(name,seed=42):
    if name=="logistic":
        return make_pipeline(StandardScaler(),LogisticRegression(
            C=.5,class_weight="balanced",max_iter=3000,random_state=seed
        ))
    if name=="extra_trees":
        return ExtraTreesClassifier(
            n_estimators=400,min_samples_leaf=2,max_features=.75,
            class_weight="balanced",random_state=seed,n_jobs=-1
        )
    if name=="random_forest":
        return RandomForestClassifier(
            n_estimators=400,min_samples_leaf=2,max_features=.75,
            class_weight="balanced_subsample",random_state=seed,n_jobs=-1
        )
    raise KeyError(name)

def train_model(rows,algo,group):
    rr=[r for r in rows if r["group"]==group]
    y=np.asarray([r["y"] for r in rr],dtype=int)
    if len(rr)<12 or y.sum()<3 or len(np.unique(y))<2:
        return None,{"rows":len(rr),"positives":int(y.sum()),"reason":"insufficient-class-support"}
    X=np.asarray([r["x"] for r in rr],dtype=float)
    model=make_model(algo)
    model.fit(X,y)
    return model,{"rows":len(rr),"positives":int(y.sum()),"negative":int((y==0).sum())}

def predict_rows(model,rows,group):
    rr=[r for r in rows if r["group"]==group]
    if model is None:return []
    X=np.asarray([r["x"] for r in rr],dtype=float)
    p=model.predict_proba(X)[:,1]
    return [(r,float(q)) for r,q in zip(rr,p)]

def dedupe_selected(selected):
    out=[]
    for row,p in sorted(selected,key=lambda z:(z[0]["time"],-z[1])):
        old=next((x for x in out if abs(x[0]["time"]-row["time"])<=.05 and x[0]["group"]==row["group"]),None)
        if old is None: out.append((row,p))
        elif p>old[1]:
            out[out.index(old)]=(row,p)
    return out

def additions_for_song(predictions,threshold,song,group):
    return dedupe_selected([(r,p) for r,p in predictions if r["song"]==song and r["group"]==group and p>=threshold])

def aggregate_group_score(songs,baselines,truth,predictions,threshold,group):
    rows=[]
    added=0
    for song in songs:
        adds=additions_for_song(predictions,threshold,song,group)
        pred=[*baselines[song],*({"time":r["time"],"group":group,"probability":p} for r,p in adds)]
        rows.append(score_group(pred,truth[song],group))
        added+=len(adds)
    tp=sum(x["tp"] for x in rows);pp=sum(x["pred"] for x in rows);ref=sum(x["ref"] for x in rows)
    return {"tp":tp,"pred":pp,"ref":ref,"f1":2*tp/(pp+ref) if pp+ref else 0.0,"added":added}

def choose_threshold(train_songs,baselines,truth,predictions,group):
    base=aggregate_group_score(train_songs,baselines,truth,[],2.0,group)
    best={"threshold":1.01,"f1":base["f1"],"delta":0.0,"added":0,"added_tp":0,"added_precision":None}
    # probability thresholds are tuned only on the four training songs.
    for th in np.linspace(.15,.95,33):
        sc=aggregate_group_score(train_songs,baselines,truth,predictions,float(th),group)
        added=sc["pred"]-base["pred"];added_tp=sc["tp"]-base["tp"]
        ap=added_tp/added if added else None
        delta=sc["f1"]-base["f1"]
        if added<=0 or added_tp<=0 or ap is None or ap<.80 or delta<=0: continue
        key=(delta,ap,-added,float(th))
        old=(best["delta"],best["added_precision"] or -1,-best["added"],best["threshold"])
        if key>old:
            best={"threshold":float(th),"f1":sc["f1"],"delta":delta,"added":added,
                  "added_tp":added_tp,"added_precision":ap}
    return best

def fixed_v39d_additions(rows,song):
    selected=[]
    for r in rows:
        if r["song"]!=song:continue
        if r["confidence"]<.50 or r["family_quality"]<.90 or r["support_rate"]<.50 or r["gmd_lift"]<.80:continue
        rank=r["confidence"]+.35*r["support_rate"]+.12*min(2,r["gmd_lift"])+.08*r["family_quality"]
        selected.append((r,rank))
    return dedupe_selected(selected)

def evaluate_variant(per_song_additions,baselines,truth):
    scores={};detail={}
    for song in SONGS:
        adds=per_song_additions.get(song,[])
        pred=[*baselines[song],*({"time":r["time"],"group":r["group"]} for r,p in adds)]
        scores[song]=score(pred,truth[song])
        # Incremental TP/FP is derived from full one-to-one score, not candidate label.
        base=score(baselines[song],truth[song])
        inc_tp=scores[song]["tp"]-base["tp"]
        inc_pred=scores[song]["pred"]-base["pred"]
        detail[song]={"added":inc_pred,"tp":inc_tp,"fp":inc_pred-inc_tp,
                      "rows":[{"time":r["time"],"group":r["group"],"probability":p,
                               "confidence":r["confidence"],"support_rate":r["support_rate"],
                               "family_quality":r["family_quality"],"gmd_lift":r["gmd_lift"],
                               "family":r["family"],"label":r["label"],"slot":r["slot"]} for r,p in adds]}
    return merge_scores(list(scores.values())),scores,detail

def fit_full_export(rows,algo):
    export={"schema":1,"version":"arrangement-kst-learned-v43","algorithm":algo,
            "features":FEATURES,"inference_status":"research-only-until-fresh-browser-validation",
            "groups":{}}
    for g in GROUPS:
        model,meta=train_model(rows,algo,g)
        if model is None:
            export["groups"][g]={"enabled":False,"training":meta};continue
        # Full-data threshold for possible later runtime experiment. This is not
        # used for the LOOCV result and therefore is not evidence of generalization.
        preds=predict_rows(model,rows,g)
        # caller fills threshold separately; here expose model parameters when portable.
        info={"enabled":True,"training":meta}
        if algo=="logistic":
            scaler=model.named_steps["standardscaler"];lr=model.named_steps["logisticregression"]
            info["mean"]=scaler.mean_.tolist();info["scale"]=scaler.scale_.tolist()
            info["coef"]=lr.coef_[0].tolist();info["intercept"]=float(lr.intercept_[0])
        export["groups"][g]=info
    return export

def main():
    data=json.loads(CAND.read_text())
    prior=json.loads(PRIOR.read_text())
    truth={}
    for song in SONGS:
        meta=json.loads((ROOT/"DruMaster"/"songs"/song/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        truth[song]=parse_midi(ROOT/"DruMaster"/"songs"/song/"chart.mid",shift)
    rows,baselines=build_rows(data,prior,truth)
    DATASET_OUT.parent.mkdir(parents=True,exist_ok=True)
    DATASET_OUT.write_text(json.dumps({
        "schema":1,
        "version":"arrangement-kst-training-candidates-v43",
        "date":"2026-09-23",
        "features":FEATURES,
        "label_definition":"1 when the candidate matches a same-instrument reference event not already claimed by baseline within 80 ms; chart-derived training label only.",
        "source_note":"Prediction-time features come from drums audio, A/A-prime structural-family analysis, and GMD slot prior. chart.mid contributes only the training label.",
        "rows":[{
            "song":r["song"],"group":r["group"],"time":r["time"],
            "features":r["x"],"label":r["y"],
            "family":r["family"],"section_label":r["label"],
            "confidence":r["confidence"],"family_quality":r["family_quality"],
            "support_rate":r["support_rate"],"support":r["support"],
            "eligible":r["eligible"],"slot":r["slot"],"gmd_lift":r["gmd_lift"]
        } for r in rows]
    },ensure_ascii=False,indent=2)+"\n")
    baseline_scores={s:score(baselines[s],truth[s]) for s in SONGS}
    baseline=merge_scores(list(baseline_scores.values()))

    result={"schema":1,"date":"2026-09-23","experiment":"arrangement-kst-learned-v43",
            "reference_policy":"Each LOOCV fold trains/tunes on four songs. The held-out song chart.mid is used only after its predictions are fixed.",
            "features":FEATURES,
            "dataset":{
                "rows":len(rows),
                "by_group":{g:{"rows":sum(r["group"]==g for r in rows),
                                "positive_labels":sum(r["group"]==g and r["y"] for r in rows)} for g in GROUPS}
            },
            "baseline":baseline,"algorithms":{}}

    # Fixed production v39D-like policy, evaluated on the same candidate pool.
    fixed={s:fixed_v39d_additions(rows,s) for s in SONGS}
    fixed_agg,fixed_scores,fixed_detail=evaluate_variant(fixed,baselines,truth)
    result["fixed_v39d_candidate_replay"]={"aggregate":fixed_agg,"songs":fixed_scores,"detail":fixed_detail}

    for algo in ALGOS:
        heldout_add={s:[] for s in SONGS}
        folds={}
        for heldout in SONGS:
            train_songs=[s for s in SONGS if s!=heldout]
            train_rows=[r for r in rows if r["song"] in train_songs]
            test_rows=[r for r in rows if r["song"]==heldout]
            fold={"heldout":heldout,"groups":{}}
            for g in GROUPS:
                model,meta=train_model(train_rows,algo,g)
                train_pred=predict_rows(model,train_rows,g)
                th=choose_threshold(train_songs,baselines,truth,train_pred,g) if model is not None else {
                    "threshold":1.01,"f1":None,"delta":0.0,"added":0,"added_tp":0,"added_precision":None
                }
                test_pred=predict_rows(model,test_rows,g)
                adds=additions_for_song(test_pred,th["threshold"],heldout,g) if model is not None else []
                heldout_add[heldout].extend(adds)
                fold["groups"][g]={"training":meta,"threshold_selection":th,
                                  "heldout_candidates":len(test_pred),"heldout_selected":len(adds)}
            heldout_add[heldout]=dedupe_selected(heldout_add[heldout])
            folds[heldout]=fold
        agg,scores,detail=evaluate_variant(heldout_add,baselines,truth)
        agg["delta_f1"]=agg["f1"]-baseline["f1"]
        for g in GROUPS:
            agg["by_group"][g]["delta_f1"]=agg["by_group"][g]["f1"]-baseline["by_group"][g]["f1"]
        result["algorithms"][algo]={"aggregate":agg,"folds":folds,"songs":scores,"detail":detail}

    # Export the most portable model (logistic) trained on all five songs for
    # inspection only. Its thresholds are tuned on all five and must not be
    # promoted to runtime unless LOOCV warrants a fresh-browser experiment.
    export=fit_full_export(rows,"logistic")
    for g in GROUPS:
        model,meta=train_model(rows,"logistic",g)
        preds=predict_rows(model,rows,g)
        th=choose_threshold(SONGS,baselines,truth,preds,g) if model is not None else {"threshold":1.01}
        export["groups"][g]["threshold"]=th
    MODEL_OUT.parent.mkdir(parents=True,exist_ok=True)
    MODEL_OUT.write_text(json.dumps(export,ensure_ascii=False,indent=2)+"\n")
    result["full_data_logistic_export"]=str(MODEL_OUT)
    result["training_corpus"]=str(DATASET_OUT)

    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")

    def f(x):return "n/a" if x is None else f"{x:.6f}"
    lines=[
      "# Arrangement K/S/T learned rescoring v43","",
      "Five-song leave-one-song-out (LOOCV). Each held-out song is predicted by models trained and threshold-tuned on the other four songs only.","",
      f"Candidate rows in repeated A/A' families after post-filter-origin safety: **{len(rows)}**.",
      "",
      "| variant | KST F1 | delta | kick delta | snare delta | tom delta | added TP/FP |",
      "|---|---:|---:|---:|---:|---:|---:|"
    ]
    fx=fixed_agg
    fdetail=fixed_detail
    atp=sum(v["tp"] for v in fdetail.values());afp=sum(v["fp"] for v in fdetail.values())
    lines.append(f"| fixed v39D replay | {f(fx['f1'])} | {f(fx['f1']-baseline['f1'])} | {f(fx['by_group']['kick']['f1']-baseline['by_group']['kick']['f1'])} | {f(fx['by_group']['snare']['f1']-baseline['by_group']['snare']['f1'])} | {f(fx['by_group']['tom']['f1']-baseline['by_group']['tom']['f1'])} | {atp}/{afp} |")
    for algo in ALGOS:
        x=result["algorithms"][algo]["aggregate"];d=result["algorithms"][algo]["detail"]
        tp=sum(v["tp"] for v in d.values());fp=sum(v["fp"] for v in d.values())
        lines.append(f"| {algo} LOOCV | {f(x['f1'])} | {f(x['delta_f1'])} | {f(x['by_group']['kick']['delta_f1'])} | {f(x['by_group']['snare']['delta_f1'])} | {f(x['by_group']['tom']['delta_f1'])} | {tp}/{fp} |")
    lines += ["","Dataset by group:"]
    for g,d in result["dataset"]["by_group"].items():
        lines.append(f"- {g}: {d['rows']} candidates / {d['positive_labels']} recoverable-reference labels")
    lines += ["","Guardrails:",
      "- Held-out chart.mid is not used to train or tune that fold.",
      "- Every candidate already has an acoustic event and belongs to a structural family with another occurrence. same-position support, including zero support, is learned as a feature.",
      "- Snare/Tom candidates with confidence >= 1 that were removed downstream stay excluded.",
      "- This is an offline learned-gate experiment. Runtime adoption requires a separate fresh Chromium rhythm-grid/MIDI non-regression run.",
      ""]
    MD.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__":
    main()
