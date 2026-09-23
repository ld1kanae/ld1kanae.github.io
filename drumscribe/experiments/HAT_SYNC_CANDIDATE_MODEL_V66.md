# Synchronized Candidate Hi-Hat Model v66

Date: 2026-09-24

## Purpose

General Open/Closed hi-hat articulation rescoring learned from five fully synchronized WAV/MIDI pairs. The runtime model never reads chart MIDI, review ranges, song names, alternating-grid parity, or section labels.

Training candidates are the actual DrumScribe hat/open-hat candidates generated from the synchronized WAVs with the review-derived sequence repair OFF, fusion OFF, and the existing v57 Ride->Open rescue ON.

Positive class: Open HH (GM46).

Negative classes: Closed HH, Pedal HH, Ride, Crash, and unmatched/false DrumScribe candidates.

Total training candidates: 6,288.

## Model selection

The primary v65 ExtraTrees sweep showed that large models improve the five-song leave-one-song-out score, but browser model size was unnecessarily large.

A RandomForest compact sweep was therefore run with the same feature vector and fixed thresholds (Open >= 0.55, Closed <= 0.45, otherwise keep current articulation).

Selected candidate:

- 12 trees
- max depth 7
- min samples leaf 3
- class_weight=balanced
- max_features=sqrt
- fixed threshold 0.55 / 0.45
- serialized model about 25 KB
- LOOCV HH macro F1: **0.731444**
- v65 baseline HH macro F1: **0.628392**
- all five held-out songs improved

Per-song HH macro at random_state=42:

- arcaround: 0.220755 -> **0.627370**
- diamondvirgin: 0.190570 -> **0.377551**
- kaiju: 0.367628 -> **0.547408**
- nanairo: 0.901732 -> **0.916623**
- ray: 0.869218 -> **0.911274**

Aggregate:

- Closed F1: **0.658143**
- Open F1: **0.804745**
- HH macro: **0.731444**

## Seed stability

Ten additional seeds were checked for the compact RandomForest family.

12-tree/depth-7:

- mean HH macro: **0.7090476**
- min: **0.6850997**
- max: **0.7324770**
- 10/10 seeds: all five songs non-regressing
- worst observed per-song improvement across the sweep: **+0.00992**

6-tree/depth-6 was also tested and was smaller, but had weaker stability:

- mean HH macro: **0.7039767**
- min: **0.6755917**
- worst observed per-song improvement: **+0.00078**

Therefore the 12-tree model is preferred for production replay.

## Runtime placement

The model is applied after the existing v57 high-confidence Ride->Open rescue, matching the candidate distribution used for training. It only relabels existing GM42/GM46 candidates and cannot create/delete/retime Kick, Snare, or Tom events.

## Production gate

The model is not considered production-approved until a fresh Chromium replay against the repository five-song MP3/chart corpus confirms:

1. aggregate HH macro improvement;
2. no per-song HH macro regression;
3. exact Kick/Snare/Tom event-list equality;
4. exact Hat/Ride onset-list equality.

