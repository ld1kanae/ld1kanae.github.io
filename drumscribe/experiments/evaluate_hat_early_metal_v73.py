"""Probe whether early pedal/crash assignments hide acoustic open hats.

This experiment changes only saved predictions for offline scoring. It does
not alter runtime, and the reviewed WAV/MIDI is never part of the training set.
"""
import json
from bisect import bisect_right
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from train_hat_mp3_transfer_v68 import ROOT, EXP, SONGS, audio, features, midi_notes, score

EVENTS = json.loads((EXP/'results-hat-sync-candidate-promote-predictions-v67.json').read_text())['songs']
REVIEW = json.loads((EXP/'reviews/kimi-wa-shijin-hihat-review-v1.json').read_text())['reviews']
MIDI = ROOT.resolve().parent/'kimiwa-shijin-fresh-v72.mid'
OUT = EXP/'results-hat-early-metal-v73.json'
SOURCES = ('pedal_hat','crash','ride')
METALS = ('hat','open_hat','pedal_hat','crash','ride')


def rows(events, samples, truth=None):
    candidates=[(i,e) for i,e in enumerate(events) if e['group'] in METALS]
    art=sorted(e['time'] for e in events if e['group'] in ('hat','open_hat','pedal_hat','ride'))
    x=[]
    for _,e in candidates:
        j=bisect_right(art,e['time']+1e-8)
        x.append(features(samples,e['time'],art[j] if j<len(art) else None))
    y=[]
    if truth is not None:
        options=sorted((abs(e['time']-t),i,j) for i,(_,e) in enumerate(candidates)
                       for j,(t,n) in enumerate(truth) if abs(e['time']-t)<=.08)
        y=[-1]*len(candidates);used_i=set();used_j=set()
        for _,i,j in options:
            if i in used_i or j in used_j:continue
            y[i]=int(truth[j][1]==46)
            used_i.add(i);used_j.add(j)
    return {'candidates':candidates,'x':np.asarray(x),'y':np.asarray(y)}


def evaluate(events, truth, ignore_ride):
    s=score(events,truth,ignore_ride)
    for group,notes in (('pedal',(44,)),('crash',(49,52,55,57)),('ride',(51,53,59))):
        p=sorted(e['time'] for e in events if e['note'] in notes)
        r=sorted(t for t,n in truth if n in notes)
        used=set();tp=0
        for t in p:
            z=min(((abs(t-u),j) for j,u in enumerate(r) if j not in used and abs(t-u)<=.08),default=None)
            if z:used.add(z[1]);tp+=1
        s[group]={'tp':tp,'pred':len(p),'ref':len(r),'f1':2*tp/(len(p)+len(r)) if p or r else 0}
    return s


def predict(events,row,model,threshold=.98):
    out=[dict(e) for e in events]
    pp=model.predict_proba(row['x'])[:,1]
    for (index,e),p in zip(row['candidates'],pp):
        if e['group'] in SOURCES and p>=threshold:
            out[index].update(group='open_hat',note=46)
    return out


def main():
    inputs={}
    for song in SONGS:
        folder=ROOT/'DruMaster/songs'/song
        meta=json.loads((folder/'song.json').read_text())['playback']
        shift=float(meta['stemOffsetSec'])+float(meta.get('midiOffsetSec',0))
        truth=midi_notes(folder/'chart.mid',shift)
        events=EVENTS[song]['off']['events']
        inputs[song]=(events,truth,rows(events,audio(folder/'drums.mp3'),truth))
    out={'schema':1,'threshold':.98,'sourceGroups':SOURCES,'songs':{},'review':{}}
    for held in SONGS:
        ev,truth,test=inputs[held]
        train=[inputs[s][2] for s in SONGS if s!=held]
        x=np.vstack([v['x'][v['y']>=0] for v in train]);y=np.concatenate([v['y'][v['y']>=0] for v in train])
        model=make_pipeline(StandardScaler(),LogisticRegression(C=.4,class_weight='balanced',max_iter=1000)).fit(x,y)
        after=predict(ev,test,model)
        changed={source:sum(a['group']=='open_hat' and b['group']==source for a,b in zip(after,ev)) for source in SOURCES}
        out['songs'][held]={'baseline':evaluate(ev,truth,held=='arcaround'),
                            'candidate':evaluate(after,truth,held=='arcaround'),'changed':changed}
        print(held,changed,out['songs'][held]['baseline']['macro'],out['songs'][held]['candidate']['macro'],flush=True)
    if MIDI.exists():
        notes=midi_notes(MIDI)
        n2g={42:'hat',44:'pedal_hat',46:'open_hat',49:'crash',51:'ride'}
        ev=[{'time':t,'note':n,'group':n2g[n]} for t,n in notes if n in n2g]
        x=np.vstack([v[2]['x'][v[2]['y']>=0] for v in inputs.values()]);y=np.concatenate([v[2]['y'][v[2]['y']>=0] for v in inputs.values()])
        model=make_pipeline(StandardScaler(),LogisticRegression(C=.4,class_weight='balanced',max_iter=1000)).fit(x,y)
        test=rows(ev,audio(ROOT.resolve().parent/'upload/君は詩人になった [drums].wav'))
        after=predict(ev,test,model)
        for rev in REVIEW:
            a,b=rev['startSec'],rev['endSec']
            count=lambda events:{str(n):sum(a<=e['time']<b and e['note']==n for e in events) for n in (42,44,46,49,51)}
            out['review'][str(rev['index'])]={'baseline':count(ev),'candidate':count(after)}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
