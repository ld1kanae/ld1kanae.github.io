from __future__ import annotations
import json
from pathlib import Path
import mido
ROOT=Path('.');EXP=ROOT/'drumscribe/experiments';SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
D=EXP/'generated-openhat-combined-v44'
def midi_events(path):
    mid=mido.MidiFile(path);tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=='set_tempo': tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0:
            group='other'
            out.append((sec,group,msg.note))
    return out
def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        cand=[(abs(t-u),j) for j,u in enumerate(ref) if j not in used and abs(t-u)<=w]
        if cand:
            _,j=min(cand);used.add(j);tp+=1
    return tp
def metric(pred,ref):
    tp=greedy(pred,ref);p=len(pred);r=len(ref)
    return {'tp':tp,'predicted':p,'reference':r,'precision':tp/p if p else 0.,'recall':tp/r if r else 0.,'f1':2*tp/(p+r) if p+r else 0.}
def times(evts,notes,shift=0):return sorted(t+shift for t,g,n in evts if n in notes)
rows=[]
for song in SONGS:
    side=json.loads((D/f'{song}.json').read_text())
    meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
    export=float(side.get('exportOffsetSec',0) or 0);shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
    pred=midi_events(D/f'{song}.mid');truth=midi_events(ROOT/'DruMaster/songs'/song/'chart.mid')
    r={'song':song}
    for name,pnotes,rnotes in [('closed',{42},{42}),('open',{46},{46}),('kick',{36},{35,36}),('snare',{38},{37,38,39,40}),('tom',{45},{41,43,45,47,48,50})]:
        r[name]=metric(times(pred,pnotes,-export),times(truth,rnotes,shift))
    r['macroHatF1']=(r['closed']['f1']+r['open']['f1'])/2
    rows.append(r)
def agg(k):
    tp=sum(r[k]['tp'] for r in rows);p=sum(r[k]['predicted'] for r in rows);ref=sum(r[k]['reference'] for r in rows)
    return {'tp':tp,'predicted':p,'reference':ref,'precision':tp/p if p else 0.,'recall':tp/ref if ref else 0.,'f1':2*tp/(p+ref) if p+ref else 0.}
summary={k:agg(k) for k in ('closed','open','kick','snare','tom')};summary['macroHatF1']=(summary['closed']['f1']+summary['open']['f1'])/2
baseline=json.loads((EXP/'results-openhat-v40.json').read_text())['variants']['base']['summary']
delta={'macroHatF1':summary['macroHatF1']-baseline['macroHatF1'],
 'closedF1':summary['closed']['f1']-baseline['closed']['f1'],'openF1':summary['open']['f1']-baseline['open']['f1'],
 'kickF1':summary['kick']['f1']-baseline['kick']['f1'],'snareF1':summary['snare']['f1']-baseline['snare']['f1'],'tomF1':summary['tom']['f1']-baseline['tom']['f1']}
out={'schema':1,'date':'2026-09-23','variant':'ride-open-decay-rescue','summary':summary,'deltaVsBase':delta,'songs':rows,
 'referencePolicy':'chart.mid was used only after fresh browser generation.'}
(EXP/'results-openhat-combined-v44.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
