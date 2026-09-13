# Viva rehearsal

*Four questions, four written answers. Written down rather than improvised,
because the first three are predictable and the fourth is the one that matters.
Every number below is checkable in this repository.*

---

## 1. "You didn't find any ice."

**Correct. The candidate area is 0.0000 km², with a 95 % confidence interval of
[0.0000, 0.147] km² on 38 051 effective samples. And I can prove that number
could not have been anything
else.**

Three things, in order.

**The measured distribution.** Peak CPR anywhere in the swath is **0.0534**,
against a threshold of 1.00. Not close — short by a factor of 19. Median DOP is
0.0475 against a threshold of 0.13.

**The algebraic reason, which is not empirical.** With CPR derived from amplitude
alone, write `x = ln(LH/LV)`. Then

```
CPR_amp = tanh²(x/4)        DOP_amp = |tanh(x/2)|
```

Both are monotone functions of the **same single variable**, so
`CPR_amp = tanh²(artanh(DOP_amp)/2)` — one degree of freedom, not two. The
screening rule is `CPR > 1.00 AND DOP < 0.13`, which is one condition pushing
`|x|` up and another pushing it down on the same axis. `DOP < 0.13` therefore
*caps* CPR at **0.0042610**. **No pixel satisfying the DOP criterion can exhibit
CPR above 0.00426, whatever the terrain, whatever the instrument.** The screen is
empty by construction, 235× below the configured threshold. Verified across all
2,337,086 measured pixels: max residual 1.24 × 10⁻⁶, r = 0.999999999994.

**The Monte Carlo, which is stronger.** The algebra bounds the magnitude under
the DOP gate. Simulation bounds the *information*: at equal channel powers the
proxy's population value is **exactly zero for every value of CPR**. Across a
true CPR range of 0.30 → 1.50 its median moves **0.00043**; add 3 dB of channel
imbalance at unchanged CPR and it moves by a factor of **68**. It is not a weak
estimator of CPR — it is not an estimator of CPR at all, because CPR lives in the
H–V phase and taking magnitudes discards it.

**What would change the answer.** The Stokes S3 phase term, from the complex
`sli` products which are on disk but not ingested. With the true Stokes vector,
`CPR = (S0 − S3)/(S0 + S3)` and `DOP = √(S1²+S2²+S3²)/S0` are built from
*different* combinations of four parameters and are genuinely independent, so
`high CPR AND low DOP` selects a real physical population instead of an empty
set. That is Phase 5b, and it is scoped.

**A measured null on an incomplete product is a result. A fabricated detection
would not have been.**

---

## 2. "This is trivial — it's a dashboard."

**Four things in it are not, and each is a measurement rather than a feature.**

**The horizon computation.** Permanent shadow is not a brightness threshold. For
every one of 360 azimuths, the maximum elevation angle of terrain along that ray
is computed across the full 2533² LOLA polar array, by an O(n) skyline scan
(Dozier & Frew 1990) verified against O(n²) brute force to **1.7 × 10⁻⁶**. The
Sun is modelled as a **finite disc**, because the product I validate against
models one. Result: **Jaccard 0.714, precision 0.772, recall 0.906** against the
LOLA team's own published PSR mask.

**Two pre-registrations were scored, and they are not the same one.** Both were
**committed to git before the sweep finished**, so the timestamps prove no result
existed when the predictions were written.

*Two pre-registrations were scored — the eight-row solar-disc A/B held **8 of 8**,
and the earlier **1.2–1.6×** band for the LPSR area ratio is recorded as **NOT A
HIT** at 1.174×, conservatively, since that band was written for the point-Sun
model it has since superseded (where it measured 1.301× and did fall inside) and
is arguably void rather than missed.*

This sentence used to read *"the eight-row prediction for that comparison … 8 of 8
held"*, which let the 8-of-8 be taken as the score for the band. The 8-of-8 is
true — it scores eight *directional* predictions about how each metric would move
when the finite disc replaced the point Sun, and all eight moved as predicted —
but it is not the band's score, and the band did not hit. METHODS §5.10 records
all three facts separately: the mechanism held, the numeric band was scored
against a model it was not written for, and the miss is recorded conservatively
rather than dismissed as void.

**A correction to the physics.** Solar elevation at the pole is not capped at
1.54°. That is a bound on the *subsolar latitude*; elevation at latitude φ
reaches `1.54° + (90° − |φ|)`, which is 6.71° at this frame's edge. Treating it as
constant under-illuminates the frame by up to 4.4×.

**The georeferencing.** Every raster is placed by parsing the PDS4 label and
inverting the polar stereographic projection, validated against ISRO's own grid
to **13.2 mm**. Not an image stretched onto a bounding box.

**The ENL control.** The delivered product declares 21 looks. I measured 5–6, then
built 21 looks *myself* from the single-look complex two different ways and got
**4.5** and **9.9** — so "21 looks" names a method, not a count. Along the way the
control validated itself: the measured azimuth bandwidth came out **1071.2 Hz**
against the label's declared **1071.336 Hz**, in 9 windows out of 9.

**And the search.** Landing sites are the argmax of a six-criterion search over
all **14,943,444** native 25 m pixels — not five hardcoded grid offsets, which is
what this project had before and which all fell outside the measured radar
ribbon.

---

## 3. "How do I know any of these numbers are real?"

**Because the build fails if they aren't, and I can show you it failing.**

**Every value carries a mark** — `MEASURED`, `DERIVED` or `NO DATA` — and
`emit_provenance.py` **fails the build** if any value reaches the UI unmarked,
marked MODELLED, absent without a reason, in an impossible unit, or with a
non-zero candidate area under an amplitude-only screen. Currently 56 values:
41 MEASURED, 5 DERIVED, **0 MODELLED**, 10 UNAVAILABLE, **0 unmarked**.

**The DEM's identity is re-measured every run.** `assert_dem_is_lola()` compares
the native DEM against the LOLA crop at **tolerance 0.0** — bit-identity, not
"close enough" — and exits non-zero on any difference.

**Twenty-two gates**, five of them on every rebuild, and `verify_all.py` runs all
twenty-two and maps each to a statement in PRD section 6.

**Every gate was verified by making it fail on purpose.** That is not decoration:
**seven times in this project the verification apparatus itself was wrong.** A
histogram check tested a CSS filter the application did not apply — it *passed*,
on a fiction. A latitude test had the wrong sign and would have certified a
perfect interpolation artifact as clean terrain. **No test leaves a question
open; a wrong-signed test closes it with the wrong answer and hands you a green
light to cite.** Those five are documented in `METHODS.md` §0, with the rule that
came out of them: **a verifier must read the value the application uses, never
restate it.**

**And the honest one:** three numbers in this project were wrong and are recorded
as wrong. A PSR area 2.88× larger than the frame it was inside. A hazard field
saturating at 1.0 in the API while the screen showed the correct value. A
provenance string naming the 80 m product in the same sentence as "20 m posts".
Each was found, each is written up, none was quietly corrected.

---

## 4. "What is your contribution?"

> **Read down a column: at N = 6 nothing clears the floor, by N = 38 everything
> does. The look count decides the answer, and it is not reported.**

Concretely, four things this literature does not currently do:

1. **The first ENL measured on a DFSAR product** — 5–6 against a nominal 21 — with
   a controlled experiment on the single-look complex from the same pass that
   isolates the mechanism and rules out scene texture.
2. **A per-pixel detection floor at a named look count.** A pixel must read above
   **1.70–1.90** to be significantly above a threshold of 1.00. The swath's
   maximum is 0.0534 — short by a factor of 35.
3. **An ice-candidate area reported with a confidence interval** —
   0.0000 km², 95 % CI [0.0000, 0.147] km² on 38 051 effective samples
   (2,337,086 pixels ÷ 61.42 px per independent sample). Wilson, not the normal
   approximation, because at k = 0 the normal interval collapses to [0, 0] and
   would report a measured zero as carrying no uncertainty at all. **The zero is
   the case that most needs its interval.**
4. **A re-analysis of the published detections against their own floors**, with
   every assumption listed beside it — including, explicitly, that my measured
   ENL **cannot** be transferred to their full-polarimetric product. *The point is
   not that their look count is mine. It is that nobody has measured theirs.*

**What I am not claiming.** Not that any published detection is wrong. Not that
there is no ice at Faustini. Not that my ENL applies to anyone else's data. The
claim is narrower and harder to dismiss: **the floor is not reported alongside
these detections, so a reader cannot tell — and it is cheap to report.**
