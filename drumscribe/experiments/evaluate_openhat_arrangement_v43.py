from __future__ import annotations
import json, math
from collections import Counter
from pathlib import Path
import mido

ROOT=Path('.')
IN=Path('drumscribe/experiments/results-openhat-arrangement-predictions-v43.json')
OUT=Path('drumscribe/experiments/results-openhat-arrangement-v43.json')
MD=Path('drumscribe/experiments/OPENHAT_ARRANGEMENT_V43.md')
SONGS=['arcaround','diamondvirgin','kaiju','nanairo','ray']
KICK={35,36}; SNARE={37,38,39,40}; TOM={41,43,45,47,48,50}
CLOSED={42}; OPEN={46}; RIDE={51,53,59}

def midi_events(path,shift=0.0):
    mid=mido.MidiFile(path);tempo=500000;sec=0.;out=[]
    for msg in mido.merge_tracks(mid.tracks):
        sec += msg.time*tempo/1e6/mid.ticks_per_beat
        if msg.type=='set_tempo': tempo=msg.tempo
        elif msg.type=='note_on' and msg.velocity>0:
            out.append((sec+shift,msg.note))
    return out

def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        best=None
        for j,u in enumerate(ref):
            if j in used: continue
            d=abs(t-u)
            if d<=w and (best is None or d<best[0]): best=(d,j)
        if best is not None: used.add(best[1]);tp+=1
    return tp

def metric(pred,ref):
    tp=greedy(pred,ref);p=len(pred);r=len(ref)
    return {'tp':tp,'predicted':p,'reference':r,
      'precision':tp/p if p else 0.,'recall':tp/r if r else 0.,
      'f1':2*tp/(p+r) if p+r else 0.}

def times_pred(events,notes):
    return [float(e['time']) for e in events if int(e['note']) in notes]

def times_ref(events,notes):
    return [t for t,n in events if n in notes]

def aggregate(rows,key):
    tp=sum(x[key]['tp'] for x in rows);p=sum(x[key]['predicted'] for x in rows);r=sum(x[key]['reference'] for x in rows)
    return {'tp':tp,'predicted':p,'reference':r,
      'precision':tp/p if p else 0.,'recall':tp/r if r else 0.,
      'f1':2*tp/(p+r) if p+r else 0.}

def section_for(sections,t):
    for s in sections:
        if float(s['startSec'])<=t<float(s['endSec']): return s
    return None

def rel_slot(t,s,bar_sec):
    rel=max(0.,t-float(s['startSec']));bar=int(math.floor(rel/bar_sec+1e-8))
    slot=int(round((rel-bar*bar_sec)/bar_sec*16))
    if slot>=16:bar+=1;slot=0
    return bar,max(0,min(15,slot))

def articulation_maps(truth,sections,bpm,num,den):
    beat=60/bpm*4/den;bar_sec=beat*num
    maps={}
    for s in sections:
        d={}
        for t,n in truth:
            if n not in (42,46):continue
            if float(s['startSec'])<=t<float(s['endSec']):
                k=rel_slot(t,s,bar_sec)
                # if two hats land on same slot, keep open only if both agree; rare collisions are ignored later
                v=1 if n==46 else 0
                if k in d and d[k]!=v:d[k]=None
                else:d[k]=v
        maps[int(s['index'])]=d
    return maps

def family_agreement(truth,sections,bpm,num,den):
    maps=articulation_maps(truth,sections,bpm,num,den)
    same=[];cross=[]
    for i,a in enumerate(sections):
        for b in sections[i+1:]:
            ma,mb=maps.get(int(a['index']),{}),maps.get(int(b['index']),{})
            common=set(ma)&set(mb)
            vals=[(ma[k],mb[k]) for k in common if ma[k] is not None and mb[k] is not None]
            if not vals:continue
            arr=same if a['group']==b['group'] else cross
            arr.extend([int(x==y) for x,y in vals])
    return {'same_n':len(same),'same_match_rate':sum(same)/len(same) if same else None,
            'cross_n':len(cross),'cross_match_rate':sum(cross)/len(cross) if cross else None,
            'lift':(sum(same)/len(same)-sum(cross)/len(cross)) if same and cross else None}

def main():
    data=json.loads(IN.read_text())
    configs=list(data['configs'])
    report={'schema':1,'date':'2026-09-23','experiment':'openhat-arrangement-v43',
      'reference_policy':'chart.mid is scoring-only; browser prediction did not fetch it.',
      'configs':data['configs'],'variants':{},'familyReferenceAgreement':{}}
    per={c:[] for c in configs}
    agree=[]
    for song in SONGS:
        meta=json.loads((ROOT/'DruMaster'/'songs'/song/'song.json').read_text())
        shift=float(meta['playback']['stemOffsetSec'])+float(meta['playback'].get('midiOffsetSec',0))
        truth=midi_events(ROOT/'DruMaster'/'songs'/song/'chart.mid',shift)
        base=data['songs'][song]['base']
        agree_row=family_agreement(truth,base['sections'],float(base['bpm']),int(base['numerator']),int(base['denominator']))
        report['familyReferenceAgreement'][song]=agree_row;agree.append(agree_row)
        for c in configs:
            row=data['songs'][song][c];ev=row['events']
            r={
              'song':song,
              'closed':metric(times_pred(ev,CLOSED),times_ref(truth,CLOSED)),
              'open':metric(times_pred(ev,OPEN),times_ref(truth,OPEN)),
              'kick':metric(times_pred(ev,{36}),times_ref(truth,KICK)),
              'snare':metric(times_pred(ev,{38}),times_ref(truth,SNARE)),
              'tom':metric(times_pred(ev,{45}),times_ref(truth,TOM)),
              'metalHatOnset':metric(times_pred(ev,{42,46,51}),times_ref(truth,CLOSED|OPEN|RIDE)),
              'predRide':len(times_pred(ev,{51})),
              'referenceRide':len(times_ref(truth,RIDE)),
              'arrangementChanged':int(row.get('arrangementHatInfo',{}).get('changed',0) or 0),
            }
            r['strictHatMacroF1']=(r['closed']['f1']+r['open']['f1'])/2
            per[c].append(r)
    for c,rows in per.items():
        s={k:aggregate(rows,k) for k in ('closed','open','kick','snare','tom','metalHatOnset')}
        s['strictHatMacroF1']=(s['closed']['f1']+s['open']['f1'])/2
        s['arrangementChanged']=sum(r['arrangementChanged'] for r in rows)
        report['variants'][c]={'summary':s,'songs':rows}
    base=report['variants']['base']['summary']
    for c,v in report['variants'].items():
        s=v['summary']
        v['deltaVsBase']={
          'strictHatMacroF1':s['strictHatMacroF1']-base['strictHatMacroF1'],
          'closedF1':s['closed']['f1']-base['closed']['f1'],
          'openF1':s['open']['f1']-base['open']['f1'],
          'metalHatOnsetF1':s['metalHatOnset']['f1']-base['metalHatOnset']['f1'],
          'kickF1':s['kick']['f1']-base['kick']['f1'],
          'snareF1':s['snare']['f1']-base['snare']['f1'],
          'tomF1':s['tom']['f1']-base['tom']['f1'],
        }
    same_n=sum(x['same_n'] for x in agree);cross_n=sum(x['cross_n'] for x in agree)
    same_num=sum((x['same_match_rate'] or 0)*x['same_n'] for x in agree)
    cross_num=sum((x['cross_match_rate'] or 0)*x['cross_n'] for x in agree)
    report['familyReferenceAgreement']['aggregate']={
      'same_n':same_n,'same_match_rate':same_num/same_n if same_n else None,
      'cross_n':cross_n,'cross_match_rate':cross_num/cross_n if cross_n else None,
      'lift':same_num/same_n-cross_num/cross_n if same_n and cross_n else None
    }
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Open/Closed Hi-Hat + Arrangement v43','',
      'Reference chart.mid is scoring-only. Prediction uses drums.mp3 plus offvocal.mp3 structure; no reference MIDI is loaded in the browser stage.','',
      '## Exact synchronized nanairo teacher observation','',
      '- GM42 closed and GM46 open are strongly separated by 5–18 kHz decay in the supplied synchronized pair.',
      '- That pair contains 240 GM46 events but zero open->open transitions, so it is not used as sole evidence for open-only runs.',
      '',
      '## Five-song browser comparison','',
      '| variant | strict HH macro F1 | closed F1 | open F1 | collapsed hat/ride onset F1 | arrangement changes |',
      '|---|---:|---:|---:|---:|---:|']
    for c in configs:
        s=report['variants'][c]['summary']
        lines.append(f"| {c} | {s['strictHatMacroF1']:.6f} | {s['closed']['f1']:.6f} | {s['open']['f1']:.6f} | {s['metalHatOnset']['f1']:.6f} | {s['arrangementChanged']} |")
    a=report['familyReferenceAgreement']['aggregate']
    lines += ['','## Reference-only structural learning check','',
      f"- same-family corresponding-slot articulation agreement: {a['same_match_rate']:.4f} (n={a['same_n']})" if a['same_match_rate'] is not None else '- same-family agreement: n/a',
      f"- cross-family corresponding-slot articulation agreement: {a['cross_match_rate']:.4f} (n={a['cross_n']})" if a['cross_match_rate'] is not None else '- cross-family agreement: n/a',
      f"- same-family lift: {a['lift']:+.4f}" if a['lift'] is not None else '- lift: n/a',
      '',
      '## Guardrails','',
      '- Arrangement rescoring changes 42/46 articulation only; it creates no new hit.',
      '- Ride-rounding variants are scored both strictly and with ride accepted as a hat-family onset.',
      '- Kick/snare/tom must remain unchanged before any production adoption.',
      '- A/A\' are structural-family labels, not verse/chorus semantics.',
      '']
    MD.write_text('\n'.join(lines))
    print('\n'.join(lines))

if __name__=='__main__':main()
