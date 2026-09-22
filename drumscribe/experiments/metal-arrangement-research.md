# Metal / hi-hat arrangement prior research notes

Date: 2026-09-22

## Purpose

The browser transcription reached roughly F1 0.786 after ADTOF integration,
but residual errors are concentrated in metal instruments:

- hand hi-hat
- pedal hi-hat
- ride
- crash

These instruments are not treated as independent one-shot classifications in
this experiment. Their musical role is strongly sequential and structural.

## Arrangement concepts used

### 1. Hat and ride are time-keeping states

A conventional drum arrangement often changes the right-hand time-keeping
surface between song sections. A verse/chorus or chorus/bridge contrast can be
created simply by switching a hi-hat pattern to ride while leaving much of the
rest of the groove intact.

Source:
- Sound On Sound, "Programming Realistic Drum Parts"
  https://www.soundonsound.com/techniques/programming-realistic-drum-parts

Implication for DrumScribe:
- do not classify each hat/ride hit independently;
- decode a persistent bar/section-level hat-vs-ride state;
- allow weak per-hit acoustic evidence to accumulate over multiple bars.

### 2. Fills and cymbal changes mark transitions

Drum fills are commonly used to transition into a changed time-keeping surface.
Educational material also demonstrates moving from eighth-note hi-hat through a
one-bar fill into ride, then returning through another fill.

Source:
- Drumeo, "192 Drum Beats You Can Play With The Stick Control Book"
  https://www.drumeo.com/beat/?p=28445

Implication:
- tom/snare activity before a bar boundary is useful context for a following
  crash or metal-state change.

### 3. Crash is a sparse structural accent

Production examples use crash accents to emphasize chorus entries / section
boundaries, while a repeating ride can provide the ongoing texture.

Source:
- Sound On Sound, "Mix Rescue: Dave Gerard"
  https://www.soundonsound.com/techniques/mix-rescue-dave-gerard

Implication:
- crash probability should be raised near a detected bar head, especially
  after fill-like activity;
- repeating periodic high-frequency events should be biased toward ride/hat,
  not repeated crash.

### 4. Pedal hi-hat is rhythmic, not only timbral

Pedal hi-hat is a distinct GM drum sound and can be used as a repeated rhythmic
voice, including off-beat emphasis. It therefore needs rhythmic-context
features, not only a single-hit template comparison.

Source:
- Sound On Sound, "Effective Drum Programming, Part 1"
  https://www.soundonsound.com/techniques/effective-drum-programming-part-1

Implication:
- pedal-hat inference should use neighboring hand-hat pattern, periodic phase,
  and repetition, while preserving a real detected onset requirement.

## External symbolic dataset

### Groove MIDI Dataset (GMD)

Official source:
https://magenta.tensorflow.org/datasets/groove

License:
Creative Commons Attribution 4.0 International (CC BY 4.0)

Properties relevant here:
- 13.6 h
- 1,150 MIDI performances
- more than 22,000 measures
- genre, tempo, beat/fill, time-signature metadata
- distinct note mappings for closed/open hi-hat, pedal hi-hat, ride and crash
- official train / validation / test split

For symbolic-only use, GMD is preferred over E-GMD; the official E-GMD page
also recommends the original GMD when only symbolic drum data is required.

DrumScribe uses:
- GMD v1.0.0 MIDI-only archive
- official **train split only**
- 4/4 performances only
- aggregate statistics only are committed to this repository

No GMD source MIDI files are committed.

Generated aggregate model:
- `drumscribe/models/gmd-metal-prior.json`
- attribution:
  `drumscribe/models/gmd-metal-prior-LICENSE.txt`

Current aggregate:
- 887 train/4-4 files
- 147,449 metal hits

Observed general priors:
- crash probability is substantially higher at 16th-position 0 (bar head)
  than at the other quarter-note heads;
- hat-dominant bars strongly tend to continue as hat;
- ride-dominant bars strongly tend to continue as ride;
- a bar-head metal hit following dense tom activity has much higher crash
  probability than an ordinary bar-head metal hit.

## Use of the supplied DruMaster chart.mid files

The five supplied reference MIDIs are not allowed to train the predictor and
then score the same song.

For arrangement-prior experiments, use leave-one-song-out:

1. choose one song as held-out evaluation song;
2. optionally build a small domain prior from the other four chart.mid files;
3. predict the held-out song from audio-derived features + GMD prior + the
   other-four prior;
4. only then compare to the held-out chart.mid.

Search includes `loo_weight=0`, so GMD-only and GMD+project-MIDI variants are
compared under the same held-out evaluation.

Relevant benchmark:
- `drumscribe/experiments/browser_metal_arrangement_prior.py`
- output:
  `drumscribe/experiments/results-browser-metal-arrangement-prior.json`

## Rejected / weak directions so far

- single-hit pedal-vs-hand-hat template ratio:
  distributions overlap heavily; no useful pedal recovery.
- temporal cymbal decay alone:
  current experiment strongly degrades overall / ride precision.
- independent hat->ride/crash reclassification from template ratio alone:
  insufficient; section persistence is necessary.

These failures are retained as experiment JSON/scripts rather than deleted.
