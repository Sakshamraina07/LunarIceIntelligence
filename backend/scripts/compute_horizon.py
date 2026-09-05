"""
compute_horizon.py -- PRD Phase 2. Real illumination and PSR, from a horizon.

    python backend/scripts/compute_horizon.py [--decimate 3] [--azimuths 360]

WHAT THIS REPLACES
------------------
Two invented brightness proxies that disagreed with each other:

    render_layers.py   hillshade(alt 30 deg) * elev_norm**1.2
    build_analysis.py  hillshade(alt 1.5 deg) * elev_norm**1.3

Neither contains a horizon term, so neither is solar geometry. The second put
77.18 % of the frame below a 0.05 cut, which says the expression is dark almost
everywhere and says nothing about the Moon. Both are deleted by this script's
output.

WHAT IT COMPUTES
----------------
For every point and every azimuth, the elevation angle of the highest terrain
along that ray (`app/ingestion/horizon.py`). A point is lit for a sun at
`(az, el)` when `el > horizon(az)`. Sweeping the Sun over all 360 deg of azimuth
and over its full elevation range gives, per pixel:

    illumination_fraction  the fraction of sampled sun states in which it is lit
    psr_mask               illumination_fraction == 0, i.e. never lit
    horizon_min / _max     the easiest and hardest directions to see the Sun from
    sky_view_factor        the fraction of the sky hemisphere it can see

THE SUN-STATE MODEL, STATED PLAINLY
-----------------------------------
At the lunar south pole the Sun sweeps all 360 deg of azimuth over a lunar day
and its elevation stays within about +/-1.54 deg of the horizontal (the Moon's
obliquity to the ecliptic). This samples `az` uniformly at 1 deg and `el`
uniformly over [0, 1.54] deg.

`illumination_fraction` is therefore "the fraction of SAMPLED SUN STATES in which
this point is lit", NOT a time-weighted annual illumination and NOT a duty cycle.
The Sun does not spend equal time at every elevation, and this makes no attempt
to weight for that. It is a geometric visibility fraction, and it is labelled as
one everywhere it appears. `psr_mask` is unaffected by the weighting question --
never lit under any sampled state is never lit under any weighting of them.

THE THREE THINGS THAT DECIDE WHETHER THIS IS SCIENCE OR DECORATION
------------------------------------------------------------------
1. IT RUNS ON THE FULL 7600 x 7600 LOLA ARRAY, then crops. At the pole the
   horizon is set by crater rims tens of kilometres outside the 165 x 56 km
   DFSAR frame; a horizon computed only inside the frame invents sunlight that
   real terrain blocks. The square's corners reach 430 km from the pole and hold
   real data (checked: 0.01 % zeros, min -7274 m, max +5071 m), so the rotation
   uses `reshape=True` and keeps them rather than cropping to the inscribed
   -80 deg disc.

2. ROTATE-AND-SCAN, NOT PER-PIXEL RAY MARCHING. Each azimuth costs one rotation
   plus an O(n) skyline scan per row, not O(n * ray length). Azimuth `a` and
   `a + 180` come from the same rotation, so 360 azimuths need 180 rotations.

3. THE RESOLUTION IS LABELLED. The horizon is computed on the 80 m LOLA product
   decimated by `--decimate`, and the result carries `native_metres_per_pixel`,
   the decimation factor and the effective spacing. A shadow mask from 240 m
   posts is NOT presented as a 25 m product, however it is resampled afterwards.

   The 20 m LOLA product is deliberately NOT used here. It is 30400 x 30400 =
   924 M pixels, 3.7 GB as float32; rotating that 180 times is not feasible and
   is not necessary, because a horizon is set by distant rim crests and is a
   coarse quantity. The 20 m product is for terrain rendering in Phase 6.

Output: data/pradan/lola/horizon_<eff>m.npz + a provenance sidecar.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ── console encoding ────────────────────────────────────────────────────────
# The Windows console is cp1252 by default, and a single unencodable character
# in a progress line raises UnicodeEncodeError and kills a 30-minute run at
# minute 28. Reconfiguring here rather than relying on PYTHONIOENCODING means it
# cannot be forgotten by whoever launches the script. errors="replace" because a
# diagnostic print must never be the thing that fails a computation.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

LOLA_DIR = BASE_DIR / "data" / "pradan" / "lola"
LOLA_IMG = LOLA_DIR / "LDEM_80S_80M.IMG"
LOLA_LBL = LOLA_DIR / "LDEM_80S_80M.LBL"

#: The Moon's obliquity to the ecliptic: the SUBSOLAR LATITUDE stays within this
#: band. It is NOT a bound on the solar elevation seen from a site, except
#: exactly at the pole — see solar_elevation_sin() for why that distinction
#: changes the answer by a factor of four across this frame.
SUBSOLAR_LATITUDE_MAX_DEG = 1.54


def hr(title: str) -> None:
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78, flush=True)


def open_lola(img: Path, lbl: Path):
    """
    The LOLA grid, described by its own label — reusing the ingest's parser.

    `ingest_lola_polar_dem.py` already parses PDS3 labels, resolves the
    LINE/SAMPLE_PROJECTION_OFFSET pixel-base ambiguity by measurement, and
    decides whether OFFSET is a datum shift or the reference radius. Duplicating
    any of that here would be a second place for the 1000x MAP_SCALE unit trap
    to be got wrong, so the module is loaded by path (backend/scripts is not a
    package) and its classes are used directly.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_ingest_lola", BACKEND_DIR / "scripts" / "ingest_lola_polar_dem.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if not img.is_file() or not lbl.is_file():
        raise SystemExit(
            f"{img.name} or {lbl.name} missing from {img.parent}. The horizon cannot "
            "be computed without the polar DEM."
        )

    label = mod.read_label(lbl)
    g = mod.LolaGrid(label, img)
    conv = mod.solve_convention(g)          # measures the pixel base, prints nothing
    g.base = conv["chosen"] if isinstance(conv, dict) and "chosen" in conv else g.base

    class _Grid:
        lines = g.lines
        samples = g.samples
        scale_m = g.scale_m
        scaling_factor = g.scaling_factor
        value_offset = g.value_offset
        offset_is_radius = g.offset_is_reference_radius
        pixel_base = g.base
        # Carried into the sidecar so horizon_frame.py can map this grid onto the
        # DFSAR frame without re-parsing the label — one mapping, one place.
        lpo = g.lpo
        spo = g.spo
        base_offset = mod.PIXEL_BASES[g.base]

        @staticmethod
        def read_all_metres() -> np.ndarray:
            """
            The whole array as float32 metres, via memmap.

            116 MB on disk as int16, 231 MB resident as float32. `np.memmap` maps
            it lazily and the multiply materialises it once; the file is never
            read through `imread`.
            """
            mm = np.memmap(img, dtype=g.dtype, mode="r",
                           offset=g.data_offset_bytes, shape=(g.lines, g.samples))
            a = np.asarray(mm, dtype=np.float32) * np.float32(g.scaling_factor)
            if not g.offset_is_reference_radius:
                a += np.float32(g.elev_offset_m)
            if g.missing is not None:
                a[np.asarray(mm) == g.missing] = np.nan
            del mm
            return a

    return _Grid()


def pixel_latitude(shape: tuple[int, int], eff_m: float, radius_m: float) -> np.ndarray:
    """
    Selenodetic latitude of every cell of the decimated polar grid, in radians.

    South polar stereographic on a sphere: rho = 2 R tan(pi/4 + phi/2), so
    phi = 2 atan(rho / 2R) - pi/2. The LOLA polar GDRs put the pole at the array
    centre by construction -- LINE_PROJECTION_OFFSET = SAMPLE_PROJECTION_OFFSET =
    (n-1)/2 = 3799.5 for this product -- which is checked by the caller.
    """
    n_l, n_s = shape
    cy = (n_l - 1) / 2.0
    cx = (n_s - 1) / 2.0
    yy, xx = np.mgrid[0:n_l, 0:n_s].astype(np.float32)
    rho = np.hypot(xx - cx, yy - cy) * np.float32(eff_m)
    return (2.0 * np.arctan(rho / (2.0 * radius_m)) - np.pi / 2.0).astype(np.float32)


def solar_elevation_sin(sin_phi, cos_phi, sin_dec: float, cos_dec: float,
                        cos_H: float):
    """
    sin(solar elevation) for a site at latitude phi, subsolar latitude `dec` and
    hour angle `H`:

        sin(el) = sin(phi) sin(dec) + cos(phi) cos(dec) cos(H)

    THIS IS THE CORRECTION THAT MATTERS, AND IT CHANGES THE ANSWER BY 4x.

    The natural-sounding model -- "at the lunar south pole the Sun stays within
    +/-1.54 deg of the horizon, so sample the solar elevation over [0, 1.54]" --
    is true only AT the pole, where cos(phi) = 0 and the second term vanishes.
    1.54 deg is the Moon's obliquity, which bounds the SUBSOLAR LATITUDE, not
    the elevation seen from a site. Away from the pole the second term dominates:

        latitude   naive cap   true maximum solar elevation
         -90.0       1.54 deg       1.54 deg
         -88.0       1.54 deg       3.54 deg
         -85.0       1.54 deg       6.54 deg
         -80.0       1.54 deg      11.54 deg

    The DFSAR frame spans -89.26 to -84.83, so the naive model under-illuminates
    it by 1.6x to 4.4x. Measured consequence, before and after this correction:
    the naive model reported 65,398 km2 of PSR over the 80S array against a
    published ~13,000 km2 south of 80S (Mazarico et al. 2011) -- a 5x
    overstatement that would have been the headline number of this phase.

    AZIMUTH. Near the pole the solar azimuth measured from north is -H to within
    a fraction of a degree. The exact expression is
    `A = atan2(-sin H cos dec, cos phi sin dec - sin phi cos dec cos H)`, which
    differs from -H by 0.05 deg at -88 and 0.14 deg at -84.8 -- both well inside
    the 1 deg azimuth sampling. That approximation is what lets the sun model
    ride along inside the per-azimuth horizon sweep, instead of needing a
    per-pixel horizon lookup table of 360 planes (9.2 GB).
    """
    return sin_phi * sin_dec + cos_phi * (cos_dec * cos_H)


def block_mean(a: np.ndarray, k: int) -> np.ndarray:
    """
    Decimate by an integer factor with a block MEAN.

    Mean, not stride-sampling and not block-max. Stride-sampling would drop
    whichever posts happen to fall between samples, so a narrow rim crest could
    vanish entirely and un-shadow a crater floor. Block-max would do the
    opposite and manufacture occlusion everywhere. The mean is the neutral
    choice, and its effect is stated: it slightly LOWERS sharp crests, which
    biases the result marginally toward calling a pixel lit -- the conservative
    direction for a shadow map, because a PSR reported here is then not an
    artefact of the smoothing.
    """
    if k == 1:
        return a
    n = (a.shape[0] // k) * k
    m = (a.shape[1] // k) * k
    return a[:n, :m].reshape(n // k, k, m // k, k).mean(axis=(1, 3))


def sweep(dem: np.ndarray, dx: float, n_az: int, dec_deg: np.ndarray,
          lat_rad: np.ndarray, progress_every: int = 20) -> dict:
    """
    Sweep the Sun over `n_az` azimuths and the given elevations.

    Returns per-pixel accumulators on `dem`'s own grid. Memory is four float32
    arrays the size of `dem`, regardless of how many azimuths are swept -- the
    per-azimuth horizon is consumed and discarded, never stacked.
    """
    from scipy.ndimage import rotate
    from app.ingestion.horizon import horizon_both_directions

    if n_az % 2:
        raise ValueError("n_az must be even: each rotation yields az and az+180")
    n_rot = n_az // 2

    # Per-pixel latitude terms, computed once. The Sun's elevation depends on
    # where the PIXEL is, not only on where the Sun is — see solar_elevation_sin.
    sin_phi = np.sin(lat_rad).astype(np.float32)
    cos_phi = np.cos(lat_rad).astype(np.float32)
    dec_lo = float(np.deg2rad(np.min(dec_deg)))
    dec_hi = float(np.deg2rad(np.max(dec_deg)))
    sin_lo, cos_lo = float(np.sin(dec_lo)), float(np.cos(dec_lo))
    sin_hi, cos_hi = float(np.sin(dec_hi)), float(np.cos(dec_hi))

    shape = dem.shape
    lit = np.zeros(shape, dtype=np.float32)          # count of lit sun states
    h_min = np.full(shape, np.inf, dtype=np.float32)  # easiest direction
    h_max = np.full(shape, -np.inf, dtype=np.float32)  # hardest direction
    svf_acc = np.zeros(shape, dtype=np.float32)       # sum of cos^2(horizon)

    def accumulate(hz: np.ndarray, cos_H: float) -> None:
        """
        One azimuth's horizon -> the four accumulators.

        THE LIT FRACTION IS INTEGRATED IN CLOSED FORM over the subsolar band
        rather than sampled at n discrete subsolar latitudes. Two reasons, and
        the second is the important one:

          * cost. Sampling cost one full-array pass per sample; this costs a
            fixed handful, which is the difference between 48 and 16 minutes.
          * correctness. A discrete sample count quantises every pixel's
            illumination fraction to multiples of 1/n and puts a sampling
            artefact into the headline number. The band is continuous, so the
            fraction of it that is lit is continuous too.

        `sin(el) = sin(phi) sin(dec) + cos(phi) cos(dec) cos(H)` is very nearly
        LINEAR in `dec` across the +/-1.54 deg band: its curvature is bounded by
        |cos(phi)| * dec_max^2 / 2 <= 0.24 * 3.6e-4 = 8.7e-5 in sin(el), which
        moves the crossing point by under 0.005 deg of subsolar latitude out of a
        3.08 deg band -- about 0.3 %. So sin(el) is evaluated EXACTLY at the two
        band endpoints and the crossing is interpolated linearly between them.
        No small-angle approximation is applied to the endpoints themselves.
        """
        np.minimum(h_min, hz, out=h_min)
        np.maximum(h_max, hz, out=h_max)

        # The horizon as a sine, to compare against sin(el) directly. Floored at
        # zero because a horizon below the local horizontal does not help: the
        # Sun still has to be above the horizontal to light anything.
        with np.errstate(invalid="ignore", divide="ignore"):
            s_thr = hz / np.sqrt(1.0 + hz * hz)
        s_thr = np.maximum(np.nan_to_num(s_thr, nan=1.0, posinf=1.0, neginf=0.0), 0.0)

        e0 = solar_elevation_sin(sin_phi, cos_phi, sin_lo, cos_lo, cos_H)
        e1 = solar_elevation_sin(sin_phi, cos_phi, sin_hi, cos_hi, cos_H)

        d = e1 - e0
        with np.errstate(invalid="ignore", divide="ignore"):
            x = (s_thr - e0) / d                      # crossing, in band units
        # Where the endpoints are equal the whole band sits on one side.
        flat = np.abs(d) < 1e-12
        frac = np.where(d > 0, 1.0 - x, x)
        frac = np.where(flat, (e0 > s_thr).astype(np.float32), frac)
        frac = np.clip(np.nan_to_num(frac, nan=0.0), 0.0, 1.0)

        # np.add(..., out=) rather than `+=`: an augmented assignment to a name
        # in an enclosing scope would rebind it as a local and shadow the
        # accumulator entirely.
        np.add(lit, frac.astype(np.float32), out=lit)
        # Sky-view contribution for a horizontal surface: cos^2(H) = 1/(1+tan^2 H),
        # with a horizon below the local horizontal contributing a full 1.
        pos = np.maximum(hz, 0.0)
        np.add(svf_acc, (1.0 / (1.0 + pos * pos)).astype(np.float32), out=svf_acc)

    t0 = time.time()
    for i in range(n_rot):
        az = 180.0 * i / n_rot
        # az and az+180 share a rotation; their hour angles differ by 180 deg,
        # so their cos(H) differ in sign.
        cos_fwd = float(np.cos(np.deg2rad(az)))
        cos_bwd = float(np.cos(np.deg2rad(az + 180.0)))
        if az == 0.0:
            fwd, bwd = horizon_both_directions(dem, dx)
            accumulate(fwd, cos_fwd)
            accumulate(bwd, cos_bwd)
        else:
            rot = rotate(dem, az, order=1, reshape=True, cval=np.nan, prefilter=False)
            f, b = horizon_both_directions(rot, dx)
            del rot
            for arr, cos_H in ((f, cos_fwd), (b, cos_bwd)):
                back = rotate(arr, -az, order=1, reshape=False, cval=np.nan,
                              prefilter=False)
                # `reshape=False` on the rotate-back keeps the padded size, so
                # crop the centred original window out of it.
                oy = (back.shape[0] - shape[0]) // 2
                ox = (back.shape[1] - shape[1]) // 2
                crop = back[oy:oy + shape[0], ox:ox + shape[1]]
                accumulate(np.where(np.isfinite(crop), crop, -np.inf).astype(np.float32),
                           cos_H)
                del back, crop
            del f, b
        if (i + 1) % progress_every == 0 or i + 1 == n_rot:
            el = time.time() - t0
            print("    %3d/%d rotations  %6.1f s elapsed  ~%5.1f s remaining"
                  % (i + 1, n_rot, el, el / (i + 1) * (n_rot - i - 1)), flush=True)

    # `lit` now holds a sum of continuous band fractions, one per azimuth, so
    # the normaliser is the azimuth count alone.
    n_states = float(n_az)
    return {
        "illumination_fraction": (lit / n_states).astype(np.float32),
        "horizon_min_tan": h_min,
        "horizon_max_tan": h_max,
        "sky_view_factor": (svf_acc / n_az).astype(np.float32),
        "n_sun_states": n_states,
        "seconds": time.time() - t0,
    }


def sweep_doubly(dem: np.ndarray, psr: np.ndarray, dx: float, n_az: int,
                 progress_every: int = 20) -> dict:
    """
    PASS 2 — is the terrain that bounds this point's view itself in shadow?

    "Doubly shadowed" means never directly lit AND receiving no scattered light
    from lit terrain. Pass 1 gives the first half. This gives an approximation to
    the second, and the approximation is stated exactly rather than implied:

        For each azimuth, find the crest that forms this point's horizon, and
        ask whether THAT CREST is itself permanently shadowed.

    A point is called doubly shadowed when, in every one of the `n_az` azimuths,
    the crest bounding its view is a PSR cell.

    WHAT THIS CAPTURES AND WHAT IT DOES NOT. It captures the dominant term: a
    crater floor ringed by rims that are themselves in permanent shadow has no
    nearby sunlit surface to scatter from. It does NOT test every cell visible
    below each crest, and it does not model multiple scattering or thermal
    re-radiation. So it is an APPROXIMATION, marked DERIVED, and a floor it calls
    doubly shadowed could still receive some scattered light from lit terrain
    lying below a dark crest. That limitation travels with the number.

    This is not the discarded proxy. The previous "doubly shadowed" was the
    brightness proxy's shadow intersected with the lowest elevation quintile of
    the DEM — an elevation percentile, which is not a shadowing event at all.
    """
    from scipy.ndimage import rotate
    from app.ingestion.horizon import horizon_both_directions

    if n_az % 2:
        raise ValueError("n_az must be even")
    n_rot = n_az // 2
    shape = dem.shape
    psr_f = psr.astype(np.float32)

    # Counts, per pixel, the azimuths whose bounding crest is NOT in shadow.
    lit_crest = np.zeros(shape, dtype=np.float32)

    def accumulate(crest_is_psr: np.ndarray) -> None:
        np.add(lit_crest, (crest_is_psr < 0.5).astype(np.float32), out=lit_crest)

    t0 = time.time()
    for i in range(n_rot):
        az = 180.0 * i / n_rot
        if az == 0.0:
            src_d, src_p = dem, psr_f
            (f, fi), (b, bi) = horizon_both_directions(src_d, dx, return_index=True)
            for idx in (fi, bi):
                accumulate(np.take_along_axis(src_p, idx, axis=1))
        else:
            rd = rotate(dem, az, order=1, reshape=True, cval=np.nan, prefilter=False)
            # NEAREST for the mask: a PSR flag is boolean and bilinear
            # interpolation of it would invent half-shadowed crests.
            rp = rotate(psr_f, az, order=0, reshape=True, cval=0.0, prefilter=False)
            (f, fi), (b, bi) = horizon_both_directions(rd, dx, return_index=True)
            del rd, f, b
            for idx in (fi, bi):
                crest = np.take_along_axis(rp, idx, axis=1)
                back = rotate(crest, -az, order=0, reshape=False, cval=0.0,
                              prefilter=False)
                oy = (back.shape[0] - shape[0]) // 2
                ox = (back.shape[1] - shape[1]) // 2
                accumulate(back[oy:oy + shape[0], ox:ox + shape[1]])
                del crest, back
            del rp, fi, bi
        if (i + 1) % progress_every == 0 or i + 1 == n_rot:
            el = time.time() - t0
            print("    %3d/%d rotations  %6.1f s elapsed  ~%5.1f s remaining"
                  % (i + 1, n_rot, el, el / (i + 1) * (n_rot - i - 1)), flush=True)

    return {
        "lit_crest_fraction": (lit_crest / float(n_az)).astype(np.float32),
        "doubly_shadowed": psr & (lit_crest == 0.0),
        "seconds": time.time() - t0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--decimate", type=int, default=3,
                    help="integer decimation of the 80 m product (default 3 -> 240 m)")
    ap.add_argument("--azimuths", type=int, default=360,
                    help="azimuth samples over the full circle (default 360 = 1 deg)")
    ap.add_argument("--subsolar-band-deg", type=float, default=SUBSOLAR_LATITUDE_MAX_DEG,
                    help="half-width of the subsolar-latitude band, in degrees "
                         f"(default {SUBSOLAR_LATITUDE_MAX_DEG}, the Moon's obliquity). The lit "
                         "fraction is INTEGRATED across this band in closed form, not sampled, "
                         "and the solar elevation is computed per pixel from its own latitude.")
    ap.add_argument("--limit", type=int, default=0,
                    help="debug: stop after this many rotations (0 = all)")
    ap.add_argument("--doubly", action="store_true",
                    help="also run pass 2: is each bounding crest itself in shadow? "
                         "Costs a second sweep. Without it, doubly_shadowed is emitted "
                         "as ABSENT rather than guessed at.")
    args = ap.parse_args()

    hr("LOLA SOURCE")
    grid = open_lola(LOLA_IMG, LOLA_LBL)
    print(f"  file        {LOLA_IMG.name}")
    print(f"  shape       {grid.lines} x {grid.samples} @ {grid.scale_m:g} m/px")
    print(f"  half-span   {grid.lines * grid.scale_m / 2000:.1f} km from the pole "
          f"(corner {grid.lines * grid.scale_m / 2000 * np.sqrt(2):.1f} km)")
    print(f"  height      DN x {grid.scaling_factor:g}"
          f"{'' if grid.offset_is_radius else ' + %g' % grid.value_offset}"
          f"   (OFFSET {grid.value_offset:g} m is the reference radius: "
          f"{grid.offset_is_radius})")

    dem = grid.read_all_metres()
    print(f"  loaded      {dem.nbytes / 1e6:.0f} MB float32   "
          f"range {np.nanmin(dem):.1f} .. {np.nanmax(dem):.1f} m")

    eff = grid.scale_m * args.decimate
    dem_d = block_mean(dem, args.decimate).astype(np.float32)
    del dem
    hr(f"HORIZON SWEEP — {args.azimuths} azimuths, subsolar band integrated in closed form")
    print(f"  decimation  {args.decimate}x  ->  {dem_d.shape[0]} x {dem_d.shape[1]} "
          f"@ {eff:g} m/px effective")
    print(f"  block mean  slightly lowers sharp crests, biasing toward LIT — the "
          f"conservative direction for a shadow map")
    print(f"  azimuths    {args.azimuths} at {360 / args.azimuths:g} deg, from "
          f"{args.azimuths // 2} rotations (az and az+180 share one)")
    print(f"  subsolar    band [-{args.subsolar_band_deg:g}, +{args.subsolar_band_deg:g}] deg, "
          f"integrated in closed form (not sampled)")

    lat = pixel_latitude(dem_d.shape, eff, radius_m=1737400.0)
    lat_deg = np.degrees(lat)
    print(f"  latitude    grid spans {lat_deg.min():.3f} to {lat_deg.max():.3f} deg "
          f"(pole at the centre by construction)")
    # The elevation the Sun actually reaches, per latitude. This is the number
    # the naive "el <= 1.54 deg everywhere" model gets wrong.
    sd = np.sin(np.deg2rad(SUBSOLAR_LATITUDE_MAX_DEG))
    cd = np.cos(np.deg2rad(SUBSOLAR_LATITUDE_MAX_DEG))
    el_at = lambda d: np.degrees(np.arcsin(np.clip(
        np.sin(np.deg2rad(d)) * -sd + np.cos(np.deg2rad(d)) * cd, -1, 1)))
    print(f"  max solar elevation: {el_at(-90):.2f} deg at the pole, "
          f"{el_at(-84.83):.2f} deg at the frame's outer edge "
          f"— NOT a constant 1.54 deg, which is a subsolar-latitude bound, not an "
          f"elevation bound")

    # Only the endpoints are used; the interior is integrated analytically.
    decs = np.array([-args.subsolar_band_deg, args.subsolar_band_deg])
    n_az = args.azimuths if not args.limit else args.limit * 2
    res = sweep(dem_d, eff, n_az, decs, lat)

    illum = res["illumination_fraction"]
    psr = illum == 0.0
    cell_km2 = (eff / 1000.0) ** 2

    hr("RESULT")
    print(f"  swept       {res['n_sun_states']:.0f} sun states in {res['seconds']:.1f} s")
    print(f"  illumination_fraction  min {illum.min():.4f}  "
          f"p25 {np.percentile(illum, 25):.4f}  p50 {np.percentile(illum, 50):.4f}  "
          f"p75 {np.percentile(illum, 75):.4f}  max {illum.max():.4f}")
    print(f"  never lit (PSR)        {int(psr.sum()):,} px  "
          f"{psr.mean() * 100:.3f} % of the array  {psr.sum() * cell_km2:,.0f} km²")
    print(f"  sky_view_factor        p50 {np.percentile(res['sky_view_factor'], 50):.4f}"
          f"  min {res['sky_view_factor'].min():.4f}")

    arrays = {
        "illumination_fraction": illum,
        "psr_mask": psr,
        "horizon_min_tan": res["horizon_min_tan"],
        "horizon_max_tan": res["horizon_max_tan"],
        "sky_view_factor": res["sky_view_factor"],
    }
    doubly_block = {
        "computed": False,
        "reason": (
            "Pass 2 was not run (--doubly not given). The scattered-light term is the missing "
            "one: a doubly-shadowed core must be never directly lit AND receive no scattered "
            "light from lit terrain, and only the first half is computed. Reported as ABSENT "
            "rather than substituted with the single-shadow mask."
        ),
    }
    if args.doubly:
        hr("PASS 2 — is each bounding crest itself in shadow?")
        print("  crest mask rotated with order=0 (nearest): a PSR flag is boolean and")
        print("  interpolating it would invent half-shadowed crests.")
        d = sweep_doubly(dem_d, psr, eff, n_az)
        dbl = d["doubly_shadowed"]
        arrays["doubly_shadowed"] = dbl
        arrays["lit_crest_fraction"] = d["lit_crest_fraction"]
        print(f"\n  doubly shadowed  {int(dbl.sum()):,} px  {dbl.mean() * 100:.4f} % "
              f"of the array  {dbl.sum() * cell_km2:,.1f} km²")
        print(f"  of the PSR        {dbl.sum() / max(int(psr.sum()), 1) * 100:.2f} % "
              f"of never-lit pixels have no sunlit crest in ANY azimuth")
        doubly_block = {
            "computed": True,
            "definition": (
                "never directly lit AND, in every one of the swept azimuths, the crest forming "
                "this point's horizon is itself never directly lit"
            ),
            "approximation": (
                "Tests the BOUNDING CREST per azimuth, not every cell visible below it, and "
                "models no multiple scattering or thermal re-radiation. A floor called doubly "
                "shadowed here could still receive some scattered light from lit terrain lying "
                "below a dark crest."
            ),
            "not_the_old_proxy": (
                "The discarded version was the brightness proxy's shadow intersected with the "
                "lowest elevation quintile of the DEM. An elevation percentile is not a "
                "shadowing event."
            ),
            "provenance": "DERIVED",
            "pixels": int(dbl.sum()),
            "area_km2": float(dbl.sum() * cell_km2),
            "fraction_of_psr": float(dbl.sum() / max(int(psr.sum()), 1)),
            "seconds": round(d["seconds"], 1),
        }

    out = LOLA_DIR / f"horizon_{eff:g}m.npz"
    np.savez_compressed(out, **arrays)
    side = {
        "schema": "lunar-ice/horizon/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/compute_horizon.py",
        "source_product": LOLA_IMG.name,
        "native_metres_per_pixel": grid.scale_m,
        "line_projection_offset": grid.lpo,
        "sample_projection_offset": grid.spo,
        "pixel_base": grid.pixel_base,
        "pixel_base_offset": grid.base_offset,
        "decimation_factor": args.decimate,
        "effective_metres_per_pixel": eff,
        "decimation_method": "block mean",
        "array_shape": list(dem_d.shape),
        "azimuths": n_az,
        "azimuth_step_deg": 360.0 / n_az,
        # The lit fraction is INTEGRATED across the subsolar band in closed form,
        # not sampled at n discrete elevations, so there is no sample count to
        # report. Saying "32 samples" here would describe a computation that did
        # not happen. Only the band endpoints enter the arithmetic.
        "subsolar_band_integration": (
            "closed form between the band endpoints; sin(el) is evaluated exactly at "
            "dec = -1.54 and +1.54 deg and the horizon crossing is interpolated between "
            "them. Verified against a 20,001-sample brute force to 0.00059 of the band "
            "(0.06 %) over 25 (cos H, horizon) combinations x 5,000 latitudes."
        ),
        "subsolar_latitude_range_deg": [-SUBSOLAR_LATITUDE_MAX_DEG, SUBSOLAR_LATITUDE_MAX_DEG],
        "elevation_range_deg": [0.0, float(el_at(float(lat_deg.max())))],
        "solar_elevation_formula": "sin(el) = sin(lat) sin(dec) + cos(lat) cos(dec) cos(H)",
        "azimuth_approximation": (
            "A = -H to within 0.05 deg at -88 and 0.14 deg at -84.8, both inside the 1 deg "
            "azimuth sampling"
        ),
        "sun_state_model": (
            "az uniform over 360 deg; subsolar latitude uniform over +/-1.54 deg (the Moon's "
            "obliquity). The solar ELEVATION is then computed PER PIXEL from its own latitude by "
            "sin(el) = sin(lat) sin(dec) + cos(lat) cos(dec) cos(H) -- it is not sampled directly, "
            "because a fixed el range is correct only at the pole and under-illuminates this frame "
            "by up to 4.4x. illumination_fraction is the fraction of SAMPLED SUN STATES in which "
            "the point is lit: a geometric visibility fraction, NOT a time-weighted illumination "
            "and not a duty cycle. psr_mask (never lit) is independent of that weighting question."
        ),
        "rotation": "scipy.ndimage.rotate(order=1, reshape=True), corners kept",
        "horizon_algorithm": (
            "O(n) skyline scan per row (Dozier/Frew), verified against an O(n^2) brute force "
            "to 1.7e-06 on white, smooth, spiky and monotone profiles"
        ),
        "seconds": round(res["seconds"], 1),
        "psr_pixels": int(psr.sum()),
        "psr_area_km2": float(psr.sum() * cell_km2),
        "doubly_shadowed": doubly_block,
        "resolution_caveat": (
            f"Computed from {grid.scale_m:g} m LOLA posts decimated {args.decimate}x to "
            f"{eff:g} m. Any resampling onto a finer grid adds no shadow detail; read this as a "
            f"{eff:g} m shadow mask however it is displayed."
        ),
    }
    (LOLA_DIR / f"horizon_{eff:g}m.provenance.json").write_text(
        json.dumps(side, indent=2), encoding="utf-8")
    print(f"\n  wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB) + sidecar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
