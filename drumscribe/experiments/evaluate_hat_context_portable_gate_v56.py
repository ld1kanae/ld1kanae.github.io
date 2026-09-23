from __future__ import annotations
import json
from pathlib import Path
import mido

ROOT=Path('.'); EXP=ROOT/'drumscribe/experiments'
IN=EXP/'results-hat-context-heldout-predictions-v55.json'
OUT=EXP/'results-hat-context-portable-gate-v56.json'
MD=EXP/'HAT_CONTEXT_PORTABLE_GATE_V56.md'
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
SETS={'closed':{42},'open':{46},'ride':{51,53,59},'kick':{35,36},'snare':{37,38,39,40},'tom':{41,43,45,47,48,50}}
GATES=[2,8,16,24,32,64]
TH=.99

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
    return {'tp':tp,'predicted':p,'reference':r,'precision':tp/p if p else 0.,'recall':tp/r if r else 0.,'f1':2*tp/(p+r) if p+r else 0.}

def score(ev,truth):
    r={}
    for k in ('closed','open','ride','kick','snare','tom'):
        pn={42} if k=='closed' else ({46} if k=='open' else ({51} if k=='ride' else SETS[k]))
        r[k]=metric([e['time'] for e in ev if int(e['note']) in pn],[t for t,n in truth if n in SETS[k]])
    r['hatRideOnset']=metric([e['time'] for e in ev if int(e['note']) in {42,46,51}],
                             [t for t,n in truth if n in SETS['closed']|SETS['open']|SETS['ride']])
    r['hatMacroF1']=(r['closed']['f1']+r['open']['f1'])/2
    return r

def aggregate(rows,key):
    tp=sum(r[key]['tp'] for r in rows);p=sum(r[key]['predicted'] for r in rows);ref=sum(r[key]['reference'] for r in rows)
    return {'tp':tp,'predicted':p,'reference':ref,'precision':tp/p if p else 0.,'recall':tp/ref if ref else 0.,'f1':2*tp/(p+ref) if p+ref else 0.}

def main():
    data=json.loads(IN.read_text());truth={}
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster'/'songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth[song]=midi_events(ROOT/'DruMaster'/'songs'/song/'chart.mid',shift)
    variants={}
    configs=[('baseline',None)]+[(f'minride{g}',g) for g in GATES]
    for name,gate in configs:
        rows=[]
        for song in SONGS:
            ev=[dict(e) for e in data['songs'][song]['events']]
            ride_count=sum(e['group']=='ride' for e in ev)
            enabled=gate is not None and ride_count>=gate
            changed=0
            if enabled:
                for e in ev:
                    if e['group']=='ride' and float(e.get('hatContextProbability') or 0)>=TH:
                        e['group']='open_hat';e['note']=46;changed+=1
            rows.append({'song':song,'rideCandidates':ride_count,'gateEnabled':enabled,'changed':changed,**score(ev,truth[song])})
        s={k:aggregate(rows,k) for k in ('closed','open','ride','kick','snare','tom','hatRideOnset')}
        s['hatMacroF1']=(s['closed']['f1']+s['open']['f1'])/2
        variants[name]={'summary':s,'songs':rows}
    base=variants['baseline']['summary']
    for v in variants.values():
        x=v['summary'];v['delta']={k:x[k]['f1']-base[k]['f1'] for k in ('closed','open','ride','kick','snare','tom','hatRideOnset')}
        v['delta']['hatMacroF1']=x['hatMacroF1']-base['hatMacroF1']
    report={'schema':1,'experiment':'hat-context-portable-gate-v56','threshold':TH,'variants':variants,
            'note':'Gate uses generated Ride candidate count only. Probabilities remain song-held-out from v55.'}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Hat context portable gate v56','',
      'Uses the v55 song-held-out probabilities. The gate reads only the number of generated Ride candidates; reference MIDI is scoring-only.','',
      '| variant | Open F1 | Closed F1 | Ride F1 | HH macro | ΔHH macro |',
      '|---|---:|---:|---:|---:|---:|']
    for name,_ in configs:
        x=variants[name]['summary'];d=variants[name]['delta']
        lines.append(f"| {name} | {x['open']['f1']:.6f} | {x['closed']['f1']:.6f} | {x['ride']['f1']:.6f} | {x['hatMacroF1']:.6f} | {d['hatMacroF1']:+.6f} |")
    lines+=['','Per-song gate activity for minride24:']
    for r in variants['minride24']['songs']:
        lines.append(f"- {r['song']}: rides={r['rideCandidates']}, enabled={r['gateEnabled']}, changed={r['changed']}, HH macro={r['hatMacroF1']:.6f}")
    MD.write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
if __name__=='__main__': main()
