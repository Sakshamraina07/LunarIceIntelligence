"""
horizon_frame.py -- project the polar horizon product onto the DFSAR frame.

`compute_horizon.py` computes illumination on the LOLA polar grid, decimated,
because that is the grid the occluding terrain lives on. Everything downstream --
the analysis, the layers, the screen -- works on the DFSAR frame's 25 m grid. This
is the one place that maps between them, so the mapping cannot be done two
slightly different ways in two files.

RESAMPLING A SHADOW MASK IS NOT THE SAME AS RESAMPLING A HEIGHT
---------------------------------------------------------------
`illumination_fraction` is continuous in [0, 1] and bilinear interpolation of it
is meaningful: a cell straddling a shadow boundary genuinely is lit for some of
the sun states sampled. `psr_mask` is boolean, and interpolating it would invent
half-shadowed pixels. So the mask is NOT resampled -- it is RE-DERIVED on the
frame grid from the resampled fraction, by the same `fraction == 0` rule that
defined it on the polar grid. That keeps one definition of "never lit" rather
than two.

AND IT IS STILL A 240 m PRODUCT
-------------------------------
Putting a 240 m shadow mask on a 25 m grid does not give it 25 m detail. Every
consumer is handed `effective_metres_per_pixel` alongside the arrays and is
expected to say so. `assert_resolution_declared()` is the guard: a caller that
forgets to carry the resolution forward fails rather than publishing a mask that
looks nine times sharper than it is.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

__all__ = ["HorizonProduct", "load_horizon", "assert_resolution_declared"]


class HorizonProduct:
    """The polar horizon arrays plus the sidecar that describes them."""

    def __init__(self, arrays: dict, meta: dict, npz_path: Path):
        self.illumination_fraction = arrays["illumination_fraction"]
        self.psr_mask = arrays["psr_mask"]
        self.horizon_min_tan = arrays["horizon_min_tan"]
        self.horizon_max_tan = arrays["horizon_max_tan"]
        self.sky_view_factor = arrays["sky_view_factor"]
        # Written only when compute_horizon.py ran pass 2 (--doubly). Absent is a
        # real state: the scattered-light term simply was not computed, and the
        # single-shadow mask must NOT be substituted for it.
        self.doubly_shadowed = arrays.get("doubly_shadowed")
        self.lit_crest_fraction = arrays.get("lit_crest_fraction")
        self.meta = meta
        self.path = npz_path

    # -- the properties every consumer is required to carry ----------------
    @property
    def native_m(self) -> float:
        return float(self.meta["native_metres_per_pixel"])

    @property
    def effective_m(self) -> float:
        return float(self.meta["effective_metres_per_pixel"])

    @property
    def decimation(self) -> int:
        return int(self.meta["decimation_factor"])

    def to_frame(self, frame, shape: tuple[int, int]) -> dict:
        """
        Resample onto a DFSAR frame of `shape` (lines, samples).

        `frame` is a `sar_geometry.SarFrame`. Both grids are south polar
        stereographic on the same sphere, so the mapping is a closed-form
        composition of the two affine pixel-to-projected transforms -- no
        reprojection, no interpolation of coordinates, and no assumption that
        the two products happen to share an origin.
        """
        from scipy.ndimage import map_coordinates

        lines, samples = shape
        dec = self.decimation
        lpo = float(self.meta["line_projection_offset"])
        spo = float(self.meta["sample_projection_offset"])
        base = float(self.meta["pixel_base_offset"])
        native = self.native_m

        out = {}
        rows = np.arange(lines, dtype=np.float64)
        cols = np.arange(samples, dtype=np.float64)

        # DFSAR pixel -> projected metres -> LOLA native pixel -> decimated pixel.
        # A block-mean cell of size `dec` starting at native index d*dec has its
        # centre at d*dec + (dec-1)/2, so the inverse is (native - (dec-1)/2)/dec.
        gx, gy = frame.pixel_to_xy(rows[:, None], cols[None, :])
        gx, gy = np.broadcast_arrays(gx, gy)
        lola_line = lpo - gy / native - base
        lola_samp = spo + gx / native - base
        dec_line = (lola_line - (dec - 1) / 2.0) / dec
        dec_samp = (lola_samp - (dec - 1) / 2.0) / dec
        coords = np.stack([dec_line, dec_samp])

        for name in ("illumination_fraction", "sky_view_factor",
                     "horizon_min_tan", "horizon_max_tan"):
            src = getattr(self, name)
            # horizon_*_tan can hold -inf where the source had no data. Bilinear
            # interpolation of -inf poisons a whole neighbourhood, so those are
            # carried as NaN and restored after.
            finite = np.isfinite(src)
            clean = np.where(finite, src, 0.0).astype(np.float64)
            res = map_coordinates(clean, coords, order=1, mode="nearest")
            w = map_coordinates(finite.astype(np.float64), coords, order=1, mode="nearest")
            res = np.where(w > 0.999, res, np.nan)
            out[name] = res.astype(np.float32)

        # RE-DERIVED, not resampled. See the module docstring.
        out["psr_mask"] = out["illumination_fraction"] == 0.0

        # doubly_shadowed is CATEGORICAL, so it is resampled NEAREST (order=0)
        # and never bilinearly — an interpolated boolean would invent
        # half-doubly-shadowed pixels. It cannot be re-derived from a continuous
        # field the way psr_mask can, because it is not a threshold on one.
        if self.doubly_shadowed is not None:
            dbl = map_coordinates(self.doubly_shadowed.astype(np.uint8), coords,
                                  order=0, mode="nearest")
            # Intersected with the frame's own PSR: doubly shadowed is a SUBSET
            # of never-lit by definition, and resampling two masks on slightly
            # different rules could otherwise let a cell out of that subset.
            out["doubly_shadowed"] = (dbl > 0) & out["psr_mask"]
        if self.lit_crest_fraction is not None:
            out["lit_crest_fraction"] = map_coordinates(
                self.lit_crest_fraction.astype(np.float64), coords,
                order=1, mode="nearest").astype(np.float32)
        out["effective_metres_per_pixel"] = self.effective_m
        out["native_metres_per_pixel"] = native
        out["decimation_factor"] = dec
        out["resample_ratio"] = self.effective_m / 25.0
        return out


def load_horizon(lola_dir: Path, effective_m: float | None = None) -> HorizonProduct:
    """
    Load the horizon product, or fail with the command that makes it.

    There is deliberately NO fallback to the old brightness proxy. If the
    horizon has not been computed, illumination is UNAVAILABLE — which is what
    it was before Phase 2 and is an honest state. Substituting the proxy here
    would put a modelled quantity back in a measured slot.
    """
    if effective_m is not None:
        npz = lola_dir / f"horizon_{effective_m:g}m.npz"
        side = lola_dir / f"horizon_{effective_m:g}m.provenance.json"
    else:
        found = sorted(lola_dir.glob("horizon_*m.npz"))
        if not found:
            raise FileNotFoundError(
                f"no horizon product in {lola_dir}. Illumination and PSR stay UNAVAILABLE "
                "until it exists. Run:\n"
                "    python backend/scripts/compute_horizon.py"
            )
        npz = found[0]
        side = npz.with_name(npz.stem + ".provenance.json")

    if not npz.is_file() or not side.is_file():
        raise FileNotFoundError(
            f"{npz.name} or its provenance sidecar is missing. Run:\n"
            "    python backend/scripts/compute_horizon.py"
        )

    meta = json.loads(side.read_text(encoding="utf-8"))
    for key in ("native_metres_per_pixel", "effective_metres_per_pixel",
                "decimation_factor", "azimuths"):
        if key not in meta:
            raise SystemExit(
                f"{side.name} has no '{key}'. A shadow mask that cannot state its own "
                "resolution must not be published. Re-run compute_horizon.py."
            )
    with np.load(npz) as z:
        arrays = {k: z[k] for k in z.files}
    return HorizonProduct(arrays, meta, npz)


def assert_resolution_declared(block: dict, where: str) -> None:
    """
    Fail if a consumer publishes illumination without its resolution.

    The whole failure mode this phase exists to end is a modelled quantity worn
    as a measured one. The successor failure mode is a real quantity worn at a
    resolution it does not have — a 240 m shadow mask captioned as 25 m. This is
    cheap insurance against that.
    """
    for key in ("native_metres_per_pixel", "effective_metres_per_pixel",
                "decimation_factor"):
        if block.get(key) in (None, ""):
            raise SystemExit(
                f"{where}: illumination is published without '{key}'. A shadow mask derived "
                "from decimated posts must never be presented at the display grid's "
                "resolution. Carry the field."
            )
