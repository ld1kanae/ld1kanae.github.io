from __future__ import annotations
import csv, io, json, math
from collections import defaultdict
from pathlib import Path

import mido
from remotezip import RemoteZip

ROOT=Path(".")
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
STRUCT=Path("drumscribe/experiments/results-arrangement-structure-v37.json")
OUT=Path("drumscribe/experiments/results-arrangement-prior-v37.json")
MD=Path("drumscribe/experiments/ARRANGEMENT_PRIOR_V37.md")
GMD_URL="https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0.zip"
GMD_MAX_FILES=240

NOTE_GROUPS={
    "kick":{35,36},
    "snare":{37,38,39,40},
    "tom":{41,43,45,47,48,50},
    "hat":{42,44,46},
    "crash":{49,52,55,57},
    "ride":{51,53,59},
}
PATTERN_GROUPS=("kick","snare","tom","hat","crash","ride")
KST=("kick","snare","tom")
METAL=("hat","crash","ride")

def group_note(note):
    for g,notes in NOTE_GROUPS.items():
        if note in notes:
            return g
    return None

def parse_midi(path, shift=0.0):
    mid=mido.MidiFile(path)
    tempo=500000
    sec=0.0
    tick=0
    notes=[]
    tempos=[(0,0.0,tempo)]
    signatures=[(0,4,4)]
    for msg in mido.merge_tracks(mid.tracks):
        tick += msg.time
        sec += msg.time * tempo / 1e6 / mid.ticks_per_beat
        if msg.type=="set_tempo":
            tempo=msg.tempo
            tempos.append((tick,sec,tempo))
        elif msg.type=="time_signature":
            signatures.append((tick,msg.numerator,msg.denominator))
        elif msg.type=="note_on" and msg.velocity>0:
            g=group_note(msg.note)
            if g:
                notes.append({"time":sec+shift,"tick":tick,"group":g,"note":msg.note})
    return {
        "ppq":mid.ticks_per_beat,
        "notes":notes,
        "tempos":sorted({(int(t),float(s),int(u)) for t,s,u in tempos}),
        "signatures":sorted({(int(t),int(n),int(d)) for t,n,d in signatures}),
        "max_tick":max([n["tick"] for n in notes],default=0),
        "shift":shift,
    }

def tick_to_sec(midi,tick):
    seg=midi["tempos"][0]
    for row in midi["tempos"]:
        if row[0]>tick:
            break
        seg=row
    return seg[1]+(tick-seg[0])*seg[2]/1e6/midi["ppq"]+midi["shift"]

def bar_heads(midi):
    sigs=midi["signatures"]
    if not sigs or sigs[0][0]!=0:
        sigs=[(0,4,4),*sigs]
    out=[]
    tick=0
    max_tick=midi["max_tick"]+midi["ppq"]*8
    while tick<=max_tick:
        current=sigs[0]
        next_change=None
        for s in sigs:
            if s[0]<=tick:
                current=s
            elif s[0]>tick:
                next_change=s[0]
                break
        out.append(tick_to_sec(midi,tick))
        bar_len=round(midi["ppq"]*4*current[1]/current[2])
        nxt=tick+max(1,bar_len)
        if next_change is not None and tick<next_change<nxt:
            nxt=next_change
        if nxt<=tick:
            break
        tick=nxt
    return out

def hit_rate(points, notes, beat_sec, groups):
    if not points:
        return {"hits":0,"points":0,"rate":0.0}
    hits=0
    for t in points:
        lo=t-.25*beat_sec
        hi=t+.75*beat_sec
        if any(lo<=n["time"]<=hi and n["group"] in groups for n in notes):
            hits+=1
    return {"hits":hits,"points":len(points),"rate":hits/len(points)}

def pattern_set(notes,start,bar_sec,groups):
    end=start+bar_sec
    out=set()
    gi={g:i for i,g in enumerate(groups)}
    for n in notes:
        if n["group"] not in gi or not (start<=n["time"]<end):
            continue
        rel=(n["time"]-start)/bar_sec*16
        slot=max(0,min(15,int(round(rel))))
        out.add(gi[n["group"]]*16+slot)
    return out

def f1set(a,b):
    if not a and not b:
        return None
    return 2*len(a&b)/(len(a)+len(b)) if (a or b) else None

def mean(values):
    values=[x for x in values if x is not None and math.isfinite(x)]
    return sum(values)/len(values) if values else None

def compare_sections(sections,notes,bar_sec,same):
    full=[]; kst=[]; metal=[]
    pairs=0; bars=0
    for i,a in enumerate(sections):
        for b in sections[i+1:]:
            if (a["group"]==b["group"]) != same:
                continue
            ratio=min(a["duration"],b["duration"])/max(a["duration"],b["duration"],1e-9)
            if ratio<.65:
                continue
            na=max(1,int(round(a["duration"]/bar_sec)))
            nb=max(1,int(round(b["duration"]/bar_sec)))
            count=min(na,nb)
            pairs+=1
            for j in range(count):
                sa=a["startSec"]+j*bar_sec
                sb=b["startSec"]+j*bar_sec
                full.append(f1set(pattern_set(notes,sa,bar_sec,PATTERN_GROUPS),pattern_set(notes,sb,bar_sec,PATTERN_GROUPS)))
                kst.append(f1set(pattern_set(notes,sa,bar_sec,KST),pattern_set(notes,sb,bar_sec,KST)))
                metal.append(f1set(pattern_set(notes,sa,bar_sec,METAL),pattern_set(notes,sb,bar_sec,METAL)))
                bars+=1
    return {"pairs":pairs,"bars":bars,"full_f1":mean(full),"kst_f1":mean(kst),"metal_f1":mean(metal)}

def project_stats(struct):
    by_mode={mode:{"songs":{}} for mode in struct["modes"]}
    for song in SONGS:
        folder=ROOT/"DruMaster"/"songs"/song
        meta=json.loads((folder/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        midi=parse_midi(folder/"chart.mid",shift)
        bpm=float(meta["bpm"])
        den=int(meta.get("timeSignature",{}).get("denominator",4))
        num=int(meta.get("timeSignature",{}).get("numerator",4))
        beat_sec=60/bpm*4/den
        bar_sec=beat_sec*num
        controls_all=bar_heads(midi)
        for mode in struct["modes"]:
            ana=struct["songs"][song]["analyses"][mode]
            boundaries=ana["boundaries"][1:-1]
            controls=[t for t in controls_all if 0<=t<=ana["duration"] and all(abs(t-b)>beat_sec for b in boundaries)]
            boundary_crash=hit_rate(boundaries,midi["notes"],beat_sec,{"crash"})
            control_crash=hit_rate(controls,midi["notes"],beat_sec,{"crash"})
            boundary_cymbal=hit_rate(boundaries,midi["notes"],beat_sec,{"crash","ride"})
            control_cymbal=hit_rate(controls,midi["notes"],beat_sec,{"crash","ride"})
            same=compare_sections(ana["sections"],midi["notes"],bar_sec,True)
            cross=compare_sections(ana["sections"],midi["notes"],bar_sec,False)
            by_mode[mode]["songs"][song]={
                "sections":len(ana["sections"]),
                "repeated_sections":sum(1 for s in ana["sections"] if s.get("occurrence",1)>1),
                "boundary_crash":boundary_crash,
                "control_crash":control_crash,
                "boundary_cymbal":boundary_cymbal,
                "control_cymbal":control_cymbal,
                "same_family":same,
                "cross_family":cross,
            }
    for mode,data in by_mode.items():
        songs=data["songs"]
        def weighted_rate(key):
            hits=sum(s[key]["hits"] for s in songs.values())
            pts=sum(s[key]["points"] for s in songs.values())
            return {"hits":hits,"points":pts,"rate":hits/pts if pts else 0.0}
        bc=weighted_rate("boundary_crash"); cc=weighted_rate("control_crash")
        byc=weighted_rate("boundary_cymbal"); cyc=weighted_rate("control_cymbal")
        same_k=[];cross_k=[];same_full=[];cross_full=[];same_m=[];cross_m=[]
        for s in songs.values():
            same_k.append(s["same_family"]["kst_f1"]); cross_k.append(s["cross_family"]["kst_f1"])
            same_full.append(s["same_family"]["full_f1"]); cross_full.append(s["cross_family"]["full_f1"])
            same_m.append(s["same_family"]["metal_f1"]); cross_m.append(s["cross_family"]["metal_f1"])
        summary={
            "boundary_crash":bc,
            "control_crash":cc,
            "boundary_crash_lift":bc["rate"]/cc["rate"] if cc["rate"] else None,
            "boundary_cymbal":byc,
            "control_cymbal":cyc,
            "boundary_cymbal_lift":byc["rate"]/cyc["rate"] if cyc["rate"] else None,
            "same_family_full_f1":mean(same_full),
            "cross_family_full_f1":mean(cross_full),
            "same_family_kst_f1":mean(same_k),
            "cross_family_kst_f1":mean(cross_k),
            "same_family_metal_f1":mean(same_m),
            "cross_family_metal_f1":mean(cross_m),
        }
        for key in ("full","kst","metal"):
            a=summary[f"same_family_{key}_f1"]
            b=summary[f"cross_family_{key}_f1"]
            summary[f"{key}_repeat_margin"]=a-b if a is not None and b is not None else None
        data["summary"]=summary
    return by_mode

def gmd_midi_events(data):
    mid=mido.MidiFile(file=io.BytesIO(data))
    tick=0
    out=[]
    for msg in mido.merge_tracks(mid.tracks):
        tick+=msg.time
        if msg.type=="note_on" and msg.velocity>0:
            g=group_note(msg.note)
            if g:
                out.append((tick/mid.ticks_per_beat,g))
    return out

def gmd_bar_vector(events,start,groups=PATTERN_GROUPS):
    end=start+4
    gi={g:i for i,g in enumerate(groups)}
    out=set()
    for q,g in events:
        if g not in gi or not (start<=q<end):
            continue
        slot=max(0,min(15,int(round((q-start)*4))))
        out.add(gi[g]*16+slot)
    return out

def gmd_stats():
    with RemoteZip(GMD_URL) as rz:
        names=set(rz.namelist())
        info_name=next((n for n in names if n.endswith("/info.csv") or n=="info.csv"),None)
        if not info_name:
            raise RuntimeError("GMD info.csv not found")
        prefix=info_name.rsplit("/",1)[0]+"/" if "/" in info_name else ""
        rows=list(csv.DictReader(io.TextIOWrapper(rz.open(info_name),encoding="utf-8")))
        candidates=[r for r in rows if r.get("split")=="train" and r.get("beat_type")=="beat" and r.get("time_signature")=="4-4" and r.get("midi_filename")]
        by_style=defaultdict(list)
        for r in candidates:
            style=(r.get("style") or "unknown").split("/",1)[0]
            by_style[style].append(r)
        for arr in by_style.values():
            arr.sort(key=lambda x:x.get("id",""))
        selected=[]
        styles=sorted(by_style)
        depth=0
        while len(selected)<GMD_MAX_FILES:
            added=False
            for style in styles:
                arr=by_style[style]
                if depth<len(arr):
                    selected.append(arr[depth]); added=True
                    if len(selected)>=GMD_MAX_FILES:
                        break
            if not added:
                break
            depth+=1

        adjacent=[]
        style_firstbars=defaultdict(list)
        beat_crash=[0,0,0,0]; beat_cym=[0,0,0,0]; beat_total=[0,0,0,0]
        used=0; bars_total=0
        for row in selected:
            member=row["midi_filename"] if row["midi_filename"] in names else prefix+row["midi_filename"]
            if member not in names:
                continue
            events=gmd_midi_events(rz.read(member))
            maxq=max([q for q,_ in events],default=0)
            bars=int(maxq//4)
            if bars<1:
                continue
            used+=1; bars_total+=bars
            vectors=[gmd_bar_vector(events,b*4) for b in range(bars)]
            for a,b in zip(vectors,vectors[1:]):
                s=f1set(a,b)
                if s is not None: adjacent.append(s)
            style=(row.get("style") or "unknown").split("/",1)[0]
            style_firstbars[style].append((row.get("id",""),vectors[0]))
            for b in range(bars):
                base=b*4
                for pos in range(4):
                    beat_total[pos]+=1
                    lo=base+pos-.08; hi=base+pos+.22
                    if any(lo<=q<=hi and g=="crash" for q,g in events):
                        beat_crash[pos]+=1
                    if any(lo<=q<=hi and g in {"crash","ride"} for q,g in events):
                        beat_cym[pos]+=1

        cross=[]
        for style,arr in style_firstbars.items():
            arr=sorted(arr,key=lambda x:x[0])
            for (_,a),(_,b) in zip(arr[::2],arr[1::2]):
                s=f1set(a,b)
                if s is not None: cross.append(s)

        crash_rates=[beat_crash[i]/beat_total[i] if beat_total[i] else 0 for i in range(4)]
        cym_rates=[beat_cym[i]/beat_total[i] if beat_total[i] else 0 for i in range(4)]
        other_crash=sum(crash_rates[1:])/3
        other_cym=sum(cym_rates[1:])/3
        return {
            "dataset":"Groove MIDI Dataset v1.0.0",
            "archive_url":GMD_URL,
            "selection":{"split":"train","beat_type":"beat","time_signature":"4-4","max_files":GMD_MAX_FILES,"stratified_by_style":True},
            "files_used":used,
            "bars_used":bars_total,
            "adjacent_bar_full_f1":mean(adjacent),
            "same_style_cross_file_first_bar_f1":mean(cross),
            "adjacent_repeat_margin":(mean(adjacent)-mean(cross)) if mean(adjacent) is not None and mean(cross) is not None else None,
            "crash_rate_by_beat":crash_rates,
            "cymbal_rate_by_beat":cym_rates,
            "crash_downbeat_lift_vs_beats_2_4":crash_rates[0]/other_crash if other_crash else None,
            "cymbal_downbeat_lift_vs_beats_2_4":cym_rates[0]/other_cym if other_cym else None,
            "limitation":"GMD has no song-section labels or offvocal; these are generic bar-head/repetition priors, not evidence that a detected A/B/C boundary is a chorus/verse boundary.",
        }

def safe(v,d=4):
    if v is None:
        return "n/a"
    return f"{v:.{d}f}"

def main():
    struct=json.loads(STRUCT.read_text())
    project=project_stats(struct)
    gmd=gmd_stats()
    result={
        "schema":1,
        "date":"2026-09-23",
        "experiment":"arrangement-prior-v37",
        "prediction_rule":"offvocal structure is produced without chart.mid; chart.mid is opened only here for post-hoc evaluation.",
        "project":project,
        "gmd":gmd,
        "hypotheses":{
            "H1_boundary_cymbal":"Detected offvocal structural boundaries should carry crash/cymbal more often than ordinary non-boundary bar heads.",
            "H2_family_repetition":"Bars at the same relative position in A/A-prime structural-family occurrences should have more similar drum patterns than different-family controls.",
            "H3_gmd_general_prior":"GMD should show generic bar-head cymbal concentration and within-performance bar repetition; use only as weak generic prior because GMD has no section labels.",
        },
    }
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")

    lines=["# DrumScribe Arrangement Prior v37","",
      "offvocal structure is inferred before opening reference chart.mid. Reference MIDI is used only for the evaluation below.","",
      "## Three structure hypotheses","",
      "1. H1 boundary-cymbal prior: structural boundaries should have more crash/cymbal support than ordinary bar heads.",
      "2. H2 family-repetition prior: A/A' corresponding bars should be more similar than different-family bars.",
      "3. H3 GMD general prior: use GMD only for generic downbeat-cymbal and repeated-groove statistics; GMD has no section labels.","",
      "## Five-song results by segmentation mode","",
      "| mode | boundary crash lift | boundary cymbal lift | K/S/T repeat margin | metal repeat margin |",
      "|---|---:|---:|---:|---:|"]
    for mode,data in project.items():
        s=data["summary"]
        lines.append(f"| {mode} | {safe(s['boundary_crash_lift'])} | {safe(s['boundary_cymbal_lift'])} | {safe(s['kst_repeat_margin'])} | {safe(s['metal_repeat_margin'])} |")
    lines += ["","## GMD generic prior","",
      f"- Files used: {gmd['files_used']}; bars used: {gmd['bars_used']}",
      f"- Adjacent-bar full-pattern F1: {safe(gmd['adjacent_bar_full_f1'])}",
      f"- Same-style cross-file first-bar F1: {safe(gmd['same_style_cross_file_first_bar_f1'])}",
      f"- Adjacent repetition margin: {safe(gmd['adjacent_repeat_margin'])}",
      f"- Crash downbeat lift vs beats 2-4: {safe(gmd['crash_downbeat_lift_vs_beats_2_4'])}",
      f"- Cymbal downbeat lift vs beats 2-4: {safe(gmd['cymbal_downbeat_lift_vs_beats_2_4'])}",
      "",
      "## Interpretation guard",
      "",
      "- A/B/C are structural-family labels only; A' is a recurrence of A.",
      "- GMD does not provide verse/pre-chorus/chorus labels or paired offvocal audio.",
      "- No production note is added or deleted by this experiment.",
      "- The next stage may use only priors that are supported here, and must validate kick/snare/tom non-regression before runtime adoption.",
      ""]
    MD.write_text("\n".join(lines))
    print(json.dumps({"project":{m:d["summary"] for m,d in project.items()},"gmd":gmd},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
