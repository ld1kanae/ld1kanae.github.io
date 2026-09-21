"""Canonical detailed MIDI comparison for DrumScribe experiments.

Scores real generated MIDI files against chart.mid after generation.
Outputs every song x every part with:
- TP / FP / FN
- precision / recall / F1
- false discovery and miss rates
- predicted/reference count ratio
- matched timing error distribution
- unmatched prediction distance to nearest same-class reference
- class-confusion matrix
- hat/cymbal family aggregates

Reference MIDI is never used by transcription; this module is evaluation only.
"""
from __future__ import annotations
import argparse, importlib.util, json, math
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(".")
spec=importlib.util.spec_from_file_location("ev",ROOT/"drumscribe/experiments/evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=list(ev.ORDER)
TOL=.080

def _percentile(xs,q):
    if not xs:return None
    return round(float(np.percentile(np.asarray(xs,dtype=float),q)),6)

def greedy_match(pred,ref,tol=TOL):
    """One-to-one nearest-time matching within one class."""
    pairs=[];used=set()
    order=sorted(range(len(pred)),key=lambda i:pred[i][0])
    for pi in order:
        pt=pred[pi][0];best=None
        for ri,(rt,*_) in enumerate(ref):
            if ri in used:continue
            d=abs(pt-rt)
            if d<=tol and (best is None or d<best[0]):
                best=(d,ri)
        if best is not None:
            used.add(best[1]);pairs.append((pi,best[1],pred[pi][0]-ref[best[1]][0]))
    return pairs,used

def nearest_distance(t,refs):
    if not refs:return None
    return min(abs(t-r[0]) for r in refs)

def class_confusions(pred,ref,tol=TOL):
    """Count wrong-class nearby reference hits after same-class support check."""
    matrix=Counter()
    for pt,pg,*_ in pred:
        same=any(rg==pg and abs(pt-rt)<=tol for rt,rg,*_ in ref)
        if same:continue
        near=[(abs(pt-rt),rg) for rt,rg,*_ in ref if rg!=pg and abs(pt-rt)<=tol]
        if near:
            _,rg=min(near)
            matrix[f"{rg}_to_{pg}"]+=1
    return dict(sorted(matrix.items()))

def score_group(pred,ref):
    pairs,used=greedy_match(pred,ref)
    tp=len(pairs);fp=len(pred)-tp;fn=len(ref)-tp
    errs=[e for _,_,e in pairs]
    abs_err=[abs(e) for e in errs]
    unmatched=[pred[i] for i in range(len(pred)) if i not in {p[0] for p in pairs}]
    nearest=[nearest_distance(x[0],ref) for x in unmatched]
    nearest=[x for x in nearest if x is not None]
    precision=tp/len(pred) if pred else 0.0
    recall=tp/len(ref) if ref else 0.0
    f1=2*tp/(len(pred)+len(ref)) if len(pred)+len(ref) else 0.0
    return {
      "tp":tp,"fp":fp,"fn":fn,"predicted":len(pred),"reference":len(ref),
      "precision":round(precision,6),"recall":round(recall,6),"f1":round(f1,6),
      "false_discovery_rate":round(fp/len(pred),6) if pred else 0.0,
      "miss_rate":round(fn/len(ref),6) if ref else 0.0,
      "count_ratio":round(len(pred)/len(ref),6) if ref else None,
      "timing_signed_mean_ms":round(1000*float(np.mean(errs)),3) if errs else None,
      "timing_abs_median_ms":round(1000*_percentile(abs_err,50),3) if abs_err else None,
      "timing_abs_p90_ms":round(1000*_percentile(abs_err,90),3) if abs_err else None,
      "unmatched_nearest_ref_median_ms":round(1000*_percentile(nearest,50),3) if nearest else None,
      "unmatched_farther_than_160ms":sum(1 for x in nearest if x>.160),
    }

def score_song(pred,ref):
    out={"by_group":{}}
    for g in GROUPS:
        pp=[x for x in pred if x[1]==g];rr=[x for x in ref if x[1]==g]
        out["by_group"][g]=score_group(pp,rr)
    out["confusion_matrix"]=class_confusions(pred,ref)
    out["families"]={}
    for name,groups in {
      "hat_family":["hat","pedal_hat"],
      "cymbal_family":["crash","ride","other"],
      "kick_snare":["kick","snare"],
      "hands":["snare","hat","tom","crash","ride"],
    }.items():
        pp=[x for x in pred if x[1] in groups];rr=[x for x in ref if x[1] in groups]
        # Family matching ignores within-family subtype for this diagnostic only.
        p2=[(x[0],name,*x[2:]) for x in pp];r2=[(x[0],name,*x[2:]) for x in rr]
        out["families"][name]=score_group(p2,r2)
    tp=sum(x["tp"] for x in out["by_group"].values())
    pr=sum(x["predicted"] for x in out["by_group"].values())
    rf=sum(x["reference"] for x in out["by_group"].values())
    out["overall"]={
      "tp":tp,"predicted":pr,"reference":rf,
      "precision":round(tp/pr,6) if pr else 0,
      "recall":round(tp/rf,6) if rf else 0,
      "f1":round(2*tp/(pr+rf),6) if pr+rf else 0,
    }
    return out

def aggregate(songs):
    out={"by_group":{},"families":{}}
    for g in GROUPS:
        xs=[s["by_group"][g] for s in songs.values()]
        tp=sum(x["tp"] for x in xs);pr=sum(x["predicted"] for x in xs);rf=sum(x["reference"] for x in xs)
        song_f1=[x["f1"] for x in xs if x["reference"]>0]
        out["by_group"][g]={
          "tp":tp,"fp":pr-tp,"fn":rf-tp,"predicted":pr,"reference":rf,
          "precision":round(tp/pr,6) if pr else 0,
          "recall":round(tp/rf,6) if rf else 0,
          "f1":round(2*tp/(pr+rf),6) if pr+rf else 0,
          "false_discovery_rate":round((pr-tp)/pr,6) if pr else 0,
          "miss_rate":round((rf-tp)/rf,6) if rf else 0,
          "count_ratio":round(pr/rf,6) if rf else None,
          "mean_song_f1":round(float(np.mean(song_f1)),6) if song_f1 else None,
          "worst_song_f1":round(float(np.min(song_f1)),6) if song_f1 else None,
        }
    for fam in next(iter(songs.values()))["families"]:
        xs=[s["families"][fam] for s in songs.values()]
        tp=sum(x["tp"] for x in xs);pr=sum(x["predicted"] for x in xs);rf=sum(x["reference"] for x in xs)
        out["families"][fam]={
          "tp":tp,"fp":pr-tp,"fn":rf-tp,"predicted":pr,"reference":rf,
          "precision":round(tp/pr,6) if pr else 0,
          "recall":round(tp/rf,6) if rf else 0,
          "f1":round(2*tp/(pr+rf),6) if pr+rf else 0,
          "count_ratio":round(pr/rf,6) if rf else None,
        }
    tp=sum(s["overall"]["tp"] for s in songs.values());pr=sum(s["overall"]["predicted"] for s in songs.values());rf=sum(s["overall"]["reference"] for s in songs.values())
    out["overall"]={"tp":tp,"predicted":pr,"reference":rf,"precision":round(tp/pr,6) if pr else 0,"recall":round(tp/rf,6) if rf else 0,"f1":round(2*tp/(pr+rf),6) if pr+rf else 0}
    return out

def compare_dir(pred_dir:Path,name:str):
    songs={}
    for song in SONGS:
        folder=ROOT/"DruMaster/songs"/song
        meta=json.loads((folder/"song.json").read_text())
        shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
        pred=ev.midi_events(pred_dir/f"{song}.mid")
        ref0=ev.midi_events(folder/"chart.mid")
        ref=[(t+shift,g,*rest) for t,g,*rest in ref0]
        songs[song]=score_song(pred,ref)
    return {"schema":1,"name":name,"tolerance_sec":TOL,"pred_dir":str(pred_dir),"songs":songs,"aggregate":aggregate(songs)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pred-dir",required=True);ap.add_argument("--name",required=True);ap.add_argument("--out",required=True)
    a=ap.parse_args()
    obj=compare_dir(Path(a.pred_dir),a.name)
    Path(a.out).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(obj["aggregate"],ensure_ascii=False,indent=2))

if __name__=="__main__":main()
