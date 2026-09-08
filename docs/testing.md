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
| G8 | `stamp_methods.py --check` | a figure in METHODS whose source artifact has moved since it was written; **a labelled figure that disagrees with the artifact it is mapped to** (`--inject-digit` perturbs one digit of the Jaccard row and the untouched checker must find it); and a duplicated or out-of-order section number |
| G9 | `assert_pdf_agrees_with_analysis.py` | a figure in the PDF report that is not in the artifacts the report renders — read from the rendered bytes, not from the generator's inputs |
| G10 | `assert_upper_bounds_labelled.py` | a bounded figure quoted as if it were a rate, anywhere in the tracked sources |
| G12 | `assert_incidence_geometry.py` | an incidence field in which any pixel sits below the look angle — an identity on a convex body — and any consumer that uses one |
| G13 | (same script) | two consumers disagreeing about the look count of the one CPR field |
| G15 | `verify_production.mjs --all-states` | a production bundle that does not mount, a map at zero size, zero site markers, a tripped error boundary, an application console error, or two rendered strings disagreeing about whether the backend is reachable — loaded in headless Chromium in **all three** backend states (unreachable / not-ingested / ok); **and the host-state badge having been deleted rather than moved** — G15 clicks through to stage 09, asserts the badge and its explanation render there with the wording the observed state calls for, and asserts no host-state badge has drifted back into the global header |
| G16 | `assert_pdf_refuses_without_rasters.py` | a PDF issued on a host that answers but holds no rasters — the loader must raise, the endpoint must return 409, and a report that *is* issued must name the host state it was issued under |
| G17 | `assert_sweep_grid_discriminates.py` | a precomputed sweep whose cells are all the same number — a vacuous criterion behind a control surface; an axis re-centred on the published threshold instead of built from the measured field; a grid that varies on one axis while the other slider is dead; a stated crossing factor that is not the published threshold over the measured crossing; or a grid that disagrees with the analysis artifact at the published operating point |
| G18 | `assert_report_state_is_its_own.py` | a Report control that infers its state from `/api/mission` — a different capability, which needs the rasters the report does not — or a report claiming the rasters are a precondition for issuing it, or a missing/non-discriminating `/report/status` probe |

**The sequence skips G11 and G14 because those numbers were never allocated** —
no gate was written under either and none was deleted. G12 and G13 were named as
a pair when the two incidence defects were found; G15 was named when the blank
production page needed a gate. A gap in a numbered list of checks otherwise
reads like a check that used to pass, so it is stated here rather than closed:
renumbering would move G12, G13 and G15, which are cited by number in
`METHODS.md` and in the commit history, and a citation resolving to a different
gate is worse than a documented gap. `verify_all.py` asserts that neither number
ever comes back into use.

**G16 is verifiable locally only.** The deployed backend answers `NOT_INGESTED`
for `faustini`, so `/report/pdf/faustini` returns 409 in production and no PDF
exists there to check. That is the correct behaviour, not a limitation of the
gate — but it means the report itself is only ever exercised on a host that
holds the 9 GB of gitignored rasters, i.e. this one.

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

G16's injection was **wrong on its first pass, and passed anyway**. It injected
at the *generator* — handing it an empty bundle to see whether a PDF came out.
None did, so the gate printed INJECTION CAUGHT; but the generator had raised a
`KeyError` on the malformed dict, for a reason with nothing to do with the claim
under test. An injection that fails for the wrong reason tests nothing, and it is
the more dangerous kind of green light because it looks like one. The defect G16
exists to catch is *a loader that tolerates absence*, so that is what is now
injected: `report_data._read` is replaced by one that invents a document instead
of raising, exactly as a `.get(key, default)` would.

G15's header assertion **failed in state `unreachable` on a string that was
correct**. It read the whole top bar, and the Report control there says "backend
unreachable" because it is required to name the state it is in. A check that
cannot tell *a control describing itself* from *a badge describing the system*
would have forced the Report control to go quiet — causing the exact defect the
file exists to prevent. It now reads `.mc-topbar .mc-badge` only.

G8's digit check was **wrong twice before it was right**, and both versions were
caught by disbelieving a clean-looking result rather than by a test.

Its first version copied `assert_pdf_agrees_with_analysis.py` wholesale — every
numeric literal in a mapped section must appear in the artifact. That works for
the PDF because the PDF is *purely* a rendering. `METHODS.md` is not: §7.7's whole
table is closed forms computed in the prose, correctly absent from
`cpr_significance.json`. It produced **188 findings, almost all the checker's
fault** — and a gate that cries wolf gets waved through, which this project had
already learned once with G10. It is now anchored on **labels**: where the prose
names a quantity the artifact also names, in a table row, the number beside it
must be that artifact's value. That is exactly the shape the defect had.

Its `--inject-digit` was then wrong in the more dangerous direction: it
**appended a fabricated finding** to the results list, which proves the print
statement works and nothing else. That is METHODS §0's seventh instance committed
inside the fix for its twentieth. It now perturbs one digit of the real Jaccard
row in the document under test and requires the untouched checker to find it.

G10's own first version **failed on its own test fixture**: the injection payload
was a string literal in the file, so the gate found an unlabelled occurrence in a
tracked source on every ordinary run. The payload is now constructed rather than
spelled. A gate that cries wolf gets waved through, which is the failure mode
that matters more than the one it was written for. An assertion that has never failed is an
assertion nobody has tested — and this project found five cases where the
verification apparatus itself was wrong (`METHODS.md` §0).
