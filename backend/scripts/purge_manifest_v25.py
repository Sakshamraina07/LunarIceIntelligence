"""
purge_manifest_v25.py -- the renderings of DFSAR-derived quantities finer than 200 m per pixel that were
removed from the repository and its history (V24, V25), recorded as sha256 + pixel size. (V25 Part A)

    python backend/scripts/purge_manifest_v25.py            # build the manifest and copy the files out, BEFORE the history rewrite
    python backend/scripts/purge_manifest_v25.py --verify   # check local copies against docs/removed_native_renderings.json

WHY. The two 25 m/px layer files, the CPR/DOP tile pyramid and the application screenshots that show the CPR or DOP
proxy at map zoom are one-to-one per-pixel renderings of a third-party-copyrighted product (ISRO's Chandrayaan-2 DFSAR).
They are not published. This record keeps what is needed to know they existed and to tell whether a local copy is the
same file: path, every blob version (git blob id, sha256, bytes), the pixel size at which it renders the quantity
(measured: the tile and image size, the application's recorded map zoom, the frame's 646.289 m per CRS unit), and the
reason. Nothing here is a pixel value.

BUILD mode reads the pre-rewrite history (every blob version of every matching path on any ref, the two V24 layer
files from D:\\FYP_local_layers), writes the manifest, and copies every version to data/local_layers/<path>[.<blob8>]
(gitignored) and to D:\\FYP_local_layers\\removed_v25\\ (outside the repository). VERIFY mode: for each recorded sha256
looks for a local copy under data/local_layers/ (or $LUNAR_ICE_LOCAL_LAYERS): every file found must match its sha256
(else FAIL); a manifest whose files are absent prints REQUIRES LOCAL DATA and exits 77, never PASS.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "removed_native_renderings.json"
LOCAL = Path(os.environ.get("LUNAR_ICE_LOCAL_LAYERS", str(BASE_DIR / "data" / "local_layers")))
BACKUP = Path(r"D:\FYP_local_layers\removed_v25")
V24_DIR = Path(r"D:\FYP_local_layers")
REQUIRES_LOCAL_DATA_RC = 77
M_PER_UNIT = 646.289062          # layers.json::crs.metres_per_unit (frame 165.45 km = 256 units)
PATTERNS = (r"^backend/tiles/faustini/(cpr_heatmap|dop_heatmap)/",
            r"^docs/gate6/(before|after)\.(full|detail)\.(cpr_heatmap|dop_heatmap)\.png$",
            r"^docs/map_(before|after)_cpr\.png$",
            r"^docs/v8_opening_view\.png$",
            r"^docs/v8_(opening_view|after_reset|full_extent)\.before\.png$")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def git(*a, raw=False, inp=None):
    r = subprocess.run(["git", *a], capture_output=True, cwd=str(BASE_DIR), input=inp)
    return r.stdout if raw else r.stdout.decode("utf-8", "replace")


def mpp(zoom: float) -> float:
    """Application map zoom -> metres per screen pixel (CRS.Simple: 2**zoom pixels per unit)."""
    return M_PER_UNIT / 2 ** zoom


def zoom_of(path: str) -> tuple[float, str]:
    if path.startswith("docs/gate6/"):
        z = 4.5 if ".detail." in path else 2.1661630826
        return z, "docs/gate6/capture.{before,after}.json: view `detail` zoom 4.5, `full` zoom 2.166 (state.zoom)"
    if path.startswith("docs/map_"):
        return 4.0, "docs/verify_map.json: view.zoom 4"
    if path == "docs/v8_opening_view.png":
        return 3.4999582438, "docs/verify_v8_view.json: opening.zoom 3.5; the on-screen readout of the CPR version reads 57.1 m/px"
    if path.endswith("opening_view.before.png"):
        return 3.4999582438, "docs/verify_v8_view.before.json: opening zoom 3.5, layers cpr_heatmap + hillshade"
    if path.endswith("after_reset.before.png"):
        return 3.0, "docs/verify_v8_view.before.json: after-reset zoom 3, layers cpr_heatmap + hillshade"
    return 2.188588845707348, "docs/verify_v8_view.before.json: full-extent zoom 2.19, layers cpr_heatmap + hillshade"


def build() -> int:
    objs = {}
    for l in git("log", "--all", "--raw", "--no-abbrev", "--format=C %H").split("\n"):
        m = re.match(r":\d+ \d+ [0-9a-f]+ ([0-9a-f]+) [AMR]\d*\t(.+?)(?:\t(.+))?$", l)
        if m and m.group(1) != "0" * 40:
            p = m.group(3) or m.group(2)
            if any(re.search(x, p) for x in PATTERNS):
                objs.setdefault(p, set()).add(m.group(1))
    first = {}
    cur = None
    for l in git("log", "--all", "--diff-filter=A", "--name-only", "--format=C %h %ad", "--date=short").split("\n"):
        if l.startswith("C "):
            cur = l[2:]
        elif l.strip():
            first.setdefault(l.strip(), cur)
    entries = []
    for p, ids in sorted(objs.items()):
        for oid in sorted(ids):
            b = git("cat-file", "blob", oid, raw=True)
            e = {"path": p, "git_blob": oid, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b),
                 "first_commit_before_purge": first.get(p)}
            if p.startswith("backend/tiles/"):
                from PIL import Image
                im = Image.open(io.BytesIO(b))
                e["image_px"] = list(im.size)
                z = int(p.split("/")[-3])
                e["tile_zoom"] = z
            else:
                from PIL import Image
                im = Image.open(io.BytesIO(b))
                e["image_px"] = list(im.size)
                z, src = zoom_of(p)
                e["map_zoom"] = round(z, 4)
                e["metres_per_pixel"] = round(mpp(z), 1)
                e["pixel_size_source"] = src
            entries.append(e)
            for root in (LOCAL, BACKUP):
                dest = root / p
                if len({x for x in objs[p]}) > 1:
                    dest = dest.with_name(dest.name + "." + oid[:8])
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b)
    # the two V24 layer files
    for name, bid in (("cpr_heatmap.webp", "25e989d5014b25c9607e8f098f0787d4a3c13513"), ("dop_heatmap.webp", "fc65c9dca918f8e8cd6d79595645d4cfe523003b")):
        f = V24_DIR / name
        b = f.read_bytes()
        from PIL import Image
        im = Image.open(io.BytesIO(b))
        e = {"path": f"frontend/public/layers/{name}", "git_blob": bid, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b),
             "first_commit_before_purge": "4a683ea 2026-09-05", "image_px": list(im.size), "metres_per_pixel": 25.0,
             "pixel_size_source": "layers.json::native.metres_per_pixel (6618 x 2258 at 25 m): the delivered frame itself", "removed_in": "V24"}
        entries.append(e)
        for root in (LOCAL, BACKUP):
            (root / e["path"]).parent.mkdir(parents=True, exist_ok=True)
            (root / e["path"]).write_bytes(b)
    tiles = [e for e in entries if e["path"].startswith("backend/tiles/")]
    doc = {"schema": "lunar-ice/removed-native-renderings/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/purge_manifest_v25.py", "seed": None, "seed_note": "draws nothing",
           "frame": {"product": "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_xx_d18", "px": [6618, 2258], "metres_per_pixel": 25.0,
                     "extent_km": [165.45, 56.45], "metres_per_crs_unit": M_PER_UNIT},
           "rule": "no rendering of a DFSAR-derived quantity at a resolution finer than 200 m per pixel is published",
           "tile_pyramid_pixel_size": ("256 px tiles, zoom 0-3: the generator of the first commit resized the 6618 x 2258 frame to a "
                                       "2**z * 256 px square, so zoom 3 is 2048 px per axis: 165 450 m / 2048 = 80.8 m/px along the swath and "
                                       "56 450 m / 2048 = 27.6 m/px across it"),
           "paths_patterns": list(PATTERNS), "entries": entries,
           "summary": {"entries": len(entries), "distinct_paths": len({e['path'] for e in entries}), "bytes": sum(e['bytes'] for e in entries),
                       "tile_files": len(tiles)},
           "local_copies": {"expected_under": "data/local_layers/<path> (or $LUNAR_ICE_LOCAL_LAYERS); a path with several versions is stored as <path>.<blob8>",
                            "verification": "purge_manifest_v25.py --verify; G28 C8 (REQUIRES LOCAL DATA when absent, FAIL on a mismatch)"},
           "run_info": run_info()}
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"  {len(entries)} blob versions, {doc['summary']['distinct_paths']} paths, {doc['summary']['bytes']:,} bytes; copied to {LOCAL} and {BACKUP}")
    return 0


def verify() -> int:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    missing, ok, bad = [], 0, []
    for e in doc["entries"]:
        cands = [LOCAL / e["path"], LOCAL / (e["path"] + "." + e["git_blob"][:8])]
        f = next((c for c in cands if c.is_file()), None)
        if f is None:
            missing.append(e["path"])
        elif hashlib.sha256(f.read_bytes()).hexdigest() == e["sha256"]:
            ok += 1
        else:
            bad.append(e["path"])
    if bad:
        print(f"  FAIL: {len(bad)} local file(s) differ from their recorded sha256: {bad[:5]}")
        return 1
    if missing and not ok:
        print(f"  REQUIRES LOCAL DATA: {LOCAL} (the local copies of {len(doc['entries'])} removed renderings are not on this machine; "
              f"the record docs/removed_native_renderings.json is tracked, the files are not)")
        return REQUIRES_LOCAL_DATA_RC
    print(f"  {ok} local copies match their sha256" + (f"; {len(missing)} not present locally" if missing else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(verify() if "--verify" in sys.argv else build())
