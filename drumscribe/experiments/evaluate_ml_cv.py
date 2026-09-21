"""DrumScribe Round 4: leave-one-song-out lightweight ML evaluation.

Each held-out song is never used for fitting. MIDI labels are used for training
on the other four songs and for scoring the held-out prediction only.
"""
import json, math, subprocess, wave
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks, resample_poly
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

SR, FFT, HOP = 11025, 1024, 110
SONGS = ["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS = {
 "kick":(35,36),"snare":(37,38,39,40),"hat":(42,44,46),
 "tom":(41,43,45,47,48,50),"crash":(49,52,55,57),"ride":(51,53,59)
}
ORDER=list(GROUPS)

def varlen(data,i):
    v=0
    while True:
        b=data[i]; i+=1; v=(v<<7)|(b&127)
        if not b&128:return v,i

def midi_events(path):
    d=Path(path).read_bytes(); div=int.from_bytes(d[12:14],"big")
    pos=8+int.from_bytes(d[4:8],"big"); tracks=[]
    while pos<len(d) and d[pos:pos+4]==b"MTrk":
        end=pos+8+int.from_bytes(d[pos+4:pos+8],"big"); i=pos+8; tick=0; run=0; ns=[]; ts=[]
        while i<end:
            dt,i=varlen(d,i); tick+=dt; st=d[i]
            if st&128:i+=1;run=st
            else:st=run
            if st==255:
                typ=d[i];i+=1;n,i=varlen(d,i)
                if typ==81 and n==3:ts.append((tick,int.from_bytes(d[i:i+3],"big")))
                i+=n
            elif st in (240,247):
                n,i=varlen(d,i);i+=n
            else:
                op=st&240; ch=st&15; n=1 if op in (192,208) else 2
                p=d[i]; vel=d[i+1] if n==2 else 0;i+=n
                if op==144 and vel>0:ns.append((tick,p,ch))
        tracks.append((ns,ts));pos=end
    tempos=sorted([x for _,tt in tracks for x in tt] or [(0,500000)])
    if tempos[0][0]!=0:tempos.insert(0,(0,500000))
    starts=[0.]
    for (t,us),(t2,_) in zip(tempos,tempos[1:]):starts.append(starts[-1]+(t2-t)*us/1e6/div)
    alln=[x for ns,_ in tracks for x in ns]; cc=Counter(c for _,p,c in alln if 35<=p<=59)
    ch=9 if cc[9] else cc.most_common(1)[0][0]
    out=[]
    tt=[t for t,_ in tempos]
    for tick,p,c in alln:
        if c!=ch:continue
        g=next((g for g,ps in GROUPS.items() if p in ps),None)
        if not g:continue
        j=np.searchsorted(tt,tick,side="right")-1
        sec=starts[j]+(tick-tempos[j][0])*tempos[j][1]/1e6/div
        out.append((sec,g,p))
    return sorted(out)

def audio(path):
    cmd=["ffmpeg","-v","error","-i",str(path),"-ac","1","-ar",str(SR),"-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd),dtype="<f4").copy()

def spectrum(x):
    x=np.pad(x,(FFT//2,FFT//2))
    fr=np.lib.stride_tricks.sliding_window_view(x,FFT)[::HOP]
    return np.abs(np.fft.rfft(fr*np.hanning(FFT),axis=1)).astype("f4").T

def templates(folder):
    out={g:[] for g in ORDER}
    for g,ps in GROUPS.items():
        for p in ps:
            f=folder/f"{p}.wav"
            if not f.exists():continue
            with wave.open(str(f)) as w:
                a=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").astype("f4")/32768
                a=a.reshape(-1,w.getnchannels()).mean(axis=1)
                a=resample_poly(a,SR,w.getframerate())
            out[g].append(spectrum(a[:int(.15*SR)])[:,2:12].mean(axis=1))
    return np.stack([np.mean(out[g],axis=0) if out[g] else np.zeros(FFT//2+1) for g in ORDER],axis=1)

def features(spec,tmpl):
    rise=np.maximum(spec-np.pad(spec[:,:-2],((0,0),(2,0))),0)
    freqs=np.arange(spec.shape[0])*SR/FFT
    edges=[(35,140),(140,900),(900,3000),(3000,5500)]
    flux=np.stack([rise[(freqs>=a)&(freqs<b)].sum(axis=0) for a,b in edges])
    base=median_filter(flux,size=(1,101)); flux=np.maximum(flux-.6*base,0)
    band=flux/(np.percentile(flux,98,axis=1)[:,None]+1e-7)
    white=np.maximum(np.mean(spec,axis=1),np.percentile(np.mean(spec,axis=1),35))
    white=np.maximum(white,1e-3)**.6
    A=rise/white[:,None]; B=tmpl/white[:,None]; B/=np.linalg.norm(B,axis=0,keepdims=True)+1e-8
    sim=B.T@A; sim/=np.linalg.norm(A,axis=0,keepdims=True)+1e-8
    return band,sim

def candidates(band):
    onset=np.maximum.reduce([band[0],band[1],band[2]*.7,band[3]*.7])
    floor=np.maximum(.12,median_filter(onset,size=201)*1.8)
    ps,_=find_peaks(onset,distance=max(1,int(.035*SR/HOP)),prominence=.035)
    return [int(p) for p in ps if onset[p]>=floor[p]]

def vector(band,sim,p):
    b=[float(band[i,p]) for i in range(4)]
    s=[float(sim[i,p]) for i in range(len(ORDER))]
    ratios=[
      b[0]/(b[1]+1e-5),b[1]/(b[0]+1e-5),
      b[2]/(b[3]+1e-5),b[3]/(b[2]+1e-5),
      (b[0]+b[1])/(b[2]+b[3]+1e-5)
    ]
    local=[]
    for a in band:
        lo=max(0,p-3);hi=min(len(a),p+4)
        local.extend([float(np.mean(a[lo:hi])),float(np.max(a[lo:hi]))])
    return np.array(b+s+ratios+local,dtype="f4")

def phase_strength(t,bpm,num=4,den=4,phase=0):
    beat=60/bpm*4/den;bar=beat*num;x=(t-phase)%bar;d=min(x,bar-x)
    return math.exp(-.5*(d/max(.04,beat*.13))**2)

def infer_phase(times,weights,bpm,num=4,den=4):
    beat=60/bpm*4/den;bar=beat*num;best=(-1,0)
    for k in range(96):
        ph=bar*k/96;sc=0
        for t,w in zip(times,weights):
            x=(t-ph)%bar;d=min(x,bar-x);sc+=w*math.exp(-.5*(d/max(.04,beat*.13))**2)
        if sc>best[0]:best=(sc,ph)
    return best[1]

def periodic(times,i,bpm):
    if len(times)<3:return 0
    t=times[i];best=0
    for step in (30/bpm,60/bpm,120/bpm):
        n=0
        for k in (-2,-1,1,2):
            if any(abs(x-(t+k*step))<=.07 for x in times):n+=1
        best=max(best,n/4)
    return best

def build_song(root,name,tmpl):
    f=root/"DruMaster/songs"/name; meta=json.loads((f/"song.json").read_text())
    shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
    truth=midi_events(f/"chart.mid")
    spec=spectrum(audio(f/"drums.mp3"));band,sim=features(spec,tmpl);ps=candidates(band)
    X=np.stack([vector(band,sim,p) for p in ps])
    Y=np.zeros((len(ps),len(ORDER)),dtype="i1")
    for i,p in enumerate(ps):
        t=p*HOP/SR
        for j,g in enumerate(ORDER):
            if any(tol<=.08 for tol in [abs(t-(tt+shift)) for tt,gg,*_ in truth if gg==g]):
                Y[i,j]=1
    return dict(name=name,meta=meta,shift=shift,truth=truth,ps=ps,X=X,Y=Y,band=band,sim=sim)

def fit_binary(X,y):
    # Guard against a fold lacking a rare class.
    if y.min()==y.max():return None,float(y[0])
    m=LogisticRegression(max_iter=500,class_weight="balanced",C=.7,solver="liblinear")
    m.fit(X,y);return m,None

def predict_fold(train,test):
    scaler=StandardScaler().fit(np.concatenate([x["X"] for x in train]))
    Xt=np.concatenate([x["X"] for x in train]);Xt=scaler.transform(Xt)
    Yt=np.concatenate([x["Y"] for x in train])
    Xh=scaler.transform(test["X"])
    probs=np.zeros((len(Xh),len(ORDER)))
    for j,g in enumerate(ORDER):
        m,const=fit_binary(Xt,Yt[:,j])
        probs[:,j]=const if m is None else m.predict_proba(Xh)[:,1]

    times=np.array(test["ps"])*HOP/SR
    # audio-only bar phase estimated from kick/crash probabilities
    weights=1.8*probs[:,0]+3.0*probs[:,4]
    meta=test["meta"];bpm=float(meta["bpm"]);ts=meta.get("timeSignature",{"numerator":4,"denominator":4})
    num=int(ts.get("numerator",4));den=int(ts.get("denominator",4))
    phase=infer_phase(times,weights,bpm,num,den)
    high_times=[float(t) for t,p in zip(times,probs) if max(p[2],p[4],p[5])>.28]

    pred=[]
    for i,t in enumerate(times):
        pk,ps,ph,pt,pc,pr=probs[i]
        # kick/snare arbitration: layered output requires high independent confidence.
        if pk>=.52 and (pk>=ps*.92 or ps<.68):pred.append((float(t),"kick",pk))
        if ps>=.55:
            if pk<.52 or ps>=pk*1.12 or (ps>=.76 and pk>=.62):
                pred.append((float(t),"snare",ps))
        if ph>=.55:pred.append((float(t),"hat",ph))
        if pt>=.68:pred.append((float(t),"tom",pt))

        db=phase_strength(float(t),bpm,num,den,phase)
        per=0
        if high_times:
            k=min(range(len(high_times)),key=lambda q:abs(high_times[q]-t));per=periodic(high_times,k,bpm)
        # User-specified prior: crash strongly favors measure heads.
        if pc>=.48 and (db>=.38 or pc>=.82):pred.append((float(t),"crash",pc*(1+.35*db)))
        if pr>=.52 and per>=.50 and pr>=ph*.92:pred.append((float(t),"ride",pr*(1+.2*per)))
    return sorted(pred),probs,scaler

def score(pred,truth,shift,tol=.08):
    by={};tp=0
    for g in ORDER:
        a=[t for t,gg,*_ in pred if gg==g];b=[t+shift for t,gg,*_ in truth if gg==g];used=set();hit=0
        for x in a:
            opts=[k for k,y in enumerate(b) if k not in used and abs(x-y)<=tol]
            if opts:k=min(opts,key=lambda k:abs(x-b[k]));used.add(k);hit+=1
        by[g]={"tp":hit,"predicted":len(a),"reference":len(b),"count_ratio":round(len(a)/len(b),3) if b else None};tp+=hit
    n=len(pred);m=sum(x["reference"] for x in by.values())
    return {"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,3) if n else 0,
      "recall":round(tp/m,3) if m else 0,"f1":round(2*tp/(n+m),3) if n+m else 0,"by_group":by}

def confusion(pred,truth,shift,tol=.08):
    tr=[(t+shift,g) for t,g,*_ in truth];err=Counter()
    for t,g,*_ in pred:
        if any(gg==g and abs(t-tt)<=tol for tt,gg in tr):continue
        near=[(abs(t-tt),gg) for tt,gg in tr if abs(t-tt)<=tol]
        if near:err[f"{min(near)[1]}_to_{g}"]+=1
    return {"kick_to_snare":err["kick_to_snare"],"snare_to_kick":err["snare_to_kick"],"class_errors":dict(err)}

def main():
    root=Path(".");tmpl=templates(root/"DruMaster/assets/drums")
    data={s:build_song(root,s,tmpl) for s in SONGS}
    out={"schema":1,"formal_round":4,"method":"leave-one-song-out logistic multi-label classifier + musical priors","songs":{}}
    total=Counter()
    for held in SONGS:
        pred,_,_=predict_fold([data[s] for s in SONGS if s!=held],data[held])
        sc=score(pred,data[held]["truth"],data[held]["shift"]);cf=confusion(pred,data[held]["truth"],data[held]["shift"]);sc["confusion"]=cf
        out["songs"][held]=sc
        total.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
        for g,d in sc["by_group"].items():
            for k in ("tp","predicted","reference"):total[f"{g}_{k}"]+=d[k]
        print(held,sc["f1"],cf,flush=True)
    tp,n,m=total["tp"],total["predicted"],total["reference"]
    out["summary"]={"tp":tp,"predicted":n,"reference":m,"precision":round(tp/n,3),"recall":round(tp/m,3),"f1":round(2*tp/(n+m),3),
      "kick_to_snare":total["kick_to_snare"],"snare_to_kick":total["snare_to_kick"],"by_group":{}}
    for g in ORDER:
        a,b,c=total[f"{g}_tp"],total[f"{g}_predicted"],total[f"{g}_reference"]
        out["summary"]["by_group"][g]={"tp":a,"predicted":b,"reference":c,"count_ratio":round(b/c,3) if c else None}
    Path("drumscribe/experiments/results-v2-round4-ml.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")

if __name__=="__main__":main()
