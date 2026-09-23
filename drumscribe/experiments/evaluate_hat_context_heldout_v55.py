from __future__ import annotations
import json
from pathlib import Path
import mido

ROOT=Path('.');EXP=ROOT/'drumscribe/experiments'
IN=EXP/'results-hat-context-heldout-predictions-v55.json'
OUT=EXP/'results-hat-context-heldout-v55.json'
MD=EXP/'HAT_CONTEXT_HELDOUT_V55.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
SETS={'closed':{42},'open':{46},'ride':{51,53,59},'kick':{35,36},'snare':{37,38,39,40},'tom':{41,43,45,47,48,50},'crash':{49,52,55,57},'pedal_hat':{44}}
THRESHOLDS=[.70,.80,.85,.90,.93,.95,.97,.98,.99]
MODES=['hat-rescue','ride-rescue','both']

def midi_events(path,shift=0.0):
    mid=mido.MidiFile(path);tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=='set_tempo':tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0:out.append((sec+shift,msg.note))
    return out

def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        opts=[(abs(t-u),j) for j,u in enumerate(ref) if j not in used and abs(t-u)<=w]
        if opts:
            _,j=min(opts);used.add(j);tp+=1
    return tp

def metric(pred,ref):
    tp=greedy(pred,ref);p=len(pred);r=len(ref)
    return {'tp':tp,'predicted':p,'reference':r,'precision':tp/p if p else 0.,'recall':tp/r if r else 0.,'f1':2*tp/(p+r) if p+r else 0.}

def aggregate(rows,key):
    tp=sum(r[key]['tp'] for r in rows);p=sum(r[key]['predicted'] for r in rows);ref=sum(r[key]['reference'] for r in rows)
    return {'tp':tp,'predicted':p,'reference':ref,'precision':tp/p if p else 0.,'recall':tp/ref if ref else 0.,'f1':2*tp/(p+ref) if p+ref else 0.}

def apply(events,mode,threshold):
    out=[]
    for e in events:
        x=dict(e);g=x['group'];p=x.get('hatContextProbability')
        if p is not None and float(p)>=threshold:
            if mode in ('hat-rescue','both') and g=='hat': x['group']='open_hat';x['note']=46
            if mode in ('ride-rescue','both') and g=='ride': x['group']='open_hat';x['note']=46
        out.append(x)
    return out

def score_song(ev,truth):
    r={}
    for k in ('closed','open','ride','kick','snare','tom','crash','pedal_hat'):
        pn={42} if k=='closed' else ({46} if k=='open' else ({51} if k=='ride' else SETS[k]))
        pred=[float(e['time']) for e in ev if int(e['note']) in pn]
        ref=[t for t,n in truth if n in SETS[k]]
        r[k]=metric(pred,ref)
    pred=[float(e['time']) for e in ev if int(e['note']) in {42,46,51}]
    ref=[t for t,n in truth if n in SETS['closed']|SETS['open']|SETS['ride']]
    r['hatRideOnset']=metric(pred,ref)
    r['hatMacroF1']=(r['closed']['f1']+r['open']['f1'])/2
    return r

def main():
    data=json.loads(IN.read_text());truth={}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster'/'songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth[song]=midi_events(ROOT/'DruMaster'/'songs'/song/'chart.mid',shift)
    variants={'baseline':{}}
    for song in SONGS: variants['baseline'][song]=score_song(data['songs'][song]['events'],truth[song])
    for mode in MODES:
        for th in THRESHOLDS:
            name=f'{mode}@{th:.2f}';variants[name]={}
            for song in SONGS:
                ev=apply(data['songs'][song]['events'],mode,th)
                variants[name][song]=score_song(ev,truth[song])
    report={'schema':1,'date':'2026-09-23','experiment':'hat-context-heldout-v55',
      'training_policy':'For each song, context logistic weights were trained on the other four synchronized pairs.',
      'reference_policy':'Held song chart.mid used only for scoring after browser prediction.',
      'variants':{}}
    for name,by_song in variants.items():
        rows=[{'song':s,**by_song[s]} for s in SONGS]
        s={k:aggregate(rows,k) for k in ('closed','open','ride','kick','snare','tom','crash','pedal_hat','hatRideOnset')}
        s['hatMacroF1']=(s['closed']['f1']+s['open']['f1'])/2
        report['variants'][name]={'summary':s,'songs':rows}
    base=report['variants']['baseline']['summary']
    for name,v in report['variants'].items():
        x=v['summary'];v['deltaVsBaseline']={k:x[k]['f1']-base[k]['f1'] for k in ('closed','open','ride','kick','snare','tom','hatRideOnset')}
        v['deltaVsBaseline']['hatMacroF1']=x['hatMacroF1']-base['hatMacroF1']
    eligible=[]
    for name,v in report['variants'].items():
        if name=='baseline':continue
        s=v['summary'];d=v['deltaVsBaseline']
        if d['kick']==0 and d['snare']==0 and d['tom']==0 and d['hatRideOnset']>=-1e-12 and d['hatMacroF1']>0:
            eligible.append((s['hatMacroF1'],s['open']['f1'],name))
    eligible.sort(reverse=True)
    report['bestEligible']=eligible[0][2] if eligible else None
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Hat context held-out v55','',
      'Each held song uses a context logistic model trained on the other four synchronized WAV/MIDI pairs. Runtime sees only audio + generated events; chart.mid is scoring-only.','',
      f"Best eligible: **{report['bestEligible']}**" if report['bestEligible'] else 'No variant passed the non-regression guard.','',
      '| variant | closed F1 | open F1 | ride F1 | HH macro | collapsed onset | ΔHH macro |',
      '|---|---:|---:|---:|---:|---:|---:|']
    show=['baseline']+[f'{m}@{t:.2f}' for m in MODES for t in (.80,.90,.95,.98,.99)]
    for name in show:
        x=report['variants'][name]['summary'];d=report['variants'][name]['deltaVsBaseline']
        lines.append(f"| {name} | {x['closed']['f1']:.6f} | {x['open']['f1']:.6f} | {x['ride']['f1']:.6f} | {x['hatMacroF1']:.6f} | {x['hatRideOnset']['f1']:.6f} | {d['hatMacroF1']:+.6f} |")
    lines+=['','Guard: K/S/T unchanged, collapsed onset non-regression, HH macro improvement. Threshold sweep is development analysis; any production threshold remains subject to fresh validation on new paired songs.','']
    MD.write_text('\n'.join(lines));print('\n'.join(lines))
if __name__=='__main__':main()
