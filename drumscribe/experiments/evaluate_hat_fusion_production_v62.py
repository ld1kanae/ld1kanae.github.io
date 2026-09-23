from __future__ import annotations
import json
from pathlib import Path
import mido

ROOT=Path('.')
IN=ROOT/'drumscribe/experiments/results-hat-fusion-production-predictions-v62.json'
OUT=ROOT/'drumscribe/experiments/results-hat-fusion-production-v62.json'
MD=ROOT/'drumscribe/experiments/HAT_FUSION_PRODUCTION_V62.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
GROUPS={'kick':{35,36},'snare':{37,38,39,40},'tom':{41,43,45,47,48,50},'closed':{42},'open':{46},'ride':{51,53,59},'hatRide':{42,46,51,53,59}}

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
        if best is not None:used.add(best[1]);tp+=1
    p=len(pred);r=len(ref)
    return {'tp':tp,'pred':p,'ref':r,'precision':tp/p if p else 0.,'recall':tp/r if r else 0.,'f1':2*tp/(p+r) if p+r else 0.}

def aggregate(rows,key):
    tp=sum(r[key]['tp'] for r in rows);p=sum(r[key]['pred'] for r in rows);ref=sum(r[key]['ref'] for r in rows)
    return {'tp':tp,'pred':p,'ref':ref,'precision':tp/p if p else 0.,'recall':tp/ref if ref else 0.,'f1':2*tp/(p+ref) if p+ref else 0.}

def exact_kst(a,b):
    def filt(ev):
        return [(round(float(e['time']),9),int(e['note'])) for e in ev if int(e['note']) in GROUPS['kick']|GROUPS['snare']|GROUPS['tom']]
    return filt(a)==filt(b)

def main():
    data=json.loads(IN.read_text())
    truth={}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster/songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth[song]=parse_midi(ROOT/'DruMaster/songs'/song/'chart.mid',shift)
    result={'schema':1,'date':'2026-09-24','experiment':'hat-fusion-production-v62',
      'referencePolicy':'chart.mid is scoring-only; browser prediction did not load it.',
      'reviewSpecificInputsUsed':False,'variants':{}}
    for variant in ('off','on'):
        rows=[]
        for song in SONGS:
            ev=data['songs'][song][variant]['events'];ref=truth[song]
            row={'song':song,'fusionInfo':data['songs'][song][variant].get('fusionInfo')}
            for g,notes in GROUPS.items():
                row[g]=metric([float(e['time']) for e in ev if int(e['note']) in notes],[t for t,n in ref if n in notes])
            row['hatMacroF1']=(row['closed']['f1']+row['open']['f1'])/2
            row['kstExactVsOff']=True if variant=='off' else exact_kst(data['songs'][song]['off']['events'],ev)
            rows.append(row)
        s={g:aggregate(rows,g) for g in GROUPS};s['hatMacroF1']=(s['closed']['f1']+s['open']['f1'])/2
        result['variants'][variant]={'summary':s,'songs':rows}
    base=result['variants']['off']['summary'];on=result['variants']['on']['summary']
    delta={g:on[g]['f1']-base[g]['f1'] for g in GROUPS};delta['hatMacroF1']=on['hatMacroF1']-base['hatMacroF1']
    per_nonreg=all(result['variants']['on']['songs'][i]['hatMacroF1']+1e-12>=result['variants']['off']['songs'][i]['hatMacroF1'] for i in range(len(SONGS)))
    kst_exact=all(r['kstExactVsOff'] for r in result['variants']['on']['songs'])
    result['deltaOnVsOff']=delta
    result['productionGuard']={'kstEventListsExact':kst_exact,'noPerSongHatMacroRegression':per_nonreg,'aggregateHatMacroImproved':delta['hatMacroF1']>0,'passed':kst_exact and per_nonreg and delta['hatMacroF1']>0}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# Production Hi-Hat Fusion v62','',
      'Per-hit acoustic Open/Closed fusion. No review range, alternating parity or song identity is used at runtime.','',
      '| variant | Closed F1 | Open F1 | HH macro | K | S | T |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for v in ('off','on'):
        s=result['variants'][v]['summary']
        lines.append(f"| {v} | {s['closed']['f1']:.6f} | {s['open']['f1']:.6f} | {s['hatMacroF1']:.6f} | {s['kick']['f1']:.6f} | {s['snare']['f1']:.6f} | {s['tom']['f1']:.6f} |")
    lines+=['',f"- HH macro delta: {delta['hatMacroF1']:+.6f}",f"- K/S/T event lists exact: {kst_exact}",f"- No per-song HH macro regression: {per_nonreg}",f"- Production guard: {result['productionGuard']['passed']}",'']
    for song in SONGS:
        off=result['variants']['off']['songs'][SONGS.index(song)]
        onr=result['variants']['on']['songs'][SONGS.index(song)]
        lines.append(f"- {song}: {off['hatMacroF1']:.6f} -> {onr['hatMacroF1']:.6f}, changes={onr.get('fusionInfo',{}).get('changed') if onr.get('fusionInfo') else 0}")
    MD.write_text('\n'.join(lines))
    print('\n'.join(lines))
if __name__=='__main__':main()
