"""Create sample MIDI outputs without using chart.mid for transcription."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from evaluate import MIDI_PITCH, audio, candidates, features, midi_events, spectrum, templates


def vlq(n):
    out = [n & 127]
    while n >> 7:
        n >>= 7; out.insert(0, (n & 127) | 128)
    return bytes(out)


def midi(pred):
    ev = [(0, 0, bytes([255, 81, 3, 7, 161, 32]))]
    for t, group, confidence in pred:
        tick = max(0, round(t * 960)); pitch = MIDI_PITCH[group]
        vel = max(40, min(120, round(80 + 15 * math.log1p(confidence))))
        ev.extend([(tick, 2, bytes([153, pitch, vel])), (tick + 67, 1, bytes([137, pitch, 0]))])
    ev.sort(key=lambda row: (row[0], row[1], row[2][1] if len(row[2]) > 1 else 0))
    body = bytearray(); prev = 0
    for tick, _, data in ev:
        body.extend(vlq(tick-prev)); body.extend(data); prev = tick
    body.extend(bytes([0, 255, 47, 0]))
    return b'MThd' + (6).to_bytes(4, 'big') + bytes([0, 0, 0, 1, 1, 224]) + b'MTrk' + len(body).to_bytes(4, 'big') + body


def main():
    p = argparse.ArgumentParser(); p.add_argument('--data', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    tm = templates(args.data/'samples')
    for folder in sorted(args.data.iterdir()):
        if not (folder/'song.json').exists(): continue
        metadata = json.loads((folder/'song.json').read_text())
        actual = hashlib.sha256((folder/'drums.mp3').read_bytes()).hexdigest()
        assert actual == metadata['stems']['drums']['sha256'], f'{folder.name}: audio integrity mismatch'
        pred = candidates(*features(spectrum(audio(folder/'drums.mp3')), tm), 'band-precision')
        path = args.output/f'{folder.name}.mid'; path.write_bytes(midi(pred))
        parsed = midi_events(path)
        assert len(parsed) == len(pred), f'{folder.name}: MIDI round trip event count mismatch'
        assert all(group == group2 and abs(t-t2) < .001 for (t,group,_),(t2,group2,_) in zip(pred, parsed)), f'{folder.name}: MIDI time round trip mismatch'
        print(folder.name, len(pred), path, 'round trip OK', flush=True)


if __name__ == '__main__': main()
