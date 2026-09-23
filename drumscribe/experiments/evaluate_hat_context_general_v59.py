from __future__ import annotations
import json
from pathlib import Path
import mido

ROOT=Path('.')
PRED=ROOT/'drumscribe/experiments/results-hat-context-general-predictions-v59.json'
OUT=ROOT/'drumscribe/experiments/results-hat-context-general-v59.json'
MD=ROOT/'drumscribe/experiments/HAT_CONTEXT_GENERAL_V59.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
VARIANTS=['off','closed-open-995','closed-open-990','closed-open-highgap','bidirectional-extreme']
GROUPS={
 'kick':{35,36},'snare':{37,38,39,40},'tom':{41,43,45,47,48,50},
 'closed':{42},'open':{46},'ride':{51,53,59},'hatRide':{42,46,51,53,59}
}

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

def norm(events,groups):
    return [(round(float(e['time']),9),int(e['note'])) for e in events if e['group'] in groups]

def main():
    data=json.loads(PRED.read_text())
    truth={}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth[song]=parse_midi(ROOT/'DruMaster/songs'/song/'chart.mid',shift)
    result={'schema':1,'date':'2026-09-24','experiment':'hat-context-general-v59',
      'referencePolicy':'chart.mid is scoring-only; browser prediction never loaded it.',
      'reviewSpecificInputsUsed':False,'variants':{}}
    base_rows=None
    for variant in VARIANTS:
        rows=[]
        for song in SONGS:
            ev=data['songs'][song]['rows'][variant]['events'];ref=truth[song]
            row={'song':song,'info':data['songs'][song]['rows'][variant]['info']}
            for g,notes in GROUPS.items():
                row[g]=metric([float(e['time']) for e in ev if int(e['note']) in notes],[t for t,n in ref if n in notes])
            row['hatMacroF1']=(row['closed']['f1']+row['open']['f1'])/2
            rows.append(row)
        summary={g:aggregate(rows,g) for g in GROUPS}
        summary['hatMacroF1']=(summary['closed']['f1']+summary['open']['f1'])/2
        result['variants'][variant]={'summary':summary,'songs':rows}
        if variant=='off':base_rows=rows
    base=result['variants']['off']['summary']
    for variant,v in result['variants'].items():
        s=v['summary']
        v['deltaVsOff']={g:s[g]['f1']-base[g]['f1'] for g in GROUPS}
        v['deltaVsOff']['hatMacroF1']=s['hatMacroF1']-base['hatMacroF1']
        per_nonreg=all(r['hatMacroF1']+1e-12>=base_rows[i]['hatMacroF1'] for i,r in enumerate(v['songs']))
        kst_exact=all(abs(v['deltaVsOff'][g])<1e-12 for g in ('kick','snare','tom'))
        v['guard']={'kstExactNonRegression':kst_exact,'noPerSongHatMacroRegression':per_nonreg,
                    'aggregateHatMacroImproved':v['deltaVsOff']['hatMacroF1']>0,
                    'passed':kst_exact and per_nonreg and v['deltaVsOff']['hatMacroF1']>0}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# Generic synchronized-context Hi-Hat v59','',
      'No user review ranges, song identity or alternating parity are used. The review-trained sequence repair is explicitly disabled.','',
      '| variant | Closed F1 | Open F1 | HH macro | delta | K delta | S delta | T delta | guard |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for variant in VARIANTS:
        v=result['variants'][variant];s=v['summary'];d=v['deltaVsOff']
        lines.append(f"| {variant} | {s['closed']['f1']:.6f} | {s['open']['f1']:.6f} | {s['hatMacroF1']:.6f} | {d['hatMacroF1']:+.6f} | {d['kick']:+.6f} | {d['snare']:+.6f} | {d['tom']:+.6f} | {v['guard']['passed']} |")
    lines += ['','Per-song HH macro:']
    for variant in VARIANTS:
        lines.append('- '+variant+': '+', '.join(f"{r['song']}={r['hatMacroF1']:.6f}" for r in result['variants'][variant]['songs']))
    lines += ['','- Prediction stage did not read chart.mid.','- K/S/T exact non-regression is required.','- No reviewed-song-specific runtime model is part of this benchmark.','']
    MD.write_text('\n'.join(lines))
    print('\n'.join(lines))
if __name__=='__main__':main()
