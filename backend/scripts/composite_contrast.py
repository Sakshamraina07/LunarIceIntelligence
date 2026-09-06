"""
Verify the COMPOSITE, not the base: is relief still readable under each layer?

WHY THIS IS A SEPARATE CHECK
----------------------------
hillshade_histogram.py checks the BARE hillshade against the CSS filter. That is
necessary and not sufficient. Two things happen after it:

  * the shipped relief scheme is four azimuths across a 135 deg arc, which
    carries 37 % less contrast than the single 315 deg sun it replaced
    (std 0.0420 against 0.0668) -- see METHODS 8.6;
  * every science layer is then composited ON TOP of it at some opacity.

So the relief a viewer actually sees is weaker than the one that was measured,
and by an amount no bare-base check can report. If the composite hides the
landforms, the fix is the LAYER'S OPACITY, not the hillshade's brightness -- that
was just measured into compliance and must not be undone to compensate for
something happening two steps later.

WHAT IS MEASURED
----------------
For each science layer, over the pixels that layer actually covers:

  relief retention = std(highpass(composite luminance))
                     / std(highpass(filtered hillshade luminance))

A high-pass (the image minus a 9 px box mean) isolates landform-scale structure
from the layer's own broad colour gradient, so a smooth science field cannot
inflate the score. Retention is 1.0 when the composite carries the base's relief
untouched and 0.0 when it is gone. The correlation of the two high-passes is
reported beside it: retention says how much structure survives, correlation says
whether the surviving structure is still the TERRAIN'S.

Usage:
    python -u backend/scripts/composite_contrast.py [--opacity 0.72]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter

BASE_DIR = Path(__file__).resolve().parents[2]
LAYERS = BASE_DIR / "frontend" / "public" / "layers"
MC_CSS = BASE_DIR / "frontend" / "src" / "mission" / "mc.css"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

#: Retention below this reads as "the landforms are gone".
RETENTION_FLOOR = 0.25
#: And the surviving structure must actually BE the terrain's.
CORR_FLOOR = 0.30
HIGHPASS_PX = 9


def read_css_filter() -> tuple[float, float, str]:
    """The filter the app applies, READ from mc.css. Never restated here."""
    try:
        text = MC_CSS.read_text(encoding="utf-8")
    except OSError:
        return 1.0, 1.0, "mc.css unreadable - SOURCE NOT VERIFIED"
    for m in re.finditer(r"(?<!backdrop-)filter:\s*([^;]+);", text):
        decl = m.group(1)
        c = re.search(r"contrast\(([0-9.]+)\)", decl)
        b = re.search(r"brightness\(([0-9.]+)\)", decl)
        if c and b:
            return float(c.group(1)), float(b.group(1)), decl.strip()
    return 1.0, 1.0, "no contrast()+brightness() filter found"


def css_filter(v: np.ndarray, contrast: float, brightness: float) -> np.ndarray:
    c = v.astype(np.float32) / 255.0
    c = np.clip(contrast * c + (0.5 - 0.5 * contrast), 0.0, 1.0)
    c = np.clip(brightness * c, 0.0, 1.0)
    return c * 255.0


def luma(rgb: np.ndarray) -> np.ndarray:
    return (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2])


def highpass(a: np.ndarray) -> np.ndarray:
    return a - uniform_filter(a, size=HIGHPASS_PX)


def load(name: str):
    im = Image.open(LAYERS / name)
    arr = np.asarray(im.convert("RGBA"), dtype=np.float32)
    return arr[..., :3], arr[..., 3]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--opacity", type=float, default=0.72)
    ap.add_argument("--scan", default="0.5,0.6,0.72,0.8,0.9,1.0")
    ap.add_argument("--out", default="docs/composite_contrast.json")
    args = ap.parse_args()

    manifest = json.loads((LAYERS / "layers.json").read_text(encoding="utf-8"))
    contrast, brightness, decl = read_css_filter()

    base_rgb, _ = load("hillshade.webp")
    base = css_filter(luma(base_rgb), contrast, brightness)
    base_hp = highpass(base)

    print("=" * 78)
    print("COMPOSITE CONTRAST - is the relief still readable under each layer?")
    print("=" * 78)
    print(f"  base filter (read from mc.css)  {decl}")
    print(f"  bare hillshade high-pass std    {base_hp.std():.4f}")
    print(f"  high-pass window                {HIGHPASS_PX} px")
    print(f"  retention floor                 {RETENTION_FLOOR:.2f}")
    print(f"\n  Relief retention = std(highpass(composite)) / "
          f"std(highpass(base)), over the pixels each layer covers.\n")

    scan = [float(x) for x in args.scan.split(",")]
    ids = [l["id"] for l in manifest["layers"] if l["id"] != "hillshade"]
    print(f"  {'layer':24s}" + "".join(f"{a:>8.2f}" for a in scan))
    rows = {}
    for lid in ids:
        entry = next(l for l in manifest["layers"] if l["id"] == lid)
        rgb, alpha = load(entry["file"])
        cover = alpha > 0
        if not cover.any():
            continue
        vals, corrs = [], []
        for a in scan:
            # Normal alpha compositing, exactly what Leaflet does with an
            # imageOverlay at `opacity` over the base pane. No blend mode.
            eff = (alpha / 255.0) * a
            comp = luma(rgb) * eff + base * (1.0 - eff)
            ch = highpass(comp)[cover]
            bh = base_hp[cover]
            vals.append(float(ch.std() / max(bh.std(), 1e-9)))
            # RETENTION ALONE CAN BE GAMED. A layer with strong texture of its
            # own -- speckle, in the radar layers' case -- raises the composite's
            # high-pass without any terrain surviving, and scores above 1.0 while
            # hiding the landforms completely. So the correlation of the two
            # high-passes is measured beside it: retention says how much
            # structure is there, correlation says whether it is the TERRAIN'S.
            corrs.append(float(np.corrcoef(ch, bh)[0, 1]))
        rows[lid] = {"label": entry["label"], "scan": scan,
                     "retention": vals, "correlation": corrs}
        print(f"  {lid:24s}" + "".join(f"{v:>8.2f}" for v in vals))
        print(f"  {'  (corr with base relief)':24s}" + "".join(f"{c:>8.2f}" for c in corrs))

    hold = args.opacity
    i = min(range(len(scan)), key=lambda k: abs(scan[k] - hold))
    print(f"\n  AT THE SHIPPED OPACITY {scan[i]:.2f}")
    worst, failed = None, []
    print(f"  {'layer':24s}{'retention':>11}{'corr':>8}   verdict")
    for lid, r in rows.items():
        v, c = r["retention"][i], r["correlation"][i]
        # BOTH must hold. Structure that does not correlate with the base is the
        # layer's own texture, not surviving terrain.
        ok = v >= RETENTION_FLOOR and c >= CORR_FLOOR
        score = min(v, 1.0) if c >= CORR_FLOOR else 0.0
        worst = score if worst is None else min(worst, score)
        if not ok:
            failed.append(lid)
        print(f"  {lid:24s}{v:>11.3f}{c:>8.2f}   "
              + ("relief readable" if ok else
                 "RELIEF GONE - lower this layer" if v < RETENTION_FLOOR else
                 "structure is the LAYER'S OWN, not terrain"))
    print()
    if not failed:
        print(f"  PASS - every layer keeps terrain relief (retention "
              f">= {RETENTION_FLOOR:.2f} AND correlation >= {CORR_FLOOR:.2f}).")
    else:
        print(f"  FAIL - {', '.join(failed)}")
        print("  Fix the LAYER OPACITY. Do NOT raise the hillshade brightness:")
        print("  that was measured into compliance in METHODS 8.7 and raising it")
        print("  would trade a real clipping rule for a composite problem.")

    (BASE_DIR / args.out).write_text(json.dumps({
        "css_filter": decl, "highpass_px": HIGHPASS_PX,
        "retention_floor": RETENTION_FLOOR, "correlation_floor": CORR_FLOOR,
        "base_highpass_std": float(base_hp.std()),
        "shipped_opacity": scan[i], "layers": rows,
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
