"""DrumScribe v2 offline evaluation.

No reference MIDI is consulted until after prediction. This script evaluates three
successive on-device-style algorithms on the five public DruMaster drum stems.
"""
from __future__ import annotations
import argparse, json, math, subprocess, wave
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks, resample_poly

SR, FFT, HOP = 11025, 1024, 110
GROUPS = {
    "kick": (35, 36),
    "snare": (37, 38, 39, 40),
    "hat": (42, 44, 46),
    "tom": (41, 43, 45, 47, 48, 50),
    "crash": (49, 52, 55, 57),
    "ride": (51, 53, 59),
    "other": (58,),
}
ORDER = list(GROUPS)
MIDI_PITCH = {"kick":36,"snare":38,"hat":42,"tom":45,"crash":49,"ride":51,"other":58}


def variable(data, i):
    result = 0
    while True:
        b = data[i]; i += 1
        result = (result << 7) | (b & 127)
        if not b & 128:
            return result, i


def midi_events(path):
    data = Path(path).read_bytes()
    assert data[:4] == b"MThd"
    division = int.from_bytes(data[12:14], "big")
    tracks, pos = [], 8 + int.from_bytes(data[4:8], "big")
    while pos < len(data) and data[pos:pos+4] == b"MTrk":
        size = int.from_bytes(data[pos+4:pos+8], "big")
        end = pos + 8 + size; i = pos + 8; tick = 0; running = 0; notes = []; tempos = []
        while i < end:
            delta, i = variable(data, i); tick += delta
            status = data[i]
            if status & 128: i += 1; running = status
            else: status = running
            if status == 255:
                typ = data[i]; i += 1; n, i = variable(data, i)
                if typ == 81 and n == 3: tempos.append((tick, int.from_bytes(data[i:i+3], "big")))
                i += n
            elif status in (240, 247):
                n, i = variable(data, i); i += n
            else:
                op = status & 240; channel = status & 15
                n = 1 if op in (192, 208) else 2
                pitch = data[i]; velocity = data[i+1] if n == 2 else 0; i += n
                if op == 144 and velocity > 0: notes.append((tick, pitch, channel))
        tracks.append((notes, tempos)); pos = end
    tempos = sorted([t for _, tt in tracks for t in tt] or [(0, 500000)])
    if tempos[0][0] != 0: tempos.insert(0, (0, 500000))
    starts = [0.0]
    for (t, us), (t2, _) in zip(tempos, tempos[1:]):
        starts.append(starts[-1] + (t2-t) * us / 1e6 / division)
    allnotes = [n for ns, _ in tracks for n in ns]
    channels = Counter(c for _, p, c in allnotes if 35 <= p <= 59)
    use_channel = 9 if channels[9] else (channels.most_common(1)[0][0] if channels else 9)
    out = []
    for tick, pitch, channel in allnotes:
        if channel != use_channel: continue
        group = next((g for g,pitches in GROUPS.items() if pitch in pitches), None)
        if group is None: continue
        j = np.searchsorted([t for t,_ in tempos], tick, side="right") - 1
        sec = starts[j] + (tick-tempos[j][0]) * tempos[j][1] / 1e6 / division
        out.append((sec, group, pitch))
    return sorted(out)


def audio(path, seconds=None):
    cmd = ["ffmpeg","-v","error","-i",str(path),"-ac","1","-ar",str(SR)]
    if seconds: cmd += ["-t", str(seconds)]
    cmd += ["-f","f32le","-acodec","pcm_f32le","-"]
    return np.frombuffer(subprocess.check_output(cmd), dtype="<f4").copy()


def spectrum(x):
    x = np.pad(x, (FFT//2, FFT//2))
    frames = np.lib.stride_tricks.sliding_window_view(x, FFT)[::HOP]
    return np.abs(np.fft.rfft(frames*np.hanning(FFT), axis=1)).astype("f4").T


def templates(folder):
    by_group = {g: [] for g in ORDER}
    for group,pitches in GROUPS.items():
        for pitch in pitches:
            p = folder/f"{pitch}.wav"
            if not p.exists(): continue
            with wave.open(str(p)) as w:
                raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("f4")/32768
                raw = raw.reshape(-1, w.getnchannels()).mean(axis=1)
                x = resample_poly(raw, SR, w.getframerate())
            by_group[group].append(spectrum(x[:int(.15*SR)])[:,2:12].mean(axis=1))
    nbin = FFT//2+1
    return np.stack([np.mean(by_group[g],axis=0) if by_group[g] else np.zeros(nbin) for g in ORDER], axis=1)


def features(spec, tmpl):
    rise = np.maximum(spec - np.pad(spec[:,:-2], ((0,0),(2,0))), 0)
    freqs = np.arange(spec.shape[0])*SR/FFT
    bands = [(35,140),(140,900),(900,3000),(3000,5500)]
    flux = np.stack([rise[(freqs>=lo)&(freqs<hi)].sum(axis=0) for lo,hi in bands])
    baseline = median_filter(flux, size=(1,101))
    flux = np.maximum(flux - baseline*.6, 0)
    bandnorm = np.percentile(flux,98,axis=1)[:,None] + 1e-7
    band = flux/bandnorm
    whitening = np.maximum(np.mean(spec,axis=1), np.percentile(np.mean(spec,axis=1),35))
    whitening = np.maximum(whitening,1e-3)**.6
    a = rise/whitening[:,None]
    b = tmpl/whitening[:,None]
    b /= np.linalg.norm(b,axis=0,keepdims=True)+1e-8
    sim = b.T@a
    sim /= np.linalg.norm(a,axis=0,keepdims=True)+1e-8
    return band, sim


def local_floor(s, mult=2.4):
    return np.maximum(median_filter(s,size=201)*mult, 1e-7)


def peaks_for(signal, threshold, distance=.06, prominence=.07):
    floor = np.maximum(threshold, local_floor(signal))
    peaks,_ = find_peaks(signal, distance=max(1,int(distance*SR/HOP)), prominence=prominence)
    return [int(p) for p in peaks if signal[p] >= floor[p]]


def estimate_downbeat_phase(events, bpm, numerator=4, denominator=4):
    if not bpm or bpm <= 0: return 0.0
    beat = 60.0/bpm*4/denominator
    bar = beat*numerator
    if bar <= 0: return 0.0
    weighted=[]
    for e in events:
        w={"crash":3.2,"kick":1.8,"snare":.8,"ride":.2,"hat":.1,"tom":.5,"other":.1}.get(e[1],.1)
        weighted.append((e[0]%bar,w*e[2]))
    if not weighted: return 0.0
    steps=96
    sigma=max(.035, beat*.11)
    best=(float("-inf"),0.0)
    for i in range(steps):
        phase=bar*i/steps
        score=0.0
        for x,w in weighted:
            d=abs(x-phase); d=min(d,bar-d)
            score += w*math.exp(-.5*(d/sigma)**2)
        if score>best[0]: best=(score,phase)
    return best[1]


def downbeat_strength(t,bpm,phase,numerator=4,denominator=4):
    if not bpm or bpm<=0: return 0.0
    beat=60.0/bpm*4/denominator; bar=beat*numerator
    x=(t-phase)%bar; d=min(x,bar-x)
    sigma=max(.04,beat*.13)
    return math.exp(-.5*(d/sigma)**2)


def periodic_support(times, i, bpm):
    if len(times)<3 or not bpm: return 0.0
    beat=60.0/bpm
    t=times[i]; best=0.0
    for step in (beat/2, beat, beat*2):
        count=0
        for k in (-2,-1,1,2):
            target=t+k*step
            if any(abs(x-target)<=.07 for x in times): count+=1
        best=max(best,count/4)
    return best


def acoustic_candidates(band, sim):
    onset = np.maximum.reduce([band[0]*1.05, band[1], band[2]*.72, band[3]*.72])
    raw = peaks_for(onset, .20, distance=.045, prominence=.055)
    idx={g:i for i,g in enumerate(ORDER)}
    events=[]
    for p in raw:
        b0,b1,b2,b3=(float(band[k,p]) for k in range(4))
        sm={g:float(sim[idx[g],p]) for g in ORDER}
        kick = 1.15*b0 + .55*sm["kick"] - .28*b2
        snare = .92*b1 + .38*b2 + .62*sm["snare"] - .48*max(0,b0-b1)
        hat = .92*b3 + .66*sm["hat"] - .22*b0
        tom = .78*b1 + .58*sm["tom"] - .22*b3
        crash = .82*b2 + .72*b3 + .90*sm["crash"] - .18*b0
        ride = .58*b2 + .88*b3 + 1.02*sm["ride"] - .12*b0
        if kick >= .82 and b0 >= .38:
            events.append((p*HOP/SR,"kick",kick))
        snare_ratio=b1/(b0+1e-6)
        if snare >= 1.00 and (snare_ratio>=.92 or sm["snare"]>=.48):
            if not (kick>=.82 and b0>=.38) or snare>=kick*1.02 or sm["snare"]>=.56:
                events.append((p*HOP/SR,"snare",snare))
        if hat >= .83 and b3 >= .18 and sm["hat"]>=.16:
            events.append((p*HOP/SR,"hat",hat))
        if tom >= 1.18 and sm["tom"]>=.42 and b1>=.45:
            events.append((p*HOP/SR,"tom",tom))
        if crash >= 1.18 and sm["crash"]>=.34:
            events.append((p*HOP/SR,"crash",crash))
        if ride >= 1.02 and sm["ride"]>=.31:
            events.append((p*HOP/SR,"ride",ride))
    return sorted(events)


def postprocess(events,bpm,num,den,round_id):
    if round_id==1: return events
    phase=estimate_downbeat_phase(events,bpm,num,den)
    ride_times=[t for t,g,s in events if g=="ride"]
    ride_index={t:i for i,t in enumerate(ride_times)}
    out=[]
    for t,g,s in events:
        if g=="crash":
            db=downbeat_strength(t,bpm,phase,num,den)
            if db>=.34 or s>=2.25: out.append((t,g,s*(1+.4*db)))
        elif g=="ride":
            per=periodic_support(ride_times,ride_index[t],bpm)
            if per>=.25 or s>=1.75: out.append((t,g,s*(1+.25*per)))
        else:
            out.append((t,g,s))
    if round_id==2: return sorted(out)

    by=defaultdict(list)
    for e in out: by[e[1]].append(e)
    final=[]
    for g,arr in by.items():
        arr=sorted(arr)
        if g=="crash":
            last=-999
            for e in arr:
                if e[0]-last < .32 and e[2] < 2.65: continue
                final.append(e); last=e[0]
        elif g=="snare":
            ts=[x[0] for x in arr]
            for e in arr:
                near=sum(abs(t-e[0])<2.2 for t in ts)-1
                if e[2]<1.12 and near==0: continue
                final.append(e)
        else:
            final.extend(arr)
    return sorted(final)


def score(pred, truth, shift=0, tol=.08):
    totals=Counter(); hits=Counter(); errors=[]
    for group in ORDER:
        a=np.array([t for t,g,*_ in pred if g==group])
        b=np.array([t+shift for t,g,*_ in truth if g==group])
        totals[group]=(len(a),len(b))
        if not len(a) or not len(b): continue
        used=set()
        for x in a:
            j=np.searchsorted(b,x)
            options=[k for k in (j-1,j,j+1) if 0<=k<len(b) and k not in used]
            if options:
                k=min(options,key=lambda k:abs(x-b[k]))
                if abs(x-b[k])<=tol:
                    hits[group]+=1;used.add(k);errors.append(x-b[k])
    tp=sum(hits.values());n=sum(v[0] for v in totals.values());m=sum(v[1] for v in totals.values())
    return dict(tp=tp,predicted=n,reference=m,
                precision=round(tp/n,3) if n else 0, recall=round(tp/m,3) if m else 0,
                f1=round(2*tp/(n+m),3) if n+m else 0,
                by_group={g:dict(tp=hits[g],predicted=totals[g][0],reference=totals[g][1]) for g in ORDER},
                median_error=round(float(np.median(errors)),3) if errors else None)


def confusion(pred, truth, shift=0, tol=.08):
    truth_by=[(t+shift,g) for t,g,*_ in truth]
    matrix={g:{h:0 for h in ORDER+["none"]} for g in ORDER}
    unmatched_pred=Counter()
    for pt,pg,*_ in pred:
        near=[(abs(pt-tt),tg) for tt,tg in truth_by if abs(pt-tt)<=tol]
        if not near:
            unmatched_pred[pg]+=1
            continue
        _,tg=min(near,key=lambda z:z[0]); matrix[tg][pg]+=1
    for tt,tg in truth_by:
        if not any(abs(pt-tt)<=tol for pt,*_ in pred): matrix[tg]["none"]+=1
    ks_dupes=0
    kicks=[t for t,g,*_ in pred if g=="kick"]; snares=[t for t,g,*_ in pred if g=="snare"]
    for t in kicks:
        if any(abs(s-t)<=.04 for s in snares): ks_dupes+=1
    return {"matrix":matrix,"unmatched_predicted":dict(unmatched_pred),"kick_snare_same_onset":ks_dupes}


def count_ratios(score_obj):
    return {g:(round(d["predicted"]/d["reference"],3) if d["reference"] else None)
            for g,d in score_obj["by_group"].items()}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args();root=args.repo_root
    tmpl=templates(root/"DruMaster/assets/drums")
    results={"schema":2,"description":"Three full validation passes; truth MIDI is used only for scoring."}
    all_summary={str(r):Counter() for r in (1,2,3)}
    for folder in sorted((root/"DruMaster/songs").iterdir()):
        meta_path=folder/"song.json"
        if not meta_path.exists() or not (folder/"drums.mp3").exists() or not (folder/"chart.mid").exists(): continue
        if folder.name not in {"arcaround","diamondvirgin","kaiju","nanairo","ray"}: continue
        meta=json.loads(meta_path.read_text())
        bpm=float(meta.get("bpm") or 0)
        ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
        num=int(ts.get("numerator",4)); den=int(ts.get("denominator",4))
        shift=meta["playback"]["stemOffsetSec"]+meta["playback"].get("midiOffsetSec",0)
        x=audio(folder/"drums.mp3"); spec=spectrum(x); band,sim=features(spec,tmpl)
        truth=midi_events(folder/"chart.mid")
        songres={"bpm":bpm,"time_signature":[num,den],"reference_total":len(truth),"rounds":{}}
        base=acoustic_candidates(band,sim)
        for rid in (1,2,3):
            pred=postprocess(base,bpm,num,den,rid)
            sc=score(pred,truth,shift); cf=confusion(pred,truth,shift)
            sc["count_ratio"]=count_ratios(sc); sc["confusion"]=cf
            songres["rounds"][str(rid)]=sc
            all_summary[str(rid)].update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                                         kick_snare_same_onset=cf["kick_snare_same_onset"])
            for g,d in sc["by_group"].items():
                all_summary[str(rid)][f"{g}_tp"]+=d["tp"]
                all_summary[str(rid)][f"{g}_pred"]+=d["predicted"]
                all_summary[str(rid)][f"{g}_ref"]+=d["reference"]
        results[folder.name]=songres
        print(folder.name,{r:songres["rounds"][str(r)]["f1"] for r in (1,2,3)},flush=True)
    results["summary"]={}
    for rid,c in all_summary.items():
        tp,n,m=c["tp"],c["predicted"],c["reference"]
        q={"tp":tp,"predicted":n,"reference":m,
           "precision":round(tp/n,3) if n else 0,
           "recall":round(tp/m,3) if m else 0,
           "f1":round(2*tp/(n+m),3) if n+m else 0,
           "kick_snare_same_onset":c["kick_snare_same_onset"],"by_group":{}}
        for g in ORDER:
            a,b,d=c[f"{g}_tp"],c[f"{g}_pred"],c[f"{g}_ref"]
            q["by_group"][g]={"tp":a,"predicted":b,"reference":d,
                              "count_ratio":round(b/d,3) if d else None}
        results["summary"][rid]=q
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n")


if __name__=="__main__":
    main()
