from __future__ import annotations
import importlib.util,json,subprocess,math
from pathlib import Path
import numpy as np

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"; D=EXP/"generated-crash-collision-v56"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
SR=44100; NFFT=4096; WIN=np.hanning(NFFT); FREQ=np.fft.rfftfreq(NFFT,1/SR)
spec=importlib.util.spec_from_file_location("ev56",EXP/"evaluate_v2.py");ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def decode(path):
    cmd=["ffmpeg","-v","error","-i",str(path),"-ac","1","-ar",str(SR),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()
def spectrum(x,t,offset):
    center=int(round((t+offset)*SR));lo=center-NFFT//2;fr=np.zeros(NFFT)
    a=max(0,lo);b=min(len(x),lo+NFFT)
    if b>a:fr[a-lo:b-lo]=x[a:b]
    return np.abs(np.fft.rfft(fr*WIN))+1e-12
def rms(x,t,a,b):
    lo=max(0,int((t+a)*SR));hi=min(len(x),int((t+b)*SR))
    return float(np.sqrt(np.mean(x[lo:hi]**2)+1e-12))
def bandsum(sp,lo,hi):return float(sp[(FREQ>=lo)&(FREQ<hi)].sum())
def features(x,t):
    ss={o:spectrum(x,t,o) for o in [0,.012,.04,.08,.18,.35,.5]}
    onset=ss[.012];total=float(onset.sum());cs=np.cumsum(onset)
    rs=[rms(x,t,a,b) for a,b in [(0,.025),(.025,.06),(.06,.12),(.12,.22),(.22,.4),(.4,.65)]]
    r0=max(rs[0],1e-9);oh=bandsum(onset,5000,18000)+1e-12;olm=bandsum(onset,800,5000)+1e-12
    return {
      "centroidHz":float((FREQ*onset).sum()/(total+1e-12)),
      "flatness":float(np.exp(np.mean(np.log(onset)))/(np.mean(onset)+1e-12)),
      "roll85Hz":float(FREQ[np.searchsorted(cs,.85*cs[-1])]),
      "rms0_25":rs[0],
      "rmsRatio25_60":rs[1]/r0,"rmsRatio60_120":rs[2]/r0,
      "rmsRatio120_220":rs[3]/r0,"rmsRatio220_400":rs[4]/r0,"rmsRatio400_650":rs[5]/r0,
      "highTail80":bandsum(ss[.08],5000,18000)/oh,
      "highTail180":bandsum(ss[.18],5000,18000)/oh,
      "highTail350":bandsum(ss[.35],5000,18000)/oh,
      "lowMidTail180":bandsum(ss[.18],800,5000)/olm,
      "highShare":bandsum(onset,5000,18000)/(bandsum(onset,800,18000)+1e-12),
      "bodyShare":bandsum(onset,800,5000)/(bandsum(onset,800,18000)+1e-12)
    }
def truth_crash(song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    return sorted(t+shift for t,g,n in ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid") if n in {49,52,55,57})
def is_true(t,refs):return any(abs(t-r)<=.080 for r in refs)

rows=[]
for song in SONGS:
    side=json.loads((D/f"{song}.json").read_text())
    decisions=side.get("adtofInfo",{}).get("cymbalPolicy",{}).get("crashCompetition",{}).get("decisions",[])
    audio=decode(ROOT/"DruMaster/songs"/song/"drums.mp3");refs=truth_crash(song)
    for d in decisions:
        t=float(d["time"]);f=features(audio,t)
        rows.append({"source":"dru5","song":song,"time":t,"label":1 if is_true(t,refs) else 0,
          "runtime":{k:d.get(k) for k in ["hatGroup","openProbability","templateMargin","baseConfidence","hatGrid16","hatGrid8","regularHatRun","rawCrashSupport"]},
          "features":f})
proof=json.loads((EXP/"proof-review2-crash-features-v56.json").read_text())
rows.append({"source":"proof-review2","song":"proof","time":proof["timing"]["analyzedTransientSec"],"label":0,"runtime":None,"features":proof["features"]})

FEATURES=list(proof["features"].keys())
public=[r for r in rows if r["source"]=="dru5"]
proofrow=next(r for r in rows if r["source"]=="proof-review2")

# Diagnostic single-feature separation. We do not call a rule valid unless it
# keeps every public TP, removes at least one public FP, and also rejects Proof.
def threshold_values(vals):
    a=sorted(set(float(v) for v in vals));out=[]
    if not a:return []
    out.extend(a)
    out.extend((x+y)/2 for x,y in zip(a,a[1:]))
    return sorted(set(out))
single=[]
for key in FEATURES:
    vals=[r["features"][key] for r in rows]
    for direction in ("ge","le"):
        for th in threshold_values(vals):
            keep=lambda r: r["features"][key]>=th if direction=="ge" else r["features"][key]<=th
            tp=sum(r["label"] for r in public if keep(r));tp_total=sum(r["label"] for r in public)
            fp=sum(1-r["label"] for r in public if keep(r));fp_total=sum(1-r["label"] for r in public)
            proof_keep=bool(keep(proofrow))
            single.append({"feature":key,"direction":direction,"threshold":th,
              "publicTP":tp,"publicTPTotal":tp_total,"publicFP":fp,"publicFPTotal":fp_total,"proofKeep":proof_keep,
              "safe":tp==tp_total and fp<fp_total and not proof_keep})
single.sort(key=lambda r:(r["safe"],r["publicTP"],-r["publicFP"],not r["proofKeep"]),reverse=True)

# Three physically distinct hypothesis families, scored with a conservative
# "remove only" condition. Thresholds are explored for diagnosis, not runtime adoption.
hypotheses={}
families={
 "H1_body_decay":["rmsRatio120_220","rmsRatio220_400","lowMidTail180"],
 "H2_high_decay":["highTail80","highTail180","highTail350","highShare"],
 "H3_attack_shape":["centroidHz","flatness","roll85Hz","bodyShare"]
}
for name,keys in families.items():
    cand=[r for r in single if r["feature"] in keys]
    hypotheses[name]=cand[0] if cand else None

out={"schema":1,"date":"2026-09-23","experiment":"collision-only 44.1k crash-vs-hat v56",
 "referencePolicy":"Five-song chart.mid labels are applied only after browser candidate generation. Proof Review 2 is an explicit user-labeled negative and is kept separate from the five-song score.",
 "counts":{"rows":len(rows),"public":len(public),"publicTP":sum(r["label"] for r in public),"publicFP":sum(1-r["label"] for r in public),"proofNegatives":1},
 "rows":rows,"hypotheses":hypotheses,"safeSingleRules":[r for r in single if r["safe"]][:20],"topSingleRules":single[:30]}
(EXP/"results-crash-collision-v56.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"counts":out["counts"],"hypotheses":hypotheses,"safeSingleRules":out["safeSingleRules"][:10]},ensure_ascii=False,indent=2))
