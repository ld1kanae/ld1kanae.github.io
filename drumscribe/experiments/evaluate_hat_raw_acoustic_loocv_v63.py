from __future__ import annotations
import json, math
from pathlib import Path
import mido
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path('.')
IN=ROOT/'drumscribe/experiments/results-hat-raw-acoustic-candidates-v63.json'
OUT=ROOT/'drumscribe/experiments/results-hat-raw-acoustic-loocv-v63.json'
MD=ROOT/'drumscribe/experiments/HAT_RAW_ACOUSTIC_LOOCV_V63.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
GROUPS={'kick':{35,36},'snare':{37,38,39,40},'tom':{41,43,45,47,48,50},'closed':{42},'open':{46},'ride':{51,53,59},'hatRide':{42,46,51,53,59}}

def parse_midi(path,shift):
    mid=mido.MidiFile(path);tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec+=msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=='set_tempo':tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0:out.append((sec+shift,msg.note))
    return out

def metric(pred,ref,tol=.08):
    pred=sorted(pred);ref=sorted(ref);used=set();tp=0
    for t in pred:
        best=None
        for j,x in enumerate(ref):
            if j in used:continue
            d=abs(t-x)
            if d<=tol and (best is None or d<best[0]):best=(d,j)
        if best is not None:used.add(best[1]);tp+=1
    p=len(pred);r=len(ref)
    return {'tp':tp,'pred':p,'ref':r,'precision':tp/p if p else 0.,'recall':tp/r if r else 0.,'f1':2*tp/(p+r) if p+r else 0.}

def aggregate(rows,key):
    tp=sum(r[key]['tp'] for r in rows);p=sum(r[key]['pred'] for r in rows);ref=sum(r[key]['ref'] for r in rows)
    return {'tp':tp,'pred':p,'ref':ref,'precision':tp/p if p else 0.,'recall':tp/ref if ref else 0.,'f1':2*tp/(p+ref) if p+ref else 0.}

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

def build_rows(song,data,truth):
    desc=data['songs'][song]['descriptors']
    if not desc:return []
    raw=np.array([d['vector'] for d in desc],float)
    base=np.array([float(d['openHatProbability']) for d in desc],float)
    raw_rank=np.stack([ranks(raw[:,j]) for j in range(raw.shape[1])],axis=1)
    raw_z=np.stack([robust_z(raw[:,j]) for j in range(raw.shape[1])],axis=1)
    base_rank=ranks(base);base_z=robust_z(base)
    rows=[]
    for i,d in enumerate(desc):
        y=nearest_label(float(d['time']),truth)
        rows.append({
          'song':song,'time':float(d['time']),'label':y,
          'current_open':1 if d['group']=='open_hat' else 0,
          'base_p':base[i],'base_rank':base_rank[i],'base_z':base_z[i],
          'score':float(d.get('score') or 0),'confidence':float(d.get('confidence') or 0),
          'raw':raw[i].tolist(),'raw_rank':raw_rank[i].tolist(),'raw_z':raw_z[i].tolist()
        })
    return rows

def macro_candidate(y,p):
    y=np.asarray(y,int);p=np.asarray(p,int);vals=[]
    for c in (0,1):
        tp=int(np.sum((y==c)&(p==c)));pp=int(np.sum(p==c));rr=int(np.sum(y==c))
        vals.append(2*tp/(pp+rr) if pp+rr else 0.)
    return sum(vals)/2

def apply(base,prob,hi):
    out=np.asarray(base,int).copy();out[prob>=hi]=1;out[prob<=1-hi]=0;return out

def choose_hi(y,base,prob):
    best=None
    for hi in (.55,.60,.65,.70,.75,.80,.85,.90,.95):
        p=apply(base,prob,hi);score=macro_candidate(y,p);changes=int(np.sum(p!=base))
        key=(score,-changes)
        if best is None or key>best[0]:best=(key,hi)
    return best[1]

def vec(r,variant):
    raw=np.array(r['raw'],float)
    if variant=='H1_raw':
        return raw
    if variant=='H2_raw_base':
        return np.r_[raw,[r['base_p'],r['score'],r['confidence'],r['current_open']]]
    if variant=='H3_raw_localnorm':
        return np.r_[raw,r['raw_rank'],r['raw_z'],[r['base_p'],r['base_rank'],r['base_z'],r['score'],r['confidence'],r['current_open']]]
    raise KeyError(variant)

def model(variant):
    if variant=='H1_raw':
        return Pipeline([('scale',StandardScaler()),('clf',LogisticRegression(max_iter=2500,class_weight='balanced',C=.7))])
    return ExtraTreesClassifier(n_estimators=420,max_depth=12,min_samples_leaf=4,class_weight='balanced',max_features='sqrt',random_state=42,n_jobs=-1)

def relabel(events,rows,pred):
    out=[dict(e) for e in events]
    # Match descriptor rows back by exact serialized time and current articulation.
    buckets={}
    for idx,e in enumerate(out):
        if e['group'] not in ('hat','open_hat'):continue
        buckets.setdefault(round(float(e['time']),9),[]).append(idx)
    for r,y in zip(rows,pred):
        arr=buckets.get(round(r['time'],9),[])
        if not arr:continue
        idx=arr[0]
        if y==1:
            out[idx]['group']='open_hat';out[idx]['note']=46
        else:
            out[idx]['group']='hat';out[idx]['note']=42
    return out

def score_events(events,truth):
    row={}
    for g,notes in GROUPS.items():
        row[g]=metric([float(e['time']) for e in events if int(e['note']) in notes],[t for t,n in truth if n in notes])
    row['hatMacroF1']=(row['closed']['f1']+row['open']['f1'])/2
    return row

def main():
    data=json.loads(IN.read_text())
    truth={};rows={}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth[song]=parse_midi(ROOT/'DruMaster/songs'/song/'chart.mid',shift)
        rows[song]=build_rows(song,data,truth[song])
    variants=['baseline','H1_raw','H2_raw_base','H3_raw_localnorm']
    result={'schema':1,'date':'2026-09-24','experiment':'hat-raw-acoustic-loocv-v63',
      'referencePolicy':'Each held-out song chart is scoring-only for that fold; model training uses only the other four songs.',
      'reviewSpecificInputsUsed':False,'variants':{}}
    per={v:{} for v in variants}
    for held in SONGS:
        train=[r for s in SONGS if s!=held for r in rows[s] if r['label'] is not None]
        test=rows[held]
        per['baseline'][held]=score_events(data['songs'][held]['events'],truth[held])
        y=np.array([r['label'] for r in train],int);base_tr=np.array([r['current_open'] for r in train],int)
        for variant in variants[1:]:
            X=np.array([vec(r,variant) for r in train],float)
            Xt=np.array([vec(r,variant) for r in test],float)
            m=model(variant);m.fit(X,y)
            ptr=m.predict_proba(X)[:,1];pte=m.predict_proba(Xt)[:,1]
            hi=choose_hi(y,base_tr,ptr)
            base_te=np.array([r['current_open'] for r in test],int)
            pred=apply(base_te,pte,hi)
            ev=relabel(data['songs'][held]['events'],test,pred)
            score=score_events(ev,truth[held]);score['model']={'confidenceThreshold':hi,'changes':int(np.sum(pred!=base_te))}
            per[variant][held]=score
    base_summary=None
    for variant in variants:
        rr=[per[variant][s] for s in SONGS]
        s={g:aggregate(rr,g) for g in GROUPS};s['hatMacroF1']=(s['closed']['f1']+s['open']['f1'])/2
        if variant=='baseline':base_summary=s
        result['variants'][variant]={'summary':s,'songs':per[variant]}
    for variant,v in result['variants'].items():
        d={g:v['summary'][g]['f1']-base_summary[g]['f1'] for g in GROUPS};d['hatMacroF1']=v['summary']['hatMacroF1']-base_summary['hatMacroF1']
        v['deltaVsBaseline']=d
        per_nonreg=all(v['songs'][s]['hatMacroF1']+1e-12>=result['variants']['baseline']['songs'][s]['hatMacroF1'] for s in SONGS)
        kst=all(abs(d[g])<1e-12 for g in ('kick','snare','tom'))
        v['guard']={'kstExactNonRegression':kst,'noPerSongHatMacroRegression':per_nonreg,'aggregateHatMacroImproved':d['hatMacroF1']>0,'passed':kst and per_nonreg and d['hatMacroF1']>0}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# Raw per-hit acoustic Hi-Hat LOOCV v63','',
      'No alternating-grid parity or review-specific label/range is used. Features are attack/decay/tail/choke acoustics extracted from each detected hit.','',
      '| variant | Closed F1 | Open F1 | HH macro | delta | guard |',
      '|---|---:|---:|---:|---:|---|']
    for v in variants:
        x=result['variants'][v];s=x['summary']
        lines.append(f"| {v} | {s['closed']['f1']:.6f} | {s['open']['f1']:.6f} | {s['hatMacroF1']:.6f} | {x['deltaVsBaseline']['hatMacroF1']:+.6f} | {x['guard']['passed']} |")
    lines+=['','Per-song HH macro:']
    for v in variants:
        lines.append('- '+v+': '+', '.join(f"{s}={result['variants'][v]['songs'][s]['hatMacroF1']:.6f}" for s in SONGS))
    MD.write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
if __name__=='__main__':main()
