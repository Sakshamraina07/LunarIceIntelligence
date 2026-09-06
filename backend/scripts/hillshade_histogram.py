"""
hillshade_histogram.py — measure the base raster, and measure what the CSS
filter on `.mc-raster--base` does to it.

Why this exists: `mc.css` carries `filter: contrast(1.14) brightness(1.16)
saturate(0.92)` on the terrain base. That is a rendering decision applied to
measured (soon) topography, and it was never checked against the actual pixel
distribution — so it could be silently clipping the sunlit crests to flat white.
This prints the numbers instead of guessing.

CSS filter arithmetic, per the Filter Effects spec (shorthand functions run with
color-interpolation-filters: sRGB, and each primitive clamps to [0,1]):

    contrast(a):   c -> a*c + (0.5 - 0.5*a)
    brightness(b): c -> b*c
    saturate(s):   colour matrix; identity on a neutral grey

Applied in the order written. Spot check against the handoff: v=140 ->
1.14*0.549 - 0.07 = 0.5559 -> *1.16 = 0.6448 -> 164.4. Matches.

Usage:
    python backend/scripts/hillshade_histogram.py               # current filter
    python backend/scripts/hillshade_histogram.py 1.14 1.10     # try contrast/brightness
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

BASE_DIR = Path(__file__).resolve().parents[2]
IMG = BASE_DIR / "frontend" / "public" / "layers" / "hillshade.webp"

MC_CSS = BASE_DIR / "frontend" / "src" / "mission" / "mc.css"


def read_css_filter() -> tuple[float, float, str]:
    """READ the filter out of mc.css instead of restating it here.

    These were literals -- CONTRAST = 1.14, BRIGHTNESS = 1.16, under a comment
    saying "what mc.css:449 says today" -- while mc.css actually said
    contrast(1.06) brightness(1.10). So the check tested a filter the app does
    not apply, and would have passed or failed on a fiction. A verifier that
    restates the thing it verifies is not a verifier.
    """
    import re
    try:
        text = MC_CSS.read_text(encoding="utf-8")
    except OSError:
        return 1.0, 1.0, "mc.css unreadable — SOURCE NOT VERIFIED"
    # The base-map filter: a `filter:` declaration carrying contrast() and
    # brightness(), ignoring the backdrop-filter blurs.
    for m in re.finditer(r"(?<!backdrop-)filter:\s*([^;]+);", text):
        decl = m.group(1)
        c = re.search(r"contrast\(([0-9.]+)\)", decl)
        b = re.search(r"brightness\(([0-9.]+)\)", decl)
        if c and b:
            return float(c.group(1)), float(b.group(1)), decl.strip()
    return 1.0, 1.0, "no contrast()+brightness() filter found in mc.css"


CONTRAST, BRIGHTNESS, CSS_DECL = read_css_filter()


def css_filter(v8: np.ndarray, contrast: float, brightness: float) -> np.ndarray:
    """8-bit in, 8-bit out, following the CSS primitive chain with clamping."""
    c = v8.astype(np.float32) / 255.0
    c = np.clip(contrast * c + (0.5 - 0.5 * contrast), 0.0, 1.0)   # contrast()
    c = np.clip(brightness * c, 0.0, 1.0)                          # brightness()
    # saturate(0.92) is a colour matrix: identity on neutral grey, and the
    # hillshade is neutral grey, so it is deliberately not modelled here.
    return np.rint(c * 255.0).astype(np.uint8)


def describe(name: str, v: np.ndarray) -> dict:
    d = {
        "mean": float(v.mean()),
        "median": float(np.median(v)),
        "p2": float(np.percentile(v, 2)),
        "p98": float(np.percentile(v, 98)),
        "min": int(v.min()),
        "max": int(v.max()),
        "clip0": float((v == 0).mean()),
        "clip255": float((v == 255).mean()),
    }
    print(f"  {name:<22s} mean {d['mean']:7.2f}   median {d['median']:6.1f}   "
          f"p2 {d['p2']:6.1f}   p98 {d['p98']:6.1f}   "
          f"min {d['min']:3d}  max {d['max']:3d}   "
          f"clip@0 {d['clip0'] * 100:6.3f} %   clip@255 {d['clip255'] * 100:6.3f} %")
    return d


def main() -> int:
    contrast = float(sys.argv[1]) if len(sys.argv) > 1 else CONTRAST
    brightness = float(sys.argv[2]) if len(sys.argv) > 2 else BRIGHTNESS

    im = Image.open(IMG)
    print(f"file      {IMG}")
    print(f"mode      {im.mode}   size {im.size[0]} x {im.size[1]} = {im.size[0] * im.size[1]:,} px")

    arr = np.asarray(im.convert("RGBA"))
    rgb, a = arr[..., :3], arr[..., 3]
    # The hillshade covers 100 % of the frame (it is terrain, not radar), so
    # alpha should be fully opaque. Measured, not assumed:
    print(f"alpha     opaque {float((a == 255).mean()) * 100:.3f} %   "
          f"transparent {float((a == 0).mean()) * 100:.3f} %")
    spread = int(np.abs(rgb[..., 0].astype(np.int16) - rgb[..., 2].astype(np.int16)).max())
    print(f"neutral   max |R-B| = {spread}  ({'neutral grey' if spread <= 2 else 'tinted'})")

    # Rec.709 luma is what a viewer's eye integrates; on a neutral image it is
    # the grey value itself, so this is exact rather than approximate here.
    lum = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2])
    v = np.rint(lum).astype(np.uint8)

    print(f"\n8-bit luminance histogram — hillshade.webp, all {v.size:,} px")
    before = describe("SOURCE (no filter)", v)
    print(f"\nafter  filter: contrast({contrast}) brightness({brightness}) saturate(0.92)")
    after = describe(f"POST-FILTER", css_filter(v, contrast, brightness))

    ok_median = after["median"] <= 190.0
    ok_clip = after["clip255"] <= 0.01
    print(f"\nrule check   post-filter median <= 190 : "
          f"{'PASS' if ok_median else 'FAIL'}  ({after['median']:.1f})")
    print(f"             clip@255       <= 1 %  : "
          f"{'PASS' if ok_clip else 'FAIL'}  ({after['clip255'] * 100:.3f} %)")

    if not (ok_median and ok_clip):
        print("\nwalking brightness back (contrast held at "
              f"{contrast}) until both hold:")
        b = brightness
        while b > 0.80:
            f = describe(f"brightness({b:.2f})", css_filter(v, contrast, b))
            if f["median"] <= 190.0 and f["clip255"] <= 0.01:
                print(f"\n  -> lowest failing rule cleared at brightness({b:.2f})")
                break
            b = round(b - 0.02, 2)

    print(f"\nreference   a mid-grey v=140 maps to "
          f"{int(css_filter(np.array([140], np.uint8), contrast, brightness)[0])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
