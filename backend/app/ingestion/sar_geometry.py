"""
Real georeferencing for the Chandrayaan-2 DFSAR L2-SELENOREF (`sri`) product.

Nothing here is invented. Every number is either read directly from the
product's own GeoTIFF GeoKeys / PDS4 label, or derived in closed form from
those numbers.

The `sri` rasters carry complete GeoTIFF georeferencing:

    ModelPixelScaleTag = (25.0, 25.0, 0.0)                      -> 25 m isotropic
    ModelTiepointTag   = (0,0,0, -13488.786634, 38611.318869, 0)
    GeoKey 3075        = 15   CT_PolarStereographic
    GeoDoubleParams    -> lat_origin -90, lon_origin 0, k0 1.0, R 1737400 m
    GeoAsciiParams     -> "POLARSTEREOGRAPHIC MOON|GCS_MOON|D_MOON|..."

so pixel <-> selenodetic lat/lon is an exact closed-form transform rather than
an interpolation over sparse tie points. Cross-checked against ISRO's own
geolocation grid (`..._g_sri_..._d18.csv`, 566 x 1656 nodes, 4-pixel spacing):

    column residual   max 0.490 px (12.3 m)   rms 0.285 px
    row    residual   max 0.794 px (19.9 m)   rms 0.455 px

Sub-pixel agreement with an independently supplied product.

Dependencies: numpy + tifffile + stdlib only. No GDAL / rasterio / pyproj.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

try:
    import tifffile
except ImportError:  # pragma: no cover - tifffile is a hard dep of the pipeline
    tifffile = None


# --- GeoTIFF / GeoKey identifiers we actually consume -----------------------
GK_RASTER_TYPE = 1025
GK_SEMI_MAJOR = 2057
GK_SEMI_MINOR = 2058
GK_PROJ_METHOD = 3075
GK_LINEAR_UNITS = 3076
GK_NAT_ORIGIN_LAT = 3081        # ProjFalseOriginLatGeoKey (polar aspect latitude)
GK_STRAIGHT_VERT_POLE = 3095    # ProjStraightVertPoleLongGeoKey
GK_NAT_ORIGIN_LONG = 3080       # ProjNatOriginLongGeoKey
GK_FALSE_EASTING = 3082
GK_FALSE_NORTHING = 3083
GK_SCALE_AT_NAT_ORIGIN = 3092

CT_POLAR_STEREOGRAPHIC = 15
RASTER_PIXEL_IS_AREA = 1
RASTER_PIXEL_IS_POINT = 2

# Fill value ISRO writes into off-swath nodes of the geolocation CSV.
GRID_FILL = -9999.0


def _strip_ns(tag: str) -> str:
    """`{http://...}isda:no_scans` / `{ns}no_scans` -> `no_scans`."""
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()


def parse_pds4_label(xml_path: Path) -> Dict[str, str]:
    """
    Flatten a PDS4 XML label into {leaf_tag_lowercase: text}.

    Repeated tags (e.g. `polarization` appears once per channel) are joined
    with '|' so nothing is silently dropped.
    """
    import xml.etree.ElementTree as ET

    out: Dict[str, str] = {}
    root = ET.parse(str(xml_path)).getroot()
    for node in root.iter():
        text = (node.text or "").strip()
        if not text:
            continue
        key = _strip_ns(node.tag)
        if key in out and out[key] != text:
            out[key] = f"{out[key]}|{text}"
        else:
            out[key] = text
    return out


def _as_int(mapping: Dict[str, str], key: str) -> int:
    if key not in mapping:
        raise KeyError(f"required label field '{key}' not present")
    return int(str(mapping[key]).split("|")[0])


def parse_geolocation_grid_spec(geometry_xml: Path, product: str = "sri") -> Dict[str, int]:
    """
    Read the geolocation-grid shape for one product family out of the
    `..._g_xxx_..._d18.xml` geometry label. Nothing is hardcoded: for
    product='sri' this reads sri_grid_no_records / sri_grid_no_samples /
    sri_grid_interval_scan / sri_grid_interval_pix.
    """
    label = parse_pds4_label(geometry_xml)
    p = product.lower()
    spec = {
        "records": _as_int(label, f"{p}_grid_no_records"),
        "samples": _as_int(label, f"{p}_grid_no_samples"),
        "interval_line": _as_int(label, f"{p}_grid_interval_scan"),
        "interval_sample": _as_int(label, f"{p}_grid_interval_pix"),
    }
    spec["expected_rows"] = spec["records"] * spec["samples"]
    return spec


def decode_geokeys(
    key_dir: Sequence[int],
    doubles: Optional[Sequence[float]] = None,
    ascii_params: str = "",
) -> Dict[int, Any]:
    """
    Decode a GeoTIFF GeoKeyDirectoryTag (34735) into {key_id: value},
    resolving indirections into GeoDoubleParamsTag (34736) and
    GeoAsciiParamsTag (34737). Implements the GeoTIFF 1.8.2 key layout.
    """
    doubles = list(doubles or [])
    out: Dict[int, Any] = {}
    if len(key_dir) < 4:
        return out
    n_keys = int(key_dir[3])
    for i in range(n_keys):
        base = 4 + i * 4
        if base + 3 >= len(key_dir):
            break
        key_id, loc, count, offset = (int(v) for v in key_dir[base:base + 4])
        if loc == 0:
            out[key_id] = offset
        elif loc == 34736:
            vals = doubles[offset:offset + count]
            out[key_id] = vals[0] if count == 1 else vals
        elif loc == 34737:
            out[key_id] = ascii_params[offset:offset + count].rstrip("|\x00 ")
    return out


@dataclass
class SarFrame:
    """
    Exact south-polar-stereographic frame for one seleno-referenced raster.

    All fields come from the GeoTIFF tags of the source product; `shape` is the
    array shape those tags describe. Pixel indices follow the GeoTIFF
    PixelIsArea convention: the tiepoint is the *outer corner* of pixel (0, 0),
    so pixel centres sit at index + 0.5.
    """

    shape: Tuple[int, int]                  # (lines, samples)
    pixel_size_m: Tuple[float, float]       # (x / sample, y / line)
    tiepoint_xy_m: Tuple[float, float]      # projected (E, N) at pixel corner (0, 0)
    radius_m: float
    lat_origin_deg: float
    lon_origin_deg: float
    scale_factor: float = 1.0
    false_easting_m: float = 0.0
    false_northing_m: float = 0.0
    projection: str = "POLARSTEREOGRAPHIC MOON"
    raster_type: int = RASTER_PIXEL_IS_AREA
    source: str = ""
    label: Dict[str, str] = field(default_factory=dict)

    # -- projection -------------------------------------------------------
    def _check_south(self) -> None:
        if not math.isclose(self.lat_origin_deg, -90.0, abs_tol=1e-6):
            raise ValueError(
                f"only the south polar aspect is implemented; label says "
                f"lat_origin={self.lat_origin_deg}. Refusing to guess."
            )

    def latlon_to_xy(self, lat_deg, lon_deg):
        """Selenodetic lat/lon -> projected metres (spherical, tangent plane)."""
        self._check_south()
        lat = np.deg2rad(np.asarray(lat_deg, dtype=np.float64))
        lam = np.deg2rad(np.asarray(lon_deg, dtype=np.float64) - self.lon_origin_deg)
        rho = 2.0 * self.radius_m * self.scale_factor * np.tan(np.pi / 4.0 + lat / 2.0)
        return (rho * np.sin(lam) + self.false_easting_m,
                rho * np.cos(lam) + self.false_northing_m)

    def xy_to_latlon(self, x_m, y_m):
        """Projected metres -> selenodetic lat/lon."""
        self._check_south()
        x = np.asarray(x_m, dtype=np.float64) - self.false_easting_m
        y = np.asarray(y_m, dtype=np.float64) - self.false_northing_m
        rho = np.hypot(x, y)
        lat = 2.0 * np.arctan(rho / (2.0 * self.radius_m * self.scale_factor)) - np.pi / 2.0
        lon = np.arctan2(x, y)
        return np.rad2deg(lat), (np.rad2deg(lon) + self.lon_origin_deg + 180.0) % 360.0 - 180.0

    # -- pixel <-> world ---------------------------------------------------
    def pixel_to_xy(self, line, sample, centre: bool = True):
        """(line, sample) -> projected (E, N) metres."""
        off = 0.5 if (centre and self.raster_type == RASTER_PIXEL_IS_AREA) else 0.0
        sx, sy = self.pixel_size_m
        e0, n0 = self.tiepoint_xy_m
        return (e0 + (np.asarray(sample, dtype=np.float64) + off) * sx,
                n0 - (np.asarray(line, dtype=np.float64) + off) * sy)

    def xy_to_pixel(self, x_m, y_m, centre: bool = True):
        """Projected (E, N) metres -> fractional (line, sample)."""
        off = 0.5 if (centre and self.raster_type == RASTER_PIXEL_IS_AREA) else 0.0
        sx, sy = self.pixel_size_m
        e0, n0 = self.tiepoint_xy_m
        return ((n0 - np.asarray(y_m, dtype=np.float64)) / sy - off,
                (np.asarray(x_m, dtype=np.float64) - e0) / sx - off)

    def pixel_to_latlon(self, line, sample):
        """(line, sample) -> (lat_deg, lon_deg). Exact, no interpolation."""
        x, y = self.pixel_to_xy(line, sample)
        return self.xy_to_latlon(x, y)

    def latlon_to_pixel(self, lat_deg, lon_deg):
        """(lat_deg, lon_deg) -> fractional (line, sample)."""
        x, y = self.latlon_to_xy(lat_deg, lon_deg)
        return self.xy_to_pixel(x, y)

    # -- UI grid (0..100 in both axes, as used by the mission modules) -----
    def grid_to_pixel(self, gx, gy, grid_max: float = 100.0):
        """UI grid (gx across, gy down, 0..grid_max) -> (line, sample)."""
        lines, samples = self.shape
        return (np.asarray(gy, dtype=np.float64) / grid_max * (lines - 1),
                np.asarray(gx, dtype=np.float64) / grid_max * (samples - 1))

    def grid_to_latlon(self, gx, gy, grid_max: float = 100.0):
        """UI grid -> (lat_deg, lon_deg). Replaces the old flat-earth approximation."""
        line, sample = self.grid_to_pixel(gx, gy, grid_max)
        return self.pixel_to_latlon(line, sample)

    # -- scale ------------------------------------------------------------
    def metres_per_pixel(self, shape: Optional[Tuple[int, int]] = None) -> Tuple[float, float]:
        """
        Ground spacing (y_per_line, x_per_sample) for an array covering this
        frame's full extent at `shape`. At native shape this returns the
        product's own 25 m / 25 m; a downsampled array scales linearly.
        """
        lines, samples = shape if shape is not None else self.shape
        sx, sy = self.pixel_size_m
        return (sy * self.shape[0] / float(lines), sx * self.shape[1] / float(samples))

    def stereographic_scale_error(self) -> float:
        """
        Peak fractional scale distortion of the tangent-plane projection over
        this raster, i.e. how wrong a distance read off the map can be.
        k = 2 / (1 + cos c), c = angular distance from the pole.
        """
        lines, samples = self.shape
        corners = [(0, 0), (0, samples - 1), (lines - 1, 0), (lines - 1, samples - 1)]
        worst = 0.0
        for line, sample in corners:
            lat, _ = self.pixel_to_latlon(line, sample)
            c = math.radians(90.0 + float(lat))
            worst = max(worst, 2.0 / (1.0 + math.cos(c)) - 1.0)
        return worst

    def great_circle_m(self, lat1, lon1, lat2, lon2) -> float:
        """Haversine great-circle distance on the sphere used by the product."""
        p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
        dp = p2 - p1
        dl = math.radians(float(lon2) - float(lon1))
        h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2.0 * self.radius_m * math.asin(min(1.0, math.sqrt(h)))

    def footprint(self, valid_mask: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        Measure the illuminated swath. With `valid_mask` the extent is measured
        over pixels that actually carry data; without it, over the full raster.
        Distances are great-circle, so they are real ground distances rather
        than projected-plane distances.
        """
        lines, samples = self.shape
        if valid_mask is not None:
            rows = np.flatnonzero(valid_mask.any(axis=1))
            cols = np.flatnonzero(valid_mask.any(axis=0))
            if rows.size == 0 or cols.size == 0:
                raise ValueError("valid_mask is empty; nothing to measure")
            r0, r1, c0, c1 = int(rows[0]), int(rows[-1]), int(cols[0]), int(cols[-1])
        else:
            r0, r1, c0, c1 = 0, lines - 1, 0, samples - 1

        mid_line = 0.5 * (r0 + r1)
        mid_samp = 0.5 * (c0 + c1)
        lat_a, lon_a = self.pixel_to_latlon(r0, mid_samp)
        lat_b, lon_b = self.pixel_to_latlon(r1, mid_samp)
        lat_c, lon_c = self.pixel_to_latlon(mid_line, c0)
        lat_d, lon_d = self.pixel_to_latlon(mid_line, c1)

        lat_grid, lon_grid = self.pixel_to_latlon(
            np.array([r0, r0, r1, r1], dtype=np.float64),
            np.array([c0, c1, c1, c0], dtype=np.float64),
        )
        return {
            "bbox_pixels": {"line_min": r0, "line_max": r1,
                            "sample_min": c0, "sample_max": c1},
            "across_track_m": round(self.great_circle_m(lat_a, lon_a, lat_b, lon_b), 2),
            "along_track_m": round(self.great_circle_m(lat_c, lon_c, lat_d, lon_d), 2),
            "corners_latlon": [
                {"label": lbl, "lat_deg": round(float(la), 6), "lon_deg": round(float(lo), 6)}
                for lbl, la, lo in zip(("UL", "UR", "LR", "LL"), lat_grid, lon_grid)
            ],
            "measured_over": "valid_mask" if valid_mask is not None else "full_raster",
        }

    # -- provenance --------------------------------------------------------
    def geodetic_frame(
        self,
        valid_mask: Optional[np.ndarray] = None,
        grid_spec: Optional[Dict[str, int]] = None,
        grid_validation: Optional[Dict[str, Any]] = None,
        incidence_range_deg: Optional[Tuple[float, float]] = None,
    ) -> Dict[str, Any]:
        """
        The JSON-serialisable replacement for the old hardcoded `bounds` block.

        Note there is deliberately no `min_lon`/`max_lon`: the south pole falls
        *inside* this raster, so longitude wraps the full +/-180 range and a
        lon bounding box carries no information. The corner list and the
        projected extent are the honest description.
        """
        lines, samples = self.shape
        e0, n0 = self.tiepoint_xy_m
        sx, sy = self.pixel_size_m
        lat_all, _ = self.pixel_to_latlon(
            np.array([0, 0, lines - 1, lines - 1], dtype=np.float64),
            np.array([0, samples - 1, samples - 1, 0], dtype=np.float64),
        )
        pole_inside = (e0 <= 0.0 <= e0 + samples * sx) and (n0 - lines * sy <= 0.0 <= n0)

        frame: Dict[str, Any] = {
            "crs": {
                "name": self.projection,
                "method": "south polar stereographic (spherical, tangent, k0=%.6f)" % self.scale_factor,
                "body_radius_m": self.radius_m,
                "latitude_of_origin_deg": self.lat_origin_deg,
                "central_meridian_deg": self.lon_origin_deg,
                "false_easting_m": self.false_easting_m,
                "false_northing_m": self.false_northing_m,
                "linear_unit": "metre",
            },
            "raster": {
                "lines": lines,
                "samples": samples,
                "pixel_size_m": {"x": sx, "y": sy},
                "raster_type": "PixelIsArea" if self.raster_type == RASTER_PIXEL_IS_AREA else "PixelIsPoint",
                "tiepoint_xy_m": {"easting": e0, "northing": n0},
                "projected_extent_m": {
                    "easting_min": e0, "easting_max": e0 + samples * sx,
                    "northing_min": n0 - lines * sy, "northing_max": n0,
                },
                "extent_km": {"across_track": round(lines * sy / 1000.0, 3),
                              "along_track": round(samples * sx / 1000.0, 3)},
            },
            "latitude_deg": {
                "corner_min": round(float(np.min(lat_all)), 6),
                "corner_max": round(float(np.max(lat_all)), 6),
                "true_min": -90.0 if pole_inside else round(float(np.min(lat_all)), 6),
                "pole_inside_raster": bool(pole_inside),
            },
            "longitude_deg": {
                "bounding_box_meaningful": not bool(pole_inside),
                "note": ("south pole lies inside the raster, so longitude spans the full "
                         "-180..180 range and a lon bounding box is not informative")
                if pole_inside else "",
            },
            "max_scale_distortion_fraction": round(self.stereographic_scale_error(), 6),
            "georeferencing": "exact closed-form transform from the product's own GeoTIFF GeoKeys",
            "source": self.source,
        }
        if valid_mask is not None:
            frame["valid_data_fraction"] = round(float(valid_mask.mean()), 6)
        frame["footprint"] = self.footprint(valid_mask)
        if grid_spec is not None:
            frame["isro_geolocation_grid"] = dict(grid_spec)
        if grid_validation is not None:
            frame["isro_geolocation_grid_agreement"] = grid_validation
        if incidence_range_deg is not None:
            frame["incidence_angle_deg"] = {"min": round(float(incidence_range_deg[0]), 4),
                                            "max": round(float(incidence_range_deg[1]), 4)}
        return frame


def frame_from_geodetic_metadata(json_path: Path) -> SarFrame:
    """
    Rebuild a `SarFrame` from the `geodetic_frame` block of a metadata sidecar.

    Why this exists: none of the DEM/CPR/DOP products this project writes to
    disk carry GeoTIFF georeferencing tags — `_save` in the ingestion scripts
    writes plain tifffile output. `read_geotiff_frame` therefore raises on every
    one of them, and mission_service had no way to learn the frame at request
    time. It does have a way: `process_real_sar_pipeline.py` already recorded the
    frame, verbatim from the source product's own GeoTIFF tags and PDS4 label,
    into `dfsar/metadata_real.json` at ingestion time. Reading it back is
    reading the real georeferencing, one hop removed — not a guess and not a
    constant.

    Raises if the block is missing or is not the south polar aspect, for the
    same reason `read_geotiff_frame` does: a silently-wrong frame is worse than
    a crash.
    """
    json_path = Path(json_path)
    with open(json_path, "r", encoding="utf-8") as fh:
        meta = json.load(fh)

    gf = meta.get("geodetic_frame")
    if not gf:
        raise ValueError(f"{json_path.name} carries no geodetic_frame block")

    crs = gf["crs"]
    ras = gf["raster"]
    px = ras["pixel_size_m"]
    tie = ras["tiepoint_xy_m"]

    frame = SarFrame(
        shape=(int(ras["lines"]), int(ras["samples"])),
        pixel_size_m=(float(px["x"]), float(px["y"])),
        tiepoint_xy_m=(float(tie["easting"]), float(tie["northing"])),
        radius_m=float(crs["body_radius_m"]),
        lat_origin_deg=float(crs["latitude_of_origin_deg"]),
        lon_origin_deg=float(crs["central_meridian_deg"]),
        false_easting_m=float(crs.get("false_easting_m", 0.0)),
        false_northing_m=float(crs.get("false_northing_m", 0.0)),
        projection=str(crs.get("name", "POLARSTEREOGRAPHIC MOON")),
        raster_type=(RASTER_PIXEL_IS_AREA
                     if str(ras.get("raster_type", "PixelIsArea")) == "PixelIsArea"
                     else RASTER_PIXEL_IS_POINT),
        source=f"{json_path.name}:geodetic_frame <- {gf.get('source', '')}",
    )
    frame._check_south()
    return frame


def read_geotiff_frame(tif_path: Path, label_xml: Optional[Path] = None) -> SarFrame:
    """
    Build a `SarFrame` from a seleno-referenced GeoTIFF's own tags.

    Raises rather than guessing if the file is not the projection we support --
    a silently-wrong frame is worse than a crash.
    """
    if tifffile is None:  # pragma: no cover
        raise RuntimeError("tifffile is required to read GeoTIFF georeferencing")

    tif_path = Path(tif_path)
    with tifffile.TiffFile(str(tif_path)) as tf:
        page = tf.pages[0]
        tags = {t.code: t.value for t in page.tags}
        shape = (int(page.shape[0]), int(page.shape[1]))

    if 33550 not in tags or 33922 not in tags:
        raise ValueError(f"{tif_path.name} carries no ModelPixelScale/ModelTiepoint tags")

    scale = tags[33550]
    tie = tags[33922]
    keys = decode_geokeys(tags.get(34735, ()), tags.get(34736, ()), tags.get(34737, "") or "")

    method = int(keys.get(GK_PROJ_METHOD, -1))
    if method != CT_POLAR_STEREOGRAPHIC:
        raise ValueError(
            f"{tif_path.name}: GeoKey 3075 = {method}, expected "
            f"{CT_POLAR_STEREOGRAPHIC} (CT_PolarStereographic). Refusing to guess."
        )
    units = int(keys.get(GK_LINEAR_UNITS, 9001))
    if units != 9001:
        raise ValueError(f"{tif_path.name}: linear units {units}, expected 9001 (metre)")

    radius = float(keys.get(GK_SEMI_MAJOR, keys.get(GK_SEMI_MINOR, 1737400.0)))
    lat_origin = float(keys.get(GK_NAT_ORIGIN_LAT, -90.0))
    lon_origin = float(keys.get(GK_STRAIGHT_VERT_POLE, keys.get(GK_NAT_ORIGIN_LONG, 0.0)))
    k0 = float(keys.get(GK_SCALE_AT_NAT_ORIGIN, 1.0)) or 1.0

    label: Dict[str, str] = {}
    if label_xml is None:
        # `..._d_sri_xx_cp_lh_d18.tif` and `..._d_sri_in_cp_xx_d18.tif` are both
        # described by the single label `..._d_sri_xx_cp_xx_d18.xml`.
        guess = tif_path.with_suffix(".xml").with_name(
            re.sub(r"_(sri|gri|sli)_[a-z]{2}_cp_[a-z]{2}_",
                   r"_\1_xx_cp_xx_", tif_path.stem) + ".xml"
        )
        label_xml = guess if guess.exists() else None
    if label_xml is not None and Path(label_xml).exists():
        label = parse_pds4_label(Path(label_xml))

    if label:
        for axis_key, idx in (("no_scans", 0), ("no_pixels", 1)):
            if axis_key in label:
                declared = _as_int(label, axis_key)
                if declared != shape[idx]:
                    raise ValueError(
                        f"{tif_path.name}: label {axis_key}={declared} but array "
                        f"axis {idx} is {shape[idx]}"
                    )

    src = tif_path.name
    if label_xml is not None:
        src = f"{src} + {Path(label_xml).name}"

    return SarFrame(
        shape=shape,
        pixel_size_m=(float(scale[0]), float(scale[1])),
        tiepoint_xy_m=(float(tie[3]), float(tie[4])),
        radius_m=radius,
        lat_origin_deg=lat_origin,
        lon_origin_deg=lon_origin,
        scale_factor=k0,
        false_easting_m=float(keys.get(GK_FALSE_EASTING, 0.0)),
        false_northing_m=float(keys.get(GK_FALSE_NORTHING, 0.0)),
        projection=str(keys.get(1026) or keys.get(2049) or "POLARSTEREOGRAPHIC MOON").split("|")[0],
        raster_type=int(keys.get(GK_RASTER_TYPE, RASTER_PIXEL_IS_AREA)),
        source=src,
        label=label,
    )


def parse_calibration(label_xml: Path) -> Dict[str, Any]:
    """
    Read the radiometric calibration constants out of the PDS4 label, grouped by
    polarisation, so the pipeline does not have to hardcode them.

    The label nests one block per channel, each opening with `isda:polarization`,
    so document order is what associates a gain with a channel.
    """
    import xml.etree.ElementTree as ET

    root = ET.parse(str(label_xml)).getroot()
    channels: Dict[str, Dict[str, float]] = {}
    current: Optional[str] = None
    cal_db: Optional[float] = None
    per_channel = {"gain_imbalance", "phase_orthogonality", "bias_real", "bias_imag"}

    for node in root.iter():
        key = _strip_ns(node.tag)
        text = (node.text or "").strip()
        if not text:
            continue
        if key == "polarization":
            current = text.upper()
            channels.setdefault(current, {})
        elif key == "calibration_constant":
            cal_db = float(text)
        elif key in per_channel and current is not None:
            channels[current].setdefault(key, float(text))

    if cal_db is None or not channels:
        raise ValueError(f"{Path(label_xml).name}: no calibration constants found")
    return {
        "calibration_constant_db": cal_db,
        "channels": channels,
        "source": Path(label_xml).name,
    }


def load_geolocation_grid(csv_path: Path, grid_spec: Dict[str, int]) -> np.ndarray:
    """
    Load ISRO's geolocation grid as `(records, samples, 4)` =
    (latitude_deg, longitude_deg, slant_range_m, incidence_angle_deg).

    The row count is checked against the geometry label rather than assumed.
    """
    csv_path = Path(csv_path)
    arr = np.loadtxt(str(csv_path), delimiter=",", skiprows=1, dtype=np.float64)
    expected = grid_spec["expected_rows"]
    if arr.shape[0] != expected:
        raise ValueError(
            f"{csv_path.name}: {arr.shape[0]} data rows but the geometry label "
            f"declares {grid_spec['records']} x {grid_spec['samples']} = {expected}"
        )
    return arr.reshape(grid_spec["records"], grid_spec["samples"], arr.shape[1])


def validate_against_grid(
    frame: SarFrame, grid: np.ndarray, grid_spec: Dict[str, int]
) -> Dict[str, Any]:
    """
    Independent check of the closed-form transform: project every node of
    ISRO's geolocation grid and compare with where the declared node spacing
    says it should sit. Residuals are reported in pixels and metres.

    This is the number to quote when asked "how do you know your map
    coordinates are right?" -- it compares two independently produced things.
    """
    lat, lon = grid[..., 0], grid[..., 1]
    di = float(grid_spec["interval_line"])
    dj = float(grid_spec["interval_sample"])
    exp_line, exp_sample = np.meshgrid(
        np.arange(grid.shape[0], dtype=np.float64) * di,
        np.arange(grid.shape[1], dtype=np.float64) * dj,
        indexing="ij",
    )
    # Grid nodes are indexed from the tiepoint corner, so compare corner-referenced
    # pixel coordinates (centre=False) against the declared integer lattice.
    line_c, sample_c = frame.xy_to_pixel(*frame.latlon_to_xy(lat, lon), centre=False)
    d_line = line_c - exp_line
    d_samp = sample_c - exp_sample
    sy, sx = frame.pixel_size_m[1], frame.pixel_size_m[0]
    inc = grid[..., 3]
    inc_valid = inc[inc > GRID_FILL + 1.0]

    return {
        "nodes_compared": int(lat.size),
        "grid_shape": [int(grid.shape[0]), int(grid.shape[1])],
        "node_spacing_pixels": {"line": di, "sample": dj},
        "sample_residual_px": {"max": round(float(np.abs(d_samp).max()), 4),
                               "rms": round(float(np.sqrt((d_samp ** 2).mean())), 4)},
        "line_residual_px": {"max": round(float(np.abs(d_line).max()), 4),
                             "rms": round(float(np.sqrt((d_line ** 2).mean())), 4)},
        "sample_residual_m": {"max": round(float(np.abs(d_samp).max() * sx), 2),
                              "rms": round(float(np.sqrt((d_samp ** 2).mean()) * sx), 2)},
        "line_residual_m": {"max": round(float(np.abs(d_line).max() * sy), 2),
                            "rms": round(float(np.sqrt((d_line ** 2).mean()) * sy), 2)},
        "grid_latitude_deg": {"min": round(float(lat.min()), 6), "max": round(float(lat.max()), 6)},
        "grid_incidence_deg": {"min": round(float(inc_valid.min()), 4),
                               "max": round(float(inc_valid.max()), 4),
                               "fill_nodes": int((inc <= GRID_FILL + 1.0).sum())},
        "verdict": "sub-pixel" if max(float(np.abs(d_samp).max()), float(np.abs(d_line).max())) < 1.0
                   else "CHECK: residual exceeds one pixel",
    }


def load_sri_frame(
    raw_dir: Path,
    product_stem: str,
    band: str = "lh",
    geometry_dir: Optional[Path] = None,
) -> Tuple[SarFrame, Optional[Dict[str, int]], Optional[np.ndarray]]:
    """
    Convenience loader for the DFSAR bundle layout used by this project.

    `product_stem` is e.g. 'ch2_sar_ncxl_20200808t201154198'. Returns the frame
    plus, when the geometry directory is present, the geolocation grid spec and
    the grid array itself so the caller can run `validate_against_grid`.
    """
    raw_dir = Path(raw_dir)
    tif = raw_dir / f"{product_stem}_d_sri_xx_cp_{band}_d18.tif"
    frame = read_geotiff_frame(tif)

    if geometry_dir is None:
        return frame, None, None
    geometry_dir = Path(geometry_dir)
    geom_xml = geometry_dir / f"{product_stem}_g_xxx_xx_cp_xx_d18.xml"
    grid_csv = geometry_dir / f"{product_stem}_g_sri_xx_cp_xx_d18.csv"
    if not geom_xml.exists() or not grid_csv.exists():
        return frame, None, None
    spec = parse_geolocation_grid_spec(geom_xml, "sri")
    grid = load_geolocation_grid(grid_csv, spec)
    frame.source = f"{frame.source} + {grid_csv.name} + {geom_xml.name}"
    return frame, spec, grid


# --- self-test / provenance dump --------------------------------------------
if __name__ == "__main__":
    import sys

    BUNDLE = Path(__file__).resolve().parents[3] / "data" / "pradan" / "raw"
    RAW = BUNDLE / "data" / "calibrated" / "20200808"
    GEOM = BUNDLE / "geometry" / "calibrated" / "20200808"
    STEM = "ch2_sar_ncxl_20200808t201154198"

    if not RAW.exists():
        print(f"raw bundle not present at {RAW} -- nothing to verify")
        sys.exit(0)

    frame, spec, grid = load_sri_frame(RAW, STEM, "lh", GEOM)
    print("=" * 78)
    print("DFSAR sri frame decoded from the product's own GeoTIFF tags")
    print("=" * 78)
    print(f"  shape            {frame.shape[0]} lines x {frame.shape[1]} samples")
    print(f"  pixel size       {frame.pixel_size_m[0]} m x {frame.pixel_size_m[1]} m")
    print(f"  tiepoint (E,N)   {frame.tiepoint_xy_m}")
    print(f"  projection       {frame.projection}")
    print(f"  radius / k0      {frame.radius_m} m / {frame.scale_factor}")
    print(f"  origin lat/lon   {frame.lat_origin_deg} / {frame.lon_origin_deg}")
    print(f"  raster type      {frame.raster_type} (1 = PixelIsArea)")
    print(f"  max scale error  {frame.stereographic_scale_error() * 100:.4f} %")
    print(f"  source           {frame.source}")

    if grid is not None and spec is not None:
        print("\n  ISRO geolocation grid cross-check")
        for k, v in validate_against_grid(frame, grid, spec).items():
            print(f"    {k:32s} {v}")

    mask_tif = RAW / f"{STEM}_d_sri_ma_cp_xx_d18.tif"
    valid = None
    if tifffile is not None:
        lh = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif"))
        lv = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lv_d18.tif"))
        valid = (lh > 0) & (lv > 0)
        if mask_tif.exists():
            isro = tifffile.imread(str(mask_tif))
            print(f"\n  amplitude-valid fraction   {valid.mean():.4f}")
            print(f"  ISRO sri_ma > 0 fraction   {(isro > 0).mean():.4f}")

    print("\n  geodetic_frame (replaces the old hardcoded bounds block)")
    gf = frame.geodetic_frame(valid_mask=valid, grid_spec=spec,
                              grid_validation=validate_against_grid(frame, grid, spec)
                              if grid is not None and spec is not None else None)
    print(json.dumps(gf, indent=2)[:4000])
