"""Prepare normalized DSP and MDX drum stems for one validation song."""
from __future__ import annotations
import argparse,shutil,subprocess
from pathlib import Path
from drumsep import separate as dsp_separate
from mdxnet_infer import separate as mdx_separate

def dsp_path(result,key):
    aliases={"kick":["kick"],"snare":["snare"],"tom":["tom"],"hat":["hihat","hat"],"cymbal":["cymbal"]}[key]
    for k,v in (getattr(result,"stems",{}) or {}).items():
        if any(a in str(k).lower() for a in aliases):return Path(v)
    raise KeyError((key,getattr(result,"stems",{})))

def flac(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    subprocess.check_call(["ffmpeg","-y","-v","error","-i",str(src),"-ac","1","-ar","44100","-compression_level","8",str(dst)])

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--song",required=True);ap.add_argument("--out",required=True);ap.add_argument("--cache",required=True)
    a=ap.parse_args();root=Path(".");out=Path(a.out)/a.song;cache=Path(a.cache);cache.mkdir(parents=True,exist_ok=True)
    src=root/"DruMaster/songs"/a.song/"drums.mp3"
    work=out/"work";dspdir=work/"dsp";mdxdir=work/"mdx";dspdir.mkdir(parents=True,exist_ok=True);mdxdir.mkdir(parents=True,exist_ok=True)

    print("DSP",a.song,flush=True)
    dr=dsp_separate(str(src),output_dir=str(dspdir),enhanced=True)
    for k in ("kick","snare","tom","hat","cymbal"):
        flac(dsp_path(dr,k),out/"dsp"/f"{k}.flac")

    print("MDX",a.song,flush=True)
    mr=mdx_separate(str(src),output_dir=str(mdxdir),model_name="drumsep-6stem",device="cpu",cache_dir=cache,progress=True)
    mapping={
      "kick":mr["kick"],"snare":mr["snare"],"tom":mr.get("toms") or mr["tom"],
      "hat":mr.get("hh") or mr.get("hihat"),"ride":mr["ride"],"crash":mr["crash"]
    }
    for k,v in mapping.items():flac(Path(v),out/"mdx"/f"{k}.flac")
    shutil.rmtree(work,ignore_errors=True)
    print("DONE",a.song,flush=True)

if __name__=="__main__":main()
