"""Second-stage BPM estimation from real browser kick/snare events.

Input MIDI was generated in Chromium from audio. Event times are preserved in
seconds regardless of the tempo written in the MIDI. song.json is scoring-only.

Tests kick interval, snare backbeat interval, and consensus candidates to fix
browser spectral/onset tempo outliers such as nanairo.
"""
from __future__ import annotations
import importlib.util,json,math
from pathlib import Path
import numpy as np

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]
spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def times(song,g):
    return [t for t,gg,*_ in ev.midi_events(EXP/"generated-v2-browser"/f"{song}.mid") if gg==g]

def hist_candidates(xs,kind,lo=50,hi=220,step=.25):
    n=round((hi-lo)/step)+1;h=np.zeros(n)
    maxj=18 if kind=="kick" else 12
    for i,t in enumerate(xs):
        for j in range(i+1,min(len(xs),i+maxj)):
            dt=xs[j]-t
            if dt>(2.6 if kind=="kick" else 3.2):break
            if dt<.16:continue
            if kind=="snare":
                for mult in (1,2,3):
                    bpm=120*mult/dt
                    if lo<=bpm<=hi:h[round((bpm-lo)/step)]+=1/(j-i)**.55/(mult**.45)
            else:
                for mult in (1,2,3,4):
                    bpm=60*mult/dt
                    if lo<=bpm<=hi:h[round((bpm-lo)/step)]+=1/(j-i)**.5/(mult**.35)
    # top local peaks
    rows=[]
    for i in range(1,n-1):
        if h[i]>=h[i-1] and h[i]>=h[i+1]:
            rows.append((h[i],lo+i*step))
    rows.sort(reverse=True)
    return rows[:15],h

def coherence(xs,bpm):
    if not xs:return 0.
    z=sum(np.exp(2j*np.pi*bpm*np.asarray(xs)/60))
    return float(abs(z)/len(xs))

def choose(song):
    ks=times(song,"kick");ss=times(song,"snare")
    kc,_=hist_candidates(ks,"kick");sc,_=hist_candidates(ss,"snare")
    pool=[]
    for source,rows in (("kick",kc),("snare",sc)):
        for raw,b in rows[:10]:
            for ratio in (.5,1,2):
                x=b*ratio
                if 50<=x<=220:
                    pool.append((x,source,raw))
    # de-duplicate
    uniq=[]
    for b,src,raw in sorted(pool,key=lambda z:z[2],reverse=True):
        if any(abs(b-u[0])<.7 for u in uniq):continue
        uniq.append((b,src,raw))
    scored=[]
    kmax=max([r[0] for r in kc],default=1);smax=max([r[0] for r in sc],default=1)
    for b,src,raw in uniq:
        kh=max((v for v,x in kc if abs(x-b)<.8),default=0)/max(kmax,1e-9)
        sh=max((v for v,x in sc if abs(x-b)<.8),default=0)/max(smax,1e-9)
        kco=coherence(ks,b);sco=coherence(ss,b)
        # snare recurrence resolves metrical level; kick coherence stabilizes.
        score=.55*sh+.20*kh+.15*sco+.10*kco
        scored.append((score,b,kh,sh,kco,sco))
    scored.sort(reverse=True)
    return {"bpm":scored[0][1],"candidates":[{"score":a,"bpm":b,"kick_hist":kh,"snare_hist":sh,"kick_coh":kc0,"snare_coh":sc0}
            for a,b,kh,sh,kc0,sc0 in scored[:10]],"kick_count":len(ks),"snare_count":len(ss)}

def main():
    out={"schema":1,"songs":{}};errs=[]
    for song in SONGS:
        pred=choose(song)
        truth=float(json.loads((ROOT/"DruMaster/songs"/song/"song.json").read_text())["bpm"])
        err=abs(pred["bpm"]-truth)/truth*100;errs.append(err)
        out["songs"][song]={"prediction":pred,"truth":truth,"error_percent":err}
        print("EVENTBPM",song,json.dumps(out["songs"][song],ensure_ascii=False),flush=True)
    out["summary"]={"mean_error_percent":float(np.mean(errs)),"max_error_percent":float(np.max(errs))}
    (EXP/"results-browser-event-bpm.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("SUMMARY",json.dumps(out["summary"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
