"""Evaluate the externally trained E-GMD K/S/T reclassifier on DruMaster songs.

No DruMaster chart is used to train or set model thresholds. The E-GMD model and
its thresholds are frozen before this transfer test. chart.mid is scoring-only.

Policies:
- baseline: current real-browser MIDI.
- rescue: preserve all current kick/snare/tom; add externally accepted low
  candidates for snare/tom only (kick frozen because baseline is already strong).
- conservative: same rescue, plus remove a current tom only when the external
  classifier rejects it at a strict probability margin.
"""
from __future__ import annotations
import bisect,importlib.util,json,math,subprocess
from collections import Counter
from pathlib import Path
import numpy as np
import torch

from adtof_pytorch import calculate_n_bins,create_frame_rnn_model,get_default_weights_path,load_pytorch_weights
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";BASE=EXP/"generated-v2-browser"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
MODEL=json.loads((ROOT/"drumscribe/models/egmd-kst-reclassifier-v1.json").read_text())
FPS=100;GROUPS=("kick","snare","tom");CI={"kick":0,"snare":1,"tom":2}
LOW_SCALE=float(MODEL["lowScale"]);BASE_THRESH=MODEL["baseThresholds"]
spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py");ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def audio44(path):
    cmd=["ffmpeg","-v","error","-i",str(path),"-ac","1","-ar","44100","-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def frozen():
    n=calculate_n_bins();m=create_frame_rnn_model(n)
    return load_pytorch_weights(m,get_default_weights_path(),strict=False).eval()

def activities(model,processor,audio):
    st=processor.compute_stft(audio);fx=processor.apply_filterbank(st).T.astype(np.float32)[...,None]
    x=torch.from_numpy(fx[None,...]).float()
    with torch.no_grad():
        B,T,F,C=x.shape;z=x.permute(0,3,1,2)
        for block in model.cnn_blocks:z=block(z)
        z=z.permute(0,2,3,1).reshape(B,T,-1)
        if getattr(model,"context_layer",None) is not None:z=model.context_layer(z)
        for gru in model.gru_layers:z,_=gru(z)
        return torch.sigmoid(model.output_layer(z))[0].cpu().numpy().astype(np.float32)

def residual(x,left=10,right=1):
    y=np.empty(len(x),np.float32);size=left+1+right
    for i in range(len(x)):
        s=sum(float(x[max(0,min(len(x)-1,i+d))]) for d in range(-left,right+1))
        y[i]=max(0.,float(x[i])-s/size)
    return y

def residuals(a):return np.stack([residual(a[:,c]) for c in range(5)],axis=1)

def pick(a,r,c,thr):
    p=r[:,c];peaks=[]
    for i in range(len(p)):
        mx=max(float(p[max(0,min(len(p)-1,i+d))]) for d in (-2,-1,0,1))
        if float(p[i])>=mx and float(p[i])>=thr:peaks.append(i)
    if not peaks:return []
    groups=[];cur=[peaks[0]]
    for q in peaks[1:]:
        if q-cur[-1]<=2:cur.append(q)
        else:groups.append(cur);cur=[q]
    groups.append(cur)
    return [max(g,key=lambda i:float(p[i])) for g in groups]

def feat(a,r,fr,c,thr):
    T=len(a);lo=max(0,fr-2);hi=min(T,fr+3);cur=a[fr];res=r[fr]
    vals=np.concatenate([cur,res,a[lo:hi].mean(0),a[lo:hi].max(0)]).astype(np.float32).tolist()
    at=lambda d:float(a[max(0,min(T-1,fr+d)),c])
    other=max(float(np.max(np.delete(cur,c))),1e-5);ro=max(float(np.max(np.delete(res,c))),1e-5)
    vals += [at(-2),at(-1),at(1),at(2),float(cur[c])/other,float(res[c])/ro,
             float(cur[c])/max(thr,1e-5),float(res[c])/max(thr,1e-5)]
    return np.asarray(vals,dtype=np.float64)

def sigmoid(x):
    if x>=0:return 1/(1+math.exp(-x))
    z=math.exp(x);return z/(1+z)

def predict(g,x):
    m=MODEL["models"][g];mean=np.asarray(m["mean"]);scale=np.asarray(m["scale"]);coef=np.asarray(m["coef"])
    z=(x-mean)/np.maximum(scale,1e-12)
    return sigmoid(float(z@coef+float(m["intercept"])))

def candidates(a):
    r=residuals(a);out={g:[] for g in GROUPS}
    for g in GROUPS:
        c=CI[g];thr=float(BASE_THRESH[g])*LOW_SCALE
        for fr in pick(a,r,c,thr):
            out[g].append({"time":fr/FPS,"prob":predict(g,feat(a,r,fr,c,thr)),
                           "activation":float(a[fr,c]),"frame":fr})
    return out

def near(rows,t,w):
    return any(abs(x[0]-t)<=w for x in rows)

def current(song):
    side=json.loads((BASE/f"{song}.json").read_text());off=float(side.get("exportOffsetSec",0) or 0)
    return [(t-off,g) for t,g,*_ in ev.midi_events(BASE/f"{song}.mid")]

def build(song,cand,policy):
    rows=current(song);base={g:sorted((t,g) for t,gg in rows if gg==g) for g in GROUPS}
    out=list(rows);diag={"added":Counter(),"removed":Counter()}
    if policy in ("rescue","conservative"):
        # External thresholds were selected without DruMaster labels.
        for g in ("snare","tom"):
            th=float(MODEL["models"][g]["threshold"])
            for q in cand[g]:
                if q["prob"]<th:continue
                if near(base[g],q["time"],.055):continue
                out.append((q["time"],g));diag["added"][g]+=1
    if policy=="conservative":
        # Only touch tom false-positive candidates with a strong external reject.
        tm=float(MODEL["models"]["tom"]["threshold"])
        keep=[]
        for t,g in out:
            if g!="tom":keep.append((t,g));continue
            q=min(cand["tom"],key=lambda x:abs(x["time"]-t),default=None)
            if q is not None and abs(q["time"]-t)<=.055 and q["prob"]<max(.10,tm-.20):
                diag["removed"]["tom"]+=1
            else:keep.append((t,g))
        out=keep
    return sorted(out),{"added":dict(diag["added"]),"removed":dict(diag["removed"])}

def score(rows,song):
    meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    truth=ev.midi_events(ROOT/"DruMaster/songs"/song/"chart.mid")
    return ev.score([(t,g,0,0) for t,g in rows],truth,shift)

def aggregate(scores):
    tot=Counter()
    for sc in scores.values():
        tot.update(tp=sc["tp"],pred=sc["predicted"],ref=sc["reference"])
        for g,x in sc["by_group"].items():tot.update({f"{g}_tp":x["tp"],f"{g}_pred":x["predicted"],f"{g}_ref":x["reference"]})
    s={"tp":tot["tp"],"predicted":tot["pred"],"reference":tot["ref"],
       "precision":tot["tp"]/tot["pred"],"recall":tot["tp"]/tot["ref"],
       "f1":2*tot["tp"]/(tot["pred"]+tot["ref"]),"by_group":{}}
    for g in ev.ORDER:
        a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
        s["by_group"][g]={"tp":a,"predicted":b,"reference":c,"precision":a/b if b else 0,
          "recall":a/c if c else 0,"f1":2*a/(b+c) if b+c else 0,"count_ratio":b/c if c else None}
    return s

def main():
    model=frozen();processor=create_adtof_processor();cand={}
    for song in SONGS:
        a=activities(model,processor,audio44(ROOT/"DruMaster/songs"/song/"drums.mp3"))
        cand[song]=candidates(a)
        print("CAND",song,{g:(len(cand[song][g]),sum(q["prob"]>=MODEL["models"][g]["threshold"] for q in cand[song][g])) for g in GROUPS},flush=True)

    policies={}
    for p in ("baseline","rescue","conservative"):
        scores={};diag={}
        for song in SONGS:
            rows,dd=build(song,cand[song],p);diag[song]=dd;scores[song]=score(rows,song)
        policies[p]={"summary":aggregate(scores),"songs":scores,"diag":diag}
        s=policies[p]["summary"]
        print("POLICY",p,json.dumps({"overall":s["f1"],"kick":s["by_group"]["kick"],"snare":s["by_group"]["snare"],"tom":s["by_group"]["tom"],"diag":diag},ensure_ascii=False),flush=True)

    base=policies["baseline"]["summary"]
    eligible=[]
    for p in ("rescue","conservative"):
        s=policies[p]["summary"]
        ok=(s["by_group"]["kick"]["f1"]>=base["by_group"]["kick"]["f1"]-.0001
            and s["by_group"]["snare"]["precision"]>=base["by_group"]["snare"]["precision"]-.025
            and s["by_group"]["tom"]["precision"]>=base["by_group"]["tom"]["precision"]-.025
            and (s["by_group"]["snare"]["f1"]+s["by_group"]["tom"]["f1"]>
                 base["by_group"]["snare"]["f1"]+base["by_group"]["tom"]["f1"]))
        if ok:eligible.append(p)
    retained=max(eligible,key=lambda p:(policies[p]["summary"]["by_group"]["snare"]["f1"]+policies[p]["summary"]["by_group"]["tom"]["f1"],policies[p]["summary"]["f1"])) if eligible else "baseline"
    result={"schema":1,"description":"Frozen E-GMD KST reclassifier transfer; DruMaster charts scoring-only.",
      "model":"models/egmd-kst-reclassifier-v1.json","policies":policies,"retained":retained}
    (EXP/"results-egmd-kst-transfer-v1.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("RETAINED",retained,flush=True)

if __name__=="__main__":main()
