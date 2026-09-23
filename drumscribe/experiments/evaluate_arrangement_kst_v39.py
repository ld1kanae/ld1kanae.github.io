from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
import mido

ROOT=Path(".")
BASE=Path("drumscribe/experiments/results-arrangement-kst-rescore-v38.json")
CAND=Path("drumscribe/experiments/results-arrangement-kst-candidates-v38.json")
OUT=Path("drumscribe/experiments/results-arrangement-kst-postfilter-v39.json")
MD=Path("drumscribe/experiments/ARRANGEMENT_KST_V39.md")
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
GROUPS=("kick","snare","tom")
NOTE_TO_GROUP={35:"kick",36:"kick",37:"snare",38:"snare",39:"snare",40:"snare",41:"tom",43:"tom",45:"tom",47:"tom",48:"tom",50:"tom"}

def parse_midi(path,shift):
    mid=mido.MidiFile(path)
    tempo=500000;sec=0.0;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec+=msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=="set_tempo": tempo=msg.tempo
        elif msg.type=="note_on" and msg.velocity>0:
            g=NOTE_TO_GROUP.get(msg.note)
            if g: out.append({"time":sec+shift,"group":g})
    return out

def nearest(events,t,g,tol=.08):
    return any(e["group"]==g and abs(e["time"]-t)<=tol for e in events)

def dedupe(events,tol=.05):
    out=[]
    for e in sorted(events,key=lambda x:(x["time"],x["group"])):
        if not any(x["group"]==e["group"] and abs(x["time"]-e["time"])<=tol for x in out):
            out.append(e)
    return out

def score(pred,truth,tol=.08):
    by={};T=Counter()
    for g in GROUPS:
        p=sorted(e["time"] for e in pred if e["group"]==g)
        r=sorted(e["time"] for e in truth if e["group"]==g)
        used=set();tp=0
        for t in p:
            opts=[(abs(t-x),i) for i,x in enumerate(r) if i not in used and abs(t-x)<=tol]
            if opts:
                _,i=min(opts);used.add(i);tp+=1
        by[g]={"tp":tp,"pred":len(p),"ref":len(r),
               "precision":tp/len(p) if p else 0,
               "recall":tp/len(r) if r else 0,
               "f1":2*tp/(len(p)+len(r)) if p or r else 0}
        T.update(tp=tp,pred=len(p),ref=len(r))
    return {"tp":T["tp"],"pred":T["pred"],"ref":T["ref"],
            "precision":T["tp"]/T["pred"] if T["pred"] else 0,
            "recall":T["tp"]/T["ref"] if T["ref"] else 0,
            "f1":2*T["tp"]/(T["pred"]+T["ref"]) if T["pred"]+T["ref"] else 0,
            "by_group":by}

def merge(rows):
    agg={g:Counter() for g in GROUPS}
    for row in rows:
        for g,d in row["by_group"].items(): agg[g].update(tp=d["tp"],pred=d["pred"],ref=d["ref"])
    by={};T=Counter()
    for g,c in agg.items():
        tp,p,r=c["tp"],c["pred"],c["ref"]
        by[g]={"tp":tp,"pred":p,"ref":r,"precision":tp/p if p else 0,"recall":tp/r if r else 0,"f1":2*tp/(p+r) if p+r else 0}
        T.update(tp=tp,pred=p,ref=r)
    return {"tp":T["tp"],"pred":T["pred"],"ref":T["ref"],
            "precision":T["tp"]/T["pred"] if T["pred"] else 0,
            "recall":T["tp"]/T["ref"] if T["ref"] else 0,
            "f1":2*T["tp"]/(T["pred"]+T["ref"]) if T["pred"]+T["ref"] else 0,
            "by_group":by}

def egmd_match(cand_song,addition):
    if addition["group"]!="snare": return None
    rows=cand_song.get("egmdSnareSupport") or []
    best=None
    for e in rows:
        d=abs(float(e["time"])-float(addition["time"]))
        if d<=.05 and (best is None or d<best[0]): best=(d,e)
    return best[1] if best else None

def keep_variant(name,a,cand_song):
    if name=="V39_A_subthreshold_hand":
        # Family rescue should mainly recover events omitted by the production
        # threshold. Do not resurrect a hand event that already exceeded the
        # production threshold and was then removed by downstream logic.
        return a["group"]=="kick" or float(a.get("confidence",0))<1.0
    eg=egmd_match(cand_song,a)
    egpass=bool(eg and float(eg.get("probability",0))>=float(eg.get("modelThreshold",1)))
    if name=="V39_B_egmd_snare_gate":
        return a["group"]!="snare" or egpass
    if name=="V39_C_subthreshold_and_egmd":
        if a["group"]=="kick": return True
        if a["group"]=="tom": return float(a.get("confidence",0))<1.0
        return float(a.get("confidence",0))<1.0 and egpass
    if name=="V39_D_symbolic_gmd_plus_postfilter":
        # Start from H3 additions, then apply the same post-filter-origin guard
        # to hand-played K/S/T.
        return a["group"]=="kick" or float(a.get("confidence",0))<1.0
    raise KeyError(name)

def main():
    base=json.loads(BASE.read_text())
    cand=json.loads(CAND.read_text())
    variants={
      "V39_A_subthreshold_hand":{"source":"sensitive/H1_strict_family"},
      "V39_B_egmd_snare_gate":{"source":"sensitive/H1_strict_family"},
      "V39_C_subthreshold_and_egmd":{"source":"sensitive/H1_strict_family"},
      "V39_D_symbolic_gmd_plus_postfilter":{"source":"sensitive/H3_family_gmd"},
    }
    truth={}
    for song in SONGS:
        meta=json.loads((ROOT/"DruMaster"/"songs"/song/"song.json").read_text())
        shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
        truth[song]=parse_midi(ROOT/"DruMaster"/"songs"/song/"chart.mid",shift)

    results={"schema":1,"date":"2026-09-23","experiment":"arrangement-kst-postfilter-v39","variants":variants,"songs":{}}
    for song in SONGS:
        baseline=[dict(e) for e in cand["songs"][song]["finalKst"]]
        results["songs"][song]={"baseline":score(baseline,truth[song]),"variants":{}}
        for name,v in variants.items():
            source_policy="H3_family_gmd" if "symbolic_gmd" in name else "H1_strict_family"
            additions=base["songs"][song]["modes"]["sensitive"][source_policy]["addition_details"]
            kept=[dict(a) for a in additions if keep_variant(name,a,cand["songs"][song])]
            final=dedupe(baseline+kept)
            addstats={g:{"added":0,"tp":0,"fp":0} for g in GROUPS}
            details=[]
            for a in kept:
                hit=nearest(truth[song],a["time"],a["group"],.08)
                st=addstats[a["group"]];st["added"]+=1;st["tp"]+=int(hit);st["fp"]+=int(not hit)
                eg=egmd_match(cand["songs"][song],a)
                details.append({**a,"truth_hit":hit,"egmd_probability":None if not eg else eg.get("probability"),"egmd_threshold":None if not eg else eg.get("modelThreshold")})
            results["songs"][song]["variants"][name]={"metrics":score(final,truth[song]),"added_by_group":addstats,"details":details}

    baseline=merge([results["songs"][s]["baseline"] for s in SONGS])
    results["baseline"]=baseline;results["aggregate"]={}
    for name in variants:
        x=merge([results["songs"][s]["variants"][name]["metrics"] for s in SONGS])
        x["delta_f1"]=x["f1"]-baseline["f1"]
        for g in GROUPS:x["by_group"][g]["delta_f1"]=x["by_group"][g]["f1"]-baseline["by_group"][g]["f1"]
        adds={g:Counter() for g in GROUPS}
        for s in SONGS:
            for g,d in results["songs"][s]["variants"][name]["added_by_group"].items(): adds[g].update(d)
        x["added_by_group"]={g:dict(c) for g,c in adds.items()}
        results["aggregate"][name]=x

    OUT.write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n")
    def f(x):return f"{x:.6f}"
    lines=["# Arrangement K/S/T post-filter v39","",
      "v38 sensitive family rescue was the starting point. This round tests whether the one observed false-positive Snare can be rejected without losing the true A/A' rescues.","",
      "| variant | KST F1 | delta | kick delta | snare delta | tom delta | added TP/FP |",
      "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name,x in results["aggregate"].items():
        tp=sum(v.get("tp",0) for v in x["added_by_group"].values());fp=sum(v.get("fp",0) for v in x["added_by_group"].values())
        lines.append(f"| {name} | {f(x['f1'])} | {f(x['delta_f1'])} | {f(x['by_group']['kick']['delta_f1'])} | {f(x['by_group']['snare']['delta_f1'])} | {f(x['by_group']['tom']['delta_f1'])} | {tp}/{fp} |")
    lines += ["","Interpretation rules:",
      "- chart.mid remains scoring-only.",
      "- no variant copies a note from A to A'; all additions originate from low-threshold acoustic candidates.",
      "- V39_A/C/D treat a hand candidate already above production threshold but absent from final output as a downstream-veto case rather than a missing-threshold case.",
      "- Production integration still requires a fresh browser non-regression run.",
      ""]
    MD.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__": main()
