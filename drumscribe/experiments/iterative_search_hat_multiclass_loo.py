"""Cycles 213-215: multi-class reclassification of remaining predicted hat events.

Base: adaptive hat winner c207_r15.

For each held-out song, a classifier is trained on the other four songs.
Training labels are nearest chart class within 80 ms, but chart.mid from the
held-out song is never used for prediction.

Prediction classes: hat / kick / snare / tom / crash / ride / pedal_hat / drop.
Only existing hat onsets are reclassified; no new onset times are invented.

Cycle 213: multinomial logistic / RandomForest / ExtraTrees.
Cycle 214: confidence thresholds .55 / .70 / .85.
Cycle 215: target-policy variants:
  metal_only = only crash/ride reclassification, otherwise keep hat
  metal_kick = crash/ride/kick
  full = all target classes + drop

All candidates write real MIDI, are re-read, then scored on all parts/songs.
"""
from __future__ import annotations
import importlib.util,json,math,subprocess
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier,RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=["kick","snare","hat","pedal_hat","tom","crash","ride","other"]
LABELS=["hat","kick","snare","tom","crash","ride","pedal_hat","drop"]
HANDS={"snare","hat","tom","crash","ride"}
BASE=EXP/"generated-search-hat-adaptive-v2/cycle207/c207_r15"
BROWSER=EXP/"generated-v2-browser";SR=44100;NFFT=2048

def loadmod(name,path):
 sp=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
ev=loadmod("ev",EXP/"evaluate_v2.py");base=loadmod("base",EXP/"iterative_search.py")
detail=loadmod("detail",EXP/"detailed_metrics.py");sel=loadmod("sel",EXP/"selection_policy.py")

def audio(s):
 cmd=["ffmpeg","-v","error","-i",str(ROOT/"DruMaster/songs"/s/"drums.mp3"),"-ac","1","-ar",str(SR),"-f","f32le","-acodec","pcm_f32le","-"]
 return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()
def rows(s):return [(t,g) for t,g,*_ in ev.midi_events(BASE/f"{s}.mid")]
def side(s):return json.loads((BROWSER/f"{s}.json").read_text())
def meta(s):return json.loads((ROOT/"DruMaster/songs"/s/"song.json").read_text())
def truth(s):
 m=meta(s);sh=float(m["playback"]["stemOffsetSec"])+float(m["playback"].get("midiOffsetSec",0))
 return [(t+sh,g) for t,g,*_ in ev.midi_events(ROOT/"DruMaster/songs"/s/"chart.mid")]
def near(xs,t,w):return any(abs(x-t)<=w for x in xs)
def nearest(xs,t):return min((abs(x-t) for x in xs),default=9.)

def periodic(xs,t,bpm):
 best=0.
 for st in (30/bpm,60/bpm,120/bpm):
  n=sum(any(abs(x-(t+k*st))<=.06 for x in xs) for k in (-2,-1,1,2));best=max(best,n/4)
 return best

def spectral(x,t):
 c=int(round(t*SR))
 def fr(cc):
  lo=cc-NFFT//2;hi=lo+NFFT;z=np.zeros(NFFT,np.float32);a=max(0,lo);b=min(len(x),hi)
  if b>a:z[a-lo:b-lo]=x[a:b]
  return z*np.hanning(NFFT)
 cur=fr(c);pre=fr(c-int(.025*SR));S=np.abs(np.fft.rfft(cur))+1e-9;P=np.abs(np.fft.rfft(pre))+1e-9
 f=np.fft.rfftfreq(NFFT,1/SR);tot=float(S.sum())+1e-9;pt=float(P.sum())+1e-9;out=[]
 for lo,hi in [(30,150),(150,500),(500,1500),(1500,3500),(3500,7000),(7000,12000),(12000,20000)]:
  m=(f>=lo)&(f<hi);e=float(S[m].sum())/tot;pe=float(P[m].sum())/pt
  out += [math.log1p(100*e),math.log1p(100*max(0,e-pe))]
 cent=float((f*S).sum()/tot)/22050;flat=float(np.exp(np.mean(np.log(S)))/(np.mean(S)+1e-9))
 rms=float(np.sqrt(np.mean(cur*cur))+1e-9);crest=float(np.max(np.abs(cur))/(rms+1e-9))
 return out+[cent,flat,math.log1p(1000*rms),crest/10]

def feature(x,t,rr,sd):
 bpm=float(sd["bpm"]);phase=float(sd["barPhaseSec"]);beat=60/bpm;bar=4*beat
 by={g:sorted(q for q,gg in rr if gg==g) for g in GROUPS};h=by["hat"];i=min(range(len(h)),key=lambda k:abs(h[k]-t))
 prev=t-h[i-1] if i>0 else 9.;nxt=h[i+1]-t if i+1<len(h) else 9.;pos=((t-phase)%bar)/bar*16
 return np.asarray(spectral(x,t)+[
  min(nearest(by["kick"],t),.25)/.25,min(nearest(by["snare"],t),.25)/.25,min(nearest(by["tom"],t),.25)/.25,
  min(nearest(by["crash"],t),.25)/.25,min(nearest(by["ride"],t),.25)/.25,min(nearest(by["pedal_hat"],t),.25)/.25,
  float(near(by["kick"],t,.025)),float(near(by["kick"],t,.045)),float(near(by["snare"],t,.045)),
  min(prev,.5)/.5,min(nxt,.5)/.5,periodic(h,t,bpm),
  min(abs(pos-round(pos)),.5)*2,float(int(round(pos))%16 in (0,4,8,12)),
  math.sin(2*math.pi*pos/16),math.cos(2*math.pi*pos/16)
 ],np.float32)

def label_for(t,tr):
 cand=[(abs(t-tt),g) for tt,g in tr if abs(t-tt)<=.080 and g in LABELS[:-1]]
 if not cand:return "drop"
 return min(cand,key=lambda z:(z[0],LABELS.index(z[1])))[1]

def prepare():
 d={}
 for s in SONGS:
  print("FEATURES",s,flush=True);x=audio(s);rr=rows(s);sd=side(s);tr=truth(s);h=sorted(t for t,g in rr if g=="hat")
  X=np.stack([feature(x,t,rr,sd) for t in h]) if h else np.zeros((0,34),np.float32)
  y=np.asarray([LABELS.index(label_for(t,tr)) for t in h],np.int16)
  d[s]={"rows":rr,"side":sd,"hats":h,"X":X,"y":y,"labelCounts":dict(Counter(LABELS[i] for i in y))}
 return d

class Model:
 def __init__(self,fam):self.fam=fam;self.scaler=None;self.model=None
 def fit(self,X,y):
  if self.fam=="logistic":
   self.scaler=StandardScaler().fit(X);X=self.scaler.transform(X)
   self.model=LogisticRegression(max_iter=1000,class_weight="balanced",C=.55,solver="lbfgs").fit(X,y)
  elif self.fam=="rf":
   self.model=RandomForestClassifier(n_estimators=280,max_depth=13,min_samples_leaf=3,class_weight="balanced_subsample",random_state=213,n_jobs=-1).fit(X,y)
  else:
   self.model=ExtraTreesClassifier(n_estimators=300,max_depth=13,min_samples_leaf=3,class_weight="balanced",random_state=215,n_jobs=-1).fit(X,y)
  return self
 def predict(self,X):
  if self.scaler is not None:X=self.scaler.transform(X)
  p=self.model.predict_proba(X);out=np.zeros((len(X),len(LABELS)))
  for j,c in enumerate(self.model.classes_):out[:,int(c)]=p[:,j]
  return out

def train(d,held,fam):
 X=np.concatenate([d[s]["X"] for s in SONGS if s!=held]);y=np.concatenate([d[s]["y"] for s in SONGS if s!=held])
 return Model(fam).fit(X,y)

def enforce(rr):
 ded=[]
 for g in GROUPS:
  arr=sorted(t for t,gg in rr if gg==g);last=-999.;md=.035 if g in ("snare","hat","ride") else .05 if g in ("tom","pedal_hat") else .08 if g=="crash" else .04
  for t in arr:
   if t-last>=md:ded.append((t,g));last=t
 ded=sorted(ded);out=[];i=0;pri={"snare":.95,"tom":.88,"crash":.88,"ride":.82,"hat":.62}
 while i<len(ded):
  t=ded[i][0];j=i
  while j<len(ded) and ded[j][0]-t<=.033:j+=1
  c=ded[i:j];ex=[z for z in c if z[1] not in HANDS];h=[z for z in c if z[1] in HANDS]
  h=sorted(h,key=lambda z:pri.get(z[1],.5),reverse=True)[:2];out.extend(ex+h);i=j
 return sorted(out)

def allowed(policy):
 if policy=="metal_only":return {"crash","ride"}
 if policy=="metal_kick":return {"crash","ride","kick"}
 return {"crash","ride","kick","snare","tom","pedal_hat","drop"}

def build(d,p,thr,policy):
 targets=allowed(policy);out=[z for z in d["rows"] if z[1]!="hat"]
 existing={g:sorted(t for t,gg in out if gg==g) for g in GROUPS}
 for i,t in enumerate(d["hats"]):
  j=int(np.argmax(p[i]));lab=LABELS[j];conf=float(p[i,j])
  if conf<thr or lab=="hat" or lab not in targets:
   out.append((t,"hat"));continue
  if lab=="drop":continue
  # If that target already exists at the onset, just remove the redundant hat.
  if not near(existing.get(lab,[]),t,.030):
   out.append((t,lab));existing.setdefault(lab,[]).append(t)
 return enforce(out)

def write(path,rr,bpm):base.write_midi(path,[{"time":t,"group":g,"score":1.0,"confidence":1.0} for t,g in rr],bpm)

def evaluate(name,d,fam,thr,policy,outdir):
 result={"family":fam,"threshold":thr,"policy":policy,"songs":{},"diagnostic":{}};tot=Counter()
 for held in SONGS:
  m=train(d,held,fam);p=m.predict(d[held]["X"]);rr=build(d[held],p,thr,policy)
  predlabels=Counter(LABELS[int(np.argmax(z))] for z in p if float(np.max(z))>=thr)
  result["diagnostic"][held]={"trainingExcluded":held,"sourceLabels":d[held]["labelCounts"],"predictedLabels":dict(predlabels)}
  q=outdir/name/f"{held}.mid";write(q,rr,float(d[held]["side"]["bpm"]))
  pred=ev.midi_events(q);tr=ev.midi_events(ROOT/"DruMaster/songs"/held/"chart.mid");mt=meta(held);sh=float(mt["playback"]["stemOffsetSec"])+float(mt["playback"].get("midiOffsetSec",0))
  sc=ev.score(pred,tr,sh);cf=ev.confusion(pred,tr,sh);sc["confusion"]=cf;sc["count_ratio"]=ev.count_ratios(sc);result["songs"][held]=sc
  tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
  for g,z in sc["by_group"].items():tot[f"{g}_tp"]+=z["tp"];tot[f"{g}_pred"]+=z["predicted"];tot[f"{g}_ref"]+=z["reference"]
 tp,n,r=tot["tp"],tot["predicted"],tot["reference"];sm={"tp":tp,"predicted":n,"reference":r,"precision":tp/n if n else 0,"recall":tp/r if r else 0,"f1":2*tp/(n+r) if n+r else 0,"kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],"two_limb_violations":0,"by_group":{}}
 for g in GROUPS:
  a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"];sf=[]
  for s in SONGS:
   z=result["songs"][s]["by_group"].get(g,{});rr=z.get("reference",0)
   if rr:sf.append(2*z.get("tp",0)/(z.get("predicted",0)+rr) if z.get("predicted",0)+rr else 0)
  sm["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,"recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,"false_discovery_rate":(b-a)/b if b else 0,"miss_rate":(c-a)/c if c else 0,"count_ratio":b/c if c else None,"mean_song_f1":sum(sf)/len(sf) if sf else None,"worst_song_f1":min(sf) if sf else None}
 result["summary"]=sm;result["canonical_score"]=sel.score(sm);result["detailed"]=detail.compare_dir(outdir/name,name)["aggregate"];return result

def choose(res,baseline,targets):
 d=sel.select(res,baseline["summary"],target_parts=targets,max_part_drop=.015,target_tolerance=.006)
 for n in res:res[n]["guard"]=d["guards"][n]
 return d

def main():
 d=prepare();root=EXP/"generated-search-hat-multiclass-loo";report={"schema":1,"cycles":[]}
 # Baseline as very high threshold => all remain hats.
 baseline=evaluate("baseline",d,"logistic",1.01,"full",root/"baseline")
 res={}
 for name,fam in [("c213_logistic","logistic"),("c213_rf","rf"),("c213_extra","extra")]:
  res[name]=evaluate(name,d,fam,.70,"full",root/"cycle213");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"crash":res[name]["summary"]["by_group"]["crash"],"ride":res[name]["summary"]["by_group"]["ride"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
 z=choose(res,baseline,("hat","crash","ride"));w=z["winner"] or "c213_extra";b1=res[w];report["cycles"].append({"cycle":213,"candidates":res,"winner":w,"ranking":z["ranking"],"guards":z["guards"]})
 fam=b1["family"];res={}
 for name,t in [("c214_t55",.55),("c214_t70",.70),("c214_t85",.85)]:
  res[name]=evaluate(name,d,fam,t,"full",root/"cycle214");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"crash":res[name]["summary"]["by_group"]["crash"],"ride":res[name]["summary"]["by_group"]["ride"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
 z=choose(res,b1,("hat","crash","ride"));w=z["winner"] or "c214_t70";b2=res[w];report["cycles"].append({"cycle":214,"candidates":res,"winner":w,"ranking":z["ranking"],"guards":z["guards"]})
 res={}
 for name,p in [("c215_metal","metal_only"),("c215_metal_kick","metal_kick"),("c215_full","full")]:
  res[name]=evaluate(name,d,fam,b2["threshold"],p,root/"cycle215");print("SUMMARY",name,json.dumps({"f1":res[name]["summary"]["f1"],"hat":res[name]["summary"]["by_group"]["hat"],"crash":res[name]["summary"]["by_group"]["crash"],"ride":res[name]["summary"]["by_group"]["ride"],"score":res[name]["canonical_score"]},ensure_ascii=False),flush=True)
 z=choose(res,b2,("hat","crash","ride"));w=z["winner"] or "c215_metal";b3=res[w];report["cycles"].append({"cycle":215,"candidates":res,"winner":w,"ranking":z["ranking"],"guards":z["guards"]})
 best=max([baseline,b1,b2,b3],key=lambda q:q["canonical_score"]["score"]);report["baseline"]=baseline;report["final"]={"winner":"cross-cycle-best","summary":best["summary"],"canonical_score":best["canonical_score"],"family":best["family"],"threshold":best["threshold"],"policy":best["policy"],"diagnostic":best["diagnostic"],"detailed":best["detailed"]}
 (EXP/"results-iterative-hat-multiclass-loo.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n");print("FINAL",json.dumps(report["final"],ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
