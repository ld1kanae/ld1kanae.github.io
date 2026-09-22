"""Generate browser template bank matching evaluate_v2.py.

Output layout is group-major [group][fft_bin], which is what transcribe.js
expects. Uses only DruMaster reference drum samples.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
import numpy as np

ROOT=Path(".")
EXP=ROOT/"drumscribe/experiments"

spec=importlib.util.spec_from_file_location("ev",EXP/"evaluate_v2.py")
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

GROUPS=["kick","snare","hat","tom","crash","ride","pedal_hat"]

def main():
    tmpl=ev.templates(ROOT/"DruMaster/assets/drums")  # bins x ORDER
    idx={g:i for i,g in enumerate(ev.ORDER)}
    spectra=[tmpl[:,idx[g]].astype(float).tolist() for g in GROUPS]
    out={
      "sampleRate":ev.SR,
      "fft":ev.FFT,
      "hop":ev.HOP,
      "groups":GROUPS,
      "spectra":spectra,
      "source":"../DruMaster/assets/drums/*.wav via evaluate_v2.templates"
    }
    (ROOT/"drumscribe/templates-v2.json").write_text(json.dumps(out,separators=(",",":"))+"\n")
    print(json.dumps({"groups":GROUPS,"bins":len(spectra[0])}))
if __name__=="__main__":main()
