from __future__ import annotations
import csv, io, json, math
from collections import defaultdict, Counter
from pathlib import Path

import mido
from remotezip import RemoteZip

ROOT=Path(".")
IN=Path("drumscribe/experiments/results-arrangement-kst-candidates-v38.json")
OUT=Path("drumscribe/experiments/results-arrangement-kst-rescore-v38.json")
MD=Path("drumscribe/experiments/ARRANGEMENT_KST_V38.md")
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
SIMPLE3={"diamondvirgin","nanairo","ray"}
GROUPS=("kick","snare","tom")
GMD_URL="https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0.zip"
GMD_MAX_FILES=240

NOTE_TO_GROUP={}
for n in (35,36): NOTE_TO_GROUP[n]="kick"
for n in (37,38,39,40): NOTE_TO_GROUP[n]="snare"
for n in (41,43,45,47,48,50): NOTE_TO_GROUP[n]="tom"

POLICIES={
  "H1_strict_family":{
    "min_confidence":.72,
    "min_support_rate":.50,
    "min_family_quality":.90,
    "min_gmd_lift":0.0,
  },
  "H2_family_consensus":{
    "min_confidence":.55,
    "min_support_rate":.67,
    "min_family_quality":.92,
    "min_gmd_lift":0.0,
  },
  "H3_family_gmd":{
    "min_confidence":.50,
    "min_support_rate":.50,
    "min_family_quality":.90,
    "min_gmd_lift":.80,
  },
}

def parse_midi(path,shift):
    mid=mido.MidiFile(path)
    tempo=500000
    sec=0.0
    out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += msg.time * tempo / 1e6 / mid.ticks_per_beat
        if msg.type=="set_tempo":
            tempo=msg.tempo
        elif msg.type=="note_on" and msg.velocity>0:
            g=NOTE_TO_GROUP.get(msg.note)
            if g:
                out.append({"time":sec+shift,"group":g})
    return out

def nearest_exists(events,t,group,tol=.055):
    return any(e["group"]==group and abs(e["time"]-t)<=tol for e in events)

def dedupe(events,tol=.05):
    out=[]
    for e in sorted(events,key=lambda x:(x["time"],x["group"],-x.get("_rank",0))):
        same=[x for x in out if x["group"]==e["group"] and abs(x["time"]-e["time"])<=tol]
        if same:
            if e.get("_rank",0)>same[0].get("_rank",0):
                out.remove(same[0]); out.append(e)
        else:
            out.append(e)
    return sorted(out,key=lambda x:(x["time"],x["group"]))

def score(pred,truth,tol=.08):
    by={}
    total_tp=total_p=total_r=0
    for group in GROUPS:
        p=sorted(e["time"] for e in pred if e["group"]==group)
        r=sorted(e["time"] for e in truth if e["group"]==group)
        used=set();tp=0
        for t in p:
            best=None
            for j,x in enumerate(r):
                if j in used: continue
                d=abs(t-x)
                if d<=tol and (best is None or d<best[0]): best=(d,j)
            if best:
                used.add(best[1]);tp+=1
        precision=tp/len(p) if p else 0.0
        recall=tp/len(r) if r else 0.0
        f1=2*tp/(len(p)+len(r)) if (p or r) else 0.0
        by[group]={"tp":tp,"pred":len(p),"ref":len(r),"precision":precision,"recall":recall,"f1":f1}
        total_tp+=tp; total_p+=len(p); total_r+=len(r)
    return {
        "tp":total_tp,"pred":total_p,"ref":total_r,
        "precision":total_tp/total_p if total_p else 0.0,
        "recall":total_tp/total_r if total_r else 0.0,
        "f1":2*total_tp/(total_p+total_r) if total_p+total_r else 0.0,
        "by_group":by
    }

def merge_scores(rows):
    sums={g:Counter() for g in GROUPS}
    for r in rows:
        for g,d in r["by_group"].items():
            sums[g].update(tp=d["tp"],pred=d["pred"],ref=d["ref"])
    total=Counter()
    by={}
    for g,c in sums.items():
        tp,p,r=c["tp"],c["pred"],c["ref"]
        by[g]={
            "tp":tp,"pred":p,"ref":r,
            "precision":tp/p if p else 0.0,
            "recall":tp/r if r else 0.0,
            "f1":2*tp/(p+r) if p+r else 0.0
        }
        total.update(tp=tp,pred=p,ref=r)
    tp,p,r=total["tp"],total["pred"],total["ref"]
    return {
        "tp":tp,"pred":p,"ref":r,
        "precision":tp/p if p else 0.0,
        "recall":tp/r if r else 0.0,
        "f1":2*tp/(p+r) if p+r else 0.0,
        "by_group":by
    }

def gmd_events(data):
    mid=mido.MidiFile(file=io.BytesIO(data))
    tick=0;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        tick+=msg.time
        if msg.type=="note_on" and msg.velocity>0:
            g=NOTE_TO_GROUP.get(msg.note)
            if g:
                out.append((tick/mid.ticks_per_beat,g))
    return out

def build_gmd_slot_prior():
    counts={g:[0]*16 for g in GROUPS}
    bars_seen={g:[0]*16 for g in GROUPS}
    used_files=0;used_bars=0
    with RemoteZip(GMD_URL) as rz:
        names=set(rz.namelist())
        info_name=next((n for n in names if n.endswith("/info.csv") or n=="info.csv"),None)
        if not info_name: raise RuntimeError("GMD info.csv not found")
        prefix=info_name.rsplit("/",1)[0]+"/" if "/" in info_name else ""
        rows=list(csv.DictReader(io.TextIOWrapper(rz.open(info_name),encoding="utf-8")))
        candidates=[r for r in rows if r.get("split")=="train" and r.get("beat_type")=="beat" and r.get("time_signature")=="4-4" and r.get("midi_filename")]
        by_style=defaultdict(list)
        for r in candidates:
            by_style[(r.get("style") or "unknown").split("/",1)[0]].append(r)
        for arr in by_style.values(): arr.sort(key=lambda x:x.get("id",""))
        selected=[];depth=0;styles=sorted(by_style)
        while len(selected)<GMD_MAX_FILES:
            added=False
            for style in styles:
                arr=by_style[style]
                if depth<len(arr):
                    selected.append(arr[depth]);added=True
                    if len(selected)>=GMD_MAX_FILES: break
            if not added: break
            depth+=1
        for row in selected:
            member=row["midi_filename"] if row["midi_filename"] in names else prefix+row["midi_filename"]
            if member not in names: continue
            ev=gmd_events(rz.read(member))
            maxq=max([q for q,_ in ev],default=0)
            nb=int(maxq//4)
            if nb<1: continue
            used_files+=1;used_bars+=nb
            for b in range(nb):
                present={g:set() for g in GROUPS}
                lo=b*4;hi=lo+4
                for q,g in ev:
                    if lo<=q<hi:
                        slot=max(0,min(15,int(round((q-lo)*4))))
                        present[g].add(slot)
                for g in GROUPS:
                    for slot in range(16):
                        bars_seen[g][slot]+=1
                        if slot in present[g]: counts[g][slot]+=1
    probs={}
    lifts={}
    for g in GROUPS:
        probs[g]=[(counts[g][s]+1)/(bars_seen[g][s]+2) for s in range(16)]
        mean=sum(probs[g])/16
        lifts[g]=[p/mean if mean else 1.0 for p in probs[g]]
    return {
        "source":"Groove MIDI Dataset v1.0.0 train beat 4/4",
        "files_used":used_files,
        "bars_used":used_bars,
        "probability":probs,
        "lift":lifts
    }

def family_quality(sections,group):
    fam=[s for s in sections if s["group"]==group]
    if len(fam)<2:return 0.0
    vals=[float(s.get("repeatSimilarity",1)) for s in fam if int(s.get("occurrence",1))>1]
    return sum(vals)/len(vals) if vals else 1.0

def section_for_time(sections,t):
    for s in sections:
        if s["startSec"]<=t<s["endSec"]: return s
    return None

def slot_info(t,section,bar_sec):
    rel=max(0.0,t-section["startSec"])
    bar_idx=int(math.floor(rel/bar_sec+1e-8))
    inbar=rel-bar_idx*bar_sec
    slot=int(round(inbar/bar_sec*16))
    if slot>=16:
        bar_idx+=1;slot=0
    return bar_idx,slot

def family_support(t,group,section,sections,baseline,bar_sec):
    bar_idx,slot=slot_info(t,section,bar_sec)
    others=[s for s in sections if s["group"]==section["group"] and s["index"]!=section["index"]]
    eligible=0;support=0
    for other in others:
        target=other["startSec"]+bar_idx*bar_sec+slot/16*bar_sec
        if target>=other["endSec"]-.03: continue
        eligible+=1
        if nearest_exists(baseline,target,group,.075): support+=1
    return {
        "bar_index":bar_idx,"slot":slot,
        "support":support,"eligible":eligible,
        "rate":support/eligible if eligible else 0.0
    }

def apply_policy(songrow,mode,policy,gmd):
    sections=songrow["analyses"][mode]["sections"]
    bpm=float(songrow["bpm"]);num=int(songrow.get("numerator",4));den=int(songrow.get("denominator",4))
    beat=60/bpm*4/den;bar=beat*num
    baseline=[dict(e) for e in songrow["finalKst"]]
    additions=[]
    for group in GROUPS:
        for c in (songrow.get("candidates") or {}).get(group,[]):
            t=float(c["time"])
            if nearest_exists(baseline,t,group,.055): continue
            sec=section_for_time(sections,t)
            if not sec: continue
            fq=family_quality(sections,sec["group"])
            if fq<policy["min_family_quality"]: continue
            fs=family_support(t,group,sec,sections,baseline,bar)
            if fs["eligible"]<1 or fs["support"]<1 or fs["rate"]+1e-12<policy["min_support_rate"]: continue
            conf=float(c.get("confidence") or 0)
            if conf<policy["min_confidence"]: continue
            gmd_lift=float(gmd["lift"][group][fs["slot"]])
            if gmd_lift+1e-12<policy["min_gmd_lift"]: continue
            rank=conf+.35*fs["rate"]+.12*min(2,gmd_lift)+.08*fq
            additions.append({
                "time":t,"group":group,"confidence":conf,
                "family":sec["group"],"section_label":sec.get("label"),
                "family_quality":fq,"support":fs["support"],"eligible":fs["eligible"],
                "support_rate":fs["rate"],"bar_index":fs["bar_index"],"slot":fs["slot"],
                "gmd_lift":gmd_lift,"_rank":rank
            })
    additions=dedupe(additions)
    final=dedupe(baseline+additions)
    return final,additions

def added_truth_stats(additions,truth):
    out={}
    for g in GROUPS:
        a=[e for e in additions if e["group"]==g]
        hits=sum(1 for e in a if nearest_exists(truth,e["time"],g,.08))
        out[g]={"added":len(a),"tp":hits,"fp":len(a)-hits,"precision":hits/len(a) if a else None}
    return out

def safe(x):
    return "n/a" if x is None else f"{x:.4f}"

def main():
    data=json.loads(IN.read_text())
    gmd=build_gmd_slot_prior()
    result={
        "schema":1,"date":"2026-09-23","experiment":"arrangement-kst-rescore-v38",
        "reference_policy":"chart.mid is opened only in this scoring script, after browser transcription/candidate generation.",
        "policies":POLICIES,"gmd_prior":gmd,"modes":{},"songs":{}
    }
    song_truth={}
    for song in SONGS:
        meta=json.loads((ROOT/"DruMaster"/"songs"/song/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        song_truth[song]=parse_midi(ROOT/"DruMaster"/"songs"/song/"chart.mid",shift)

    for song in SONGS:
        baseline=[dict(e) for e in data["songs"][song]["finalKst"]]
        truth=song_truth[song]
        result["songs"][song]={"baseline":score(baseline,truth),"modes":{}}
        for mode in data["modes"]:
            mr={}
            for pname,p in POLICIES.items():
                final,additions=apply_policy(data["songs"][song],mode,p,gmd)
                mr[pname]={
                    "metrics":score(final,truth),
                    "additions":len(additions),
                    "added_by_group":added_truth_stats(additions,truth),
                    "addition_details":additions
                }
            result["songs"][song]["modes"][mode]=mr

    for mode in data["modes"]:
        mode_out={}
        baseline_all=merge_scores([result["songs"][s]["baseline"] for s in SONGS])
        baseline_simple=merge_scores([result["songs"][s]["baseline"] for s in SONGS if s in SIMPLE3])
        mode_out["baseline_all5"]=baseline_all
        mode_out["baseline_simple3"]=baseline_simple
        for pname in POLICIES:
            all_rows=[result["songs"][s]["modes"][mode][pname]["metrics"] for s in SONGS]
            simple_rows=[result["songs"][s]["modes"][mode][pname]["metrics"] for s in SONGS if s in SIMPLE3]
            agg=merge_scores(all_rows);simple=merge_scores(simple_rows)
            agg["delta_f1"]=agg["f1"]-baseline_all["f1"]
            simple["delta_f1"]=simple["f1"]-baseline_simple["f1"]
            for g in GROUPS:
                agg["by_group"][g]["delta_f1"]=agg["by_group"][g]["f1"]-baseline_all["by_group"][g]["f1"]
                simple["by_group"][g]["delta_f1"]=simple["by_group"][g]["f1"]-baseline_simple["by_group"][g]["f1"]
            mode_out[pname]={"all5":agg,"simple3":simple}
        result["modes"][mode]=mode_out

    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")

    lines=[
      "# Arrangement K/S/T rescoring v38","",
      "A/A' structural-family support is used only to rescore low-threshold acoustic candidates. No note is copied from another section. Reference chart.mid is scoring-only.","",
      "## Hypotheses","",
      "- H1 strict family: acoustic confidence >= 0.72, same-family support >= 50%, family similarity >= 0.90.",
      "- H2 family consensus: acoustic confidence >= 0.55, same-family support >= 67%, family similarity >= 0.92.",
      "- H3 family + GMD: acoustic confidence >= 0.50, same-family support >= 50%, family similarity >= 0.90, GMD slot lift >= 0.80.",
      "",
      f"GMD slot prior: {gmd['files_used']} train files / {gmd['bars_used']} 4/4 bars.",
      "",
      "## Aggregate all-five-song comparison","",
      "| segmentation | policy | KST F1 | delta | kick delta | snare delta | tom delta |",
      "|---|---|---:|---:|---:|---:|---:|"
    ]
    for mode,mo in result["modes"].items():
        for pname in POLICIES:
            x=mo[pname]["all5"]
            lines.append(f"| {mode} | {pname} | {safe(x['f1'])} | {safe(x['delta_f1'])} | {safe(x['by_group']['kick']['delta_f1'])} | {safe(x['by_group']['snare']['delta_f1'])} | {safe(x['by_group']['tom']['delta_f1'])} |")
    lines += ["","## Simple three-song comparison (diamondvirgin / nanairo / ray)","",
      "| segmentation | policy | KST F1 | delta | kick delta | snare delta | tom delta |",
      "|---|---|---:|---:|---:|---:|---:|"]
    for mode,mo in result["modes"].items():
        for pname in POLICIES:
            x=mo[pname]["simple3"]
            lines.append(f"| {mode} | {pname} | {safe(x['f1'])} | {safe(x['delta_f1'])} | {safe(x['by_group']['kick']['delta_f1'])} | {safe(x['by_group']['snare']['delta_f1'])} | {safe(x['by_group']['tom']['delta_f1'])} |")
    lines += ["","## Guardrails","",
      "- This round is rescue-only: it never deletes an existing production K/S/T note.",
      "- A/A' is a structural-family relationship, not verse/chorus semantics.",
      "- arcaround and kaiju are retained in all-five reporting but the simple3 aggregate is also shown because the current arrangement experiment assumes a 4/4 bar correspondence.",
      "- Production adoption requires non-regression of kick/snare/tom individually and a fresh real-browser run.",
      ""]
    MD.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__":
    main()
