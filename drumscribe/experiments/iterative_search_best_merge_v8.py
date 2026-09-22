"""Cycles 216-218: merge independently validated hat and pedal improvements.

Base: c197_merge.
Hat sources: adaptive-v2 cycle207 ratio thresholds.
Pedal sources: sparse-gate cycle210 count thresholds.

216: hat-only / pedal-only / both.
217: with pedal fixed, hat threshold 1.2 / 1.5 / 1.8.
218: with winning hat, pedal threshold 5 / 20 / 50.

Parts are copied from real generated MIDI candidates; outputs are new real MIDI,
re-read and scored on all songs/parts.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
BASE=EXP/"generated-search-browser-component-fusion/cycle197/c197_merge"
HATS={1.2:EXP/"generated-search-hat-adaptive-v2/cycle207/c207_r12",1.5:EXP/"generated-search-hat-adaptive-v2/cycle207/c207_r15",1.8:EXP/"generated-search-hat-adaptive-v2/cycle207/c207_r18"}
PEDS={5:EXP/"generated-search-pedal-sparse-gate/cycle210/c210_n5",20:EXP/"generated-search-pedal-sparse-gate/cycle210/c210_n20",50:EXP/"generated-search-pedal-sparse-gate/cycle210/c210_n50"}

def loadmod(name,path):
 sp=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py");base=loadmod("base",EXP/"iterative_search.py");detail=loadmod("detail",EXP/"detailed_metrics.py");sel=loadmod("sel",EXP/"selection_policy.py")

def rows(path,s):return [(t,g) for t,g,*_ in ev.midi_events(path/f"{s}.mid")]
def meta(s):return json.loads((ROOT/"DruMaster/songs"/s/"song.json").read_text())

def compose(song,hat_thr=None,ped_n=None):
 rr=rows(BASE,song)
 if hat_thr is not None:
  hh=[x for x in rows(HATS[hat_thr],song) if x[1]=="hat"]
  rr=[x for x in rr if x[1]!="hat"]+hh
 if ped_n is not None:
  pp=[x for x in rows(PEDS[ped_n],song) if x[1]=="pedal_hat"]
  rr=[x for x in rr if x[1]!="pedal_hat"]+pp
 return sorted(rr)

def write(path,rr,bpm):base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in rr],bpm)

def evaluate(name,hat_thr,ped_n,outdir):
 result={"hat_threshold":hat_thr,"pedal_min_count":ped_n,"songs":{}};tot=Counter()
 for s in SONGS:
  rr=compose(s,hat_thr,ped_n);m=meta(s);p=outdir/name/f"{s}.mid";write(p,rr,float(m["bpm"]))
  pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/s/"chart.mid");sh=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
  sc=ev.score(pred,truth,sh);cf=ev.confusion(pred,truth,sh);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][s]=sc
  tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
  for g,z in sc["by_group"].items():tot[f"{g}_tp"]+=z["tp"];tot[f"{g}_pred"]+=z["predicted"];tot[f"{g}_ref"]+=z["reference"]
 tp,n,r=tot["tp"],tot["predicted"],tot["reference"];sm={"tp":tp,"predicted":n,"reference":r,"precision":tp/n if n else 0,"recall":tp/r if r else 0,"f1":2*tp/(n+r) if n+r else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":0,"by_group":{}}
 for g in GROUPS:
  a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
  for s in SONGS:
   z=result["songs"][s]["by_group"].get(g,{});ref=z.get("reference",0)
   if ref:sf.append(2*z.get("tp",0)/(z.get("predicted",0)+ref) if z.get("predicted",0)+ref else 0)
  sm["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,"false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,"count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
 result["summary"]=sm;result["canonical_score"]=sel.score(sm);result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def choose(res,baseline,targets):
 d=sel.select(res,baseline["summary"],target_parts=targets,max_part_drop=.008,target_tolerance=.004)
 for n in res:res[n]["guard"]=d["guards"][n]
 return d

def main():
 root=EXP/"generated-search-best-merge-v8";report={"schema":1,"cycles":[]};baseline=evaluate("baseline",None,None,root/"baseline")
 res={
  "c216_hat":evaluate("c216_hat",1.5,None,root/"cycle216"),
  "c216_pedal":evaluate("c216_pedal",None,50,root/"cycle216"),
  "c216_both":evaluate("c216_both",1.5,50,root/"cycle216")}
 for n,v in res.items():print("SUMMARY",n,json.dumps({"f1":v["summary"]["f1"],"hat":v["summary"]["by_group"]["hat"],"pedal":v["summary"]["by_group"]["pedal_hat"],"score":v["canonical_score"]},ensure_ascii=False),flush=True)
 d=choose(res,baseline,("hat","pedal_hat"));w=d["winner"] or "c216_both";b1=res[w];report["cycles"].append({"cycle":216,"candidates":res,"winner":w,"ranking":d["ranking"],"guards":d["guards"]})

 res={}
 for name,t in [("c217_h12",1.2),("c217_h15",1.5),("c217_h18",1.8)]:
  res[name]=evaluate(name,t,50,root/"cycle217");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
 d=choose(res,b1,("hat","pedal_hat"));w=d["winner"] or "c217_h15";b2=res[w];report["cycles"].append({"cycle":217,"candidates":res,"winner":w,"ranking":d["ranking"],"guards":d["guards"]})

 res={}
 ht=b2["hat_threshold"]
 for name,nc in [("c218_p5",5),("c218_p20",20),("c218_p50",50)]:
  res[name]=evaluate(name,ht,nc,root/"cycle218");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
 d=choose(res,b2,("hat","pedal_hat"));w=d["winner"] or "c218_p50";b3=res[w];report["cycles"].append({"cycle":218,"candidates":res,"winner":w,"ranking":d["ranking"],"guards":d["guards"]})
 best=max([baseline,b1,b2,b3],key=lambda z:z["canonical_score"]["score"]);report["baseline"]=baseline;report["final"]={"winner":"cross-cycle-best","summary":best["summary"],"canonical_score":best["canonical_score"],"hat_threshold":best["hat_threshold"],"pedal_min_count":best["pedal_min_count"],"detailed":best["detailed"]}
 (EXP/"results-iterative-best-merge-v8.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n");print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
