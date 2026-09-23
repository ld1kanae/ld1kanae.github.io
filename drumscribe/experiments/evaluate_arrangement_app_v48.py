from __future__ import annotations
import importlib.util,json
from collections import Counter
from pathlib import Path

ROOT=Path(".")
GEN=ROOT/"drumscribe/experiments/generated-arrangement-app-v48"
EXPECTED=ROOT/"drumscribe/experiments/results-arrangement-kst-runtime-v47.json"
OUT=ROOT/"drumscribe/experiments/results-arrangement-app-v48.json"
MD=ROOT/"drumscribe/experiments/ARRANGEMENT_APP_V48.md"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
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
    data=Path(path).read_bytes();ppq=int.from_bytes(data[12:14],"big")
    pos=8+int.from_bytes(data[4:8],"big");notes=[];tempos=[];sigs=[]
    while pos+8<=len(data) and data[pos:pos+4]==b"MTrk":
        size=int.from_bytes(data[pos+4:pos+8],"big");i=pos+8;end=i+size;tick=0;running=0
        while i<end:
            delta,i=varlen(data,i);tick+=delta;status=data[i]
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
    r=t%q;return min(r,q-r)

def hand_tick_violations(notes):
    c=Counter(t for t,n in notes if n in HAND_NOTES)
    return sum(1 for v in c.values() if v>2),max(c.values(),default=0)

def aggregate(scores,groups):
    by={};T=Counter()
    for g in groups:
        tp=sum(s["by_group"][g]["tp"] for s in scores)
        p=sum(s["by_group"][g]["predicted"] for s in scores)
        r=sum(s["by_group"][g]["reference"] for s in scores)
        by[g]={"tp":tp,"pred":p,"ref":r,"precision":tp/p if p else 0,
               "recall":tp/r if r else 0,"f1":2*tp/(p+r) if p+r else 0}
        T.update(tp=tp,pred=p,ref=r)
    tp,p,r=T["tp"],T["pred"],T["ref"]
    return {"tp":tp,"pred":p,"ref":r,"precision":tp/p if p else 0,
            "recall":tp/r if r else 0,"f1":2*tp/(p+r) if p+r else 0,"by_group":by}

expected=json.loads(EXPECTED.read_text())["variants"]["V46_R1_runtime"]
songs={};scores=[]
for song in SONGS:
    folder=ROOT/"DruMaster"/"songs"/song
    meta=json.loads((folder/"song.json").read_text())
    truth=ev.midi_events(folder/"chart.mid")
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    side=json.loads((GEN/f"{song}.json").read_text())
    exported=ev.midi_events(GEN/f"{song}.mid")
    export_offset=float(side.get("exportOffsetSec",0) or 0)
    pred=[(t-export_offset,*rest) for t,*rest in exported]
    sc=ev.score(pred,truth,shift);scores.append(sc)

    ppq,notes,tempos,sigs=midi_ticks(GEN/f"{song}.mid")
    q=quantum((side.get("rhythmGridInfo") or {}).get("subdivision"),ppq)
    residuals=[tick_residual(t,q) for t,_ in notes] if q else []
    hv,hmax=hand_tick_violations(notes)
    policy=side.get("arrangementInfo",{}).get("rescore",{}).get("policy",{}).get("name")
    assert policy=="family-gmd-plus-egmd-residual-v46r1",(song,policy)
    assert max(residuals,default=0)==0,(song,"grid residual",max(residuals,default=0))
    assert hv==0,(song,"hand violations",hv)
    expected_meter=json.loads((ROOT/"drumscribe/experiments/generated-arrangement-kst-v47/V46_R1_runtime"/f"{song}.json").read_text()).get("meterInfo")
    assert side.get("meterInfo")==expected_meter,(song,"meter changed",side.get("meterInfo"),expected_meter)

    songs[song]={
      "score":sc,
      "policy":policy,
      "accepted":side["arrangementInfo"]["rescore"].get("accepted",0),
      "acceptedArrangement":side["arrangementInfo"]["rescore"].get("acceptedArrangement",0),
      "acceptedEgmdResidual":side["arrangementInfo"]["rescore"].get("acceptedEgmdResidual",0),
      "max_grid_residual_ticks":max(residuals,default=0),
      "hand_tick_violations":hv,
      "max_hands_same_tick":hmax,
      "meterInfo":side.get("meterInfo"),
    }

kst=aggregate(scores,KST);allscore=aggregate(scores,tuple(ev.ORDER))
for key in ("tp","pred","ref"):
    assert kst[key]==expected["kst"][key],("KST mismatch",key,kst[key],expected["kst"][key])
    assert allscore[key]==expected["all"][key],("ALL mismatch",key,allscore[key],expected["all"][key])
assert abs(kst["f1"]-expected["kst"]["f1"])<1e-12
assert abs(allscore["f1"]-expected["all"]["f1"])<1e-12
rescued=sum(x["accepted"] for x in songs.values())
residual=sum(x["acceptedEgmdResidual"] for x in songs.values())
assert rescued==12,("rescued",rescued)
assert residual==3,("residual",residual)

result={
  "schema":1,"date":"2026-09-23","experiment":"arrangement-app-v48",
  "purpose":"Verify the actual production UI/app.js path uses the v46R1 policy and reproduces v47 exported-MIDI metrics.",
  "kst":kst,"all":allscore,"rescued":rescued,"egmdResidualRescued":residual,"songs":songs,
  "matches_v47_runtime":True
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
MD.write_text(f"""# Arrangement K/S/T production app v48

Actual `index.html -> app.js` UI path was exercised in fresh Chromium for all five validation songs.

- policy: `family-gmd-plus-egmd-residual-v46r1`
- K/S/T F1: **{kst['f1']:.6f}**
- all-class F1: **{allscore['f1']:.6f}**
- rescued notes: **{rescued}**
- E-GMD residual Snare rescues: **{residual}**
- max grid residual ticks: **0**
- hand-grid violations: **0**
- meter changes vs v47 validated runtime: **none**
- exported MIDI TP/pred/ref exactly matches v47 `V46_R1_runtime`.

Reference MIDI is opened only in this post-generation scoring script.
""")
print(MD.read_text())
