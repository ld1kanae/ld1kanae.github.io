from __future__ import annotations
import json
from pathlib import Path
import mido

ROOT=Path('.'); EXP=ROOT/'drumscribe/experiments'
IN=EXP/'results-hat-context-production-predictions-v58.json'
OUT=EXP/'results-hat-context-production-v58.json'
MD=EXP/'HAT_CONTEXT_PRODUCTION_V58.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
SETS={'closed':{42},'open':{46},'ride':{51,53,59},'kick':{35,36},'snare':{37,38,39,40},'tom':{41,43,45,47,48,50}}

def midi_events(path,shift=0.0):
    mid=mido.MidiFile(path); tempo=500000; sec=0.; out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=='set_tempo': tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0: out.append((sec+shift,msg.note))
    return out

def greedy(pred,ref,w=.080):
    used=set(); tp=0
    for t in sorted(pred):
        opts=[(abs(t-u),j) for j,u in enumerate(ref) if j not in used and abs(t-u)<=w]
        if opts:
            _,j=min(opts); used.add(j); tp+=1
    return tp

def metric(pred,ref):
    tp=greedy(pred,ref); p=len(pred); r=len(ref)
    return {'tp':tp,'predicted':p,'reference':r,
            'precision':tp/p if p else 0.,'recall':tp/r if r else 0.,
            'f1':2*tp/(p+r) if p+r else 0.}

def score(ev,truth,song):
    ignore_ride=[t for t,n in truth if n in SETS['ride']] if song=='arcaround' else []
    def pred(notes,mask=False):
        vals=[float(e['time']) for e in ev if int(e['note']) in notes]
        if mask and ignore_ride:
            vals=[t for t in vals if not any(abs(t-u)<=.080 for u in ignore_ride)]
        return vals
    out={}
    for k in ('closed','open','ride','kick','snare','tom'):
        pn={42} if k=='closed' else ({46} if k=='open' else ({51} if k=='ride' else SETS[k]))
        ref=[] if (song=='arcaround' and k=='ride') else [t for t,n in truth if n in SETS[k]]
        out[k]=metric(pred(pn,k in ('closed','open','ride') and song=='arcaround'),ref)
    onset_pred=pred({42,46,51},song=='arcaround')
    onset_ref=[t for t,n in truth if n in (SETS['closed']|SETS['open']|SETS['ride'])]
    if song=='arcaround':
        onset_ref=[t for t,n in truth if n in (SETS['closed']|SETS['open'])]
    out['hatRideOnset']=metric(onset_pred,onset_ref)
    out['hatMacroF1']=(out['closed']['f1']+out['open']['f1'])/2
    return out

def aggregate(rows,key):
    tp=sum(r[key]['tp'] for r in rows); p=sum(r[key]['predicted'] for r in rows); ref=sum(r[key]['reference'] for r in rows)
    return {'tp':tp,'predicted':p,'reference':ref,
            'precision':tp/p if p else 0.,'recall':tp/ref if ref else 0.,
            'f1':2*tp/(p+ref) if p+ref else 0.}

def main():
    data=json.loads(IN.read_text()); truth={}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster'/'songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth[song]=midi_events(ROOT/'DruMaster'/'songs'/song/'chart.mid',shift)
    report={'schema':1,'date':'2026-09-24','experiment':'hat-context-production-v58',
            'reference_policy':'chart.mid used only after prediction. Arcaround Ride zones ignored in HH scoring as arrangement-only.',
            'variants':{}}
    for name in ('off','production'):
        rows=[]
        for song in SONGS:
            row=data['songs'][song][name]
            rows.append({'song':song,'info':row.get('info'),**score(row['events'],truth[song],song)})
        s={k:aggregate(rows,k) for k in ('closed','open','ride','kick','snare','tom','hatRideOnset')}
        s['hatMacroF1']=(s['closed']['f1']+s['open']['f1'])/2
        report['variants'][name]={'summary':s,'songs':rows}
    b=report['variants']['off']['summary']; p=report['variants']['production']['summary']
    report['delta']={k:p[k]['f1']-b[k]['f1'] for k in ('closed','open','ride','kick','snare','tom','hatRideOnset')}
    report['delta']['hatMacroF1']=p['hatMacroF1']-b['hatMacroF1']
    per_song_ok=True
    for pr in report['variants']['production']['songs']:
        br=next(x for x in report['variants']['off']['songs'] if x['song']==pr['song'])
        if pr['hatMacroF1']+1e-12 < br['hatMacroF1']: per_song_ok=False
    report['productionGuard']={
        'kstExactNonRegression':report['delta']['kick']==0 and report['delta']['snare']==0 and report['delta']['tom']==0,
        'collapsedOnsetNonRegression':report['delta']['hatRideOnset']>=-1e-12,
        'hatMacroImproved':report['delta']['hatMacroF1']>0,
        'noPerSongHatMacroRegression':per_song_ok
    }
    report['productionGuard']['passed']=all(report['productionGuard'].values())
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Hat context production v58','',
      'Fresh Chromium direct comparison: current production default vs identical runtime with hatContextVariant=off.',
      'Arcaround reference Ride zones are ignored in HH scoring as arrangement-only.','',
      f"Production guard: **{'PASS' if report['productionGuard']['passed'] else 'FAIL'}**",'',
      '| variant | Closed F1 | Open F1 | Ride F1 | HH macro | collapsed onset |',
      '|---|---:|---:|---:|---:|---:|']
    for name in ('off','production'):
        s=report['variants'][name]['summary']
        lines.append(f"| {name} | {s['closed']['f1']:.6f} | {s['open']['f1']:.6f} | {s['ride']['f1']:.6f} | {s['hatMacroF1']:.6f} | {s['hatRideOnset']['f1']:.6f} |")
    d=report['delta']
    lines += ['',
      f"- Δ HH macro: {d['hatMacroF1']:+.6f}",
      f"- Δ Open F1: {d['open']:+.6f}",
      f"- Δ Closed F1: {d['closed']:+.6f}",
      f"- Δ K/S/T: {d['kick']:+.6f} / {d['snare']:+.6f} / {d['tom']:+.6f}",
      f"- Δ collapsed onset: {d['hatRideOnset']:+.6f}",'',
      '## Per-song HH macro','']
    for name in ('off','production'):
        vals=', '.join(f"{r['song']}={r['hatMacroF1']:.6f}" for r in report['variants'][name]['songs'])
        lines.append(f"- {name}: {vals}")
    MD.write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
if __name__=='__main__': main()
