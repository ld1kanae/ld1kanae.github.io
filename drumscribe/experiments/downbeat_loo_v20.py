import json, math
from pathlib import Path
from collections import defaultdict
import numpy as np
import mido
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

ROOT=Path('.')
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
GROUPS=['kick','snare','hat','pedal_hat','tom','crash','ride']
PITCH_GROUP={36:'kick',38:'snare',42:'hat',46:'hat',44:'pedal_hat',45:'tom',49:'crash',51:'ride'}

MODELS={
 'logistic': lambda: make_pipeline(StandardScaler(),LogisticRegression(C=.55,class_weight='balanced',max_iter=2500)),
 'extra_trees': lambda: ExtraTreesClassifier(n_estimators=180,max_depth=10,min_samples_leaf=5,class_weight='balanced',random_state=17,n_jobs=-1),
 'hist_gb': lambda: HistGradientBoostingClassifier(max_iter=160,max_depth=6,learning_rate=.055,l2_regularization=1.2,random_state=17),
}
PENALTIES=[.25,.45,.65]

def midi_notes(path):
    mid=mido.MidiFile(path);tempo=500000;t=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        t+=mido.tick2second(msg.time,mid.ticks_per_beat,tempo)
        if msg.type=='set_tempo':tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0 and msg.note in PITCH_GROUP:
            out.append((t,PITCH_GROUP[msg.note],msg.velocity/127))
    return out

def reference_bars(path,shift,duration):
    mid=mido.MidiFile(path);ppq=mid.ticks_per_beat
    tempos={0:500000};sigs={0:(4,4)};last=0
    for tr in mid.tracks:
        tick=0
        for msg in tr:
            tick+=msg.time;last=max(last,tick)
            if msg.type=='set_tempo':tempos[tick]=msg.tempo
            elif msg.type=='time_signature':sigs[tick]=(msg.numerator,msg.denominator)
    seg=[];sec=0.;prev=0;us=500000
    for tick,new in sorted(tempos.items()):
        sec+=(tick-prev)*us/1e6/ppq;seg.append((tick,sec,new));prev=tick;us=new
    def at(t):
        x=seg[0]
        for y in seg[1:]:
            if y[0]>t:break
            x=y
        return x
    def sec_at(t):
        x=at(t);return x[1]+(t-x[0])*x[2]/1e6/ppq
    ss=sorted((t,*v) for t,v in sigs.items());bars=[]
    for i,(start,n,d) in enumerate(ss):
        end=ss[i+1][0] if i+1<len(ss) else last+ppq*16
        step=ppq*n*4/d;t=float(start)
        while t<end-1e-6:
            ti=int(round(t));tm=sec_at(ti)+shift
            if 0<=tm<=duration:bars.append({'time':tm,'numerator':n,'denominator':d,'beatSec':at(ti)[2]/1e6})
            t+=step
    return bars

def beat_grid(side,duration):
    beat=60/float(side['bpm'])
    phase=float(side.get('beatPhaseSec',side['barPhaseSec']))
    # choose the beat-grid congruence that includes detected bar phase
    bar=float(side['barPhaseSec'])
    k=round((bar-phase)/beat);phase=phase+k*beat
    while phase>0:phase-=beat
    while phase+beat<=0:phase+=beat
    times=[];t=phase
    while t<=duration+2*beat:
        if t>=0:times.append(t)
        t+=beat
    return np.array(times,float),beat

def beat_event_matrix(notes,times,beat):
    # per-beat event aggregates, deliberately no modulo-4 feature
    base=np.zeros((len(times),len(GROUPS)*3),float)
    gi={g:i for i,g in enumerate(GROUPS)}
    for t,g,v in notes:
        if g not in gi:continue
        i=int(np.argmin(np.abs(times-t)))
        d=abs(times[i]-t)
        if d>.24*beat:continue
        j=gi[g]*3
        w=math.exp(-.5*(d/(.10*beat+1e-9))**2)
        base[i,j]+=1
        base[i,j+1]=max(base[i,j+1],v*w)
        base[i,j+2]+=v*w
    feats=[]
    for i in range(len(times)):
        row=[]
        # local context {-2,-1,0,+1,+2}, role-aware but meter-position agnostic
        for off in (-2,-1,0,1,2):
            k=min(len(times)-1,max(0,i+off))
            row.extend(base[k])
        # contrasts useful for downbeat accents / fill resolution
        cur=base[i]
        prev=base[max(0,i-1)]
        nxt=base[min(len(times)-1,i+1)]
        row.extend(cur-prev)
        row.extend(cur-.5*(prev+nxt))
        # local densities over 3 and 5 beats
        for radius in (1,2):
            a=max(0,i-radius);b=min(len(times),i+radius+1)
            row.extend(base[a:b].mean(axis=0))
        feats.append(row)
    return np.asarray(feats,float)

def labels_for(times,beat,ref):
    y=np.zeros(len(times),int)
    numerator=np.full(len(times),4,int)
    for i,t in enumerate(times):
        if not ref:continue
        r=min(ref,key=lambda z:abs(z['time']-t))
        if abs(r['time']-t)<=.20*beat:
            y[i]=1;numerator[i]=r['numerator']
    return y,numerator

def dp_meter(times,p,penalty3):
    # force first candidate to be a strong nearby start selected among first 4 beats
    eps=1e-5
    logits=np.log(np.clip(p,eps,1-eps)/(1-np.clip(p,eps,1-eps)))
    starts=list(range(min(4,len(times))))
    best=None
    n=len(times)
    for st in starts:
        dp={(st,0):(float(logits[st]),[])}
        for i in range(st,n):
            states=[(k,v) for k,v in dp.items() if k[0]==i]
            for (idx,last),(score,path) in states:
                for L in (4,3):
                    j=i+L
                    if j>=n:continue
                    s=score+float(logits[j])
                    if L==3:s-=penalty3
                    if path and last!=L:s-=.18
                    key=(j,L)
                    if key not in dp or s>dp[key][0]:dp[key]=(s,path+[L])
        target=n-1
        cand=[(abs(k[0]-target),-v[0],k,v) for k,v in dp.items() if k[0]>=n-7]
        if not cand:continue
        _,_,key,(score,path)=min(cand)
        candidate=(score,st,path)
        if best is None or candidate[0]>best[0]:best=candidate
    score,st,path=best
    bars=[];i=st
    # path stores lengths used to get to subsequent heads; start head's meter is first L
    for L in path:
        bars.append({'time':float(times[i]),'numerator':L,'denominator':4,'beatIndex':i,'prob':float(p[i])})
        i+=L
    if i<len(times):
        bars.append({'time':float(times[i]),'numerator':path[-1] if path else 4,'denominator':4,'beatIndex':i,'prob':float(p[i])})
    return bars

def score_bars(pred,ref):
    errs=[];tp=0;sig=0
    for r in ref:
        p=min(pred,key=lambda x:abs(x['time']-r['time'])) if pred else None
        e=abs(p['time']-r['time'])/r['beatSec'] if p else 99
        errs.append(e)
        if e<=.25:tp+=1
        if p and e<=.25 and p['numerator']==r['numerator']:sig+=1
    true3=[r for r in ref if r['numerator']==3]
    hit3=sum(any(abs(p['time']-r['time'])/r['beatSec']<=.25 and p['numerator']==3 for p in pred) for r in true3)
    false3=sum(1 for p in pred if p['numerator']==3 and all(abs(p['time']-r['time'])/r['beatSec']>.25 or r['numerator']!=3 for r in ref))
    return {
      'mean_abs_bar_error_beats':float(np.mean(errs)),
      'p95_abs_bar_error_beats':float(np.percentile(errs,95)),
      'max_abs_bar_error_beats':float(np.max(errs)),
      'bar_recall_025':tp/len(ref),
      'signature_bar_accuracy_025':sig/len(ref),
      'three_four_recall':hit3/len(true3) if true3 else None,
      'false_three_four_bars':false3,
      'pred_three_four_bars':sum(p['numerator']==3 for p in pred),
      'ref_three_four_bars':len(true3)
    }

data={}
for song in SONGS:
    meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
    side=json.loads((ROOT/'drumscribe/experiments/generated-v2-browser'/f'{song}.json').read_text())
    notes=midi_notes(ROOT/'drumscribe/experiments/generated-v2-browser'/f'{song}.mid')
    exp=float(side.get('exportOffsetSec',0) or 0)
    notes=[(t-exp,g,v) for t,g,v in notes]
    duration=float(meta['duration'])
    times,beat=beat_grid(side,duration)
    X=beat_event_matrix(notes,times,beat)
    shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
    ref=reference_bars(ROOT/'DruMaster/songs'/song/'chart.mid',shift,duration)
    y,num=labels_for(times,beat,ref)
    data[song]={'X':X,'y':y,'times':times,'beat':beat,'ref':ref}

out={'schema':1,'description':'Nested leave-one-song-out downbeat classifier from predicted drum events. Held chart MIDI is scoring-only. Models train only on the other songs.','candidates':{}}
for model_name,factory in MODELS.items():
    for penalty in PENALTIES:
        key=f'{model_name}_p{penalty:.2f}'
        songs={};agg=[]
        for held in SONGS:
            train=[s for s in SONGS if s!=held]
            X=np.vstack([data[s]['X'] for s in train]);y=np.concatenate([data[s]['y'] for s in train])
            model=factory();model.fit(X,y)
            if hasattr(model,'predict_proba'):
                p=model.predict_proba(data[held]['X'])[:,1]
            else:
                z=model.decision_function(data[held]['X']);p=1/(1+np.exp(-z))
            pred=dp_meter(data[held]['times'],p,penalty)
            sc=score_bars(pred,data[held]['ref'])
            sc['mean_downbeat_prob']=float(np.mean(p))
            sc['top_prob']=float(np.max(p))
            songs[held]=sc;agg.append(sc)
        valid=[x for x in agg if x['three_four_recall'] is not None]
        out['candidates'][key]={
          'model':model_name,'penalty3':penalty,'songs':songs,
          'summary':{
            'mean_bar_error_beats':float(np.mean([x['mean_abs_bar_error_beats'] for x in agg])),
            'mean_bar_recall_025':float(np.mean([x['bar_recall_025'] for x in agg])),
            'mean_signature_accuracy_025':float(np.mean([x['signature_bar_accuracy_025'] for x in agg])),
            'three_four_recall':float(np.mean([x['three_four_recall'] for x in valid])) if valid else None,
            'false_three_four_bars':sum(x['false_three_four_bars'] for x in agg)
          }
        }

# rank with a conservative metric: structure accuracy first, false 3/4 penalty
for k,v in out['candidates'].items():
    s=v['summary']
    s['objective']=s['mean_signature_accuracy_025']-.012*s['false_three_four_bars']-.08*s['mean_bar_error_beats']
out['ranking']=sorted(out['candidates'],key=lambda k:out['candidates'][k]['summary']['objective'],reverse=True)
print(json.dumps({'ranking':out['ranking'][:8],'top':{k:out['candidates'][k] for k in out['ranking'][:3]}},ensure_ascii=False,indent=2))
(ROOT/'drumscribe/experiments/results-downbeat-loo-v20.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
