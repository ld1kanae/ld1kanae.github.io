"""Unique-coverage audit for the independent high-frequency rescue stream.

This does not train or select any classifier. It answers one question:
does the audio-only HF candidate generator actually contain the missed open-HH
onsets, one-to-one, before classification?
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path

ROOT=Path("."); EXP=ROOT/"drumscribe/experiments"
SONGS=["arcaround","diamondvirgin","kaiju","nanairo","ray"]

def loadmod(name,path):
    sp=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
hf=loadmod("hf_cov_base",EXP/"open_hat_hf_offvocal_loo.py")

def greedy(pred,ref,w=.080):
    used=set();tp=0
    for t in sorted(pred):
        best=None
        for j,u in enumerate(ref):
            if j in used:continue
            d=abs(t-u)
            if d<=w and (best is None or d<best[0]):best=(d,j)
        if best is not None:
            used.add(best[1]);tp+=1
    return tp

def main():
    d=hf.prepare()
    out={"schema":1,"description":"One-to-one candidate coverage before rescue classification.","songs":{}}
    sums={"ref":0,"base":0,"hf":0,"union":0,"cand":0}
    for s in SONGS:
        ref=d[s]["refs"][46];base=d[s]["hats"];cand=d[s]["hf"]["times"].tolist()
        b=greedy(base,ref);h=greedy(cand,ref);u=greedy(sorted(base+cand),ref)
        q={"referenceOpen":len(ref),
           "existingHatCoverage":{"matched":b,"recall":b/len(ref) if ref else 0.},
           "hfRescueCoverage":{"matched":h,"recall":h/len(ref) if ref else 0.,"candidates":len(cand)},
           "unionCoverage":{"matched":u,"recall":u/len(ref) if ref else 0.}}
        out["songs"][s]=q
        sums["ref"]+=len(ref);sums["base"]+=b;sums["hf"]+=h;sums["union"]+=u;sums["cand"]+=len(cand)
        print("COVERAGE",s,json.dumps(q),flush=True)
    out["summary"]={
      "referenceOpen":sums["ref"],
      "existingHatMatched":sums["base"],"existingHatRecall":sums["base"]/sums["ref"],
      "hfMatched":sums["hf"],"hfRecall":sums["hf"]/sums["ref"],
      "unionMatched":sums["union"],"unionRecall":sums["union"]/sums["ref"],
      "hfCandidateCount":sums["cand"]
    }
    (EXP/"results-open-hat-hf-coverage.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(out["summary"],indent=2),flush=True)
if __name__=="__main__":main()
