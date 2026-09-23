"""Evaluate next-hit tail/choke features + GMD sequence priors on HF Open-HH rescue candidates.

Strict source policy
--------------------
- songs_context: trained only from other DruMaster songs.
- songs_choke: trained only from other DruMaster songs; adds prediction-side
  next-existing-hat decay/continuity features.
- gmd_sequence_prior: fixed symbolic score from models/gmd-kst/
  hihat-sequence-patterns-v2.json. No DruMaster chart labels train this score.
- score_fusion: logistic meta-model trained only on out-of-fold SOURCE SCORES
  (songs_choke probability + fixed GMD score). Training rows from GMD and songs
  are never concatenated.

The frozen production baseline may contain historical GMD augmentation. It is
only the comparator/base transcription here. Rescue adds GM46 only.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression

ROOT = Path(".")
EXP = ROOT / "drumscribe/experiments"
MODELS = ROOT / "drumscribe/models"
SONGS = ["arcaround", "diamondvirgin", "kaiju", "nanairo", "ray"]
THRESHOLDS = [.55, .62, .68, .74, .80, .86, .90, .93, .96, .98, .995, 1.01]
BASE_SEED = 31000
BASE_CACHE = {}


def baseline_cached(d, held, train, hx, hy, gx, gy, seed):
    """Return one frozen base transcription for an exact held/train/seed key.

    The same open/closed lists are reused by every variant so a no-op selector
    is mathematically guaranteed to equal the reported baseline.
    """
    key = (held, tuple(train), int(seed))
    if key not in BASE_CACHE:
        bo, bc, diag = baseexp.baseline_for(d, held, train, hx, hy, gx, gy, seed)
        BASE_CACHE[key] = (tuple(bo), tuple(bc), dict(diag))
    bo, bc, diag = BASE_CACHE[key]
    return list(bo), list(bc), dict(diag)


def loadmod(name, path):
    sp = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


baseexp = loadmod("chseq_base", EXP / "open_hat_source_separated_hf_loo.py")
ctx = baseexp.ctx
hf = baseexp.hf
ov = baseexp.ov


def sig(x):
    x = np.clip(x, -30, 30)
    return 1.0 / (1.0 + np.exp(-x))


def logit(p):
    p = min(max(float(p), 1e-5), 1.0 - 1e-5)
    return math.log(p / (1.0 - p))


def robust(X):
    if not len(X):
        return X
    med = np.median(X, axis=0)
    q1 = np.percentile(X, 25, axis=0)
    q3 = np.percentile(X, 75, axis=0)
    return np.clip((X - med) / np.maximum(q3 - q1, 1e-3), -8, 8).astype(np.float32)


def rms_abs(x, a, b):
    i = max(0, int(a * hf.SR))
    j = min(len(x), int(b * hf.SR))
    if j <= i:
        return 1e-8
    z = x[i:j]
    return float(np.sqrt(np.mean(z * z) + 1e-12))


def signal_next_hit_features(x, t, next_t):
    early = rms_abs(x, t + .015, t + .055)
    gap = float(next_t - t) if next_t is not None else 9.0
    available = next_t is not None and .09 <= gap <= 1.20
    horizon = min(.65, max(.10, (gap - .03) if available else .65))

    fracs = (.14, .30, .48, .66, .84)
    vals = []
    ts = []
    for f in fracs:
        c = t + horizon * f
        vals.append(rms_abs(x, c - .010, c + .010))
        ts.append(horizon * f)
    vals = np.maximum(np.asarray(vals, float), 1e-10)
    logs = np.log(vals / max(early, 1e-10))
    slope = float(np.polyfit(np.asarray(ts, float), logs, 1)[0]) if len(logs) >= 2 else 0.0
    monotonic = float(np.mean(np.diff(logs) <= .05)) if len(logs) > 1 else 0.0

    if available:
        pre = rms_abs(x, next_t - .055, next_t - .020)
        attack = rms_abs(x, next_t, next_t + .025)
        post1 = rms_abs(x, next_t + .045, next_t + .085)
        post2 = rms_abs(x, next_t + .110, next_t + .180)
    else:
        pre = rms_abs(x, t + .50, t + .56)
        attack = rms_abs(x, t + .56, t + .59)
        post1 = rms_abs(x, t + .59, t + .63)
        post2 = rms_abs(x, t + .63, t + .70)

    eps = 1e-10
    return np.asarray([
        math.log((vals[0] + eps) / (early + eps)),
        math.log((vals[2] + eps) / (early + eps)),
        math.log((vals[-1] + eps) / (early + eps)),
        slope,
        monotonic,
        float(np.mean(np.exp(np.clip(logs, -20, 5)))),
        math.log((pre + eps) / (early + eps)),
        math.log((attack + eps) / (early + eps)),
        math.log((post1 + eps) / (early + eps)),
        math.log((post2 + eps) / (early + eps)),
        math.log((post2 + eps) / (pre + eps)),
        math.log((post2 + eps) / (attack + eps)),
    ], np.float32)


def next_hit_features(x, xhf, times, anchors):
    anchors = np.asarray(sorted(float(t) for t in anchors), float)
    rows = []
    for i, t in enumerate(np.asarray(times, float)):
        j = int(np.searchsorted(anchors, t + .060, side="left"))
        next_t = float(anchors[j]) if j < len(anchors) else None
        k = int(np.searchsorted(anchors, t - .060, side="right")) - 1
        prev_t = float(anchors[k]) if k >= 0 else None
        next_gap = (next_t - t) if next_t is not None else 9.0
        prev_gap = (t - prev_t) if prev_t is not None else 9.0
        b = signal_next_hit_features(x, t, next_t)
        h = signal_next_hit_features(xhf, t, next_t)

        eb = rms_abs(x, t + .015, t + .055)
        eh = rms_abs(xhf, t + .015, t + .055)
        if next_t is not None and .09 <= next_gap <= 1.20:
            pb = rms_abs(x, next_t - .055, next_t - .020)
            ph = rms_abs(xhf, next_t - .055, next_t - .020)
        else:
            pb = rms_abs(x, t + .50, t + .56)
            ph = rms_abs(xhf, t + .50, t + .56)

        rows.append(np.concatenate([
            np.asarray([
                min(prev_gap, 2.0),
                min(next_gap, 2.0),
                1.0 if next_t is not None and next_gap <= 1.20 else 0.0,
                math.log((eh + 1e-10) / (eb + 1e-10)),
                math.log((ph + 1e-10) / (pb + 1e-10)),
            ], np.float32),
            b,
            h,
        ]))
    return np.stack(rows) if rows else np.zeros((0, 29), np.float32)


def prep_item(d, s, sos):
    print("CHSEQ_PREP", s, flush=True)
    x = hf.decode(s, "drums.mp3")
    flux, hlev, bands = hf.hf_stream(x)
    times, score, ids = hf.peak_candidates(flux, hlev)
    duration = len(x) / hf.SR
    valid = times < duration - .7
    times = times[valid]
    ids = ids[valid]
    keep = np.asarray([not hf.near(d[s]["hats"], t, .060) for t in times], bool)
    times = times[keep]
    ids = ids[keep]

    extra = hf.candidate_extra(times, ids, flux, hlev, bands)
    acoustic = hf.extract_at(x, times, d[s]["X"]["timbre"])
    fz = hf.robust1(flux)
    hz = hf.robust1(hlev)
    raw_score = np.asarray(score)
    sc = raw_score[ids] if len(ids) else np.zeros(0)
    aux = []
    for i, z in zip(ids, sc):
        lo = max(0, i - 2)
        hi = min(len(score), i + 3)
        aux.append([
            baseexp.hfctx.sig(z),
            baseexp.hfctx.sig(np.mean(score[lo:hi])),
            baseexp.hfctx.sig(np.max(score[lo:hi])),
            baseexp.hfctx.sig(hz[i]),
            baseexp.hfctx.sig(fz[i]),
        ])
    aux = np.asarray(aux, np.float32) if aux else np.zeros((0, 5), np.float32)
    base = np.concatenate([acoustic, aux, extra], axis=1)
    fake = {"times": times, "Xc": base}
    Xctx, info = ctx.context_features(d, s, fake)
    Xctx = baseexp.strip_grid(Xctx, base.shape[1])

    xhf = sosfiltfilt(sos, x).astype(np.float32)
    dyn = next_hit_features(x, xhf, times, d[s]["hats"])
    Xchoke = np.concatenate([Xctx, robust(dyn)], axis=1)
    y = ctx.one_to_one_labels(times, d[s]["refs"][46])
    info = {
        **info,
        "oneToOnePositive": int(y.sum()),
        "featuresContext": int(Xctx.shape[1]),
        "featuresChoke": int(Xchoke.shape[1]),
        "nextHitFeatureCount": int(dyn.shape[1]) if dyn.ndim == 2 else 0,
    }
    return {"times": times, "Xctx": Xctx, "Xchoke": Xchoke, "y": y, "info": info}


def abs_slot(t, side):
    bpm = float(side.get("bpm") or 120.0)
    beat = 60.0 / max(bpm, 1e-6)
    phase = float(side.get("barPhaseSec") or side.get("beatPhaseSec") or 0.0)
    return int(round((float(t) - phase) / (beat / 4.0)))


def genre_weights(gmd, hats, side):
    obs = np.zeros(16, float)
    for t in hats:
        obs[abs_slot(t, side) % 16] += 1.0
    obs /= np.linalg.norm(obs) + 1e-12
    rows = []
    for name, g in gmd["genres"].items():
        ref = np.asarray(g["slotOpen"], float) + np.asarray(g["slotClosed"], float)
        ref /= np.linalg.norm(ref) + 1e-12
        rows.append((name, float(np.dot(obs, ref))))
    sims = np.asarray([v for _, v in rows], float)
    w = np.exp(8.0 * (sims - np.max(sims)))
    w /= w.sum() + 1e-12
    return {name: float(z) for (name, _), z in zip(rows, w)}


def pattern_tables(gmd):
    out = {}
    for name, g in gmd["genres"].items():
        rows = []
        for r in g.get("topBarPatterns", []):
            p = r["pattern"]
            occ = 0
            opn = 0
            for i, ch in enumerate(p[:16]):
                if ch in ("C", "O"):
                    occ |= 1 << i
                if ch == "O":
                    opn |= 1 << i
            rows.append((occ, opn, int(r["count"]), int(occ.bit_count())))
        out[name] = rows
    return out


def pattern_prob(rows, slot, obs_mask, slotp):
    den = 0.0
    num = 0.0
    obs_n = int(obs_mask.bit_count())
    sb = 1 << slot
    for pmask, omask, count, pn in rows:
        if not (pmask & sb):
            continue
        missing = int((obs_mask & ~pmask).bit_count())
        extra = abs(pn - obs_n)
        w = float(count) * math.exp(-1.35 * missing - .12 * extra)
        den += w
        if omask & sb:
            num += w
    if den <= 1e-12:
        return float(slotp)
    return float((num + 6.0 * slotp) / (den + 6.0))


def gmd_sequence_scores(gmd, tables, d, s, item):
    side = d[s]["side"]
    hslots = {abs_slot(t, side) for t in d[s]["hats"]}
    kslots = set()
    sslots = set()
    for t, group, pitch in d[s]["rows"]:
        if group == "kick":
            kslots.add(abs_slot(t, side))
        elif group == "snare":
            sslots.add(abs_slot(t, side))

    bybar = {}
    for h in hslots:
        b = h // 16
        bybar[b] = bybar.get(b, 0) | (1 << (h % 16))

    gw = genre_weights(gmd, d[s]["hats"], side)
    top_names = [k for k, _ in sorted(gw.items(), key=lambda q: q[1], reverse=True)[:6]]
    top_mass = sum(gw[k] for k in top_names)
    global_base = float(gmd["global"]["openRate"])
    cache = {}
    scores = []

    for t in item["times"]:
        a = abs_slot(t, side)
        sl = a % 16
        mask9 = 0
        for bit, off in enumerate(range(-4, 5)):
            if off == 0 or (a + off) in hslots:
                mask9 |= 1 << bit
        ksm = 0
        for bit, off in enumerate((-1, 0, 1)):
            if a + off in kslots:
                ksm |= 1 << bit
            if a + off in sslots:
                ksm |= 1 << (bit + 3)
        b = a // 16
        bmask = bybar.get(b, 0) | (1 << sl)

        p = 0.0
        used = 0.0
        for name, w in gw.items():
            g = gmd["genres"][name]
            slotp = g["pOpenGivenHatSlot"][sl]
            if slotp is None:
                slotp = g["openRate"]
            slotp = float(slotp)

            rec = g.get("hatContext9", {}).get(str(mask9))
            if rec:
                hp = (float(rec["open"]) + 10.0 * slotp) / (float(rec["count"]) + 10.0)
            else:
                hp = slotp

            rec = g.get("ksContext6", {}).get(str(ksm))
            if rec:
                kp = (float(rec["open"]) + 16.0 * slotp) / (float(rec["count"]) + 16.0)
            else:
                kp = slotp

            if name in top_names:
                ck = (name, sl, bmask)
                if ck not in cache:
                    cache[ck] = pattern_prob(tables[name], sl, bmask, slotp)
                pp = cache[ck]
            else:
                pp = slotp

            gp = sig(.45 * logit(hp) + .20 * logit(kp) + .25 * logit(pp) + .10 * logit(slotp))
            p += w * gp
            used += w

        p = p / max(used, 1e-12)
        scores.append(float(sig(logit(p) - logit(global_base))))

    return np.asarray(scores, float), {
        "genreTop": sorted(gw.items(), key=lambda q: q[1], reverse=True)[:6],
        "genreTopMass": float(top_mass),
    }


def p1(m, X):
    if not len(X):
        return np.zeros(0)
    p = m.predict_proba(X)
    cls = list(m.classes_)
    return p[:, cls.index(1)] if 1 in cls else np.zeros(len(X))


def fit_songs(items, songs, key, seed):
    XX = []
    yy = []
    for s in songs:
        y = items[s]["y"]
        pos = np.flatnonzero(y == 1)
        neg = np.flatnonzero(y == 0)
        rng = np.random.default_rng(seed + SONGS.index(s) * 47)
        cap = max(400, 5 * len(pos))
        if len(neg) > cap:
            neg = rng.choice(neg, cap, replace=False)
        ids = np.sort(np.concatenate([pos, neg]))
        XX.append(items[s][key][ids])
        yy.append(y[ids])
    X = np.concatenate(XX)
    y = np.concatenate(yy)
    m = ExtraTreesClassifier(
        n_estimators=520,
        max_depth=16,
        min_samples_leaf=3,
        max_features="sqrt",
        class_weight="balanced",
        random_state=seed,
        n_jobs=-1,
    )
    m.fit(X, y)
    return m, {"rows": len(y), "positive": int(y.sum()), "features": int(X.shape[1])}


def oof_scores(items, outer, seed):
    rows = []
    ys = []
    for i, val in enumerate(outer):
        tr = [s for s in outer if s != val]
        sm, _ = fit_songs(items, tr, "Xchoke", seed + i)
        rows.append(np.column_stack([p1(sm, items[val]["Xchoke"]), items[val]["gmdSeq"]]))
        ys.append(items[val]["y"])
    return np.concatenate(rows), np.concatenate(ys)


def fit_fusion(items, outer, seed):
    X, y = oof_scores(items, outer, seed)
    m = LogisticRegression(C=.45, class_weight="balanced", max_iter=1600, random_state=seed)
    m.fit(X, y)
    return m, {"rows": len(y), "positive": int(y.sum()), "features": 2}


def score_variant(items, s, variant, songs_model=None, fusion=None):
    if variant == "songs_context":
        return p1(songs_model, items[s]["Xctx"])
    if variant == "songs_choke":
        return p1(songs_model, items[s]["Xchoke"])
    if variant == "gmd_sequence_prior":
        return items[s]["gmdSeq"]
    if variant == "score_fusion":
        sp = p1(songs_model, items[s]["Xchoke"])
        return p1(fusion, np.column_stack([sp, items[s]["gmdSeq"]]))
    raise KeyError(variant)


def choose_threshold(d, items, outer, variant, hx, hy, gx, gy, seed):
    cache = {}
    for i, val in enumerate(outer):
        tr = [s for s in outer if s != val]
        sm = None
        fm = None
        train = {}
        if variant == "songs_context":
            sm, train = fit_songs(items, tr, "Xctx", seed + i)
        elif variant == "songs_choke":
            sm, train = fit_songs(items, tr, "Xchoke", seed + i)
        elif variant == "score_fusion":
            sm, st = fit_songs(items, tr, "Xchoke", seed + i)
            fm, ft = fit_fusion(items, tr, seed + 100 + i)
            train = {"songs": st, "fusion": ft}
        bo, bc, bdiag = baseline_cached(d, val, tr, hx, hy, gx, gy, 32000 + SONGS.index(val))
        prob = score_variant(items, val, variant, sm, fm)
        cache[val] = (bo, bc, bdiag, prob, train)

    base = {s: ctx.articulation(v[0], v[1], d[s]["refs"]) for s, v in cache.items()}
    bsum = ctx.aggregate(base)
    ranking = []
    for th in THRESHOLDS:
        per = {}
        for s, (bo, bc, bdiag, prob, _) in cache.items():
            add = baseexp.select_add(d, s, items[s], prob, th, bo)
            per[s] = ctx.articulation(sorted(bo + add), bc, d[s]["refs"])
        a = ctx.aggregate(per)
        eligible = (
            a["open"]["precision"] >= bsum["open"]["precision"] - .025
            and a["open"]["f1"] > bsum["open"]["f1"]
            and a["macroF1"] > bsum["macroF1"]
        )
        utility = a["macroF1"] + .08 * a["open"]["precision"]
        ranking.append({"threshold": th, "eligible": eligible, "utility": utility, "summary": a})
    ranking.sort(key=lambda r: (r["eligible"], r["utility"]), reverse=True)
    best = next((r for r in ranking if r["eligible"]), None)
    return (best["threshold"] if best else 1.01), {"base": bsum, "ranking": ranking}


def evaluate(d, items, variant, hx, hy, gx, gy):
    per = {}
    folds = {}
    for oi, held in enumerate(SONGS):
        outer = [s for s in SONGS if s != held]
        th, inner = choose_threshold(d, items, outer, variant, hx, hy, gx, gy, 23000 + oi * 50)
        sm = None
        fm = None
        train = {}
        if variant == "songs_context":
            sm, train = fit_songs(items, outer, "Xctx", 24000 + oi)
        elif variant == "songs_choke":
            sm, train = fit_songs(items, outer, "Xchoke", 24000 + oi)
        elif variant == "score_fusion":
            sm, st = fit_songs(items, outer, "Xchoke", 24000 + oi)
            fm, ft = fit_fusion(items, outer, 25000 + oi)
            train = {"songs": st, "fusion": ft}

        bo, bc, bdiag = baseline_cached(d, held, outer, hx, hy, gx, gy, BASE_SEED + SONGS.index(held))
        prob = score_variant(items, held, variant, sm, fm)
        add = baseexp.select_add(d, held, items[held], prob, th, bo)
        met = ctx.articulation(sorted(bo + add), bc, d[held]["refs"])
        per[held] = met
        folds[held] = {
            "threshold": th,
            "metrics": met,
            "base": bdiag,
            "train": train,
            "candidate": items[held]["info"],
            "gmdSequence": items[held]["gmdDiag"],
            "selected": len(add),
            "addedTpDiagnostic": sum(ov.near(d[held]["refs"][46], t, .080) for t in add),
            "scoreMax": float(np.max(prob)) if len(prob) else 0.0,
            "inner": inner,
        }
        print("CHSEQ_FOLD", variant, held, json.dumps({
            "threshold": th,
            "open": met["open"],
            "selected": len(add),
            "tpDiag": folds[held]["addedTpDiagnostic"],
        }), flush=True)
    return {"summary": ctx.aggregate(per), "songs": per, "folds": folds}


def main():
    d = ov.local_prepare()
    hx, hy, gx, gy, manifest = ov.gmd_collect()
    gmd = json.loads((MODELS / "gmd-kst/hihat-sequence-patterns-v2.json").read_text())
    if not gmd.get("sourceSeparation", {}).get("gmdOnly"):
        raise RuntimeError("GMD v2 source separation violated")

    sos = butter(4, [5000, 18000], btype="bandpass", fs=hf.SR, output="sos")
    items = {s: prep_item(d, s, sos) for s in SONGS}
    tables = pattern_tables(gmd)
    for s in SONGS:
        gp, gd = gmd_sequence_scores(gmd, tables, d, s, items[s])
        items[s]["gmdSeq"] = gp
        items[s]["gmdDiag"] = gd
        items[s]["info"]["gmdScoreMean"] = float(np.mean(gp)) if len(gp) else 0.0
        items[s]["info"]["gmdScoreMax"] = float(np.max(gp)) if len(gp) else 0.0
        print("CHSEQ_COUNTS", s, json.dumps(items[s]["info"]), flush=True)

    base_per = {}
    for i, held in enumerate(SONGS):
        tr = [s for s in SONGS if s != held]
        bo, bc, _ = baseline_cached(d, held, tr, hx, hy, gx, gy, BASE_SEED + SONGS.index(held))
        base_per[held] = ctx.articulation(bo, bc, d[held]["refs"])
    baseline = ctx.aggregate(base_per)

    saved = json.loads((EXP / "results-open-hat-hf-context-rank-best-v1.json").read_text())
    prior_best = saved.get("retainedStrictSummary") or saved.get("strictVariants", {}).get("forest_context", {}).get("summary")
    if prior_best is None:
        prior_best = baseline

    out = {
        "schema": 1,
        "description": "Next-hit tail/choke + GMD sequence-prior LOO over independent HF Open-HH candidates.",
        "sourcePolicy": {
            "trainingRowsPooled": False,
            "songsContextAndChoke": "DruMaster other-song LOO rows only",
            "gmdSequence": "fixed GMD-only derived symbolic score",
            "fusion": "OOF source scores only; no GMD rows concatenated with song rows",
            "syncNanairoTeacherUsed": False,
        },
        "gmdAsset": "drumscribe/models/gmd-kst/hihat-sequence-patterns-v2.json",
        "baselineProductionApprox": baseline,
        "previousNonGridHFBest": prior_best,
        "candidates": {s: items[s]["info"] for s in SONGS},
        "variants": {},
    }

    for variant in ("songs_context", "songs_choke", "gmd_sequence_prior", "score_fusion"):
        q = evaluate(d, items, variant, hx, hy, gx, gy)
        ss = q["summary"]
        q["passesBaselineGuard"] = (
            ss["open"]["f1"] > baseline["open"]["f1"]
            and ss["macroF1"] > baseline["macroF1"]
            and ss["open"]["precision"] >= baseline["open"]["precision"] - .025
        )
        q["beatsPreviousBest"] = (
            ss["open"]["f1"] > prior_best["open"]["f1"]
            and ss["macroF1"] > prior_best["macroF1"]
            and ss["open"]["precision"] >= prior_best["open"]["precision"] - .025
        )
        out["variants"][variant] = q
        print("CHSEQ_RESULT", variant, json.dumps({
            "baselineGuard": q["passesBaselineGuard"],
            "beatsPreviousBest": q["beatsPreviousBest"],
            "summary": ss,
        }), flush=True)

    eligible = [
        (q["summary"]["macroF1"], q["summary"]["open"]["f1"], name, q)
        for name, q in out["variants"].items()
        if q["beatsPreviousBest"]
    ]
    best = max(eligible) if eligible else None
    out["retainedStrict"] = best[2] if best else "previous_non_grid_hf_best"
    out["retainedStrictSummary"] = best[3]["summary"] if best else prior_best
    out["guard"] = {
        "kickSnareTomChanged": False,
        "existingNotesRemoved": False,
        "operation": "only add high-confidence GM46 rescue candidates",
        "adoptionRule": "must beat saved previous non-grid HF best, not merely baseline",
    }

    path = EXP / "results-open-hat-choke-gmd-sequence-loo.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print("CHSEQ_RETAINED", out["retainedStrict"], json.dumps(out["retainedStrictSummary"]), flush=True)


if __name__ == "__main__":
    main()
