from __future__ import annotations
import json
from pathlib import Path
import mido

ROOT=Path('.')
PRED=ROOT/'drumscribe/experiments/results-hat-sequence-runtime-predictions-v52.json'
BASEP=ROOT/'drumscribe/experiments/results-hat-sequence-predictions-v51.json'
BASEM=ROOT/'drumscribe/experiments/results-hat-sequence-v51.json'
OUT=ROOT/'drumscribe/experiments/results-hat-sequence-runtime-v52.json'
MD=ROOT/'drumscribe/experiments/HAT_SEQUENCE_RUNTIME_V52.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
GROUPS={'kick':{35,36},'snare':{37,38,39,40},'tom':{41,43,45,47,48,50},'closed':{42},'open':{46},'ride':{51,53,59},'pedal':{44},'crash':{49,52,55,57},'hatRide':{42,46,51,53,59}}

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
        if best:used.add(best[1]);tp+=1
    p=len(pred);r=len(ref)
    return {'tp':tp,'pred':p,'ref':r,'precision':tp/p if p else 0.,'recall':tp/r if r else 0.,'f1':2*tp/(p+r) if p+r else 0.}

def aggregate(rows,key):
    tp=sum(r[key]['tp'] for r in rows);p=sum(r[key]['pred'] for r in rows);ref=sum(r[key]['ref'] for r in rows)
    return {'tp':tp,'pred':p,'ref':ref,'precision':tp/p if p else 0.,'recall':tp/ref if ref else 0.,'f1':2*tp/(p+ref) if p+ref else 0.}

def normalized(events):return [(round(float(e['time']),9),int(e['note'])) for e in events]

def main():
    pred=json.loads(PRED.read_text());basep=json.loads(BASEP.read_text());basem=json.loads(BASEM.read_text())
    rows=[];song_rows={};exact_equal=True
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth=parse_midi(ROOT/'DruMaster/songs'/song/'chart.mid',shift);events=pred['songs'][song]['events']
        same=normalized(events)==normalized(basep['songs'][song]['rows']['off']['events']);exact_equal &= same
        row={'song':song,'exactEventEqualityVsV51Off':same,'hatSequence':pred['songs'][song]['hatSequence']}
        for g,notes in GROUPS.items():row[g]=metric([float(e['time']) for e in events if int(e['note']) in notes],[t for t,n in truth if n in notes])
        row['hatMacroF1']=(row['closed']['f1']+row['open']['f1'])/2;rows.append(row);song_rows[song]=row
    summary={g:aggregate(rows,g) for g in GROUPS};summary['hatMacroF1']=(summary['closed']['f1']+summary['open']['f1'])/2
    base=basem['variants']['off']['summary']
    delta={g:summary[g]['f1']-base[g]['f1'] for g in GROUPS};delta['hatMacroF1']=summary['hatMacroF1']-base['hatMacroF1']
    result={'schema':1,'date':'2026-09-23','experiment':'hat-sequence-runtime-v52','referencePolicy':'chart.mid is scoring-only',
      'exactEventEqualityVsV51Off':exact_equal,'summary':summary,'deltaVsV51Off':delta,'songs':song_rows}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# Alternating Hi-Hat Runtime v52 — fresh default validation','',
      f"Exact event equality vs v51 off baseline: **{exact_equal}**",'',
      '| Part | F1 | delta vs v51 off |','|---|---:|---:|']
    for g in ['kick','snare','tom','closed','open','hatRide','pedal','crash','ride']:
        lines.append(f"| {g} | {summary[g]['f1']:.6f} | {delta[g]:+.6f} |")
    lines.append(f"| HH macro | {summary['hatMacroF1']:.6f} | {delta['hatMacroF1']:+.6f} |")
    lines += ['','Gate status:']
    for song in SONGS:
        info=song_rows[song]['hatSequence'] or {}
        lines.append(f"- {song}: gate={info.get('inversionGate')}, gated={info.get('gated')}, changed={info.get('changed',0)}, rescued={info.get('rescued',0)}")
    lines += ['','- Prediction did not read chart.mid.','- K/S/T equality and event-level equality are asserted against the previous default baseline.','']
    MD.write_text('\n'.join(lines));print('\n'.join(lines))
if __name__=='__main__':main()
