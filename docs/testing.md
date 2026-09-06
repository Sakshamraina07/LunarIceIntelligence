# Verification

## One command

```bash
python -u backend/scripts/verify_all.py
```

Runs every gate, maps each to the statement it backs in **PRD section 6**, and
writes `docs/verification.json`. Roughly 2.5 minutes; `--skip-slow` omits the
three that re-read multi-gigabyte rasters and marks them **UNVERIFIED, not
passed**.

It asserts nothing of its own. Every verdict is produced by the gate that owns
it — a verifier computing its own opinion would be one more source of truth, and
this project has spent long enough removing those.

## The gates

| id | gate | what it refuses to let ship |
|---|---|---|
| G1 | `emit_provenance.py` | a value reaching the UI unmarked, marked MODELLED, absent without a reason, in the wrong unit, or a non-zero candidate area under an amplitude-only screen; **and a detection area without its confidence interval** |
| G2 | `validate_psr_vs_lola.py` | shadow that disagrees with the LOLA team's own published mask — currently Jaccard 0.714, ratio 1.174× |
| G3 | `search_landing_sites.py` | a site chosen on a coarse grid, a criterion that admits >99 % of the frame going unlabelled, or a site sitting on interpolated terrain without its verdict |
| G4 | `plan_traverse.py` | a route shorter than its own straight-line separation, or `UNREACHABLE` reported before connectivity is |
| G5 | `detection_statistics.py` | a candidate area without an interval, or a significance claim without a named look count |
| G6 | `hillshade_histogram.py` | a base filter set by eye — post-filter median > ~190 or >1 % clipping at 255 |
| G6b | `composite_contrast.py` | a science layer that hides the relief beneath it, tested on retention **and** correlation |
| G7 | `assert_paths_agree.py` | the API and the static analysis disagreeing on a terrain quantity |
| G8 | `stamp_methods.py --check` | a figure in METHODS whose source artifact has moved since it was written |
| G9 | `assert_pdf_agrees_with_analysis.py` | a figure in the PDF report that is not in the artifacts the report renders — read from the rendered bytes, not from the generator's inputs |
| G10 | `assert_upper_bounds_labelled.py` | a bounded figure quoted as if it were a rate, anywhere in the tracked sources |

`rebuild_all.py` runs G1, G5, G7, G8 and G9 on every rebuild, and **any non-zero exit
stops the build**, so a rebuild that would ship an unlabelled number fails before
it reaches disk.

## The browser gate

```bash
node frontend/scripts/verify_v8_view.mjs      # needs the dev server up
node frontend/scripts/capture_layers.mjs --tag after
```

Nine assertions on the live map — opening view, reset, marker and route
visibility measured rather than assumed, the zoom-out clamp, and no page errors.
Zero new dependencies: CDP over the global WebSocket in Node 22.

## Unit tests

```bash
python -m pytest -q backend/tests/
```

These cover the module contracts. **They are not the evidence** — the gates above
are. A passing unit test says a function does what its author expected; a passing
gate says a number on screen is real.

## Injection testing

Every assertion in G1 was verified by **making it fail on purpose** and checking
it caught the thing. So were the G5 interval gate, the G8 staleness stamp, the
G4 straight-line invariant, G9 — `--inject` adds a fabricated landing site with
the deleted list's own numbers (slope 6.7°, illumination 0.02, score 37.1) and
the gate names all six figures that are not in any artifact — and G10, whose
`--inject` writes one unlabelled quotation of a bounded figure and is caught.

G10's own first version **failed on its own test fixture**: the injection payload
was a string literal in the file, so the gate found an unlabelled occurrence in a
tracked source on every ordinary run. The payload is now constructed rather than
spelled. A gate that cries wolf gets waved through, which is the failure mode
that matters more than the one it was written for. An assertion that has never failed is an
assertion nobody has tested — and this project found five cases where the
verification apparatus itself was wrong (`METHODS.md` §0).
