#!/usr/bin/env python3
from __future__ import annotations
import json, math, subprocess
from pathlib import Path
from collections import Counter, defaultdict

import mido
import numpy as np
from scipy.signal import butter, sosfiltfilt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
from sklearn.preprocessing import StandardScaler

ROOT=Path('.')
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
OUT=Path('drumscribe/experiments/results-hat-choke-five-v44.json')
MODEL=Path('drumscribe/experiments/hat-choke-logreg-candidate-v44.json')
HATS={42,44,46}
METAL={49,51,52,53,55,57,59}
SNARE={37,38,39,40}
TOM={41,43,45,47,48,50}

def decode(path,sr=44100):
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-ac','1','-ar',str(sr),'-f','f32le','-acodec','pcm_f32le','-'])
    return np.frombuffer(raw,dtype='<f4').copy(),sr

def timed_notes(path,shift=0.0):
    mid=mido.MidiFile(path);tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=='set_tempo': tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0:
            out.append((sec+shift,msg.note,msg.velocity))
    return out

def rms(x,sr,a,b):
    lo=max(0,int(a*sr));hi=min(len(x),int(b*sr))
    if hi-lo<16:return None
    y=x[lo:hi]
    return float(np.sqrt(np.mean(y*y)+1e-12))

def contaminated(notes,t):
    # High-frequency metal is the strongest confound. Snare/tom coincidence is
    # reported separately but not automatically discarded because normal
    # backbeats often contain hat+snare.
    return any(abs(s-t)<=.13 and n in METAL for s,n,_ in notes)

def row_features(band,sr,t0,t1):
    onset=rms(band,sr,t0,t0+.025)
    pre=rms(band,sr,t1-.070,t1-.025)
    post1=rms(band,sr,t1+.070,t1+.130)
    post2=rms(band,sr,t1+.130,t1+.210)
    if not onset or pre is None or post1 is None or post2 is None:return None
    eps=1e-9
    return [
      math.log1p(pre/(onset+eps)),
      math.log1p(post1/(onset+eps)),
      math.log1p(post2/(onset+eps)),
      math.log1p(post1/(pre+eps)),
      math.log1p(post2/(pre+eps)),
      t1-t0,
    ]

def summarize(vals):
    if not vals:return {'n':0}
    a=np.asarray(vals,float)
    return {'n':int(len(a)),'median':float(np.median(a)),'q25':float(np.quantile(a,.25)),'q75':float(np.quantile(a,.75))}

rows=[]
per_song={}
for song in SONGS:
    folder=ROOT/'DruMaster'/'songs'/song
    meta=json.loads((folder/'song.json').read_text())
    shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
    notes=timed_notes(folder/'chart.mid',shift)
    audio,sr=decode(folder/'drums.mp3')
    sos=butter(4,[5000,18000],btype='bandpass',fs=sr,output='sos')
    band=sosfiltfilt(sos,audio).astype(np.float32)
    hats=[e for e in notes if e[1] in HATS]
    cnt=Counter();local=[]
    for i,(t0,n0,v0) in enumerate(hats[:-1]):
        if n0!=46:continue
        t1,n1,v1=hats[i+1]
        gap=t1-t0
        if gap<.10 or gap>.95:continue
        label=1 if n1==46 else 0
        kind='open_open' if label else ('open_closed' if n1==42 else 'open_pedal')
        cnt[kind]+=1
        f=row_features(band,sr,t0,t1)
        if f is None:continue
        metal_contam=contaminated(notes,t1)
        snare_near=any(abs(s-t1)<=.08 and n in SNARE for s,n,_ in notes)
        tom_near=any(abs(s-t1)<=.08 and n in TOM for s,n,_ in notes)
        r={'song':song,'t0':t0,'t1':t1,'nextNote':n1,'labelPersistent':label,
           'features':f,'metalContaminated':metal_contam,'snareNear':snare_near,'tomNear':tom_near}
        rows.append(r);local.append(r)
    per_song[song]={'transitions':dict(cnt),'usableRows':len(local),
      'persistent':sum(r['labelPersistent'] for r in local),
      'choked':sum(1-r['labelPersistent'] for r in local)}

FEATURES=['pre_tail','post_70_130','post_130_210','cut_70_130','cut_130_210','gap_sec']

def eval_rows(pool,clean_only):
    use=[r for r in pool if not clean_only or not r['metalContaminated']]
    pred=[];truth=[];folds={}
    for test_song in SONGS:
        tr=[r for r in use if r['song']!=test_song];te=[r for r in use if r['song']==test_song]
        if not te or len({r['labelPersistent'] for r in tr})<2:continue
        X=np.asarray([r['features'] for r in tr]);y=np.asarray([r['labelPersistent'] for r in tr])
        Xt=np.asarray([r['features'] for r in te]);yt=np.asarray([r['labelPersistent'] for r in te])
        sc=StandardScaler().fit(X)
        lr=LogisticRegression(max_iter=2000,class_weight='balanced',C=.7,random_state=44).fit(sc.transform(X),y)
        yp=lr.predict(sc.transform(Xt))
        pred.extend(yp.tolist());truth.extend(yt.tolist())
        p,r,f,_=precision_recall_fscore_support(yt,yp,average='binary',zero_division=0)
        folds[test_song]={'n':len(te),'persistent':int(yt.sum()),'precisionPersistent':float(p),'recallPersistent':float(r),'f1Persistent':float(f)}
    if not truth:return {'n':0,'folds':folds}
    tn,fp,fn,tp=confusion_matrix(truth,pred,labels=[0,1]).ravel()
    p,r,f,_=precision_recall_fscore_support(truth,pred,average='binary',zero_division=0)
    return {'n':len(truth),'persistent':int(sum(truth)),
      'precisionPersistent':float(p),'recallPersistent':float(r),'f1Persistent':float(f),
      'confusionMatrix':{'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)},'folds':folds}

# Fit a train-all candidate only as a compact learned artifact. LOO above is
# the generalization check; this artifact is NOT production by itself.
clean=[r for r in rows if not r['metalContaminated']]
fitrows=clean if sum(r['labelPersistent'] for r in clean)>=10 else rows
X=np.asarray([r['features'] for r in fitrows]);y=np.asarray([r['labelPersistent'] for r in fitrows])
sc=StandardScaler().fit(X)
lr=LogisticRegression(max_iter=2000,class_weight='balanced',C=.7,random_state=44).fit(sc.transform(X),y)
model={'schema':1,'kind':'hat-tail-persistence-logreg-candidate','featureNames':FEATURES,
  'trainingSongs':SONGS,'trainingRows':len(fitrows),'persistentRows':int(y.sum()),
  'normalization':{'mean':sc.mean_.tolist(),'scale':sc.scale_.tolist()},
  'coef':lr.coef_[0].tolist(),'intercept':float(lr.intercept_[0]),
  'note':'chart.mid was used offline to label transitions. Candidate only; runtime adoption requires browser non-regression.'}
MODEL.write_text(json.dumps(model,ensure_ascii=False,indent=2)+'\n')

by_label={0:[r for r in rows if r['labelPersistent']==0],1:[r for r in rows if r['labelPersistent']==1]}
summary={}
for label,rs in by_label.items():
    summary['persistent' if label else 'choked']={
      FEATURES[j]:summarize([r['features'][j] for r in rs]) for j in range(len(FEATURES))
    }
out={'schema':1,'date':'2026-09-23','experiment':'hat-choke-five-v44',
  'definition':{'persistent':'GM46 -> next hat GM46','choked':'GM46 -> next hat GM42 or GM44',
    'bandHz':[5000,18000],'gapSec':[.10,.95],
    'features':FEATURES},
  'songs':per_song,'rows':len(rows),'persistentRows':sum(r['labelPersistent'] for r in rows),
  'chokedRows':sum(1-r['labelPersistent'] for r in rows),
  'featureSummary':summary,
  'leaveOneSongOutAll':eval_rows(rows,False),
  'leaveOneSongOutNoMetalContamination':eval_rows(rows,True),
  'candidateModel':model,
  'limitations':['chart.mid labels are training/evaluation-only; no reference MIDI may be read by production prediction.',
    'The synchronized nanairo pair has no GM46->GM46 transition, so persistent-open learning must come from the other songs/GMD.',
    'Backbeat snare coincidence is retained because it is common in real drum performance; metal contamination is separately ablated.']}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['rows','persistentRows','chokedRows','featureSummary','leaveOneSongOutAll','leaveOneSongOutNoMetalContamination']},ensure_ascii=False,indent=2))
