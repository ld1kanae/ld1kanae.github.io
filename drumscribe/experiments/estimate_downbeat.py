"""Audio-only downbeat/bar-head benchmark.

Uses BPM estimator v3, then estimates:
1) beat phase from low/mid drum onset alignment
2) one of four beat positions as the 4/4 bar head

Three bar-position scorers are compared:
A backbeat: snare 2/4 structure + kick contrast
B cymbal_head: strong high-frequency transients at bar starts
C combined: backbeat + kick + sparse crash-like evidence

song.json is used only after prediction to score the bar phase against the
published audio/MIDI synchronization.
"""
from __future__ import annotations
import importlib.util,json,math
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
v1=loadmod("bpm1",EXP/"estimate_bpm.py")
v3=loadmod("bpm3",EXP/"estimate_bpm_v3.py")
FPS=v1.FPS

def sample_max(x,tsec,rsec=.035):
    c=tsec*FPS;r=max(1,int(rsec*FPS));i=int(round(c))
    a=max(0,i-r);b=min(len(x),i+r+1)
    return float(np.max(x[a:b])) if b>a else 0.

def beat_phase(env,band,bpm):
    p=60/bpm
    best=None
    for q in range(128):
        ph=p*q/128
        ts=np.arange(ph,len(env)/FPS,p)
        if len(ts)<8:continue
        low=np.array([sample_max(band[0],t) for t in ts])
        mid=np.array([sample_max(band[1],t) for t in ts])
        allv=np.array([sample_max(env,t) for t in ts])
        vals=.52*np.minimum(low,2.5)+.34*np.minimum(mid,2.5)+.14*np.minimum(allv,2.5)
        score=float(np.mean(vals)+.16*np.mean(vals>np.percentile(vals,45)))
        row={"phase":ph,"score":score}
        if best is None or score>best["score"]:best=row
    return best

def beat_features(env,band,bpm,phase):
    p=60/bpm;duration=len(env)/FPS
    ts=np.arange(phase,duration,p)
    rows=[]
    high=band[2]+band[3]
    for n,t in enumerate(ts):
        rows.append({
          "n":n,"t":t,
          "low":sample_max(band[0],t),
          "mid":sample_max(band[1],t),
          "high":sample_max(high,t),
          "all":sample_max(env,t),
        })
    return rows

def groupvals(rows,offset,key):
    out=[[],[],[],[]]
    for r in rows:
        pos=(r["n"]-offset)%4
        out[pos].append(r[key])
    return [np.asarray(x,float) for x in out]

def mean(a):return float(np.mean(a)) if len(a) else 0.
def q80(a):return float(np.percentile(a,80)) if len(a) else 0.
def topmean(a,frac=.18):
    if not len(a):return 0.
    k=max(1,int(len(a)*frac));return float(np.mean(np.sort(a)[-k:]))

def score_offset(rows,offset,mode):
    lo=groupvals(rows,offset,"low")
    mi=groupvals(rows,offset,"mid")
    hi=groupvals(rows,offset,"high")
    sn_back=(mean(mi[1])+mean(mi[3]))*.5
    sn_front=(mean(mi[0])+mean(mi[2]))*.5
    sn_contrast=(sn_back-sn_front)/(sn_back+sn_front+.12)

    k0=mean(lo[0]);k2=mean(lo[2]);k13=(mean(lo[1])+mean(lo[3]))*.5
    kick_head=(k0-.35*k13)/(k0+k13+.12)
    kick_strong=(k0+.45*k2)

    h0=topmean(hi[0],.20)
    hother=np.mean([topmean(hi[j],.20) for j in (1,2,3)])
    cym_head=(h0-hother)/(h0+hother+.12)

    h80=(q80(hi[0])-np.mean([q80(hi[j]) for j in (1,2,3)]))/(q80(hi[0])+np.mean([q80(hi[j]) for j in (1,2,3)])+.12)

    if mode=="backbeat":
        score=1.30*sn_contrast+.34*kick_head+.10*kick_strong
    elif mode=="cymbal_head":
        score=1.10*cym_head+.45*h80+.34*sn_contrast+.20*kick_head
    else:
        score=1.05*sn_contrast+.52*kick_head+.62*cym_head+.25*h80+.08*kick_strong
    return {"score":float(score),"snare_contrast":float(sn_contrast),
            "kick_head":float(kick_head),"cymbal_head":float(cym_head),"h80":float(h80)}

def estimate_method(env,band,bpm,mode):
    bp=beat_phase(env,band,bpm)
    rows=beat_features(env,band,bpm,bp["phase"])
    opts=[]
    for off in range(4):
        s=score_offset(rows,off,mode)
        bar=4*60/bpm
        ph=(bp["phase"]+off*60/bpm)%bar
        opts.append({"offset":off,"bar_phase_sec":ph,**s})
    opts.sort(key=lambda x:x["score"],reverse=True)
    return {"bpm":bpm,"beat_phase_sec":bp["phase"],"beat_phase_score":bp["score"],
            "bar_phase_sec":opts[0]["bar_phase_sec"],"offset":opts[0]["offset"],"candidates":opts}

def circ_dist(a,b,period):
    d=abs((a-b)%period);return min(d,period-d)

def main():
    report={"schema":1,"description":"Audio-only 4/4 downbeat benchmark; metadata scoring-only.","songs":{}}
    totals={m:[] for m in ("backbeat","cymbal_head","combined")}
    for song in SONGS:
        env,band=v1.onset_envelope(ROOT/"DruMaster/songs"/song/"drums.mp3")
        bpmp=v3.estimate(env,band);bpm=bpmp["bpm"]
        preds={m:estimate_method(env,band,bpm,m) for m in totals}

        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        truth_bpm=float(meta["bpm"]);ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
        num=int(ts.get("numerator",4));den=int(ts.get("denominator",4))
        true_beat=60/truth_bpm*4/den;true_bar=true_beat*num
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        ref_phase=shift%true_bar
        scored={}
        for m,pred in preds.items():
            e=circ_dist(pred["bar_phase_sec"]%true_bar,ref_phase,true_bar)
            scored[m]={"prediction":pred,"error_sec":e,"error_beats":e/true_beat}
            totals[m].append(e/true_beat)
        report["songs"][song]={"truth_bpm":truth_bpm,"predicted_bpm":bpm,
          "reference_bar_phase_sec":ref_phase,"reference_shift_sec":shift,"methods":scored}
        print("DOWNBEAT",song,json.dumps(report["songs"][song],ensure_ascii=False),flush=True)
    report["summary"]={m:{"mean_abs_beats":float(np.mean(v)),"max_abs_beats":float(np.max(v))}
                       for m,v in totals.items()}
    (EXP/"results-downbeat-estimation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("SUMMARY",json.dumps(report["summary"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
