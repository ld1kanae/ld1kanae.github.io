"""Offline, song-held-out comparison of per-hit and adjacent-hit hat acoustics.

The supplied review is never used for fitting or threshold selection. Reference
MIDI on the five test songs is read only for training on the other four songs
and for scoring after the prediction. No runtime code is modified.
"""
from __future__ import annotations

import json
from bisect import bisect_right
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from train_hat_mp3_transfer_v68 import ROOT, EXP, SONGS, audio, features, midi_notes, score, unique_labels

EVENTS = json.loads((EXP/'results-hat-sync-candidate-promote-predictions-v67.json').read_text())['songs']
OUT = EXP/'results-hat-pair-contrast-v72.json'
REVIEW = json.loads((EXP/'reviews/kimi-wa-shijin-hihat-review-v1.json').read_text())['reviews']
UPLOADED_MIDI = ROOT.resolve().parent/'kimiwa-shijin-fresh-v72.mid'
UPLOADED_AUDIO = ROOT.resolve().parent/'upload/君は詩人になった [drums].wav'
METALS = (42, 44, 46, 49, 51)


def midi_events(path):
    return sorted((t, n) for t, n in midi_notes(path) if n in METALS)


def extraction(samples, events, labels=None):
    art = sorted(e['time'] for e in events if e['group'] in ('hat', 'open_hat', 'pedal_hat', 'ride'))
    hats = [e for e in events if e['group'] in ('hat', 'open_hat')]
    x = []
    for e in hats:
        i = bisect_right(art, e['time']+1e-8)
        x.append(features(samples, e['time'], art[i] if i < len(art) else None))
    return {'events': events, 'hats': hats, 'X': np.asarray(x),
            'labels': np.asarray([int(v == 46) if v in (42, 46) else -1
                                  for v in labels], int) if labels is not None else None}


def rows_for(song):
    folder = ROOT/'DruMaster/songs'/song
    meta = json.loads((folder/'song.json').read_text())['playback']
    shift = float(meta['stemOffsetSec'])+float(meta.get('midiOffsetSec', 0))
    truth = midi_notes(folder/'chart.mid', shift)
    events = EVENTS[song]['off']['events']
    return extraction(audio(folder/'drums.mp3'), events, unique_labels(events, truth)), truth


def fit(rows):
    x = np.vstack([r['X'][r['labels'] >= 0] for r in rows])
    y = np.concatenate([r['labels'][r['labels'] >= 0] for r in rows])
    return make_pipeline(StandardScaler(), LogisticRegression(C=.4, class_weight='balanced', max_iter=1000)).fit(x, y)


def fit_pair(rows):
    x, y = [], []
    for row in rows:
        for i in range(len(row['hats'])-1):
            a, b = row['hats'][i:i+2]
            if not .16 < b['time']-a['time'] < .36:continue
            la, lb = row['labels'][i:i+2]
            if la < 0 or lb < 0 or la == lb:continue
            # Only opposite-articulation pairs teach the phase. A pair model
            # cannot assert that any arbitrary pair ought to alternate.
            diff = row['X'][i+1]-row['X'][i]
            x.extend([diff, -diff]);y.extend([int(lb), int(la)])
    if not x:return None, 0
    model = make_pipeline(StandardScaler(), LogisticRegression(C=.35, max_iter=1000))
    model.fit(np.asarray(x), np.asarray(y))
    return model, len(x)//2


def predict_pair(row, individual, pair_model, min_pair=.85, min_individual=.65):
    """Promote only an existing Closed; retain onset count and all non-HH."""
    result = [dict(e) for e in row['events']]
    index = {id(e):i for i,e in enumerate(row['events'])}
    candidates = []
    for i in range(len(row['hats'])-1):
        a,b = row['hats'][i:i+2]
        if not .16 < b['time']-a['time'] < .36:continue
        if a['group'] == b['group'] == 'open_hat':continue
        p=float(pair_model.predict_proba([(row['X'][i+1]-row['X'][i]).tolist()])[0,1])
        for j, prob in ((i,1-p),(i+1,p)):
            h=row['hats'][j]
            if h['group'] != 'hat' or prob < min_pair or individual[j] < min_individual:continue
            candidates.append((prob*individual[j], index[id(h)]))
    for _, idx in sorted(candidates, reverse=True):
        result[idx].update(group='open_hat',note=46)
    return result


def aggregate(scores):
    return {g:{'tp':sum(s[g]['tp'] for s in scores),
               'pred':sum(s[g]['pred'] for s in scores),
               'ref':sum(s[g]['ref'] for s in scores)} for g in ('closed','open')}


def main():
    loaded={s: rows_for(s) for s in SONGS}
    results={'schema':1,'method':'four-song train, one-song score; preselected thresholds',
             'thresholds':{'individual':.65,'pair':.85},'songs':{},'review':{}}
    for held in SONGS:
        train=[loaded[s][0] for s in SONGS if s!=held]
        row,truth=loaded[held]
        individual=fit(train).predict_proba(row['X'])[:,1]
        pair_model,pairs=fit_pair(train)
        before=score(row['events'],truth,held=='arcaround')
        if pair_model is None:
            after=before;changed=0
        else:
            pred=predict_pair(row,individual,pair_model)
            after=score(pred,truth,held=='arcaround')
            changed=sum(e['note']==46 and old['note']==42 for e,old in zip(pred,row['events']))
        results['songs'][held]={'trainOppositePairs':pairs,'baseline':before,'pairContrast':after,'promoted':changed}
        print(held,'train pairs',pairs,'promoted',changed,'HH F1',before['macro'],after['macro'],flush=True)
    for name in ('baseline','pairContrast'):
        s=aggregate([results['songs'][song][name] for song in SONGS])
        results[name]={'closed':s['closed'],'open':s['open'],
                       'macro':sum(2*s[g]['tp']/(s[g]['pred']+s[g]['ref']) for g in s)/2}
    if UPLOADED_MIDI.exists():
        notes=midi_events(UPLOADED_MIDI)
        events=[{'time':t,'note':n,'group':{42:'hat',44:'pedal_hat',46:'open_hat',49:'crash',51:'ride'}[n]}
                for t,n in notes]
        row=extraction(audio(UPLOADED_AUDIO),events)
        model=fit([loaded[s][0] for s in SONGS])
        pair_model,pairs=fit_pair([loaded[s][0] for s in SONGS])
        pred=predict_pair(row,model.predict_proba(row['X'])[:,1],pair_model)
        for review in REVIEW:
            a,b=review['startSec'],review['endSec']
            def counts(xs):
                return {str(n):sum(a <= e['time'] < b and e['note']==n for e in xs)
                        for n in METALS}
            results['review'][str(review['index'])]={'rangeSec':[a,b],
                'baseline':counts(events),'pairContrast':counts(pred),
                'scope':'existing onsets only; review is not exact note-level reference'}
    OUT.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print('aggregate',results['baseline']['macro'],results['pairContrast']['macro'],flush=True)


if __name__=='__main__':main()
