from __future__ import annotations
import json, math
from pathlib import Path
import mido
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

ROOT=Path('.')
IN=ROOT/'drumscribe/experiments/results-hat-fusion-candidates-v60.json'
OUT=ROOT/'drumscribe/models/hat-articulation-fusion-v61.json'
REPORT=ROOT/'drumscribe/experiments/HAT_FUSION_MODEL_V61.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
FEATURES=['base_p','ctx_p','base_rank','ctx_rank','base_z','ctx_z','logit_diff','next_gap','score','confidence','current_open']

def parse_midi(path,shift):
    mid=mido.MidiFile(path);tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec+=msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=='set_tempo':tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0:out.append((sec+shift,msg.note))
    return out

def logit(p):
    p=min(.999999,max(.000001,float(p)))
    return math.log(p/(1-p))

def ranks(xs):
    order=np.argsort(xs);out=np.zeros(len(xs),dtype=float)
    if len(xs)<=1:return out
    for rank,i in enumerate(order):out[i]=rank/(len(xs)-1)
    return out

def robust_z(xs):
    a=np.asarray(xs,float);med=float(np.median(a));mad=float(np.median(np.abs(a-med)))
    scale=max(1e-6,1.4826*mad)
    return np.clip((a-med)/scale,-8,8),med,scale

def nearest_label(t,truth,tol=.08):
    best=None
    for u,n in truth:
        if n not in (42,46):continue
        d=abs(t-u)
        if d<=tol and (best is None or d<best[0]):best=(d,1 if n==46 else 0)
    return None if best is None else best[1]

def build_rows(song,data,truth):
    events=data['songs'][song]['events']
    art=[e for e in events if e['group'] in ('hat','open_hat','pedal_hat','ride')]
    art_times=[float(e['time']) for e in art]
    candidates=[e for e in events if e['group'] in ('hat','open_hat') and e.get('openHatProbability') is not None and e.get('hatContextProbability') is not None]
    bp=np.array([float(e['openHatProbability']) for e in candidates],float)
    cp=np.array([float(e['hatContextProbability']) for e in candidates],float)
    br=ranks(bp);cr=ranks(cp);bz,bmed,bscale=robust_z(bp);cz,cmed,cscale=robust_z(cp)
    rows=[]
    for i,e in enumerate(candidates):
        t=float(e['time'])
        if art_times:
            j=min(range(len(art_times)),key=lambda k:abs(art_times[k]-t))
            nt=art_times[j+1] if j+1<len(art_times) else None
        else:nt=None
        gap=min(1.5,max(0.,nt-t)) if nt is not None else 1.5
        label=nearest_label(t,truth)
        rows.append({
          'song':song,'time':t,'label':label,
          'base_p':bp[i],'ctx_p':cp[i],'base_rank':br[i],'ctx_rank':cr[i],
          'base_z':bz[i],'ctx_z':cz[i],'logit_diff':logit(cp[i])-logit(bp[i]),
          'next_gap':gap,'score':float(e.get('score') or 0),'confidence':float(e.get('confidence') or 0),
          'current_open':1.0 if e['group']=='open_hat' else 0.0
        })
    return rows,{'baseMedian':bmed,'baseScale':bscale,'contextMedian':cmed,'contextScale':cscale,'candidates':len(candidates)}

def serialize_tree(est):
    t=est.tree_
    # Leaf probability for class 1.
    prob1=[]
    for v in t.value:
        a=v[0]
        s=float(np.sum(a))
        prob1.append(float(a[1]/s) if s>0 and len(a)>1 else 0.0)
    return {
      'feature':t.feature.astype(int).tolist(),
      'threshold':[float(x) for x in t.threshold.tolist()],
      'left':t.children_left.astype(int).tolist(),
      'right':t.children_right.astype(int).tolist(),
      'prob1':prob1
    }

def main():
    data=json.loads(IN.read_text())
    rows=[];song_stats={};counts={'closed':0,'open':0}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth=parse_midi(ROOT/'DruMaster/songs'/song/'chart.mid',shift)
        rr,st=build_rows(song,data,truth)
        labeled=[r for r in rr if r['label'] is not None]
        rows.extend(labeled);song_stats[song]={**st,'labeled':len(labeled),'open':sum(r['label'] for r in labeled),'closed':sum(1-r['label'] for r in labeled)}
        counts['open']+=song_stats[song]['open'];counts['closed']+=song_stats[song]['closed']
    X=np.array([[float(r[f]) for f in FEATURES] for r in rows],float)
    y=np.array([int(r['label']) for r in rows],int)
    model=ExtraTreesClassifier(n_estimators=320,max_depth=10,min_samples_leaf=5,class_weight='balanced',max_features='sqrt',random_state=42,n_jobs=-1)
    model.fit(X,y)
    payload={
      'schema':1,'model':'hat-articulation-fusion-v61','date':'2026-09-24',
      'purpose':'per-hit open/closed hi-hat acoustic fusion; no pattern parity or review-song rule',
      'features':FEATURES,'treeCount':len(model.estimators_),
      'confidenceThreshold':0.55,'closedThreshold':0.45,
      'training':{
        'songs':SONGS,'labeledCandidates':len(rows),'classCounts':counts,
        'source':'five-song browser candidates; chart.mid used offline for labels only',
        'reviewSpecificInputsUsed':False,'songStats':song_stats,
        'validationReference':'experiments/HAT_FUSION_LOOCV_V60.md'
      },
      'trees':[serialize_tree(est) for est in model.estimators_]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n')
    REPORT.write_text(
      '# Hi-Hat Articulation Fusion Model v61\n\n'
      'Production model trained after five-song leave-one-song-out selection.\n\n'
      '- Inputs: existing single-hit Open probability + synchronized-corpus tail/choke probability + per-song rank/robust normalization + next-articulation gap.\n'
      '- No alternating parity, review range, song filename, or user review label is a runtime feature.\n'
      '- Teacher chart.mid is used only offline to label the five training songs.\n'
      f'- Labeled detected candidates: {len(rows)} (Closed {counts["closed"]}, Open {counts["open"]}).\n'
      '- Decision: probability >= 0.55 => Open, <= 0.45 => Closed; middle band keeps existing articulation.\n'
      '- Model family/hyperparameters were selected using five-song LOOCV in HAT_FUSION_LOOCV_V60.md.\n'
    )
    print(json.dumps({'labeled':len(rows),'counts':counts,'songs':song_stats,'trees':len(model.estimators_)},indent=2))

if __name__=='__main__':main()
