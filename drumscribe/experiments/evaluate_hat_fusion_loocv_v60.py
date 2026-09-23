from __future__ import annotations
import json, math
from pathlib import Path
from collections import defaultdict

import mido
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path('.')
IN=ROOT/'drumscribe/experiments/results-hat-fusion-candidates-v60.json'
OUT=ROOT/'drumscribe/experiments/results-hat-fusion-loocv-v60.json'
MD=ROOT/'drumscribe/experiments/HAT_FUSION_LOOCV_V60.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
GROUPS={'kick':{35,36},'snare':{37,38,39,40},'tom':{41,43,45,47,48,50},'closed':{42},'open':{46},'ride':{51,53,59},'hatRide':{42,46,51,53,59}}
FEATURES=['base_p','ctx_p','base_rank','ctx_rank','base_z','ctx_z','logit_diff','next_gap','score','confidence','current_open']

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

def logit(p):
    p=min(.999999,max(.000001,float(p)))
    return math.log(p/(1-p))

def ranks(xs):
    order=np.argsort(xs);out=np.zeros(len(xs),dtype=float)
    if len(xs)<=1:return out
    for rank,i in enumerate(order):out[i]=rank/(len(xs)-1)
    return out

def robust_z(xs):
    a=np.asarray(xs,float);med=np.median(a);mad=np.median(np.abs(a-med))
    scale=max(1e-6,1.4826*mad)
    return np.clip((a-med)/scale,-8,8)

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
    next_time={}
    for i,e in enumerate(art):next_time[id(e)]=art[i+1]['time'] if i+1<len(art) else None
    candidates=[e for e in events if e['group'] in ('hat','open_hat') and e.get('openHatProbability') is not None and e.get('hatContextProbability') is not None]
    bp=np.array([float(e['openHatProbability']) for e in candidates],float)
    cp=np.array([float(e['hatContextProbability']) for e in candidates],float)
    br=ranks(bp);cr=ranks(cp);bz=robust_z(bp);cz=robust_z(cp)
    rows=[]
    # Map event identity by (time,note,group) because serialized objects are distinct.
    art_times=[float(e['time']) for e in art]
    for i,e in enumerate(candidates):
        t=float(e['time'])
        j=min(range(len(art_times)),key=lambda k:abs(art_times[k]-t)) if art_times else -1
        nt=art_times[j+1] if j>=0 and j+1<len(art_times) else None
        gap=min(1.5,max(0.,nt-t)) if nt is not None else 1.5
        row={
          'song':song,'time':t,'label':nearest_label(t,truth),
          'base_p':bp[i],'ctx_p':cp[i],'base_rank':br[i],'ctx_rank':cr[i],
          'base_z':bz[i],'ctx_z':cz[i],'logit_diff':logit(cp[i])-logit(bp[i]),
          'next_gap':gap,'score':float(e.get('score') or 0),'confidence':float(e.get('confidence') or 0),
          'current_open':1.0 if e['group']=='open_hat' else 0.0,
          'event_index':events.index(e)
        }
        rows.append(row)
    return rows

def candidate_macro(y,pred):
    y=np.asarray(y,int);pred=np.asarray(pred,int)
    vals=[]
    for cls in (0,1):
        tp=int(np.sum((y==cls)&(pred==cls)));pp=int(np.sum(pred==cls));rr=int(np.sum(y==cls))
        vals.append(2*tp/(pp+rr) if pp+rr else 0.)
    return sum(vals)/2

def apply_with_confidence(base,prob,hi):
    out=np.asarray(base,int).copy()
    out[prob>=hi]=1
    out[prob<=1-hi]=0
    return out

def choose_hi(y,base,prob):
    best=None
    for hi in (.55,.60,.65,.70,.75,.80,.85,.90,.95):
        pred=apply_with_confidence(base,prob,hi);score=candidate_macro(y,pred)
        changes=int(np.sum(pred!=base))
        key=(score,-changes)
        if best is None or key>best[0]:best=(key,hi)
    return best[1]

def model_prob(kind,Xtr,ytr,Xte):
    if kind=='logistic':
        m=Pipeline([('scale',StandardScaler()),('clf',LogisticRegression(max_iter=2000,class_weight='balanced',C=.7))])
    else:
        m=ExtraTreesClassifier(n_estimators=320,max_depth=10,min_samples_leaf=5,class_weight='balanced',max_features='sqrt',random_state=42,n_jobs=-1)
    m.fit(Xtr,ytr)
    return m.predict_proba(Xtr)[:,1],m.predict_proba(Xte)[:,1]

def fusion_prob(rows,w,bias):
    vals=[]
    for r in rows:
        z=w*logit(r['base_p'])+(1-w)*logit(r['ctx_p'])+bias
        vals.append(1/(1+math.exp(-max(-30,min(30,z)))))
    return np.asarray(vals)

def choose_fusion(train):
    y=np.array([r['label'] for r in train],int);base=np.array([int(r['current_open']) for r in train],int)
    best=None
    for w in np.linspace(0,1,11):
        for bias in np.linspace(-1.5,1.5,13):
            p=fusion_prob(train,float(w),float(bias))
            hi=choose_hi(y,base,p);pred=apply_with_confidence(base,p,hi)
            score=candidate_macro(y,pred);changes=int(np.sum(pred!=base))
            key=(score,-changes)
            if best is None or key>best[0]:best=(key,float(w),float(bias),float(hi))
    return best[1:]

def relabel_events(events,row_by_index,pred):
    out=[dict(e) for e in events]
    for r,y in zip(row_by_index,pred):
        idx=r['event_index']
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
    truth={}
    all_rows={}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth[song]=parse_midi(ROOT/'DruMaster/songs'/song/'chart.mid',shift)
        all_rows[song]=build_rows(song,data,truth[song])
    variants={'baseline':{},'H1_logistic':{},'H2_extratrees':{},'H3_logit_fusion':{}}
    fold_meta={}
    for held in SONGS:
        train=[r for s in SONGS if s!=held for r in all_rows[s] if r['label'] is not None]
        test=all_rows[held]
        test_labeled=[r for r in test if r['label'] is not None]
        Xtr=np.array([[r[f] for f in FEATURES] for r in train],float);ytr=np.array([r['label'] for r in train],int)
        Xte=np.array([[r[f] for f in FEATURES] for r in test],float)
        base_tr=np.array([int(r['current_open']) for r in train],int)
        base_te=np.array([int(r['current_open']) for r in test],int)
        fold_meta[held]={'trainLabeled':len(train),'testCandidates':len(test),'testLabeled':len(test_labeled)}
        variants['baseline'][held]=score_events(data['songs'][held]['events'],truth[held])
        for name,kind in [('H1_logistic','logistic'),('H2_extratrees','extratrees')]:
            ptr,pte=model_prob(kind,Xtr,ytr,Xte)
            hi=choose_hi(ytr,base_tr,ptr)
            pred=apply_with_confidence(base_te,pte,hi)
            ev=relabel_events(data['songs'][held]['events'],test,pred)
            m=score_events(ev,truth[held]);m['model']={'confidenceThreshold':hi,'changes':int(np.sum(pred!=base_te))}
            variants[name][held]=m
        w,bias,hi=choose_fusion(train)
        pte=fusion_prob(test,w,bias);pred=apply_with_confidence(base_te,pte,hi)
        ev=relabel_events(data['songs'][held]['events'],test,pred)
        m=score_events(ev,truth[held]);m['model']={'baseWeight':w,'contextWeight':1-w,'bias':bias,'confidenceThreshold':hi,'changes':int(np.sum(pred!=base_te))}
        variants['H3_logit_fusion'][held]=m

    result={'schema':1,'date':'2026-09-24','experiment':'hat-fusion-loocv-v60',
      'predictionReferencePolicy':'browser candidates generated without chart.mid; each held-out song chart is used only after a model is fit on the other four songs.',
      'reviewSpecificInputsUsed':False,'features':FEATURES,'folds':fold_meta,'variants':{}}
    base_summary=None
    for name,rows_by_song in variants.items():
        rows=[rows_by_song[s] for s in SONGS]
        summary={g:aggregate(rows,g) for g in GROUPS};summary['hatMacroF1']=(summary['closed']['f1']+summary['open']['f1'])/2
        if name=='baseline':base_summary=summary
        result['variants'][name]={'summary':summary,'songs':rows_by_song}
    for name,v in result['variants'].items():
        s=v['summary'];d={g:s[g]['f1']-base_summary[g]['f1'] for g in GROUPS};d['hatMacroF1']=s['hatMacroF1']-base_summary['hatMacroF1']
        v['deltaVsBaseline']=d
        per_nonreg=all(v['songs'][song]['hatMacroF1']+1e-12>=result['variants']['baseline']['songs'][song]['hatMacroF1'] for song in SONGS)
        kst=all(abs(d[g])<1e-12 for g in ('kick','snare','tom'))
        v['guard']={'kstExactNonRegression':kst,'noPerSongHatMacroRegression':per_nonreg,'aggregateHatMacroImproved':d['hatMacroF1']>0,'passed':kst and per_nonreg and d['hatMacroF1']>0}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# Five-song held-out Hi-Hat fusion v60','',
      'Review-song labels/ranges are not used. Each song is held out while the other four songs train the articulation fusion.','',
      '| variant | Closed F1 | Open F1 | HH macro | delta | K delta | S delta | T delta | guard |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for name,v in result['variants'].items():
        s=v['summary'];d=v['deltaVsBaseline']
        lines.append(f"| {name} | {s['closed']['f1']:.6f} | {s['open']['f1']:.6f} | {s['hatMacroF1']:.6f} | {d['hatMacroF1']:+.6f} | {d['kick']:+.6f} | {d['snare']:+.6f} | {d['tom']:+.6f} | {v['guard']['passed']} |")
    lines+=['','Per-song HH macro:']
    for name,v in result['variants'].items():
        lines.append('- '+name+': '+', '.join(f"{s}={v['songs'][s]['hatMacroF1']:.6f}" for s in SONGS))
    lines+=['','- Candidate features are audio/runtime-derived only.','- K/S/T exact non-regression is mandatory.','- No specific review song is used for training or threshold selection.','']
    MD.write_text('\n'.join(lines))
    print('\n'.join(lines))
if __name__=='__main__':main()
