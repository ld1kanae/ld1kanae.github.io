"""Experimental five-way spectral masking and beat-pattern postprocessing.

The scorer and the MIDI labels are used only after predictions are frozen.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks

from evaluate import ORDER, SR, HOP, audio, candidates, features, midi_events, score, spectrum, templates


def separate(spec, tmpl):
    """Return additive nonnegative group spectra (kick/snare/tom/metal/other).

    Fit five kit spectra and a learned, broad residual with nonnegative least
    squares, then create soft masks. This is approximate in-kit separation, not
    a claim to isolate instruments from a complete mixed song.
    """
    order = [0, 1, 3, 2, 4]
    reference = np.column_stack([tmpl[:, i] for i in order])
    reference[:, 3] = .62 * tmpl[:, 2] + .38 * tmpl[:, 4]
    average = np.mean(spec, axis=1)
    reference = np.column_stack([reference, average])
    whitening = np.maximum(average, np.percentile(average, 35)) ** .35
    w = (reference / whitening[:, None]).astype('f4')
    w /= np.maximum(np.linalg.norm(w, axis=0), 1e-8)
    x = (spec / whitening[:, None]).astype('f4')
    projection = np.maximum(w.T @ x, 1e-7)
    h = projection.copy()
    gram = w.T @ w
    for _ in range(9):
        h *= projection / np.maximum(gram @ h, 1e-7)
    contribution = w[:, :, None] * h[None, :, :]
    masks = contribution / np.maximum(contribution.sum(axis=1, keepdims=True), 1e-7)
    return masks * spec[:, None, :]


def detect(stems, spec, tmpl, method='group', bpm=None):
    baseline, sim = features(spec, tmpl)
    base = candidates(baseline, sim, 'band-precision')
    # Measure class-specific attack in the separated component, not only in the
    # full mix. Toms require more than a spectral lookalike during snare hits.
    class_band = [(35, 140), (140, 900), (140, 900), (3000, 5500), (900, 5500), (900, 5500)]
    flux = []
    for k, (lo, hi) in enumerate(class_band):
        band = stems[:, k, :][(np.arange(stems.shape[0]) * SR / 1024 >= lo) & (np.arange(stems.shape[0]) * SR / 1024 < hi)]
        signal = np.maximum(band[:, 2:] - band[:, :-2], 0).sum(axis=0)
        signal = np.pad(signal, (2, 0))
        signal = np.maximum(signal - .6 * median_filter(signal, 101), 0)
        signal /= np.percentile(signal, 98) + 1e-7
        flux.append(signal)
    pred = []
    group_names = ['kick', 'snare', 'tom', 'hat', 'cymbal', 'other']
    if method in ('separation-only','hybrid','loop'):
        thresholds = [.56, .65, 2.1 if method != 'separation-only' else 1.2, .31, .75, 1.8]
        for k in range(5):
            s = flux[k]; floor = median_filter(s,201); peaks, _ = find_peaks(s, distance=int(([.075,.075,.09,.055,.12][k])*SR/HOP), prominence=.09)
            for p in peaks:
                if s[p] > max(thresholds[k], 2.3*floor[p]):
                    pred.append((p*HOP/SR,group_names[k],float(s[p])))
        if method in ('hybrid','loop'):
            # Source-specific detector for the overlapping metal band, with the
            # legacy low-frequency kick detector as a check on timbre mismatch.
            pred=[row for row in pred if row[1] in ('snare','hat','tom')]
            pred += [row for row in base if row[1] in ('kick','cymbal')]
            if method == 'loop':pred=rhythm(pred,flux,bpm)
    else:
        for t, g, v in base:
            k=group_names.index(g); p=round(t*SR/HOP)
            required = {'kick':.21,'snare':.25,'hat':.15,'tom':.38,'cymbal':.35}[g]
            if max(flux[k][max(0,p-2):p+3]) >= required:
                pred.append((t,g,v))
        if method in ('repeat', 'repeat-bpm'):
            pred = rhythm(pred, flux, bpm)
    return sorted(pred)


def rhythm(pred, flux, bpm=None):
    # Search recurring onset periodicity without using reference MIDI. A caller
    # may give a fixed BPM; blank input uses the audio periodicity instead.
    envelope = np.maximum(flux[0],flux[1])
    if bpm is None:
        lags = np.arange(round(.27*SR/HOP), round(.85*SR/HOP))
        corr = np.array([np.dot(envelope[lag:],envelope[:-lag]) for lag in lags])
        beat = int(lags[np.argmax(corr)])
    else:
        beat = round(60/bpm*SR/HOP)
    if beat < 20:return pred
    # Phase learned from stronger kick/snare attacks; half-beat subdivision.
    step=beat/2
    strong=np.array([round(t*SR/HOP) for t,g,v in pred if g in ('kick','snare') and v>.65])
    if not len(strong):return pred
    phases=np.arange(max(1,round(step)))
    votes=np.array([np.sum(np.exp(-.5*((strong-phase+step/2)%step-step/2)**2/3**2)) for phase in phases])
    phase=int(phases[np.argmax(votes)])
    out=[]; cym=np.array([t*SR/HOP for t,g,v in pred if g=='cymbal'])
    fills=np.array([t for t,g,v in pred if g=='tom'])
    for t,g,v in pred:
        p=t*SR/HOP
        near=abs((p-phase+step/2)%step-step/2)
        # Compare the same instrument one bar away before rejecting a weak
        # off-grid cymbal. Fills and genuinely strong off-grid hits survive.
        repeated=np.any(np.abs(np.abs(cym-p)-4*beat)<6)
        fill=np.any(np.abs(fills-t)<.45)
        if g=='cymbal' and v < 1.15 and near>7 and not (repeated or fill):continue
        out.append((t,g,v))
    return out


def main():
    a=argparse.ArgumentParser();a.add_argument('--data',type=Path,required=True);a.add_argument('--seconds',type=float,default=80);a.add_argument('--output',type=Path);args=a.parse_args()
    tmpl=templates(args.data/'samples'); results={}
    for song in sorted(args.data.iterdir()):
        if not (song/'song.json').exists():continue
        x=audio(song/'drums.mp3',args.seconds);s=spectrum(x);stems=separate(s,tmpl)
        meta=json.loads((song/'song.json').read_text());shift=meta['playback']['stemOffsetSec']+meta['playback'].get('midiOffsetSec',0)
        truth=[(t,g,p) for t,g,p in midi_events(song/'chart.mid') if 0<=t+shift<len(x)/SR]
        tests={'baseline':score(candidates(*features(s,tmpl),'band-precision'),truth,shift)}
        for method in ('separation-only','group','repeat','hybrid','loop'):
            tests[method]=score(detect(stems,s,tmpl,method),truth,shift)
        results[song.name]=tests
        print(song.name,{k:v['f1'] for k,v in tests.items()},flush=True)
    if args.output:args.output.write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n')


if __name__=='__main__':main()
