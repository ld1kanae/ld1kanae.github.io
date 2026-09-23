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
    "hat": (42, 46),
    "tom": (41, 43, 45, 47, 48, 50),
    "crash": (49, 52, 55, 57),
    "ride": (51, 53, 59),
    "other": (58,),
    # MIDI 44 is foot/pedal hi-hat. Keep it separate so the two-hand
    # polyphony constraint never treats it as a hand-played hi-hat.
    "pedal_hat": (44,),
}
ORDER = list(GROUPS)
MIDI_PITCH = {"kick":36,"snare":38,"hat":42,"tom":45,"crash":49,"ride":51,"other":58,"pedal_hat":44}


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
    """Formal Round 3 acoustic candidates.

    Keep the published band-precision detector intact and defer ambiguous
    kick/snare and high-frequency classification to rhythmic post-processing.
    """
    idx={g:i for i,g in enumerate(ORDER)}
    signals={"kick":band[0],"snare":band[1],"hat":band[3],"tom":band[1],"cymbal":band[2]}
    thresholds={"kick":.58,"snare":.70,"hat":.19,"tom":1.5,"cymbal":1.0}
    distances={"kick":.075,"snare":.075,"hat":.055,"tom":.09,"cymbal":.12}
    raw=[]

    for group in ("kick","snare","hat","tom","cymbal"):
        s=signals[group]
        for p in peaks_for(s,thresholds[group],distance=distances[group],prominence=.07):
            if group=="kick" and band[0,p] < .48*band[1,p]:
                continue
            if group=="snare" and band[1,p] < .62*band[0,p]:
                continue
            if group=="tom":
                if sim[idx["tom"],p] < .44:
                    continue
                if sim[idx["tom"],p] < .85*max(sim[idx["kick"],p],sim[idx["snare"],p]):
                    continue
            if group=="cymbal":
                if max(float(sim[idx["crash"],p]),float(sim[idx["ride"],p])) < .39:
                    continue
                raw.append((p*HOP/SR,"cymbal_raw",float(s[p]),p))
            else:
                raw.append((p*HOP/SR,group,float(s[p]),p))
    return sorted(raw)


def postprocess(events,bpm,num,den,round_id=3,sim=None,band=None):
    idx={g:i for i,g in enumerate(ORDER)}
    beat=60.0/bpm*4/den if bpm else .5
    bar=beat*num
    sigma=max(.035,beat*.15)

    # Estimate a bar phase from common drum roles: kick tends toward strong beats,
    # snare toward backbeats, crash toward the bar head. This is a prior, not a
    # hard rule, and uses no reference MIDI.
    def circ_dist(x,y,period):
        d=abs(x-y)%period
        return min(d,period-d)

    phase_candidates=[e for e in events if e[1] in ("kick","snare","cymbal_raw")]
    best_phase=0.0; best_score=-1.0
    steps=96
    for q in range(steps):
        phase=bar*q/steps
        score0=0.0
        for t,g,s,p in phase_candidates:
            pos=(t-phase)%bar
            if g=="kick":
                targets=[beat*i for i in range(num) if i%2==0] or [0.0]
                w=1.0
            elif g=="snare":
                targets=[beat*i for i in range(num) if i%2==1] or [beat]
                w=1.15
            else:
                targets=[0.0]
                w=.75
            d=min(circ_dist(pos,z,bar) for z in targets)
            score0 += w*min(2.0,math.sqrt(max(s,0)))*math.exp(-.5*(d/sigma)**2)
        if score0>best_score:
            best_score=score0; best_phase=phase

    def beat_info(t):
        pos=(t-best_phase)%bar
        bi=int(round(pos/beat))%num
        target=bi*beat
        d=circ_dist(pos,target,bar)
        return bi,d/beat

    def db_strength(t):
        pos=(t-best_phase)%bar
        d=circ_dist(pos,0.0,bar)
        return math.exp(-.5*(d/max(.04,beat*.14))**2)

    # Resolve kick/snare after bar phase is known.
    keep=[True]*len(events)
    kicks=[i for i,e in enumerate(events) if e[1]=="kick"]
    snares=[i for i,e in enumerate(events) if e[1]=="snare"]
    used=set()
    for ki in kicks:
        kt,kg,ks,kp=events[ki]
        near=[si for si in snares if si not in used and abs(events[si][0]-kt)<=.04]
        if not near: continue
        si=min(near,key=lambda j:abs(events[j][0]-kt)); used.add(si)
        st,sg,sscore,sp=events[si]
        center=(kt+st)/2
        bi,bd=beat_info(center)
        backbeat=(bi%2==1 and bd<=.24)

        b0=float(band[0,kp]); b1=float(band[1,sp])
        kr=b0/(b1+1e-7); sr=b1/(b0+1e-7)
        sk=float(sim[idx["kick"],kp]); ss=float(sim[idx["snare"],sp])

        layered=(sk>=.54 and ss>=.56 and .72<=kr<=1.45 and backbeat)
        if layered:
            continue

        if backbeat:
            # Restore snare on beats 2/4 unless low-frequency evidence is overwhelming.
            keep[si]=True
            if kr>=1.55 and sk>=.42 and ss<sk+.10:
                keep[si]=False
                keep[ki]=True
            else:
                # Kick may coexist only with clear independent low-end evidence.
                keep[ki]=(b0>=.90 and sk>=.46)
        else:
            snare_strong=(sr>=1.60 and ss>=.42) or (ss>=sk+.20 and sr>=1.18)
            if snare_strong:
                keep[ki]=False
            else:
                keep[si]=False

    retained=[e for i,e in enumerate(events) if keep[i]]
    hats=[e for e in retained if e[1]=="hat"]
    cym=[e for e in retained if e[1]=="cymbal_raw"]
    fixed=[e for e in retained if e[1] not in ("hat","cymbal_raw")]

    # Use all high-frequency onsets for periodicity. Candidate-to-index matching is
    # stable because event times are unique enough at the detector's peak distances.
    high=sorted(hats+cym,key=lambda e:e[0])
    high_times=[e[0] for e in high]
    periodic={}
    for i,e in enumerate(high):
        periodic[id(e)]=periodic_support(high_times,i,bpm)

    # Decide whether the song has meaningful ride evidence before reclassifying hats.
    ride_votes=0
    for e in hats:
        t,g,s,p=e
        rs=float(sim[idx["ride"],p]); hs=float(sim[idx["hat"],p])
        per=periodic[id(e)]
        ratio=float(band[2,p])/(float(band[3,p])+1e-7)
        if per>=.50 and rs>=.31 and rs>=hs*1.06 and ratio>=.42:
            ride_votes+=1
    ride_mode=ride_votes>=max(8,int(.025*max(1,len(hats))))

    out=list(fixed)
    consumed_cym=set()

    # Reclassify hats first. Downbeat hats with crash evidence become crash;
    # periodic ride-like hats become ride only when song-level ride evidence exists.
    for hi,e in enumerate(hats):
        t,g,s,p=e
        db=db_strength(t)
        cs=float(sim[idx["crash"],p]); rs=float(sim[idx["ride"],p]); hs=float(sim[idx["hat"],p])
        ratio=float(band[2,p])/(float(band[3,p])+1e-7)
        per=periodic[id(e)]
        nearby=[j for j,x in enumerate(cym) if abs(x[0]-t)<=.045]

        crash_from_hat=(db>=.58 and cs>=.28 and (ratio>=.28 or bool(nearby)))
        ride_from_hat=(ride_mode and db<.55 and per>=.50 and rs>=.31 and rs>=hs*1.06 and ratio>=.42)

        if crash_from_hat:
            out.append((t,"crash",s*(1+.30*db),p))
            consumed_cym.update(nearby)
        elif ride_from_hat:
            out.append((t,"ride",s*(1+.20*per),p))
            consumed_cym.update(nearby)
        else:
            out.append(e)

    # Remaining dedicated cymbal candidates: bar-head crash, periodic ride, or reject.
    for j,e in enumerate(cym):
        if j in consumed_cym: continue
        t,g,s,p=e
        db=db_strength(t); per=periodic[id(e)]
        cs=float(sim[idx["crash"],p]); rs=float(sim[idx["ride"],p]); hs=float(sim[idx["hat"],p])
        crash_ok=(db>=.50 and cs>=.32) or (db>=.12 and s>=1.95 and cs>=.50)
        ride_ok=(ride_mode and db<.60 and per>=.50 and rs>=.32 and rs>=hs*1.04)

        if crash_ok and (not ride_ok or db>=.68):
            out.append((t,"crash",s*(1+.30*db),p))
        elif ride_ok:
            out.append((t,"ride",s*(1+.20*per),p))

    # Per-class de-duplication after reclassification.
    result=[]
    min_dist={"kick":.05,"snare":.05,"hat":.04,"tom":.07,"crash":.16,"ride":.05}
    for g in ("kick","snare","hat","tom","crash","ride"):
        arr=sorted([e for e in out if e[1]==g],key=lambda e:(e[0],-e[2]))
        last=-999.0
        for e in arr:
            if e[0]-last < min_dist[g]:
                continue
            result.append((e[0],e[1],e[2]))
            last=e[0]
    return sorted(result)

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
    errors=Counter()
    unmatched_pred=Counter()

    for pt,pg,*_ in pred:
        same=[abs(pt-tt) for tt,tg in truth_by if tg==pg and abs(pt-tt)<=tol]
        if same:
            continue
        near=[(abs(pt-tt),tg) for tt,tg in truth_by if abs(pt-tt)<=tol]
        if not near:
            unmatched_pred[pg]+=1
            continue
        _,tg=min(near,key=lambda z:z[0])
        errors[f"{tg}_to_{pg}"] += 1

    kicks=[t for t,g,*_ in pred if g=="kick"]
    snares=[t for t,g,*_ in pred if g=="snare"]
    supported=0; unsupported=0
    for kt in kicks:
        near_s=[st for st in snares if abs(st-kt)<=.04]
        if not near_s:
            continue
        st=min(near_s,key=lambda x:abs(x-kt))
        center=(kt+st)/2
        has_k=any(g=="kick" and abs(tt-center)<=tol for tt,g in truth_by)
        has_s=any(g=="snare" and abs(tt-center)<=tol for tt,g in truth_by)
        if has_k and has_s:
            supported+=1
        else:
            unsupported+=1

    return {
        "class_errors":dict(errors),
        "kick_to_snare":errors["kick_to_snare"],
        "snare_to_kick":errors["snare_to_kick"],
        "unmatched_predicted":dict(unmatched_pred),
        "kick_snare_double_supported":supported,
        "kick_snare_double_unsupported":unsupported,
    }

def count_ratios(score_obj):
    return {g:(round(d["predicted"]/d["reference"],3) if d["reference"] else None)
            for g,d in score_obj["by_group"].items()}





def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args(); root=args.repo_root
    tmpl=templates(root/"DruMaster/assets/drums")
    results={
        "schema":5,
        "formal_round":3,
        "description":"Formal Round 3: beat-aware kick/snare conflict resolution and reclassification of high-frequency hat/cymbal candidates into crash/ride. Truth MIDI is scoring-only.",
        "songs":{}
    }
    total=Counter()
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
        raw=acoustic_candidates(band,sim)
        pred=postprocess(raw,bpm,num,den,3,sim=sim,band=band)
        truth=midi_events(folder/"chart.mid")

        sc=score(pred,truth,shift); cf=confusion(pred,truth,shift)
        sc["count_ratio"]=count_ratios(sc); sc["confusion"]=cf
        results["songs"][folder.name]={"bpm":bpm,"time_signature":[num,den],"metrics":sc}

        total.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
                     kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"],
                     double_supported=cf["kick_snare_double_supported"],
                     double_unsupported=cf["kick_snare_double_unsupported"])
        for g,d in sc["by_group"].items():
            total[f"{g}_tp"]+=d["tp"]; total[f"{g}_pred"]+=d["predicted"]; total[f"{g}_ref"]+=d["reference"]
        print(folder.name,sc["f1"],sc["count_ratio"],cf,flush=True)

    tp,n,m=total["tp"],total["predicted"],total["reference"]
    summary={"tp":tp,"predicted":n,"reference":m,
             "precision":round(tp/n,3) if n else 0,
             "recall":round(tp/m,3) if m else 0,
             "f1":round(2*tp/(n+m),3) if n+m else 0,
             "kick_to_snare":total["kick_to_snare"],
             "snare_to_kick":total["snare_to_kick"],
             "kick_snare_double_supported":total["double_supported"],
             "kick_snare_double_unsupported":total["double_unsupported"],
             "by_group":{}}
    for g in ORDER:
        a,b,d=total[f"{g}_tp"],total[f"{g}_pred"],total[f"{g}_ref"]
        summary["by_group"][g]={"tp":a,"predicted":b,"reference":d,
                                "count_ratio":round(b/d,3) if d else None}
    results["summary"]=summary
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n")

if __name__=="__main__":
    main()
