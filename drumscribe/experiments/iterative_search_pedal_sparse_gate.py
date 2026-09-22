"""Cycles 210-212: sparse pedal-hat false-positive suppression on c197.

Prediction-only rules:
210: minimum predicted pedal count 5 / 20 / 50.
211: minimum pedal events per predicted bar 0.02 / 0.05 / 0.10.
212: sparse-song rescue only if periodic support is strong.

No song-name branches; chart.mid is scoring-only after MIDI generation.
"""
from __future__ import annotations
import importlib.util,json,math
from collections import Counter
from pathlib import Path

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
BASE=EXP/"generated-search-browser-component-fusion/cycle197/c197_merge"
BROWSER=EXP/"generated-v2-browser"

def loadmod(name,path):
 sp=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py");base=loadmod("base",EXP/"iterative_search.py");detail=loadmod("detail",EXP/"detailed_metrics.py");sel=loadmod("sel",EXP/"selection_policy.py")

def rows(s):return [(t,g) for t,g,*_ in ev.midi_events(BASE/f"{s}.mid")]
def side(s):return json.loads((BROWSER/f"{s}.json").read_text())
def meta(s):return json.loads((ROOT/"DruMaster/songs"/s/"song.json").read_text())

def periodic(xs,t,bpm):
 best=0.
 for step in (30/bpm,60/bpm,120/bpm):
  n=sum(any(abs(x-(t+k*step))<=.065 for x in xs) for k in (-2,-1,1,2));best=max(best,n/4)
 return best

def apply(song,mode,value,rescue=.75):
 rr=rows(song);p=sorted(t for t,g in rr if g=="pedal_hat");sd=side(song);bpm=float(sd["bpm"]);phase=float(sd["barPhaseSec"]);bar=4*60/bpm
 bars=max(1,math.ceil((max((t for t,g in rr),default=0)-phase)/bar))
 count=len(p);density=count/bars
 drop=False
 if mode=="count":drop=count<value
 elif mode=="density":drop=density<value
 elif mode=="periodic":
  if density<value:
   support=sum(periodic(p,t,bpm)>=rescue for t in p)/max(1,count)
   drop=support<.50
 if drop:p=[]
 return [x for x in rr if x[1]!="pedal_hat"]+[(t,"pedal_hat") for t in p],{"count":count,"bars":bars,"density":density,"dropped":drop}

def write(path,rr,bpm):base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in sorted(rr)],bpm)

def evaluate(name,mode,value,rescue,outdir):
 result={"mode":mode,"value":value,"rescue":rescue,"songs":{},"diagnostic":{}};tot=Counter()
 for s in SONGS:
  rr,d=apply(s,mode,value,rescue);result["diagnostic"][s]=d;p=outdir/name/f"{s}.mid";write(p,rr,float(side(s)["bpm"]))
  pred=ev.midi_events(p);truth=ev.midi_events(ROOT/"DruMaster/songs"/s/"chart.mid");m=meta(s);sh=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
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

def choose(res,basecand):
 d=sel.select(res,basecand["summary"],target_parts=("pedal_hat",),max_part_drop=.010,target_tolerance=.004)
 for n in res:res[n]["guard"]=d["guards"][n]
 return d

def main():
 root=EXP/"generated-search-pedal-sparse-gate";report={"schema":1,"cycles":[]};baseline=evaluate("baseline","count",0,.75,root/"baseline")
 res={}
 for name,v in [("c210_n5",5),("c210_n20",20),("c210_n50",50)]:
  res[name]=evaluate(name,"count",v,.75,root/"cycle210");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"],"diag":res[name]["diagnostic"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
 d=choose(res,baseline);w=d["winner"] or "c210_n20";b1=res[w];report["cycles"].append({"cycle":210,"candidates":res,"winner":w,"ranking":d["ranking"],"guards":d["guards"]})
 res={}
 for name,v in [("c211_d02",.02),("c211_d05",.05),("c211_d10",.10)]:
  res[name]=evaluate(name,"density",v,.75,root/"cycle211");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"],"diag":res[name]["diagnostic"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
 d=choose(res,b1);w=d["winner"] or "c211_d05";b2=res[w];report["cycles"].append({"cycle":211,"candidates":res,"winner":w,"ranking":d["ranking"],"guards":d["guards"]})
 res={}
 for name,sup in [("c212_p50",.50),("c212_p75",.75),("c212_p100",1.0)]:
  res[name]=evaluate(name,"periodic",b2["value"],sup,root/"cycle212");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"pedal":res[name]["summary"]["by_group"]["pedal_hat"],"diag":res[name]["diagnostic"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
 d=choose(res,b2);w=d["winner"] or "c212_p75";b3=res[w];report["cycles"].append({"cycle":212,"candidates":res,"winner":w,"ranking":d["ranking"],"guards":d["guards"]})
 best=max([baseline,b1,b2,b3],key=lambda z:z["canonical_score"]["score"]);report["baseline"]=baseline;report["final"]={"winner":"cross-cycle-best","summary":best["summary"],"canonical_score":best["canonical_score"],"mode":best["mode"],"value":best["value"],"rescue":best["rescue"],"diagnostic":best["diagnostic"],"detailed":best["detailed"]}
 (EXP/"results-iterative-pedal-sparse-gate.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n");print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
