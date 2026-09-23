from __future__ import annotations
import json
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
import mido
from sklearn.ensemble import RandomForestClassifier

ROOT=Path('.')
IN=ROOT/'drumscribe/experiments/results-hat-raw-acoustic-candidates-v68.json'
MODEL=ROOT/'drumscribe/models/hat-mp3-domain-rf-v68.json'
OUT=ROOT/'drumscribe/experiments/results-hat-mp3-domain-loocv-v68.json'
MD=ROOT/'drumscribe/experiments/HAT_MP3_DOMAIN_LOOCV_V68.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
METAL={42:'closed',44:'pedal',46:'open',49:'crash',51:'ride',53:'ride',55:'crash',57:'crash',59:'ride'}
NOTES={'closed':{42},'open':{46}}
THRESHOLD=.65

def parse_midi(path,shift):
    mid=mido.MidiFile(path);tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec+=msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=='set_tempo': tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0: out.append((sec+shift,msg.note))
    return out

def truth_for(song):
    meta=json.loads((ROOT/'DruMaster'/'songs'/song/'song.json').read_text())
    shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
    return parse_midi(ROOT/'DruMaster'/'songs'/song/'chart.mid',shift)

def ranks(a):
    a=np.asarray(a,float);out=np.zeros(len(a))
    if len(a)<=1:return out
    order=np.argsort(a,kind='stable')
    for r,i in enumerate(order):out[i]=r/(len(a)-1)
    return out

def robust_z(a):
    a=np.asarray(a,float);med=np.median(a);mad=np.median(np.abs(a-med));scale=max(1e-6,1.4826*mad)
    return np.clip((a-med)/scale,-8,8)

def greedy_labels(desc,truth,tol=.08):
    refs=[(t,n) for t,n in truth if n in METAL]
    used=set();labels=[]
    for d in desc:
        t=float(d['time']);best=None
        for j,(u,n) in enumerate(refs):
            if j in used:continue
            dist=abs(t-u)
            if dist<=tol and (best is None or dist<best[0]):best=(dist,j,n)
        if best is None:labels.append('false')
        else:
            used.add(best[1]);labels.append(METAL[best[2]])
    return labels

def make_rows(song,data,truth):
    desc=data['songs'][song]['descriptors']
    labels=greedy_labels(desc,truth)
    raw=np.asarray([d['vector'] for d in desc],float)
    base=np.asarray([float(d['openHatProbability']) for d in desc],float)
    rr=np.stack([ranks(raw[:,j]) for j in range(raw.shape[1])],axis=1)
    rz=np.stack([robust_z(raw[:,j]) for j in range(raw.shape[1])],axis=1)
    br=ranks(base);bz=robust_z(base)
    rows=[]
    for i,d in enumerate(desc):
        x=np.r_[raw[i],rr[i],rz[i],[base[i],br[i],bz[i],float(d.get('score') or 0),float(d.get('confidence') or 0),1 if d['group']=='open_hat' else 0]]
        rows.append({'song':song,'time':float(d['time']),'label':labels[i],'x':x.tolist(),'current_open':1 if d['group']=='open_hat' else 0})
    return rows

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
    return {'tp':tp,'pred':p,'ref':r,'f1':2*tp/(p+r) if p+r else 0.}

def score(events,truth):
    out={}
    for key,notes in NOTES.items():
        out[key]=metric([float(e['time']) for e in events if int(e['note']) in notes],[t for t,n in truth if n in notes])
    out['hatMacroF1']=(out['closed']['f1']+out['open']['f1'])/2
    return out

def relabel(events,rows,pred):
    out=[dict(e) for e in events]; buckets=defaultdict(list)
    for i,e in enumerate(out):
        if e['group'] in ('hat','open_hat'): buckets[round(float(e['time']),9)].append(i)
    for r,y in zip(rows,pred):
        arr=buckets.get(round(float(r['time']),9),[])
        if not arr:continue
        i=arr[0]
        out[i]['group']='open_hat' if y else 'hat';out[i]['note']=46 if y else 42
    return out

def forest(seed=42):
    return RandomForestClassifier(n_estimators=48,max_depth=9,min_samples_leaf=3,class_weight='balanced',max_features='sqrt',random_state=seed,n_jobs=-1)

def apply(base,p):
    y=np.asarray(base,int).copy();y[p>=THRESHOLD]=1;y[p<=1-THRESHOLD]=0;return y

def serialize_tree(est,dec=6):
    t=est.tree_;probs=[]
    for v in t.value[:,0,:]:
        den=float(v.sum());probs.append(round(float(v[1]/den) if den else 0.,dec))
    return {'feature':t.feature.astype(int).tolist(),
      'threshold':[round(float(x),dec) if x!=-2 else -2 for x in t.threshold],
      'left':t.children_left.astype(int).tolist(),'right':t.children_right.astype(int).tolist(),'prob1':probs}

def aggregate(rows,key):
    tp=sum(r[key]['tp'] for r in rows);p=sum(r[key]['pred'] for r in rows);ref=sum(r[key]['ref'] for r in rows)
    return 2*tp/(p+ref) if p+ref else 0.

def main():
    data=json.loads(IN.read_text());truth={s:truth_for(s) for s in SONGS};rows={s:make_rows(s,data,truth[s]) for s in SONGS}
    base={s:score(data['songs'][s]['events'],truth[s]) for s in SONGS}
    held={}
    for song in SONGS:
        tr=[r for s in SONGS if s!=song for r in rows[s]];te=rows[s]
        X=np.asarray([r['x'] for r in tr],float);y=np.asarray([r['label']=='open' for r in tr],int)
        Xt=np.asarray([r['x'] for r in te],float);m=forest();m.fit(X,y)
        pred=apply([r['current_open'] for r in te],m.predict_proba(Xt)[:,1])
        held[song]=score(relabel(data['songs'][song]['events'],te,pred),truth[song])
    base_rows=[base[s] for s in SONGS];held_rows=[held[s] for s in SONGS]
    bclosed=aggregate(base_rows,'closed');bopen=aggregate(base_rows,'open');bmacro=(bclosed+bopen)/2
    hclosed=aggregate(held_rows,'closed');hopen=aggregate(held_rows,'open');hmacro=(hclosed+hopen)/2
    per_nonreg=all(held[s]['hatMacroF1']+1e-12>=base[s]['hatMacroF1'] for s in SONGS)

    # Seed stability is selection evidence, not held-out test reuse for a single seed.
    seed_guard={}
    for seed in range(10):
        ok=True;min_delta=1.
        for song in SONGS:
            tr=[r for s in SONGS if s!=song for r in rows[s]];te=rows[s]
            X=np.asarray([r['x'] for r in tr],float);y=np.asarray([r['label']=='open' for r in tr],int)
            Xt=np.asarray([r['x'] for r in te],float);m=forest(seed);m.fit(X,y)
            pred=apply([r['current_open'] for r in te],m.predict_proba(Xt)[:,1])
            sc=score(relabel(data['songs'][song]['events'],te,pred),truth[song])
            delta=sc['hatMacroF1']-base[song]['hatMacroF1'];min_delta=min(min_delta,delta)
            if delta < -1e-12:ok=False
        seed_guard[str(seed)]={'allSongsNonRegressing':ok,'minSongDelta':min_delta}

    allrows=[r for s in SONGS for r in rows[s]]
    X=np.asarray([r['x'] for r in allrows],float);y=np.asarray([r['label']=='open' for r in allrows],int)
    final=forest(42);final.fit(X,y)
    features=[f'raw{i}' for i in range(14)]+[f'rank{i}' for i in range(14)]+[f'z{i}' for i in range(14)]+['base_p','base_rank','base_z','score','confidence','current_open']
    model={'schema':1,'name':'hat-mp3-domain-rf-v68','date':'2026-09-24','features':features,
      'treeCount':48,'maxDepth':9,'minSamplesLeaf':3,'classWeight':'balanced','maxFeatures':'sqrt','randomState':42,
      'confidenceThreshold':THRESHOLD,'closedThreshold':1-THRESHOLD,'trainingSongs':SONGS,'trainingRows':len(allrows),
      'positiveClass':'open','negativeClasses':['closed','pedal','ride','crash','false'],
      'reviewSpecificInputsUsed':False,'patternParityUsed':False,
      'featureDesignSource':'synchronized WAV/MIDI tail/choke study; classifier fitted on repository MP3 DrumScribe candidate domain',
      'loocv':{'baselineClosedF1':bclosed,'baselineOpenF1':bopen,'baselineHatMacroF1':bmacro,
        'closedF1':hclosed,'openF1':hopen,'hatMacroF1':hmacro,'allFiveSongsNonRegressing':per_nonreg},
      'seedStability':seed_guard,'trees':[serialize_tree(e) for e in final.estimators_],'quantizedDecimals':6}
    MODEL.write_text(json.dumps(model,separators=(',',':'))+'\n')

    result={'schema':1,'experiment':'hat-mp3-domain-loocv-v68','threshold':THRESHOLD,
      'candidateCounts':{s:len(rows[s]) for s in SONGS},
      'labelCounts':{s:dict(Counter(r['label'] for r in rows[s])) for s in SONGS},
      'baseline':{'closedF1':bclosed,'openF1':bopen,'hatMacroF1':bmacro,'songs':base},
      'heldout':{'closedF1':hclosed,'openF1':hopen,'hatMacroF1':hmacro,'songs':held},
      'allFiveSongsNonRegressing':per_nonreg,'seedStability':seed_guard}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# MP3-domain Hi-Hat candidate LOOCV v68','',
      'Synchronized WAV/MIDI data established the attack/decay/tail/choke feature family. Direct WAV->MP3 transfer failed in v66/v67, so the production classifier is fitted on repository MP3 DrumScribe candidates. Each validation fold excludes the held-out song completely.','',
      f'- candidates: {sum(len(rows[s]) for s in SONGS)}',
      '- model: RandomForest 48 trees / depth 9 / min leaf 3 / balanced / sqrt',
      '- fixed decision band: Open >= 0.65, Closed <= 0.35, otherwise keep current articulation',
      f'- aggregate Closed F1: {bclosed:.6f} -> **{hclosed:.6f}**',
      f'- aggregate Open F1: {bopen:.6f} -> **{hopen:.6f}**',
      f'- aggregate HH macro: {bmacro:.6f} -> **{hmacro:.6f}** ({hmacro-bmacro:+.6f})',
      f'- all five held-out songs non-regressing: **{per_nonreg}**','',
      'Per-song HH macro:']
    for s in SONGS:lines.append(f"- {s}: {base[s]['hatMacroF1']:.6f} -> **{held[s]['hatMacroF1']:.6f}** ({held[s]['hatMacroF1']-base[s]['hatMacroF1']:+.6f})")
    lines+=['','Seed stability (same fixed hyperparameters/threshold):']
    for seed,v in seed_guard.items():lines.append(f"- seed {seed}: all-five non-regressing={v['allSongsNonRegressing']}, min song delta={v['minSongDelta']:+.6f}")
    lines+=['','The final serialized model is trained on all five MP3 candidate sets only after the song-held-out configuration is fixed. A subsequent five-song production replay is an implementation check, not independent generalization evidence.','']
    MD.write_text('\n'.join(lines))
    print('\n'.join(lines))

if __name__=='__main__':main()
