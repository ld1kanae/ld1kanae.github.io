"""Unlabeled song adaptation using existing predicted 42/46 as pseudo teachers.

Held-out song reference MIDI is used only for the final score. All same-song
pseudo labels come from the previously generated browser predictions.
"""
import json
from bisect import bisect_right

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from train_hat_missing_onsets_v69 import SONGS, EXP, ROOT, make_song, evaluate
from train_hat_mp3_transfer_v68 import audio, features

OUT = EXP / 'results-hat-song-adaptation-v71.json'
THRESHOLDS = (.5, .7, .85, .95, .98)


def probability(train, labels, test):
    scale = StandardScaler().fit(train)
    x = np.clip(scale.transform(train), -8, 8)
    xt = np.clip(scale.transform(test), -8, 8)
    model = LogisticRegression(C=.35, class_weight='balanced', max_iter=500)
    model.fit(x, labels)
    return model.predict_proba(xt)[:, 1]


def pseudo_features(song, events):
    samples = audio(ROOT / 'DruMaster/songs' / song / 'drums.mp3')
    art = sorted(e['time'] for e in events if e['group'] in ('hat', 'open_hat', 'ride', 'pedal_hat'))
    source = [e for e in events if e['group'] in ('hat', 'open_hat')]
    x = []
    for e in source:
        next_index = bisect_right(art, e['time'] + 1e-8)
        x.append(features(samples, e['time'], art[next_index] if next_index < len(art) else None))
    return np.asarray(x), np.asarray([e['group'] == 'open_hat' for e in source], int)


def main():
    data = {s: make_song(s) for s in SONGS}
    pseudo = {s: pseudo_features(s, data[s]['events']) for s in SONGS}
    result = {'schema': 1, 'source': 'unlabeled in-song predicted Hat/Open events, no held-out chart for adaptation',
              'thresholds': THRESHOLDS, 'songs': {}, 'variants': {}}
    for s in SONGS:
        result['songs'][s] = {'pseudoOpen': int(sum(pseudo[s][1])),
                              'pseudoClosed': int(len(pseudo[s][1]) - sum(pseudo[s][1])),
                              'baseline': evaluate(data[s], np.zeros(len(data[s]['times'])), 1.01)[0]}
    for name in ('pseudo_only', 'global_only', 'average', 'agreement'):
        result['variants'][name] = {}
    for held in SONGS:
        tr = [s for s in SONGS if s != held]
        X = np.vstack([data[s]['X'][:, :14] for s in tr])
        y = np.concatenate([data[s]['y'] for s in tr])
        test = data[held]['X'][:, :14]
        global_p = probability(X, y, test)
        px, py = pseudo[held]
        if sum(py) < 8 or sum(py == 0) < 8:
            song_p = global_p.copy()
        else:
            song_p = probability(px[:, :14], py, test)
        for name, p in (
            ('pseudo_only', song_p),
            ('global_only', global_p),
            ('average', (song_p + global_p) / 2),
            ('agreement', np.minimum(song_p, global_p)),
        ):
            result['variants'][name][held] = {}
            for t in THRESHOLDS:
                metric, n = evaluate(data[held], p, t)
                result['variants'][name][held][str(t)] = {'added': n, 'macro': metric['macro'],
                                                           'open': metric['open'], 'closed': metric['closed']}
        print(held, 'anchors', result['songs'][held]['pseudoOpen'],
              'pseudo@.85', result['variants']['pseudo_only'][held]['0.85']['added'],
              'macro', result['variants']['pseudo_only'][held]['0.85']['macro'], flush=True)
    def aggregate(rows):
        return sum(2*sum(r[k]['tp'] for r in rows) /
                   (sum(r[k]['pred'] for r in rows)+sum(r[k]['ref'] for r in rows))
                   for k in ('open','closed'))/2
    result['aggregate'] = {'baseline': aggregate([result['songs'][s]['baseline'] for s in SONGS])}
    for name in result['variants']:
        result['aggregate'][name] = {}
        for t in THRESHOLDS:
            rows = [result['variants'][name][s][str(t)] for s in SONGS]
            result['aggregate'][name][str(t)] = {'macro': aggregate(rows),
                                                 'added': sum(r['added'] for r in rows),
                                                 'newOpenTP': sum(r['open']['tp'] - result['songs'][s]['baseline']['open']['tp']
                                                                  for s,r in zip(SONGS,rows))}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['aggregate'],indent=2), flush=True)


if __name__ == '__main__':main()
