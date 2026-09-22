"""One-song MDX23C 6-stem + ADTOF benchmark on kaiju.

External pretrained models only. DruMaster chart.mid is scoring-only.
The DrumSep checkpoint has unclear original licensing; this experiment does
not commit or redistribute the checkpoint or separated audio.
"""
from __future__ import annotations
import json, tempfile, time
from pathlib import Path

import pretty_midi

from mdxnet_infer import separate
from adtof_pytorch import transcribe_to_midi

ROOT=Path(".");EXP=ROOT/"drumscribe/experiments";SONG="kaiju"


def extract_expected(mid_path:Path,stem:str):
    midi=pretty_midi.PrettyMIDI(str(mid_path))
    notes=[]
    expected={
      "kick":(35,36),
      "snare":(38,38),
      "toms":(47,47),
      "hh":(42,42),
      "ride":(49,51),
      "crash":(49,49),
    }[stem]
    source_pitch,target_pitch=expected
    for inst in midi.instruments:
        for n in inst.notes:
            if n.pitch==source_pitch:
                notes.append((n.start,target_pitch,n.velocity))
    return notes


def main():
    src=ROOT/"DruMaster/songs"/SONG/"drums.mp3"
    outmid=EXP/"generated-mdx6-kaiju.mid"
    t0=time.time()
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        stems=separate(str(src),output_dir=str(td/"stems"),model_name="drumsep-6stem",device="cpu")
        sep_sec=time.time()-t0
        print("STEMS",stems,flush=True)
        combined=[]
        transcribe_sec={}
        for stem in ("kick","snare","toms","hh","ride","crash"):
            path=Path(stems[stem])
            m=td/f"{stem}.mid"
            a=time.time()
            transcribe_to_midi(path,m,thresholds=[.22*1.15,.24*1.15,.32*1.15,.22*1.15,.30*1.15],device="cpu")
            transcribe_sec[stem]=time.time()-a
            combined.extend(extract_expected(m,stem))

        midi=pretty_midi.PrettyMIDI(initial_tempo=120)
        inst=pretty_midi.Instrument(program=0,is_drum=True)
        for t,p,v in sorted(combined):
            inst.notes.append(pretty_midi.Note(velocity=max(1,min(127,v)),pitch=p,start=t,end=t+.06))
        midi.instruments.append(inst);midi.write(str(outmid))

    # score only after predictions are complete
    import importlib.util
    spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
    ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
    meta=json.loads((ROOT/"DruMaster/songs"/SONG/"song.json").read_text())
    shift=float(meta["playback"]["stemOffsetSec"])+float(meta["playback"].get("midiOffsetSec",0))
    pred=ev.midi_events(outmid);truth=ev.midi_events(ROOT/"DruMaster/songs"/SONG/"chart.mid")
    sc=ev.score(pred,truth,shift);sc["confusion"]=ev.confusion(pred,truth,shift)
    report={"schema":1,"song":SONG,"separation_sec":sep_sec,"transcribe_sec":transcribe_sec,
            "elapsed_sec":time.time()-t0,"summary":sc}
    (EXP/"results-mdx6-kaiju.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
      "separation_sec":sep_sec,"elapsed_sec":report["elapsed_sec"],
      "f1":sc["f1"],"by_group":sc["by_group"]
    },ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
