# METHODS

The actual method behind each number, with the numbers. `PROVENANCE.md` says
*what* every value is and where it came from; this says *how*, and what each
method can and cannot support.

Sections are added as phases land. Anything not listed here is not yet computed,
and `PROVENANCE.md` names the phase that will compute it.

## 0 · The recurring defect in this project

*Four patterns, twenty-two instances. Two of them are about descriptions drifting
from what they describe, one is about a transform written twice, and the fourth
is about a whole surface that had no check on it at all.*

**Six instances of one failure: a caption, a name or a summary that stopped
tracking the computation it describes.** The illumination layer's
`MODEL OUTPUT` badge over a real horizon computation; a `StepUnavailable`
heading above four measured values; a `within 2.00%` summary printed over a row
gated at 5%; one DEM product name hardcoded in twelve places and stale in all
twelve at once; and `dem_native_synthetic.tif` holding real LOLA elevation.

They are not five unrelated bugs, and the direction varies — two overstated, two
understated, one merely drifted. What they share is that a human wrote a
description once and nothing afterwards forced it to agree with the thing it
described. The fixes are all the same shape: make whatever produces the number
also produce the words about it, and fail the build when they part company. That
is what PRD rules 5a–5c, `emit_provenance.py`, `assert_paths_agree.py` and
`stamp_methods.py` exist to do. **Provenance discipline does not catch a stale
sentence; only a generator or a gate does.**

**The sixth drifted PESSIMISTIC, twice, in the same sentence.** The map banner
shown on a host without rasters named what needs the on-demand backend. First it
said the landing sites and rover routes did — both had become static artifacts,
drawn on the map *above the banner denying them*. That was corrected to "the
sensitivity studio, the stage panels and the PDF". Then `/api/sensitivity/{param}`
was changed to read the committed analysis artifact instead of scaling a
fabricated 8.75 km² base area, which made stage 09's sweep **tables** static too —
and the sentence was wrong again, still claiming a whole studio was unavailable
when what was actually unavailable was four re-query sliders.

> **A sentence naming more than is broken is the same defect as one naming
> less.** The first five instances overstated what the project had; this one
> overstated what it had lost. Both are a description that stopped tracking its
> computation, and understating your own work is not the safe direction — it is
> the same failure wearing modesty.

The consequence was visible: the badge derived from that sentence sat in the
global header beside VERDICT, so a screen on which the verdict, the rasters, the
sites, the traverse, the probe and both sweep tables were all rendering correctly
announced itself as degraded. The badge is not deleted — it moved to the stage a
no-raster host actually costs something, with its whole explanation.
`NEEDS_BACKEND` is now a single exported string, so the next drift has one place
to happen instead of three.

**And it drifted a third time, one commit later, in the commit that caused it.**
The badge went to the Sensitivity Studio because that stage's four sliders
re-queried the pipeline. §1.9 then precomputed the joint screen, the sliders
became a read of a static artifact, and stage 09 stopped depending on a host at
all — which made both the sentence *and the badge's location* wrong again, in the
same change that removed the dependency. A host-state badge on a stage with no
host dependency is the identical defect it was moved out of the header to fix,
one scope smaller. It now sits in stage 12, beside the PDF, which is the only
consumer left. G15 followed it **both** times: it clicks to stage 12, asserts the
badge and explanation render there, and asserts stage 09 shows none —
`--inject staleststage`.

**And a fifth, in red.** The mission endpoint's `NOT_INGESTED` message was
rendered as an `.mc-error` banner across the top of the map — after the host-state
overlay had been removed from that same screen for saying less than this one did.
The text itself is accurate and is the clearest writing in the app about what a
served host has: it names the product id, names the missing rasters, and says why
a served host reports absence rather than substituting generated data. But it is
not an *error*. After the sweep grid and the report-status fix, nothing on that
screen depends on the mission endpoint at all — the relief, the science layers,
the sites, the traverse, the probe, the verdict, stage 09's sweep and the PDF all
work without it.

> **Red is a claim.** Reserving it for conditions that actually break something is
> the entire value of having it. Painting a working screen red does not make the
> project look careful; it makes the one genuine failure indistinguishable from
> six harmless states.

The text is kept verbatim, in stage 12's host-state block, under *"What the
mission endpoint reports"* — moved, not summarised. G15 asserts both halves:
no host-state condition may be painted as an error on the main screen
(`--inject hosterror`), **and** the endpoint's own reason must still render on the
stage that owns host state (`--inject hostreason`), because "move it, delete
nothing" is only true if the destination renders it.

**A fourth time, in the move itself.** The badge's explanation was carried to
stage 12 verbatim, and its closing sentence — *"the two sweep tables below are
static artifacts"* — described stage 09. On stage 12 there are no sweep tables.
The text was moved without being reread, which is the drift in its purest form:
not a computation changing under a description, but a description changing
location while claiming the same surroundings. It was caught by loading the
deployed page and reading it, not by any check, and the check now exists: G15
extracts the block's card and asserts that a "sweep tables below" claim is only
made on a card that contains a sweep table, and a "report below" claim only on
one that contains a report control (`--inject wrongstage`).

> **The fix that removes a dependency has to carry the sentence describing it.**
> Four revisions of one passage, each correct when written, each falsified by a
> later improvement — and the last two falsified by the commits that were fixing
> the previous ones. This is not a sentence written carelessly; it is a sentence
> with no generator. That is why it needed a gate reading the rendered text
> against the rendered DOM, rather than a resolution to be more careful.

**Instance 19 — one document, two look counts, and the wrong one came first.**
§7.4 closed with *"the operative number for everything downstream is therefore
N ≈ 5, not 21"*. §7.7, four sections later, states in capitals that the operating
point is **N = 13.72**, because the pipeline boxcars σ⁰ before forming CPR and the
threshold touches the smoothed field. Both sentences were in this file at once,
and §7.4 is the one a reader reaches first. §7.4's own content was never wrong —
the *delivered product* really does measure 5.3–6.5 against a nominal 21 — it
just claimed a scope it had not established. A section that overreaches by one
clause is harder to catch than one that is simply incorrect, because everything
around the clause checks out.

**Instance 20 — the stamp's own documented blind spot, in the section that
carries the project's only external validation.** §5.10 reported Jaccard
**0.6732**, Dice 0.8047 and ratio 1.301 against the LOLA team's published PSR
mask. `docs/psr_validation.json` held **0.714229**, 0.833295 and 1.174153, and
the deployed site had been displaying 0.714 for days. The §5.10 numbers were the
*point-Sun* run; the finite solar disc shipped afterwards
(`solar_model.primary = "finite disc"`, radius 0.25°, confirmed by the shipped
`psr_pixels = 411535` matching the 0.25° branch of its own A/B and not the
464333 of the 0.0° branch), the validation was re-run, and the prose was not.
§5.9 and §5.10's pre-registration paragraph were still arguing from *"this model
treats the Sun as a point"* about a model that no longer existed.

> **The staleness stamp said in writing that it could not catch this.** *"It does
> not verify that any individual digit was transcribed correctly; only generation
> could do that."* The artifact's sha256 changed when the disc shipped, so G8
> fired, the stamp was refreshed — and refreshing the stamp is precisely the act
> of recording that the prose has been re-checked. It had not been. **A gate that
> documents its own blind spot has not mitigated it; it has only made the eventual
> failure quotable in advance.**

That blind spot is now closed rather than only named: `stamp_methods.py` extracts
every numeric literal from the sections an artifact maps to and asserts each one
appears in that artifact at the precision printed. It is
`assert_pdf_agrees_with_analysis.py`'s mechanism turned on this document. Ten
figures in §5.10 alone would have failed it the moment the disc shipped.

### The second pattern: the verification apparatus itself being wrong

Seven instances, and it is a distinct failure from the one above, because the
thing that has drifted is the thing meant to catch drift.

1. **`verify_map.mjs` asserted a pane v8 had removed.** It exited 3 before
   producing any evidence at all — a true negative reported as a tool failure.
   Deleted in Phase 1F.
2. **`routes_visible` flagged the Science-Aware route's own emphasis glow as an
   invisible route**, failing the gate on every run for a style that was correct.
   Fixed by making the glow distinguishable, not by lowering the opacity floor.
3. **The hillshade histogram check tested `contrast(1.14) brightness(1.16)` while
   `mc.css` shipped `1.06 / 1.10`** — restated as literals under a comment that
   said "what mc.css says today".

4. **`composite_contrast.py` measured a quantity that could be satisfied without
   the thing it was checking for.** Its first version scored only *relief
   retention* — how much high-frequency structure survives in the composite. The
   radar layers scored **2.61 at opacity 0.72, more structure than the bare
   hillshade**, while the landforms underneath were completely hidden: the
   structure being counted was the layer's own speckle. Adding a correlation test
   against the base's high-pass turned three PASSes into FAILs.

5. **`roughness_vs_latitude.py` tested the wrong sign.** Latitude runs −90 at
   the pole to −84.8 at the equatorward edge, so roughness falling equatorward is
   a **negative** correlation. The check asked `corr > 0.6` and would have
   reported "no artifact" for a perfect artifact. It measured −0.498 and printed
   a clean bill of health.

**A test with the wrong sign is worse than no test at all.** No test leaves a
question open; a test with the wrong sign closes it with the wrong answer, and
hands you a green light to cite. The fifth instance would have certified a
perfect interpolation artifact as clean terrain, and the site list would have
shipped with that certification attached.

**The fourth is the only one found BY DESIGN rather than by accident.** It was
caught because the number was implausible on its face — a composite cannot carry
*more* terrain relief than the terrain — and that is what a measurement is for.
The first three were each noticed by a person looking at something else.

**The third is the worst of the four**, and it is worth being precise about why.
The first two *failed* — noisily, uselessly, but visibly. The third *passed*, on
a filter the application does not apply. A gate that validates something other
than what ships does not merely fail to catch a problem; **it certifies the wrong
thing**, and its green light is then evidence for a claim nobody checked. Two of
the first three were found by accident rather than by any process.

The rule now applied, and the reason `hillshade_histogram.py` parses `mc.css`
and `stamp_methods.py` digests artifacts rather than quoting them:

> **A verifier must READ the value the application uses. It must never restate
> it.** A verifier that restates the thing it verifies is not a verifier — it is
> a second copy of the same assumption, and it will agree with itself.

### The third pattern: one transform, written twice

Two instances, both found while drawing the Phase 4 routes on the map for the
first time, and both are the closing rule of the second pattern applied to
something that is not a verifier.

1. **`plan_traverse.py` re-derived the inverse projection and got the longitude
   backwards.** Rather than calling `frame.pixel_to_latlon`, it computed
   `lat` and `lon` inline and used `arctan2(x, -y)` — the `y_away_lam0`
   convention of the LOLA polar product
   (`ingest_lola_polar_dem.py:272`) — against a DFSAR frame whose transform is
   `arctan2(x, y)` (`sar_geometry.py:198`, validated against ISRO's 937,296-node
   geolocation grid to 13.2 mm). **Latitude was unaffected.** Longitude came out
   as `180° − lon`: route 1 started at 97.33971° where the frame puts site 1 at
   82.64773°, and 177 waypoint longitudes across five routes were written wrong.

   Nothing caught it because nothing compared the two files that have to agree.
   Every existing check on this script looks at length, climb, energy,
   connectivity or the detour ratio — quantities the longitude does not enter,
   all of which were correct. The fix is one line plus a gate: the first waypoint
   of a route *is* its site, so it must plot within one planning cell of that
   site's own `lat_deg`/`lon_deg` in `landing_sites.json`. It now measures
   **25.0–55.8 m** against a 150 m tolerance, and says so on every run.

   Re-running the planner changed **177 longitudes and nothing else**: 0
   latitudes, 0 lengths, 0 climbs, 0 energies, 0 cell counts, 0 connectivity
   figures, 0 detour ratios. Verified by walking both JSON documents scalar by
   scalar, which is also the evidence that §10 needed no revision.

2. **`MissionMap.tsx` plotted the Phase 3 sites through the coarse-grid
   transform.** `gridToPixel` maps the backend's 0–100 grid; the searched sites
   are in native raster pixels. Passing `(line 965, sample 5026)` through a
   function that divides by 100 placed site 1 at CRS `(−755, 12867)` on an
   `87 × 256` extent — off the raster by two orders of magnitude, in both axes,
   for all five sites.

   **It was invisible for two reasons, and the second is the interesting one.**
   Leaflet clips an off-view path to `M0 0` rather than erroring, so the markers
   existed in the DOM with plausible attributes. And the console line underneath
   already read *"5/5 outside the measured amplitude ribbon"* — a sentence
   written for the API's hardcoded offsets, which genuinely were outside. **The
   new symptom arrived wearing the old symptom's label**, and a log line that is
   expected to say something is not a check.

   The gate that closes it does not compare the map to a sentence. It compares
   the map to the search's own verdict: `in_amplitude_mask` is a hard criterion
   of Phase 3, so a site carrying it passed is inside the measured ribbon by
   construction, and a map that plots it elsewhere is wrong. Before the fix the
   console read `#1 outside … #5 outside`; after it, `#1 amplitude … #5
   amplitude`, matching all five records.

**Drawing the deliverable then surfaced three more of the FIRST pattern in one
afternoon, all of them prose written before Phase 3 and 4 ran and never revisited.**

- The degraded-state banner read *"landing sites and rover routes need the
  on-demand backend, which is not reachable"* — printed directly over five
  searched sites and a five-route traverse, both from static artifacts. It now
  names what actually needs the backend: the sensitivity studio, the stage panels
  and the PDF.
- Stage 06 asserted *"the five sites are hardcoded grid offsets … asserted and
  then scored, not searched"* and stage 07 *"no traverse is planned"*, beside a
  map drawing both. Both stages now report from the artifact that holds the
  result — `landing_sites.json` and `traverse.json` — and fall back to the
  absence notice only when it is genuinely absent. The corresponding reasons in
  `build_analysis.py` were rewritten to say where the answer is rather than that
  there is not one; **zero numeric or boolean values in `faustini.json` changed**,
  verified scalar by scalar, and the marks stayed 41 MEASURED / 5 DERIVED /
  0 MODELLED / 10 UNAVAILABLE / 0 unmarked.
- And the sharpest one: `if (!mission) return` at the top of the landing-site
  effect meant that **with the backend down, no landing sites were drawn at all**
  — including the five that come from a static file and need no backend. The
  guard was right when written, when the only sites came from the API. It had
  simply stopped tracking what it guards. It now sits on the API branch, which
  really does need `mission`.

The last of those is worth the emphasis: the banner and the code were making the
same claim, the banner's version was corrected first, and for one commit the app
told the truth in a sentence and contradicted it in a render.

**And a sixth instance of the SECOND pattern, in the capture harness itself.**
The stage fit ran inside a `requestAnimationFrame`, which only fires when the
page actually paints. On a background tab or a host that is not compositing the
callback never runs, so the fit silently did not happen — with no error, and no
way to tell that from a fit that ran and chose this view. Measured in one
session: `focusRoute`, called straight from a click handler, fired every time;
`focusSites`, called from an rAF, fired never. The same condition had already
stopped the rover animation, and it stopped the rail's smooth scroll too.

**`capture_traverse.mjs` could not have caught it**, because headless Chrome
paints: the harness saw 5/5 sites while the running app showed 3. A verifier that
runs in a *more permissive environment than the user's* is a verifier that passes
on conditions the user does not have — the same defect as reading a value the
application does not use, one level out. Both are now effects and instant
scrolls: React's own after-commit hook has no such condition, and it runs after
the map's child effects, so the bounds being fitted to are already drawn. The fit
also now logs what it fitted, or why it did not, so a silent no-op cannot happen
again undetected.

**And a seventh: G16's injection passed for a reason that was not its claim.**
The gate asserts that no report is issued on a host without the analysis
artifacts. Its first injection tested the **generator** — hand it an empty bundle
and see whether a PDF comes out. None did, so the gate printed INJECTION CAUGHT
and looked green. But the generator had raised a `KeyError` on a malformed dict:
the branch never reached the claim, and would have gone on printing INJECTION
CAUGHT if the loader had been replaced with one that invented data. **An
injection that fails for the wrong reason tests nothing, and it is the more
dangerous kind of green light, because it looks like one.** The defect G16 exists
to catch is *a loader that tolerates absence*, so the injection now replaces
`report_data._read` with one that returns an invented document instead of
raising — exactly what a `.get(key, default)` would do. This one was caught by
reading the gate's own output rather than its exit code, which is the only reason
it is instance seven and not a footnote in some later phase.

#### The sub-kind: a TYPE that stopped tracking the wire

Every instance above is a description drifting from a computation. This one is a
description drifting from a **protocol**, and it is worse because a type is
supposed to be the check.

`MissionState` declared every field non-optional. The backend has **two** wire
shapes: a full payload, and a `status: "NOT_INGESTED"` document carrying
`selected_crater`, `data_mode`, `gate`, `status` and nothing else — which is what
the deployed instance returns, being reachable and holding none of the gitignored
rasters. So `tsc` **proved** that `mission.target_coordinates.x` was safe, and in
production it was `.x` of undefined: one uncaught throw inside a React effect,
the whole tree unmounted, a blank page with every asset at 200.

> **A type that cannot represent a shape the wire produces is not a check. It is
> a second copy of an assumption, wearing a compiler's authority.**

Two guards were then drafted for one condition — a `missionHasData` flag in the
map beside the boundary check in the fetch layer — and one was deleted. Two names
for one condition is how the defect was born: the badge derived "OFFLINE" from
`error`, the banner derived "not reachable" from `error`, and the panel beside
them derived "reachable but NOT_INGESTED" from the payload. Three sentences, one
boolean, two of them false, all on one screen. There is now one `BackendState`
with three values and one place that words them.

**Instance three of this pattern is one error appearing twice, in our own
geometry and in our reading of someone else's.** The nadir (look) angle was used
where the incidence angle belongs — once in `incidence_mask.py`, which treated
the product's incidence raster as an incidence angle and built a Bragg-domain
criterion on it, and once in reading Putrevu et al. 2023, where `9.6/sin(26°)`
used their printed *nadir* angle to convert a slant-range spacing that is set by
*incidence*. They are logged as ONE instance because they are one confusion:
`sin θ_inc = ((R+h)/R) sin η`, and the two angles differ by 1.3° at 20° and 1.6°
at 26°.

The two consequences were opposite, which is the useful part. In our own
geometry the error produced a headline claim that was false and is withdrawn
(§7.12). In the reading of Putrevu it produced a bound that was *flattering* —
N ≤ 51.89 instead of 54.88, a higher floor, an easier claim — and was described
in the commit as "the safe way", which it was not (§7.10). **An error that makes
your own case easier is the one you are least likely to look for**, and this one
survived a commit message that congratulated it.

**Both of the first two are the same defect as the five in the second pattern,
one step upstream.** There, a *verifier* restated the value it was meant to check. Here a
*producer* and a *consumer* each restated a transform that already existed
elsewhere in the repository — and, as always, the second copy agreed with the
first until it did not. The rule generalises without amendment:

> **One transform, one implementation, called from everywhere.** Where two
> artifacts must describe the same point, make one of them check the other; a
> quantity nothing compares is a quantity nothing is testing.

The second instance also carries its own smaller lesson. The five landing sites
had been on that map, in the wrong place, since Phase 3 shipped. They were never
noticed because **nobody had drawn a route between them** — the traverse existed
only in `traverse.json`. Rendering a deliverable is not only presentation; it is
the first time two computations are made to agree on a screen.


### The fourth pattern: the surface nobody was looking at

Three instances. The third is §5.12 — §5.8, §5.9 and §5.11 quoted measured PSR
areas printed to a terminal, so they mapped to no artifact, and neither the
staleness digest nor the numeric-literal checker could see them. Every figure in
all three was stale by a whole solar model while §5.10 beside them was correct.
The document-scale version of the same shape, and switching the coverage
assertion on found six further uncovered sections immediately.

The second is §5.1b — G7 compared slope, roughness and hazard
only, so a disagreement about permanent shadow between the API and the static
analysis could not fire, and a served path computed its own shadow from a model
§5.3 refutes by 4.4× for as long as that was true. Same shape as the first, one
scale smaller: a quantity with no check rather than a document with none.

The first, and it is the worst defect this project has produced since the
Random Forest's `P(ice) = 0.96`.

**The PDF report was printing five landing sites that do not exist.** Alpha Ridge
(North), Beta Plateau, Gamma Bench, Delta Spur and Epsilon Crest — the exact five
names, in the exact order, of the hardcoded grid offsets in
`module_e_landing.py` that Phase 3 replaced with a search over all 14,943,444
native pixels. Every figure in that table came from the deleted list:

| | in the report | measured |
|---|---|---|
| slope | 6.7 / 8.6 / 10.6 / 10.7 / 12.2° | 0.26 / 0.18 / 0.05 / 0.55 / 0.20° |
| illumination | 0.02 / 0.01 / 0.04 / 0.03 / 0.00 | 0.457 / 0.456 / 0.409 / 0.460 / 0.389 |
| score | 37.1 | 0.9290 |

**The score is not even on the same scale**, which is the tell: two numbers that
disagree can be argued about, but 37.1 against 0.929 is two different
quantities wearing one label. And one of those five rows was marked
**RECOMMENDED**, in a formal report, for a site the search never chose.

Three more, in the same document:

1. **It contradicted the app.** 18.06 km and 3,137.5 Wh as headline rover
   figures, while the screen's ROVER cell read NO DATA — not computable. Phase 4
   plans routes of 1,641–7,280 m and reports energy **per kilogram** precisely so
   that no rover mass is invented; the report invented 30 kg.
2. **It contradicted itself, two pages apart.** §2: *"Explainable ML Likelihood:
   Random Forest model … provides continuous probability distributions."* §5
   item 2: *"the Random Forest ice-likelihood classifier was WITHDRAWN."*
3. **It made a false reproducibility claim**: *"every figure above is computed
   from the Chandrayaan-2 DFSAR product named on page 1, and re-running the
   pipeline on that product reproduces them."* The sites and the rover figures
   were hardcoded, so re-running reproduced none of them. **That sentence had
   already been deleted from `pdf_generator.py` once, and had come back in new
   wording** — which is the first pattern, in the file that had most recently
   been cleaned of it.

And **all of Phase 8 was absent**: no confidence interval on the candidate area,
which `assert_detection_area_has_interval` exists to require; no measured ENL; no
significance floor; no PSR area; no coverage figures.

**Why nothing caught it.** `assert_paths_agree.py` compares `mission_service`
against `faustini.json` on **slope, roughness and hazard** — the three quantities
that diverged the last time — and on nothing else.
`assert_detection_area_has_interval` guards the analysis JSON, which is not what
the report reads. So the PDF was generated from the legacy payload and **no gate
had ever looked at it**. It is not that a check was wrong; it is that a whole
surface had none, and it was the surface that leaves the browser.

> **A PDF is read without the badge.** Every other surface in this project
> carries its provenance beside it and a reader can hover a figure to find out
> where it came from. On paper they cannot, which makes the report the place
> where a stale number does the most damage — and it was the last output with
> no gate on it.

**The fix is structural and is Phase 1's, applied to the surface Phase 1 missed.**
The report is now a *rendering* of the four artifacts the mission screen reads —
`<crater>.json`, `landing_sites.json`, `traverse.json`,
`detection_statistics.json` — and computes nothing. `report_data.py` reads them
and re-derives not a rounding, not a unit conversion, not a sum. Every table
carries a provenance column, and no site is marked RECOMMENDED, because the
ranking is a score order over one frame and the cold-trap target is modelled.

**And the gate, because this was the third time two surfaces disagreed.**
`assert_pdf_agrees_with_analysis.py` renders the report, extracts the text from
the **rendered bytes** — not from the generator's inputs, which would be checking
one assumption against itself — and fails the build on any numeric literal that
is not in the artifacts at the precision printed. Two presentational transforms
are allowed and named (a fraction shown as a percentage; magnitude, because the
extractor reads unsigned literals); no sums, no ratios, no unit conversions. It
also fails on six phrases by name, because *"Random Forest … provides continuous
probability distributions"* contains no numbers.

Injection-tested: `--inject` adds one fabricated site carrying the deleted list's
own figures, and the gate names all six that are not in any artifact — slope
6.70, illumination 0.020, cold-trap distance 11.44, score 37.1000, and both
coordinates.

The PDF text extractor it depends on had **two defects of its own**, both found
by disbelieving a clean result. It reported a full two-page report as empty,
because ReportLab writes `/Filter [/ASCII85Decode /FlateDecode]` and a plain
`zlib` attempt fails silently. Then, once ASCII85 was added, it "successfully"
extracted 3,156 bytes of undecoded noise, because ASCII85 output is printable
letters and a 3 kB block of it contains the byte pairs `BT` and `TJ` by chance —
a plausibility test that passes on garbage. Chains are now tried most-decoded
first, and the stream regex is anchored because `stream\r?\n` also matches the
tail of `endstream`.

### The three backend states apply to the report too — G16

The screen names three backend states apart (§0, third pattern — three
sentences, one boolean): *unreachable*,
*reachable but holding no rasters*, and *ok*. The report is the one artefact that
leaves the browser, and the same rule binds it:

| state | what the report does |
|---|---|
| unreachable | nothing answers; there is no report to speak of |
| reachable, `NOT_INGESTED` | **no PDF is issued.** `load_report_bundle` raises `ReportArtifactsMissing`, `api_router.py` turns that into **409** |
| reachable, `OK` | a PDF, which **names on its own front page the host state it was issued under**, and what a host without the rasters returns instead |

A thinner report rendered from whatever happened to be present would be the
`np.zeros_like` mistake in document form: a plausible artefact standing where a
measurement belongs, read on paper without the badge that would have warned a
reader. So absence refuses rather than degrades. **G16 —
`assert_pdf_refuses_without_rasters.py`** asserts all three legs: the loader
raises with the analysis directory absent, the router maps that to 409, and an
issued report states its own host state.

**THAT PARAGRAPH USED TO SAY THE PDF WAS "VERIFIABLE LOCALLY ONLY". IT WAS
FALSE, AND THE DEPLOYED SITE WAS DISPROVING IT AT THE TIME.**

The claim was that the deployed backend answers `NOT_INGESTED`, therefore
`/report/pdf/faustini` returns 409 in production, therefore there is no PDF to
check. Every step after the first was wrong. `GET /api/report/pdf/faustini` on
the deployed host returns **HTTP 200 and a 12,356-byte report**, containing the
measured `0.0000 km²`, the `1,460.68 km²` radar area and the NO DATA marks — the
genuine document.

**The precondition is the ARTIFACTS, not the rasters.** The moment the report was
restructured into a *rendering* of `<crater>.json`, `landing_sites.json`,
`traverse.json` and `detection_statistics.json`, it stopped needing the rasters —
and those four files are committed, so they are in every checkout, including
Render's. The rasters are needed to *regenerate* the artifacts, never to render
them.

The false premise was inherited from `/api/mission/{crater}`, which genuinely does
recompute, genuinely does need the rasters, and genuinely does answer
`NOT_INGESTED`. Two endpoints, two capabilities, one assumption — and it
propagated into the UI control, the report's own front page, this section and PRD
statement 10 before anything checked it against the endpoint.

> **It hid a working feature rather than inventing a missing one, which is why it
> survived.** Every other instance in §0 was caught because a number looked too
> good; this one made the project look *worse* than it was, and nothing in the
> discipline is tuned to notice modesty. The check that found it was `curl`.

The report control now reads `/api/report/status/{crater}` — a route that calls
the loader and discards the bundle — instead of deriving its state from the
mission endpoint. The document's own "Issued state" paragraph says what it is
rendered from and that the rasters are not a precondition. G16 asserts all three
of those strings, and G18 asserts the two endpoints are never again collapsed.

The gate's own injection was **wrong on its first pass and passed anyway** — it
injected at the generator, which raised a `KeyError` on a malformed dict, so the
gate reported INJECTION CAUGHT for a reason unrelated to its claim. That is
logged in §0 as the seventh instance of the SECOND pattern, *the verification
apparatus itself being wrong*. The injection now replaces
`report_data._read` with one that invents a document instead of raising —
a loader that tolerates absence, which is the defect G16 exists to catch.


---

## 1 · The polarimetric ice screen, and why it is empty by construction

**This is the most important result in the project so far, and it is a negative
one.** It is also the answer to "you didn't find any ice", so it is worth stating
precisely.

### 1.1 What this build actually computes

`backend/scripts/process_real_sar_pipeline.py:405-431` calibrates the two
amplitude channels to σ⁰, applies a 5×5 boxcar multi-look, and forms:

```
σ_sc = ½(√lh − √lv)²                 σ_oc = ½(√lh + √lv)²
CPR  = σ_sc / σ_oc                   DOP  = |lh − lv| / (lh + lv)
```

where `lh`, `lv` are the smoothed σ⁰ of the two channels. Both quantities are
built from **the same two numbers**.

### 1.2 The identity

Write `r = lh/lv` and `x = ln r`. Then

```
CPR = ((√lh − √lv)/(√lh + √lv))²  =  ((√r − 1)/(√r + 1))²  =  tanh²(x/4)
DOP = |lh − lv|/(lh + lv)         =  |(r − 1)/(r + 1)|     =  |tanh(x/2)|
```

Both are monotone functions of the **same single variable** `|x|`. They are not
two observables; they are two reparameterisations of one channel ratio. Eliminate
`x`:

```
CPR = tanh²( artanh(DOP) / 2 )
```

CPR is a **strictly increasing** function of DOP. The two quantities carry
**one degree of freedom between them**, not two.

### 1.3 The consequence for the screen

The screening rule is `CPR > cpr_th` **AND** `DOP < dop_th` — one condition
pushing `|x|` up, the other pushing it down, along the same axis. The DOP
condition therefore imposes a hard ceiling on achievable CPR:

```
DOP < 0.13  ⟹  |x| < 2·artanh(0.13) = 0.2614797
            ⟹  CPR < tanh²(0.2614797/4) = 0.0042611
```

**No pixel satisfying `DOP < 0.13` can exhibit `CPR > 0.0042611` — whatever the
terrain, whatever the instrument, whatever the threshold.** The configured
`CPR_THRESHOLD = 1.00` is **235×** that ceiling, so the screen is *logically
empty*, not merely unsatisfied. `CANDIDATE AREA 0.00 km²` is the only
arithmetically possible answer.

### 1.4 Numerical verification

Run on all 2,337,086 measured pixels of the Faustini frame
(`backend/scripts/build_analysis.py`, emitted as `cpr_dop_identity` and asserted
by `emit_provenance.py`):

| Check | Result |
|---|---|
| `CPR` predicted from `DOP` alone, max\|residual\| | **1.241 × 10⁻⁶** (float32 storage precision) |
| rms residual | 8.025 × 10⁻⁹ |
| Pearson r between predicted and stored CPR | **0.999999999994** |
| Ceiling implied by `DOP < 0.13` | CPR < **0.004261082862785302** (algebraic) |
| Highest CPR observed among pixels with `DOP < 0.13` | **0.004261057358235121** (measured) |
| Agreement between them | **2.5504550181000563e-08** absolute, **5.985462147133474e-06** relative |

**It is not "hit exactly", and saying so was both false and weaker than the
truth.** These are two independent computations — one a closed form in
`tanh`/`artanh`, the other a max over 2,166,825 measured pixels — and they
converge to six parts in a million. Exactness would be the *expected* result of
one number having been copied from the other. Six-significant-figure agreement
between a derivation and a measurement is the claim worth making, and §1.9
re-derives it from the sweep artifact independently of this table.

The Phase 1 sensitivity sweep brackets the ceiling without having been designed
to. Its grid was built from the measured percentiles, and the transition falls
exactly where the algebra says it must:

| CPR threshold | vs ceiling 0.0042611 | predicted | observed |
|---|---|---|---|
| 0.003546 (measured p90) | below | > 0 | **63,481 px** ✓ |
| 0.009258 (measured p99) | above | 0 | **0 px** ✓ |

One more check at the extreme. The frame's maximum CPR is 0.053411, implying
`|x| = 4·artanh(√0.053411) = 0.941439`, so that pixel's DOP must be
`tanh(0.941439/2) = 0.438780`. Its **measured** DOP is **0.438779**.

That pixel is 3.4× *above* the DOP gate. **The brightest "CPR anomaly" in the
swath is necessarily the least depolarised pixel in it.** This also settles the
old `anomaly_classification` defect twice over: pairing the frame's maximum CPR
with its minimum DOP did not merely describe two different pixels — it described
two pixels that *cannot be the same pixel by construction*.

### 1.5 What this does and does not mean

It does **not** mean there is no ice at the lunar south pole, and it is **not**
evidence against ice. It means this measurement cannot address the question, and
it says so in closed form rather than as a caveat.

The defect is not that the amplitude proxy is *small*. It is that it **collapses
two independent physical observables onto one degree of freedom**, which is why
their conjunction is empty. With the true Stokes vector,

```
CPR = (S0 − S3)/(S0 + S3)          DOP = √(S1² + S2² + S3²)/S0
```

are built from **different combinations** of the four Stokes parameters and are
**distinct observables** — two degrees of freedom where the amplitude pair has
one. *Corrected 2026-09-16:* this read "genuinely independent", and they are
not. `DOP ≥ |S₃|/S₀` couples them: `DOP ≥ |1 − CPR|/(1 + CPR)`, so `DOP < 0.13`
admits only `0.7699 < CPR < 1.2989` (§1.11). Distinct is the load-bearing word
and it survives — `high CPR AND low DOP` selects a real physical population
rather than an empty set — but the conjunction is narrower than two free
conditions would be, and §7.9.4 measures what that costs the test's power. Recovering `S3` requires the phase term `2·Im⟨E_H·E_V*⟩`, which
exists only in the complex `sli` products — 2 × 2.17 GB, on disk, not yet
ingested. That is Phase 5b, and this is the reason it is the fix.

### 1.6 The third argument, and the strongest: a pure propagation result

§1.2's algebra and §7.9.2's Monte Carlo both say something about *the amplitude
proxy*. This one says nothing about it at all, which is why it is the strongest
of the three.

The calibration multiplies both channels by `sin(inc)` **before** the 5 × 5
boxcar. That factor is common to both channels, so in a ratio it ought to cancel —
and it very nearly does. But **a spatially varying weight does not commute with a
boxcar**: `boxcar(a·w)/boxcar(b·w) ≠ boxcar(a)/boxcar(b)` unless `w` is locally
constant or `a ∝ b`. So the residual is not zero, and it can be measured by
re-running the screening with the factor removed:

| | with `sin(inc)` | without | difference |
|---|---|---|---|
| peak CPR | 0.053411 | 0.053852 | |
| **max ΔCPR over the frame** | | | **1.310 × 10⁻²** |
| **max ΔDOP over the frame** | | | **1.393 × 10⁻¹** |
| pixels passing `CPR > 1.00 AND DOP < 0.13` | **0** | **0** | |

**The DOP figure is the result.** The DOP decision threshold is **0.13**, and the
largest excursion the calibration field alone induces is **0.1393 — 1.07× the
entire threshold.** A pixel's DOP can be moved across the whole width of the
criterion by a field that is not part of the physics being tested, and in this
product that field is one whose meaning is unknown (§12).

**Why this is the strongest of the three arguments.** §1.2 assumes CPR is built
from amplitude; §7.9.2 assumes a scattering model to simulate against. **This
assumes neither.** It is arithmetic on the pipeline as written: a weight, a
boxcar, a ratio. It would hold for a Stokes-derived CPR, for a different
threshold, and for any instrument whose calibration varies across the scene and
is applied before spatial averaging.

**Both figures are MAXIMA over 2,337,086 measured pixels, not typical values**,
and **0 pixels pass the screen either way** — the candidate area does not move
and the headline is untouched. What moves is what may be concluded from a
*single pixel's* DOP: on this product, less than the threshold's own width.

### 1.7 The assertion that keeps this honest

`emit_provenance.py` gate 6 fails the build if `candidate_area_km2` is non-zero
while the CPR source is amplitude-only and `CPR_THRESHOLD` exceeds the ceiling.
A non-zero area there is arithmetically impossible, so it can only be a broken
mask, a swapped threshold, or a silently changed CPR source — **never a
discovery**. The distinction is automatic rather than dependent on somebody
remembering the algebra.

### 1.8 Do not retune the threshold

Lowering `CPR_THRESHOLD` below 0.0042611 would make the screen return area
again. That area would be "pixels whose two channels differ by a little", which
is not a CBOE signature and is not evidence of ice. PRD §2 rule 4 stands: if a
threshold is mis-set, print the distribution and say so. The distribution is
printed above.

### 1.9 How far the threshold has to fall — the sweep, precomputed

Stage 09's four sliders re-queried `/api/mission/{crater}`, which re-runs the
pipeline and therefore needs the 9 GB of gitignored products. No deployed host
has them, so on the live site the sliders did nothing — beside two sweep tables,
on the same stage, that worked, because they were already read from the committed
analysis. `emit_sweep_grid.py` now measures the joint screen offline at every
threshold pair and writes `analysis/sweep_grid.json`; the sliders index into it
and stage 09 needs no host at all.

**The axis range is set from the measured field, and that is the whole point.**
A CPR axis spanning the published criterion — CPR ∈ [0.6, 1.6], as the sliders
used to — is a column of zeros at every position, because nothing in this swath
comes near it. A control whose output never moves is a vacuous criterion behind a
control surface: it reads as a broken widget, and it is what the
non-discriminating gate exists to catch. So the axis is built to span where the
count actually changes, and the published value is carried **on** the axis and
marked, so the degenerate point is shown rather than cropped away.

**The result, as a single number:**

| quantity | value | mark |
|---|---|---|
| peak CPR anywhere in the swath | 0.0534108989 | `MEASURED` |
| max CPR among pixels satisfying DOP < 0.13 — **the crossing** | **0.0042610574** | `MEASURED` |
| algebraic ceiling `tanh²(artanh(0.13)/2)` (§1.2, independent) | 0.0042610829 | `DERIVED` |
| agreement between them | 2.550e-08 absolute, **5.985e-06 relative** | — |
| **factor the published threshold must fall before one pixel passes** | **234.68×** | `MEASURED` |

The candidate count is non-zero for a threshold `t` exactly when `t` is below the
crossing, so that one number answers the question completely. And the measured
crossing lands on the algebraic ceiling to six parts in a million — a field
measurement and a closed-form identity, computed by different code from different
inputs, agreeing to six significant figures.

> **The emptiness is confirmed, not merely asserted.** §1.2 derives that
> `DOP < 0.13` caps an amplitude-formed CPR at 0.0042611; this measures the cap
> in the data and finds it exactly there. The screen is empty by construction,
> and the construction is now checked against the product rather than only
> argued from algebra.

The grid is 26 × 19 = 494 cells, 383 of them non-zero, varying on **both** axes —
so the sliders move, and what they show is measured at every position. Volume is
deliberately **not** in the artifact: it is area × assumed depth × assumed pore
fraction, both untested, so it stays `DERIVED` and is computed where it is
displayed, beside its own mark. Putting it in the file would have let a derived
number inherit the file's measured provenance by proximity.

**G17** asserts four things, each injection-tested: the grid agrees with
`faustini.json` at the published operating point; the axes are built from the
field's own extrema and still carry the published values; the grid is not
constant **on either axis** — a grid varying with CPR alone would pass a naive
check with a dead DOP slider; and the stated factor is arithmetically the
published threshold over the crossing, with the counts dying exactly there. The
`configaxis` injection — re-centring the axis on the published threshold, the
defect this gate exists for — trips two of the four independently.

### 1.10 The degeneracy replicates on an independent acquisition

§1.2's identity is **algebra**, so it cannot depend on which acquisition it is
evaluated on. That makes a second product a real check on whether these files are
being read correctly at all — and a **positive result**, not an absence.

The 2020-03-05 pass is independent of ours in every respect that could matter: a
different date, orbit and hemispheric track, a look angle of 26.007650° against
19.997919°, a PRF of 3107.597454 Hz against 3321.641156, a pulse bandwidth of
2.0 MHz against 7.5 MHz, 39 declared azimuth looks against 21, and a 90 m output
grid against 25 m.

| | 2020-08-08 (screened) | 2020-03-05 (independent) |
|---|---:|---:|
| valid pixels | 2,337,086 | 86,357 |
| max \|CPR − tanh²(artanh(DOP)/2)\| | 7.54e-14 | **4.32e-14** |
| max CPR where DOP < 0.13 | 0.0042610239 | **0.0042607148** |
| closed form tanh²(artanh(0.13)/2) | 0.0042610829 | 0.0042610829 |
| relative agreement | 1.38e-05 | **8.64e-05** |
| pixels passing CPR > 1.00 **and** DOP < 0.13 | **0** | **0** |

The identity holds to a float-precision residual on both, the measured crossing
sits on the closed form to better than one part in ten thousand, and **the joint
screen is empty on both products**. The emptiness §1 derives is not a property of
our scene.

> **If this ever fails to replicate, the finding is that we are reading the file
> wrong, not that the algebra varies.** `G20 — assert_degeneracy_replicates.py`
> exists so that conclusion is forced rather than merely available: it asserts
> the independent product's crossing matches the closed form to better than 1e-3
> relative (three orders looser than either product achieves), that CPR predicted
> from DOP matches stored CPR to float precision, and that no pixel passes on
> either product. Injection-tested three ways — perturbing the crossing,
> shuffling one channel to break the pairing without changing its marginal
> distribution, and forcing a passing pixel.

---

### 1.11 The Stokes vector from the single-look complex

Everything above is proved from the delivered amplitude rasters — about the
product, using the product. The single-look complex from the same pass retains
the H–V cross-product, so `backend/scripts/stokes_from_slc.py` forms the
21-look coherency matrix ⟨|E_H|²⟩, ⟨|E_V|²⟩, ⟨E_H E_V*⟩ over the whole swath,
applies the same 5 × 5 boxcar to all three elements, and computes the genuine
Stokes quantities and the amplitude proxy **from the same samples**
(`docs/stokes_from_slc.json`; 5 883 594 matched cells).

**The sign of S₃ is the one convention the product admits, and it is fixed.**
CPR = (S₀ − S₃)/(S₀ + S₃) with S₃ = ±2 Im⟨E_H E_V*⟩; the two readings are
reciprocals (medians 4.7273 and 0.2115, product 1.0000). CPR is defined so
that single-bounce reflection, which reverses handedness, gives CPR < 1; the
reading with median 0.2115 is physical, and the artifact records that
reasoning. Rotations other than 0°/180° mistake S₂ for S₃ and are kept only
as non-admissible diagnostics. The inter-channel phase clusters at −88.33°
with resultant 0.9463 — 1.67° from the quadrature single bounce requires. If
the scene-mean phase IS that quadrature, the instrumental offset is 1.67° and
its effect on |S₃| is cos 1.67° = 0.99957, 0.043 %; but a relative-phase
rotation δ also moves S₂ at first order (S₃ → S₃ cos δ ± S₂ sin δ), and scene
and instrument phase are confounded without a calibration target. It is a
consistency check on the scene mean under the single-bounce assumption, not a
bound on the calibration. (Corrected 2026-09-23, third review M12: the earlier
text said the data bound the phase error. `phase_gain_perturbation.json`
measures the screen under ±1–5° rotations and ±0.5–1 dB gain errors.)

**Eq. (1)'s band holds exactly.** With c = ((√l_H − √l_V)/(√l_H + √l_V))² —
which is CPR_a itself — the Stokes CPR lies in [c, 1/c] on every cell, at both
signs: violation fraction 0.000000, maximum excursion 0. (An earlier run tested
the coupling band built from DOP_a instead, reported 80 % violations and
explained the wrong formula's failure as algebra; that report was withdrawn.)

**Rotation-invariant results.** Cross-channel coherence
|⟨E_H E_V*⟩|/√(l_H l_V): median 0.6580, IQR [0.4639, 0.7861]; over the 20
lowest-CV non-overlapping 15 × 15 windows (the criterion of §7.10 on the SLC
grid) median 0.1738, range [0.0925, 0.6366]. The published DOP < 0.13
condition, evaluated on the Stokes vector, admits 88 421 of 5 883 594 cells =
1.5028 % (binomial SE 0.0050 pp); per window median 11.33 %, range
[0.00, 31.56] %. Of the 13.5605 % of cells with DOP_a ≥ 0.13, 100.0000 % also
have Stokes DOP ≥ 0.13. Of the 88 421 cells with Stokes DOP < 0.13, 0.000000
lie outside (0.7699, 1.2989): the coupling identity holds on data.

**The measured joint rate, physical sign.** P(CPR > 1 | DOP < 0.13) =
29.9273 ± 0.1540 % over 88 421 cells; P(CPR > 1 AND DOP < 0.13) =
0.4498 ± 0.0028 % of all cells (26 462). These are rates on this terrain,
where the DOP < 0.13 cells already have CPR inside (0.77, 1.30) by the coupling
identity; they are not the simulated noise exceedance rate at a 0.7 background
(§7.9.4).

**Circular ENLs and the within-window tail.** At the physical sign N_SC =
12.69 ± 0.15, N_OC = 18.15 ± 0.17 (moment, 16 × 16 patches), |corr(SC, OC)| =
0.4991 frame-wide. The tail test of the sampling model is made *within*
homogeneous windows, where terrain cannot enter: the empirical Stokes-CPR
quantiles about each window's median against F(2N_SC, 2N_OC) at the window's
own ENLs. Over the 109 64 × 64 blocks below the 10th CV percentile (N_SC
median 14.78, near the operating point) the p95 ratio is 0.859 (range
[0.679, 1.091]) and the p99 ratio 0.805 ([0.535, 1.139]) with per-block
|corr(SC, OC)| median 0.500: the measured tail is **narrower** than F by
14 % at the 95th and 19 % at the 99th percentile (the two are stated
separately since 2026-09-16; "14–20 %" rounded 19.48 up), which is what
channel correlation does and is the reviewer's 4.5 answered on data. The 20 15 × 15 windows selected by lowest CV have within-window
ENLs near 100 (the selection favours flat smoothed fields) and ratios of 1.018
/ 0.978 — consistent with F at their own ENL, but not a test at the operating
look count. The whole-frame quantiles of the first run were a test of terrain,
not speckle, and are withdrawn.

**Against the delivered rasters (partial).** The grids differ (slant-range vs
selenoreferenced), so the comparison is distributional, at matched ENL, with
the delivered DN read as amplitude: LH/LV amplitude-ratio quantiles [5, 25, 50,
75, 95] % are [0.7925, 0.9407, 1.0425, 1.1547, 1.3711] raw (ENL ≈ 5.8),
[0.9345, 0.996, 1.0411, 1.0895, 1.1679] after √(boxcar₅(DN²)) (ENL ≈ 13.7),
against [0.887, 0.965, 1.0194, 1.0779, 1.1776] for the SLC's 21-look +
boxcar₅ field. A per-cell slope and r² need a geocoding step whose own error
would dominate the residual, and are not claimed.

**Third review (2026-09-23): coherence by gate, two-channel models, held-out
tails, phase and gain.** Four additions, all at the physical sign, all in
`stokes_from_slc.json` unless named.

*The gate forces the circular coherence down (M7).* The circular-channel
FIELD coherence γ_c = √(S₁² + S₂²)/√(S₀² − S₃²), per cell from the same
boxcar'd coherency matrix as the DOP, has median 0.0724 (IQR 0.0487–0.0951,
max 0.1300) on the 88 421 cells with sample DOP < 0.13 and 0.1324 (IQR
0.0851–0.1879) on the rest; the H–V coherence is 0.0781 inside and 0.6623
outside. The identity DOP² = q² + γ_c²(1 − q²) holds to 5.6 × 10⁻¹⁶ on every
cell, and no gated cell has γ_c ≥ 0.13 — a check on the code path, since the
identity is exact. The frame-wide 0.50 is the circular-channel INTENSITY
correlation (`corr_sc_oc`), a different quantity: γ_c² under Gaussian speckle,
larger with shared texture. (`coherence_by_gate`)

*Which tail model the blocks follow (M10).* For each 64 × 64 block and 15 × 15
window, the empirical p95 and p99 of CPR over its median are set against
three models: equal-look F at the smaller circular count, unequal-look
F(2N_SC, 2N_OC), and Lee et al. (1994) correlated equal-look at N_min with the
block's pooled γ_c (median 0.0995 in the blocks, 0.0672 in the windows). In
104 of the 109 blocks the ordering is empirical ≤ unequal ≤ equal-low-N at
both percentiles, and the unequal model is closest in 107 (p95) and 109 (p99);
median empirical/model ratios 0.859 / 0.789 / 0.789 at p95 and 0.805 / 0.704 /
0.704 at p99 (unequal / equal-low-N / Lee). At the blocks' small γ_c the Lee
model is indistinguishable from equal-look F, so correlation of the FIELDS
does not explain the narrowing; the unequal counts and shared texture (the
intensity correlation 0.50) are what remain. In the 20 windows the ordering
is mixed (9 / 5 / 6 at p95) and the empirical tail sits within 2–5 % of every
model. (`t3e.180_deg.two_channel_models`)

*Held-out tail calibration (M11).* Each block's median CPR and N_SC, N_OC were
estimated on the same cells whose tail they normalize (`same_cells_in_sample`).
Estimated instead on one half of the block and tested on the other (two folds,
pooled), the rejection frequencies at nominal 1 / 5 / 10 % are 0.10 / 1.39 /
4.42 % (medians over 109 blocks); the pooled PIT is hump-shaped (0.046 and
0.055 in the outer deciles, 0.134 at the centre): the model's tails are too
wide for these blocks, which is the direction that makes Section V's rates
upper bounds. Adjacent held-out cells are correlated through the boxcar.
(`t3e.180_deg.tail_calibration`)

*S₂ and the screen under phase and gain errors (M12).* |S₂|/|S₃| has median
0.084 (p95 0.70) over the frame and 0.81 (p95 10.3) inside the DOP gate;
|S₂|/S₀ is 0.051 (p95 0.171) and 0.039 (p95 0.099). A relative-phase rotation
leaves the DOP < 0.13 fraction unchanged (DOP depends on |⟨E_H E_V*⟩| only)
and moves the joint fraction by at most 0.0019 pp at ±5°. A relative-gain
error does not: −1 / −0.5 / +0.5 / +1 dB move the DOP < 0.13 fraction from
1.5028 % to 0.571 / 1.030 / 1.742 / 1.593 % and the joint fraction from 0.4498 %
to 0.162 / 0.304 / 0.530 / 0.489 %. The screen frequencies are therefore
sensitive to the per-channel gain at the half-decibel level and insensitive
to phase. (`docs/phase_gain_perturbation.json`)

*The coherence predicts the windows' CPR.* Each window's (1 − ρ)/(1 + ρ), ρ
its median H–V coherence, against its median CPR: Spearman 0.979 over 20
windows, medians 0.704 predicted and 0.718 observed.
(`t3e.180_deg.coherence_predicts_cpr`)

What this does to the paper: Section V remains a sensitivity calculation and
is labelled so; the measured coherence, the 1.50 %, the exact band, the sign
and the measured joint rate are measured facts for Section III-E.

## 2 · Georeferencing

The frame is south polar stereographic on a sphere of radius 1,737,400 m
(the product's own `A_AXIS_RADIUS`), read from the GeoTIFF GeoKeys of
`ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_lh_d18.tif`.

```
lat/lon → x,y :  ρ = 2·R·k₀·tan(π/4 + φ/2),  x = ρ·sin(λ),  y = ρ·cos(λ)
x,y → lat/lon :  ρ = √(x² + y²),  φ = 2·atan(ρ/2Rk₀) − π/2,  λ = atan2(x, y)
```

`PixelIsArea`, so the tiepoint names the **corner** of pixel (0,0) and a
half-pixel offset is applied for centres.

| | |
|---|---|
| Validated against | ISRO's own 937,296-node geolocation grid shipped with the product |
| Sample residual (rms) | 0.2846 px |
| Line residual (rms) | 0.4550 px |
| Corner residual | **13.2 mm** |
| Peak scale distortion over the frame | 0.2036 % |

`backend/app/ingestion/sar_geometry.py` is the implementation;
`frontend/src/mission/MissionMap.tsx` carries a direct port of the inverse, so
the cursor readout and the backend agree by construction. This replaced a flat
`30.37 km/°` approximation that was wrong by ~25× in longitude at −87.7° and
~570× at −89.9°.

---

## 3 · Elevation

LOLA **`LDEM_80S_20M`** V2.0 (`LRO-L-LOLA-4-GDR-V1.0`), **20 m native posts**,
low-passed with a measured anti-alias sigma and carried onto this frame's 25 m
grid. `build_analysis.py` reads that figure from
`data/pradan/lola/ldem_frame_25m.provenance.json` rather than holding a literal
(`NATIVE_POST_M`, line 178), so this section and the pipeline cannot drift apart.

> **THIS SECTION SAID 80 m UNTIL NOW, AND IT WAS DESCRIBING A PRODUCT THAT HAD
> BEEN REPLACED.** Phase 8 ingested the 1.85 GB 20 m product and §8.2 measured
> what it bought; §3 was never updated and went on naming the 80 m source and
> calling the terrain "80 m-post quantities". The document then contradicted
> itself — §3 said 80, §8 said 20 — and a reader checking the resolution would
> have got a different answer depending on which section they opened.

**TWO LOLA PRODUCTS ARE IN USE AND THEY ARE NOT INTERCHANGEABLE.** Conflating
them is what produced the error above, so they are tabulated rather than
described:

| use | product | native | carried onto | provenance file |
|---|---|---|---|---|
| **frame DEM** — slope, roughness, hazard, the 25 m grid | `LDEM_80S_20M` | **20 m** | 25 m | `ldem_frame_25m.provenance.json` |
| **horizon, illumination, PSR** (§5) | `LDEM_80S_80M` | **80 m** | 240 m, block mean, decimation 3 | `horizon_240m.provenance.json` |

The horizon runs on the 80 m product because it sweeps 360 azimuths across the
full 2533 × 2533 polar array and the 20 m array is 30400 × 30400; the frame DEM
runs on the 20 m product because it covers one frame. Both figures are correct
for their own product, and neither may be quoted for the other.

- The PDS label is parsed as plain text and **units are parsed out of the angle
  brackets**: `MAP_SCALE = 80 <m/pix>` versus `0.080 <KM/PIXEL>` is a 1000× trap
  that produces entirely plausible floats. The parser raises when the unit is
  absent rather than assuming metres.
- `SCALING_FACTOR = 0.5`, `OFFSET = 1737400.0`, `SAMPLE_TYPE = LSB_INTEGER`,
  `SAMPLE_BITS = 16`. Height = DN × 0.5; radius = height + OFFSET.
- Read via `np.memmap`, never `imread` — the 20 m product is 1.85 GB and the
  80 m product 116 MB.
- `assert_dem_is_lola()` re-measures, on **every** run, that the file the
  pipeline reads is bit-identical to the LOLA crop, at tolerance **0.0 m**. It is
  a hard failure, not a warning, because the file is still named
  `dem_native_synthetic.tif` for historical reasons and that name must never
  quietly become true again.

**Resolution honesty.** Slope, roughness and hazard are **20 m-post** quantities
carried on a 25 m grid, and every terrain value emitted names its own source post
spacing in its note — the number a reader needs in order to judge them is the
post spacing, not the grid. **The grid is the binding constraint, not the
source**: §8.2 measures that moving from the 80 m to the 20 m source shifted the
whole distribution by about 2.4 % — p50 +2.4 % against p90 +2.1 %, the same shift
throughout rather than detail appearing in the tails — because a 25 m grid cannot
carry relief finer than 25 m however fine the posts beneath it are. The 1.85 GB
bought provenance, not resolution, and §8.2 says so at length.

---

## 4 · Masks, and what "measured" means

| Mask | Source | Pixels | Area | Fraction |
|---|---|---:|---:|---:|
| Frame | the full raster | 14,943,444 | 9,339.65 km² | 100 % |
| ISRO pointed swath | the product's own `sri_ma` | 5,324,544 | 3,327.84 km² | 35.63 % |
| Amplitude returned | `valid_native.tif` | 2,337,086 | 1,460.68 km² | 15.64 % |

Amplitude / pointed = **43.89 %**. The remaining 56.11 % of the pointed swath
returned literal integer zero: the beam was aimed there and nothing came back.

**Every `MEASURED` radar statistic in this project is taken over the amplitude
mask only.** The request path used to average over the whole frame — 84 %
never-observed padding — which moved the CPR mean by 5.5× and destroyed the DOP
median outright. Nothing is resampled and nothing is averaged across the void.

---

## 5 · Illumination, and permanent shadow

### 5.1 What replaced what

Two invented brightness proxies, which disagreed with each other:

```
render_layers.py    hillshade(alt 30°) × elev_norm^1.2
build_analysis.py   hillshade(alt 1.5°) × elev_norm^1.3     < 0.05  →  "PSR"
```

Neither contains a horizon term, so neither is solar geometry. The second put
77.18 % of the frame in "shadow", which is a statement about the expression and
not about the Moon. The map and the statistics were computed from *different*
formulas for the same quantity, and nothing in the build could notice.

The old "doubly shadowed" mask was that proxy's shadow intersected with the
lowest elevation quintile of the DEM. An elevation percentile is not a shadowing
event.

Both are deleted. Illumination is now a horizon computation, and the layer and
the statistics are the same array.

#### 5.1a One PSR source — the third application of Phase 1's fix

`pradan_pipeline.py` computed `psr_mask = (illumination < 0.05)` from a hillshade
at a capped **1.5°** solar altitude, and `mission_service` served it. §5.3
measures that model wrong by up to **4.4×** — solar elevation at latitude φ
reaches `1.54° + (90° − |φ|)`, which is 6.71° at this frame's outer edge — and
§5.1 had already deleted both brightness proxies from every other path. **This
one survived because it sat behind an API nobody was reading.**

**It is deleted, not adapted.** `simulate_grazing_illumination` and
`sun_altitude_deg` are gone; `process_real_dem` no longer returns `illumination`,
`psr_mask` or `doubly_shadowed` at all. An adapter would have been a second
implementation of a transform that already exists, which is §0's third pattern
and is exactly how the PDF and the screen came to disagree. `mission_service`
now calls `load_horizon(...).to_frame(...)` — the same product, through the same
call, that `build_analysis.py` reads for the verdict and the report renders — or
raises `HorizonPSRUnavailable` with its reason. **Absence refuses; it does not
degrade**, the same rule G16 applies to the report.

`sun_altitude_deg` is **not** recorded in `docs/assumptions.md`. With no consumer
it is not an assumption, and declaring it would assert the capped-elevation model
this section spends §5.3 refuting.

**The projection was wrong before it was right, and the wrong version answered.**
`to_frame(frame, shape)` builds `rows = arange(lines)` and feeds them to
`frame.pixel_to_xy`, so `shape` is **frame pixel indices**, not an output grid.
Passing the API's 100 × 100 display grid sampled a 100 × 100-pixel *corner* of a
2258 × 6618 frame — about 2.5 km of it — and reported **8704.56 km²** of shadow
against the analysis artifact's 2043.22, with a mean illumination of exactly
0.0. The refusal path was correct and the projection was not, which is the more
dangerous half to get wrong because it returns a number. The horizon is now
projected at the frame's native shape and reduced there — a pixel count times the
frame's own cell area, `build_analysis.py`'s arithmetic line for line — and the
masks are downsampled **nearest-neighbour, for display only**. Every number comes
from the native reduction, so nothing served is a statistic of a resampled mask.

| | API path | static analysis |
|---|---:|---:|
| PSR pixels | **3269150** | **3269150** |
| PSR area | 2043.22 km² | 2043.219 km² |

Both are roundings of one native reduction of one product. G7 gates the **pixel
count at tolerance 0**, because two areas are two roundings but two counts are
the same integer or they are not the same measurement.

#### 5.1b The gate that could not have caught it — §0's fourth pattern, smaller

`assert_paths_agree.py` (G7) compared **slope, roughness and hazard only**. For as
long as the served path computed its own shadow, a disagreement about PSR between
the two paths **could not fire**. Nothing was wrong with the three checks it ran;
there was simply no check on the fourth quantity.

> **This is §0's fourth pattern — a surface with no check on it — one scale
> smaller than the PDF was.** There the uncovered surface was a whole document;
> here it is one quantity inside a gate that was otherwise working. The failure
> shape is identical: *it is not that a check was wrong; it is that a whole
> surface had none*, and a green light from the covered part reads as a green
> light for the whole.

G7 now compares PSR area and PSR pixel count at tolerance 0, and — because a gate
that checks three of six named quantities certifies the three it happens to know
about — it **enumerates every quantity both paths produce** and fails if any is
neither compared nor excluded with a stated reason. Injection-tested both ways:
`--inject shadow` adds one pixel to one path's count, `--inject coverage` removes
a quantity from both lists.

### 5.2 The quantity

For a point `p` and azimuth `az`, the horizon is the elevation angle of the
highest terrain along that ray:

```
horizon(p, az) = max over r > 0 of  atan( (h(p + r·u_az) − h(p)) / r )
```

`p` is lit for a sun at `(az, el)` when `el > horizon(p, az)`. A permanently
shadowed region is a point for which that is false for every sun state.

**Not a running maximum.** The obvious implementation — sweep along the ray
keeping a running max of `(h − h₀)/r` — is wrong, because `r` differs for every
pair: a low ridge nearby can subtend a larger angle than a high one far away, so
the maximising point is not the highest point. `app/ingestion/horizon.py`
implements the O(n) skyline scan (Dozier, Bruno & Downey 1981; Dozier & Frew
1990), vectorised across rows so the per-row Python loop disappears.

| Check | Result |
|---|---|
| Fast scan vs O(n²) brute force, 12 profiles across white / smooth / spiky / monotone terrain | **max diff 1.7 × 10⁻⁶** |
| Crest index reproduces its own reported slope | 4.7 × 10⁻⁷ |
| Backward-scan crest indices lie behind their column | true |

### 5.3 The correction that matters — solar elevation is not capped at 1.54°

**This is a correction to the specification, not a bug fix, and it changes the
headline number by a factor of 2.4.**

The natural-sounding model is: *at the lunar south pole the Sun stays within
±1.54° of the horizon, so sample the solar elevation over [0°, 1.54°]*. That is
true only **at** the pole. 1.54° is the Moon's obliquity to the ecliptic, which
bounds the **subsolar latitude** — not the elevation seen from a site.

```
sin(el) = sin(φ)·sin(δ) + cos(φ)·cos(δ)·cos(H)
```

At φ = −90° the first term is all that survives and the bound really is 1.54°.
Away from the pole `cos(φ)` grows and the second term dominates, giving a
maximum elevation of **1.54° + (90° − |φ|)**:

| latitude | naive cap | true maximum solar elevation |
|---|---|---|
| −90.000° | 1.54° | **1.54°** |
| −89.000° | 1.54° | 2.54° |
| −88.000° | 1.54° | 3.54° |
| −85.000° | 1.54° | 6.54° |
| **−84.833408°** (this frame's outer edge) | 1.54° | **6.7066°** |
| −80.000° | 1.54° | 11.54° |

The DFSAR frame spans −89.263057° to −84.833408°, so the naive model
under-illuminates it by between 1.6× and 4.4×.

**Measured consequence.** The full sweep was run both ways over the same array.
**Both figures below are over the full 608 × 608 km LOLA array — 369,567 km² —
which is a diagnostic domain, not this project's scene.** See §5.8 for why that
distinction is load-bearing.

| sun model | PSR ∩ full array | of 369,567 km² |
|---|---:|---:|
| naive, `el ∈ [0°, 1.54°]` for every pixel | 65,398 km² | 17.70 % |
| **per-pixel, `sin(el) = sin φ sin δ + cos φ cos δ cos H`** | **26,900 km²** | **7.28 %** |

The naive figure is 2.40× the corrected one. It would have been this phase's
headline number, and nothing about it would have looked wrong.

**Azimuth.** Near the pole the solar azimuth measured from north is `−H` to
within a fraction of a degree — the exact form
`A = atan2(−sin H cos δ, cos φ sin δ − sin φ cos δ cos H)` differs from `−H` by
0.05° at −88° and 0.14° at −84.8°, both well inside the 1° azimuth sampling.
That approximation is what allows the sun model to ride along inside the
per-azimuth horizon sweep instead of requiring a per-pixel horizon lookup table
of 360 planes (9.2 GB).

### 5.4 The lit fraction is integrated, not sampled

For each azimuth the fraction of the subsolar band in which the Sun clears the
pixel's horizon is computed **in closed form** rather than by sampling `n`
discrete subsolar latitudes. `sin(el)` is very nearly linear in `δ` across the
±1.54° band — its curvature is bounded by `|cos φ|·δ_max²/2 ≤ 8.7 × 10⁻⁵` — so
`sin(el)` is evaluated *exactly* at both band endpoints and the crossing is
interpolated between them.

| Check | Result |
|---|---|
| Closed form vs 20,001-sample brute force, 25 (cos H, horizon) combinations × 5,000 latitudes | **max error 0.00059** — 0.06 % of the band |

This is both faster (it removed ~7 s from every one of 180 rotations) and more
correct: discrete sampling quantises every pixel's illumination fraction to
multiples of `1/n` and puts a sampling artefact into the headline number.

### 5.5 Computed on the full array, then cropped

At the pole the horizon is set by crater rims tens of kilometres outside the
165 × 56 km frame, so the sweep runs over the whole 7600 × 7600 LOLA polar array
and the frame is cropped out afterwards. A horizon computed only inside the
frame would invent sunlight that real terrain blocks.

The square's corners reach 430 km from the pole — beyond the −80° circle the
product nominally covers — and were checked rather than assumed: 0.01 % zeros,
min −7,274 m, max +5,071 m, 245 distinct values in a sample block. They hold real
terrain, so the rotation uses `reshape=True` and keeps them.

Azimuth `a` and `a + 180°` are the same line scanned in opposite senses, so 360
azimuths cost 180 rotations.

### 5.6 Resolution, and how it is labelled

The horizon runs on the 80 m LOLA product decimated 3× by **block mean** to
240 m. Block mean rather than stride-sampling (which would drop narrow rim
crests entirely and un-shadow a crater floor) or block max (which would
manufacture occlusion). The mean slightly lowers sharp crests, which biases
marginally toward calling a pixel **lit** — the conservative direction for a
shadow map, so a PSR reported here is not an artefact of the smoothing.

The 20 m LOLA product is deliberately **not** used: it is 30400 × 30400 = 924 M
pixels, 3.7 GB as float32, and rotating that 180 times is neither feasible nor
necessary, because a horizon is set by distant rim crests and is a coarse
quantity. It is for terrain rendering in Phase 6.

Every consumer receives `native_metres_per_pixel`, the decimation factor and the
effective spacing alongside the arrays, and
`horizon_frame.assert_resolution_declared()` fails a caller that publishes
illumination without them. **A 240 m shadow mask resampled onto the 25 m grid is
still a 240 m shadow mask.**

`psr_mask` is *re-derived* on the frame grid by the same `fraction == 0` rule,
never interpolated — bilinear interpolation of a boolean would invent
half-shadowed pixels.

### 5.7 The polar → frame mapping, checked end to end

`app/ingestion/horizon_frame.py` is the single place the two grids meet. Its
mapping was verified by using it to sample **elevation** — the one quantity that
exists on both grids and was produced by a different code path — and comparing
against `ldem_frame_25m.tif`, which `ingest_lola_polar_dem.py` produced
independently and which was validated separately against ISRO's geolocation grid.

| | rms | bias | Pearson r |
|---|---:|---:|---:|
| Mapping as implemented | **2.93 m** | **−0.00 m** | **0.999997870** |
| Control: same mapping shifted one decimated pixel (240 m) | 36.34 m | — | 0.999673870 |

A 240 m block mean cannot reproduce a 25 m crop exactly; the point is that there
is no *offset*. The control shows a half-pixel error would be caught.

### 5.8 Every PSR area, with the denominator it belongs to

**An area without its domain is as defective as a number without its provenance
mark.** The horizon runs over the whole polar array; the DFSAR frame is 3.9 % of
it. Quoting the full-array total as "the PSR area" would state a figure 2.54×
larger than the entire scene.

`backend/scripts/psr_domains.py` computes all four and writes
`docs/psr_domains.json`; only the last may reach `faustini.json`:

| domain | PSR | of domain | % | status |
|---|---:|---:|---:|---|
| full 608 × 608 km array | 23,704.4 km² | 369,566.7 km² | 6.41 % | **diagnostic only** |
| inscribed 80°S circle | 22,810.9 km² | 290,345.3 km² | 7.86 % | the product's nominal coverage |
| poleward of 87.5°S | 4,730.6 km² | 18,057.4 km² | 26.20 % | Mazarico comparison band |
| **DFSAR frame** | **2,043.2 km²** | **9,339.7 km²** | **21.88 %** | **the only value in the UI** |

*Every figure in this table moved when the finite solar disc shipped (§5.9), and
none of them moved in this document until now, because this section quoted a
terminal and appeared in no stamp entry. See §5.12.*

### 5.9 Sanity anchor — Mazarico et al. (2011)

Mazarico et al. (2011, LPI *Lunar Volatiles* abstract 6007) report **3,660 km²**
of PSR poleward of 87.5°S at 240 m/px, and note explicitly that their figure is
*larger* than earlier work (2,751 km² for the same band).

| | area poleward of 87.5°S | % of the 18,060 km² band |
|---|---:|---:|
| Mazarico et al. 2011, 240 m/px | 3,660 km² | 20.3 % |
| **this project, 240 m/px** | **4,730.6 km²** | **26.2 %** |
| ratio | **1.2925×** | |

**We report 29 % more shadow than the published figure, and the direction is
worth stating rather than explaining away.**

> **This said 50 % until the finite disc's effect was propagated here, and it was
> understating our own agreement.** The 1.50× was the point-Sun ratio; the disc
> that §5.10 validates reduced our 87.5°S band from 5,474.9 km² to 4,730.6 km²,
> and the ratio with it. §0 names understating your own work as the same defect
> as overstating it — the direction of a drift is not what makes it a drift —
> and this one had the added property of making the project look more at odds
> with the published literature than it is.

Three candidate causes were listed,
in the order I thought they mattered. **The first has since been closed by
acting on it**, and the entry is kept rather than deleted so the prediction and
its outcome stay side by side:

1. **~~A point Sun.~~ CLOSED — the finite disc shipped, and this is no longer a
   candidate cause.** It was the leading one, and it was acted on rather than
   left as an explanation. `compute_horizon.py` now models the solar disc at an
   angular radius of **0.25°**, lighting a pixel when *any part of the disc*
   clears the horizon — the condition Mazarico et al. themselves use, which is
   why the sign was predictable. The shipped
   `horizon_240m.provenance.json` records `solar_model.primary = "finite disc"`
   and the A/B it was chosen from:

   | solar radius | PSR pixels | PSR km² (full array) | mean illumination |
   |---|---:|---:|---:|
   | 0.00° (point) | 464,333 | 26,745.58 | 0.2614 |
   | **0.25° (shipped)** | **411,535** | **23,704.42** | **0.2721** |

   A finite disc removed **11.4 %** of the point-Sun shadow, in the predicted
   direction. The figures in the table above are the point-Sun run and are left
   standing as the *before* side of that A/B; §5.10 carries the shipped result.
2. **Uniform band weighting.** The subsolar latitude is sampled uniformly over
   ±1.54°, whereas the real ephemeris does not distribute uniformly. `psr_mask`
   is *never lit under any state*, so it is insensitive to weighting — but it is
   sensitive to whether the extreme states are reachable at all.
3. **An exact-zero definition.** PSR here is `illumination_fraction == 0` with no
   tolerance. A definition with any threshold above zero returns less area.

Decimation is **not** a candidate: block mean lowers crests and raises floors,
both of which reduce shadow, so it biases the other way.

The decisive comparison is not this one but §5.10 — against the LOLA team's own
published PSR raster, on the same grid, pixel for pixel.

### 5.10 External validation — against the LOLA team's own published PSR

Everything above §5.10 is an internal consistency argument: the algorithm matches
its own brute force, the projection has no offset, the closed form matches
sampling. **None of that says the shadows are right.**

The LOLA team publishes its own permanently-shadowed masks and average-visibility
rasters — same instrument, same PDS node, same PDS3 `.IMG` + `.LBL` format, same
south polar stereographic projection on the same 1737.4 km sphere. So this is not
an argument. It is a measurement against the instrument team's own product, pixel
for pixel, with no reprojection.

| product | m/px | role |
|---|---:|---|
| `LPSR_75S_120M_201608` | 120 | binary permanent-shadow mask |
| `AVGVISIB_75S_120M_201608` | 120 | average solar visibility — checks the *continuous* field, not just the mask |

Fetched from **PDS Geosciences** (`pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/
lrolol_1xxx/extras/illumination/img/`); `imbrium.mit.edu` was unreachable
throughout this session, including the path that served the DEM. Identical
products, same 2016 release.

**The mask is resampled nearest-neighbour, never bilinear.** An interpolated
boolean invents half-shadowed pixels and would quietly improve the very agreement
it is meant to test. `AVGVISIB` is continuous and is resampled bilinearly.

#### The prediction, stated before looking

**The prediction below was written against the POINT-SUN model, and is kept
verbatim because that is what a pre-registration is for.** The finite disc
(§5.9) shipped afterwards, and the run reported here is the finite-disc one — so
the prediction is being scored against a *later, better* model than the one it
was written for. That direction is stated rather than quietly benefited from: a
finite disc removes shadow, so it moves the result toward the low end of the
predicted band, and the band would have been narrower had it been written after.

> Ours is 80 m posts decimated to 240 m; theirs is 120 m and epoch-specific.
> Finer topography resolves more small shadows, and this model treats the Sun as
> a **point** when its angular radius is ~0.25° — large next to a ±1.54° band at
> grazing incidence. Both bias toward more shadow. **Predicted: we over-call PSR
> by roughly 1.2–1.6×, with high recall and lower precision.**
>
> *(That band is the point-Sun band; it is superseded, and scored below as NOT A
> HIT rather than void.)*

#### The result

Confusion matrix over the frame (14,943,444 px), read from
`docs/psr_validation.json`:

| | LPSR shadow | LPSR lit |
|---|---:|---:|
| **ours shadow** | 2,522,138 | 747,012 |
| **ours lit** | 262,124 | 11,412,170 |

| | |
|---|---:|
| our PSR ∩ frame | 2043.21875 km² |
| their PSR ∩ frame | 1740.16375 km² |
| **ratio** | **1.174153** |
| Jaccard (IoU) | **0.714229** |
| Dice | 0.833295 |
| precision | 0.771497 |
| recall | 0.905855 |
| overall agreement | 0.932470 |

Against `AVGVISIB`, on the continuous field:

| | |
|---|---:|
| Pearson r | **0.911915** |
| rms difference | 0.074238 |
| least-squares fit | ours = 0.821453 × theirs − 0.013873 |

Recall 0.906 against precision 0.771: we find nearly all of their shadow and add
some of our own. The regression slope of 0.821 says the same thing from the other
side — we report systematically *less* illumination than they do. The direction
and the shape are both as predicted.

#### Scoring the prediction — three facts, not one

These are separable and were previously collapsed into a single verdict, which is
how a true claim and a missed one came to share a sentence.

**1. The MECHANISM prediction (§5.9) HELD, with the correct sign.** A point Sun
over-predicts shadow; a finite disc will reduce it. Measured: the disc removed
**11.4 %** of the point-Sun shadow (464,333 → 411,535 px). This was the
substantive physical claim and it is a clean hit.

**2. The NUMERIC BAND (1.2–1.6×) was written for the point-Sun model, and is
scored here against the finite-disc model.** Against the model it was *written
for* it measured **1.301×** — comfortably inside. Against the model that
*shipped* it measures **1.174×** — just outside the 1.2 floor. The band did not
move; the model underneath it did.

**3. It is recorded as NOT A HIT. That is the conservative reading, and the
alternative is stated rather than suppressed.** A band written for a model that
has since been superseded is arguably **VOID** rather than missed: it makes a
claim about a computation this project no longer performs, and scoring it against
a different computation is not the test it was registered as. Both readings are
defensible. **The conservative one is the one recorded**, because a project whose
entire argument is that it does not grade itself generously does not get to
invoke a technicality the one time a prediction goes against it.

> **THE TALLY, IN ONE SENTENCE, USED EVERYWHERE:** *Two pre-registrations were
> scored — the eight-row solar-disc A/B held **8 of 8**, and the earlier
> **1.2–1.6×** band for the LPSR area ratio is recorded as **NOT A HIT** at
> 1.174×, conservatively, since that band was written for the point-Sun model it
> has since superseded (where it measured 1.301× and did fall inside) and is
> arguably void rather than missed.*

**These are two different pre-registrations and conflating them is a defect.**
The 8-of-8 is `validate_psr_vs_lola.py`'s solar-disc A/B: eight *directional*
predictions about how each metric would move when the disc replaced the point
Sun, committed before the sweep ran, with the point-Sun values as baselines. All
eight moved as predicted, including its own numeric ratio prediction (`~1.16`,
measured 1.174, tolerance ±0.06). The 1.2–1.6× band is the *earlier* prediction
about how our PSR would compare to LPSR at all. `docs/viva.md` previously ran the
two together in one sentence, so a reader took the 8-of-8 as the score for the
band. **The 8 of 8 is true and stays; it just does not mean what that sentence
implied.**

`verify_all.py` (G10) fails the build if the band is quoted anywhere without the
qualifier that it was written for the superseded model — the same protection the
29.16 % upper bound carries, for the same reason: a figure whose meaning depends
on a condition is a different claim once the condition is dropped.

**93.2 % of pixels agree.** The disagreement is one-sided and its sign was
predicted from the physics before the comparison was run.

### 5.11 The doubly-shadowed term — computed, and its approximation stated

A doubly-shadowed core is terrain that is **never directly lit** *and* **receives
no scattered light from lit terrain**. Pass 1 gives the first half. Pass 2
(`compute_horizon.py --doubly`, a second full sweep) approximates the second:

> For each azimuth, find the crest that forms this point's horizon, and ask
> whether **that crest** is itself permanently shadowed. A point is doubly
> shadowed when this holds in **every** azimuth.

The crest mask is rotated with `order=0` (nearest) — a PSR flag is boolean and
interpolating it would invent half-shadowed crests.

**Both domains, each with its own denominator** — because this section quoted a
frame area beside a fraction computed over the full array, which is exactly the
defect §5.8 exists to prevent:

| domain | doubly shadowed | as a fraction of THAT domain's PSR |
|---|---:|---:|
| full 608 × 608 km array, 240 m | 1.8432 km² (32 px) | 7.7758e-05 = 0.0078 % |
| **DFSAR frame, 25 m** | **0.48125 km² (770 px)** | **2.3554e-04 = 0.0236 %** |

*Was 0.94 km² and "0.04 % of our PSR" — the point-Sun frame figures, with a
fraction that in the artifact was relative to the full array rather than the
frame. An area without its domain is as defective as a number without its
provenance mark (§5.8), and this section was quoting one of each.*

**What it captures and what it does not.** It captures the dominant term: a floor
ringed by rims that are themselves in permanent shadow has no nearby sunlit
surface to scatter from. It does **not** test every cell visible below each crest,
and models neither multiple scattering nor thermal re-radiation. So it is marked
`DERIVED`, not `MEASURED`, and a floor it calls doubly shadowed could still
receive some scattered light from lit terrain lying below a dark crest.

It is **not** the discarded proxy. That was the brightness proxy's shadow
intersected with the lowest elevation quintile of the DEM — an elevation
percentile, which is not a shadowing event.

### 5.12 Why nothing caught §5.8 and §5.11 — and the assertion that now does

§5.10 was corrected from `docs/psr_validation.json` when the finite solar disc
shipped. **§5.8, §5.9 and §5.11 were not, and could not have been**, because they
quoted figures printed to a terminal by `psr_domains.py` and appeared in **no
stamp entry**. The staleness stamp watches artifacts; the numeric-literal checker
only reads sections that map to one. Neither could see these sections at all, so
both passed them in silence while every figure in them was stale by a whole solar
model — the frame PSR read 2,264.2 km² beside a §5.10 reporting 2,043.2, and
2264.2 / 1740.2 = 1.3011, the superseded ratio, sitting in the document as a
current fact.

> **This is §0's fourth pattern at document scale — a surface no check covered.**
> Not a check that was wrong: §8's digest check was working correctly and had
> nothing to say, because nothing had told it these sections existed. The green
> light from the covered sections read as a green light for the document.

Two things closed it:

1. **`psr_domains.py` now emits `docs/psr_domains.json`** — the four domains, the
   Mazarico anchor, and the doubly-shadowed term in **both** of its domains, each
   with its own denominator. §5.8, §5.9 and §5.11 map to it.
2. **`stamp_methods.py --check` asserts the coverage rule**: every section
   containing a numeric literal must appear in at least one stamp entry, or be
   listed by name in `SECTIONS_WITHOUT_ARTIFACTS` with a reason. It is the same
   assertion G7 gained for the two computation paths, turned on this document.
   `--inject-unstamped` adds a numbered section with a figure and no mapping.

**It found six more the moment it was switched on** — §1.4, §6.2, §6.3, §6.4,
§8.7 and §9. Three now map to artifacts that already existed and had never been
connected (`faustini.json`, `f2_footprint.json`, `composite_contrast.json`);
three are excluded by name with their reasons. The stamp went from 20 artifacts
to 23.

---

## 6 · The screening thresholds, and whose they are

`CPR_THRESHOLD = 1.00` and `DOP_THRESHOLD = 0.13` are **not** inherited magic
numbers. They are exactly the published criterion in:

> Sinha, R. K. et al. (2026). *npj Space Exploration* **2**:22.
> doi:[10.1038/s44453-026-00038-9](https://doi.org/10.1038/s44453-026-00038-9)

which reports crater **F2** inside Faustini at 87.39°S, 82.31°E, ~1.1 km across,
with peak CPR **1.95** and CPR > 1 over ~47 % of its interior, DOP 0.1–0.13 where
CPR is elevated, and reads the combination as strong evidence for subsurface ice.

The criterion is **disputed**. Saran et al. (2026, Research Square preprint)
report mean CPR 1.01 ± 0.3 and DOP 0.32 ± 0.1 for the same feature and attribute
it to roughness. That is precisely why the thresholds are *cited* rather than
tuned (PRD §2 rule 4).

### 6.1 We cannot replicate their formula, and do not claim to

Both 2026 papers use **full polarimetry** (HH/HV/VH/VV). These products are
**hybrid / compact pol** (`_cp_`, channels LH/LV), for which the correct
formulation is the Stokes one:

```
CPR = (S0 − S3)/(S0 + S3)        DOP = √(S1² + S2² + S3²)/S0
```

already implemented in `module_b_radar.compute_cpr_from_stokes()`. This project
can state which mode it used and why its derivation is the right one for that
mode. It cannot enter the formula dispute, and must not imply it has.

### 6.2 Does the published detection fall inside our data?

Run through `sar_geometry`'s forward projection — the one validated to 13.2 mm —
and not by hand:

| question | answer |
|---|---|
| F2 projected position | E 78,445.7 m, N 10,592.3 m → frame pixel line 1,120.3, sample 3,676.9 |
| Inside the 2258 × 6618 frame? | **YES** |
| Inside ISRO's pointed swath? | **YES — 100 %** of the 1,521-pixel disc |
| Inside the measured amplitude ribbon? | **No — only 17.09 %** of the disc returned amplitude |

**So F2 was targeted, and this product carries almost no usable signal over it.**
That is itself a finding: a published detection sits in a part of the swath where
56 % of the pointed area returned literal zero.

Over the 260 pixels of F2 that *did* return amplitude:

| | mean | median | extreme |
|---|---:|---:|---:|
| CPR (amplitude-only) | 0.001442 | 0.000798 | max **0.015383** |
| DOP | 0.061965 | 0.056468 | min 0.000455 |

### 6.2a The maximum over F2's actual amplitude mask

The paper's F2 figures are expected maxima of *independent* F(2N, 2N) draws
at true CPR 0.7 — over the 1521-pixel disc, or over 24.7 effective samples.
The crater as measured is neither: 260 of the 1521 disc pixels returned
amplitude (17.1 %), and neighbouring CPR pixels are correlated (lag-one 0.884
azimuth, 0.509 range; §7.9.1). `backend/scripts/f2_maximum.py` fits a
correlogram per axis to the measured lag-1 and lag-2 values — Gaussian in
azimuth (ℓ = 3.159 px), exponential in range (ℓ = 1.312 px), both fits and
their residuals recorded — and draws the CPR field over the disc as 0.7 X/Y
with X, Y independent Gamma(N, 1/N) fields sharing that correlation (Gaussian
copula, Cholesky of the 1521 × 1521 matrix), 10 000 trials, seed 7
(`docs/f2_maximum.json`).

| N | correlated, 260 amplitude px: max median / p95 | count > 1.00 per trial | correlated, full disc | independent 25 / 260 / 1521 samples, max median |
|---|---|---|---|---|
| 5 | 4.035 ± 0.018 / 8.085 | 75.8 ± 0.2 | 6.358 / 12.064 | 2.528 / 4.821 / 7.377 |
| 13.72 | 1.911 ± 0.004 / 2.729 | 46.5 ± 0.2 | 2.428 / 3.330 | 1.485 / 2.105 / 2.627 |

The independent 25- and 1521-sample rows reproduce the paper's 2.52 and 7.38
at N = 5. On the mask actually measured, at the operating look count, a
speckle-only field with true CPR 0.7 has a maximum above 1.00 in every trial
and 46 of its 260 pixels above the threshold on average; correlation lowers
the maximum relative to 260 independent samples (1.91 against 2.11) because
the correlated field holds fewer independent draws. The achieved lag-one
correlation of the simulated CPR field is 0.897 (az) and 0.447 (rg) against
the targets 0.884 and 0.509. A second generative model — correlated complex
fields, boxcar'd with the production zero-fill, then divided — is in §14.6; at
true CPR 0.7 it gives a median maximum of 1.754 and puts the excursions into
larger clusters.

### 6.3 It is a different pass, and that is the point

Their detection is almost certainly **not** a different reduction of our data. It
cannot be, because the two use different acquisition modes.

| | this project | Sinha et al. 2026 |
|---|---|---|
| polarimetric mode | **compact / hybrid pol** | **full pol** |
| channels | LH, LV (`num_polarizations = 2`) | HH, HV, VH, VV |
| product | `ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_*` | — |
| beam mode | `STRIPMAP`, look `RIGHT`, band `L` | L **and** S |
| pass | orbit **4265**, 2020-08-08 | not stated in the open text |

The left column is read directly from our own PDS4 label. The right is from the
paper's own description — it reports *"full-polarimetric L- and S-band
observations"* and states it used *"the full-polarimetry data from Chandrayaan-2
DFSAR for the first time"*.

**A radar records one mode per pass.** DFSAR's full-pol and compact-pol are
distinct acquisition configurations, so a single observation cannot be both.
*(That is an inference from the instrument's design, not a quoted statement — the
paper is paywalled and its orbit numbers were not verifiable from the open
text.)* Their F2 detection therefore comes from a **different DFSAR pass over the
same ground**.

Which gives the finding its real shape:

> **Even for a crater with a published detection, a different pass over the same
> ground returned usable signal on only 17.09 % of it — with 100 % of it pointed
> at. Radar coverage is per-pass, not per-crater.**

That is Phase 8's thesis — that L-band polar coverage is thin and unquantified —
confirmed against a specific published claim on a specific 1.1 km crater, rather
than argued in general. It also sharpens why the two 2026 papers can disagree by
a factor of two about the same feature: they are not necessarily looking at the
same returned signal.

### 6.4 Why the CPR numbers still cannot be compared

Their peak CPR of 1.95 is **127× our maximum** — and **this is not a
contradiction**. Our CPR is the amplitude-only ratio, which §1 proves cannot
exceed 0.0042611 wherever DOP < 0.13 and cannot reach 1.95 anywhere by
construction. Different polarimetric mode, different quantity. The comparison
becomes meaningful only after Phase 5b recovers true Stokes CPR — at which point
it becomes a direct test against a specific published claim on a specific 1.1 km
crater, which is a far stronger position than a general improvement.

---

### 6.5 A planned traverse mostly crosses ground the radar never saw

The coverage thesis is usually argued from the frame: 15.64 % of it carries
amplitude, and even F2 — a crater with a published detection — returned usable
signal on 17.09 % of itself while 100 % of it was pointed at. This is the same
fact met from the other direction, and it is the form a mission planner would
actually feel.

Three rover strategies are planned across this frame by Dijkstra over measured
slope, roughness, hazard and illumination. Classifying each of their 33 waypoints
by what the radar did there (`docs/rover_coverage.json`):

| strategy | km | inside the amplitude ribbon | pointed, no return | never observed | **no radar return** |
|---|---|---|---|---|---|
| Shortest | 18.1 | 9 (27.3 %) | 9 (27.3 %) | 15 (45.5 %) | **72.7 %** |
| **Safest** | **34.6** | **3 (9.1 %)** | 11 (33.3 %) | 19 (57.6 %) | **90.9 %** |
| Science-Aware | 18.1 | 9 (27.3 %) | 9 (27.3 %) | 15 (45.5 %) | **72.7 %** |

**The safest route is the worst covered.** That is not a coincidence and it is
the point: safety is scored from LOLA topography, which covers the whole frame,
while radar covers a thin ribbon — so optimising for terrain safety walks the
rover *away* from the only ground with any radar evidence on it. Nine tenths of
the route a lander would actually prefer crosses terrain about which this
instrument says nothing at all.

Two honest qualifications. The destination is a hardcoded grid centre — the
screen found no candidate, so there is nothing to route *to* — which is why the
UI marks the route DEMO TARGET and reports no traverse distance. And "pointed, no
return" and "never observed" are different failures: the first is a radar that
looked and got nothing back, the second is ground outside the swath entirely.
They are counted separately above rather than merged into one comfortable number.

## 7 · The radar product itself — looks, speckle, and what a DN means

Everything in Phase 8 is a function of the look count *N*: a per-pixel
significance test on CPR is built out of speckle statistics, and speckle
statistics are parameterised by *N* and nothing else. So *N* is measured here,
from the label and then from the pixels, before anything is built on it.

Reproduce with `python -u backend/scripts/measure_enl.py`; the numbers below are
written to `docs/enl.json`.

### 7.1 The declared look count

| field (from `..._d_sri_xx_cp_xx_d18.xml`) | value |
|---|---|
| `range_looks` | **1** |
| `azimuth_looks` | **21** |
| **total nominal looks** | **21** |
| `azimuth_look_bandwidth` | 51.016 Hz |
| `total_processed_azimuth_bandwidth` | 1071.336 Hz |
| `range_window` | HAMMING, coefficient 0.7 |
| `azimuth_window` | HAMMING, coefficient 1.0 |

Two internal checks that the field means what it says. First, 21 × 51.016 =
1071.336 Hz, which is the total processed azimuth bandwidth **exactly** — the
looks are non-overlapping sub-bands that tile the aperture, which is the
configuration that can deliver 21 statistically independent looks. Second, the
single-look product from the same pass (`_sli_`) declares `azimuth_looks = 1`
and `range_looks = 1`, and is stored as `ComplexLSB8` I/Q. The field
discriminates between products from the same processor on the same day.

### 7.2 Are the DN amplitude or intensity? — and why the obvious test fails

This propagates into results that already exist. The CPR proxy forms
`0.5*(sqrt(a) ∓ sqrt(b))²`, which is `sigma_sc`/`sigma_oc` only if `a` and `b`
are **intensities**; if they are already amplitudes the derivation carries a
spurious square root and the 0.0042610 ceiling would need recomputing.

The tempting test is the variance ratio: an *N*-look intensity has
`mean²/var = N`, its amplitude has `≈ 4N`, and 21 against 83 look far apart.
**That test cannot settle it, and the reason is worth recording.** For small
coefficient of variation, `mean²/var` of `X^k` is about `1/k²` times that of `X`.
So *every* power of the DN yields a self-consistent story with its own implied
look count, and reading 21 off one of them assumes the answer. Measured:
`mean²/var` is 21.2–24.4 on DN and 5.3–6.5 on DN², which fits "intensity with
21 looks" and "amplitude with 5.3 looks" equally well. The declared 21 cannot
break the tie, because a real product is entitled to under-deliver its nominal
looks — which, as §7.3 shows, this one does.

**The label settles it, against the instrument's own noise floor.** The same
label carries the noise-equivalent sigma-zero, and a scene cannot sit below the
noise floor of the radar that recorded it. With `calibration_constant`
K = 70.3089 dB, incidence 20.00°, and a median LH DN of 542:

| hypothesis | σ⁰ = | median σ⁰ | relative to NESZ |
|---|---|---|---|
| **DN are amplitude** | DN² · sin θ / 10^(K/10) | −20.3 dB | **+11.2 dB** |
| DN are intensity | DN · sin θ / 10^(K/10) | −47.6 dB | **−16.1 dB** |

(NESZ from `nes0_coeff_0`: LH 7.038×10⁻⁴ = −31.5 dB, LV 6.065×10⁻⁴ = −32.2 dB.)

The intensity reading puts the entire scene 16 dB *beneath* the instrument's own
**noise** floor — a value no measured intensity containing the receiver's own
noise can take, and the label declares no noise subtraction or offset. The
amplitude reading puts it 11 dB above the floor, and −20.3 dB is an ordinary
lunar L-band backscatter at this incidence. This is support for the amplitude
reading, not a proof of it: the label declares no unit or radiometric
convention. (Reworded 2026-09-23, third review M4; "impossibility" withdrawn.)
`calibration_example.json` carries the worked example with the exact inputs.

**The 20.00° above is the label's nominal figure, which §12 proves the product
cannot carry — and the verdict does not depend on it.** §12.1 shows
`sin θ = ((R+h)/R)·sin η` forbids an incidence angle at or below the look angle
on a convex body, and §12.3 shows the delivered incidence raster fails three
independent tests. The geometric value implied by the label's own altitude is
**21.2678°** (§12.1). The `sin θ` term moves by:

```
10·log10(sin 20.0000°) = −4.6595 dB
10·log10(sin 21.2678°) = −4.4042 dB
                shift  =  0.2553 dB
```

**0.2553 dB against a 27.3 dB separation between the two hypotheses** — the
amplitude reading sits +11.2 dB above the noise floor and the intensity reading
−16.1 dB below it. The tie is broken by more than two orders of magnitude more
than this angle is worth, so **every incidence angle in the plausible range gives
the same verdict**, and no value of θ rescues the intensity hypothesis. A reader
arriving from §12 asking whether the amplitude finding rests on a discredited
field will find the answer here: it does not.

#### Every consumer of the label incidence, and its sensitivity

`sin θ` enters `process_real_sar_pipeline.py:410-411` as a factor on **both**
channels — `sigma0_lh` and `sigma0_lv` — so it divides out of any ratio built
from them. That splits the consumers cleanly into the two that see it and the
ones that cannot:

| consumer | does θ reach it? | sensitivity |
|---|---|---|
| **§7.2 amplitude vs intensity** (this section) | **yes** — an absolute σ⁰ level against NESZ | 0.2553 dB over 20.0000° → 21.2678°, against a 27.3 dB margin. **Verdict unchanged.** |
| **CPR, DOP, the screen, candidate area** | **no** — a common factor in a ratio | Cancels algebraically. Measured residual (§12.4, `incidence_audit.json`): max ΔCPR **0.013095542788505554**, max ΔDOP **0.1392841339111328**, and **0 pixels pass either way**. |
| **§7.10 Putrevu slant-range spacing** | **yes** | Their printed 26° is a *nadir* angle; the incidence it implies is 27.6198°. Handled at §7.10, and it changed the N cap from 51.89 to 54.88. |
| **§7.12 Bragg-domain criterion** | **yes, decisively** | It was the criterion's entire input. **Withheld**, not recomputed — §7.12. |

The pattern is worth naming: **θ matters exactly where an absolute radiometric
level matters, and nowhere a ratio is formed.** The one place it was decisive is
the one place the criterion has been withdrawn.

**Verdict: the DN are amplitude.** This is also the convention in the DFSAR
instrument paper, whose calibration equation carries `(DN)²`
(Bhiravarasu et al. 2021, *Planet. Sci. J.* **2**, 134, doi 10.3847/PSJ/abfdbf).

**Nothing downstream changes.** `process_real_sar_pipeline.py` already computes
`sigma0 = DN² · sinθ / (K_lin · G²)`, so the arrays the CPR proxy consumes are
intensities, its `sqrt()` correctly recovers a field amplitude, and the
0.0042610 ceiling stands as published. The ambiguity was real and worth
resolving; the answer is that the existing code was right.

### 7.3 The measured ENL, which is not 21

ENL is `mean²/var` on intensity — here on DN², over patches lying entirely
inside the DN mask (entirely, not mostly: one zero-fill pixel would dominate a
patch's variance and manufacture a low outlier). The estimate is the **mode** of
the per-patch distribution rather than its mean, because terrain texture adds
variance and therefore only ever biases ENL *downward*; the population has a
ceiling, not a centre.

| patch | LH | LV |
|---|---|---|
| 16 × 16 (400 m) | **5.30** | **6.46** |
| 32 × 32 (800 m) | 2.64 | 2.40 |
| 64 × 64 (1.6 km) | 1.51 | 1.61 |

Spread at 16 × 16 (LH): p5 0.77, median 4.12, p95 9.14.

**Measured ENL is 5–6 against a nominal 21.** On this evidence alone the honest
statement was a wide bound — texture is inseparable from speckle without a
homogeneous target, so the true value could have been anywhere from about 5 to
21 — and every quantity in a significance test scales with it. §7.4 closes that
bound to a number, using data rather than an argument.

A skewness cross-check was run and **did not discriminate** — measured third
moments (+0.90 on DN, +1.74 on DN²) sit well above every speckle-only
prediction, because bright scatterers dominate the third moment long before they
dominate the second. It is recorded here as attempted and uninformative rather
than quietly dropped.

#### 7.3.1 The estimator, specified by reading the code

`docs/enl_estimator_spec.json` is emitted by `backend/scripts/enl_estimator_spec.py`,
which imports `measure_enl.py` and `bootstrap_enl.py` and reports what they
do — a specification typed from memory drifts from the code; one read from it
cannot. Statistic: mean²/var of DN² per patch. Patches 16 × 16 (headline),
32 × 32, 64 × 64 (400, 800, 1600 m on the 25 m grid); stride equal to the patch,
overlap 0, tiles anchored at the raster origin, partial edge tiles dropped; a
patch is used only if every pixel is inside the mask; variance with ddof = 1.
Mode: 120 equal-width bins of ln(mean²/var) over [min, max], the estimate is
exp of the midpoint of the fullest bin; mean and quantiles are reported beside
it. Masks: the amplitude mask (LH > 0) & (LV > 0), 2 337 086 px, is also the
screening mask (`valid_native.tif`); the ENL-measurement mask is the amplitude
mask eroded by the 5 × 5 boxcar footprint, 2 294 084 px, holding 8 337 wholly
inside 16 × 16 patches. Bootstrap (`docs/bootstrap_enl.json`, ported from the
reference and reproducing it): B = 2000, seed 2026; simple = patches i.i.d.;
block = whole rows of the 16 × 16 patch grid, one row an azimuth band 16 px =
400 m high across the full range extent; percentile interval at 2.5 / 97.5, not
BCa. LH raw 5.8276, block [4.03, 6.19] (simple [4.04, 6.15]); boxcar 13.7166,
block [10.69, 22.52]; LV raw 5.1413, block [4.38, 7.29]; boxcar 19.7677, block
[12.11, 24.76]. Propagated through F(2N, 2N) at each replicate's boxcar ENL: LH
FP at true CPR 0.7 17.80 %, block [11.76, 20.81]; floor 1.895, block
[1.641, 2.070].

#### 7.3.2 The estimator benchmarked at known ENL, and two other estimators on the SLC

`backend/scripts/enl_benchmark.py` (`docs/enl_benchmark.json`) runs the
identical pipeline — `measure_enl.patch_ratios`, `mode_of`,
`bootstrap_enl.block_boot` / `simple_boot`, imported unmodified, no boxcar — on
synthetic fields whose ENL is known: N independent complex circular-Gaussian
looks, each with separable AR(1) correlation chosen so the *intensity* lag-one
correlation equals the product's measured 0.838 (azimuth) and 0.576 (range),
1024 × 512 cells, with and without multiplicative K-distributed texture
(Gamma(ν, 1/ν) per cell), 200 replicates per configuration, B = 2000, seeds
11/12. Bias, RMSE and the coverage of the 95 % block interval, each with its
Monte Carlo SE over the replicates:

| N | ν | bias (± SE) | RMSE | coverage, block 95 % (± SE) | coverage, simple | measured lag-1 az / rg |
|---|---|---|---|---|---|---|
| 4 | ∞ | +0.685 ± 0.019 | 0.738 | 0.120 ± 0.023 | 0.105 | 0.820 / 0.527 |
| 6 | ∞ | +0.940 ± 0.028 | 1.021 | 0.260 ± 0.031 | 0.215 | 0.820 / 0.528 |
| 8 | ∞ | +1.310 ± 0.041 | 1.434 | 0.245 ± 0.030 | 0.265 | 0.820 / 0.528 |
| 12 | ∞ | +1.864 ± 0.058 | 2.037 | 0.245 ± 0.030 | 0.245 | 0.820 / 0.528 |
| 4 | 8 | −1.228 ± 0.009 | 1.235 | 0.000 | 0.000 | 0.483 / 0.310 |
| 6 | 8 | −2.470 ± 0.010 | 2.474 | 0.000 | 0.000 | 0.414 / 0.266 |
| 8 | 8 | −3.910 ± 0.010 | 3.912 | 0.000 | 0.000 | 0.362 / 0.232 |
| 12 | 8 | −7.118 ± 0.012 | 7.120 | 0.000 | 0.000 | 0.290 / 0.186 |
| 4 | 4 | −2.018 ± 0.006 | 2.019 | 0.000 | 0.000 | 0.341 / 0.219 |
| 6 | 4 | −3.635 ± 0.006 | 3.636 | 0.000 | 0.000 | 0.276 / 0.177 |
| 8 | 4 | −5.382 ± 0.007 | 5.382 | 0.000 | 0.000 | 0.232 / 0.148 |
| 12 | 4 | −9.021 ± 0.007 | 9.022 | 0.000 | 0.000 | 0.175 / 0.111 |

Two results, neither flattering, both now on record. **On pure correlated
speckle the mode estimator reads about 16 % high** at every N tested
(+0.685 at 4, +1.864 at 12): correlated cells return a low sample variance.
**The block-bootstrap "95 %" interval covers the true value 12–26 % of the
time**, because the bootstrap resamples an estimate that is biased, and the
simple bootstrap does no better; the intervals quoted in §7.3.1 and in the
manuscript are therefore *precision* statements about the estimator, not
coverage statements about the ENL. Read through the +16 %, the delivered
product's raw 5.83 corresponds to a speckle ENL nearer 5.0 — at the lower end
of the manuscript's indicative range 5.0–5.8, which is not a bound: the two
biases act in opposite directions and neither is bounded (third review M8,
2026-09-23; `enl_interval_validation.json` measures what a validated interval
would cover). With texture on every cell
the mode cannot find a homogeneous population and reads far low; that
configuration also destroys the lag correlation (the measured lag-1 column),
so it is not this product, which keeps its 0.838. The AR(1) field is more
correlated at lag two (0.702) than the product (0.565), which is recorded as a
caveat in the artifact.

On the SLC's spatial arm (21-look coherency, no boxcar, 21 489 wholly-inside
16 × 16 patches, block-bootstrap 95 % intervals over rows of the patch grid),
three estimators, each reported as the mode over patches with the median
beside it:

| estimator | mode | block 95 % | median |
|---|---|---|---|
| moment, LH intensity | 4.643 | [4.62, 5.51] | 3.65 |
| moment, LV intensity | 5.407 | [4.85, 5.68] | 3.67 |
| trace moment, 2 × 2 (Anfinsen et al. 2009) | 6.088 | [5.54, 6.09] | 4.03 |
| log-cumulant, 2 × 2 (var ln det C = ψ′(L) + ψ′(L − 1)) | 4.826 | [4.27, 5.28] | 4.25 |
| log-cumulant, LH (var ln I = ψ′(L)) | 5.336 | [5.18, 5.68] | 4.65 |
| log-cumulant, LV | 5.529 | [5.03, 5.86] | 4.68 |

The moment mode on the full swath (4.64) agrees with the nine-window control's
4.52. The three families disagree by up to 1.4 looks on the same patches — the
trace moment, which uses the cross-channel term, reads highest — which is the
spread a reader should attach to any single "measured ENL".

#### 7.3.3 Patch bias and stationarity

`backend/scripts/patch_bias.py` (block B3 of the reference, ported with its RNG
state replayed so the digits reproduce) draws pure correlated speckle at
N = 6.00 with field AR(1) correlations 0.84 (az) and 0.58 (rg) and runs the
estimator unchanged: mode 7.08 at 8 × 8, **6.61 at 16 × 16, 6.01 at 32 × 32**,
5.95 at 64 × 64; uncorrelated Gamma(6, 1/6) control 6.00 and 6.06 at 16 and 32
(`docs/patch_bias.json`). Lag correlation inflates the small-patch mode.
One qualification the manuscript's sentence does not make: the reference set
the *field* correlation to 0.84/0.58, so the simulated *intensity* lag-one is
0.705/0.339 — below the product's 0.838/0.576 — and the inflation it reports
is a lower bound (§7.3.2 matches the intensity lag-one properly and finds more).
`backend/scripts/stationarity.py` (block D3, no randomness) splits the frame
into azimuth thirds × range halves: four blocks have ≥ 5000 valid pixels and
their 16 × 16 modes are 3.29, 4.02, 7.95 and 7.53 — **3.3 to 8.0** — with
lag-one 0.849–0.952 (az) and 0.754–0.897 (rg) (`docs/stationarity.json`). The
frame-wide ENL is a mode over a heterogeneous population.

### 7.4 The control: forming 21 looks ourselves, from the single-look complex

The single-look complex from the **same pass** is on disk — 355,768 azimuth
lines × 759 slant-range bins of `ComplexLSB8`, which is contiguous `complex64`
at byte 5,725,302. That layout is not assumed: the script asserts
`offset + lines × samples × 8` against the file size and gets an **exact** match,
and refuses to memmap a raster whose geometry is unconfirmed.

So we can build our own 21-look product and measure it with the *identical*
patch estimator. Reproduce with
`python -u backend/scripts/slc_multilook_control.py --windows 9`; results in
`docs/slc_multilook_control.json`.

**Two checks that the reading of the file is right, before any conclusion rests
on it.** First, the azimuth power spectrum gives an occupied bandwidth of
**1071.2 Hz** in 9 windows out of 9, against the label's declared
`total_processed_azimuth_bandwidth` of **1071.336 Hz** — agreement to 0.01 %,
which independently confirms the byte layout, the complex interpretation, the
PRF and which axis is azimuth. Second, the single-look intensity measures
**ENL 1.04** (range 0.93–1.12) against a theoretical **1.00**, so the estimator
is unbiased on data whose answer is known analytically.

**Why 21 looks need not be 21.** Azimuth is sampled at the PRF, 3321.64 Hz, but
only 1071.34 Hz of azimuth bandwidth is processed — a measured oversampling
factor of **3.10**, identical in all 9 windows. Averaging 21 *consecutive*
samples therefore averages 21 samples that are not independent, and can deliver
at most 21 / 3.10 ≈ **6.8** looks. Splitting the processed band into 21
non-overlapping sub-bands and averaging their intensities gives looks that are
independent.

Both were built, from the same complex data, decimated to the same grid, and
measured with the same patches:

| how the 21 looks are formed | measured ENL | reference value for that scheme |
|---|---|---|
| single look (control) | 1.04 | 1.00 |
| **21 by spatial average** | **4.52** | 6.77 = 21 / 3.10 (asymptotic; 7.34 exact) |
| **21 by sub-band split** | **9.95** | 21 |
| *the delivered `sri` product* | *5.30 / 6.46* | *21 (nominal)* |

**The answer is a third outcome, and neither of the two that were anticipated.**
It is not scene texture: the single-look control measures 1.04, so there is no
detectable texture depressing these numbers, and in any case spatial and
sub-band multilooking were measured on the *same grid, same patches, same
terrain*. It is not that the archive is corrupt either.

**And the first reading of the 2× gap was wrong — corrected 2026-09-16.** This
paragraph read *"'21 looks' names a method, and the two methods do not deliver
the same number of looks."* They do. The arms differ in effective azimuth
**resolution** — intensity autocorrelation half-widths of 0.95 and 2.79 output
rows — and the patch estimator responds to that through the within-patch
correlation of §7.5. Smoothed to a common width, the paired difference over the
nine windows is **−1.00 ± 0.57** against **+4.47 ± 0.43** raw: at matched
resolution the two methods agree. §7.4b is the measurement, and the 9.95 is a
resolution effect on the estimator, not a look count. The delivered product's
5–6 still sits with the spatial-average figure and its 6.77–7.34 reference.

**What this section establishes is a fact about the DELIVERED PRODUCT: it
measures 5.3–6.5 effective looks against a nominal 21.** That is the whole
claim here, and it is about `cpr_real.tif`'s input channels as archived.

**It is NOT the look count that applies to the screened field, and this sentence
used to say it was.** It read *"the operative number for everything downstream is
therefore N ≈ 5, not 21"*, which contradicted §7.7 four sections later: the
pipeline applies a 5 × 5 boxcar to σ⁰ *before* forming CPR, so the threshold
touches a smoothed field whose measured ENL is **13.72**, not the raw product's
5.83. Both sentences were in this document at once, and the wrong one came
first — so a reader who stopped at §7.4 left with the superseded number.
**See §7.6 for the smoothing step and §7.7 for the operating point that applies
to every downstream figure.**

*One window of nine (the last, at the very end of the pass) is a clear outlier
at 1.50 / 4.03, and the medians above are taken over all nine regardless.*

**The sub-band arm falls short of its own ceiling, and three hypotheses failed
to explain it.** At 8.8–9.9 against a ceiling of 21, the obvious suspect was
spectral leakage from a hard rectangular band split. It was tested:

| sub-band variant | measured ENL |
|---|---|
| hard rectangular split | 8.76 |
| Hamming taper + 8-bin guard bands | **8.37** |
| powers equalised across looks | 9.39 |
| tapered *and* equalised | 6.96 |
| *ceiling implied by the measured per-look powers* | *12.81* |

**Tapering does not climb — it falls slightly. The leakage diagnosis is
rejected.** Equalising the looks recovers little, so unequal sub-band power is
not the main term either, even though the measured per-look powers cap the
achievable figure at 12.8 rather than 21. The residual gap between about 9 and
21 is **unexplained**, and no attempt is made here to explain it away.

Two things follow, and the second matters more than the first. **We have not
demonstrated that 21 independent looks are achievable on this data**, so no
claim to that effect is made anywhere. And **the conclusion does not depend on
it**: it rests on the spatial arm (4.4–4.5) matching the delivered product
(5.3–6.5) and its independently derived 6.77 ceiling, and on the sub-band arm
being roughly twice the spatial arm on identical grids, identical patches and
identical terrain — a gap that texture cannot produce.

### 7.4a A pre-registered prediction, and its failure

**(a) The prediction, as committed before measurement.** §7.3 derives a ceiling
from the label alone: looks are formed by splitting the processed Doppler
bandwidth, so when the PRF exceeds that bandwidth the looks overlap in frequency
and the achievable ENL is `azimuth_looks / (PRF / processed_azimuth_bandwidth)`.
`predict_enl_ceiling.py` computes it and opens no raster. Committed at
**`4aba4cd`**, before `measure_enl.py` was pointed at the second product:

| product | looks | PRF (Hz) | processed bw (Hz) | oversampling | predicted ceiling |
|---|---:|---:|---:|---:|---:|
| 2020-08-08 (ours) | 21 | 3321.641156 | 1071.335975 | 3.100466 | 6.7732 |
| **2020-03-05** | **39** | **3107.597454** | **1069.708995** | **2.905087** | **13.4247** |

Ours reproduces §7.3's 6.77, so the formula scored here is the document's own.

**(b) The refactor was inert, and that is what makes the result admissible.**
`measure_enl.py` had its input pinned in three module constants. They became
`--dir`, `--stem`, `--label` with those exact values as defaults; **the estimator
did not change** — not the patch geometry, not the mode-versus-mean choice, not
the wholly-inside-mask rule, not the patch sizes. Re-running the original product
through the new argument form reproduced **5.8276** (LH) and **5.1413** (LV), and
**5.2960 / 6.4629** at 16 × 16, to every digit; a strict subset check found **0**
of the committed artifact's leaves changed; and under `--patches 16,32` — what
the committed file was written with — the output was **byte-identical**, with
`git` reporting `docs/enl.json` unmodified. An estimator adjusted per product
measures the adjustment, so it was proven unadjusted before it was used.

**(c) The measurement.** On the 2020-03-05 L-band product the estimator returned
**2.2806** (LH) and **2.2084** (LV) — **0.170** and **0.165** of the predicted
13.4247, against 0.860 and 0.759 for our own product. **Doubling the declared
azimuth looks, from 21 to 39, lowered the measured ENL.**

**(d) The verdict.**

> `azimuth_looks / oversampling` is not sufficient on its own, and the mechanism
> as pre-registered does not generalise across these two configurations.

**(e) What survives: the bound, not the prediction.** Every multilooked
measurement sits below its own ceiling, and the attained fraction does not
cluster:

| product | band | ch | declared looks | ceiling | measured ENL | attained |
|---|---|---|---:|---:|---:|---:|
| 2020-08-08 | L | LH | 21 | 6.7732 | 5.8276 | 0.860 |
| 2020-08-08 | S | LV | 21 | 6.7732 | 6.2721 | 0.926 |
| 2020-08-08 | S | LH | 21 | 6.7732 | 5.2439 | 0.774 |
| 2020-08-08 | L | LV | 21 | 6.7732 | 5.1413 | 0.759 |
| 2020-03-05 | S | LH | 39 | 13.4247 | 3.7204 | 0.277 |
| 2020-03-05 | L | LH | 39 | 13.4247 | 2.2806 | 0.170 |
| 2020-03-05 | L | LV | 39 | 13.4247 | 2.2084 | 0.165 |
| 2020-03-05 | S | LV | 39 | 13.4247 | 1.6250 | 0.121 |

**The bound holds in 8 of 8. The attained fraction spans a factor of 7.65.** A
quantity that bounds a measurement but does not predict where in its range the
measurement falls is a ceiling, not a model, and §8.2 must not be read as
claiming more.

**The single-look control calibrates the estimator; it does not test the bound.**
The `sli` products declare `azimuth_looks = 1` and `range_looks = 1`, so the
ceiling is exactly 1.00 and coincides with the expected value. Measured, on
16 × 16 patches of intensity wholly inside the valid mask: median **0.9854**
(2020-08-08) and **0.9965** (2020-03-05), with per-patch p5–p95 of
**0.4554–1.4110** and **0.4994–1.5228**. The estimator is unbiased at one look.
It is listed here because omitting a control that came out well would be
selection, but a bound equal to the expectation cannot be violated from below and
is therefore not a constraint that could have failed.

**(f) Candidate explanations — UNTESTED.** These are differences between the two
products, not findings, and are recorded so that a later test has something to
address:

- output spacing against input resolution — 90 m output over 74.9 × 49.6 m input
  resolution, against 25 m over 19.99 × 26.73 m
- pulse bandwidth — 2.0 MHz against 7.5 MHz
- lag-1 correlation — 0.689 / 0.729 (azimuth / range) against 0.838 / 0.576

**They are not ranked and none is selected.** Choosing among them now would
construct an explanation after seeing the answer, which is the failure the
pre-registration exists to prevent. §7.4b states what will be tested next and
commits to it in advance.

### 7.4b Mechanism control: the two arms do not have the same azimuth resolution

The reading §7.4 first gave the 2× gap — that the two arms delivered different
numbers of looks — has an alternative the
reviewer (4.9) put plainly: each sub-band look is band-limited to 1/21 of the
processed spectrum, so its impulse response is ~21 × the full-band one, and on
the same decimated grid its cells are correlated over several rows; a patch of
correlated cells returns a smaller sample variance and therefore a larger
mean²/var. `backend/scripts/mechanism_controls.py` imports the control's own
windows, crop and look-forming code and measures, per window
(`docs/mechanism_controls.json`):

* the half-maximum width of the intensity autocorrelation along azimuth, in
  decimated rows: **spatial 0.95, sub-band 2.79** (medians of nine; window 3's
  sub-band profile does not cross 0.5 within ten lags and is recorded as
  undefined); along range 1.62 and 1.72 bins — the arms differ in azimuth
  resolution by about 3 ×, and only there;
* the 2-D normalised autocovariance to lag 10 on both axes for each arm
  (lag-one azimuth 0.316 spatial, 0.635 sub-band);
* the **paired** difference sub-band − spatial over the nine windows:
  +4.473 ± 0.427 (sd 1.280, t = 10.5) — the gap is real;
* the same difference after Gaussian-smoothing the finer (spatial) arm along
  azimuth until its width matches the sub-band arm's in that window (σ found by
  bisection, 0.63–1.03 rows): **−0.996 ± 0.570 over the eight windows where a
  match exists**, the smoothed spatial arm measuring a median 10.99.

At matched azimuth resolution the two arms agree within one look. The 4.52
against 9.95 of §7.4 is therefore a difference of **resolution on the
estimator**, not of look count delivered by the method, and the sentence in the
manuscript that reads it as the latter needs to change. The delivered product's
5–6 still sits with the spatial arm as measured; what the control now shows is
why the sub-band arm reads higher.

### 7.5 Neighbouring pixels are not independent

Correlation of DN with itself at small lags, after removing each patch's mean:

| direction | lag 1 | lag 2 | lag 3 |
|---|---|---|---|
| azimuth (lines) | **+0.838** | +0.565 | +0.363 |
| range (samples) | **+0.576** | +0.476 | +0.396 |

The anisotropy is consistent with its processing cause: azimuth is far more
correlated than range, and the product has 21 azimuth looks against 1 range
look. Incidence geometry and interpolation can also align with the radar axes,
so this is consistency, not attribution (third review C10, 2026-09-23). (These
are an upper bound on the speckle correlation, since sub-patch terrain
structure survives the mean removal.)

### 7.6 The boxcar trap

CPR and DOP are not formed on raw pixels: the pipeline applies a 5 × 5 boxcar to
σ⁰ first. If pixels were independent that would multiply the looks by 25.
Measured, over the DN mask eroded by the boxcar half-width so no window reaches
a zero-fill pixel (2,337,086 → 2,294,084 px):

| channel | ENL raw | ENL after 5 × 5 | gain | if independent | variance understated | SD understated |
|---|---|---|---|---|---|---|
| LH | 5.83 | 13.72 | **2.35×** | 25× | **10.6×** | 3.26× |
| LV | 5.14 | 19.77 | **3.84×** | 25× | **6.5×** | 2.55× |

This generalises beyond this product and is the most transferable result here:
**any study that spatially averages a SAR image and assumes its looks scale with
pixel count is understating its noise by roughly an order of magnitude in
variance.** The correction requires measuring the pixel-to-pixel correlation,
which — as far as this project's literature sweep found — nobody does for lunar
radar, so nobody knows the size of their own error.

### 7.7 What that does to a CPR threshold

CPR is a **ratio** of two N-look intensities, so its sampling distribution is
`CPR · F(2N, 2N)`. Everything below follows from that and is reproducible from
`scipy.stats.f` alone.

| N | rel. SD | bias E[R]/CPR | FP at CPR 0.5 (upper bound) | 0.7 (upper bound) | 0.9 (upper bound) | true CPR for 95 % confidence above 1.0 |
|---|---|---|---|---|---|---|
| 5 | 0.775 | 1.250 | 14.48 % | 29.16 % | 43.55 % | 2.978 |
| 6 | 0.677 | 1.200 | 12.21 % | 27.31 % | 42.91 % | 2.687 |
| 6.77 | 0.623 | 1.173 | 10.75 % | 26.03 % | 42.46 % | 2.525 |
| 9 | 0.519 | 1.125 | 7.55 % | 22.84 % | 41.28 % | 2.217 |
| **13.72** | **0.406** | **1.079** | **3.74 %** | **17.79 %** | **39.23 %** | **1.895** |
| 19.77 | 0.331 | 1.053 | 1.60 % | 13.32 % | 37.10 % | 1.698 |
| 21 | 0.321 | 1.050 | 1.35 % | 12.59 % | 36.72 % | 1.671 |
| 38 | 0.234 | 1.027 | 0.14 % | 6.11 % | 32.36 % | 1.462 |

**THE OPERATING POINT IS N = 13.72, NOT N = 5, AND THIS WAS WRONG UNTIL NOW.**
There is one CPR field and it has one look count. `process_real_sar_pipeline.py`
applies a 5 × 5 boxcar to σ⁰ **before** forming CPR — `cpr = σ_sc/σ_oc` is built
from `lh_smooth` and `lv_smooth`, and `cpr_native.tif` is that field — so the
`CPR > 1.00` threshold touches the **smoothed** field, whose measured ENL is
13.72 (LH) / 19.77 (LV), not the raw product's 5.83 / 5.14. The bold row is the
one that describes this screen. Reading the table at N ≈ 5 quoted the raw
product's look count against a threshold applied to a different field, and every
figure that came from it was too pessimistic:

*Both FP columns below are upper bounds, for the reason in §7.10.*

| | at N = 5 (wrong) | at N = 13.72 (the field) |
|---|---|---|
| bias E[R]/CPR | 1.250 | **1.079** |
| relative SD | 0.775 | **0.406** |
| 95 % floor | 2.978 | **1.895** |
| FP at true CPR 0.7, upper bound | 29.16 % | **17.79 %** |
| FP at true CPR 0.5, upper bound | 14.48 % | **3.74 %** |

Phase 8 was already correct — `detection_statistics.py` has used
`ENL_SCREENING = (13.72, 19.77)` and published the 1.8946 floor since it was
written. It was §7.7's *narrative* that read the table at the wrong row, which is
worse than a wrong computation: the number was right in the artifact and wrong in
the prose that quoted it.

**EVERY NOISE EXCEEDANCE RATE IN THIS TABLE IS AN UPPER BOUND**, and the label is
not decoration. The rates assume the two circular channels are independent;
§7.10 shows from Putrevu et al. 2023's own Byrgius C dispersion that they are
correlated at |ρ|² ≥ 0.31, and correlation between numerator and denominator
narrows a ratio's distribution. `verify_all.py` fails the build if either figure
appears anywhere in this repository without that qualification attached.

The threshold in use is CPR = 1.00. **At the measured N = 13.72, a single pixel
needs a true CPR above 1.895 before it reads over 1.0 with 95 % confidence, and
ordinary rock at a true CPR of 0.7 crosses the threshold up to 17.79 % (upper
bound; assumes independent same- and opposite-sense channels) of the time.** At
the nominal 21 those figures are 1.671 and 12.59 %. The swath's measured maximum
is 0.0534 — short of the floor by a factor of 35.5 — so the conclusion is
unchanged and its margin is smaller than it was being quoted as.

### 7.8 What is and is not novel here

The loose claim "nobody reports uncertainty on lunar CPR" is **false**, and is
not made anywhere in this project. The DFSAR instrument paper reports a
"~38 look average for each sampled location" over Peary crater and "an
approximate 1/N^1/2 … uncertainty in the CPR measurements of ±0.16"
(Bhiravarasu et al. 2021, *Planet. Sci. J.* **2**, 134). Five narrower statements
replace it, each separately defensible:

**(a) The published error bar uses the wrong statistic.** `1/sqrt(N)` is the
relative error of a *single channel*. CPR is a *ratio* of two, whose relative
standard deviation is `sqrt((2N-1) / (N(N-2)))`:

| N | 1/√N | correct ratio SD | ratio |
|---|---|---|---|
| 38 | 0.1622 | 0.2341 | **1.44×** |
| 21 | 0.2182 | 0.3206 | 1.47× |
| 6 | 0.4082 | 0.6770 | 1.66× |

**(b) It is computed from nominal looks.** §7.3–7.4 measure ENL on a DFSAR
product and find it 3–4× below nominal. Combined with (a), a published bar of
±0.16 may understate the true figure by roughly 3×.

*Calibration of this claim.* **ENL falling below nominal looks because of
azimuth oversampling is textbook in terrestrial SAR and is not presented here as
a discovered phenomenon.** What is ours is narrower and survives that: the first
measurement of ENL on a DFSAR product; a controlled experiment on the
single-look complex from the same pass that isolates the mechanism and rules out
texture; and the quantified consequence for a live scientific dispute. The verb
throughout is **measure and quantify**, never *discover*.

**(c) There is an uncorrected positive bias.** `E[R] = CPR · N/(N−1)`, because
the denominator is a random variable and `E[1/Y] > 1/E[Y]`. It pushes every
estimate *toward* the threshold, in the direction that manufactures detections,
and no lunar CPR study found applies the correction. Its size depends on the look
count of the field being thresholded: **+25 % at N = 5**, but **+7.9 % at
N = 13.72**, which is this screen's operating point (§7.7). The +25 % figure is
the one that applies to a *raw-product* CPR; quoted against our own screen it
overstates the bias by a factor of three.

**(d) Three nulls survive the counterexample intact.** Among the 25 records
examined (§13.1), none tests per-pixel significance, none states an interval on
a detected area, and none computes a noise exceedance rate for CPR > 1. Scoped
and dated 2026-09-16: an unscoped "nobody" is a claim about the literature
rather than about a search, and the one exception found — Spudis et al.'s
measured effective look count — is named in §13.1. "Noise exceedance rate"
replaces "false-positive rate" throughout: the quantity is P(R > 1) at a stated
true CPR, and a false-positive rate for *ice* would need a distribution over
ice-free terrain that no study supplies.

**(e) The product's own incidence raster fails three geometric tests.** 80.53 %
of its values sit below the spacecraft look angle, which is impossible on a
convex body; its pixel-to-pixel step is 35–41× the geometric ramp; and it does
not track slope, so it is not a local incidence either. **§12** is the
measurement and **§12.5** states the claim with its four caveats. No published
work reports it — which is a statement about the published record, not about what
ISRO knows.

**What cannot be claimed.** Our measured ENL is a property of *this* compact-pol
`sri` product from *this* pass. It cannot be transferred to Sinha et al.'s
full-polarimetric result — different acquisition mode, different processing
chain, different look configuration — and no statement here does so. The point
is narrower and harder to dismiss: **nobody has measured it for theirs either**,
so the uncertainty on a published lunar CPR detection is presently unknown
rather than small.

### 7.9 Two corrections to how these numbers may be used

Both of these constrain *our own* claims, not the literature's.

#### 7.9.1 A crater does not hold as many independent samples as it holds pixels

Any "the peak over an ice-free crater would reach X" argument is a
multiple-comparisons calculation, and computing it from raw pixel counts assumes
the pixels are independent. §7.5 shows they are not, and the field that is
actually thresholded is a 5 × 5 boxcar of σ⁰ on top of that. So the effective
count is measured, by integrating the two-dimensional autocorrelation of
`cpr_real.tif` itself over patches lying wholly inside the valid mask:

**A = 61.420749918170166 pixels per independent sample**, read from
`docs/cpr_significance.json` (`effective_samples.area_all_lags`) and identical in
`docs/cpr_dispersion.json` (`correlation_correction.correlation_area_px`). F2's
**1,520 pixels of CPR are therefore about 25 independent samples**, not 1,520.

*This read `A = 61.5` while §7.10 used `61.42` for the same quantity from the
same artifact — one number, two roundings, and the coarser one first. Both now
quote the artifact.*

Patches are mean-removed before the ACF, which suppresses the DC terrain level
and biases A slightly *low* — that is, biases the independent count *high*, so
the penalty derived from it errs against our own argument rather than for it.

Median peak over an ice-free F2, true CPR 0.7, as the median of the maximum of
*n* draws of `CPR · F(2N,2N)`:

| N | from 1,520 raw pixels | from 25 effective samples |
|---|---|---|
| 5 | 7.38 | **2.52** |
| 6 | 5.77 | **2.23** |
| 9 | 3.71 | **1.78** |
| 21 | 2.00 | **1.27** |

**The raw-pixel column overstates the penalty by roughly 3×, and quoting it
would be precisely the error this project exists to avoid.** Only the
right-hand column may be used.

#### 7.9.1a Why F(2N,2N) may not be applied to our own values

`R ~ CPR · F(2N, 2N)` holds for a ratio of two independent N-look **intensities**
— which is what published CPR, `σ_SC/σ_OC` from the Stokes vector, is. The
critique in §7.8 is aimed at those values and stands. It is **not** what this
build computes: the amplitude proxy `((√LH − √LV)/(√LH + √LV))²` is a different
functional form with a different sampling distribution, and applying F(2N,2N) to
it would be the same class of error the critique is about. Its distribution is
therefore obtained by Monte Carlo, below — which turned out to say something
considerably stronger than "different distribution".

#### 7.9.2 The quantity this build calls CPR is a channel-imbalance estimator

**This is the deepest result in the project, and it is stronger than the
0.0042610 ceiling recorded in §1.** The ceiling bounded the proxy's *magnitude*
under the DOP gate. This bounds its *information content*, everywhere,
unconditionally.

**The statement.** At equal channel powers, the amplitude proxy's population
value is **exactly zero for every value of CPR**. Not small — zero, identically,
as an algebraic fact about the quantity rather than a property of this scene. It
is a function of LH and LV alone, and the circular polarisation ratio lives in
the **H–V phase**, which taking magnitudes discards before the ratio is ever
formed. What remains responds to one thing only: the imbalance between the two
channels. **It is a channel-imbalance estimator carrying CPR's name.**

##### The experiment

`backend/scripts/cpr_significance.py`. Circular complex Gaussian draws at N
looks. The population CPR is set through the H–V correlation and the population
channel imbalance through the covariance diagonal, **independently**, so the two
can be moved one at a time — which is the whole design. Run at the swath's own
measured coherence, |ρ| = 0.9822 (§7.9.3), N = 5, 120,000 trials per row.

| true CPR | imbalance | Stokes median | Stokes p5 | p95 | **proxy median** | proxy p95 | proxy population |
|---|---|---|---|---|---|---|---|
| 0.30 | 0 dB | **0.300** | 0.233 | 0.387 | **0.00043** | 0.00434 | 0 |
| 0.70 | 0 dB | **0.700** | 0.563 | 0.869 | **0.00043** | 0.00432 | 0 |
| 1.00 | 0 dB | **1.000** | 0.806 | 1.239 | **0.00043** | 0.00438 | 0 |
| 1.50 | 0 dB | **1.500** | 1.203 | 1.866 | **0.00043** | 0.00435 | 0 |
| 0.70 | 1 dB | 0.700 | 0.563 | 0.869 | 0.00331 | 0.01224 | 0.00331 |
| 0.70 | 3 dB | 0.700 | 0.569 | 0.861 | **0.02922** | 0.04967 | 0.02924 |

**Read the last three columns down.** Across a factor of five in true CPR the
proxy's median is *constant to five decimal places*. Hold the CPR fixed and add
3 dB of channel imbalance and it moves by a factor of **68**, landing on its
population value to four decimals. The Stokes estimator, computed from the very
same draws, tracks the truth in every row.

##### Two independent routes to one conclusion

The algebra of §1 — `CPR_amp = tanh²(x/4)`, `DOP_amp = |tanh(x/2)|`, one degree
of freedom, ceiling 0.0042610 — and this simulation were derived separately and
agree. The proxy's non-zero median at zero imbalance is a pure **speckle noise
floor**: LH and LV differ by chance at finite looks and the proxy squares that
difference, so the floor is positive-definite and biased upward. That is the same
fact as the ceiling, reached from the sampling distribution instead of from the
identity. **Neither is quoted as confirming the other's method; they share no
step.**

##### One deliberate control, and why it is in the table

The CPR = 1.00 row is kept even though it adds no new physics. An early version
of this simulation had a sign error on `Im(C[0,1])` that **inverted** the Stokes
CPR — 0.30 read as 3.35. **CPR = 1.0 is its own reciprocal, so that row alone
cannot detect an inversion**, and had the table contained only it, the bug would
have shipped. Every other row disagreed immediately. The row stays as a standing
reminder that a test whose expected value is a fixed point of the failure mode is
not a test.

#### 7.9.3 The simulator, validated against the swath — a pre-registered failure

Predictions were committed in `docs/preregistration_proxy_validation.md` **before
this was run**, because a simulator nobody checked against data is not evidence,
and that applies to ours.

**P1 — the Monte Carlo should reproduce the analytic form.** To first order the
proxy is `χ²₁/(8N)` when the channels are independent. Predicted median 0.01137
and p95 0.09604 at N = 5; measured 0.01207 and 0.09995 — within 4 %. **Held**, at
N = 5, 14 and 20.

**P3 — the observed swath cannot be quieter than the speckle floor.** This was
the falsifiable one, and **it failed.**

| | pre-registered | measured |
|---|---|---|
| simulated floor p95 at N = 14–20 | 0.024–0.034 | 0.024–0.035 |
| observed p95, native grid | *above the floor* | **0.00508** |

The observed swath came out **five times quieter than its own speckle floor** —
the same kind of inconsistency, in the same direction, as the intensity reading
of §7.2 putting the scene below the instrument's noise floor.

**Two candidate explanations, one wrong and one right.**

The first suspect was the grid. `cpr_real.tif` is 2048 × 2048 — the *resampled*
analysis product, not the native 2258 × 6618 — and resampling 6618 range samples
down to 2048 smooths by a further ~3.2×. Comparing it against a simulation at
native-grid N compares two different fields. So the native proxy was rebuilt from
the raw DN exactly as `process_real_sar_pipeline.py` forms it. **It made almost no
difference**: native p95 0.00508 against resampled 0.00478. The hypothesis was
tested and rejected.

The real cause was an omission in the simulator. **The measured LH/LV intensity
correlation over the swath is +0.9647.** CPR fixes only the *imaginary* part of
the H–V correlation; leaving the real part at zero — which the first version did
implicitly — makes the two channels as independent as the CPR allows, and so as
noisy as possible for a statistic built on their difference. With
`Var(δ₁ − δ₂) = 2(1 − r)/N`, a correlation of 0.96 lowers the floor by ~28×.

Supplying the **measured** |ρ| = √0.9647 = 0.9822 — measured, not fitted to close
the gap:

| | value |
|---|---|
| simulated floor p95, N = 14–20 | 0.00090 – 0.00133 |
| observed native p95 | **0.00508** |

**P3 now holds**, with the observed distribution sitting a factor of 5.6 above the
floor. That excess is real channel imbalance and terrain, which is a measurement
rather than an error. P2 holds likewise.

**What is honestly weaker after this.** The `(1 − r)` correction is first-order,
and at r = 0.96 the Monte Carlo departs from it by 5–10 % (0.00133 against
0.00121 predicted at N = 14) — so P1 passes in its independent-channel form and
not in its corrected form. And the correlation used is the *total* within-patch
correlation, which conflates speckle coherence with terrain shared between the
two channels; feeding it in as |ρ|² is an empirical calibration of the floor, not
a physical decomposition of it. Neither weakens §7.9.2, whose central claim —
population value identically zero at equal channel powers — holds at every
coherence, including zero.

**The pre-registered check earned its keep.** It was written to be capable of
failing, it failed, and what it caught was a real omission in our own simulator
rather than a problem with the data.

> **Had the prediction been written afterwards, the coherence term would never
> have been noticed.**

That is the whole justification for the habit. A simulator that disagrees with
the data by a factor of five is a discovery; a simulator tuned until it agrees,
and then written up, is nothing at all — and from the inside the two feel
identical unless the prediction was committed first.


#### 7.9.4 The joint criterion: specification, maximiser, and the measured rate

The 1.8 % joint rate (`backend/scripts/joint_criterion.py`, seed 7, 600 000
trials per row, N = 14) is now fully specified in `docs/joint_criterion.json::specification`
and copied into `docs/cpr_significance.json::joint_criterion`. Population at
true CPR 0.7, true m = m_min + 10⁻⁶ = 0.17647: E|H|² = E|V|² = 1,
E[H V*] = 0.000594 − 0.176471 i (|c| 0.17647, arg −89.81°); Stokes S₀ = 2,
S₁ = 0, S₂ = 0.00119, S₃ = 0.35294; CPR 0.7, DOP 0.17647. Draw: E_H = z₁,
E_V = c* z₁ + √(1 − |c|²) z₂, z ~ CN(0, 1) i.i.d. per look; S₃ = −2 Im⟨E_H E_V*⟩,
the physical sign of §1.11. Result: marginal 17.69 %, **joint 1.815 ± 0.017 %**.
At the requested maximiser — true CPR just below the band edge, 1.29875, with
m = 0.12996 just below the threshold (E[H V*] = 0.00051 + 0.12996 i, S₃ =
−0.25992) — the joint rate is 3.367 ± 0.023 % (marginal 75.25 %). A scan at
m = m_min + 10⁻⁶ shows the joint rate is nearly flat across the band, 3.72 ±
0.06 % at CPR 1.05 falling to 3.29 ± 0.06 % at the edge, so the edge point is
not the maximiser; the maximum inside DOP < 0.13 is ≈ 3.7 %. Beside the
simulation, the **measured** rate from the SLC (§1.11): 29.93 ± 0.15 % of the
88 421 cells with Stokes DOP < 0.13 have CPR > 1 at the physical sign, and
0.4498 ± 0.0028 % of all cells satisfy both — rates on this terrain, not at a
0.7 background, and printed as such.

### 7.10 External check: Putrevu et al. 2023, and why 29.16 % is an upper bound

*Generated by `backend/scripts/cpr_dispersion.py`; figures in
`docs/cpr_dispersion.json` and `docs/incidence_mask.json`.*

§7.7 computes noise exceedance rates from `CPR · F(2N,2N)` — the sampling
distribution of a ratio of two **independent** N-look intensities. That
independence is an assumption about the two circular channels, and it had never
been checked. A published DFSAR measurement checks it.

#### The constraint

Putrevu et al. 2023 (10.1029/2023JE007745) Figure 4 reports the Byrgius C
interior at **CPR = 1.07 ± 0.17**, a relative SD of **0.1589**. The paper
**states no ENL and no look count anywhere**; its only statement on the matter is
*"averaging several independent single-look coherency matrices"* (Sec 3.1). So
the look count has to be bounded from the geometry it does state:

**26° is the NADIR angle they print, not the incidence angle**, and the ground
range spacing is set by incidence. Converting first, with the same spherical
relation as §7.11:

```
sin θ_inc = ((R + h)/R) · sin η  →  η = 26.0000°  gives  θ_inc = 27.6198°
ground range spacing = 9.6 / sin(27.6198°) = 20.7074 m
```

| quantity | stated | |
|---|---|---|
| azimuth SLC spacing | 0.55 m | 25 / 0.55 = 45.45 samples |
| slant-range spacing | 9.6 m at 26° **nadir** | incidence 27.6198° → ground range 20.71 m → 1.2073 samples |
| output pixel | 25 m | **N ≤ 54.88** |

That product is an **upper** bound on N: it assumes every sample is independent
and all of them are used. The independent-channel floor is

```
sqrt((2N − 1) / (N(N − 2))) = 0.1936     at N = 54.88   ← conservative
                            = 0.1993     at N = 51.89   ← the alternative
```

**Their measured dispersion, 0.1589, is below their own floor.** A ratio of two
independent intensities cannot be that narrow.

**Which of the two is conservative, and an earlier version of this section had it
backwards.** A *larger* N gives a *lower* floor, and a lower floor is a harder
bar for the measured 0.1589 to sit under — so **54.88 is the conservative bound
and 51.89 is the flattering one.** The first version of this work used
`9.6/sin(26°)`, got 51.89, and called the difference "the safe way". It was the
favourable way. The claim survives against both floors, which is why the error
did not change the conclusion — but the reasoning quoted for it was wrong, and
that is worth more than the conclusion.

#### What follows

For two circular-Gaussian channels with field coherence ρ, the intensity
correlation is |ρ|², and correlation between numerator and denominator narrows
the ratio: relative SD² scales as (1 − |ρ|²). Inverting,

The estimator, and the arithmetic:

```
relSD_obs²  =  (1 − ρ_I) · relSD_indep²          correlation narrows the ratio
ρ_I         =  1 − (relSD_obs / relSD_indep)²
            =  1 − N · relSD_obs² / 2            with relSD_indep² → 2/N

relSD_obs   =  0.17 / 1.07 = 0.158879
relSD_obs²  =  0.02524238        relSD_obs² / 2 = 0.01262119
ρ_I         ≥  1 − 55.038 × 0.01262119  =  0.3054
```

**Their orbit altitude is not stated in the paper**, so three are tested — the
nominal 100 km, this product's label value, and a 150 km stress case:

| h | incidence | N ≤ | floor | 0.1589 below it? | **ρ_I ≥** (large-N) | ρ_I ≥ (exact floor) |
|---|---|---|---|---|---|---|
| 100,000 m | 27.6198° | 54.877 | 0.1936 | yes | 0.3074 | 0.3265 |
| **105,376 m** | **27.7076°** | **55.038** | **0.1933** | **yes** | **0.3054** | 0.3245 |
| 150,000 m | 28.4387° | 56.371 | 0.1909 | yes | 0.2885 | 0.3076 |
| *(nadir angle used directly)* | *26.0000°* | *51.891* | *0.1993* | *yes* | *0.3451* | *0.3642* |

> **|ρ|² ≥ 0.3054**, at the led-with N = 55.038.

**Two estimators are printed because neither may be left unsourced.** The large-N
form substitutes `relSD_indep² = 2/N`; the exact form uses
`(2N−1)/(N(N−2))`, which at N ≈ 55 is 0.19330 against `sqrt(2/N)` = 0.19058 — a
1.4 % gap that squares into 2.9 % of the bound. **The large-N form gives the
smaller number, so it is the conservative one and it is what is reported.**

**The bound moves, the conclusion does not.** Across the altitudes tested the
bound ranges 0.2885 → 0.3451, but their measured 0.1589 is below the
independent-channel floor in every one of them. The channels are correlated
whichever altitude is assumed; only *how* correlated depends on it.

The two circular channels are **correlated**, so **`F(2N,2N)` with independent
numerator and denominator is conservative**, and every noise exceedance rate in
§7.7 is an **upper bound on the rate, not the rate** — the operating-point
figure of **17.79 % at true CPR 0.7 and N = 13.72** included, and equally the
superseded **29.16 % at N = 5**, which §7.7 records as the value the narrative
wrongly quoted before the look count was resolved.

**This does not weaken the argument, it bounds it.** An upper bound of 29 % on
ordinary rock crossing a CPR threshold is still a reason not to trust the
threshold. What changes is that the figure must be *labelled* as a bound
wherever it appears, and `verify_all.py` now fails the build if the string
`29.16 %` occurs in this repository without the words "upper bound" nearby.

#### Our own dispersion does not settle it, and says so

The same question was put to this product directly. `cpr_dispersion.py` selects
the 20 most radiometrically homogeneous 15 × 15 windows — ranked by the
coefficient of variation of **s0_native**, backscatter, never of CPR, so the
selection cannot bias the statistic being measured — and reads the CPR
dispersion inside them:

| | |
|---|---|
| minimum relative SD over 20 windows | **0.5013** |
| median | 1.1226 |
| correlation correction (225 px hold 3.66 independent samples, ρ̄ = 0.2697) | × 1.1702 |
| **corrected** | **0.5867** |

against the independent-channel floor:

| N | floor | measured / floor | |
|---|---|---|---|
| 5.00 | 0.7746 | 0.757 | round figure in §7.7 |
| 5.83 | 0.6909 | 0.849 | measured ENL, LH, raw (§7.3) |
| 6.77 | 0.6232 | 0.941 | sub-band ceiling, 21/3.10 (§7.4) |
| **13.72** | **0.4055** | **1.447** | **measured ENL after the 5 × 5 boxcar (§7.6)** |

**The result is the opposite of what was expected, and the applicable row is the
last one.** CPR here is formed on the boxcar-smoothed field, so 13.72 is the look
count an independent model would use for *this* field — and against it the
observed dispersion is **1.45× wider**, not narrower. The measurement therefore
**does not** support the claim that the independent model overstates our spread.

**And the estimate itself is noisy, in the direction that helps the negative
conclusion — so it is volunteered rather than waited for.** With A = 61.42 px per
independent sample, a 15 × 15 window holds **3.66 effective samples**, and the
relative sampling error of an SD estimated from n effective samples is
`1/sqrt(2(n−1))` = **43 %**. The reported figure is then the **minimum of twenty**
such estimates, which selects the low tail of that spread. Both effects bias the
number **low**. A figure biased low that still lands *above* the theory is a
stronger negative result than the raw comparison suggests, not a weaker one — but
it also means the 0.5867 should not be read as a precise floor.

It also cannot refute it. The minimum over homogeneous windows is an **upper
bound** on the speckle floor: residual terrain structure inside a window adds
variance and can only push the figure up. A result above the theory is consistent
with the theory *and* with terrain, so nothing is claimed from this direction.
The experiment was designed to be able to fail, and it did.

**The upper-bound relabelling of 29.16 % therefore rests on the external
constraint, not on our own dispersion.** Recording which evidence carries a claim
matters more than the claim, and these two point in opposite directions.

### 7.11 The calibration constant, checked against theirs

Putrevu et al. give the calibration for ortho-rectified DFSAR images as
`σ⁰[dB] = 20·log₁₀(DN) − C`, with **C = 70.308868**.

This product's PDS4 label carries `calibration_constant = 70.308868`.
**Identical to six decimals** — difference `+0.000000` dB. Their constant is the
per-product label field, and the ingest is reading the right one. That is an
external check on the calibration path, not a coincidence to note and move past.

The formulae are not identical, and the difference is stated rather than
absorbed. Ours is

```
σ⁰ = DN² · sin(inc) / (K_lin · G²)
   → σ⁰[dB] = 20·log₁₀(DN) + 10·log₁₀(sin inc) − K − 20·log₁₀(G)
```

so two terms theirs does not have:

| | effective constant | vs theirs |
|---|---|---|
| LH | 70.467594 dB | +0.158726 |
| LV | 70.316881 dB | +0.008013 |

the per-channel gain imbalance from the same label; and a `sin(inc)` term their
stated formula has no equivalent of, which makes theirs a β⁰-like normalisation
and ours a division by the projected area. Neither is wrong — they are different
quantities, and quoting a σ⁰ from one against a σ⁰ from the other is not a
comparison.

**THE −4.660 dB PREVIOUSLY QUOTED FOR THAT TERM IS WITHDRAWN.** It was
`10·log₁₀(sin 19.998°)` — the *label nominal* — and the pipeline does not evaluate
it there. `process_real_sar_pipeline.py:408` computes `sin_inc` **per pixel** from
the product's incidence raster, so the figure described something the code does
not do. It is exactly the defect §0 names, in a number rather than a caption, and
it was found only because the value happened to equal 10·log₁₀(sin(look angle)) to
four decimals — which is what prompted the audit in §7.12.

### 7.12 Their incidence criterion, and why it is withheld

Putrevu Sec 4 omits local incidence below **20°** to stay in the Bragg domain
(20–50°). This project adopted the criterion, computed local incidence from the
product's own incidence raster, and reported an ellipsoid median of 14.44°, a
local median of 17.73°, and that **62.58 %** of the swath falls below the floor —
concluding that *"this pass was flown at a look angle of 19.998°, below the Bragg
floor for the entire scene"*.

**Every one of those figures is withdrawn, and that sentence with them.** The
raster they came from fails three independent geometric tests, and that failure
is a measured property of the distributed L2 product rather than a defect in this
project's arithmetic. It is therefore reported as a result, in **§12**, and the
criterion is **withheld** — `local_incidence_in_bragg_domain`, provenance
`NO DATA`, reason attached, criteria evaluable 5 of 6.

**The reconstruction was considered, quantified and rejected.** Deriving the field
ourselves needs the across-track distance from the sub-satellite track, and the
label carries no ephemeris. Fitting the track from the imagery gives **1.83 km
rms** (amplitude ribbon centreline, degree 4; max 6.0 km) and **2.95 km** (pointed
swath, degree 3; max 12.3 km), with the swath edges themselves only smooth to
3.0–5.3 km rms. At 1.83 km the induced error in local incidence is **≈ 0.5°**,
structured rather than random, against a near-range margin of **1.27°** between
the look angle and the incidence it implies. **Fitting an unverifiable geometric
model in order to reach a criterion is the thing this project refuses everywhere
else**, and it is refused here, with the arithmetic shown rather than a sentence
about judgement.


### 7.13 Texture that varies within the cell

§7.10's K-clutter argument draws one texture value per multilook cell, shared
by both circular channels, and the ratio tail is then exactly the F model's
(`docs/kclutter.json`: at 10⁷ trials, max |shared − F| = 0.0041 points against
a Monte Carlo σ of 0.0120 on one tail, and **0.0170 on the difference of two**,
which is the 0.02 points the manuscript quotes as the simulation's own sampling
error; the independent-texture rows span 27.47–39.34 %
over ν = 1.5–10). That cancellation needs the texture to be constant over the
averaging cell. `backend/scripts/kclutter_within_cell.py` (seed 7, 10⁶ trials
per row, N = 14, true CPR 0.7) lets each of the 14 looks carry its own texture
t_k, shared between the channels, so R = Σ t_k g₁ₖ / Σ t_k g₂ₖ and t_k no
longer cancels; t_k is i.i.d. Gamma(ν, 1/ν) or AR(1)-correlated across the
look index through a Gaussian copula at nominal lag-one 0.5 and 0.8 (achieved
Pearson 0.49 and 0.79) (`docs/kclutter_within_cell.json`):

| ν | texture across looks | exceedance P(0.7 R > 1) | − F model (points) | moment ENL of the textured cell |
|---|---|---|---|---|
| ∞ | none | 17.519 ± 0.038 % | −0.026 | 13.98 |
| 8 | independent | 18.811 ± 0.039 % | +1.267 | 11.20 |
| 8 | lag-one 0.5 | 18.558 ± 0.039 % | +1.013 | 9.56 |
| 8 | lag-one 0.8 | 18.273 ± 0.039 % | +0.728 | 7.34 |
| 4 | independent | 19.688 ± 0.040 % | +2.143 | 9.34 |
| 4 | lag-one 0.5 | 19.432 ± 0.040 % | +1.887 | 7.31 |
| 4 | lag-one 0.8 | 18.984 ± 0.039 % | +1.439 | 5.05 |

Within-cell texture does not cancel: it lifts the exceedance by 0.7–2.1 points
above the F model at these orders and lowers the textured cell's own moment
ENL well below N — which is the direction in which the measured 5.83 differs
from the nominal count. Correlating the texture across looks moves the rate
back toward the whole-cell case where it cancels exactly, and the ENL further
down.

## 8 · The 20 m DEM, and what it actually bought

### 8.1 The resample reversed direction, and the filter strength is a measurement

80 m → 25 m was a 3.2× **upsample**, where bilinear point-sampling is correct:
there is nothing between the posts to alias. 20 m → 25 m is a **downsample** of
f = 1.25, where it is wrong — `map_coordinates` interpolates, it does not
average, so content the 25 m grid cannot represent folds back instead of being
averaged away.

The two library conventions are four times apart and **neither is acceptable**.
Measured against an *ideal band-limited downsample* — a brick wall at the output
Nyquist, sampled onto the same 25 m grid, so both spectra live on one grid and no
cross-grid normalisation enters — over three windows of the real 20 m array:

| σ (source px) | passband loss ≥120 m | alias excess ≤65 m | worse of the two |
|---|---|---|---|
| `(f−1)/2` = 0.125 | −0.000 | **0.234** | 0.234 |
| `f/2` = 0.625 | **0.192** | −0.489 | 0.192 |
| **0.400 — shipped** | **0.042** | **0.031** | **0.042** |

**They fail in opposite directions.** `(f−1)/2` is indistinguishable from *no
filter* to four decimals in every column and every slope percentile — at f = 1.25
scipy truncates it to a three-tap kernel of centre weight ≈0.9999 — while the
unfiltered control runs **23.4 % hot in amplitude at Nyquist**, so the aliasing
is measured rather than assumed. `f/2` removes 19.2 % of real terrain at 120 m
and longer, which is the detail the 20 m product was fetched for.

σ = 0.400 is the **minimax**: it minimises the worse of the two failure modes, at
0.042 against 0.192 for the better convention — a 4.5× improvement. Reproduce
with `backend/scripts/choose_antialias_sigma.py`; recorded in
`docs/antialias_sigma.json` and in the DEM's provenance sidecar.

*Two defects in the first version of that measurement, both caught before the
verdict was used. A wavelength row fell outside the last frequency bin and a
`dict.get(..., [1,1,1])` default then supplied three **fabricated** 1.000s to the
verdict. And the control read 0.630 where it had to read 1.000, because two PSDs
on different grids were divided without normalising `|FFT|²` by `(dx/N)²` and the
window energy. The control now reads 1.000 at 400, 200 and 120 m, which is the
self-check that the method is sound.*

### 8.2 What the 1.85 GB bought — provenance, not resolution

Native frame, 25 m grid, 80 m source → 20 m source:

| | 80 m | 20 m | Δ |
|---|---|---|---|
| slope p50 | 9.343° | 9.563° | +2.4 % |
| slope p90 | 20.172° | 20.600° | +2.1 % |
| roughness p50 | 5.806 m | 5.948 m | +2.4 % |
| roughness p90 | 12.923 m | 13.077 m | +1.2 % |
| hazard p50 | 0.3355 | 0.3436 | +2.4 % |
| mean hazard | 0.3647 | 0.3726 | +2.2 % |
| slope > 15° | 25.161 % | 25.895 % | +0.73 pp |
| *critical hazard fraction* | *0.1146* | *0.1221* | *+6.5 %* |
| *slope max* | *62.787°* | *69.392°* | *+10.5 %* |

**The distribution shifted uniformly by about 2.4 %.** It is not that the tails
moved most: p50 +2.4 % against p90 +2.1 % is the same shift throughout. The two
larger numbers are *derived* and should not be read as detail gain —
`critical_hazard_fraction` moves 6.5 % because a 2 % shift amplifies at a
threshold crossing, and `slope max` is a single pixel.

**Why the gain is small, and it is not a disappointment.** The 25 m analysis grid
is the binding constraint, not the source posts. A 25 m grid cannot carry
anything below 50 m wavelength, and §8.1's measured filter low-passes at exactly
that Nyquist. So the 20 m product buys only the 50–160 m band — real, but modest
in any statistic taken on a 25 m grid.

**The real gain is provenance.** *"20 m native, low-passed and resampled to 25 m"*
is a clean statement. *"80 m native, bilinearly upsampled 3.2× to 25 m"* put a
caveat on **every** slope, roughness and hazard figure, and through them on every
landing criterion downstream. That caveat is now gone from the entire chain. That
is what the download bought, and claiming a detail gain the grid cannot carry
would be the opposite of the discipline this project is for.

**The 25 m grid stays.** The radar is natively 25 m. A 20 m grid would put real
20 m terrain under *upsampled* radar — trading one interpolation for a worse one.

### 8.3 The saturation problem had returned, in the request path

Roughness is a 5 × 5 window. On the 2048² serving grid the sample spacing is
**80.79 m**, so that window spans **~404 m** and measures *regional relief* — a
different physical quantity wearing the same name. `clip(roughness / 50)` then
pins at 1.0 and slope stops contributing to hazard at all.

`build_analysis.py` and `render_layers.py` — everything the UI reads — score on
the native 2258 × 6618 frame at 25 m and were never affected. But
`pradan_pipeline.process_real_dem`, which `mission_service` and the PDF use,
resized the DEM to the serving grid **first** and scored there.

**The precise statement is worth getting right, because it is a better sentence
than the loose one.** The bug existed and *could not reach the screen*. Phase 1
moved the UI onto the static analysis JSON, so the visible surface carried the
native, unsaturated numbers throughout — but the PDF report and any API consumer
were served saturated hazard, and would have been until someone looked. "The bug
existed" and "the bug existed and could not reach the screen" are different
claims, and only the second one is true here:

| hazard | p50 | p90 | p95 | p99 | pinned at 1.0 |
|---|---|---|---|---|---|
| resize-then-score *(was)* | 0.393 | 0.843 | 0.933 | **1.000** | **2.4143 %** |
| **score-then-average** *(now)* | 0.344 | 0.709 | 0.743 | 0.788 | **0.0000 %** |
| native reference | 0.344 | 0.721 | 0.744 | 0.788 | 0.0002 % |

The fix is the agreed one: score at 25 m, then **area-average the bounded 0–1
field** onto the serving grid — `INTER_AREA`, never `INTER_LINEAR`, which would
point-sample and reintroduce the aliasing. Averaging a bounded score is
meaningful in a way that averaging a DEM and re-differencing it is not.

`slope_max_deg` is carried **beside** `hazard_mean`, by a maximum filter sized to
the serving cell and then nearest-sampled, because an average hides the thing a
lander cares about: a cell that averages safe can still hold one impassable face.
Measured on the current frame, p50 11.36° against a cell-mean slope of 9.58°, and
the frame maximum of 69.39° survives the downsampling intact.

The 2048² table in the ingest log is now labelled **DIAGNOSTIC ONLY, DO NOT
QUOTE** with the reason inline, so it cannot be mistaken for a 25 m roughness.

### 8.4 One map, two scales, stated per layer

The horizon sweep runs on the LOLA polar array at 240 m effective and is **not**
rerun at 20 m: that array is 30400², 3.7 GB as float32, and 360 rotations of it
is not feasible. So after this phase the map draws **20 m-derived terrain beneath
an 80 m-derived shadow mask** — a 10× scale disparity, and the largest on the
map.

That is ordinary multi-scale practice and it is legitimate. It is not a footnote.
`layers.json` now carries a resolution record per layer, written by the same
script that renders the pixels, and the legend prints it:

| layer | native | effective | decimation |
|---|---|---|---|
| hillshade, dem_elevation, hazard_map | 20 m | 25 m | 1 |
| **illumination** | **80 m** | **240 m** | **3** |
| cpr_heatmap, dop_heatmap | 25 m | 25 m | 1 |

The field is optional in the TypeScript type so a manifest without it reads as
**absent** rather than defaulting to 25 m. Near-field horizon refinement at 20 m
is out of scope and was not started.

### 8.5 The Faustini floor, reported not tuned

From the new 20 m frame, relative to the label's own 1737400 m sphere:
min **−4250.8 m**, p01 −3933.0 m, p50 −821.1 m, max +1958.7 m.

The ingest prints its own prior — "expectation was −3 to −4 km" — as **NOT met**
and adjusts nothing. That prior came from a superseded handoff, not from a
published value, and p01 sits inside the band. The check that *can* fail is the
label-range reproduction in step 3.1, which passed with **residual 0** against a
0.5 m tolerance; this one cannot discriminate, because the old synthetic array
passed it too.

### 8.6 Evenly-spaced multi-azimuth hillshading degenerates to a slope map

A single-azimuth hillshade has a known weakness: faces pointing away from the
light shade identically to the flat ground beside them, so ridges running along
the light direction disappear. The standard remedy is to average several
azimuths. **Averaging *evenly-spaced* azimuths does not fix it — it destroys the
relief entirely, and this can be shown in one line.**

Horn's hillshade is

```
h(az) = cos(z)·cos(slope) + sin(z)·sin(slope)·cos(az − aspect)
```

Only the last term carries direction. Summing it over four azimuths 90° apart,
writing `a = −aspect`:

```
cos(0°+a) + cos(90°+a) + cos(180°+a) + cos(270°+a)
    = cos a + (−sin a) + (−cos a) + sin a
    = 0        exactly, for every aspect
```

The directional term vanishes identically. What survives is `cos(z)·cos(slope)`
— **a pure function of slope, with no aspect information at all.** The averaged
"hillshade" is a slope map wearing a hillshade's name.

Measured on this frame, at 100 m posts, against slope alone:

| scheme | contrast (std) | correlation with slope-only |
|---|---|---|
| single 315° | 0.0668 | −0.124 |
| **four evenly spaced, 315/45/135/225** | **0.0075** | **−0.950** |
| four across a 135° arc, 270/315/0/45 *(shipped)* | 0.0420 | −0.128 |
| ESRI-like 225/270/315/360, weights 3/3/1/3 | 0.0430 | −0.248 |

**−0.950 is the identity showing up in the data**, and the residual 0.0075 of
contrast is what is left after `cos(slope)` is stretched across the display
range. Nine times less contrast than the single sun it was meant to improve on.

The failure is also visible without any of this: the rendered layer's luminance
median went to **228 of 255 with 4.6 % pure white**, because a near-constant
field stretched to p2–p98 amplifies its own noise. The histogram check in §8.7
caught it as a brightness problem; the cause was three steps upstream.

**What ships is four azimuths across a 135° arc.** Confining them to less than a
half-turn leaves the directional sum non-zero, so the scheme keeps a single sun's
directional information (−0.128, identical) while filling the faces a single sun
leaves black. The single-azimuth path is kept behind
`render_layers.py --hillshade-azimuths 315`.

*This is a display choice and is recorded as one in `layers.json`. It says nothing
about where the Sun actually is: the real Sun here is within 1.54° of the horizon
and lights almost none of this frame, which is the Solar Illumination layer,
computed from horizons, and a different thing entirely.*

### 8.7 The base-map filter, measured on the rendered pixels

`mc.css` applies a CSS filter to the hillshade. Its setting is measured rather
than chosen: `backend/scripts/hillshade_histogram.py` reads the declaration out
of `mc.css`, applies it to the exported `hillshade.webp`, and reports the
luminance histogram. The rule is a post-filter median at or below ~190 and no
more than 1 % of pixels clipped at 255.

At the shipped `brightness(1.10)` the median was fine at 163, but **7.197 % of
the frame clipped to pure white** — a fourteenth of the map with its relief
gone. Walking brightness back with contrast held at 1.06:

| brightness | post-filter median | clipped at 255 |
|---|---|---|
| 1.10 | 163 | 7.197 % |
| 1.08 | 160 | 6.300 % |
| 1.04 | 154 | 4.472 % |
| 1.00 | 148 | 2.960 % |
| **0.98** | **145** | **0.000 %** |

`brightness(0.98)` is the first value that clears both rules and is what ships.

## 9 · Are the landing sites real terrain, or LOLA interpolation?

Phase 3's five best sites came back with slopes of 0.05–0.55° against a frame
median of 9.56°, hazards of 0.006–0.023 against 0.339, and roughnesses of
0.55–2.29 m against 5.95 m. **A slope of 0.05° on a 25 m grid means the surface
rises about 2 cm over 25 metres.** All five sit between −85.9° and −86.4°, the
equatorward edge of a frame running to −89.26°.

**There is a mechanism that would produce exactly that.** The DEM's own label
says so: *"The ground tracks are interpolated using the Generic Mapping Tools
programs `mapproject`, `blockmedian` and `surface`."* GMT `surface` is a
minimum-curvature spline — **smooth by construction wherever tracks are sparse**
— and LOLA track density falls away from the pole. **The product publishes no
per-pixel track-density or quality band**, so nothing in the file distinguishes a
measured cell from an interpolated one.

So two hypotheses predict the same site list: those are the flattest places, or
those are the emptiest places. Three tests separate them.

### 9.1 Roughness against latitude — suggestive, not decisive

| latitude | roughness p50 | slope p50 |
|---|---|---|
| −90.00 … −89.75 | 13.40 m | 20.75° |
| −89.00 … −88.75 | 6.22 m | 10.03° |
| −87.00 … −86.75 | 7.76 m | 12.24° |
| **−86.25 … −86.00** | **7.59 m** | **12.18°** |
| −85.25 … −85.00 | 2.49 m | 4.15° |

Correlation of roughness with latitude across 21 bands: **−0.498**; equatorward
of −86.5 the median roughness is 0.771× the poleward value. Latitude increases
equatorward, so a *negative* correlation is the artifact direction, and a mild
trend is present. **But it is not conclusive**: the poleward-most band is genuine
Shackleton-area relief and drags the fit by itself, and the bands where the sites
actually sit read 4.5–7.6 m — ordinary.

### 9.2 Where the ultra-smooth pixels are — decisive, and it exonerates the sites

Band medians answer "is the region smoother". The site list is built from
individual *pixels*, so the question is where the ultra-smooth pixels live.
Enrichment is the share of sub-1.2 m-roughness pixels in a band divided by that
band's share of area; 1.0 means they are spread exactly like area.

| latitude | enrichment |
|---|---|
| −85.25 … −85.00 | **3.65** |
| −85.00 … −84.75 | **2.98** |
| −88.50 … −88.25 | 1.87 |
| **−86.50 … −85.75 (all five sites)** | **0.59** |

**The artifact is real and it is not where the sites are.** The extreme
equatorward bands are enriched 3–3.7× in ultra-smooth pixels — the interpolation
signature, exactly as predicted. But in the band holding all five sites, smooth
pixels are **under**-represented at 0.59×. The sites are not drawn from the
suspect region.

### 9.3 Planarity — the test that separates flat from empty

A real crater floor carries metres of micro-relief about its mean plane over a
kilometre. A spline drawn between distant tracks does not. Fitting a plane to
each site's 2 km box, against 200 random boxes in the same frame (p05 **8.20 m**,
p50 20.91 m):

| site | latitude | plane-fit RMS | vs reference p05 | local rank |
|---|---|---|---|---|
| 1 | −86.2714 | 62.46 m | **7.62×** | 0.3 % |
| 2 | −86.4434 | 36.02 m | **4.39×** | 0.1 % |
| 3 | −86.0109 | 32.46 m | **3.96×** | 0.5 % |
| 4 | −86.2995 | 51.17 m | **6.24×** | 0.2 % |
| 5 | −85.8987 | 41.23 m | **5.03×** | 8.5 % |

Every site's neighbourhood is **3.9–7.6× further from a plane** than the
smoothest 5 % of the frame, and above the median. The *local rank* says the rest:
each site is smoother than 99.5 % of its own 2 km box, whose median roughness is
3.7–6.2 m. **These are small genuinely flat spots — crater floors — sitting
inside ordinary rough terrain, not regions where the data ran out.**

**Verdict: the sites are real.** The artifact exists in this product and is
measurable, but it lives at −85.25 to −84.75 and the site list does not draw from
there.

### 9.4 The guard, because it was luck and not design

Nothing in Phase 3 excluded the enriched bands — the other criteria happened to.
So each site now carries an `interpolation_check`: its 2 km plane-fit RMS, the
frame's reference p05, and a verdict. A site whose neighbourhood fits a plane
*better* than 95 % of the frame is marked **SUSPECT**, with the terrain figures
there called possibly unresolved rather than flat. **Marked, not dropped** — a
site excluded silently is a claim about the Moon; a site marked is a statement
about the data.

### 9.5 Why all five cluster in 0.55° of latitude

The physical cause is this project's own correction: max solar elevation is
`1.54° + (90 − |φ|)`, so 5.29° at −86.3° against 2.29° at −89.25°. Measured, the
illumination field follows it:

| latitude | illumination p50 | max solar elevation |
|---|---|---|
| −90.0 … −89.5 | 0.0295 | 1.79° |
| −88.5 … −88.0 | 0.0002 | 3.29° |
| −87.0 … −86.5 | 0.0591 | 4.79° |
| **−86.5 … −86.0** | **0.2677** | 5.29° |
| **−86.0 … −85.5** | **0.3184** | 5.79° |
| −85.0 … −84.5 | 0.1610 | 6.79° |

Correlation of illumination with latitude: **+0.544**. The band the sites occupy
is the illumination maximum of this frame — and it is a *local* maximum, not the
edge, which is why the sites cluster at −86 rather than at −84.8.

### 9.5b Two different sets of six, and why they are now named apart

**`all_six_fraction` and `all_six_area_km2` in `landing_sites.json` are the six
LANDING-SITE criteria** — slope, roughness, hazard, amplitude mask, cold-trap
distance, illumination. They are **not** the six ice-screening criteria of §1.

Both sixes were on one screen: the verdict card's checklist listed six
ice-screening criteria (five evaluable since §7.12 withheld the Bragg row), and
directly under it a cell read *"14,943,444 pixels searched — six criteria, native
25 m"*, counting the landing-site set. A reader was entitled to take them for the
same six and conclude the withdrawn row had been searched anyway. Every surface
now says which set it means — the card, the stage panels, the report, and the
artifact keys, which gained
`all_six_landing_criteria_fraction` / `all_six_landing_criteria_area_km2`
alongside the originals rather than replacing them, because documents already
reference the old names.

### 9.6 The score decomposition — the largest weight does the least work

| site | safety (w 0.50) | power (w 0.31) | access (w 0.19) |
|---|---|---|---|
| 1 | 0.492 (53 %) | 0.279 (30 %) | 0.159 (17 %) |
| 2 | 0.495 (54 %) | 0.278 (30 %) | 0.147 (16 %) |
| 3 | 0.497 (54 %) | 0.249 (27 %) | 0.169 (18 %) |
| 4 | 0.489 (54 %) | 0.280 (31 %) | 0.132 (15 %) |
| 5 | 0.488 (54 %) | 0.237 (26 %) | 0.173 (19 %) |

Safety carries the largest weight and **more than half of every score — and it
does none of the ranking.** Across the top five its term value ranges only
0.976–0.994, because `safety = 1 − hazard` and every candidate is already
near-perfectly safe; the term is saturated. Power ranges 0.758–0.896 and access
0.704–0.923. **The order of this list is decided by the two terms carrying
together less than half its weight.**

### 9.6a Safety is applied twice, and the second application is inert

The cause is structural, not accidental. **The criteria filter has already
removed every pixel with slope > 12°, roughness > 10 m or hazard > 0.50.** So
everything reaching the composite is safe by construction, and `1 − hazard` has
almost nothing left to separate:

| term | weight | min | max | **span** | role here |
|---|---|---|---|---|---|
| access | 0.188 | 0.704 | 0.924 | **0.219** | ranks the list |
| power | 0.312 | 0.759 | 0.896 | **0.137** | ranks the list |
| **safety** | **0.500** | 0.977 | 0.994 | **0.017** | **inert — a gate, not a discriminator** |

**The largest weight has the smallest span.** Safety enters the answer twice —
once as a hard gate, where it does all its work, and once as a weighted score,
where it can do none. That is the same double-counting fixed in Phase 1b, where
`scientific_value` carried only distance while distance had already been
subtracted: a quantity counted once where it bites and once where it cannot.

**The ranking of this list is determined by the power and access terms alone.**

**The weights are not retuned.** Reweighting to make safety "count" would be
threshold-tuning against one frame. The weight is defensible: on rougher terrain,
or a crater where the filter admits more marginal ground, safety would
discriminate. **Its inertness here is a measurement, not a flaw**, and the span
is reported beside the weight so a reader who sees "safety 0.50" cannot conclude
that safety drove the choice.



### 9.7 What "PSR km" does not mean

Every site reports a distance to the nearest permanently shadowed region, and it
will read as proximity to ice. It is not. **Candidate area in this frame is
0.00 km² — no pixel passes the ice criteria at all** — so no site here is near
detected ice, because nothing was detected. The figure is the distance to the
nearest **modelled** cold trap, from the Phase 2 horizon computation at 240 m
effective resolution. A cold trap is where ice *could* persist; that is a
different claim from where ice *is*. Each site now carries that sentence in its
own record.

## 10 · Traverse planning, and connectivity before distance

### 10.1 Connectivity is reported first, and that ordering is the point

A planning cell is impassable if **any** 25 m face inside it exceeds
`MAX_TRAVERSABLE_SLOPE_DEG` = 20°. That is the conservative rule and the correct
one — a rover meets the worst face in a cell, not its average — but `slope_max`
rises fast with cell size (p50 already 18.15° at 0.55 km cells), so at a coarse
planning resolution the graph can fragment on single steep faces.

**If it did, every `UNREACHABLE` would be reporting the cell size rather than the
Moon** — the same shape as the hazard saturation of §8.3, one level up. So
connectivity is measured and printed before a single route is computed, at two
resolutions:

| planning res | cells | passable | components | largest | sites inside it |
|---|---|---|---|---|---|
| 100 m | 932,856 | 81.32 % | 1,717 | 746,975 | **5 / 5** |
| 50 m | 3,735,861 | 85.92 % | 6,507 | 3,167,476 | **5 / 5** |

**The graph does not fragment.** All five sites lie in one component at both
resolutions, and that component holds 98.5 % of all passable cells at 100 m — the
other 1,716 components are small pockets walled in by steep ground. The passable
fraction moves 81.32 % → 85.92 % between the two resolutions, which is the
aggregation effect made visible rather than assumed away.

**The slope limit was not relaxed to reconnect anything**, because nothing needed
reconnecting; had it fragmented, the finer figures are what a reader would use to
tell terrain from quantisation.

### 10.2 What is quantised, and by how much

Planning runs at **100 m**. Every reported length is a multiple of 100 m, or
141.4 m diagonally, so a route reported as 4,180 m is **4,180 ± 50 m**. The
planner cannot resolve finer than one cell and does not pretend to.

Graph: 758,637 nodes, 5,806,726 directed edges, 8-connected, Dijkstra via
`scipy.sparse.csgraph`. Edge cost is ground length × (1 + 2 × mean hazard).
**Cost and length are tracked separately**: a cost is a planning quantity, a
length is a claim about the Moon.

### 10.3 The primary deliverable — and what the rover is driving to

**Candidate ice area in this frame is 0.00 km².** There is no measured ice target
anywhere here, so a traverse "to the ice" would be a route to something this
project did not find. The primary result is instead the route from each site to
the nearest **modelled cold trap** boundary — 206,967 cold-trap cells, 142,888 of
them passable — carrying the same caveat the site records do.

| site | length | climb | energy (J/kg) | cells | status |
|---|---|---|---|---|---|
| 1 | 3,273 m | 0.0 m | 1,330 | 30 | REACHABLE |
| 2 | 4,663 m | 46.9 m | 1,970 | 41 | REACHABLE |
| 3 | 2,207 m | 0.2 m | 897 | 21 | REACHABLE |
| 4 | 7,280 m | 47.6 m | 3,035 | 68 | REACHABLE |
| 5 | 1,641 m | 44.0 m | 738 | 17 | REACHABLE |

**This is the mission chain the project set out to demonstrate** — land here,
drive this far, spend this much — and it is honest only because the target's
status is stated: *a cold trap at 240 m effective resolution is where ice could
persist, not where ice is, and no radar detection supports it.*

The energy figure is marked **DERIVED** and is reported **per kilogram**, so no
rover mass is invented: `g_moon × (μ_roll × length + positive climb)` with
`g = 1.625 m/s²` and an **assumed** rolling resistance `μ_roll = 0.25`. That
coefficient is a stated assumption, not a measurement.

### 10.4 The pairwise matrix is the result; the tour is a demonstration

The site-to-site matrix shows the planner works between arbitrary pairs. **It is
not a mission plan.** Neither is the tour: no lander visits five sites, a lander
goes to one. The shortest tour (order 1 → 4 → 2 → 3 → 5, 76,025 m) is computed by
**exact enumeration** of all 4! permutations with the first site fixed — not a
heuristic, not annealing; for n ≤ 8 the optimum is cheap to prove. It is labelled
in the output and in `traverse.json` as a capability demonstration so nobody reads
it as a proposed concept of operations.

`UNREACHABLE` is an explicit state and never a distance of 0. A zero would read
as "no travel needed", which is the opposite of what it means.

### 10.5 The detour ratio, which is where the information is

A raw length says little. The ratio of route length to straight-line separation
says what the terrain does:

| pair | straight | route | ratio |
|---|---|---|---|
| 1–2 | 5,263 m | 5,638 m | **1.07** |
| 1–4 | 5,963 m | 6,404 m | **1.07** |
| 2–4 | 7,760 m | 8,408 m | **1.08** |
| 3–5 | 5,613 m | 6,153 m | **1.10** |
| 2–5 | 19,307 m | 59,877 m | **3.10** |
| 1–5 | 14,776 m | 58,923 m | **3.99** |
| 4–5 | 12,600 m | 65,327 m | **5.18** |
| 1–3 | 9,422 m | 54,106 m | **5.74** |
| 3–4 | 8,817 m | 60,510 m | **6.86** |

**The five sites are not one neighbourhood.** They fall into two groups — {1, 2,
4} and {3, 5} — internally connected at ratios of 1.07–1.10, and separated from
each other by 3.1–6.9×. Sites 1 and 3 are 9.4 km apart in a straight line and
54 km apart by rover. **A table of raw lengths would not show that**; the ratio
does, and it is a fact about this frame rather than about the planner.

*Asserted, not assumed: every route is at least its straight-line separation. A
path shorter than the Euclidean distance would mean the length accumulator or the
grid mapping is wrong, and the number would look entirely plausible while being
impossible.*

### 10.6 The routes are drawn, and the drawing is a gate

Until this pass the five routes existed only in `traverse.json`; the map showed
the API's demo-target path instead. They are now drawn from the artifact — every
one of the **177 waypoints**, at the planning cell centre, converted to the 25 m
raster grid by `planning.resolution_m / native_metres` read from the file rather
than written as `4`. Selecting a route flies the map to it, because five routes
spread over a 165 km frame do not fit the 40 km opening window and a route
off-screen answers nothing.

Three things are asserted at draw time, and each one exists because the quantity
it compares had no comparator before:

1. **The drawn route and the reported length are the same route.** The polyline
   is re-summed in the browser — `resolution_m` per orthogonal step,
   `resolution_m·√2` per diagonal — and must agree with `length_m` to 1 m. Two
   independent sums of one route is how the traverse coverage figure came to
   disagree with itself earlier in this project.
2. **The route starts where the site is.** Enforced in `plan_traverse.py` against
   `landing_sites.json`, to within one planning cell of great-circle distance —
   the check that would have caught the longitude convention error of §0, and
   did not exist until it had already happened. Measured: 25.0–55.8 m against a
   150 m tolerance.
3. **A site that passed `in_amplitude_mask` plots inside the measured ribbon.**
   Enforced in the map against the search's own per-criterion record.

**`UNREACHABLE` is drawn as nothing.** Not a faint line, not a dashed one: a
route that does not exist gets no geometry, and the panel prints the word.

The rover itself is an **illustration and carries no measurement**. There is no
rover mass, wheel geometry, speed or duty cycle anywhere in this project — which
is exactly why the energy figure is per kilogram — so the vehicle is a drawing
placed on a computed path, the traverse runs at a fixed 22 s end to end
regardless of length, and the panel says so beside the marker. Its position is
interpolated by **distance**, not by vertex index, because diagonal steps are
1.414× longer than orthogonal ones and index interpolation would put the marker
out of step with the odometer beside it.

## 11 · Detection statistics — the contribution

> **Read down a column: at N = 6 nothing clears the floor, by N = 38 everything
> does. The look count decides the answer, and it is not reported.**

That is this section's thesis, and it is the project's contribution. It accuses
nobody of being wrong, it is checkable by anyone in ten minutes with
`scipy.stats.f`, and the table it refers to is §11.3.

### 11.1 Per-pixel significance, at a named look count

Not *"is this value high"* but *"is it significantly above threshold"*, with the
confidence stated and the effective look count **named rather than assumed**. The
screened field carries **N = 13.72 (LH) to 19.77 (LV)** — measured in §7.3–7.6,
where the raw product's 5.83/5.14 looks are multiplied by the 5 × 5 boxcar's
**2.35–3.84×, not 25×**, because the pixels are correlated.

| N | relative SD | bias E[R]/CPR | 95 % single-pixel floor |
|---|---|---|---|
| 13.72 | 0.405 | 1.079 | **1.895** |
| 19.77 | 0.331 | 1.053 | **1.698** |

**A single pixel must read above 1.70–1.90 to be significantly above a threshold
of 1.00.** The swath's maximum is **0.0534** — short of the floor by a factor of
**35**. Zero of 2,337,086 measured pixels reach it.

*The raster is named for what it is.* Our proxy is **not** F(2N,2N)-distributed
(§7.9.2), so `cpr_significance.tif` is the ratio of the measured value to the
floor a **true** `σ_SC/σ_OC` would have to clear — not a p-value on our own
quantity. Conflating the two would be the error this section exists to identify.

### 11.2 The candidate area, and why it carries no interval

| | |
|---|---|
| candidate pixels | **0** of 2,337,086 measured |
| candidate area | **0.0000 km²** |
| interval on that area | **none is reported** |
| effective samples (a measurement, and it stands) | **38 050** = round(2 337 086 / 61.4207) |

**Withdrawn 2026-09-16: the interval, not the zero.** This section reported a
95 % score interval of [0.0000, 0.147] km² on 38 050 effective samples, and
before that [0.0000, 0.0024] km² on the raw pixel count. The second correction
was right as far as it went — pixels are correlated at 61.42 px per independent
sample (§7.9.1), so the raw-pixel interval was about sixty-one times too narrow
— but it fixed the sample size of a statistic that should not have been computed
at all.

An interval of that kind answers *a detector fired k of n times; what is its
rate?* This screen is not that detector. §1 proves its firing rate is zero
**algebraically**, for every admissible input, on any terrain: no pixel with
DOP_a < 0.13 can carry CPR_a above 0.0042611, and the threshold is 1.00. A zero
that is forced by the arithmetic has no sampling uncertainty for an interval to
express, and attaching one invites exactly the misreading it was meant to
prevent — that this was a measurement which happened to land on zero and might,
on another pass, land elsewhere.

Both superseded intervals are kept, labelled, in
`docs/detection_statistics.json::candidate_area.withdrawn_interval`: a wrong
number that vanishes cannot be audited and its correction cannot be checked.

**What stands in its place** is stronger than either interval. The screen is
empty by construction (§1); the largest CPR_a anywhere in the swath is 0.0534,
and among pixels satisfying the DOP condition the threshold would have to fall
by a factor of **234.68** before the first pixel passed (§1.9); 40.21 % of
measured pixels are *excluded* from the DOP condition by their amplitudes alone
and the remaining 59.79 % are undecidable (§1.3, `docs/dop_exclusion.json`).
Those are measurements, and none of them is a rate with an unknown parameter.

### 11.3 The published detections against their own floors

Published CPR **is** `σ_SC/σ_OC`, a ratio of two N-look intensities, so it **is**
F(2N,2N)-distributed and the F machinery applies to these values — and not to
ours.

| feature | CPR | N=6 | N=9 | N=21 | N=38 | N=100 |
|---|---|---|---|---|---|---|
| *95 % single-pixel floor* | | *2.69* | *2.22* | *1.67* | *1.46* | *1.26* |
| F2 | 1.95 | no | no | **yes** | **yes** | **yes** |
| F3 | 1.60 | no | no | no | **yes** | **yes** |
| S1 | 1.45 | no | no | no | no | **yes** |
| H3 | 1.30 | no | no | no | no | **yes** |

**Read down a column, not across.** At N = 6 no published value clears a
single-pixel 95 % floor; by N = 38 all four do. **The look count decides the
answer, and it is not reported in the source.**

**Every assumption this rests on, listed rather than buried:**

1. Published CPR is `σ_SC/σ_OC` from the Stokes vector — stated in the source,
   not our inference.
2. **Their look count is not stated in the open text.** The table is therefore
   computed *across* a range of N, and no single floor is quoted for their data.
3. **Our measured ENL cannot be transferred to their product.** Ours is a
   compact-pol `sri` product from one pass; theirs is full-polarimetric L- and
   S-band from a different acquisition and processing chain. **The point is not
   that their N is ours — it is that nobody has measured theirs.**
4. These floors are for a **single pixel**. A detection averaged over many pixels
   has a lower floor, by roughly √n_eff — and n_eff, not n, because CPR pixels
   are correlated (§7.9.1 measures 61.42 px per independent sample in our field).
5. **No claim is made that any published detection is wrong.** The claim is that
   the floor is not reported alongside it, so a reader cannot tell.

### 11.4 The gate

`emit_provenance.assert_detection_area_has_interval` fails the build if
`candidate_area_km2` reaches the UI without an interval computed in the same run.
It checks that the interval exists, that it brackets the area, that it has
non-zero width, and that the two came from the same run rather than two.

**A measured zero is not exempt** — exempting it would remove the interval from
the only number this project actually reports. Verified by injection: removing
`docs/detection_statistics.json` fails the build with the reason, and restoring
it passes.

### 11.5 The probe — the null result made checkable rather than assertable

`0.0000 km²` is a claim a reader has to take on trust. The **criteria probe**
turns it into something they can check anywhere: click any point on the map and
it reports the measured CPR and DOP there, each against its own threshold, the
margin in both directions, and how far the reading falls below the §11.1
one-sided 95 % critical value.

It was asked for as a way to "predict where ice spots exactly are", and **that
tool cannot honestly be built here** — there is nothing to predict, and §1 shows
the screen is empty *by construction* rather than by chance. A panel that output
"ice is here" would fabricate the single number this project exists not to
fabricate. What it does instead is stronger: it lets the emptiness be inspected
point by point instead of asserted once.

Four properties make it a measurement rather than a picture of one:

- **The values are shipped as values.** The rendered layers are colourised,
  clipped and lossy `.webp`; the colour map is not injective, so reading pixels
  back off the canvas would produce a number that looked measured and was not.
  `emit_probe_grid.py` writes float32 instead.
- **The decimation is stated in the header and repeated in the readout.** Every
  value is a block mean over 8×8 native 25 m pixels — a **200 m cell**, outlined
  on the map at the size the number actually covers, because a crosshair on the
  click point would imply the value belongs to that spot.
- **Absent is absent.** A cell with no measured radar reads `NaN`, and the panel
  prints `NO DATA — they are not zero and they are not low; they are absent`.
  All three coverage states are distinguished: measured radar, *pointed and
  returned integer zero* (56.11 % of ISRO's own swath mask), and never observed.
  Collapsing the middle case into either end would discard the two-mask model.
- **Nothing is restated.** The thresholds come from `config.py`, the floor and
  the look count from `detection_statistics.json`, and the algebraic ceiling is
  recomputed from the configured DOP threshold as `tanh²(artanh(d)/2)` rather
  than pasted as `0.0042610` — so if anyone moves the gate, the bound moves with
  it instead of quoting the old one beside the new one.

A representative reading inside the ribbon, at −86.3039°, 83.1289°:
`CPR 2.684 × 10⁻⁴` against a threshold of 1.00 — **3.7 × 10³ below it** — with
`DOP 0.0263` passing, and the panel explaining at that point, with that point's
own numbers, that DOP passing is precisely what caps CPR at 0.0042611. The same
cell is **7.1 × 10³ below** the 1.8946 critical value.



---

## 12 · Measured defects in the distributed L2 product

*`backend/scripts/incidence_audit.py`; figures in `docs/incidence_audit.json`.
Gate G12 (`assert_incidence_geometry.py`) fails the build if any consumer uses a
field that violates the identity below.*

Everything in this document up to here is a measurement of the Moon, of this
project's own arithmetic, or of the literature. **This section is a measurement
of the product**, and it is here because it is a finding rather than an
inconvenience.

### 12.1 The identity

On a convex body the incidence angle always exceeds the spacecraft look angle:

```
sin θ_inc = ((R + h) / R) · sin η
```

`R = 1,737,400 m` and `h = 105,376 m` are **read from the PDS4 label**, not
assumed, giving `(R + h)/R = 1.060652`. At the label's own look angle
`η = 19.9979°` this forces **`θ_inc = 21.2678°`** — a **1.27° margin** that no
correct implementation can be on the wrong side of. It is an identity, not a
tolerance.

**And the label contradicts it directly:** it reports
`look_angle = incidence_angle = 19.997919`. Those cannot be equal on a sphere.
That is the first sign, and it is in the product's own metadata.

### 12.2 What the incidence raster should carry

Forward geometry across the swath, anchored with the near edge at the incidence
the scene-centre look angle implies (`γ = d/R`, `η = atan(R sin γ / ((R+h) − R cos γ))`,
`θ = γ + η`):

| ground range from near edge | incidence |
|---|---|
| 0.0 km | 21.268° |
| 10.0 km | 26.176° |
| 20.0 km | 30.740° |
| 30.0 km | 34.949° |
| 44.5 km | 40.437° |

**Total span 19.170° over 1,780 pixels = 0.0108 °/px**, smooth and monotone.
(Anchoring the swath centre at the nominal instead gives 9.29 → 31.72°, a 22.43°
span and 0.0126 °/px; both are quoted below because the smoothness test should
not depend on which anchoring is chosen.)

**This places the scene almost entirely INSIDE the 20–50° Bragg band.** Which
means the withdrawn claim — *"below the Bragg floor for the entire scene"* — was
not merely unsupported. **It was very likely backwards.** The replacement figure
offered in review, a 24.49° local median, is withdrawn for the same reason: it
inherits the +3.29° terrain offset computed from the same unusable raster, and an
offset derived from a field of unknown meaning is not rescued by being added to a
correct number.

### 12.3 Three tests, three failures

| test | expectation | measured | verdict |
|---|---|---|---|
| **magnitude** | 0 % of pixels below the spacecraft look angle | **80.53 %** | **fail** |
| **smoothness** | 0.0108–0.0126 °/px across the swath | **0.4443 °/px** median, max **39.7** | **fail (35–41×)** |
| **terrain** | a *local* incidence tracks slope | **−0.0006** | **fail** |

Each test can fail on its own and each is a different kind of evidence:
magnitude says the values are impossible, smoothness says the field has no
geometric structure, and terrain says it is not a terrain-corrected local
incidence either. **The raster is neither of the two things an incidence layer
can be.**

### 12.4 What it does and does not reach

The same raster is in the calibration — `σ⁰ = DN² · sin(inc) / (K_lin · G²)` —
so it multiplies both channels before the boxcar. **§1.6 measures what that
propagates to**: 0 pixels change their screening outcome, peak CPR moves
0.053411 → 0.053852, and the maximum pointwise excursions are 1.310 × 10⁻² in CPR
and **1.393 × 10⁻¹ in DOP, 1.07× the entire DOP threshold**. σ⁰ itself is scaled
by a field of unknown meaning; `s0_native` carries that caveat and no ratio
depends on it beyond those maxima.

### 12.5 The claim, and its caveats

> **Claim 8. The distributed L2-SELENOREF product ships an incidence-angle raster
> that fails three independent geometric tests. We measured it; no published work
> reports it.**

Carrying the same four caveats as claims (a)–(d) in §7.8:

1. **It is a property of this product**, `ch2_sar_ncxl_20200808t201154198`, and of
   the `sri` ortho-rectified L2-SELENOREF branch. Nothing here says the `gri` or
   `sli` products, other passes, or the S-band instrument share it.
2. **Absence from the literature is not absence of knowledge.** No paper this
   project's sweep found reports the geometry of a DFSAR incidence layer — but
   ISRO may well know it internally, and a processing note we have not seen would
   settle it. The claim is that it is *not in the published record*, which is a
   claim about the record.
3. **We do not know what the raster is.** Three tests say what it is not. Naming
   it would require the processing chain, and guessing would be exactly the
   failure this project is built to avoid.
4. **It does not reach the headline.** The candidate area is unchanged, and the
   null result stands on §1.2's algebra, which needs no incidence field at all.

**What it does change** is that a Bragg-domain criterion cannot be applied to
this product, and that any published analysis which used that raster for a
geometric purpose — masking, terrain correction, or an incidence-dependent
scattering model — inherits whatever it actually contains.


---

*Sections 9, 10 and 11 are written: the site search, the traverse, and the
detection statistics. The Stokes derivation is Phase 5b and is not written,
because it is not computed — the complex `sli` products are on disk and not
ingested, and §1 states exactly what having them would change.*

### 12.6 How far sin θ propagates

§12.5 reports the maximum |ΔCPR_a| and |ΔDOP_a| between the with-sin θ and
without-sin θ pipelines. `backend/scripts/propagation_percentiles.py` re-runs
`incidence_audit.screen()` verbatim and reports the distribution over the
amplitude mask, and where the maximum sits (`docs/propagation_percentiles.json`;
map `docs/propagation_ddop_map.png`, log₁₀ |ΔDOP_a| with the maximum marked):

| | p50 | p90 | p99 | max | maximum at | on the mask edge? |
|---|---|---|---|---|---|---|
| \|ΔCPR_a\| | 2.326 × 10⁻⁵ | 2.721 × 10⁻⁴ | 1.407 × 10⁻³ | 1.310 × 10⁻² | line 1522, sample 1136 | no (interior) |
| \|ΔDOP_a\| | 1.144 × 10⁻³ | 9.531 × 10⁻³ | 3.376 × 10⁻² | 1.393 × 10⁻¹ | line 1285, sample 2573 | no (interior) |

The edge band (amplitude mask minus its 5 × 5 erosion) has maxima 8.768 × 10⁻³
and 1.187 × 10⁻¹, below the interior maxima, so the maximum is not a boundary
artefact. Zero pixels pass CPR > 1 and DOP < 0.13 in either pipeline. sin θ is
common to both channels and cancels algebraically; everything in the table is
float32 round-off through the boxcar, and the median is five orders below the
maximum.

## 13 · Literature screen, reproducibility, and the one primary source not reached

### 13.1 The literature screen, rebuilt

`backend/scripts/literature_screen.py` reads `docs/literature_search_record.csv`
(unchanged; G29 asserts its counts) and writes `docs/literature_screen.json`
and `docs/literature_screen.md` with, per record, `access` ∈ {full_text,
abstract_only, inaccessible} and the four claims measured_ENL_reported,
critical_value_reported, exceedance_rate_reported, ratio_bias_corrected ∈
{yes, no, not_found_in_accessible_material, not_assessed}. Of the 34 unique
records 25 are relevant; on re-screening the abstract-only records on
2026-09-16 (every URL and outcome recorded) full text was obtained for two
(Raney et al. 2012 LPSC 2676; the EGU2020-11285 abstract, which is the whole
item) and not for twelve (publisher 403s, one unresolvable host, a rate-limited
index). Access on the relevant set is now 14 full text, 11 abstract only, 0
inaccessible — the manuscript's sentence "full text for 12, abstracts for 12,
one not accessible" is the original screen and is reported for correction.
`spudis2013.measured_ENL_reported = yes` with the quotation "effective number
of looks of about 6.7 … as opposed to the planned 8 looks" (para. [13]),
attributed there to unpublished analysis. No record reports a critical value,
an exceedance rate, or a ratio bias correction; `ratio_bias_corrected` is
`not_assessed` for the twelve cited full texts, which the original screen did
not examine for it.

### 13.2 Reproducibility manifest

`docs/REPRODUCIBILITY.md`: one section per row of the reviewer's table —
products with SHA-256 (both acquisitions and the SLC), commit, licence,
environment (`requirements-analysis.txt`), the DN→σ⁰ equation and order, masks,
georeferencing, filter kernel and boundary rules, ENL patch and bootstrap
parameters, sub-band FFT parameters, simulation covariances and seeds, the S₃
sign convention as a documented parameter, hypotheses and sidedness, literature
queries, and the command behind each table and figure.

### 13.3 Fa & Cai (2013): the data section could not be read

The manuscript attributes the 14.8 m product to the Mini-RF S-band zoom mode
(8 looks) on the strength of Raney et al. 2012 and the PDS catalogue, not on
Fa & Cai's own text. P10 asked for their data section verbatim. From this
host the full text was not reachable (Wiley 403 on the article and the PDF,
ADS 405, Semantic Scholar with no open-access copy, Crossref with the abstract
only), and the abstract names no product level, spacing, mode or look count.
`docs/published_moments.json::mode_verification` records every attempt, the
two abstract sentences that were reached, and that the discrepancy check
**could not be performed** — the attribution stands unverified against its
primary source until the author reads Section 2 from an institutional copy.

**A correction in the artifact, dated 2026-09-16.** `published_moments.json`
carried the note *"Fa & Cai used the 14.8 m baseline CDR"*, and that was wrong:
the Mini-RF baseline mode images at **150 m** (16 looks), so a 14.8 m product
cannot be a baseline product. The zoom mode is **7.5 m at 8 looks** (Raney et
al. 2012, para. [4]) and its calibrated data record is the 14.8 m one. The
earlier note would have compared the inverted N = 8.75–9.17 against the wrong
nominal count. The artifact now carries a `mode_table` with each figure's
source, and the superseded note under `mode_table.superseded` rather than
deleted. The same block records the **6.7** effective looks Spudis et al. (2013,
para. [13]) report for that mode, attributed there to unpublished analysis —
which is the one measured look count found anywhere in the 25 records screened
(§13.1), and the exception every absence claim in this document is scoped
around.

## 14 · Third review (2026-09-23): the repository's answers

The third review (M1–M16, C1–C16) was answered in the manuscript by rewording;
this section is what the repository computed so the response letter can point
at files. Each subsection names its artifact and its command. Nothing here
changes a sentence the paper prints; where an artifact disagrees with a printed
figure the disagreement is stated, not resolved.

### 14.1 The incidence factor is applied once (M3)

`python backend/scripts/calibration_example.py` → `docs/calibration_example.json`.
The production code multiplies DN² by sin θ_inc once, before the boxcar
(`process_real_sar_pipeline.py:409-412`). Because a spatially varying weight
does not commute with a boxcar, zero, one and two applications give different
stored fields, so the stored rasters were recomputed from the raw DN under
each: one application reproduces `cpr_native.tif` to 2.9 × 10⁻⁸ (maximum
absolute) and `s0_real.tif` to 3.3 × 10⁻⁷ (maximum relative); zero and two
applications miss by 1.3 × 10⁻² and 3.1 × 10⁻² in CPR_a. Every other sin θ in
the tracked code is classified (ablations that apply it zero or one time, and
label-θ uses that cancel in ratios). The label declares no normalization — no
σ⁰/β⁰/γ⁰ or normalization field — and whether ISRO normalized before writing
the DN cannot be separated from terrain's own incidence dependence in the data;
that is recorded as not decidable.

Worked example, median LH DN 542 over the 2 337 086 amplitude pixels, label
θ = 19.997919°, K_dB = 70.308868 → K = 1.073710 × 10⁷, G_LH = 1.018442: the
amplitude reading gives σ⁰ = −20.29 dB without G and −20.45 dB with it; the
intensity reading −47.63 / −47.79 dB; NESZ −31.53 dB. **The manuscript's
−20.3 and −47.6 dB are reproduced only without the gain G** — its own
calibration equation (III-A) includes G². The 0.16 dB changes neither margin to
the floor. One pixel through the full equation, with its own incidence-raster
value, is in `pixel_example`.

### 14.2 What the joint screen selects (M6)

`python backend/scripts/dop_sampling_bias.py` → `docs/dop_sampling_bias.json`
and `docs/joint_calibration.json`. For an unpolarized population the squared
sample DOP is Beta(3/2, N − 1): 1.398 / 7.060 / 12.449 / 26.367 % of cells read
below 0.13 at N = 5 / 14 / 21 / 38, and 4 × 10⁵ simulated cells per N give
1.410 / 7.052 / 12.480 / 26.384 % (each within one Monte Carlo SE; KS on m̂²
≤ 0.0026). The grid of population DOP {0, 0.05, 0.10, 0.13, 0.2, 0.3} × CPR
{0.7, 1.0, 1.1, 1.2, 1.299} × N {5, 14, 21, 38} is simulated only where a
covariance realizes the pair (DOP ≥ |q|): 19 of 30 pairs, 76 cells, 10⁵ trials
each. Two readings. The gate is insensitive: a population sitting exactly at
DOP 0.13 passes it 5.7 % of the time at N = 14, and an unpolarized one 7.1 %,
so the 1.50 % of Sec. III-E is a screen frequency dominated by which cells the
estimator's upward bias lets through. And no jointly selected cell ever
exceeds the one-sided critical value (0 of 76 cells, as the sample identity
requires below N ≈ 80). At CPR 0.7 (DOP ≥ 0.176) the joint selection is 1.61 %
at DOP 0.2 and N = 14 — the manuscript's "about 1.8 %" at DOP 0.1765.

### 14.3 The SLC control's processor, and its spectrum (M9)

`python backend/scripts/mechanism_spec.py` → `docs/mechanism_spec.json`.
Specification, read from the control's code: azimuth FFT of the whole window
(8400 lines, no zero-padding, azimuth mean removed, circular); occupied band =
PSD > 0.05 of its maximum; 21 non-overlapping rectangular sub-bands of 128 bins
over a 2708-bin band centred on the measured Doppler centroid; no taper in the
headline arm; each arm decimated by 21 onto one grid (no registration needed);
equal-weight intensity averaging with no per-band equalization; range bins
kept where > 99.9 % of lines are non-zero; ACF with a 33 × 33 reflect local
mean; matched resolution by a 1-D Gaussian (reflect). Two new numbers:

* **Expected looks from the measured spectrum.** The participation ratio of
  the 21 × 21 covariance of consecutive samples, from each window's measured
  azimuth spectrum, is 7.13 (6.88–7.20 over nine windows), against 7.34 for a
  rectangular spectrum of the same support and 4.52 measured on the spatial
  arm.
* **Residual cross-band correlation.** Adjacent sub-band looks' intensity
  fluctuations correlate at +0.19 (median; 0.13–0.42) against +0.02 for bands
  ten apart; the local baseband complex coherence is 0.42 adjacent against 0.32
  distant (the 5 × 5 estimator's floor). The sub-band powers are far from equal
  (CV 0.80; equal-power ENL 12.8 of 21). Both lower the sub-band arm below 21
  looks without any appeal to terrain.

### 14.4 The second acquisition, full suite (M14)

`python backend/scripts/enl_generality_full.py` → `docs/enl_L_20200305_full.json`
(read in place from `data/generality/`, not ingested). Label: L band, 39
azimuth looks of 27.43 Hz, PRF 3107.60 Hz, pulse bandwidth 2 MHz (7.5 MHz on
2020-08-08), slant-range resolution 74.9 m, 90 m output, K 70.308868 dB (sri) /
80.0 dB (sli), incidence 26.0°. SLC on disk, layout confirmed against the
label (330 044 × 128 complex, offset 2 673 220). Delivered product: 86 357
amplitude pixels, 197 16 × 16 and 14 32 × 32 patches; ENL 2.28 / 2.21 at 16 px
(the figures the manuscript prints), 1.38 / 0.22 at 32 px (14 patches: the mode
of 14 values over 120 bins is not an estimate and is recorded, not used);
row-block bootstrap 1.60–7.02 (LH); boxcar gain 7.66 against 2.35 on
2020-08-08; intensity lag-one 0.715 azimuth, 0.744 range. The benchmark at
these lags gives the same +16–18 % mode bias and 7–16 % block coverage.

**Where the looks are lost.** On the pass's own SLC, 39-line averages measure
ENL 6.25 (median of nine windows; 2.77–10.00), sub-band averages 11.85, and the
participation ratio of the measured spectrum is 13.75 — the reference the label
predicts. So the spectrum delivers what the oversampling relation says; the
39-line average on these (textured: single-look ENL 0.43–1.07) windows attains
0.47 of it; the delivered product attains 0.17. About half the shortfall is
at the multilook on this terrain, the rest after it.

**The three candidate causes.** (i) Output spacing against resolution: in
GROUND range the 90 m pixel spans 0.96 resolution cells (1.81 along track,
0.53 across; 0.40 on 2020-08-08, 0.94 × 0.43) — at or below one cell in both
products, so resampling cannot add looks in either; along track the 2020-03-05
grid spans 1.81 azimuth cells per pixel, and the delivered ENL falling BELOW
the SLC's 39-line average (ratio 0.36) says those cells are not averaged; the
higher boxcar gain (7.66 against 2.35) and lower azimuth lag-one on 2020-03-05
are what a less-oversampled grid does. (ii) Pulse bandwidth sets the range
resolution (74.9 m slant against 20.0 m) and enters only through (i). (iii) Lag
correlation biases the mode estimator HIGH, by the same +16–18 % at both
products' lags; it cannot remove looks. None of the three accounts for the
delivered product falling from 6.25 to 2.28, which the label does not explain;
with two acquisitions none is tested statistically. (The first version of this
calculation compared the label's SLANT across-track resolution with a GROUND
spacing; corrected before it was reported.)

### 14.5 Does any ENL interval cover the ENL? (M8)

`python backend/scripts/enl_interval_validation.py` → `docs/enl_interval_validation.json`
(4804 s on four workers, root seed 20260925). On the benchmark's own synthetic
scenes (1024 × 512, the product's intensity lag-one 0.838 / 0.576, the
production mode estimator), 150 test scenes per configuration, N = 5, 14, 21,
38, texture off and on (order 8), patches 16 and 32 px. Two procedures:

* **2-D block bootstrap**: non-overlapping 64 × 64 px blocks of the patch grid
  — at least three correlation lengths (5.67 px azimuth, 1.81 px range) in both
  axes — resampled whole, B = 200; percentile and basic intervals.
* **Parametric**, under the fitted correlated-speckle model: the estimator's
  sampling distribution simulated at 18 values of N (200 texture-free scenes
  each) and inverted (Neyman); the basic parametric bootstrap at the estimate
  beside it. The lag nuisance parameters are held at their generating values,
  an advantage to this method that is stated, not hidden.

| texture | procedure | coverage at nominal 95 % (range over N × patch) | at nominal 90 % |
|---|---|---|---|
| off | 2-D block, percentile | 19–26 % at 16 px; 98–100 % at 32 px | 9–99 % |
| off | 2-D block, basic | 41–67 % | 37–58 % |
| off | parametric, Neyman | 88–98 % | 81–92 % |
| off | parametric, basic | 90–99 % | 87–94 % |
| on (order 8) | every procedure | 0 % | 0 % |

The bootstrap fails at 16 px for the reason §7.3.2 found — it resamples an
estimate biased +15–16 % and cannot see the bias — and "covers" at 32 px only
because four patches per block leave so few blocks that the interval widens
past the bias. The model-based interval reaches near-nominal coverage when the
model is right. Under within-cell texture the mode reads 3–7 whatever the true
N and no speckle-only procedure covers it. The product's own evidence of
texture — the ENL falling with patch size, the 3.3–8.0 range over blocks —
means the model the parametric interval needs is not the product's, so the
manuscript's ranges stay labelled precision, not confidence. The estimator
specification the reviewer listed (stride, selection rule, ddof, bin count and
the realized bin width, ≈ 5 % in ENL at 16 px; retained patches 8337 / 1925 /
399 at 16 / 32 / 64 px; B) is complete in `docs/enl_estimator_spec.json`.

### 14.6 The F2 spatial null from complex fields (M13)

`python backend/scripts/f2_maximum.py` → `docs/f2_maximum.json::complex_field`.
§6.2a draws the CPR field as correlated F variates. The second model draws what
the CPR is formed from: L equal-weight looks per circular channel, each a
separable AR(1) complex field at the delivered product's intensity lag-one
0.838 / 0.576, channels independent; both set to zero outside F2's amplitude
mask (as the production boxcar sees them), 5 × 5 boxcar, then CPR over the
260 pixels; 10 000 trials per case, seed 20260926. The look count is matched
where CPR is formed: L = 4 gives a boxcar'd patch-mode ENL of 14.50 against
13.72 (L = 2, 3, 5, 6 give 7.9, 10.9, 21.7, 21.4). A separable AR(1) field
cannot also match the raw ENL — its boxcar gain is ≈ 3 against the product's
2.35 — so its raw ENL is 4.96 against 5.83. (A first run offered only L = 5, 6,
sat at N ≈ 21 and was superseded before it was reported.)

| model, true CPR | max over 260 px, median / p95 | FWE P(max > 1.895) | area > 1.895, mean | largest cluster > 1.895, p95 |
|---|---|---|---|---|
| correlated F, 0.7 | 1.911 / 2.729 | 51.9 ± 0.5 % | 1.50 | 4 px |
| complex field, 0.7 | 1.754 / 2.891 | 39.4 ± 0.5 % | 3.40 | 17 px |
| complex field, 1.00 (the test's null) | 2.510 / 4.114 | 86.3 ± 0.3 % | 20.2 | 49 px |

The crater-level family-wise error of a per-pixel 1.895 test over F2's 260
pixels is 86 % under the null it was built for. The two models agree that an
ice-free F2 at CPR 0.7 produces a nominally significant pixel in a large
fraction of realizations; they disagree on how large — 52 % against 39 % — and
the complex-field model puts the excursions into clusters (p95 17 pixels
against 4), because the boxcar correlates the channels' intensities before the
ratio, which the F copula does not. The manuscript's "about half" is the
correlated-F figure (`q_half_realizations`, checked against 0.519).

### 14.7 The Stokes-side answers (M7, M10, M11, M12)

In §1.11: circular coherence by gate, the two-channel tail models, the held-out
tail calibration, and the phase/gain perturbation of the screen.

## 15 · Council work order on v11 (2026-09-23): the analyses scored on

Each subsection names its artifact and command; every rate carries its Monte
Carlo standard error in the artifact, every simulation its seed. Where a result
bears against a v11 sentence it is said so here and flagged in the report.

### 15.1 The v11 audit (Task 0)

`python backend/scripts/audit_manuscript_numbers.py` against
`Claude outputs/grsl/dfsar_detection_limits_submission.tex` (v11) and its master:
328 PASS, 0 MISMATCH, 0 ABSENT, 4 NO SOURCE (the DERIVED closed forms) on both.
35 rows retired with their reasons (`RETIRED_V11`), about 70 added. The joint
rule's printed figures resolve to `joint_calibration.json::summaries` (size
3.575 / 6.20 / 13.27 % at N = 14 / 21 / 38; the in-band/null ratio 1.127 and
1.308 at the same DOP; the DOP gate's pass rates), the mean-sample-DOP crossings
to `dop_sampling_bias.json::mean_sample_dop_unpolarized` (0.13 at N = 75.09,
0.10 at 127.07, E[m̂] = B(2, N−1)/B(3/2, N−1)), the held-out figures to the new
`tail_calibration` keys (pooled 0.44 / 2.31 / 5.47 %, 13 / 11 / 11 blocks above
nominal, worst 7.1 / 12.4 %). The "20.3 and 22.5 %" of V-C is the F model at
the textured cells' PRINTED moment ENLs 11.2 and 9.3; at the unrounded 9.337
the second is 22.41 % (both in `detection_statistics.json::derived`).
`calibration_example.json` was regenerated with K = 10^(70.308868/10), G_LH =
1.018442, G_LV = 1.000923 and sin θ once: −20.45 dB (amplitude reading) and
−47.79 dB (intensity reading), which print as v11's −20.4 and −47.8, 11 and
16 dB from the −31.5 dB floor. The quantifier scan classifies all 45
quantified sentences (28 checked element-wise, 17 exempt with a reason); one
is flagged: "All results come from one pass" — Sections III-B and IV-C already
use the 2020-03-05 pass, and §15.5 replicates the Stokes analysis on it.
G32 was retargeted: v11 keeps only the V-A sentence "the critical value runs
from 2.07 to 1.64" over the bootstrap range 10.7–22.5, two cells.

### 15.2 The joint rule as a test across N (Task 1)

`python backend/scripts/dop_sampling_bias.py --curve` →
`docs/joint_power_curve.json` (seed 20261001, 10⁵ trials per cell, 16 look
counts from 5 to 200, 20 populations: four nulls at CPR 1.00, nine in the band,
seven ice-free; 2395 s). Three arms: (A) independent equal-weight looks; (B)
per-look gamma texture of shape 8 common to both channels; (C) looks correlated
at the product's azimuth lags — field correlations √0.838, √0.565, √0.363 at
lags 1–3, continued geometrically at their decay (truncation at lag 3 is not a
valid covariance), which makes N looks worth 1.5 (N = 5), 2.9 (14), 6.9 (38)
and 34.7 (200) independent ones.

* Size (max over the nulls of P(joint)): arm A 0.71 / 3.63 / 6.14 / 13.15 /
  33.19 % at N = 5 / 14 / 21 / 38 / 100; arm B 0.63 / 3.10 / 5.35 / 11.62 /
  30.51 %; arm C 0.05 / 0.29 / 0.53 / 1.27 / 4.93 %. The size first exceeds
  5 % at N = 19 (A), 21 (B) and 150 (C).
* In-band power stays within a factor of the size: at N = 14 the in-band
  selection is 2.87–3.60 % in arm A; the largest in-band/null ratio at the same
  DOP is 1.23 (CPR 1.299 at its minimum DOP), 1.45 at N = 38 and 1.80 at
  N = 100. Over CPR 1.1–1.2 alone the coarser grid of `joint_calibration.json`
  gives the 1.13 and 1.31 that v11 prints; including CPR 1.25 and 1.299 the
  ratio is larger.
* P(joint AND R > crit₉₅) is exactly 0 in every arm for every N below 79.6,
  as the sample identity requires; it first becomes non-zero at N = 80 (A, B;
  2 and 4 of 2 × 10⁶ draws) and N = 100 (C).
* Gate (G33): arm A at N = 14 gives 3.626 ± 0.059 %, against 3.575 % in
  `joint_calibration.json` (z = 0.86).

### 15.3 The look count at the selected cells (Task 2)

`python backend/scripts/enl_logratio.py` → `docs/enl_logratio.json`. Common
texture cancels in R = SC/OC, and for independent gamma channels
Var(ln R) = ψ₁(N_SC) + ψ₁(N_OC); with N_SC = N_OC = N, N solves 2ψ₁(N) =
Var(ln R). Validated first on synthetic fields at the product's lags (N = 5,
14, 21, 38, 80, 120; texture off and gamma texture of shape 8 shared by both
channels; 31 × 31 windows, 640 per configuration): the estimator reads
+3.4 to +5.0 % high at every N, texture or not, and a 95 % moving-block
bootstrap inside the window (10 × 10 px blocks, B = 200) covers the true N
66–72 % of the time — a precision statement, not a confidence interval.

On the complex product (first pass, physical sign), for each of the 26 462
joint-selected cells, N from Var(ln R) over the non-selected cells of its
31 × 31 neighbourhood: median 41.8 (IQR 23.0–55.0, p95 73.6); 709 selected
cells (2.68 %) have local N ≥ 79.6, and **2 have R above F⁻¹₀.₉₅(2N, 2N) at
their local N**. For 26 462 random non-selected cells: median 17.5 (IQR
9.8–31.5), 108 (0.41 %) at N ≥ 79.6, 10 above their local critical value. The
109 homogeneous 64 × 64 blocks give median 39.4 (IQR 28.5–46.0), against block
moment ENLs of 14.8 (SC) and 25.6 (OC): the ratio's own look count on
homogeneous terrain is roughly three times the 13.72 Section V uses, the
moment ENLs being depressed by texture that cancels in the ratio. Local γ_c at
the selected cells has median 0.077 per cell (0.136 as the window mean, the
same as for random cells); the Spearman correlation of local N with the window
coherence is 0.19 at selected cells and 0.10 at random ones, so coherence does
not explain the look count; across the 20 windows the DOP gate's pass rate
follows coherence (Spearman −0.88, `stokes_from_slc.json`). Biases: terrain
CPR variation in the window lowers N̂, channel correlation raises it. Second
pass: 24 selected cells, local N median 32.5, none at N ≥ 79.6.

### 15.4 The F2 null, per cell (Task 4)

`python backend/scripts/f2_maximum.py --only-v2` →
`docs/f2_maximum.json::complex_field_v2` (10⁴ trials, seed 20261003,
independent channels, 4 looks, production boxcar with zero-fill, the sample
DOP formed per cell from the boxcar'd covariance). Gate: the crater-level rate
at 1.895 is 85.2 ± 0.4 % against 86.3 ± 0.3 %, and the per-pixel rate
7.63 ± 0.08 % against 7.76 % — both within three combined standard errors.

* **The per-pixel excess is not an edge effect.** Cells whose 5 × 5 window
  holds all 25 valid pixels fire at 6.87 %; 20–24 valid, 7.28 %; 15–19, 8.04 %;
  10–14, 8.82 %; 1–9, 10.24 %. The fragmented mask raises the rate, but the
  interior already exceeds 5 %: the boxcar'd field's F-model N is not the
  mode-estimated 14.5 the looks were matched to.
* **Calibrated per-pixel threshold** (5 % per pixel on this mask): 2.087; its
  crater-level FWE is 75.2 ± 0.4 %.
* **Crater-level threshold** (5 % FWE at CPR 1.00): 4.117.
* **Sinha's joint rule on the same null** (CPR 1.00, DOP 0): selects at least
  one cell of the 260 in 88.2 ± 0.3 % of realizations and at least five in
  49.3 ± 0.5 % (mean 5.5 cells; per cell 2.1 %, DOP gate alone 4.2 %).

### 15.5 The second pass (Task 5)

`python backend/scripts/stokes_from_slc.py --product 20200305` →
`docs/stokes_from_slc_20200305.json` (and `phase_gain_perturbation_20200305.json`).
The same script, its geometry read from that pass's sli label (330 044 × 128
at offset 2 673 220) and its azimuth average from its sri label (39 looks);
896 972 matched cells. The invariants hold: Eq. (1)'s band at every cell at
both signs, the coupling band at every DOP < 0.13 cell, DOP² = q² +
γ_c²(1 − q²) to 5.6 × 10⁻¹⁶, no gated cell with γ_c ≥ 0.13. The physical sign
is again 180° (medians 6.87 and 0.146); the phase clusters at −89.4° with
resultant 0.990. The terrain is far more polarized: H–V coherence median 0.751
(0.658 on the first pass), DOP < 0.13 on 0.045 % of cells (406), the joint rule
on 0.0027 % (24), conditional rate 5.9 ± 1.2 %. γ_c median 0.068 inside the
gate, 0.148 outside. Moment ENLs N_SC 9.68, N_OC 17.50 (physical sign). The
20 lowest-CV 15 × 15 windows give tail ratios 0.98 (p95) and 0.94 (p99) to
unequal-look F. **No 64 × 64 block fits the 128-bin swath** (0 tiles wholly
inside the mask), so the held-out calibration cannot be run at the prescribed
size. At 32 × 32, a declared deviation (`--block 32`,
`docs/stokes_from_slc_20200305_block32.json`), 53 blocks give pooled held-out
rejection 1.31 / 4.08 / 7.95 % at nominal 1 / 5 / 10 %, with 15 / 16 / 12
blocks above nominal. The first pass at 32 × 32 (`stokes_from_slc_block32.json`,
501 blocks) gives 0.89 / 4.08 / 8.36 %: smaller blocks are less conservative on
both passes.

### 15.6 Intervals on the held-out calibration (Task 6)

`python backend/scripts/tail_calibration_ci.py` → `docs/tail_calibration_ci.json`.
Block bootstrap (B = 10⁴) on the first pass's 109 blocks: pooled rejection
0.44 % [0.29, 0.64], 2.31 % [1.92, 2.75], 5.47 % [4.90, 6.08] at nominal 1, 5,
10 %; medians over blocks 0.10 % [0.05, 0.20], 1.39 % [1.22, 2.03], 4.42 %
[4.10, 5.22]. Each block's effective count is its held-out cells over its own
integrated autocorrelation area of ln CPR (median area 67 px). Under exact
calibration the number of blocks above nominal is Poisson-binomial with
expectation 46.6 / 48.7 / 50.7; the observed 13 / 11 / 11 have p ≤ 10⁻¹² in the
lower tail: **11 of 109 at 5 % is not consistent with exact calibration — it
is far too few, the model is conservative on these blocks.** At 32 × 32 the
1 % tail turns anti-conservative on both passes (144 of 501 above nominal
against 103.7 expected, p = 9 × 10⁻⁶; 15 of 53 against 8.8, p = 0.021), while
the 5 and 10 % tails stay conservative or consistent.

### 15.7 Figures (Task 7)

`cd paper && python make_figures_council.py` (kept apart from
`make_figures.py`, which is byte-identical to the manuscript's copy; G26 now
builds and inspects both). `fig_cpr_dop.pdf`: the log density of the sample
(DOP, CPR) over all 5 883 594 cells (`paper/fig_cpr_dop_density.npz`, written by
`stokes_from_slc.py`), with the coupling curve, DOP = 0.13, CPR = 1, 1.2989 and
1.895. `fig_joint_power.pdf`: Task 1's size and maximum in-band power against
N for the three arms.

### 15.8 A calibrated replacement rule (Task 3)

`python backend/scripts/decision_rule.py` → `docs/decision_rule.json` (seed
20261002; 2 × 10⁴ tested cells and a 4 × 10⁴-cell window pool per population;
the q₀.₀₅ table from 2 × 10⁵ draws at each of 36 look counts). (a) CPR test:
R > F⁻¹₀.₉₅(2N̂, 2N̂), N̂ from Var(ln R) over a window of W cells of the same
population — W = 960 (a 31 × 31 window of independent cells) and W = 16 (the
product's 61.42 px per independent sample). (b) DOP test: m̂ below the 5 %
quantile of its law at population DOP 0.13 (0.1238 at N = 14, 0.0850 at 38,
0.0713 at 100); the law depends on the population only through its DOP.
(c) Intersection–union of the two.

* Plug-in inflation of (a), arm A: size 4.98 / 5.27 / 5.17 % with the true N,
  5.11 / 5.32 / 5.25 % with W = 960, 6.21 / 6.39 / 6.50 % with W = 16, at
  N = 14 / 38 / 100. In arm C the nominal N badly overstates the looks and the
  oracle test's size is 22–25 %; the plug-in's 6.3 % corrects it.
* (b) has size 5.3 % (A) and power at DOP 0 of 6.2 / 9.5 / 20.4 % at
  N = 14 / 38 / 100: the gate barely separates DOP 0 from DOP 0.13 below N ~ 40.
* (c) has size and power **0.00 %** at N = 14 and 38 in every arm, and 0.01 % at
  N = 100: m̂ below its 5 % quantile at DOP 0.13 implies R < 1.2989 by the
  sample identity, below the critical value whenever N < 80. A calibrated joint
  test of "CPR > 1 and DOP < 0.13" cannot reject at these look counts.
* On the complex product it selects **0** of 5 883 594 cells on the first pass
  (the plug-in CPR test alone rejects 3 703, the DOP test alone 66 025; Sinha's
  rule 26 462) and 0 of 896 972 on the second (0; 593; 24). Local N̂ over the
  frame: median 17.4 (first pass), 21.0 (second).

## 16 · Final pass on v14 (2026-09-23)

The v14 work order (`Claude outputs/hygiene/CLAUDE_CODE_V14_TO_9.md`): figure
sync and re-audit (A), six analyses (B). Every artifact records its seed or
states that it draws none, its generator and `run_info`; every simulated rate
carries its Monte Carlo standard error. Where a result bears on a v14 sentence
it is said so here and flagged in the report.

### 16.1 Figures and the v14 audit (A1, A2)

`paper/make_figures.py` is the grsl copy (Fig. 1 labels now
$\mathrm{DOP}_a<0.13$); `paper/make_figures_v12.py` is the grsl `v12fig` copy
with its hard-coded `/mnt/user-data/...` path replaced by the repository's
`docs/` and the Neyman–Pearson bound added to Fig. 3. G26 builds both and
checks exactly `fig1_degeneracy.pdf`, `fig_cpr_dop.pdf`, `fig_joint_power.pdf`;
`fig3_detection.pdf` is retired from the gate (v14 replaced it).

The strict band of `joint_power_curve.json` — in-band populations with
population DOP < 0.13 only — is now a stored key
(`python backend/scripts/dop_sampling_bias.py --strict-summary`, recomputed from
the stored cells, no draws): arm A 3.496–3.598 % at N = 14 against a size of
3.626 %, 12.784–14.264 % at N = 38 against 13.153 %, largest excess over CPR 1.00
at the same DOP 40.8 %; the texture arm's size is within two standard errors of
5 % from N = 20 and above it from N = 21.

The audit (`audit_manuscript_numbers.py`, submission and master): 381 PASS,
0 MISMATCH, 0 ABSENT, 4 NO SOURCE (the DERIVED closed forms). 32 rows retired
with reasons (`RETIRED_V14`), among them `tex_f_4`, whose "22.5" had been passing
on IV-B's unrelated bootstrap range "10.7--22.5"; 85 rows added for the v14
literals, four DERIVED closed forms (1.452 and 5.8 % at N = 39.4, 0.053, 79.6),
eight quantified rows. The quantifier scan: 48 quantified sentences, 29
checked element-wise, 19 exempt with a reason, 0 unchecked; the flagged v11
sentence "All results come from one pass" is gone from v14. The texture
oracle's lower figure is a tie: 1190 of 20 000 = 5.95 %, printed 5.9 (the stored
float reads 5.9499…). G32 was retargeted: v14 removed the bootstrap-range
sentence, and the gate now recomputes V-A's four closed-form cells (the
critical value and the 0.7-background exceedance at N = 13.72 and 39.4).

### 16.2 N̂ at the IUT onset (B1)

`decision_rule.py`'s `apply_to_product` adds the maximum and 99th percentile of
the frame-wide N̂ (31 × 31 windows) and the counts at 79.6, 218 and 254, over all
cells and over the cells the published rule selects; `iut_onset` records the
q₀.₀₅ grid bracket (218, 254). First pass: max 137.2, p99 70.1; 18 342 cells
≥ 79.6, 0 ≥ 218; among the rule's 26 462 cells, 573 ≥ 79.6, max 105.9, p99 84.6.
Second pass: max **229.3**, p99 86.0; 14 827 ≥ 79.6, **3 ≥ 218**, 0 ≥ 254; the
rule's 24 cells all below 38.1. Every existing row of the artifact reproduces
draw for draw.

### 16.3 The F2 null at the complex product's look count, and on ice-free terrain (B2)

`python backend/scripts/f2_maximum.py --only-v3` →
`f2_maximum.json::complex_field_v3` (seed 20261006, 10⁴ trials per run, 20
runs). Same 260-pixel mask, zero-fill and 5 × 5 boxcar as v2. Per look,
OC = √b w_OC and SC = √a (γ_c w_OC + √(1 − γ_c²) w_SC), a = CPR/(1+CPR),
b = 1/(1+CPR), γ_c from DOP² = q² + γ_c²(1 − q²); w are separable AR(1)
complex fields, now exactly stationary (the first row and column are the
innovation; v1/v2 discarded 64 burn-in samples, a 0.3 % transient). Two lag
sets: the delivered LH's (0.838 / 0.576, both channels) and the complex
product's SC / OC before the boxcar (0.579 / 0.625, 0.738 / 0.769;
`complex_grid_correlation.json`). Looks per channel from the boxcar'd
patch-mode ENL on 3 × (1024 × 512) fields per L (L = 2–16); the delivered-lag
arm at 13.72 is pinned to v2's L = 4 so it is v2's model. The calibration reads
L = 4 as **15.98** (15.04 with the complex lags) and L = 3 as 11.54, against the
first run's 14.50 (whose three fields read 14.03–15.18). The estimator is
noisy field to field — the v3 curve is not even monotone above L = 12 (48.5,
49.2, 49.1, 62.3, 58.6) — so the printed "14.5 against 13.72" is one draw of
it, and the L = 4 field is more likely near 15–16. Near 39: L = 11 → 40.54 (delivered lags), L = 10 → 38.00 (complex).

Delivered lags, rates over 10⁴ realizations (SE ≤ 0.5 points):

| population | ENL | joint ≥ 1 cell | ≥ 5 | mean cells | CPR-only ≥ 1 px at crit(ENL) | at 1.895 |
|---|---|---|---|---|---|---|
| null CPR 1.00, DOP 0 | 16.0 (L 4) | 87.9 % | 48.9 % | 5.5 | 89.9 % (1.805) | 86.0 % |
| null CPR 1.00, DOP 0 | 40.5 (L 11) | **99.1 %** | 94.2 % | 22.3 | 88.1 % (1.444) | 31.1 % |
| CPR 0.7, DOP 0.176 | 16.0 | 72.8 % | 30.2 % | 3.5 | 46.6 % | 39.5 % |
| CPR 0.7, DOP 0.176 | 40.5 | 71.7 % | 45.6 % | 6.6 | 17.1 % | 1.2 % |
| CPR 0.7, DOP 0.20 | 16.0 | 68.6 % | 27.3 % | 3.2 | 45.4 % | 39.0 % |
| CPR 0.7, DOP 0.20 | 40.5 | 65.7 % | 38.7 % | 5.3 | 16.9 % | 1.0 % |
| CPR 0.9, DOP 0.053 | 16.0 | 85.8 % | 45.7 % | 5.1 | 80.3 % | 75.0 % |
| CPR 0.9, DOP 0.053 | 40.5 | 97.2 % | 87.8 % | 18.5 | 68.7 % | 15.1 % |
| CPR 0.9, DOP 0.20 | 16.0 | 74.2 % | 31.3 % | 3.7 | 79.0 % | 73.0 % |
| CPR 0.9, DOP 0.20 | 40.5 | 79.9 % | 54.4 % | 8.0 | 67.7 % | 13.6 % |

With the complex product's SC / OC lags every joint-rule rate is 1–6 points
higher (null 91.4 % at L 4, 99.2 % at L 10; CPR 0.7 DOP 0.20 74.5 / 69.0 %). The
delivered-lag null at L = 4 reproduces v2 (87.9 against 88.2 %, 86.0 against
85.2 % at 1.895; G33). V-C's "at a higher count the CPR-only rate at 1.895 falls
and the joint rule's rises" holds: 86.0 → 31.1 % and 87.9 → 99.1 %.

### 16.4 An upper bound on any level-5 % per-cell test (B3)

`python backend/scripts/np_power_bound.py` → `docs/np_power_bound.json` (exact;
Monte Carlo check seed 20261005). Any level-5 % test of H0 = {CPR ≤ 1} ∪
{DOP ≥ 0.13} is level 5 % against every simple Σ0 in H0, so its power at an
alternative Σ1 is at most the Neyman–Pearson power of Σ0 against Σ1, for every
Σ0: the minimum over any subset of the null is a valid bound. The NP statistic
tr((Σ0⁻¹ − Σ1⁻¹)S) of an N-look complex Wishart is λ₁X + λ₂Y, X, Y independent
Gamma(N, 1/N), λ the eigenvalues of AΣ (true for real N); its tails are computed
by Gauss–Legendre quadrature (64 nodes in the search, 256 final, 1024 as a check,
agreement ≤ 0.001 points), the null quantile by safeguarded Newton to 1e-10.
Grids: 838 alternatives (CPR 1.005–1.295 step 0.01; DOP from |q| to 0.1299
step 0.005; phase 0 and 90°; plus decision_rule.json's four in-band
populations); null boundary CPR = 1 at DOP 0–0.13 and DOP = 0.13 at CPR
1–1.2989, all phases — 360 coarse points, then six zoom rounds from the two best
per segment; the final bound at every N is the minimum over the union of the
nulls found at all N.

| N | 14 | 21 | 39.4 | 80 | 218 | 500 |
|---|---|---|---|---|---|---|
| bound (%) | 9.72 | 11.06 | 14.17 | 20.17 | 37.59 | 64.12 |
| MC check (%) | 9.70 ± 0.05 | 11.10 ± 0.07 | 14.22 ± 0.06 | 20.19 ± 0.10 | 37.55 ± 0.05 | 64.04 ± 0.09 |

Every N is maximized at CPR 1.145, DOP 0.068 (γ_c = 0, phase-free) and
limited by the diagonal null at the band's corner (CPR 1.2989, DOP 0.13;
at N = 2 by CPR 1.00, DOP 0): the alternative sits between two unpolarized
nulls. Lower than the sketch's 12 / 20 / 31 / 60 / 89 % because the search
reaches the corner, which the sketch never tried. Gates: ≥ 5 % at all 16 N,
non-decreasing in N, above every calibrated-IUT power in decision_rule.json —
PASS (G33 re-checks all three and the MC agreement). Fig. 3 draws it as a thin
curve. Above N ≈ 40 the joint rule's in-band rate exceeds the bound: it can,
because its size is 13 % at N = 38 and rising — it is not a level-5 % test.

### 16.5 The spectral ceiling on N for one complex-product cell (B4)

`python backend/scripts/complex_grid.py` → `docs/complex_cell_ceiling.json` (no
draws). A complex-product cell is the equal-weight intensity average of 105
azimuth × 5 range SLC samples (21 lines, then the 5 × 5 boxcar). Its ENL under
circular-Gaussian speckle is the participation ratio of their 525 × 525
covariance, built from each window's measured 2-D autocovariance (zero-padded,
overlap-normalized) in mechanism_spec.py's nine windows. LH: median **69.7**,
range 67.3–86.1; LV 69.9, SC 71.0 (69.0–122.7; window 0's weak SC channel is
noise-flattened), OC 69.6. Check: the 21 × 1 ratio is 7.132 against
mechanism_spec's 7.134. The ceiling is below 79.6 in the median and in seven of
nine windows (80.2 and 86.1 in the other two); the block log-ratio 39.4 is 57 %
of it.

### 16.6 The correlation area on the complex grid, and W (B5)

Same run → `docs/complex_grid_correlation.json`. The Stokes CPR (physical sign)
after the boxcar, over the 109 homogeneous 64 × 64 blocks, with
cpr_significance.py's estimator: A = **99.6 px** median (IQR 49.3–207.6), 155.6
from the block-pooled ACF, against 61.42 on the delivered grid. A 31 × 31 window
on the complex grid therefore holds 961 / 99.6 = 9.6 independent samples;
decision_rule.py adds `plugin_Wcomplex` with W = 10 (its own generator, seed
20261007). Arm A: CPR-component size 6.77 / 6.97 / 7.08 % and IUT size 0.000 /
0.005 / 0.070 % (± 0.019) at N = 14 / 38 / 100, against W = 16's 6.21 / 6.39 /
6.50 % and 0.015 %. Before the boxcar the complex product's SC and OC intensity
lag-one correlations are 0.579 / 0.625 and 0.738 / 0.769 (azimuth / range),
against the delivered LH's 0.838 / 0.576.

### 16.7 The random cells like for like (B6)

`python backend/scripts/enl_logratio.py --only-random` →
`enl_logratio.json::random_like_for_like` (the same random draw, seed
20260931). product() already dropped every selected cell from every window;
a selected cell was also absent from its own window and a random cell was not.
Dropping the random cells too, so every tested cell is estimated from
neighbours only: first pass median **17.5** (IQR 9.8–31.5; 107 ≥ 79.6), against
17.5 before and 41.8 at the selected cells; second pass 22.6 (11.9–36.8) against
32.5. The gap between selected and random cells is not the exclusion mask.

<!-- BEGIN GENERATED STAMP -- do not edit by hand -->

## Provenance of the numbers in this document

Every measured figure quoted above is transcribed from an artifact on
disk. Those artifacts are digested here, so that a figure which has gone
stale is **detectable** rather than merely wrong —
`python backend/scripts/stamp_methods.py --check` fails the build when an
artifact has moved since this stamp was written, and names the sections
that were read from it.

**What this does not do.** It does not verify that any individual digit
was transcribed correctly; only generation could do that, and generating
this document would mean templating the prose that carries its reasoning.
It catches the failure that has actually occurred here — an artifact
changing underneath text that still quotes the old numbers.

Stamped at commit `70db1a9`.

| artifact | sha256 | sections |
|---|---|---|
| `data/pradan/lola/horizon_240m.provenance.json` | `f84a64b1ae849b27…` | §5.4, §5.6, §8.4 |
| `data/pradan/lola/ldem_frame_25m.provenance.json` | `3cca8d4243ef625b…` | §8.1, §8.2, §8.4 |
| `docs/antialias_sigma.json` | `f6a2ee114aaf9a56…` | §8.1 |
| `docs/bootstrap_enl.json` | `5f4239f07f372c3f…` | §7.3.1 |
| `docs/calibration_example.json` | `5f0753e6e92fd192…` | §14.1 |
| `docs/complex_cell_ceiling.json` | `4f0f922c67d0768c…` | §16.5 |
| `docs/complex_grid_correlation.json` | `c49e76f838772719…` | §16.3, §16.6 |
| `docs/composite_contrast.json` | `994f951f2a1acd84…` | §8.7 |
| `docs/cpr_dispersion.json` | `b966a379b1af3cba…` | §7.10 |
| `docs/cpr_significance.json` | `1343f1198d3c67bf…` | §7.7, §7.9.1, §7.9.2, §7.9.3, §7.9.4 |
| `docs/decision_rule.json` | `19cc84e41695299c…` | §15.8, §16.2, §16.6 |
| `docs/degeneracy_replication.json` | `5af23a79e703e7a9…` | §1.10 |
| `docs/detection_statistics.json` | `16707f02b03be20c…` | §11.1, §11.2, §11.3 |
| `docs/dop_sampling_bias.json` | `14f3432c0344881e…` | §14.2 |
| `docs/enl.json` | `6057bd5d8ae62908…` | §7.1, §7.3, §7.5, §7.6 |
| `docs/enl_L_20200305_full.json` | `bf7bc6f1bdf4219a…` | §14.4 |
| `docs/enl_benchmark.json` | `aad47ad4c52def4c…` | §7.3.2 |
| `docs/enl_estimator_spec.json` | `95577a403a4d57be…` | §7.3.1 |
| `docs/enl_generality.json` | `3c9ae9ed9dc17e7e…` | §7.4a |
| `docs/enl_interval_validation.json` | `ad9514471b8885a6…` | §14.5 |
| `docs/enl_logratio.json` | `aa4d23a9aef3f878…` | §15.3, §16.7 |
| `docs/enl_predictions.json` | `a593830d7c84b2de…` | §7.4a |
| `docs/f2_footprint.json` | `281c9b86e0687432…` | §6.2 |
| `docs/f2_maximum.json` | `f4f9b96de7c5861f…` | §6.2a, §14.6, §15.4, §16.3 |
| `docs/incidence_audit.json` | `f52bab447a3666c5…` | §7.12, §12.1, §12.2, §12.3, §12.4, §12.5 |
| `docs/incidence_mask.json` | `ffb5684f97010a7b…` | §7.11, §7.12 |
| `docs/joint_calibration.json` | `69091c8284d96fb1…` | §14.2, §15.1 |
| `docs/joint_criterion.json` | `984eb95dc9497a0d…` | §7.9.4 |
| `docs/joint_power_curve.json` | `3d878a38901d6e12…` | §15.2, §15.7, §16.1 |
| `docs/kclutter.json` | `ae285515e3abdb5d…` | §7.13 |
| `docs/kclutter_within_cell.json` | `93d4c0a800dd55be…` | §7.13 |
| `docs/landing_sites.json` | `68b77ca3e47eeefc…` | §9.6, §9.7 |
| `docs/literature_screen.json` | `d5ff73f7ec44aea2…` | §13.1 |
| `docs/mechanism_controls.json` | `97df12ec0c5ae7d8…` | §7.4b |
| `docs/mechanism_spec.json` | `14bc6ef44f9ff8e2…` | §14.3 |
| `docs/np_power_bound.json` | `13a8fc0a9d84b453…` | §16.4 |
| `docs/patch_bias.json` | `db2b73ce9b8a1ecc…` | §7.3.3 |
| `docs/phase_gain_perturbation.json` | `07604f8f0c4c864e…` | §1.11 |
| `docs/propagation_percentiles.json` | `847af0a883190b4b…` | §12.6 |
| `docs/psr_domains.json` | `72855458be8227eb…` | §5.8, §5.9, §5.11 |
| `docs/psr_validation.json` | `b06134ce627dfb2d…` | §5.10 |
| `docs/published_moments.json` | `5bfe5549f64bc236…` | §13.3 |
| `docs/roughness_vs_latitude.json` | `ace9c0c9c9999d96…` | §9.1, §9.2 |
| `docs/rover_coverage.json` | `45e2b31fed3a7cf8…` | §6.5 |
| `docs/site_inspection.json` | `817b7a32b75980be…` | §9.3 |
| `docs/slc_multilook_control.json` | `0e4ba7a5f41a97ce…` | §7.4 |
| `docs/solar_model_ab.json` | `c8c57b02601626d1…` | §5.3, §5.10 |
| `docs/stationarity.json` | `4d72eb5cd1877932…` | §7.3.3 |
| `docs/stokes_from_slc.json` | `cf47bccb7fa4c245…` | §1.11, §14.7, §15.7 |
| `docs/stokes_from_slc_20200305.json` | `e5eca2c112a2a157…` | §15.5 |
| `docs/stokes_from_slc_20200305_block32.json` | `a3b893d7f7c5399d…` | §15.5 |
| `docs/stokes_from_slc_block32.json` | `453a44d7e23d5df6…` | §15.5 |
| `docs/tail_calibration_ci.json` | `bfa7f5c6402bcaf9…` | §15.6 |
| `docs/traverse.json` | `6df4a099ee59aaab…` | §10.1, §10.2, §10.3, §10.4, §10.5 |
| `frontend/public/analysis/faustini.json` | `e8c813e3648ebc2e…` | §1.4, §8.2, §8.3 |
| `frontend/public/analysis/probe_grid.json` | `848f0884f29b79ed…` | §11.5 |
| `frontend/public/analysis/sweep_grid.json` | `a6c22dbcf875dad5…` | §1.9 |

<!-- END GENERATED STAMP -->
