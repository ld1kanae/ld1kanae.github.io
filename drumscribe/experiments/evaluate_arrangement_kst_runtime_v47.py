from __future__ import annotations
import importlib.util, json
from collections import Counter
from pathlib import Path

ROOT=Path(".")
GEN=ROOT/"drumscribe/experiments/generated-arrangement-kst-v47"
OUT=ROOT/"drumscribe/experiments/results-arrangement-kst-runtime-v47.json"
MD=ROOT/"drumscribe/experiments/ARRANGEMENT_KST_V47.md"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
VARIANTS=["baseline","V39_D_runtime","V46_R1_runtime","V46_R1_no_hand_guard"]
KST=("kick","snare","tom")
HAND_NOTES={38,42,45,46,49,51}

spec=importlib.util.spec_from_file_location("ev",ROOT/"drumscribe/experiments/evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def varlen(data,i):
    v=0
    while True:
        b=data[i];i+=1;v=(v<<7)|(b&127)
        if not b&128:return v,i

def midi_ticks(path):
    data=Path(path).read_bytes()
    ppq=int.from_bytes(data[12:14],"big")
    pos=8+int.from_bytes(data[4:8],"big")
    notes=[];tempos=[];sigs=[]
    while pos+8<=len(data) and data[pos:pos+4]==b"MTrk":
        size=int.from_bytes(data[pos+4:pos+8],"big")
        i=pos+8;end=i+size;tick=0;running=0
        while i<end:
            delta,i=varlen(data,i);tick+=delta
            status=data[i]
            if status&128:i+=1;running=status
            else:status=running
            if status==255:
                typ=data[i];i+=1;n,i=varlen(data,i);payload=data[i:i+n];i+=n
                if typ==81 and n==3:tempos.append(tick)
                elif typ==88 and n>=2:sigs.append((tick,payload[0],2**payload[1]))
            elif status in (240,247):
                n,i=varlen(data,i);i+=n
            else:
                op=status&240
                if op in (128,144):
                    note=data[i];vel=data[i+1];i+=2
                    if op==144 and vel>0:notes.append((tick,note))
                else:i+=1 if op in (192,208) else 2
        pos=end
    return ppq,notes,tempos,sigs

def quantum(label,ppq):
    return {"1/16":ppq//4,"1/16+1/32":ppq//8,"1/32":ppq//8,"1/8T":ppq//3,"1/16T":ppq//6}.get(label)

def tick_residual(t,q):
    if not q:return None
    r=t%q
    return min(r,q-r)

def hand_tick_violations(notes):
    c=Counter(t for t,n in notes if n in HAND_NOTES)
    return sum(1 for v in c.values() if v>2),max(c.values(),default=0)

def aggregate(scores,groups=None):
    groups=groups or tuple(ev.ORDER)
    T=Counter();by={}
    for g in groups:
        tp=sum(s["by_group"][g]["tp"] for s in scores)
        p=sum(s["by_group"][g]["predicted"] for s in scores)
        r=sum(s["by_group"][g]["reference"] for s in scores)
        by[g]={"tp":tp,"pred":p,"ref":r,
               "precision":tp/p if p else 0,
               "recall":tp/r if r else 0,
               "f1":2*tp/(p+r) if p+r else 0}
        T.update(tp=tp,pred=p,ref=r)
    return {"tp":T["tp"],"pred":T["pred"],"ref":T["ref"],
            "precision":T["tp"]/T["pred"] if T["pred"] else 0,
            "recall":T["tp"]/T["ref"] if T["ref"] else 0,
            "f1":2*T["tp"]/(T["pred"]+T["ref"]) if T["pred"]+T["ref"] else 0,
            "by_group":by}

result={"schema":1,"date":"2026-09-23","experiment":"arrangement-kst-runtime-v47","variants":{},"songs":{}}
for song in SONGS:
    folder=ROOT/"DruMaster/songs"/song
    meta=json.loads((folder/"song.json").read_text())
    truth=ev.midi_events(folder/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    result["songs"][song]={}
    for variant in VARIANTS:
        side=json.loads((GEN/variant/f"{song}.json").read_text())
        exported=ev.midi_events(GEN/variant/f"{song}.mid")
        export_offset=float(side.get("exportOffsetSec",0) or 0)
        pred=[(t-export_offset,*rest) for t,*rest in exported]
        sc=ev.score(pred,truth,shift)
        ppq,notes,tempos,sigs=midi_ticks(GEN/variant/f"{song}.mid")
        q=quantum((side.get("rhythmGridInfo") or {}).get("subdivision"),ppq)
        residuals=[tick_residual(t,q) for t,_ in notes] if q else []
        hv,hmax=hand_tick_violations(notes)
        result["songs"][song][variant]={
            "score":sc,
            "side":side,
            "grid":{
                "max_note_residual_ticks":max(residuals,default=0) if residuals else None,
                "tempo_events":len(tempos),
                "time_signatures":sigs,
                "hand_tick_violations":hv,
                "max_hands_same_tick":hmax,
            }
        }

for variant in VARIANTS:
    rows=[result["songs"][s][variant]["score"] for s in SONGS]
    kst=aggregate(rows,KST)
    all_score=aggregate(rows)
    grid_max=max((result["songs"][s][variant]["grid"]["max_note_residual_ticks"] or 0) for s in SONGS)
    hand=sum(result["songs"][s][variant]["grid"]["hand_tick_violations"] for s in SONGS)
    accepted=sum(int(result["songs"][s][variant]["side"].get("arrangementRescore",{}).get("accepted",0) or 0) for s in SONGS)
    rejected_hand=sum(int(result["songs"][s][variant]["side"].get("arrangementRescore",{}).get("rejectedHand",0) or 0) for s in SONGS)
    result["variants"][variant]={
        "kst":kst,"all":all_score,
        "max_grid_residual_ticks":grid_max,
        "hand_tick_violations":hand,
        "rescued":accepted,
        "rejected_hand":rejected_hand,
    }

base=result["variants"]["baseline"]
for variant in VARIANTS[1:]:
    x=result["variants"][variant]
    x["delta_kst_f1"]=x["kst"]["f1"]-base["kst"]["f1"]
    x["delta_all_f1"]=x["all"]["f1"]-base["all"]["f1"]
    x["delta_hand_tick_violations"]=x["hand_tick_violations"]-base["hand_tick_violations"]
    for g in KST:
        x["kst"]["by_group"][g]["delta_f1"]=x["kst"]["by_group"][g]["f1"]-base["kst"]["by_group"][g]["f1"]
    x["meter_changed_songs"]=[
        s for s in SONGS
        if result["songs"][s][variant]["side"].get("meterInfo")!=result["songs"][s]["baseline"]["side"].get("meterInfo")
    ]

OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")

def f(v):return f"{v:.6f}"
lines=[
 "# Arrangement + E-GMD residual Snare runtime v47","",
 "Fresh Chromium validation of the reusable arrangement rescoring module. Generated MIDI passes through the normal rhythm-grid and MIDI exporter before scoring against chart.mid.","",
 "| variant | KST F1 | delta | kick delta | snare delta | tom delta | all F1 delta | rescued | hand-grid delta | meter changes |",
 "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
]
for variant in VARIANTS[1:]:
    x=result["variants"][variant]
    lines.append(
      f"| {variant} | {f(x['kst']['f1'])} | {f(x['delta_kst_f1'])} | "
      f"{f(x['kst']['by_group']['kick']['delta_f1'])} | {f(x['kst']['by_group']['snare']['delta_f1'])} | "
      f"{f(x['kst']['by_group']['tom']['delta_f1'])} | {f(x['delta_all_f1'])} | {x['rescued']} | "
      f"{x['delta_hand_tick_violations']} | {', '.join(x['meter_changed_songs']) or 'none'} |"
    )
lines += ["",
 f"Baseline KST F1: {f(base['kst']['f1'])}",
 f"Baseline all-class F1: {f(base['all']['f1'])}",
 "",
 "Guardrails:",
 "- chart.mid is scoring-only and is never loaded in the browser prediction stage.",
 "- Every rescued note originates from a low-threshold acoustic K/S/T candidate.",
 "- A/A' are structural-family labels, not verse/chorus semantics.",
 "- max_grid_residual_ticks must remain 0 for an adoptable candidate.",
 "- A candidate must not increase hand-grid violations or change inferred meter relative to baseline.",
 ""]
MD.write_text("\n".join(lines))
print("\n".join(lines))
