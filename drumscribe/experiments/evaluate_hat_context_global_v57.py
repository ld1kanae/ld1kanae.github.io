from __future__ import annotations
import json
from pathlib import Path
import mido

ROOT=Path('.'); EXP=ROOT/'drumscribe/experiments'
IN=EXP/'results-hat-context-global-predictions-v57.json'
OUT=EXP/'results-hat-context-global-v57.json'
MD=EXP/'HAT_CONTEXT_GLOBAL_V57.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
SETS={'closed':{42},'open':{46},'ride':{51,53,59},'kick':{35,36},'snare':{37,38,39,40},'tom':{41,43,45,47,48,50}}

def midi_events(path,shift=0.0):
    mid=mido.MidiFile(path);tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=='set_tempo': tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0: out.append((sec+shift,msg.note))
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

def score(ev,truth,song):
    ignore_ride=[t for t,n in truth if n in SETS['ride']] if song=='arcaround' else []
    def pred_for(notes,mask=False):
        vals=[float(e['time']) for e in ev if int(e['note']) in notes]
        if mask and ignore_ride:
            vals=[t for t in vals if not any(abs(t-u)<=.080 for u in ignore_ride)]
        return vals
    r={}
    for k in ('closed','open','ride','kick','snare','tom'):
        pn={42} if k=='closed' else ({46} if k=='open' else ({51} if k=='ride' else SETS[k]))
        mask=k in ('closed','open','ride') and song=='arcaround'
        ref=[] if (song=='arcaround' and k=='ride') else [t for t,n in truth if n in SETS[k]]
        r[k]=metric(pred_for(pn,mask),ref)
    onset_pred=pred_for({42,46,51},song=='arcaround')
    onset_ref=[t for t,n in truth if n in (SETS['closed']|SETS['open']|SETS['ride'])]
    if song=='arcaround': onset_ref=[t for t,n in truth if n in (SETS['closed']|SETS['open'])]
    r['hatRideOnset']=metric(onset_pred,onset_ref)
    r['hatMacroF1']=(r['closed']['f1']+r['open']['f1'])/2
    return r

def aggregate(rows,key):
    tp=sum(r[key]['tp'] for r in rows);p=sum(r[key]['predicted'] for r in rows);ref=sum(r[key]['reference'] for r in rows)
    return {'tp':tp,'predicted':p,'reference':ref,'precision':tp/p if p else 0.,
            'recall':tp/ref if ref else 0.,'f1':2*tp/(p+ref) if p+ref else 0.}

def main():
    data=json.loads(IN.read_text());truth={}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster'/'songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth[song]=midi_events(ROOT/'DruMaster'/'songs'/song/'chart.mid',shift)
    report={'schema':1,'date':'2026-09-23','experiment':'hat-context-global-v57',
            'reference_policy':'chart.mid used only after browser prediction. Arcaround Ride zones ignored in HH scoring per project instruction.',
            'variants':{}}
    for cfg in data['variants']:
        name=cfg['name'];rows=[]
        for song in SONGS:
            row=data['songs'][song][name]
            rows.append({'song':song,'info':row.get('info',{}),**score(row['events'],truth[song],song)})
        s={k:aggregate(rows,k) for k in ('closed','open','ride','kick','snare','tom','hatRideOnset')}
        s['hatMacroF1']=(s['closed']['f1']+s['open']['f1'])/2
        report['variants'][name]={'summary':s,'songs':rows}
    base=report['variants']['baseline']['summary']
    for name,v in report['variants'].items():
        x=v['summary']
        v['deltaVsBaseline']={k:x[k]['f1']-base[k]['f1'] for k in ('closed','open','ride','kick','snare','tom','hatRideOnset')}
        v['deltaVsBaseline']['hatMacroF1']=x['hatMacroF1']-base['hatMacroF1']
    eligible=[]
    for name,v in report['variants'].items():
        if name=='baseline':continue
        d=v['deltaVsBaseline'];s=v['summary']
        per_song_ok=True
        for r in v['songs']:
            b=next(x for x in report['variants']['baseline']['songs'] if x['song']==r['song'])
            if r['hatMacroF1']+1e-12 < b['hatMacroF1']: per_song_ok=False
        if d['kick']==0 and d['snare']==0 and d['tom']==0 and d['hatRideOnset']>=-1e-12 and d['hatMacroF1']>0 and per_song_ok:
            eligible.append((s['hatMacroF1'],name))
    eligible.sort(reverse=True)
    report['bestEligible']=eligible[0][1] if eligible else None
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Hat context global v57','',
      'Portable global model trained on the synchronized corpus. Runtime does not use song identity or reference MIDI. Arcaround Ride zones are ignored in HH scoring as arrangement-only.','',
      f"Best eligible: **{report['bestEligible']}**" if report['bestEligible'] else 'No variant passed the production guard.','',
      '| variant | Closed F1 | Open F1 | Ride F1 | HH macro | collapsed onset | ΔHH macro |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for cfg in data['variants']:
        name=cfg['name'];s=report['variants'][name]['summary'];d=report['variants'][name]['deltaVsBaseline']
        lines.append(f"| {name} | {s['closed']['f1']:.6f} | {s['open']['f1']:.6f} | {s['ride']['f1']:.6f} | {s['hatMacroF1']:.6f} | {s['hatRideOnset']['f1']:.6f} | {d['hatMacroF1']:+.6f} |")
    lines += ['','## Per-song HH macro','']
    for cfg in data['variants']:
        name=cfg['name']
        vals=', '.join(f"{r['song']}={r['hatMacroF1']:.6f}" for r in report['variants'][name]['songs'])
        lines.append(f"- {name}: {vals}")
    lines += ['','Production guard: K/S/T unchanged; collapsed onset non-regression; aggregate HH macro improvement; no per-song HH macro regression after the Arcaround Ride masking rule.','']
    MD.write_text('\n'.join(lines))
    print('\n'.join(lines))

if __name__=='__main__': main()
