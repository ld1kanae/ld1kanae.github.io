from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict
import mido

ROOT=Path('.')
IN=ROOT/'drumscribe/experiments/results-hat-sequence-predictions-v50.json'
OUT=ROOT/'drumscribe/experiments/results-hat-sequence-v50.json'
MD=ROOT/'drumscribe/experiments/HAT_SEQUENCE_REVIEW_V50.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
VARIANTS=['off','articulation','metal-grid','guarded-rescue']
GROUPS={
 'kick':{35,36},'snare':{37,38,39,40},'tom':{41,43,45,47,48,50},
 'closed':{42},'open':{46},'ride':{51,53,59},'pedal':{44},'crash':{49,52,55,57},
 'hatRide':{42,46,51,53,59}
}

def parse_midi(path,shift):
    mid=mido.MidiFile(path);tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += msg.time*tempo/1e6/mid.ticks_per_beat
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
        if best:used.add(best[1]);tp+=1
    p=len(pred);r=len(ref)
    return {'tp':tp,'pred':p,'ref':r,'precision':tp/p if p else 0.,'recall':tp/r if r else 0.,'f1':2*tp/(p+r) if p+r else 0.}

def aggregate(rows,key):
    tp=sum(r[key]['tp'] for r in rows);p=sum(r[key]['pred'] for r in rows);ref=sum(r[key]['ref'] for r in rows)
    return {'tp':tp,'pred':p,'ref':ref,'precision':tp/p if p else 0.,'recall':tp/ref if ref else 0.,'f1':2*tp/(p+ref) if p+ref else 0.}

def main():
    data=json.loads(IN.read_text())
    report={'schema':1,'date':'2026-09-23','experiment':'hat-sequence-review-v50','referencePolicy':'chart.mid is scoring-only','variants':{},'songs':{}}
    per={v:[] for v in VARIANTS}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth=parse_midi(ROOT/'DruMaster/songs'/song/'chart.mid',shift)
        report['songs'][song]={}
        for v in VARIANTS:
            events=data['songs'][song]['rows'][v]['events']
            row={'song':song,'info':data['songs'][song]['rows'][v]['info']}
            for g,notes in GROUPS.items():
                p=[float(e['time']) for e in events if int(e['note']) in notes]
                r=[t for t,n in truth if n in notes]
                row[g]=metric(p,r)
            row['hatMacroF1']=(row['closed']['f1']+row['open']['f1'])/2
            row['metalMacroF1']=(row['closed']['f1']+row['open']['f1']+row['ride']['f1'])/3
            report['songs'][song][v]=row;per[v].append(row)
    base=None
    for v,rows in per.items():
        summary={g:aggregate(rows,g) for g in GROUPS}
        summary['hatMacroF1']=(summary['closed']['f1']+summary['open']['f1'])/2
        summary['metalMacroF1']=(summary['closed']['f1']+summary['open']['f1']+summary['ride']['f1'])/3
        summary['changed']=sum(int(r['info'].get('changed',0) or 0) for r in rows)
        summary['convertedCymbal']=sum(int(r['info'].get('convertedCymbal',0) or 0) for r in rows)
        summary['removedOffGrid']=sum(int(r['info'].get('removedOffGrid',0) or 0) for r in rows)
        summary['rescued']=sum(int(r['info'].get('rescued',0) or 0) for r in rows)
        report['variants'][v]={'summary':summary,'songs':rows}
        if v=='off':base=summary
    for v,row in report['variants'].items():
        s=row['summary'];row['deltaVsOff']={
          'hatMacroF1':s['hatMacroF1']-base['hatMacroF1'],
          'closedF1':s['closed']['f1']-base['closed']['f1'],
          'openF1':s['open']['f1']-base['open']['f1'],
          'hatRideF1':s['hatRide']['f1']-base['hatRide']['f1'],
          'metalMacroF1':s['metalMacroF1']-base['metalMacroF1'],
          'kickF1':s['kick']['f1']-base['kick']['f1'],
          'snareF1':s['snare']['f1']-base['snare']['f1'],
          'tomF1':s['tom']['f1']-base['tom']['f1']}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Alternating Hi-Hat Review v50','',
      'Prediction uses drums audio only. chart.mid is opened after prediction for scoring.','',
      '| Variant | HH macro F1 | Closed F1 | Open F1 | collapsed HH/Ride F1 | metal macro F1 | K delta | S delta | T delta | changed | removed | rescued |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for v in VARIANTS:
        s=report['variants'][v]['summary'];d=report['variants'][v]['deltaVsOff']
        lines.append(f"| {v} | {s['hatMacroF1']:.6f} | {s['closed']['f1']:.6f} | {s['open']['f1']:.6f} | {s['hatRide']['f1']:.6f} | {s['metalMacroF1']:.6f} | {d['kickF1']:+.6f} | {d['snareF1']:+.6f} | {d['tomF1']:+.6f} | {s['changed']} | {s['removedOffGrid']} | {s['rescued']} |")
    lines += ['','Guardrails:','- Kick/snare/tom must be exactly non-regressing.','- H1 changes articulation only.','- H2 may remove off-grid metal inside strongly detected alternating-eighth runs.','- H3 may add only broad-metal/audio-supported slots and preserves the two-hand guard.','']
    MD.write_text('\n'.join(lines))
    print('\n'.join(lines))
if __name__=='__main__':main()
