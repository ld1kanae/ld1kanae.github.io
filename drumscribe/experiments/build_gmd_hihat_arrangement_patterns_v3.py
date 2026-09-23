"""Build GMD-only genre/phrase priors for Open/Closed hi-hat selection.

Reads only the official Magenta Groove MIDI Dataset MIDI-only archive.
Open = 26/46. Closed = 22/42/44 (pedal folded into Closed).
GMD has genre/style labels but no verse/pre-chorus/chorus labels, so boundary
statistics here are groove/phrase proxies rather than semantic section labels.
"""
from __future__ import annotations
import csv, hashlib, io, json, zipfile
from collections import Counter, defaultdict
from pathlib import Path
import mido, requests

ROOT=Path(".")
OUT=ROOT/"drumscribe/models/gmd-kst/hihat-arrangement-patterns-v3.json"
ZIP_URL="https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0-midionly.zip"
ZIP_SHA256="651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e"
OPEN={26,46}; CLOSED={22,42,44}; KICK={35,36}; SNARE={37,38,39,40}
TOM={41,43,45,47,48,50,58}; CRASH={49,52,55,57}; RIDE={51,53,59}
VOICE_BITS={"kick":0,"snare":1,"closed":2,"open":3}

def resolve_name(names,rel):
    rel=str(rel).replace("\\","/").lstrip("./")
    if rel in names:return rel
    c=[n for n in names if n.endswith("/"+rel) or n.endswith(rel)]
    if not c:raise KeyError(rel)
    return min(c,key=len)

def parse_midi(data):
    mf=mido.MidiFile(file=io.BytesIO(data));tick=0;notes=[]
    for msg in mido.merge_tracks(mf.tracks):
        tick+=msg.time
        if msg.type=="note_on" and msg.velocity>0:notes.append((int(tick),int(msg.note),int(msg.velocity)))
    return int(mf.ticks_per_beat),notes

def qslot(t,tpb):return int(round(float(t)/(float(tpb)/4.0)))
def state(p):
    if p in OPEN:return "open"
    if p in CLOSED:return "closed"
    if p in KICK:return "kick"
    if p in SNARE:return "snare"
    if p in TOM:return "tom"
    if p in CRASH:return "crash"
    if p in RIDE:return "ride"
    return None

def groove_bits(bar):
    x=0
    for sl,states in bar.items():
        if not 0<=sl<16:continue
        for st in states:
            if st in VOICE_BITS:x|=1<<(sl*4+VOICE_BITS[st])
    return x

def jsim(a,b):
    u=(a|b).bit_count()
    return 1.0 if not u else (a&b).bit_count()/u

def bc():return {"n":0,"crash":0,"ride":0,"anyCymbal":0,"openHat":0,"closedHat":0}
def addb(c,states):
    c["n"]+=1
    cr="crash" in states;rd="ride" in states
    c["crash"]+=int(cr);c["ride"]+=int(rd);c["anyCymbal"]+=int(cr or rd)
    c["openHat"]+=int("open" in states);c["closedHat"]+=int("closed" in states)

def init():
    return {"sequences":0,"beats":0,"fills":0,"openHits":0,"closedHits":0,
      "transitions":Counter(),"transitionGap16":defaultdict(Counter),"openRunLength":Counter(),
      "bars":0,"repeat":{1:Counter(),2:Counter(),4:Counter()},"boundary":defaultdict(bc)}

def addseq(st,tpb,notes,beat_type):
    st["sequences"]+=1;st["beats" if beat_type=="beat" else "fills"]+=1
    by=defaultdict(set);mx=0
    for tick,p,_ in notes:
        z=state(p)
        if z is None:continue
        s=qslot(tick,tpb)
        if s<0:continue
        by[s].add(z);mx=max(mx,s)
    hats=[]
    for s in sorted(by):
        ss=by[s]
        if "open" in ss:hats.append((s,"O"));st["openHits"]+=1
        elif "closed" in ss:hats.append((s,"C"));st["closedHits"]+=1
    run=0
    for i,(s,a) in enumerate(hats):
        if a=="O":run+=1
        elif run:st["openRunLength"][str(min(run,32))]+=1;run=0
        if i+1<len(hats):
            ns,b=hats[i+1];k=a+">"+b;st["transitions"][k]+=1
            st["transitionGap16"][k][str(max(0,min(32,ns-s)))]+=1
    if run:st["openRunLength"][str(min(run,32))]+=1
    if beat_type!="beat":return

    nb=max(1,mx//16+1);bars=[];bits=[]
    for b in range(nb):
        bar=defaultdict(set)
        for a,ss in by.items():
            if a//16==b:bar[a%16].update(ss)
        bars.append(bar);bits.append(groove_bits(bar))
    st["bars"]+=nb
    for lag in (1,2,4):
        for b in range(lag,nb):
            sim=jsim(bits[b],bits[b-lag]);r=st["repeat"][lag]
            r["pairs"]+=1;r["exact"]+=int(bits[b]==bits[b-lag])
            r["similar75"]+=int(sim>=.75);r["similar60"]+=int(sim>=.60)
            r["simMilliSum"]+=int(round(sim*1000))
    for b,bar in enumerate(bars):
        head=bar.get(0,set());addb(st["boundary"]["allBarHeads"],head)
        if b==0:addb(st["boundary"]["sequenceStart"],head)
        if b and b%2==0:addb(st["boundary"]["period2"],head)
        if b and b%4==0:addb(st["boundary"]["period4"],head)
        if b and b%8==0:addb(st["boundary"]["period8"],head)
        if b>0:
            sim=jsim(bits[b],bits[b-1])
            if sim>=.75:addb(st["boundary"]["repeatFromPrev"],head)
            if sim<.45:addb(st["boundary"]["changeFromPrev"],head)
            prev=bars[b-1];tail=[x for s in range(12,16) for x in prev.get(s,set())]
            toms=sum(x=="tom" for x in tail);snares=sum(x=="snare" for x in tail)
            fill=toms>=2 or toms+snares>=3
            if fill:
                addb(st["boundary"]["afterFillLike"],head)
                if sim<.45:addb(st["boundary"]["changeAfterFillLike"],head)

def finb(c):
    n=int(c["n"])
    return {**{k:int(c[k]) for k in ("n","crash","ride","anyCymbal","openHat","closedHat")},
      "pCrash":c["crash"]/n if n else None,"pRide":c["ride"]/n if n else None,
      "pAnyCymbal":c["anyCymbal"]/n if n else None,
      "pOpenHat":c["openHat"]/n if n else None,"pClosedHat":c["closedHat"]/n if n else None}

def finalize(st):
    o=int(st["openHits"]);c=int(st["closedHits"]);rep={}
    for lag,r in st["repeat"].items():
        n=int(r["pairs"])
        rep[str(lag)]={"pairs":n,"exactRate":r["exact"]/n if n else None,
          "similar75Rate":r["similar75"]/n if n else None,"similar60Rate":r["similar60"]/n if n else None,
          "meanSimilarity":r["simMilliSum"]/(1000*n) if n else None}
    tr={k:int(v) for k,v in st["transitions"].items()};tn=sum(tr.values())
    return {"sequences":int(st["sequences"]),"beats":int(st["beats"]),"fills":int(st["fills"]),
      "bars":int(st["bars"]),"openHits":o,"closedHits":c,"openRate":o/(o+c) if o+c else 0.,
      "transitions":tr,"transitionProb":{k:v/tn for k,v in tr.items()} if tn else {},
      "transitionGap16":{k:{str(g):int(n) for g,n in sorted(v.items(),key=lambda q:int(q[0]))}
                         for k,v in st["transitionGap16"].items()},
      "openRunLength":{k:int(v) for k,v in sorted(st["openRunLength"].items(),key=lambda q:int(q[0]))},
      "barRepeat":rep,"boundary":{k:finb(v) for k,v in sorted(st["boundary"].items())}}

def main():
    raw=requests.get(ZIP_URL,timeout=120);raw.raise_for_status()
    sha=hashlib.sha256(raw.content).hexdigest()
    if sha!=ZIP_SHA256:raise RuntimeError(f"GMD MIDI zip SHA256 mismatch: {sha}")
    z=zipfile.ZipFile(io.BytesIO(raw.content));names=set(z.namelist())
    info=min((n for n in names if n.endswith("info.csv")),key=len)
    rows=list(csv.DictReader(io.TextIOWrapper(z.open(info),encoding="utf-8-sig")))
    glob=init();genres=defaultdict(init);splits=Counter();types=Counter();skip=Counter();used=0
    for row in rows:
        ts=str(row.get("time_signature","")).replace("-","/")
        if ts!="4/4":skip[ts or "unknown"]+=1;continue
        rel=row.get("midi_filename")
        if not rel:continue
        genre=(row.get("style") or "unknown").split("/")[0].strip().lower() or "unknown"
        bt=(row.get("beat_type") or "unknown").strip().lower()
        splits[(row.get("split") or "unknown").strip().lower()]+=1;types[bt]+=1
        tpb,notes=parse_midi(z.read(resolve_name(names,rel)))
        if not notes:continue
        addseq(glob,tpb,notes,bt);addseq(genres[genre],tpb,notes,bt);used+=1
    out={"schema":3,"kind":"gmd-hihat-arrangement-patterns",
      "source":{"dataset":"Google Magenta Groove MIDI Dataset v1.0.0","url":ZIP_URL,
        "archiveSha256":ZIP_SHA256,"license":"CC BY 4.0","sourceMode":"MIDI-only; direct original GMD MIDI parse"},
      "sourceSeparation":{"gmdOnly":True,"readsDruMasterSongs":False,"readsOffvocal":False,
        "readsSynchronizedNanairoTeacher":False,"trainingRowsPooledWithOtherSources":False},
      "labelMapping":{"open":sorted(OPEN),"closed":sorted(CLOSED),"pedal44Policy":"fold into closed",
        "crash":sorted(CRASH),"ride":sorted(RIDE)},
      "semanticsWarning":"GMD genre/style and groove recurrence only; no verse/pre-chorus/chorus labels.",
      "grid":{"timeSignature":"4/4","slotsPerBar":16,"quantization":"nearest sixteenth"},
      "global":finalize(glob),"genres":{k:finalize(v) for k,v in sorted(genres.items())},
      "metadata":{"usableSequences4_4":used,"primaryGenres":len(genres),"splitCounts":dict(splits),
        "beatTypeCounts":dict(types),"skippedNon4_4":dict(skip)}}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    g=out["global"]
    print("GMD_HIHAT_ARR_V3",json.dumps({"usable":used,"genres":len(genres),"open":g["openHits"],
      "closed":g["closedHits"],"openRate":g["openRate"],"barRepeat":g["barRepeat"],"boundary":g["boundary"]},
      ensure_ascii=False),flush=True)
if __name__=="__main__":main()
