"""Study spectrogram classification of v69's audio-only missing-onset peaks.

All five charts are read only after the MP3 peak generator has made candidates.
Each held-out song is excluded from the classifier fit. Thresholds are reported
as a sweep, not chosen using the held-out song for production.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import stft
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from train_hat_missing_onsets_v69 import SONGS, EXP, ROOT, make_song, evaluate

OUT = EXP / 'results-hat-spectrogram-v70.json'
SR, HOP, NFFT = 22050, 220, 1024
OFFSETS = np.array([-.12, -.09, -.06, -.04, -.02, 0, .02, .04,
                    .06, .09, .12, .16, .22, .30, .40, .52])
EDGES = np.geomspace(120, 10500, 25)
THRESHOLDS = (.6, .7, .8, .9, .95, .98)


def spectrum_features(song, times):
    path = ROOT / 'DruMaster/songs' / song / 'drums.mp3'
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
                                   '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'])
    audio = np.frombuffer(raw, '<f4')
    freq, frame_t, complex_spec = stft(audio, fs=SR, nperseg=NFFT,
                                       noverlap=NFFT-HOP, boundary='zeros')
    magnitude = np.abs(complex_spec)
    bands = []
    for a, b in zip(EDGES[:-1], EDGES[1:]):
        selected = (freq >= a) & (freq < b)
        bands.append(np.mean(magnitude[selected], axis=0))
    log_bands = np.log1p(10000 * np.asarray(bands, dtype=np.float32))
    centers = np.clip(np.rint(np.asarray(times) * SR / HOP).astype(int), 0,
                      log_bands.shape[1] - 1)
    # All peak times are unlabeled at prediction time. The within-song median
    # mitigates gain/recording differences without knowing the held-out chart.
    song_median = np.median(log_bands[:, centers], axis=1)
    offset_frames = np.rint(OFFSETS * SR / HOP).astype(int)
    index = np.clip(centers[:, None] + offset_frames[None, :], 0,
                    log_bands.shape[1] - 1)
    patch = np.transpose(log_bands[:, index], (1, 2, 0))
    centered = patch - song_median[None, None, :]
    return centered.reshape(len(times), -1).astype(np.float32)


def weights_for(data, training):
    out = []
    for song in training:
        y = data[song]['y']
        pos = int(sum(y)); neg = len(y) - pos
        # Equal weight per song and bounded rare-positive weighting. A single
        # positive in nanairo must not dominate the entire training set.
        wp = .5 / max(pos, 20)
        wn = .5 / max(neg, 1)
        out.extend(np.where(y == 1, wp, wn))
    out = np.asarray(out)
    return out * len(out) / sum(out)


def train_predict(data, held, variant):
    training = [song for song in SONGS if song != held]
    key = 'raw' if variant == 'raw_logistic' else 'spectrogram'
    X = np.vstack([data[s][key] for s in training])
    y = np.concatenate([data[s]['y'] for s in training])
    w = weights_for(data, training)
    scaler = StandardScaler().fit(X)
    X = np.clip(scaler.transform(X), -8, 8)
    X_held = np.clip(scaler.transform(data[held][key]), -8, 8)
    if variant == 'spectrogram_mlp':
        model = MLPClassifier(hidden_layer_sizes=(48,), alpha=.03,
                              batch_size=128, learning_rate_init=.0007,
                              max_iter=65, early_stopping=False, random_state=70)
    else:
        model = LogisticRegression(C=.15, max_iter=500, solver='lbfgs')
    model.fit(X, y, sample_weight=w)
    return model.predict_proba(X_held)[:, 1]


def main():
    data = {}
    for song in SONGS:
        d = make_song(song)
        d['raw'] = np.asarray(d['X'], dtype=np.float32)
        patch = spectrum_features(song, d['times'])
        d['spectrogram'] = np.hstack((patch, d['raw']))
        data[song] = d
        print('features', song, len(d['times']), int(sum(d['y'])), flush=True)
    variants = ('raw_logistic', 'spectrogram_logistic', 'spectrogram_mlp')
    results = {'schema': 1, 'candidateSource': 'unchanged v69 audio-only peak rule',
               'spectrogram': {'sampleRate': SR, 'fft': NFFT, 'hop': HOP,
                                'bands': 24, 'offsetsSec': OFFSETS.tolist(),
                                'center': 'unlabeled within-song peak median'},
               'thresholds': THRESHOLDS, 'songs': {}, 'variants': {}}
    for s, d in data.items():
        base = evaluate(d, np.zeros(len(d['times'])), 1.01)[0]
        results['songs'][s] = {'candidates': len(d['times']),
                               'labeledOpenPeaks': int(sum(d['y'])),
                               'baseline': base}
    for variant in variants:
        results['variants'][variant] = {}
        for held in SONGS:
            p = train_predict(data, held, variant)
            scores = {}
            for threshold in THRESHOLDS:
                metric, added = evaluate(data[held], p, threshold)
                scores[str(threshold)] = {'added': added, 'closed': metric['closed'],
                                          'open': metric['open'], 'macro': metric['macro']}
            results['variants'][variant][held] = scores
            print(variant, held, [(t, scores[str(t)]['added'],
                                  round(scores[str(t)]['macro'], 4))
                                 for t in THRESHOLDS], flush=True)
    def aggregate(rows):
        return sum(2 * sum(r[k]['tp'] for r in rows) /
                   (sum(r[k]['pred'] for r in rows) + sum(r[k]['ref'] for r in rows))
                   for k in ('closed', 'open')) / 2
    results['aggregate'] = {'baseline': aggregate([results['songs'][s]['baseline'] for s in SONGS])}
    for variant in variants:
        results['aggregate'][variant] = {}
        for t in THRESHOLDS:
            rows = [results['variants'][variant][s][str(t)] for s in SONGS]
            results['aggregate'][variant][str(t)] = {'macro': aggregate(rows),
                                                      'added': sum(r['added'] for r in rows),
                                                      'newOpenTP': sum(r['open']['tp'] - results['songs'][s]['baseline']['open']['tp']
                                                                       for s, r in zip(SONGS, rows))}
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(results['aggregate'], indent=2), flush=True)


if __name__ == '__main__':
    main()
