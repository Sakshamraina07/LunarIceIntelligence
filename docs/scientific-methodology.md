# Scientific Methodology — SUPERSEDED by METHODS.md

This document predates every measurement in the project and contains at least one
statement now known to be wrong:

> *"At lunar polar latitudes (> 85°S), the Sun hovers between 1.0° and 2.0° above
> the local horizon."*

**That is false, and correcting it was a methods contribution.** ±1.54° is the
bound on the SUBSOLAR LATITUDE, not on solar elevation. Solar elevation at a
point of latitude φ reaches `1.54° + (90° − |φ|)`, which is 1.54° only exactly at
the pole and 6.71° at this frame's outer edge. Treating it as a constant
under-illuminates the frame by up to 4.4× and inflated the PSR area from
26,900 km² to a figure 2.88× the entire frame before the domain was fixed.

It also described "grazing-angle ray-tracing", which was a brightness proxy with
no horizon term in it. That was replaced in Phase 2 by an actual horizon
computation over the full LOLA polar array, validated against the LOLA team's own
published PSR mask.

**`METHODS.md` is the single methodological record.**

| topic | section |
|---|---|
| the polarimetric screen, and why it is empty by construction | §1 |
| georeferencing, validated against ISRO's own grid | §2 |
| illumination, permanent shadow, and the solar-elevation correction | §5 |
| external validation against LPSR — Jaccard 0.714 | §5.10 |
| the screening thresholds and whose they are | §6 |
| the radar product: looks, speckle, and what a DN means | §7 |
| detection statistics, floors, and the confidence interval | §11 |
