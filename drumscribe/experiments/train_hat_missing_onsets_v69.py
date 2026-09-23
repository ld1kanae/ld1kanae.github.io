"""Audio-only high-band onset rescue, evaluated with song-held-out Open MIDI.

This is research code: no runtime changes are made. Run from repository root.
"""
import json
import subprocess
from bisect import bisect_left, bisect_right
from pathlib import Path

import mido
import numpy as np
from scipy.signal import find_peaks, stft
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from train_hat_mp3_transfer_v68 import SONGS, EXP, ROOT, audio, features, midi_notes, score

OUTPUT = EXP / 'results-hat-missing-onsets-v69.json'
EVENTS = json.loads((EXP / 'results-hat-sync-candidate-promote-predictions-v67.json').read_text())['songs']


def close(sorted_times, t, tolerance=.08):
    pos = bisect_left(sorted_times, t)
    return any(abs(sorted_times[j] - t) <= tolerance
               for j in range(max(0, pos - 1), min(len(sorted_times), pos + 1)))


def peak_times(path):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-ac', '1',
                                   '-ar', '22050', '-f', 'f32le', '-'])
    x = np.frombuffer(raw, dtype='<f4')
    f, t, spectrum = stft(x, fs=22050, nperseg=1024, noverlap=804, boundary='zeros')
    high = np.abs(spectrum[f >= 5000])
    flux = np.maximum(0, np.diff(high, axis=1)).sum(axis=0)
    # Global audio-only candidate policy fixed before reading labels.
    peaks, _ = find_peaks(flux, distance=8, prominence=np.quantile(flux, .75) * .3)
    return t[peaks + 1], flux[peaks], flux


def make_song(song):
    directory = ROOT / 'DruMaster/songs' / song
    meta = json.loads((directory / 'song.json').read_text())['playback']
    shift = float(meta['stemOffsetSec']) + float(meta.get('midiOffsetSec', 0))
    truth = midi_notes(directory / 'chart.mid', shift)
    events = EVENTS[song]['off']['events']
    art = sorted(e['time'] for e in events if e['group'] in ('hat', 'open_hat', 'ride', 'pedal_hat', 'crash'))
    hands = sorted(e['time'] for e in events if e['group'] in ('snare', 'tom', 'hat', 'open_hat', 'ride', 'crash'))
    times, heights, flux = peak_times(directory / 'drums.mp3')
    candidate = [(float(t), float(v)) for t, v in zip(times, heights)
                 if not close(art, t) and .2 < t < len(flux) * 220 / 22050 - .7]
    samples = audio(directory / 'drums.mp3')
    art_next = sorted(e['time'] for e in events if e['group'] in ('hat', 'open_hat', 'pedal_hat', 'ride'))
    kept, X = [], []
    median_height = float(np.median(heights)) + 1e-10
    for t, height in candidate:
        k = bisect_right(art_next, t + 1e-8)
        # Keep acoustic features and a two-hand capacity flag. The latter is
        # computed from predictions only; it never reads the teacher chart.
        used_hands = sum(abs(v - t) <= .035 for v in hands[max(0, bisect_left(hands, t)-3):bisect_right(hands, t+.035)])
        if used_hands >= 2:
            continue
        nearest = min((abs(v-t) for v in art[max(0, bisect_left(art,t)-2):bisect_left(art,t)+2]), default=1.5)
        row = features(samples, t, art_next[k] if k < len(art_next) else None)
        row.extend([np.log1p(height / median_height), min(nearest, 1.5)])
        X.append(row)
        kept.append(t)
    truth_open = sorted(t for t, n in truth if n == 46)
    truth_available = [t for t in truth_open if not close(art, t)]
    # Training targets are greedy one-to-one; unmatched peaks are negatives.
    labels = np.zeros(len(kept), dtype=int)
    options = sorted((abs(t - u), i, j) for i, t in enumerate(kept)
                     for j, u in enumerate(truth_available) if abs(t-u) <= .08)
    used_i, used_j = set(), set()
    for _, i, j in options:
        if i not in used_i and j not in used_j:
            labels[i] = 1
            used_i.add(i)
            used_j.add(j)
    return {'name': song, 'events': events, 'truth': truth, 'times': kept, 'X': np.array(X),
            'y': labels, 'missingOpen': len(truth_available), 'reachable': len(used_j)}


def evaluate(song, p, t):
    out = list(song['events'])
    for at, prob in zip(song['times'], p):
        if prob >= t:
            out.append({'time': at, 'note': 46, 'group': 'open_hat'})
    return score(out, song['truth'], song['name'] == 'arcaround'), len(out) - len(song['events'])


def main():
    data = {song: make_song(song) for song in SONGS}
    result = {'schema': 1, 'candidateRule': '5–11 kHz spectral positive flux, 10 ms hop, 80 ms peak distance; exclude existing metal ±80 ms and full two-hand clusters',
              'songs': {s: {'candidates': len(d['times']), 'missingOpen': d['missingOpen'],
                             'reachableOpen': d['reachable'], 'baseline': score(d['events'], d['truth'], s == 'arcaround')}
                        for s, d in data.items()}, 'variants': {}}
    for name in ('logistic', 'extra'):
        result['variants'][name] = {}
        for held in SONGS:
            X = np.vstack([data[s]['X'] for s in SONGS if s != held])
            y = np.concatenate([data[s]['y'] for s in SONGS if s != held])
            model = (make_pipeline(StandardScaler(), LogisticRegression(C=.5, class_weight='balanced', max_iter=2000))
                     if name == 'logistic' else ExtraTreesClassifier(n_estimators=160, max_depth=12,
                         min_samples_leaf=3, class_weight='balanced', random_state=69, n_jobs=-1))
            model.fit(X, y)
            p = model.predict_proba(data[held]['X'])[:, 1]
            result['variants'][name][held] = {str(t): {'score': evaluate(data[held], p, t)[0],
                                                        'added': evaluate(data[held], p, t)[1]}
                                                for t in (.5, .7, .85, .95)}
            print(name, held, [(t, result['variants'][name][held][str(t)]['added'],
                                round(result['variants'][name][held][str(t)]['score']['macro'], 4))
                               for t in (.5, .7, .85, .95)], flush=True)
    def aggregate(rows):
        return sum(2 * sum(r[k]['tp'] for r in rows) /
                   (sum(r[k]['pred'] for r in rows) + sum(r[k]['ref'] for r in rows))
                   for k in ('closed', 'open')) / 2
    result['aggregate'] = {'baseline': aggregate([result['songs'][s]['baseline'] for s in SONGS])}
    for name in result['variants']:
        result['aggregate'][name] = {str(t): {'macro': aggregate([result['variants'][name][s][str(t)]['score'] for s in SONGS]),
                                              'added': sum(result['variants'][name][s][str(t)]['added'] for s in SONGS)}
                                     for t in (.5, .7, .85, .95)}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(result['aggregate'])


if __name__ == '__main__':
    main()
