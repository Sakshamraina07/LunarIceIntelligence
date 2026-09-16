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
| G7 | `assert_paths_agree.py` | the API and the static analysis disagreeing on a terrain quantity; **on permanent shadow — PSR area and PSR pixel count, at tolerance 0** (`--inject shadow` adds one pixel to one path); or **a quantity both paths produce that is neither compared nor excluded with a reason** (`--inject coverage`), because a gate that checks three of six named quantities certifies only the three it knows about |
| G8 | `stamp_methods.py --check` | a figure in METHODS whose source artifact has moved since it was written; **a labelled figure that disagrees with the artifact it is mapped to** (`--inject-digit` perturbs one digit of the Jaccard row and the untouched checker must find it); and a duplicated or out-of-order section number |
| G9 | `assert_pdf_agrees_with_analysis.py` | a figure in the PDF report that is not in the artifacts the report renders — read from the rendered bytes, not from the generator's inputs |
| G10 | `assert_upper_bounds_labelled.py` | a bounded figure quoted as if it were a rate, anywhere in the tracked sources |
| G12 | `assert_incidence_geometry.py` | an incidence field in which any pixel sits below the look angle — an identity on a convex body — and any consumer that uses one |
| G13 | (same script) | two consumers disagreeing about the look count of the one CPR field |
| G15 | `verify_production.mjs --all-states` | a production bundle that does not mount, a map at zero size, zero site markers, a tripped error boundary, an application console error, or two rendered strings disagreeing about whether the backend is reachable — loaded in headless Chromium in **all three** backend states (unreachable / not-ingested / ok); **and the host-state badge having been deleted rather than moved** — G15 clicks through to stage 09, asserts the badge and its explanation render there with the wording the observed state calls for, and asserts no host-state badge has drifted back into the global header |
| G16 | `assert_pdf_refuses_without_rasters.py` | a PDF issued on a host that answers but holds no rasters — the loader must raise, the endpoint must return 409, and a report that *is* issued must name the host state it was issued under |
| G17 | `assert_sweep_grid_discriminates.py` | a precomputed sweep whose cells are all the same number — a vacuous criterion behind a control surface; an axis re-centred on the published threshold instead of built from the measured field; a grid that varies on one axis while the other slider is dead; a stated crossing factor that is not the published threshold over the measured crossing; or a grid that disagrees with the analysis artifact at the published operating point |
| G18 | `assert_report_state_is_its_own.py` | a Report control that infers its state from `/api/mission` — a different capability, which needs the rasters the report does not — or a report claiming the rasters are a precondition for issuing it, or a missing/non-discriminating `/report/status` probe |
| G19 | `assert_withdrawn_claims_absent.py` | a claim this project withdrew reappearing in any tracked source. Eight terms, each anchored on the **claim** and never on a figure — `--list` prints every term with the sentence it forbids and why it was withdrawn. Tombstones, negations and the two defect registers (METHODS §0, PRD §1.2) are excused by scope, so the project can still *record* what it withdrew |
| G20 | `assert_degeneracy_replicates.py` | the CPR/DOP identity failing to replicate on the **independent 2020-03-05 acquisition** — a different orbit, look angle (26.0° vs 20.0°), PRF, pulse bandwidth and output grid (90 m vs 25 m). Asserts the measured crossing sits within 1e-3 relative of the closed-form 0.0042610829, that CPR predicted from DOP matches stored CPR to float precision, and that zero pixels pass the joint screen on either product. A failure here means the file is being read wrong, not that the algebra varies |
| G21 | `assert_artifact_matches_repro_command.py` | an artifact whose stated reproduction command produces a different number of runs than the artifact holds (nine windows named, nine windows present). Written with G22 and left out of `verify_all.py` until 2026-09-16; a gate nobody runs is a file |
| G22 | `assert_ceilings_have_own_label.py` | an ENL ceiling predicted from another product's label; a declared look count that is not the label's; pre-registered and post-hoc groups reported together |
| G23 | `assert_wilson_on_effective_samples.py` | a candidate-area interval taken on correlated pixels rather than on the 38 050 effective samples (`round(2 337 086 / 61.4207)`), a headline that is not the effective interval, or a correlation area copied rather than read |
| G24 | `assert_lola_product_agrees.py` | any document naming a LOLA product or post spacing that its provenance file does not state — the frame DEM (`LDEM_80S_20M`, 20 m) and the horizon product (`LDEM_80S_80M`, 80 m → 240 m) are two products and must never be quoted for each other |
| G25 | `assert_counts_are_read.py` | README, viva or METHODS spelling a gate count or an apparatus-failure count that disagrees with the thing counted (`len(verify_all.GATES)`; METHODS §0's register) |
| G26 | `paper/assert_figures_embed_fonts.py` | a figure that does not regenerate, or a regenerated PDF carrying a Type 3 font or an unembedded one — read from the PDF's own font dictionaries |
| G27 | `verify_data_provenance.py` | a bundle on disk that is not the product the manuscript names — seven representations (filename timestamp, per-line epochs, geometry vs byte count, manifest, look-bandwidth identity, SHA-256) that a wrong or edited file cannot all satisfy |
| G28 | `check_repo_complete.py` | a repository missing what the paper promises (C1–C6), or carrying data or a secret anywhere in its history (C7) |
| G29 | `literature_search_gate.py` | a manuscript literature count that is not the count in the screening record, a relevant paper marked as reporting one of the three criteria, or the inaccessible record dropped rather than named |
| G30 | `assert_manuscript_claims.py` | a Section V–VI sensitivity claim that is not the number its artifact holds — Slepian ceilings and their ordering, the Table V row at 5.83, the background sweep, the correlated-ratio rows, the joint rate, K-clutter within its Monte Carlo error, patch bias, the four stationarity blocks (`--inject <check>` breaks one) |
| G31 | `robustness_gate.py` | the amplitude-CPR ceiling failing to survive the data being wrong — nine corruptions (shuffled, mis-scaled, random, constant); the crossing must sit within 1e-4 of the ceiling wherever the DOP population reaches the threshold, never above it, and no pixel may pass |

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
