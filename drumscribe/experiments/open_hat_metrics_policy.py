"""Shared Open/Closed hi-hat evaluation helpers.

Project articulation policy:
- Open: GM 46
- Closed: GM 42 + GM 44 (pedal folded into Closed)

This module is evaluation-only. It does not alter runtime transcription.
"""
from __future__ import annotations
import bisect

OPEN_PITCHES={46}
CLOSED_PITCHES={42,44}

def collapse_truth_hat_events(rows, simultaneous_sec=.003):
    """Collapse simultaneous 42/44/46 reference notes to one physical event.

    Open wins if an Open note exists at the same instant; otherwise 42 and 44
    are both the Closed class.
    """
    hats=sorted((float(t),int(p)) for t,g,p in rows if int(p) in OPEN_PITCHES|CLOSED_PITCHES)
    out=[]
    for t,p in hats:
        state="open" if p in OPEN_PITCHES else "closed"
        if out and abs(t-out[-1][0])<=simultaneous_sec:
            if state=="open":out[-1]=(out[-1][0],"open")
        else:out.append((t,state))
    return out

def refs_from_rows(rows):
    h=collapse_truth_hat_events(rows)
    return {"open":[t for t,s in h if s=="open"],"closed":[t for t,s in h if s=="closed"]}

def greedy_tp(pred,ref,tol=.080):
    pred=sorted(map(float,pred));ref=sorted(map(float,ref));used=set();tp=0
    for t in pred:
        i=bisect.bisect_left(ref,t);best=None
        for j in (i-2,i-1,i,i+1,i+2):
            if 0<=j<len(ref) and j not in used:
                d=abs(t-ref[j])
                if d<=tol and (best is None or d<best[0]):best=(d,j)
        if best is not None:used.add(best[1]);tp+=1
    return tp

def prf(pred,ref,tol=.080):
    pred=list(pred);ref=list(ref);tp=greedy_tp(pred,ref,tol);p=len(pred);r=len(ref)
    return {"tp":tp,"predicted":p,"reference":r,
      "precision":tp/p if p else 0.0,"recall":tp/r if r else 0.0,
      "f1":2*tp/(p+r) if p+r else 0.0}

def articulation(open_pred,closed42_pred,pedal44_pred,truth_rows,tol=.080):
    refs=refs_from_rows(truth_rows)
    o=prf(open_pred,refs["open"],tol)
    c=prf(sorted(list(closed42_pred)+list(pedal44_pred)),refs["closed"],tol)
    return {"open":o,"closed":c,"macroF1":.5*(o["f1"]+c["f1"])}
