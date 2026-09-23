from __future__ import annotations
import json
from pathlib import Path
import mido
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path('.')
IN=ROOT/'drumscribe/experiments/results-hat-raw-acoustic-candidates-v63.json'
OUT=ROOT/'drumscribe/models/hat-raw-acoustic-v64.json'
REPORT=ROOT/'drumscribe/experiments/HAT_RAW_ACOUSTIC_MODEL_V64.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']

def parse_midi(path,shift):
    mid=mido.MidiFile(path);tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec+=msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=='set_tempo':tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0:out.append((sec+shift,msg.note))
    return out

def nearest_label(t,truth,tol=.08):
    best=None
    for u,n in truth:
        if n not in (42,46):continue
        d=abs(t-u)
        if d<=tol and (best is None or d<best[0]):best=(d,1 if n==46 else 0)
    return None if best is None else best[1]

def ranks(a):
    a=np.asarray(a,float);out=np.zeros(len(a))
    if len(a)<=1:return out
    order=np.argsort(a,kind='stable')
    for r,i in enumerate(order):out[i]=r/(len(a)-1)
    return out

def robust_z(a):
    a=np.asarray(a,float);med=np.median(a);mad=np.median(np.abs(a-med));scale=max(1e-6,1.4826*mad)
    return np.clip((a-med)/scale,-8,8)

def serialize_tree(est):
    t=est.tree_;prob1=[]
    for v in t.value:
        a=v[0];s=float(np.sum(a));prob1.append(float(a[1]/s) if s>0 and len(a)>1 else 0.)
    return {'feature':t.feature.astype(int).tolist(),'threshold':[float(x) for x in t.threshold.tolist()],
      'left':t.children_left.astype(int).tolist(),'right':t.children_right.astype(int).tolist(),'prob1':prob1}

def main():
    data=json.loads(IN.read_text())
    rows=[];stats={}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth=parse_midi(ROOT/'DruMaster/songs'/song/'chart.mid',shift)
        desc=data['songs'][song]['descriptors']
        raw=np.array([d['vector'] for d in desc],float)
        base=np.array([float(d['openHatProbability']) for d in desc],float)
        rr=np.stack([ranks(raw[:,j]) for j in range(raw.shape[1])],axis=1) if len(raw) else np.empty((0,14))
        rz=np.stack([robust_z(raw[:,j]) for j in range(raw.shape[1])],axis=1) if len(raw) else np.empty((0,14))
        br=ranks(base);bz=robust_z(base)
        nopen=nclosed=0
        for i,d in enumerate(desc):
            y=nearest_label(float(d['time']),truth)
            if y is None:continue
            vec=np.r_[raw[i],rr[i],rz[i],[base[i],br[i],bz[i],float(d.get('score') or 0),float(d.get('confidence') or 0),1.0 if d['group']=='open_hat' else 0.0]]
            rows.append((vec,int(y),song))
            if y:nopen+=1
            else:nclosed+=1
        stats[song]={'descriptors':len(desc),'labeled':nopen+nclosed,'open':nopen,'closed':nclosed}
    X=np.stack([r[0] for r in rows]);y=np.array([r[1] for r in rows],int)
    m=ExtraTreesClassifier(n_estimators=420,max_depth=12,min_samples_leaf=4,class_weight='balanced',max_features='sqrt',random_state=42,n_jobs=-1)
    m.fit(X,y)
    names=[f'raw{i}' for i in range(14)]+[f'rank{i}' for i in range(14)]+[f'z{i}' for i in range(14)]+['base_p','base_rank','base_z','score','confidence','current_open']
    payload={'schema':1,'model':'hat-raw-acoustic-v64','date':'2026-09-24','features':names,
      'confidenceThreshold':.55,'closedThreshold':.45,'treeCount':len(m.estimators_),
      'purpose':'Per-hit Open/Closed classification from attack/decay/tail/choke acoustics and reference-free within-song normalization.',
      'reviewSpecificInputsUsed':False,'patternParityUsed':False,
      'training':{'songs':SONGS,'labeled':len(rows),'open':int(y.sum()),'closed':int(len(y)-y.sum()),'songStats':stats,
        'selectionValidation':'experiments/HAT_RAW_ACOUSTIC_LOOCV_V63.md'},
      'trees':[serialize_tree(e) for e in m.estimators_]}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n')
    REPORT.write_text(
      '# Raw Acoustic Hi-Hat Model v64\n\n'
      '- Selected from five-song leave-one-song-out H3_raw_localnorm.\n'
      '- Features: per-hit attack/decay/tail/choke vector, per-song rank/robust-z of those acoustic features, existing single-hit probability, score/confidence.\n'
      '- No review range, alternating parity, section label or song filename is a runtime input.\n'
      f'- Training labeled candidates: {len(rows)} (Open {int(y.sum())}, Closed {int(len(y)-y.sum())}).\n'
      '- Runtime threshold: >=0.55 Open, <=0.45 Closed; otherwise keep current articulation.\n'
    )
    print(json.dumps({'rows':len(rows),'open':int(y.sum()),'closed':int(len(y)-y.sum()),'stats':stats},indent=2))
if __name__=='__main__':main()
