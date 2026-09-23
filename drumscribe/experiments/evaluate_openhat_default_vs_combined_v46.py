from __future__ import annotations
import json
from pathlib import Path
import mido

ROOT=Path('.')
EXP=ROOT/'drumscribe/experiments'
IN=EXP/'results-openhat-default-vs-combined-predictions-v46.json'
OUT=EXP/'results-openhat-default-vs-combined-v46.json'
MD=EXP/'OPENHAT_DEFAULT_VS_COMBINED_V46.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
SETS={
 'closed':{42},'open':{46},'ride':{51,53,59},
 'kick':{35,36},'snare':{37,38,39,40},'tom':{41,43,45,47,48,50},
 'crash':{49,52,55,57},'pedal_hat':{44}
}

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
    per={c['name']:[] for c in data['configs']}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster'/'songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth=midi_events(ROOT/'DruMaster'/'songs'/song/'chart.mid',shift)
        for cfg in data['configs']:
            name=cfg['name'];ev=data['songs'][song][name]['events']
            r={'song':song}
            for k in ('closed','open','ride','kick','snare','tom','crash','pedal_hat'):
                pred_notes={42} if k=='closed' else ({46} if k=='open' else ({51} if k=='ride' else SETS[k]))
                r[k]=metric(ptimes(ev,pred_notes),rtimes(truth,SETS[k]))
            r['hatRideOnset']=metric(ptimes(ev,{42,46,51}),rtimes(truth,SETS['closed']|SETS['open']|SETS['ride']))
            r['hatMacroF1']=(r['closed']['f1']+r['open']['f1'])/2
            r['metalMacroF1']=(r['closed']['f1']+r['open']['f1']+r['ride']['f1'])/3
            per[name].append(r)
    report={'schema':1,'date':'2026-09-23','experiment':'openhat-default-vs-combined-v46',
            'reference_policy':'chart.mid used only in this post-generation scorer.','variants':{}}
    for name,rows in per.items():
        s={k:aggregate(rows,k) for k in ('closed','open','ride','kick','snare','tom','crash','pedal_hat','hatRideOnset')}
        s['hatMacroF1']=(s['closed']['f1']+s['open']['f1'])/2
        s['metalMacroF1']=(s['closed']['f1']+s['open']['f1']+s['ride']['f1'])/3
        report['variants'][name]={'summary':s,'songs':rows}
    base=report['variants']['default']['summary'];comb=report['variants']['combined']['summary']
    report['combinedDeltaVsDefault']={
      'hatMacroF1':comb['hatMacroF1']-base['hatMacroF1'],
      'metalMacroF1':comb['metalMacroF1']-base['metalMacroF1'],
      'closedF1':comb['closed']['f1']-base['closed']['f1'],
      'openF1':comb['open']['f1']-base['open']['f1'],
      'rideF1':comb['ride']['f1']-base['ride']['f1'],
      'hatRideOnsetF1':comb['hatRideOnset']['f1']-base['hatRideOnset']['f1'],
      'kickF1':comb['kick']['f1']-base['kick']['f1'],
      'snareF1':comb['snare']['f1']-base['snare']['f1'],
      'tomF1':comb['tom']['f1']-base['tom']['f1'],
    }
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Open-hat default vs combined v46','',
      'Fresh browser comparison. Reference MIDI is scoring-only.','',
      '| variant | closed F1 | open F1 | ride F1 | hat macro | metal macro | collapsed hat/ride onset F1 |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for name in ('default','combined'):
        s=report['variants'][name]['summary']
        lines.append(f"| {name} | {s['closed']['f1']:.6f} | {s['open']['f1']:.6f} | {s['ride']['f1']:.6f} | {s['hatMacroF1']:.6f} | {s['metalMacroF1']:.6f} | {s['hatRideOnset']['f1']:.6f} |")
    d=report['combinedDeltaVsDefault']
    lines += ['','Combined minus default:',
      f"- hat macro: {d['hatMacroF1']:+.6f}",
      f"- metal macro incl. ride: {d['metalMacroF1']:+.6f}",
      f"- open F1: {d['openF1']:+.6f}",
      f"- ride F1: {d['rideF1']:+.6f}",
      f"- collapsed hat/ride onset F1: {d['hatRideOnsetF1']:+.6f}",
      f"- K/S/T deltas: kick {d['kickF1']:+.6f}, snare {d['snareF1']:+.6f}, tom {d['tomF1']:+.6f}",
      '',
      'Guardrail: do not adopt combined if Open gain is merely a Ride-to-Open relabeling that materially lowers strict Ride/metal macro accuracy.',
      '']
    MD.write_text('\n'.join(lines))
    print('\n'.join(lines))

if __name__=='__main__':main()
