"""Beat-phase benchmark using librosa dynamic-programming beat tracking.

BPM is fixed to the audio-only v3 estimate; librosa is used only to locate the
beat sequence. Multiple onset/tightness variants are compared. song.json is
scoring-only.
"""
from __future__ import annotations
import importlib.util,json,math
from pathlib import Path
import numpy as np
import librosa

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def loadmod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
v1=loadmod("bpm1",EXP/"estimate_bpm.py")
v3=loadmod("bpm3",EXP/"estimate_bpm_v3.py")

def circular_phase(times,period):
    if not len(times):return 0.
    z=np.sum(np.exp(2j*np.pi*np.asarray(times)/period))
    return float((np.angle(z)%(2*np.pi))/(2*np.pi)*period)

def estimate(path,bpm,aggregate,tightness):
    y,sr=librosa.load(path,sr=22050,mono=True)
    if aggregate=="median":
        onset=librosa.onset.onset_strength(y=y,sr=sr,hop_length=256,aggregate=np.median)
    elif aggregate=="mean":
        onset=librosa.onset.onset_strength(y=y,sr=sr,hop_length=256,aggregate=np.mean)
    else:
        # emphasize lower/mid frequencies where kick/snare dominate
        S=np.abs(librosa.stft(y,n_fft=2048,hop_length=256))
        freqs=librosa.fft_frequencies(sr=sr,n_fft=2048)
        S=S[(freqs>=40)&(freqs<=3500)]
        onset=librosa.onset.onset_strength(S=librosa.amplitude_to_db(S,ref=np.max),sr=sr,hop_length=256,aggregate=np.median)
    tempo,beats=librosa.beat.beat_track(onset_envelope=onset,sr=sr,hop_length=256,
                                        bpm=float(bpm),tightness=float(tightness),
                                        trim=True,units="time")
    beats=np.asarray(beats,float).ravel()
    p=60/bpm
    ph=circular_phase(beats,p)
    # Robust residual around fixed-tempo grid.
    residual=[]
    for t in beats:
        x=(t-ph)%p;residual.append(min(x,p-x))
    return {"phase_sec":ph,"beat_count":int(len(beats)),
            "median_grid_residual_sec":float(np.median(residual)) if residual else None,
            "first_beats":[float(x) for x in beats[:12]]}

def main():
    configs={
      "median_t50":("median",50),
      "median_t100":("median",100),
      "median_t200":("median",200),
      "mean_t100":("mean",100),
      "body_t100":("body",100),
      "body_t200":("body",200),
    }
    report={"schema":1,"songs":{}};tot={k:[] for k in configs}
    for song in SONGS:
        env,band=v1.onset_envelope(ROOT/"DruMaster/songs"/song/"drums.mp3")
        bpm=v3.estimate(env,band)["bpm"]
        preds={k:estimate(ROOT/"DruMaster/songs"/song/"drums.mp3",bpm,*cfg) for k,cfg in configs.items()}
        meta=json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())
        truth=float(meta["bpm"]);beat=60/truth
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        ref=shift%beat
        out={}
        for k,p in preds.items():
            d=abs((p["phase_sec"]-ref)%beat);d=min(d,beat-d);eb=d/beat;tot[k].append(eb)
            out[k]={"prediction":p,"error_sec":d,"error_beats":eb}
        report["songs"][song]={"bpm":bpm,"truth_bpm":truth,"reference_beat_phase_sec":ref,"methods":out}
        print("LIBBEAT",song,json.dumps(report["songs"][song],ensure_ascii=False),flush=True)
    report["summary"]={k:{"mean_abs_beats":float(np.mean(v)),"max_abs_beats":float(np.max(v))} for k,v in tot.items()}
    (EXP/"results-beat-phase-librosa.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("SUMMARY",json.dumps(report["summary"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
