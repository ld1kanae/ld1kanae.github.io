from __future__ import annotations
import json
from pathlib import Path
import mido

ROOT=Path('.'); EXP=ROOT/'drumscribe/experiments'
IN=EXP/'results-hat-context-runtime-predictions-v54.json'
OUT=EXP/'results-hat-context-runtime-v54.json'
MD=EXP/'HAT_CONTEXT_RUNTIME_V54.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
SETS={'closed':{42},'open':{46},'ride':{51,53,59},'kick':{35,36},'snare':{37,38,39,40},
      'tom':{41,43,45,47,48,50},'crash':{49,52,55,57},'pedal_hat':{44}}

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
    return {'tp':tp,'predicted':p,'reference':r,'precision':tp/p if p else 0.,
            'recall':tp/r if r else 0.,'f1':2*tp/(p+r) if p+r else 0.}

def ptimes(events,notes):return [float(e['time']) for e in events if int(e['note']) in notes]
def rtimes(events,notes):return [t for t,n in events if n in notes]
def aggregate(rows,key):
    tp=sum(r[key]['tp'] for r in rows);p=sum(r[key]['predicted'] for r in rows);ref=sum(r[key]['reference'] for r in rows)
    return {'tp':tp,'predicted':p,'reference':ref,'precision':tp/p if p else 0.,
            'recall':tp/ref if ref else 0.,'f1':2*tp/(p+ref) if p+ref else 0.}

def main():
    data=json.loads(IN.read_text())
    per={name:[] for name in data['variants']}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster'/'songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth=midi_events(ROOT/'DruMaster'/'songs'/song/'chart.mid',shift)
        for name in data['variants']:
            row=data['songs'][song][name];ev=row['events'];r={'song':song,'info':row.get('info',{})}
            for k in ('closed','open','ride','kick','snare','tom','crash','pedal_hat'):
                pred_notes={42} if k=='closed' else ({46} if k=='open' else ({51} if k=='ride' else SETS[k]))
                r[k]=metric(ptimes(ev,pred_notes),rtimes(truth,SETS[k]))
            r['hatRideOnset']=metric(ptimes(ev,{42,46,51}),rtimes(truth,SETS['closed']|SETS['open']|SETS['ride']))
            r['hatMacroF1']=(r['closed']['f1']+r['open']['f1'])/2
            r['metalMacroF1']=(r['closed']['f1']+r['open']['f1']+r['ride']['f1'])/3
            per[name].append(r)
    report={'schema':1,'date':'2026-09-23','experiment':'hat-context-runtime-v54',
            'reference_policy':'chart.mid used only after browser prediction; context model runtime reads audio and generated metal candidates only.',
            'variants':{}}
    for name,rows in per.items():
        s={k:aggregate(rows,k) for k in ('closed','open','ride','kick','snare','tom','crash','pedal_hat','hatRideOnset')}
        s['hatMacroF1']=(s['closed']['f1']+s['open']['f1'])/2
        s['metalMacroF1']=(s['closed']['f1']+s['open']['f1']+s['ride']['f1'])/3
        s['changed']=sum(int(r['info'].get('changed',0) or 0) for r in rows)
        report['variants'][name]={'summary':s,'songs':rows}
    base=report['variants']['baseline']['summary']
    for name,v in report['variants'].items():
        x=v['summary']
        v['deltaVsBaseline']={
            'hatMacroF1':x['hatMacroF1']-base['hatMacroF1'],
            'openF1':x['open']['f1']-base['open']['f1'],
            'closedF1':x['closed']['f1']-base['closed']['f1'],
            'rideF1':x['ride']['f1']-base['ride']['f1'],
            'hatRideOnsetF1':x['hatRideOnset']['f1']-base['hatRideOnset']['f1'],
            'kickF1':x['kick']['f1']-base['kick']['f1'],'snareF1':x['snare']['f1']-base['snare']['f1'],'tomF1':x['tom']['f1']-base['tom']['f1']}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Hi-hat context runtime v54','',
      'Five-song fresh Chromium comparison. The synchronized-corpus logistic model was trained offline; reference chart.mid is scoring-only in this runtime test.','',
      '| variant | closed F1 | open F1 | ride F1 | HH macro | collapsed onset F1 | changed |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for name in data['variants']:
        x=report['variants'][name]['summary']
        lines.append(f"| {name} | {x['closed']['f1']:.6f} | {x['open']['f1']:.6f} | {x['ride']['f1']:.6f} | {x['hatMacroF1']:.6f} | {x['hatRideOnset']['f1']:.6f} | {x['changed']} |")
    lines += ['','## Deltas vs baseline','']
    for name in data['variants'][1:]:
        d=report['variants'][name]['deltaVsBaseline']
        lines.append(f"- {name}: HH macro {d['hatMacroF1']:+.6f}; Open {d['openF1']:+.6f}; Closed {d['closedF1']:+.6f}; Ride {d['rideF1']:+.6f}; onset {d['hatRideOnsetF1']:+.6f}; K/S/T {d['kickF1']:+.6f}/{d['snareF1']:+.6f}/{d['tomF1']:+.6f}")
    lines += ['','Production adoption guard: K/S/T must remain exactly non-regressed and the chosen hat variant must improve HH macro without reducing collapsed hat/ride onset F1.','']
    MD.write_text('\n'.join(lines))
    print('\n'.join(lines))

if __name__=='__main__':main()
