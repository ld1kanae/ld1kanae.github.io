"""Export ADTOF-pytorch Frame_RNN to ONNX and verify numerical parity.

Artifacts:
- drumscribe/models/adtof-frame-rnn.onnx
- drumscribe/models/adtof-filterbank.f32
- drumscribe/models/adtof-model.json

The verification compares PyTorch and ONNX Runtime on:
1) random model-shaped input
2) the first 12 seconds of DruMaster/songs/ray/drums.mp3 after the official
   ADTOF-pytorch audio frontend.

No chart.mid/song.json is used.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch

from adtof_pytorch import (
    calculate_n_bins,
    create_frame_rnn_model,
    get_default_weights_path,
    load_pytorch_weights,
)
from adtof_pytorch.audio import create_adtof_processor

ROOT=Path(".")
OUT=ROOT/"drumscribe/models"
OUT.mkdir(parents=True,exist_ok=True)

ONNX=OUT/"adtof-frame-rnn.onnx"
FB=OUT/"adtof-filterbank.f32"
META=OUT/"adtof-model.json"


def model():
    n=calculate_n_bins()
    m=create_frame_rnn_model(n)
    wp=get_default_weights_path()
    if not wp or not Path(wp).exists():
        raise RuntimeError("ADTOF packaged weights were not found")
    m=load_pytorch_weights(m,wp,strict=False)
    return m.eval(),n


def export(m,n):
    dummy=torch.randn(1,600,n,1,dtype=torch.float32)
    with torch.no_grad():
        torch.onnx.export(
            m,
            dummy,
            ONNX,
            input_names=["input"],
            output_names=["activations"],
            dynamic_axes={
                "input":{0:"batch",1:"time"},
                "activations":{0:"batch",1:"time"},
            },
            opset_version=17,
            do_constant_folding=True,
            dynamo=False,
        )


def compare(m,x):
    with torch.no_grad():
        pt=m(torch.from_numpy(x)).cpu().numpy()
    sess=ort.InferenceSession(str(ONNX),providers=["CPUExecutionProvider"])
    ox=sess.run(["activations"],{"input":x})[0]
    d=np.abs(pt-ox)
    return {
        "shape":list(pt.shape),
        "mae":float(d.mean()),
        "max_abs":float(d.max()),
        "p99_abs":float(np.percentile(d,99)),
    }


def main():
    m,n=model()
    export(m,n)

    rng=np.random.default_rng(1234)
    random_x=rng.normal(0,.35,size=(1,731,n,1)).astype(np.float32)
    random_cmp=compare(m,random_x)

    processor=create_adtof_processor()
    audio=processor.load_audio(str(ROOT/"DruMaster/songs/ray/drums.mp3"))
    audio=audio[:processor.sample_rate*12]
    stft=processor.compute_stft(audio)
    filt=processor.apply_filterbank(stft).T.astype(np.float32)[...,None]
    audio_x=filt[None,...]
    audio_cmp=compare(m,audio_x)

    # Browser frontend constants/artifacts.
    processor.filterbank.astype("<f4").tofile(FB)
    info={
      "schema":1,
      "source":"xavriley/ADTOF-pytorch",
      "sampleRate":processor.sample_rate,
      "fps":processor.fps,
      "hopLength":processor.hop_length,
      "fftSize":processor.n_fft,
      "nBins":processor.n_bins,
      "nChannels":1,
      "classes":[
        {"name":"kick","midi":35,"threshold":0.22},
        {"name":"snare","midi":38,"threshold":0.24},
        {"name":"tom","midi":47,"threshold":0.32},
        {"name":"hat","midi":42,"threshold":0.22},
        {"name":"cymbal","midi":49,"threshold":0.30}
      ],
      "filterbankShape":list(processor.filterbank.shape),
      "filterbankFile":FB.name,
      "onnxFile":ONNX.name,
      "onnxBytes":ONNX.stat().st_size,
      "verification":{"random":random_cmp,"audio12s":audio_cmp},
    }
    META.write_text(json.dumps(info,indent=2)+"\n")
    print(json.dumps(info,indent=2))

    # Fail the workflow if export is numerically suspect.
    if random_cmp["max_abs"]>2e-4 or audio_cmp["max_abs"]>2e-4:
        raise SystemExit("ONNX parity check failed")


if __name__=="__main__":
    main()
