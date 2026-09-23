import json
import math
from collections import Counter
from pathlib import Path
import importlib.util

root=Path(".")
spec=importlib.util.spec_from_file_location("ev", root/"drumscribe/experiments/evaluate_v2.py")
ev=importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)

songs=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
out={"schema":2,"source":"real browser-generated MIDI with audio-only tempo/bar estimation","songs":{}}
tot=Counter()
timing_tot={"bpm_err":[],"bar_err":[],"grid_err":[]}


def circ_dist(a,b,period):
    d=abs((a-b)%period)
    return min(d,period-d)


def varlen(data,i):
    v=0
    while True:
        b=data[i];i+=1
        v=(v<<7)|(b&127)
        if not b&128:return v,i


def midi_meta(path):
    data=Path(path).read_bytes()
    division=int.from_bytes(data[12:14],"big")
    pos=8+int.from_bytes(data[4:8],"big")
    tempos=[];signatures=[];last_tick=0
    while pos+8<=len(data) and data[pos:pos+4]==b"MTrk":
        size=int.from_bytes(data[pos+4:pos+8],"big")
        i=pos+8;end=i+size;tick=0;running=0
        while i<end:
            delta,i=varlen(data,i);tick+=delta
            status=data[i]
            if status&128:
                i+=1;running=status
            else:
                status=running
            if status==255:
                typ=data[i];i+=1
                n,i=varlen(data,i);payload=data[i:i+n];i+=n
                if typ==81 and n==3:
                    tempos.append((tick,int.from_bytes(payload,"big")))
                elif typ==88 and n>=2:
                    signatures.append((tick,payload[0],2**payload[1]))
            elif status in (240,247):
                n,i=varlen(data,i);i+=n
            else:
                op=status&240
                i+=1 if op in (192,208) else 2
        last_tick=max(last_tick,tick)
        pos=end
    return {"division":division,"tempos":tempos,"time_signatures":signatures,"last_tick":last_tick}

def reference_bar_timeline(path, shift, duration):
    mm=midi_meta(path)
    division=mm["division"]
    tempo_map={0:500000}
    for tick,us in mm["tempos"]:
        tempo_map[tick]=us
    tempos=sorted(tempo_map.items())
    seg=[];sec=0.0;prev=0;us=500000
    for tick,new_us in tempos:
        sec+=(tick-prev)*us/1e6/division
        seg.append((tick,sec,new_us))
        prev=tick;us=new_us
    if not seg:
        seg=[(0,0.0,500000)]
    def segment_at(tick):
        cur=seg[0]
        for x in seg[1:]:
            if x[0]>tick: break
            cur=x
        return cur
    def tick_to_sec(tick):
        t0,s0,u0=segment_at(tick)
        return s0+(tick-t0)*u0/1e6/division
    sig_map={0:(4,4)}
    for tick,n,d in mm["time_signatures"]:
        sig_map[tick]=(n,d)
    sigs=sorted((tick,*v) for tick,v in sig_map.items())
    bars=[]
    for i,(start,n,d) in enumerate(sigs):
        end=sigs[i+1][0] if i+1<len(sigs) else mm["last_tick"]+division*16
        step=division*n*4/d
        tick=float(start)
        while tick<end-1e-6:
            ti=int(round(tick))
            t=tick_to_sec(ti)+shift
            if 0<=t<=duration:
                _,_,u=segment_at(ti)
                bars.append({"time":t,"numerator":n,"denominator":d,"beat_sec":u/1e6})
            tick+=step
    return bars,sigs

def predicted_bar_timeline(side, duration):
    bpm=float(side["bpm"])
    numerator=int(side.get("numerator",4));denominator=int(side.get("denominator",4))
    beat=60/bpm*4/denominator
    bar=beat*numerator
    phase=float(side["barPhaseSec"])
    out=[]
    k=math.floor((0-phase)/bar)-2
    while phase+k*bar<=duration+2*bar:
        t=phase+k*bar
        if 0<=t<=duration:
            out.append({"time":t,"numerator":numerator,"denominator":denominator,"beat_sec":beat})
        k+=1
    return out

def score_bar_timeline(pred, ref, tol_beats=.25):
    if not ref:
        return {}
    errors=[];matched=0;signature_ok=0
    for r in ref:
        p=min(pred,key=lambda x:abs(x["time"]-r["time"])) if pred else None
        e=abs(p["time"]-r["time"])/r["beat_sec"] if p else 99.0
        errors.append(e)
        if e<=tol_beats:
            matched+=1
            if p["numerator"]==r["numerator"] and p["denominator"]==r["denominator"]:
                signature_ok+=1
    ordered=sorted(errors)
    return {
      "mean_abs_error_beats":sum(errors)/len(errors),
      "p95_abs_error_beats":ordered[int(.95*(len(ordered)-1))],
      "max_abs_error_beats":max(errors),
      "bar_recall_025":matched/len(ref),
      "signature_bar_accuracy_025":signature_ok/len(ref),
      "reference_bars":len(ref),
      "predicted_bars":len(pred),
    }


for song in songs:
    folder=root/"DruMaster/songs"/song
    meta=json.loads((folder/"song.json").read_text())
    side=json.loads((root/"drumscribe/experiments/generated-v2-browser"/f"{song}.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    export_offset=float(side.get("exportOffsetSec",0) or 0)

    pred_export=ev.midi_events(root/"drumscribe/experiments/generated-v2-browser"/f"{song}.mid")
    pred=[(t-export_offset,*rest) for t,*rest in pred_export]
    truth=ev.midi_events(folder/"chart.mid")
    sc=ev.score(pred,truth,shift)
    cf=ev.confusion(pred,truth,shift)
    sc["count_ratio"]=ev.count_ratios(sc)
    sc["confusion"]=cf

    truth_bpm=float(meta["bpm"])
    pred_bpm=float(side["bpm"])
    ts=meta.get("timeSignature") or {"numerator":4,"denominator":4}
    numerator=int(ts.get("numerator",4));denominator=int(ts.get("denominator",4))
    truth_beat=60/truth_bpm*4/denominator
    truth_bar=truth_beat*numerator
    reference_phase=shift%truth_bar
    predicted_phase=float(side["barPhaseSec"])%truth_bar
    bar_error_sec=circ_dist(predicted_phase,reference_phase,truth_bar)
    bar_error_beats=bar_error_sec/truth_beat
    bpm_error_percent=abs(pred_bpm-truth_bpm)/truth_bpm*100
    ref_bars,reference_meter_changes=reference_bar_timeline(folder/"chart.mid",shift,float(meta["duration"]))
    pred_bars=predicted_bar_timeline(side,float(meta["duration"]))
    bar_timeline=score_bar_timeline(pred_bars,ref_bars)

    pred_bar=float(side.get("barSec") or (60/pred_bpm*4/denominator*numerator))
    grid_residual_sec=abs((predicted_phase+export_offset)%pred_bar)
    grid_residual_sec=min(grid_residual_sec,abs(pred_bar-grid_residual_sec))
    grid_residual_beats=grid_residual_sec/(pred_bar/numerator)

    mm=midi_meta(root/"drumscribe/experiments/generated-v2-browser"/f"{song}.mid")
    midi_tempo_bpm=(60000000/mm["tempos"][0][1]) if mm["tempos"] else None
    midi_signature=mm["time_signatures"][0][1:] if mm["time_signatures"] else None

    timing={
      "estimated_bpm":pred_bpm,
      "truth_bpm":truth_bpm,
      "bpm_error_percent":bpm_error_percent,
      "bar_phase_sec":predicted_phase,
      "reference_bar_phase_sec":reference_phase,
      "bar_error_sec":bar_error_sec,
      "bar_error_beats":bar_error_beats,
      "bar_timeline":bar_timeline,
      "reference_meter_changes":reference_meter_changes,
      "export_offset_sec":export_offset,
      "export_bar_pad":side.get("exportBarPad"),
      "export_grid_residual_sec":grid_residual_sec,
      "export_grid_residual_beats":grid_residual_beats,
      "beat_phase_sec":side.get("beatPhaseSec"),
      "bar_phase_info":side.get("barPhaseInfo"),
      "tempo_info":side.get("tempoInfo"),
      "midi_tempo_bpm":midi_tempo_bpm,
      "midi_time_signature":midi_signature,
    }
    sc["timing"]=timing
    out["songs"][song]=sc

    timing_tot["bpm_err"].append(bpm_error_percent)
    timing_tot["bar_err"].append(bar_timeline.get("mean_abs_error_beats",bar_error_beats))
    timing_tot["grid_err"].append(grid_residual_beats)
    tot.update(tp=sc["tp"],predicted=sc["predicted"],reference=sc["reference"],
               kick_to_snare=cf["kick_to_snare"],snare_to_kick=cf["snare_to_kick"])
    for g,d in sc["by_group"].items():
        tot[f"{g}_tp"]+=d["tp"]; tot[f"{g}_pred"]+=d["predicted"]; tot[f"{g}_ref"]+=d["reference"]

tp,n,m=tot["tp"],tot["predicted"],tot["reference"]
summary={"tp":tp,"predicted":n,"reference":m,
         "precision":round(tp/n,3) if n else 0,
         "recall":round(tp/m,3) if m else 0,
         "f1":round(2*tp/(n+m),3) if n+m else 0,
         "kick_to_snare":tot["kick_to_snare"],"snare_to_kick":tot["snare_to_kick"],
         "by_group":{}}
for g in ev.ORDER:
    a,b,c=tot[f"{g}_tp"],tot[f"{g}_pred"],tot[f"{g}_ref"]
    summary["by_group"][g]={"tp":a,"predicted":b,"reference":c,
                            "count_ratio":round(b/c,3) if c else None}
summary["timing"]={
  "mean_bpm_error_percent":sum(timing_tot["bpm_err"])/len(timing_tot["bpm_err"]),
  "max_bpm_error_percent":max(timing_tot["bpm_err"]),
  "mean_bar_timeline_error_beats":sum(timing_tot["bar_err"])/len(timing_tot["bar_err"]),
  "max_song_mean_bar_timeline_error_beats":max(timing_tot["bar_err"]),
  "mean_bar_error_beats":sum(timing_tot["bar_err"])/len(timing_tot["bar_err"]),
  "max_bar_error_beats":max(
      out["songs"][song]["timing"]["bar_timeline"].get("max_abs_error_beats",0)
      for song in songs
  ),
  "max_export_grid_residual_beats":max(timing_tot["grid_err"]),
  "all_midi_time_signatures_4_4":all(
      out["songs"][s]["timing"]["midi_time_signature"]==[4,4] or
      out["songs"][s]["timing"]["midi_time_signature"]==(4,4)
      for s in songs
  )
}
out["summary"]=summary
(root/"drumscribe/experiments/results-v2-browser.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(summary,ensure_ascii=False,indent=2))
