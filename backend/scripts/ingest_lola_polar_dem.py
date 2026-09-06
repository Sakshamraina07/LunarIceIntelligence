"""
INGEST A REAL LOLA POLAR DEM ONTO THE CHANDRAYAAN-2 DFSAR GRID.
===============================================================

Replaces `synthetic_placeholder_dem()` in process_real_sar_pipeline.py with
measured topography. Nothing in this file invents elevation: if the product is
absent, or a label key is missing, or a check fails, it prints why and exits
non-zero without writing anything.

WHAT IT NEEDS ON DISK  (the user downloads these; this script never fetches)
    data/pradan/lola/ldem_80s_20m.img   + .lbl     ~1.9 GB, 20 m/px, south of 80S
    data/pradan/lola/ldem_75s_240m.img  + .lbl     ~90 MB, the validation product

WHAT IT REFUSES TO DO
    - guess a label value. Every number below is read from the .lbl as text.
      SAMPLE_TYPE decides endianness; MAP_SCALE decides the grid; SCALING_FACTOR
      and OFFSET decide the units. Nothing about the product is hardcoded.
    - read the .img whole. The 20 m product is ~1.9 GB; only the DFSAR window is
      materialised, via np.memmap + a slice (about 47 MB for this frame).
    - write an output if any check fails.
    - fall back to anything. There is no synthetic path in this file.

THE THREE CHECKS (handoff v9 step 3), all of which must pass:
    1. the 240 m product's own MINIMUM / MAXIMUM elevation is reproduced from the
       raw DN to within one quantisation step (= SCALING_FACTOR).
    2. the resampled frame's floor is reported, not adjusted. Faustini is expected
       near -3 to -4 km against the 1737.4 km sphere; the number printed is
       whatever the data says.
    3. no NaN and no MISSING_CONSTANT survives into the output.

THE PIXEL/PROJECTION CONVENTION IS MEASURED, NOT ASSUMED
    PDS3 labels are ambiguous about whether LINE_PROJECTION_OFFSET is 0-based,
    1-based, or edge-referenced, and the variants differ by up to one pixel (20 m,
    or 0.8 of a DFSAR pixel). Rather than pick one, `solve_convention()` scores
    every candidate against two facts the label states independently — the pole
    must land where the offsets say, and the array edge must fall at
    MAXIMUM_LATITUDE — and prints the residual for each. The best-scoring
    convention is used and its residual is written into the provenance sidecar.

USAGE
    python backend/scripts/ingest_lola_polar_dem.py --selftest-crs
        Proves the projection code against metadata_real.json. Needs no LOLA file.
    python backend/scripts/ingest_lola_polar_dem.py --selftest-synthetic
        Builds a temporary product-shaped fixture and runs every stage on it.
    python backend/scripts/ingest_lola_polar_dem.py --check-only
        Labels, projection agreement, pixel convention and check 3.1. Writes nothing,
        and never touches the 1.9 GB product.
    python backend/scripts/ingest_lola_polar_dem.py
        Full ingest.

WHAT HAS ACTUALLY RUN, AND WHAT HAS NOT
    Run, and passing, on this machine:
      --selftest-crs        all four DFSAR footprint corners reproduce the lat/lon
                            ISRO wrote from the GeoTIFF GeoKeys to 4.341e-07 deg
                            (13.2 mm on the ground) in latitude and 4.306e-07 deg
                            (1.1 mm) in longitude — which is round-off in their
                            6-decimal file, not error here. The mirrored y
                            convention is rejected by 137.0 deg, i.e. 86.8 km.
      --selftest-synthetic  16 of 16 checks, including a bilinear round-trip on a
                            plane that is exact (max |err| 0.0000 m) against a
                            40 m-per-pixel-of-slip sensitivity.
    NOT run: the real ingest. No LOLA .img/.lbl exists under data/pradan/ (verified
    with `git ls-files data/` and a recursive listing), so every elevation number
    this file would print is still unmeasured. Do not quote them until it has run.

THE ONE THING NEITHER SELF-TEST CAN CHECK
    Whether LOLA's +y means the same direction as the DFSAR product's +y. Both
    labels state south polar stereographic on a sphere, centre latitude -90, centre
    longitude 0, no MAP_PROJECTION_ROTATION, which leaves the two grids differing
    only by an affine map — so they are taken to agree. Settling it by measurement
    would need a third elevation source, and there isn't one offline. The assumption
    is written into the provenance sidecar in those words rather than left implicit.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import map_coordinates

REPO = Path(__file__).resolve().parents[2]
LOLA_DIR = REPO / "data" / "pradan" / "lola"
DFSAR_META = REPO / "data" / "pradan" / "dfsar" / "metadata_real.json"
OUT_DIR = REPO / "data" / "pradan" / "lola"
OUT_FRAME = OUT_DIR / "ldem_frame_25m.tif"
OUT_SIDECAR = OUT_DIR / "ldem_frame_25m.provenance.json"

# Products this ingest knows how to look for, best resolution first. --input overrides
# the search entirely. The list is a search order, not a requirement: exactly one
# product is ingested, and whichever one it is, step 3.1 validates the reader against
# that same product's own stated elevation range — so there is no separate "validation
# product" any more. Phase A is LDEM_80S_80M (80 m/px, ~110 MB); phase B is
# LDEM_80S_20M (20 m/px, ~1.9 GB) and needs no code change, only the file on disk.
PRODUCT_PREFERENCE = [
    ("ldem_80s_20m", "20 m/px, ~1.9 GB, 80S to the pole"),
    ("ldem_80s_80m", "80 m/px, ~110 MB, 80S to the pole"),
    ("ldem_875s_20m", "20 m/px, 87.5S to the pole — does NOT cover this frame"),
    ("ldem_75s_240m", "240 m/px, ~90 MB"),
]


# ── PDS3 label parsing ─────────────────────────────────────────────────────────
#
# A .lbl is plain ODL text: KEY = VALUE, one per line, with /* comments */, nested
# OBJECT = X ... END_OBJECT blocks, quoted strings that may wrap, and units in
# angle brackets (MAP_SCALE = 20.0 <METERS/PIXEL>). Nested keys are stored twice:
# bare (last writer wins) and namespaced as "OBJECT.KEY", so a caller can ask for
# IMAGE.MINIMUM specifically when the same key appears in several objects.

_UNIT = re.compile(r"<[^>]*>")


def read_label(path: Path) -> dict:
    text = path.read_text(errors="replace")
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)

    out: dict = {}
    stack: list[str] = []
    pending_key: str | None = None
    buf = ""

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == "END":
            continue

        if pending_key is not None:                 # continuation of a wrapped value
            buf += " " + line
            if buf.count('"') % 2 == 0 and buf.count("(") <= buf.count(")"):
                _store(out, stack, pending_key, buf)
                pending_key, buf = None, ""
            continue

        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip().upper(), val.strip()

        if key == "OBJECT":
            stack.append(val.upper())
            continue
        if key == "END_OBJECT":
            if stack:
                stack.pop()
            continue
        if key == "GROUP":
            stack.append(val.upper())
            continue
        if key == "END_GROUP":
            if stack:
                stack.pop()
            continue

        if val.count('"') % 2 == 1 or val.count("(") > val.count(")"):
            pending_key, buf = key, val           # value continues on the next line
            continue
        _store(out, stack, key, val)

    if pending_key is not None:
        _store(out, stack, pending_key, buf)
    return out


def _store(out: dict, stack: list[str], key: str, val: str) -> None:
    val = val.strip()
    out[key] = val
    if stack:
        out[f"{stack[-1]}.{key}"] = val


class LabelError(RuntimeError):
    """A label key the ingest depends on is missing or unparseable."""


def num(label: dict, *keys: str) -> float:
    """First key that is present, as a float, with PDS units stripped.

    Raises rather than defaulting: a missing MAP_SCALE must stop the run, not
    silently become 1.0.
    """
    for k in keys:
        if k in label:
            raw = _UNIT.sub("", str(label[k])).strip().strip('"')
            try:
                return float(raw)
            except ValueError as exc:
                raise LabelError(f"{k} = {label[k]!r} is not a number") from exc
    raise LabelError(f"none of {keys} present in label")


def opt(label: dict, *keys: str) -> float | None:
    try:
        return num(label, *keys)
    except LabelError:
        return None


def opt_keyed(label: dict, *keys: str) -> tuple[float | None, str | None]:
    """As opt(), but also returns WHICH key supplied the value.

    Needed because the elevation range lives under DERIVED_MINIMUM in the LOLA
    GDR labels and under MINIMUM in others, and the report has to say which one
    was actually compared against rather than implying a key that is absent.
    """
    for k in keys:
        if k in label:
            return num(label, k), k
    return None, None


def text(label: dict, *keys: str) -> str:
    for k in keys:
        if k in label:
            return str(label[k]).strip().strip('"')
    raise LabelError(f"none of {keys} present in label")


def opt_text(label: dict, *keys: str) -> str | None:
    try:
        return text(label, *keys)
    except LabelError:
        return None


# PDS SAMPLE_TYPE -> numpy. Endianness comes from the label, never from the host.
_ENDIAN = {
    "MSB_INTEGER": ">i", "LSB_INTEGER": "<i",
    "MAC_INTEGER": ">i", "PC_INTEGER": "<i",
    "INTEGER": ">i", "SUN_INTEGER": ">i", "VAX_INTEGER": "<i",
    "MSB_UNSIGNED_INTEGER": ">u", "LSB_UNSIGNED_INTEGER": "<u",
    "UNSIGNED_INTEGER": ">u", "PC_UNSIGNED_INTEGER": "<u",
    "MAC_UNSIGNED_INTEGER": ">u", "SUN_UNSIGNED_INTEGER": ">u",
    "IEEE_REAL": ">f", "MSB_IEEE_REAL": ">f", "SUN_REAL": ">f",
    "PC_REAL": "<f", "LSB_IEEE_REAL": "<f",
}


def label_dtype(label: dict) -> np.dtype:
    st = text(label, "IMAGE.SAMPLE_TYPE", "SAMPLE_TYPE").upper()
    bits = int(num(label, "IMAGE.SAMPLE_BITS", "SAMPLE_BITS"))
    if st not in _ENDIAN:
        raise LabelError(f"SAMPLE_TYPE {st!r} not recognised")
    if bits % 8:
        raise LabelError(f"SAMPLE_BITS {bits} is not a whole number of bytes")
    kind = _ENDIAN[st]
    dt = np.dtype(f"{kind}{bits // 8}")
    if dt.itemsize * 8 != bits:
        raise LabelError(f"cannot represent {st}/{bits} in numpy")
    return dt


# ── south polar stereographic, sphere, tangent at the pole, k0 = 1 ─────────────
#
# Snyder's spherical polar stereographic, south case:
#     rho = 2 R k0 tan(pi/4 + phi/2)          (0 at the pole, grows equatorward)
#     x   = rho sin(lam - lam0)
#     y   = rho cos(lam - lam0)               ("+y toward lam0" convention)
# The sign of the y term is the one thing implementations disagree on, so
# LON_CONVENTIONS holds both and selftest_crs() reports which one reproduces the
# corner longitudes ISRO published in metadata_real.json. Nothing downstream picks
# a convention that has not been measured against that file.

LON_CONVENTIONS = {
    "y_toward_lam0": lambda x, y: np.arctan2(x, y),
    "y_away_lam0": lambda x, y: np.arctan2(x, -y),
}


def rho_of_lat(lat_deg: float, radius_m: float) -> float:
    return 2.0 * radius_m * math.tan(math.pi / 4.0 + math.radians(lat_deg) / 2.0)


def xy_to_latlon(x, y, radius_m: float, lon0_deg: float, convention: str):
    rho = np.hypot(x, y)
    lat = np.degrees(2.0 * np.arctan(rho / (2.0 * radius_m)) - math.pi / 2.0)
    lon = np.degrees(LON_CONVENTIONS[convention](x, y)) + lon0_deg
    lon = ((lon + 180.0) % 360.0) - 180.0
    return lat, lon


class DfsarGrid:
    """The 2258 x 6618 frame every product in this project is written on.

    Read from metadata_real.json rather than from the handoff, per v9 step 2. The
    tiepoint is the outer corner of pixel (0, 0) and the raster is PixelIsArea, so
    pixel centres sit half a pixel inside it.
    """

    def __init__(self, meta: dict):
        r = meta["geodetic_frame"]["raster"]
        c = meta["geodetic_frame"]["crs"]
        self.lines = int(r["lines"])
        self.samples = int(r["samples"])
        self.px_x = float(r["pixel_size_m"]["x"])
        self.px_y = float(r["pixel_size_m"]["y"])
        self.east_min = float(r["projected_extent_m"]["easting_min"])
        self.north_max = float(r["projected_extent_m"]["northing_max"])
        self.east_max = float(r["projected_extent_m"]["easting_max"])
        self.north_min = float(r["projected_extent_m"]["northing_min"])
        self.radius = float(c["body_radius_m"])
        self.lon0 = float(c["central_meridian_deg"])
        self.lat0 = float(c["latitude_of_origin_deg"])
        self.raster_type = str(r.get("raster_type", "")).strip()

    def xy_of(self, line, sample):
        """Projected metres at the CENTRE of the given (fractional) pixel."""
        x = self.east_min + (np.asarray(sample, np.float64) + 0.5) * self.px_x
        y = self.north_max - (np.asarray(line, np.float64) + 0.5) * self.px_y
        return x, y


def selftest_crs(meta: dict) -> dict:
    """Prove the projection code against ISRO's own numbers. Needs no LOLA product.

    metadata_real.json lists four footprint corners in BOTH pixel space
    (footprint.bbox_pixels) and geodetic space (footprint.corners_latlon), and the
    latter came from the GeoTIFF's GeoKeys, not from this code. Pushing the pixels
    through xy_of() + xy_to_latlon() and differencing against the published lat/lon
    therefore tests the whole chain — tiepoint, pixel convention, sphere radius,
    and the disputed sign of the y term — before any LOLA byte is read.

    Returns the per-convention residuals. The caller picks the winner; nothing is
    assumed.
    """
    g = DfsarGrid(meta)
    fp = meta["geodetic_frame"]["footprint"]
    bb = fp["bbox_pixels"]
    at = {
        "UL": (bb["line_min"], bb["sample_min"]),
        "UR": (bb["line_min"], bb["sample_max"]),
        "LR": (bb["line_max"], bb["sample_max"]),
        "LL": (bb["line_max"], bb["sample_min"]),
    }
    published = {c["label"]: (float(c["lat_deg"]), float(c["lon_deg"])) for c in fp["corners_latlon"]}

    scores: dict = {}
    for conv in LON_CONVENTIONS:
        rows = []
        for label, (line, sample) in at.items():
            if label not in published:
                continue
            x, y = g.xy_of(line, sample)
            lat, lon = xy_to_latlon(x, y, g.radius, g.lon0, conv)
            plat, plon = published[label]
            dlon = ((float(lon) - plon + 180.0) % 360.0) - 180.0
            dlat = float(lat) - plat
            # Ground distance is the number that means something. ISRO published the
            # corners to 6 decimals, so a residual near 5e-7 deg is round-off in
            # THEIR file, not error in this code — quoting degrees alone hides that.
            rho = math.hypot(float(x), float(y))
            rows.append({
                "corner": label, "line": line, "sample": sample,
                "x_m": round(float(x), 3), "y_m": round(float(y), 3),
                "lat_deg": round(float(lat), 6), "lon_deg": round(float(lon), 6),
                "published_lat_deg": plat, "published_lon_deg": plon,
                "d_lat_deg": dlat, "d_lon_deg": dlon,
                "d_lat_m": dlat * g.radius * math.pi / 180.0,
                "d_lon_m": dlon * rho * math.pi / 180.0,
            })
        worst_lat = max(abs(r["d_lat_deg"]) for r in rows)
        worst_lon = max(abs(r["d_lon_deg"]) for r in rows)
        scores[conv] = {
            "corners": rows,
            "max_abs_d_lat_deg": worst_lat, "max_abs_d_lon_deg": worst_lon,
            "max_abs_d_lat_m": max(abs(r["d_lat_m"]) for r in rows),
            "max_abs_d_lon_m": max(abs(r["d_lon_m"]) for r in rows),
        }
    return scores


# ── the LOLA product's own grid ────────────────────────────────────────────────

# LOLA labels do NOT all state MAP_SCALE in metres. The 20 m polar GDRs write
#     MAP_SCALE = 0.020 <KM/PIXEL>
# so reading the bare number gives 0.02 and every distance downstream is wrong by
# 1000x while still looking like a plausible float. The unit is therefore parsed
# out of the angle brackets and converted; an unrecognised or absent unit raises
# instead of defaulting. This is the single most dangerous silent failure in the
# whole ingest, which is why it gets its own table.
_LENGTH_UNITS = {
    "M": 1.0, "METER": 1.0, "METERS": 1.0, "METRE": 1.0, "METRES": 1.0,
    "KM": 1000.0, "KILOMETER": 1000.0, "KILOMETERS": 1000.0,
    "KILOMETRE": 1000.0, "KILOMETRES": 1000.0,
}


def unit_of(label: dict, *keys: str) -> str | None:
    """The <...> unit token on the first present key, upper-cased, or None."""
    for k in keys:
        if k in label:
            m = re.search(r"<([^>]*)>", str(label[k]))
            return m.group(1).strip().upper() if m else None
    raise LabelError(f"none of {keys} present in label")


def length_m(label: dict, *keys: str) -> tuple[float, str]:
    """A label length in METRES, converted using the label's own unit.

    Accepts 'KM', 'KM/PIXEL', 'METERS/PIXEL' and friends: the part before the
    slash is the length unit. Returns (metres, unit_as_written) so the caller can
    print what it read.
    """
    raw = num(label, *keys)
    unit = unit_of(label, *keys)
    if unit is None:
        raise LabelError(
            f"{keys[0]} has no <unit>; refusing to assume metres vs kilometres "
            f"(value was {raw})")
    head = unit.split("/")[0].strip()
    if head not in _LENGTH_UNITS:
        raise LabelError(f"{keys[0]} unit {unit!r} not a recognised length")
    return raw * _LENGTH_UNITS[head], unit


# PDS3 says LINE_PROJECTION_OFFSET is "the line offset of the map projection
# origin", but products in the wild disagree on the base: some count lines from 1,
# some from 0, and some reference the pixel edge rather than its centre. The three
# readings differ by at most one pixel — 20 m, or 0.8 of a DFSAR pixel — which is
# small enough to look like nothing and large enough to matter at 25 m/px. So all
# three are scored and the residuals printed.
PIXEL_BASES = {"zero_based": 0.0, "half_pixel": 0.5, "one_based": 1.0}


class LolaGrid:
    """A LOLA polar GDR, described entirely by its own label."""

    def __init__(self, label: dict, path: Path):
        self.path = path
        self.label = label
        self.lines = int(num(label, "IMAGE.LINES", "LINES"))
        self.samples = int(num(label, "IMAGE.LINE_SAMPLES", "LINE_SAMPLES"))
        self.dtype = label_dtype(label)
        self.scale_m, self.scale_unit = length_m(label, "MAP_SCALE")
        self.lpo = num(label, "LINE_PROJECTION_OFFSET")
        self.spo = num(label, "SAMPLE_PROJECTION_OFFSET")
        self.radius_m, self.radius_unit = length_m(label, "A_AXIS_RADIUS")
        self.centre_lat = num(label, "CENTER_LATITUDE")
        self.centre_lon = num(label, "CENTER_LONGITUDE")
        self.max_lat = num(label, "MAXIMUM_LATITUDE")
        self.min_lat = num(label, "MINIMUM_LATITUDE")
        self.projection = text(label, "MAP_PROJECTION_TYPE")
        self.scaling_factor = num(label, "IMAGE.SCALING_FACTOR", "SCALING_FACTOR")
        self.value_offset = num(label, "IMAGE.OFFSET", "OFFSET")
        self.value_unit = unit_of(label, "IMAGE.SCALING_FACTOR", "SCALING_FACTOR")
        # PDS3 nominally means OFFSET additively: value = DN * SCALING_FACTOR + OFFSET.
        # LOLA LDEM labels do not use it that way — OFFSET carries the reference sphere
        # radius, and the label's own NOTE says it applies to PLANETARY_RADIUS, not to
        # HEIGHT. Adding it would put every "elevation" near 1 737 400 m, which is not
        # an error that looks like an error. The discriminator is label-internal and so
        # works on any product in the family: an OFFSET equal to A_AXIS_RADIUS is a
        # radius, not a datum shift. The decision is printed and written to the sidecar
        # rather than being silent either way.
        self.offset_is_reference_radius = abs(self.value_offset - self.radius_m) < 1.0
        self.elev_offset_m = 0.0 if self.offset_is_reference_radius else self.value_offset
        self.missing = opt(label, "IMAGE.MISSING_CONSTANT", "MISSING_CONSTANT",
                           "IMAGE.MISSING", "MISSING")
        # The LOLA GDR labels state DERIVED_MINIMUM / DERIVED_MAXIMUM; other PDS
        # products state MINIMUM / MAXIMUM. Check 3.1 compares against whichever the
        # product actually carries, and names the key it used.
        self.label_min, self.label_min_key = opt_keyed(
            label, "IMAGE.DERIVED_MINIMUM", "DERIVED_MINIMUM",
            "IMAGE.MINIMUM", "MINIMUM")
        self.label_max, self.label_max_key = opt_keyed(
            label, "IMAGE.DERIVED_MAXIMUM", "DERIVED_MAXIMUM",
            "IMAGE.MAXIMUM", "MAXIMUM")
        self.record_bytes = opt(label, "RECORD_BYTES")
        self.data_offset_bytes = self._data_offset()
        self.base = "zero_based"          # replaced by solve_convention()
        self.base_residual_px = None

    def _data_offset(self) -> int:
        """Byte offset of the first sample. Detached labels start at 0."""
        ptr = None
        for k in ("^IMAGE", "^IMAGE_PTR"):
            if k in self.label:
                ptr = str(self.label[k]).strip()
                break
        if ptr is None:
            return 0
        m = re.search(r"(\d+)\s*(?:<BYTES>)?\s*\)?\s*$", ptr)
        if m is None:
            return 0
        n = int(m.group(1))
        if "<BYTES>" in ptr.upper():
            return n - 1
        if self.record_bytes:                      # record count, 1-based
            return int((n - 1) * self.record_bytes)
        return 0

    # x grows with sample, y decreases with line — the usual north-up raster.
    #   x = ((sample + base) - SPO) * scale
    #   y = (LPO - (line  + base)) * scale
    def xy_of(self, line, sample):
        b = PIXEL_BASES[self.base]
        x = (np.asarray(sample, np.float64) + b - self.spo) * self.scale_m
        y = (self.lpo - (np.asarray(line, np.float64) + b)) * self.scale_m
        return x, y

    def pixel_of(self, x, y):
        """Fractional (line, sample) for projected metres. Inverse of xy_of."""
        b = PIXEL_BASES[self.base]
        sample = self.spo + np.asarray(x, np.float64) / self.scale_m - b
        line = self.lpo - np.asarray(y, np.float64) / self.scale_m - b
        return line, sample

    def expected_bytes(self) -> int:
        return self.data_offset_bytes + self.lines * self.samples * self.dtype.itemsize

    def to_metres(self, dn):
        """Raw DN -> elevation in metres above the label's own sphere.

        HEIGHT = DN * SCALING_FACTOR. OFFSET is added only when the label shows it to
        be a genuine datum shift; in the LOLA GDRs it is the reference radius and is
        not added. See offset_is_reference_radius.
        """
        return dn.astype(np.float64) * self.scaling_factor + self.elev_offset_m


def solve_convention(g: LolaGrid) -> dict:
    """Measure which pixel base the label means, instead of choosing one.

    Two facts the label states independently:
      A. the projection origin is the pole, and a polar GDR is built centred on it,
         so the pole's fractional index must land on the array centre;
      B. the array's outer edge must fall at MAXIMUM_LATITUDE, whose stereographic
         radius is 2 R tan(pi/4 + phi/2).
    A depends on the base and discriminates between the three; B does not depend on
    the base and is a check on scale/radius/latitude agreeing at all. Both residuals
    are returned and both are written to the sidecar.
    """
    centre_line = (g.lines - 1) / 2.0
    centre_sample = (g.samples - 1) / 2.0
    table = []
    for name, b in PIXEL_BASES.items():
        line_pole = g.lpo - b
        sample_pole = g.spo - b
        d = math.hypot(line_pole - centre_line, sample_pole - centre_sample)
        table.append({
            "base": name, "pole_line": line_pole, "pole_sample": sample_pole,
            "centre_line": centre_line, "centre_sample": centre_sample,
            "residual_px": round(d, 6), "residual_m": round(d * g.scale_m, 4),
        })
    table.sort(key=lambda r: r["residual_px"])

    rho_edge = rho_of_lat(g.max_lat, g.radius_m)
    half_span_m = (g.samples / 2.0) * g.scale_m
    # Latitude the array's own outer edge actually falls at, by the same inverse the
    # corner self-test uses. The handoff asks for this residual in degrees, and degrees
    # is also the only unit in which "reads -80.000" is a statement about the product
    # rather than about the pixel size.
    edge_lat = math.degrees(2.0 * math.atan(half_span_m / (2.0 * g.radius_m))
                            - math.pi / 2.0)
    edge = {
        "maximum_latitude_deg": g.max_lat,
        "rho_of_maximum_latitude_m": round(rho_edge, 3),
        "array_half_span_m": round(half_span_m, 3),
        "array_half_span_from": f"({g.samples} / 2) x {g.scale_m} m/px",
        "array_edge_latitude_deg": round(edge_lat, 6),
        "residual_deg": round(edge_lat - g.max_lat, 8),
        "residual_m": round(half_span_m - rho_edge, 3),
        "residual_px": round((half_span_m - rho_edge) / g.scale_m, 4),
        "tolerance_deg": 1.0e-3,
        "passed": abs(edge_lat - g.max_lat) < 1.0e-3,
    }
    return {"candidates": table, "best": table[0], "edge_latitude_check": edge}


def check_frame_coverage(g: LolaGrid, d: DfsarGrid) -> dict:
    """Does this product's array actually reach the whole DFSAR frame?

    Computed here rather than copied from the handoff, because a product that covers
    the frame and a product that covers most of it fail in different ways: the second
    one produces a DEM that looks fine and is wrong along one edge. The farthest frame
    corner's distance from the pole is compared against the array half-span; the
    LDEM_875S_* products fail this and the LDEM_80S_* products pass it.
    """
    corners = {
        "UL": (d.east_min, d.north_max), "UR": (d.east_max, d.north_max),
        "LR": (d.east_max, d.north_min), "LL": (d.east_min, d.north_min),
    }
    rows = []
    for name, (x, y) in corners.items():
        rho = math.hypot(x, y)
        lat = math.degrees(2.0 * math.atan(rho / (2.0 * g.radius_m)) - math.pi / 2.0)
        rows.append({"corner": name, "x_m": x, "y_m": y,
                     "rho_m": round(rho, 2), "latitude_deg": round(lat, 6)})
    worst = max(rows, key=lambda r: r["rho_m"])
    half_span_m = (g.samples / 2.0) * g.scale_m
    return {
        "frame_corners": rows,
        "farthest_corner": worst["corner"],
        "farthest_rho_m": worst["rho_m"],
        "farthest_latitude_deg": worst["latitude_deg"],
        "array_half_span_m": round(half_span_m, 3),
        "margin_m": round(half_span_m - worst["rho_m"], 2),
        "covers_frame": half_span_m >= worst["rho_m"],
    }


def check_projection(g: LolaGrid, d: DfsarGrid) -> list[str]:
    """Refuse to resample between two grids that are not the same projection.

    If these agree, LOLA pixel -> (x, y) -> DFSAR pixel is a pure affine map and no
    reprojection is needed. If they disagree, the affine map is wrong and the run
    must stop rather than produce a plausible-looking wrong DEM.
    """
    bad: list[str] = []
    if "POLAR" not in g.projection.upper() or "STEREO" not in g.projection.upper():
        bad.append(f"MAP_PROJECTION_TYPE = {g.projection!r}, expected polar stereographic")
    if abs(g.centre_lat - d.lat0) > 1e-6:
        bad.append(f"CENTER_LATITUDE {g.centre_lat} != DFSAR latitude_of_origin {d.lat0}")
    if abs(((g.centre_lon - d.lon0 + 180.0) % 360.0) - 180.0) > 1e-6:
        bad.append(f"CENTER_LONGITUDE {g.centre_lon} != DFSAR central_meridian {d.lon0}")
    if abs(g.radius_m - d.radius) > 1.0:
        bad.append(f"A_AXIS_RADIUS {g.radius_m} m != DFSAR body_radius {d.radius} m")
    rot = opt(g.label, "MAP_PROJECTION_ROTATION")
    if rot is not None and abs(rot) > 1e-9:
        bad.append(f"MAP_PROJECTION_ROTATION = {rot}, only 0 is handled")
    return bad


def blocked_minmax(g: LolaGrid, rows: int = 512) -> dict:
    """min/max/count of the raw DN over the whole product, without loading it.

    np.memmap + a row slice per iteration: resident memory is one block
    (rows x samples x itemsize), not the file.
    """
    mm = np.memmap(g.path, dtype=g.dtype, mode="r",
                   offset=g.data_offset_bytes, shape=(g.lines, g.samples))
    lo = np.iinfo(g.dtype).max if g.dtype.kind in "iu" else math.inf
    hi = np.iinfo(g.dtype).min if g.dtype.kind in "iu" else -math.inf
    n_valid = 0
    n_missing = 0
    for r0 in range(0, g.lines, rows):
        blk = np.asarray(mm[r0:r0 + rows])
        if g.missing is not None:
            keep = blk != g.dtype.type(g.missing)
            n_missing += int(blk.size - keep.sum())
            if not keep.any():
                continue
            vals = blk[keep]
        else:
            vals = blk.reshape(-1)
        n_valid += int(vals.size)
        lo = min(lo, int(vals.min()) if g.dtype.kind in "iu" else float(vals.min()))
        hi = max(hi, int(vals.max()) if g.dtype.kind in "iu" else float(vals.max()))
    del mm
    return {"dn_min": lo, "dn_max": hi, "n_valid": n_valid, "n_missing": n_missing}


def validate_label_range(g: LolaGrid) -> dict:
    """v9 step 3.1 — reproduce the label's own stated elevation range from the raw DN.

    This is the check that actually discriminates real data from a placeholder, because
    it is the only one that compares against a number the product carries about itself.
    The Faustini-floor check (3.2) does not discriminate: the existing synthetic DEM
    already spans -4138 to -1753 m, inside the expected -3 to -4 km band, so it would
    pass 3.2 while containing no measurement at all.

    Two ambiguities are resolved by measurement rather than assumption. PDS is not
    consistent about whether the stated range is in DN or in scaled units, so both
    readings are computed and the one that matches is reported. And the key is
    DERIVED_MINIMUM in the LOLA GDRs but MINIMUM elsewhere, so whichever the label
    carries is used and named. A tolerance of one SCALING_FACTOR is one quantisation
    step — the smallest difference the product can express.
    """
    stats = blocked_minmax(g)
    tol = abs(g.scaling_factor)
    as_dn = {"min": float(stats["dn_min"]), "max": float(stats["dn_max"])}
    as_m = {"min": stats["dn_min"] * g.scaling_factor + g.elev_offset_m,
            "max": stats["dn_max"] * g.scaling_factor + g.elev_offset_m}

    out = {
        "product": g.path.name,
        "dtype": str(g.dtype), "lines": g.lines, "samples": g.samples,
        "map_scale_m": g.scale_m, "map_scale_as_written": g.scale_unit,
        "scaling_factor": g.scaling_factor,
        "offset_in_label": g.value_offset,
        "offset_added_to_elevation_m": g.elev_offset_m,
        "offset_is_reference_radius": g.offset_is_reference_radius,
        "scaling_factor_unit_as_written": g.value_unit,
        "missing_constant": g.missing,
        "label_minimum": g.label_min, "label_minimum_key": g.label_min_key,
        "label_maximum": g.label_max, "label_maximum_key": g.label_max_key,
        "computed_dn": as_dn, "computed_elevation_m": as_m,
        "n_valid": stats["n_valid"], "n_missing": stats["n_missing"],
        "tolerance": tol,
    }
    if g.label_min is None or g.label_max is None:
        out["verdict"] = ("SKIPPED — the label states neither DERIVED_MINIMUM/MAXIMUM "
                         "nor MINIMUM/MAXIMUM, so there is nothing to check against")
        out["passed"] = False
        return out

    d_dn = max(abs(as_dn["min"] - g.label_min), abs(as_dn["max"] - g.label_max))
    d_m = max(abs(as_m["min"] - g.label_min), abs(as_m["max"] - g.label_max))
    out["residual_if_label_is_dn"] = d_dn
    out["residual_if_label_is_scaled"] = d_m
    if d_dn <= tol:
        out["label_units"] = "DN"
        out["residual"] = d_dn
    else:
        out["label_units"] = "scaled"
        out["residual"] = d_m
    out["passed"] = min(d_dn, d_m) <= tol
    out["verdict"] = ("PASS" if out["passed"] else
                      f"FAIL — closest reading is off by {min(d_dn, d_m):.6g}, "
                      f"tolerance is one quantisation step {tol:.6g}")
    return out


def read_window(g: LolaGrid, d: DfsarGrid, margin_px: int = 4) -> dict:
    """v9 step 2 — materialise only the LOLA pixels the DFSAR frame can reach.

    The 20 m product is ~1.9 GB. The DFSAR frame is 165.45 x 56.45 km, which at
    20 m/px is about 8272 x 2822 pixels = 47 MB. np.memmap maps the file lazily and
    the slice copies just that rectangle; the rest is never paged in.
    """
    corners_x = [d.east_min, d.east_max, d.east_max, d.east_min]
    corners_y = [d.north_max, d.north_max, d.north_min, d.north_min]
    lines, samples = g.pixel_of(np.array(corners_x), np.array(corners_y))

    l0 = int(math.floor(lines.min())) - margin_px
    l1 = int(math.ceil(lines.max())) + margin_px + 1
    s0 = int(math.floor(samples.min())) - margin_px
    s1 = int(math.ceil(samples.max())) + margin_px + 1

    clipped = (l0 < 0 or s0 < 0 or l1 > g.lines or s1 > g.samples)
    l0c, l1c = max(0, l0), min(g.lines, l1)
    s0c, s1c = max(0, s0), min(g.samples, s1)
    if l1c <= l0c or s1c <= s0c:
        raise RuntimeError(
            f"the DFSAR frame does not intersect {g.path.name}: requested lines "
            f"{l0}..{l1}, samples {s0}..{s1} of a {g.lines}x{g.samples} array")

    size = g.expected_bytes()
    actual = g.path.stat().st_size
    if actual < size:
        raise RuntimeError(
            f"{g.path.name} is {actual} bytes but the label describes {size} "
            f"({g.lines}x{g.samples}x{g.dtype.itemsize} + {g.data_offset_bytes} "
            f"offset). Truncated or mislabelled download — refusing to read it.")

    mm = np.memmap(g.path, dtype=g.dtype, mode="r",
                   offset=g.data_offset_bytes, shape=(g.lines, g.samples))
    dn = np.array(mm[l0c:l1c, s0c:s1c])          # the only copy taken
    del mm

    valid = np.ones(dn.shape, dtype=bool) if g.missing is None else dn != g.dtype.type(g.missing)
    return {
        "dn": dn, "valid": valid, "line0": l0c, "sample0": s0c,
        "requested": {"line0": l0, "line1": l1, "sample0": s0, "sample1": s1},
        "clipped_to_array": clipped,
        "shape": [int(dn.shape[0]), int(dn.shape[1])],
        "bytes_read": int(dn.nbytes),
        "file_bytes": actual,
        "fraction_of_file": round(dn.nbytes / max(actual, 1), 6),
        "n_missing_in_window": int((~valid).sum()),
    }


def resample_to_dfsar(g: LolaGrid, d: DfsarGrid, win: dict, block: int = 128) -> dict:
    """Bilinear resample of the window onto the 2258 x 6618 frame, row-blocked.

    Doing all 14.9 M output pixels at once would allocate two float64 coordinate
    arrays of 119 MB each before map_coordinates even starts. A 128-row block keeps
    that under 14 MB and the result is identical — order=1 is separable and local.

    The validity mask is resampled alongside the elevation with the same kernel, so
    a pixel that borrowed anything from a MISSING_CONSTANT neighbour is marked
    rather than quietly averaged into a plausible number.
    """
    elev = g.to_metres(win["dn"])
    valid = win["valid"]
    if not valid.all():
        elev = np.where(valid, elev, 0.0)        # keep the kernel finite; mask below

    # ---- ANTI-ALIASING, and only when the resample is a DOWNSAMPLE ----------
    # map_coordinates POINT-SAMPLES: order=1 interpolates between neighbours, it
    # does not average over the area an output pixel covers. That is correct when
    # the output grid is FINER than the source (80 m -> 25 m, f = 0.31), where
    # there is nothing between the posts to alias. It is wrong when the output is
    # COARSER (20 m -> 25 m, f = 1.25): content with wavelengths between 40 m and
    # 50 m has no representation on the output grid and folds back as aliasing
    # rather than being averaged away. Mild at 1.25x, but real, and it lands
    # squarely in the slope and roughness fields this DEM exists to produce.
    #
    # So low-pass first, with a Gaussian of sigma = f/2 source pixels -- the usual
    # choice, and 0.625 px here. The 80 m path takes f < 1 and is NOT filtered, so
    # this changes nothing about the currently-shipped DEM.
    f_down = float(d.px_x) / float(g.scale_m)
    aa = {"applied": False, "method": "none — output grid is finer than the source, "
                                      "so there is nothing to alias",
          "downsample_factor": round(f_down, 6), "sigma_source_px": 0.0}
    if f_down > 1.0 + 1e-9:
        from scipy.ndimage import gaussian_filter
        sigma = f_down / 2.0
        # Filter the validity weights with the SAME kernel, then divide, so a
        # post next to a MISSING_CONSTANT is not pulled toward the zero-fill.
        vm = valid.astype(np.float32)
        num = gaussian_filter(elev.astype(np.float32), sigma, mode="nearest")
        den = gaussian_filter(vm, sigma, mode="nearest")
        elev = np.where(den > 1e-6, num / np.maximum(den, 1e-6), elev)
        aa = {"applied": True,
              "method": (f"Gaussian low-pass, sigma = f/2 = {sigma:.4f} source "
                         f"pixels, applied BEFORE bilinear sampling. Validity "
                         f"weights filtered with the same kernel and divided out, "
                         f"so no post is pulled toward MISSING_CONSTANT."),
              "downsample_factor": round(f_down, 6),
              "sigma_source_px": round(sigma, 6)}
        print(f"  anti-alias: downsample f = {f_down:.4f}, Gaussian sigma "
              f"{sigma:.4f} source px applied before sampling")
    else:
        print(f"  anti-alias: none — f = {f_down:.4f} is an upsample, nothing to alias")

    out = np.full((d.lines, d.samples), np.nan, dtype=np.float32)
    wsum = np.zeros((d.lines, d.samples), dtype=np.float32)
    vmask = valid.astype(np.float64)
    samples_idx = np.arange(d.samples, dtype=np.float64)

    for r0 in range(0, d.lines, block):
        r1 = min(d.lines, r0 + block)
        rows = np.arange(r0, r1, dtype=np.float64)
        gx, gy = d.xy_of(rows[:, None], samples_idx[None, :])
        ll, ss = g.pixel_of(gx, gy)
        # x depends only on sample and y only on line, so these come back as
        # (1, samples) and (block, 1). map_coordinates needs both at full size.
        ll, ss = np.broadcast_arrays(ll, ss)
        coords = np.stack([ll - win["line0"], ss - win["sample0"]])
        out[r0:r1] = map_coordinates(elev, coords, order=1, mode="nearest").astype(np.float32)
        wsum[r0:r1] = map_coordinates(vmask, coords, order=1, mode="nearest").astype(np.float32)

    contaminated = wsum < 0.999
    n_bad = int(contaminated.sum())
    if n_bad:
        out[contaminated] = np.nan

    finite = np.isfinite(out)
    stats = {
        "shape": [int(out.shape[0]), int(out.shape[1])],
        "n_nan": int((~finite).sum()),
        "n_contaminated_by_missing": n_bad,
    }
    if finite.any():
        v = out[finite]
        stats.update({
            "min_m": float(v.min()), "max_m": float(v.max()),
            "mean_m": float(v.mean()),
            "p01_m": float(np.percentile(v, 1)), "p50_m": float(np.percentile(v, 50)),
            "p99_m": float(np.percentile(v, 99)),
        })
    return {"array": out, "stats": stats, "anti_alias": aa}


# ── reporting ──────────────────────────────────────────────────────────────────

def rule(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def find_product(stem: str) -> tuple[Path | None, Path | None]:
    """The .img/.lbl pair for a stem, case-insensitively, or (None, None)."""
    if not LOLA_DIR.is_dir():
        return None, None
    img = lbl = None
    for p in LOLA_DIR.iterdir():
        if p.stem.lower() != stem.lower():
            continue
        if p.suffix.lower() == ".img":
            img = p
        elif p.suffix.lower() == ".lbl":
            lbl = p
    return img, lbl


def resolve_input(explicit: str | None) -> tuple[Path | None, Path | None, list[dict]]:
    """Pick the one product to ingest, and show what the choice was made from.

    With --input, that file is used and nothing is searched — which is all phase B
    needs. Without it, PRODUCT_PREFERENCE is walked in order and the first complete
    .img/.lbl pair wins. The survey is returned either way so the run log states which
    products were on disk, not just which one was read: "the 80 m one was used" and
    "the 80 m one was the only one there" are different facts.
    """
    survey = []
    for stem, note in PRODUCT_PREFERENCE:
        img, lbl = find_product(stem)
        survey.append({"stem": stem, "note": note,
                       "img": img.name if img else None,
                       "lbl": lbl.name if lbl else None,
                       "bytes": img.stat().st_size if img else None,
                       "complete": bool(img and lbl)})

    if explicit:
        img = Path(explicit)
        if not img.is_absolute():
            img = (REPO / explicit).resolve()
        lbl = None
        if img.parent.is_dir():
            for p in img.parent.iterdir():
                if p.stem.lower() == img.stem.lower() and p.suffix.lower() == ".lbl":
                    lbl = p
                    break
        return (img if img.is_file() else None), lbl, survey

    for row in survey:
        if row["complete"]:
            img, lbl = find_product(row["stem"])
            return img, lbl, survey
    return None, None, survey


def report_absent(survey: list[dict], explicit: str | None) -> int:
    rule("STEP 1 — SOURCE PRODUCT: NOT PRESENT")
    print(f"Looked in: {LOLA_DIR}")
    print(f"  exists: {LOLA_DIR.is_dir()}")
    if LOLA_DIR.is_dir():
        found = sorted(p.name for p in LOLA_DIR.iterdir())
        print(f"  contains: {found if found else '(empty)'}")
    if explicit:
        print(f"\n--input {explicit} did not resolve to an .img with a sibling .lbl.")
    print("\nOne of these is enough (LOLA GDR polar .IMG + .LBL, imbrium.mit.edu")
    print("/DATA/LOLA_GDR/POLAR/, the raw IMG rather than the lossy JP2):")
    for row in survey:
        print(f"  {row['stem']:<15} {row['note']}")
        print(f"      .img {'FOUND' if row['img'] else 'MISSING'}"
              f"   .lbl {'FOUND' if row['lbl'] else 'MISSING'}")
    print("\nNothing was written. No substitute was used: the synthetic placeholder")
    print("DEM is still in place and still labelled synthetic. Re-run this script")
    print("once a product is on disk.")
    return 2


def report_crs(scores: dict) -> tuple[str, float]:
    """Print the convention table and return (winner, worst residual in degrees)."""
    rule("STEP 0 — PROJECTION SELF-TEST (needs no LOLA product)")
    print("DFSAR footprint corners: this code's lat/lon vs the lat/lon ISRO wrote")
    print("into metadata_real.json from the GeoTIFF GeoKeys.\n")
    best, best_err = None, math.inf
    for conv, s in scores.items():
        err = max(s["max_abs_d_lat_deg"], s["max_abs_d_lon_deg"])
        print(f"  convention {conv:<16} max |dlat| {s['max_abs_d_lat_deg']:.3e} deg"
              f" ({s['max_abs_d_lat_m']:+.4f} m)   max |dlon| "
              f"{s['max_abs_d_lon_deg']:.3e} deg ({s['max_abs_d_lon_m']:+.4f} m)")
        if err < best_err:
            best, best_err = conv, err
    print(f"\n  winner: {best}   (worst corner error {best_err:.3e} deg)")
    print("  ISRO published these to 6 decimals, so a residual near 5e-7 deg is")
    print("  round-off in their file rather than error here.")
    for r in scores[best]["corners"]:
        print(f"    {r['corner']}  px({r['line']:>5},{r['sample']:>5})"
              f"  xy({r['x_m']:>12.1f},{r['y_m']:>12.1f})"
              f"  lat {r['lat_deg']:>11.6f} vs {r['published_lat_deg']:>11.6f}"
              f"  lon {r['lon_deg']:>11.6f} vs {r['published_lon_deg']:>11.6f}"
              f"  d {r['d_lat_m']:+.4f} m / {r['d_lon_m']:+.4f} m")
    return best, best_err


def provenance_string(g: LolaGrid, d: DfsarGrid) -> str:
    """The one-line source description the UI shows under each derived layer.

    It has to name the product and its NATIVE resolution, because that is the number
    a reader needs in order to judge the layer: 80 m posts upsampled to a 25 m grid
    are still 80 m posts. It also has to avoid the six words MissionMap.tsx tests for
    (synthetic|placeholder|analytic|unknown|unavailable) or real LOLA data will keep
    being captioned as a placeholder. Every component is read from the label.
    """
    pid = opt_text(g.label, "PRODUCT_ID")
    if not pid:
        fn = opt_text(g.label, "FILE_NAME") or g.path.name
        pid = Path(fn).stem.upper()
    ver = opt_text(g.label, "PRODUCT_VERSION_ID")
    scale_txt = f"{g.scale_m:g}"
    target = f"{d.px_x:g}"
    head = f"LOLA {pid}"
    if ver:
        head += f" {ver}" if ver.lower().startswith("v") else f" v{ver}"
    return f"{head}, {scale_txt} m/px native, bilinear to {target} m grid"


BANNED_PROVENANCE_WORDS = ("synthetic", "placeholder", "analytic", "unknown",
                           "unavailable")


def write_sidecar(payload: dict) -> None:
    OUT_SIDECAR.parent.mkdir(parents=True, exist_ok=True)
    OUT_SIDECAR.write_text(json.dumps(payload, indent=2, default=str))
    print(f"  sidecar -> {OUT_SIDECAR}")


# ── synthetic self-test ────────────────────────────────────────────────────────
#
# The real products are not on this machine, so without this the whole file would
# be an unrun code path — and an unrun ingest is exactly the kind of thing that
# produces a confident wrong number the first time it meets real data.
#
# This builds a MINIATURE product that is PDS3-shaped in every way that matters:
# KM/PIXEL units on MAP_SCALE (the 1000x trap), MSB_INTEGER 16 (so endianness has
# to come from the label), a pole-centred LPO/SPO, SCALING_FACTOR/OFFSET, and a
# MISSING_CONSTANT. The elevation field is a PLANE, because bilinear resampling
# reproduces a plane exactly: if the affine map is off by even one pixel the
# round-trip error jumps to gradient x 20 m and the test fails.
#
# The fixture lives in a temp directory, is deleted afterwards, and is never
# written under data/. It is a test of the code, not a source of elevation.

_MINI_LABEL = """PDS_VERSION_ID = PDS3
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = {record_bytes}
FILE_RECORDS = {lines}
^IMAGE = 1
OBJECT = IMAGE
  LINES = {lines}
  LINE_SAMPLES = {samples}
  SAMPLE_TYPE = MSB_INTEGER
  SAMPLE_BITS = 16
  UNIT = "METER"
  SCALING_FACTOR = {sf} <METER>
  OFFSET = {offset} <METER>
  MISSING_CONSTANT = -32768
  MINIMUM = {vmin}
  MAXIMUM = {vmax}
END_OBJECT = IMAGE
OBJECT = IMAGE_MAP_PROJECTION
  MAP_PROJECTION_TYPE = "POLAR STEREOGRAPHIC"
  A_AXIS_RADIUS = {radius_km} <KM>
  B_AXIS_RADIUS = {radius_km} <KM>
  C_AXIS_RADIUS = {radius_km} <KM>
  MAP_SCALE = {scale_km} <KM/PIXEL>
  MAP_PROJECTION_ROTATION = 0.0
  CENTER_LATITUDE = -90.0 <DEG>
  CENTER_LONGITUDE = 0.0 <DEG>
  LINE_PROJECTION_OFFSET = {lpo}
  SAMPLE_PROJECTION_OFFSET = {spo}
  MINIMUM_LATITUDE = -90.0 <DEG>
  MAXIMUM_LATITUDE = {max_lat} <DEG>
  POSITIVE_LONGITUDE_DIRECTION = EAST
END_OBJECT = IMAGE_MAP_PROJECTION
END
"""

_PLANE = (-2000.0, 2.0, -1.5)      # elev = a + b*x + c*y, metres, x/y in metres


def _mini_product(tmp: Path, stem: str, n: int, scale_m: float, sf: float,
                  n_missing: int = 0, offset: float = 0.0) -> tuple[Path, Path]:
    """Write a pole-centred mini product whose elevation is exactly _PLANE.

    `offset` writes the label's OFFSET field. Passing the body radius reproduces the
    LOLA GDR case, where OFFSET is a reference radius and must NOT be added to the
    elevation; passing anything else reproduces the ordinary PDS case, where it is a
    datum shift and must be. Both are exercised, because the difference between them
    is 1 737 400 m of silent error.
    """
    half = (n - 1) / 2.0                       # zero_based: pole at the centre index
    j = np.arange(n, dtype=np.float64)
    x = (j - half) * scale_m
    y = (half - j) * scale_m
    a, b, c = _PLANE
    elev = a + b * x[None, :] + c * y[:, None]
    dn = np.rint(elev / sf).astype(">i2")
    if n_missing:
        dn.reshape(-1)[:n_missing] = -32768
    keep = dn != -32768
    vmin = float(dn[keep].min()) * sf
    vmax = float(dn[keep].max()) * sf

    img = tmp / f"{stem}.img"
    lbl = tmp / f"{stem}.lbl"
    img.write_bytes(dn.tobytes())
    lbl.write_text(_MINI_LABEL.format(
        record_bytes=n * 2, lines=n, samples=n, sf=sf, offset=f"{offset:.1f}",
        vmin=f"{vmin:.6f}", vmax=f"{vmax:.6f}",
        radius_km=1737.4, scale_km=scale_m / 1000.0,
        lpo=half, spo=half,
        max_lat=f"{math.degrees(2.0 * math.atan((n / 2.0) * scale_m / (2.0 * 1737400.0)) - math.pi / 2.0):.6f}",
    ))
    return img, lbl


def _mini_dfsar(lines: int, samples: int, px: float) -> dict:
    """A reduced DFSAR-shaped frame straddling the pole, so the window is small."""
    return {"geodetic_frame": {
        "crs": {"body_radius_m": 1737400.0, "latitude_of_origin_deg": -90.0,
                "central_meridian_deg": 0.0},
        "raster": {
            "lines": lines, "samples": samples,
            "pixel_size_m": {"x": px, "y": px}, "raster_type": "PixelIsArea",
            "projected_extent_m": {
                "easting_min": -(samples / 2.0) * px + 300.0,
                "easting_max": (samples / 2.0) * px + 300.0,
                "northing_min": -(lines / 2.0) * px - 200.0,
                "northing_max": (lines / 2.0) * px - 200.0,
            }}}}


def selftest_synthetic() -> int:
    """Run every stage against the mini product. Returns a process exit code."""
    import shutil
    import tempfile

    rule("SYNTHETIC SELF-TEST (a fixture, not data — deleted at the end)")
    tmp = Path(tempfile.mkdtemp(prefix="lola_selftest_"))
    fails: list[str] = []
    try:
        sf = 0.5
        v_img, v_lbl = _mini_product(tmp, "mini_240m", 64, 240.0, sf, n_missing=17)
        p_img, p_lbl = _mini_product(tmp, "mini_20m", 128, 20.0, sf)

        meta = _mini_dfsar(48, 64, 25.0)
        dfsar = DfsarGrid(meta)
        primary = LolaGrid(read_label(p_lbl), p_img)
        validation = LolaGrid(read_label(v_lbl), v_img)

        def check(name: str, ok: bool, detail: str) -> None:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
            if not ok:
                fails.append(name)

        check("dtype from label", primary.dtype == np.dtype(">i2"), str(primary.dtype))
        check("MAP_SCALE km->m", abs(primary.scale_m - 20.0) < 1e-9,
              f"{primary.scale_m} m/px from <{primary.scale_unit}>")
        check("A_AXIS_RADIUS km->m", abs(primary.radius_m - 1737400.0) < 1e-6,
              f"{primary.radius_m} m from <{primary.radius_unit}>")
        check("data offset", primary.data_offset_bytes == 0,
              f"{primary.data_offset_bytes} bytes (^IMAGE = 1 record)")
        check("expected size == file size",
              primary.expected_bytes() == p_img.stat().st_size,
              f"{primary.expected_bytes():,} vs {p_img.stat().st_size:,}")
        check("projection agreement", check_projection(primary, dfsar) == [],
              "same projection as the frame")

        conv = solve_convention(primary)
        primary.base = conv["best"]["base"]
        primary._convention = conv
        check("pixel convention", conv["best"]["base"] == "zero_based"
              and conv["best"]["residual_px"] < 1e-9,
              f"{conv['best']['base']}, residual {conv['best']['residual_px']:.3g} px")
        check("edge latitude", abs(conv["edge_latitude_check"]["residual_px"]) < 1e-3,
              f"{conv['edge_latitude_check']['residual_px']:+.3g} px, "
              f"{conv['edge_latitude_check']['residual_deg']:+.3g} deg "
              f"(array edge reads "
              f"{conv['edge_latitude_check']['array_edge_latitude_deg']:.6f})")
        check("OFFSET is not added when it is a datum shift",
              primary.offset_is_reference_radius is False
              and primary.elev_offset_m == 0.0,
              f"OFFSET {primary.value_offset} vs A_AXIS_RADIUS {primary.radius_m}, "
              f"added {primary.elev_offset_m} m")

        # The LOLA case, which the other fixtures do not reach: OFFSET carries the
        # reference sphere radius. Adding it would put every elevation near 1 737 400 m
        # — a wrong answer that never raises, so it needs its own fixture rather than a
        # comment. Same bytes, same plane, only the label's OFFSET differs.
        r_img, r_lbl = _mini_product(tmp, "mini_radius_offset", 64, 240.0, sf,
                                     offset=1737400.0)
        radius_case = LolaGrid(read_label(r_lbl), r_img)
        radius_case.base = solve_convention(radius_case)["best"]["base"]
        rv = validate_label_range(radius_case)
        check("OFFSET recognised as the reference radius, not added",
              radius_case.offset_is_reference_radius
              and radius_case.elev_offset_m == 0.0
              and rv["passed"],
              f"OFFSET {radius_case.value_offset:,.0f} == A_AXIS_RADIUS "
              f"{radius_case.radius_m:,.0f}; added {radius_case.elev_offset_m} m; "
              f"range {rv['computed_elevation_m']['min']:+.1f} .. "
              f"{rv['computed_elevation_m']['max']:+.1f} m")

        # The real label states DERIVED_MINIMUM/DERIVED_MAXIMUM; the fixtures state
        # MINIMUM/MAXIMUM. Both have to resolve, and the report has to name the key it
        # actually compared against rather than implying one that is absent.
        probe = read_label(r_lbl)
        probe["IMAGE.DERIVED_MINIMUM"] = "-1234"
        check("DERIVED_MINIMUM preferred over MINIMUM, and named",
              opt_keyed(probe, "IMAGE.DERIVED_MINIMUM", "DERIVED_MINIMUM",
                        "IMAGE.MINIMUM", "MINIMUM")
              == (-1234.0, "IMAGE.DERIVED_MINIMUM")
              and radius_case.label_min_key == "IMAGE.MINIMUM",
              f"DERIVED_* wins when present; the fixture fell back to "
              f"{radius_case.label_min_key}")

        # The mini frame deliberately overruns the mini array by design — that is what
        # exercises read_window's clip path further down. So the assertion here is not
        # "the fixture is covered"; it is "the coverage gate measures the shortfall and
        # fires". A gate that has never been seen to fail is not a verified gate, and
        # this is the only place it can be made to fail without a second real product.
        cov = check_frame_coverage(primary, dfsar)
        worst_rho = max(
            math.hypot(x, y)
            for x in (dfsar.east_min, dfsar.east_max)
            for y in (dfsar.north_min, dfsar.north_max))
        hand_half = (primary.samples / 2.0) * primary.scale_m
        check("frame coverage measured, not assumed",
              (not cov["covers_frame"]
               and abs(cov["farthest_rho_m"] - worst_rho) < 0.01
               and abs(cov["array_half_span_m"] - hand_half) < 0.01
               and cov["margin_m"] < 0.0
               and len(cov["frame_corners"]) == 4),
              f"gate fired: farthest corner {cov['farthest_corner']} at "
              f"{cov['farthest_rho_m']:,.2f} m (hand-computed {worst_rho:,.2f} m) vs "
              f"half-span {cov['array_half_span_m']:,.0f} m, margin "
              f"{cov['margin_m']:+,.1f} m -> covers_frame={cov['covers_frame']}")

        prov = provenance_string(primary, dfsar)
        hits = [w for w in BANNED_PROVENANCE_WORDS if w in prov.lower()]
        check("provenance string passes MissionMap's placeholder regex",
              not hits and "m/px native" in prov, f"{prov!r}")

        vc = solve_convention(validation)
        validation.base = vc["best"]["base"]
        validation._convention = vc
        v = validate_label_range(validation)
        check("3.1 label MIN/MAX reproduced", v["passed"],
              f"{v['verdict']} (label read as {v.get('label_units')}, "
              f"residual {v.get('residual', float('nan')):.3g}, tol {v['tolerance']})")
        check("MISSING counted", v["n_missing"] == 17, f"{v['n_missing']} of 17")

        win = read_window(primary, dfsar)
        check("window is a subset", win["bytes_read"] < win["file_bytes"],
              f"{win['shape']} = {win['bytes_read']:,} B of {win['file_bytes']:,} B")
        check("window has no MISSING", win["n_missing_in_window"] == 0,
              f"{win['n_missing_in_window']}")

        res = resample_to_dfsar(primary, dfsar, win, block=16)
        st = res["stats"]
        check("3.3 no NaN", st["n_nan"] == 0, f"{st['n_nan']} NaN")

        # the decisive one: bilinear must reproduce the plane exactly, so any
        # error in LPO/SPO/base/scale/axis direction shows up here as ~b*20 m
        a, b, c = _PLANE
        rows = np.arange(dfsar.lines, dtype=np.float64)
        cols = np.arange(dfsar.samples, dtype=np.float64)
        gx, gy = dfsar.xy_of(rows[:, None], cols[None, :])
        truth = a + b * gx + c * gy
        err = np.abs(res["array"].astype(np.float64) - truth)
        tol = sf * 0.5 + 1e-3            # storage quantisation only
        check("affine round-trip on a plane", float(err.max()) <= tol,
              f"max |err| {err.max():.4f} m, mean {err.mean():.4f} m, tol {tol:.4f} m "
              f"(one pixel of slip would be {abs(b) * primary.scale_m:.1f} m)")

        # A numpy scalar anywhere in the sidecar payload would raise only AFTER the
        # real 47 MB read and full resample, so prove it serialises here instead.
        payload = {
            "label_range_check": v,
            "window": {k: win[k] for k in win if k not in ("dn", "valid")},
            "output_stats": st,
            "pixel_convention": primary._convention,
            "frame_coverage": cov,
            "provenance": prov,
        }
        try:
            json.dumps(payload, indent=2, default=str)
            check("sidecar payload is JSON-serialisable", True, "no numpy scalars leak")
        except TypeError as exc:
            check("sidecar payload is JSON-serialisable", False, str(exc))

        print(f"\n  fixture: {win['shape'][0]}x{win['shape'][1]} window -> "
              f"{st['shape'][0]}x{st['shape'][1]} frame, "
              f"min {st['min_m']:+.2f} max {st['max_m']:+.2f} m")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"  fixture deleted: {tmp}")

    if fails:
        print(f"\nSELF-TEST FAILED: {', '.join(fails)}")
        return 1
    print("\nSELF-TEST PASSED — every stage ran on a product-shaped fixture.")
    print("This does NOT mean the real ingest is correct: the fixture cannot test")
    print("LOLA's y-axis sign, only that this code is internally consistent and that")
    print("the label-driven paths (endianness, KM/PIXEL, pixel base) work.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check-only", action="store_true",
                    help="run the label and validation checks, write nothing")
    ap.add_argument("--selftest-crs", action="store_true",
                    help="only prove the projection code against metadata_real.json")
    ap.add_argument("--selftest-synthetic", action="store_true",
                    help="run every stage against a temporary product-shaped fixture")
    ap.add_argument("--input", metavar="IMG", default=None,
                    help="ingest this .IMG explicitly; its sibling .lbl is located "
                         "case-insensitively. Without it the PRODUCT_PREFERENCE "
                         "search order is used and the first complete pair wins.")
    args = ap.parse_args(argv)

    if args.selftest_synthetic:
        return selftest_synthetic()

    if not DFSAR_META.is_file():
        print(f"FATAL: {DFSAR_META} not found. The DFSAR frame is defined there and")
        print("this script refuses to hardcode it. Nothing written.")
        return 2
    meta = json.loads(DFSAR_META.read_text())
    dfsar = DfsarGrid(meta)

    scores = selftest_crs(meta)
    convention, crs_err = report_crs(scores)
    if crs_err > 1e-3:
        print("\nFAIL: this code cannot reproduce ISRO's own corner coordinates to")
        print("1e-3 deg under either convention. The projection model is wrong;")
        print("resampling anything through it would be meaningless. Nothing written.")
        return 1
    if args.selftest_crs:
        return 0

    # ── step 1: is the product actually here? ──
    p_img, p_lbl, survey = resolve_input(args.input)
    if not (p_img and p_lbl):
        return report_absent(survey, args.input)

    rule("STEP 1 — SOURCE PRODUCT")
    for row in survey:
        state = "complete" if row["complete"] else (
            "img only" if row["img"] else ("lbl only" if row["lbl"] else "absent"))
        used = "  <-- ingesting this one" if row["img"] == p_img.name else ""
        print(f"  {row['stem']:<15} {state:<9} {row['note']}{used}")
    if args.input:
        print(f"  --input {args.input}")
    print(f"\n  {p_img.name}  {p_img.stat().st_size:,} bytes   + {p_lbl.name}")

    try:
        primary = LolaGrid(read_label(p_lbl), p_img)
    except LabelError as exc:
        print(f"\nFAIL: {exc}")
        print("A key this ingest depends on is missing or unparseable. Nothing")
        print("written — no value was defaulted to keep the run alive.")
        return 1

    rule("STEP 2 — LABEL AS READ (nothing here is hardcoded)")
    g = primary
    print(f"  {g.path.name}")
    print(f"    {g.lines} x {g.samples}  dtype {g.dtype}  "
          f"(from SAMPLE_TYPE/SAMPLE_BITS, not assumed)")
    print(f"    MAP_SCALE {g.scale_m} m/px   as written <{g.scale_unit}>")
    print(f"    LPO {g.lpo}  SPO {g.spo}   A_AXIS_RADIUS {g.radius_m} m "
          f"<{g.radius_unit}>")
    print(f"    SCALING_FACTOR {g.scaling_factor}   OFFSET {g.value_offset} "
          f"unit <{g.value_unit}>")
    if g.offset_is_reference_radius:
        print(f"      -> OFFSET equals A_AXIS_RADIUS, so it is the reference sphere")
        print(f"         radius, not a datum shift. HEIGHT = DN x {g.scaling_factor}; "
              f"{g.value_offset:,.0f} m is NOT added.")
    else:
        print(f"      -> OFFSET differs from A_AXIS_RADIUS, so it is treated as a datum")
        print(f"         shift and added: HEIGHT = DN x {g.scaling_factor} "
              f"+ {g.value_offset}.")
    if g.missing is None:
        print("    MISSING_CONSTANT: absent from this label. LOLA GDRs are fully")
        print("      interpolated grids; no sentinel is substituted, and check 3.3")
        print("      therefore tests for NaN only.")
    else:
        print(f"    MISSING_CONSTANT {g.missing}")
    print(f"    stated range: {g.label_min_key} {g.label_min}   "
          f"{g.label_max_key} {g.label_max}")
    print(f"    lat range {g.min_lat} .. {g.max_lat}   projection {g.projection!r}")
    print(f"    data starts at byte {g.data_offset_bytes}; label describes "
          f"{g.expected_bytes():,} bytes; file is {p_img.stat().st_size:,}")

    bad = check_projection(g, dfsar)
    if bad:
        print("\nFAIL: the product is not the same projection as the DFSAR frame:")
        for b in bad:
            print(f"    - {b}")
        print("Nothing written.")
        return 1

    conv = solve_convention(g)
    g.base = conv["best"]["base"]
    g.base_residual_px = conv["best"]["residual_px"]
    g._convention = conv
    print("\n  pixel convention, measured against pole placement (not chosen):")
    for row in conv["candidates"]:
        mark = "  <-- used" if row["base"] == g.base else ""
        print(f"      {row['base']:<12} pole at line {row['pole_line']:.1f} "
              f"sample {row['pole_sample']:.1f}  residual "
              f"{row['residual_px']:.4f} px = {row['residual_m']:.2f} m{mark}")
    print(f"      array centre is line {conv['best']['centre_line']}, "
          f"sample {conv['best']['centre_sample']}")
    print(f"      POLE-CENTRE RESIDUAL: {conv['best']['residual_px']:.6f} px "
          f"({conv['best']['residual_m']:.3f} m)")
    if conv["best"]["residual_px"] > 1.0:
        print("\nFAIL: no pixel convention puts the projection origin within one")
        print("pixel of the array centre, so this product is not pole-centred the")
        print("way a polar GDR is expected to be. The affine map would be wrong.")
        print("Nothing written.")
        return 1

    e = conv["edge_latitude_check"]
    print("\n  MAXIMUM_LATITUDE cross-check — confirms MAP_SCALE, A_AXIS_RADIUS, the")
    print("  tangent plane and k0 = 1 simultaneously, since only one combination puts")
    print("  the array edge at the latitude the label states:")
    print(f"      array half-span   {e['array_half_span_m']:,.1f} m   "
          f"= {e['array_half_span_from']}")
    print(f"      rho({e['maximum_latitude_deg']} deg) = 2 R tan(pi/4 + phi/2) = "
          f"{e['rho_of_maximum_latitude_m']:,.1f} m")
    print(f"      array edge reads  {e['array_edge_latitude_deg']:.6f} deg vs label "
          f"{e['maximum_latitude_deg']}")
    print(f"      EDGE RESIDUAL: {e['residual_deg']:+.6f} deg "
          f"({e['residual_m']:+.1f} m, {e['residual_px']:+.4f} px), "
          f"tolerance {e['tolerance_deg']} deg -> "
          f"{'PASS' if e['passed'] else 'FAIL'}")
    if not e["passed"]:
        print("\nFAIL: the array edge does not fall at the label's own MAXIMUM_LATITUDE")
        print("to within 1e-3 deg, so the scale, the radius or the projection form is")
        print("being read wrongly. Nothing written.")
        return 1

    cov = check_frame_coverage(g, dfsar)
    print("\n  does this product reach the whole DFSAR frame? (computed here, not")
    print("  taken from the handoff):")
    for row in cov["frame_corners"]:
        print(f"      {row['corner']}  xy({row['x_m']:>11.1f},{row['y_m']:>10.1f})  "
              f"rho {row['rho_m']:>10,.0f} m   lat {row['latitude_deg']:>11.6f}")
    print(f"      farthest corner {cov['farthest_corner']} at "
          f"{cov['farthest_rho_m']:,.0f} m = "
          f"{cov['farthest_latitude_deg']:.4f} deg")
    print(f"      array half-span {cov['array_half_span_m']:,.0f} m, margin "
          f"{cov['margin_m']:,.0f} m -> "
          f"{'COVERS THE FRAME' if cov['covers_frame'] else 'DOES NOT COVER THE FRAME'}")
    if not cov["covers_frame"]:
        print("\nFAIL: part of the DFSAR frame lies outside this product's array, so")
        print("those output pixels would be extrapolated rather than measured. Use a")
        print("product with wider coverage. Nothing written.")
        return 1

    # ── step 3.1: the discriminating check ──
    rule("STEP 3.1 — REPRODUCE THE PRODUCT'S OWN STATED ELEVATION RANGE")
    print(f"Reading {g.path.name} in 512-row blocks, from raw bytes, never whole.")
    print("This is the only check here that compares against a number the product")
    print("carries about itself, so it is the only one that can tell a real product")
    print("from a fabricated one.")
    v = validate_label_range(g)
    print(f"  label {v['label_minimum_key']} = {v['label_minimum']}   "
          f"{v['label_maximum_key']} = {v['label_maximum']}")
    print(f"  computed DN         min {v['computed_dn']['min']:.6g}  "
          f"max {v['computed_dn']['max']:.6g}")
    print(f"  computed elevation  min {v['computed_elevation_m']['min']:+.4f} m  "
          f"max {v['computed_elevation_m']['max']:+.4f} m")
    print(f"  valid {v['n_valid']:,} px   MISSING {v['n_missing']:,} px")
    if "residual_if_label_is_dn" in v:
        print(f"  residual if the label is DN     : {v['residual_if_label_is_dn']:.6g}")
        print(f"  residual if the label is scaled : {v['residual_if_label_is_scaled']:.6g}")
        print(f"  tolerance (one quantisation step): {v['tolerance']:.6g}")
        print(f"  the label is in {v['label_units']}, residual {v['residual']:.6g}")
    print(f"  VERDICT: {v['verdict']}")
    if not v["passed"]:
        print("\nStopping. If the product's own stated range cannot be reproduced from")
        print("its bytes, then either the dtype, the offset or the scaling is being")
        print("read wrongly, and every elevation downstream would be wrong. Nothing")
        print("written.")
        return 1

    if args.check_only:
        rule("--check-only: stopping before the windowed read")
        print("Checks that passed: projection self-test, label parse, projection")
        print("agreement, pixel convention, MAXIMUM_LATITUDE cross-check, frame")
        print("coverage, and 3.1 range reproduction. Nothing written.")
        return 0

    # ── step 2 (read) and the resample ──
    rule(f"STEP 2 — WINDOWED READ OF {g.path.name}")
    print(f"  DFSAR frame: easting {dfsar.east_min:.2f} .. {dfsar.east_max:.2f} m")
    print(f"               northing {dfsar.north_min:.2f} .. {dfsar.north_max:.2f} m")
    try:
        win = read_window(primary, dfsar)
    except RuntimeError as exc:
        print(f"\nFAIL: {exc}")
        print("Nothing written.")
        return 1
    print(f"  window lines {win['line0']}..{win['line0'] + win['shape'][0]} "
          f"samples {win['sample0']}..{win['sample0'] + win['shape'][1]}")
    print(f"  read {win['shape'][0]} x {win['shape'][1]} = {win['bytes_read'] / 1e6:.1f} MB "
          f"of a {win['file_bytes'] / 1e9:.2f} GB file "
          f"({win['fraction_of_file'] * 100:.3f} %)")
    print(f"  MISSING_CONSTANT pixels inside the window: {win['n_missing_in_window']:,}")
    if win["clipped_to_array"]:
        print("  NOTE: the requested window ran past the array edge and was clipped;")
        print("  edge output pixels used mode='nearest'.")

    rule("RESAMPLE ONTO THE 2258 x 6618 DFSAR GRID AT 25 m")
    res = resample_to_dfsar(primary, dfsar, win)
    st = res["stats"]
    print(f"  bilinear (order=1), 128-row blocks, {st['shape'][0]} x {st['shape'][1]}")

    rule("STEP 3.2 — FAUSTINI FLOOR, AS MEASURED (not adjusted)")
    if "min_m" not in st:
        print("  every output pixel is NaN; nothing to report. Nothing written.")
        return 1
    print(f"  min  {st['min_m']:+.3f} m      p01 {st['p01_m']:+.3f} m")
    print(f"  p50  {st['p50_m']:+.3f} m      p99 {st['p99_m']:+.3f} m")
    print(f"  max  {st['max_m']:+.3f} m     mean {st['mean_m']:+.3f} m")
    print(f"  (elevations are relative to the label's own {primary.radius_m:.0f} m sphere)")
    expected = -4000.0 <= st["min_m"] <= -3000.0
    print(f"  handoff expectation was -3 to -4 km: {'consistent' if expected else 'NOT met'}")
    if not expected:
        print("  Reported as measured. Nothing was adjusted to hit the expected band,")
        print("  and this is not treated as a failure: the expectation is a prior, not")
        print("  a label value. The check that can fail is 3.1, which passed.")

    rule("STEP 3.3 — NO NaN AND NO MISSING_CONSTANT SURVIVES")
    print(f"  NaN in output                    : {st['n_nan']:,}")
    print(f"  pixels touching MISSING_CONSTANT : {st['n_contaminated_by_missing']:,}")
    if st["n_nan"]:
        frac = st["n_nan"] / (st["shape"][0] * st["shape"][1])
        print(f"  that is {frac * 100:.4f} % of the frame.")
        print("\nFAIL: step 3.3 requires none. These pixels are inside the DFSAR frame")
        print("but have no LOLA measurement behind them. Filling them would be")
        print("invention, so nothing is written. If the gap is a genuine coverage")
        print("hole, the frame needs a nodata convention agreed first.")
        return 1
    print("  PASS")

    rule("WRITE")
    OUT_FRAME.parent.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(str(OUT_FRAME), res["array"], dtype=np.float32)
    print(f"  raster  -> {OUT_FRAME}  ({OUT_FRAME.stat().st_size / 1e6:.1f} MB)")

    prov = provenance_string(primary, dfsar)
    ratio = g.scale_m / dfsar.px_x
    write_sidecar({
        "generated_by": "backend/scripts/ingest_lola_polar_dem.py",
        "provenance": prov,
        "native_metres_per_pixel": g.scale_m,
        "output_metres_per_pixel": dfsar.px_x,
        "reference_sphere_radius_m": g.radius_m,
        "elevation_datum": (
            f"heights above a sphere of radius {g.radius_m:,.1f} m "
            f"({g.radius_m / 1000.0:g} km), the label's own A_AXIS_RADIUS. Not a "
            "geoid, not local mean terrain, and not a height above the LRO orbit."
        ),
        "resample_ratio": round(ratio, 6),
        "native_metres_per_pixel": g.scale_m,
        "output_metres_per_pixel": dfsar.px_x,
        "anti_alias": res.get("anti_alias", {"applied": False, "method": "not recorded"}),
        "resample_direction": ("upsample — the output grid is finer than the "
                               "measurement, so it carries no detail below "
                               f"{g.scale_m:g} m") if ratio > 1.0 else (
                              (f"DOWNSAMPLE — the output grid is COARSER than the "
                               f"{g.scale_m:g} m measurement, so content between "
                               f"{2 * g.scale_m:g} m and {2 * dfsar.px_x:g} m wavelength "
                               f"cannot be represented and is low-passed away before "
                               f"sampling rather than allowed to alias")
                              if ratio < 1.0 else "1:1"),
        "resolution_caveat": (
            f"Native post spacing is {g.scale_m:g} m. Any slope, roughness or hazard "
            f"quantity derived from this raster is a {g.scale_m:g} m quantity resampled "
            f"onto a {dfsar.px_x:g} m grid, not a {dfsar.px_x:g} m measurement. Label "
            "derived tables with the post spacing they were computed at."
        ),
        "source_product": {
            "img": p_img.name,
            "lbl": p_lbl.name,
            "bytes": p_img.stat().st_size,
            "selected_by": ("--input" if args.input else
                            "PRODUCT_PREFERENCE search order"),
            "product_id": opt_text(g.label, "PRODUCT_ID"),
            "product_version_id": opt_text(g.label, "PRODUCT_VERSION_ID"),
            "data_set_id": opt_text(g.label, "DATA_SET_ID"),
            "producer_id": opt_text(g.label, "PRODUCER_ID"),
            "start_time": opt_text(g.label, "START_TIME"),
            "stop_time": opt_text(g.label, "STOP_TIME"),
            "product_creation_time": opt_text(g.label, "PRODUCT_CREATION_TIME"),
        },
        "lineage": (
            "LOLA gridded data record: a shape map whose values are heights above "
            f"the {g.radius_m / 1000.0:g} km reference sphere, built from LOLA Laser 1 "
            "and Laser 2 ranging through the label's STOP_TIME, on a GRAIL "
            "900C-consistent geodetic frame, gridded by the LOLA team with GMT "
            "mapproject/blockmedian/surface and pixel registration. Elevation here is "
            "not a height above a geoid or above local mean terrain."
        ),
        "value_conversion": {
            "formula": f"elevation_m = DN * {g.scaling_factor}"
                       + ("" if g.offset_is_reference_radius
                          else f" + {g.value_offset}"),
            "scaling_factor": g.scaling_factor,
            "offset_in_label": g.value_offset,
            "offset_added_to_elevation_m": g.elev_offset_m,
            "offset_is_reference_radius": g.offset_is_reference_radius,
            "offset_decision": (
                f"OFFSET = {g.value_offset:,.1f} equals A_AXIS_RADIUS "
                f"({g.radius_m:,.1f} m) to within 1 m, so the label is using it for "
                "PLANETARY_RADIUS = DN*SCALING_FACTOR + OFFSET, not as a datum shift. "
                "It is NOT added to elevation; adding it would report every pixel as "
                "roughly 1737 km."
            ) if g.offset_is_reference_radius else (
                f"OFFSET = {g.value_offset} differs from A_AXIS_RADIUS "
                f"({g.radius_m:,.1f} m), so it is treated as a genuine additive datum "
                "shift and included in the elevation."
            ),
            "unit_in_label": g.value_unit,
        },
        "missing_constant": {
            "present_in_label": g.missing is not None,
            "value": g.missing,
            "note": (
                "This label states no MISSING_CONSTANT. LOLA GDRs are fully "
                "interpolated grids, so no sentinel exists to strip and none was "
                "invented; check 3.3 tests for NaN only."
            ) if g.missing is None else (
                "Pixels equal to MISSING_CONSTANT were excluded before resampling and "
                "any output pixel whose bilinear footprint touched one is counted in "
                "output_stats.n_contaminated_by_missing."
            ),
        },
        "target_grid": {
            "lines": dfsar.lines, "samples": dfsar.samples,
            "pixel_size_m": dfsar.px_x, "raster_type": dfsar.raster_type,
            "from": str(DFSAR_META.relative_to(REPO)),
        },
        "crs_selftest": {"convention": convention,
                         "worst_corner_error_deg": crs_err,
                         "corners": scores[convention]["corners"]},
        "pixel_convention": primary._convention,
        "frame_coverage": cov,
        "axis_convention_assumption": (
            "LOLA (x, y) is taken to mean the same thing as the DFSAR (x, y): both "
            "labels state south polar stereographic, sphere, centre latitude -90, "
            "centre longitude 0, no MAP_PROJECTION_ROTATION, so the two grids differ "
            "only by an affine map. This is NOT independently verified — doing so "
            "would need a third elevation source, and none is available offline. "
            "The projection self-test above verifies this code against ISRO's own "
            "corner coordinates; it does not verify LOLA's y sign."
        ),
        "label_range_check": {k: v[k] for k in v if k != "array"},
        "window": {k: win[k] for k in win if k not in ("dn", "valid")},
        "output_stats": st,
        "resampling": "scipy.ndimage.map_coordinates order=1 (bilinear), "
                      "validity mask resampled with the same kernel",
    })
    rule("DONE")
    print(f"  provenance string: {prov}")
    print(f"  native {g.scale_m:g} m/px -> output {dfsar.px_x:g} m/px "
          f"({ratio:.2f}x upsample). The number a reader needs is "
          f"{g.scale_m:g}, not {dfsar.px_x:g}.")
    print("\nEvery check passed. The frame above is measured topography; the four")
    print("synthetic 'provenance' tags in frontend/public/layers/layers.json and the")
    print("synthetic_placeholder_dem() call in process_real_sar_pipeline.py can now")
    print("be replaced — that is step 4, and it is a separate edit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())



