"""
compare_tiles_vs_single.py -- BEFORE/AFTER evidence for handoff v4.

BEFORE: the committed tile pyramid in backend/tiles/faustini/<layer>/5/x/y.png,
        stitched back into one mosaic exactly as Leaflet would have assembled it.
        Every tile was normalised against its OWN pixels, so each 256x256 square
        got its own contrast curve -- that is the origin of the "patchy" look and
        the visible seams between neighbours.

AFTER:  frontend/public/layers/<layer>.webp, normalised ONCE over the whole
        14.9 MP array over valid pixels only.

The script prints per-tile statistics that quantify the seam problem (spread of
per-tile p50/p95 across the mosaic) and writes a stacked PNG for eyeballing.

Run:  python backend/scripts/compare_tiles_vs_single.py --layer cpr_heatmap
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

BASE_DIR = Path(__file__).resolve().parents[2]
TILE_DIR = BASE_DIR / "backend" / "tiles" / "faustini"
LAYER_DIR = BASE_DIR / "frontend" / "public" / "layers"
OUT_PNG = Path("/tmp/before_after_layers.png")

TILE_PX = 256


def stitch(layer: str, zoom: int, flip_y: bool) -> tuple[np.ndarray, dict]:
    """Reassemble one zoom level of the old pyramid into a single RGBA array."""
    root = TILE_DIR / layer / str(zoom)
    if not root.is_dir():
        raise SystemExit(f"no legacy tiles at {root}")

    tiles: dict[tuple[int, int], Path] = {}
    for xd in sorted(root.iterdir()):
        if not xd.is_dir():
            continue
        for f in sorted(xd.glob("*.png")):
            tiles[(int(xd.name), int(f.stem))] = f

    xs = [x for x, _ in tiles]
    ys = [y for _, y in tiles]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cols, rows = x1 - x0 + 1, y1 - y0 + 1

    canvas = np.zeros((rows * TILE_PX, cols * TILE_PX, 4), np.uint8)
    per_tile = []
    for (x, y), path in tiles.items():
        a = np.array(Image.open(path).convert("RGBA"))
        ty = (y1 - y) if flip_y else (y - y0)
        canvas[ty * TILE_PX:(ty + 1) * TILE_PX, (x - x0) * TILE_PX:(x + 1) * TILE_PX] = a
        lum = a[..., :3].astype(np.float32).mean(axis=2)
        m = a[..., 3] > 0
        if m.sum() > 512:
            per_tile.append((np.percentile(lum[m], 50), np.percentile(lum[m], 95),
                             float(m.mean())))

    pt = np.asarray(per_tile, np.float32)
    stats = {
        "tiles": len(tiles),
        "grid": f"{cols} x {rows} tiles",
        "canvas": f"{canvas.shape[1]} x {canvas.shape[0]} px",
        "aspect": round(canvas.shape[1] / canvas.shape[0], 3),
        "p50_spread": (float(pt[:, 0].min()), float(pt[:, 0].max()), float(pt[:, 0].std())),
        "p95_spread": (float(pt[:, 1].min()), float(pt[:, 1].max()), float(pt[:, 1].std())),
        "n_scored": int(pt.shape[0]),
    }
    return canvas, stats


def to_width(rgba: np.ndarray, width: int) -> np.ndarray:
    """Area-average downsample that respects alpha (no dark halo bleed)."""
    import cv2
    h, w = rgba.shape[:2]
    ph = max(1, int(round(h * width / float(w))))
    a = rgba[..., 3].astype(np.float32) / 255.0
    num = cv2.resize(rgba[..., :3].astype(np.float32) * a[..., None], (width, ph),
                     interpolation=cv2.INTER_AREA)
    den = cv2.resize(a, (width, ph), interpolation=cv2.INTER_AREA)
    rgb = np.clip(num / np.maximum(den, 1e-6)[..., None], 0, 255).astype(np.uint8)
    return np.dstack([rgb, np.clip(den * 255, 0, 255).astype(np.uint8)])


def on_dark(rgba: np.ndarray) -> np.ndarray:
    """Composite over the app's #03060c so transparency reads as the map's void."""
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    bg = np.array([3, 6, 12], np.float32)
    return np.clip(rgba[..., :3].astype(np.float32) * a + bg * (1 - a), 0, 255).astype(np.uint8)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="cpr_heatmap")
    ap.add_argument("--zoom", type=int, default=5)
    ap.add_argument("--width", type=int, default=1200)
    ap.add_argument("--flip-y", action="store_true", default=True)
    args = ap.parse_args()

    print(f"\nBEFORE  legacy pyramid  {TILE_DIR / args.layer / str(args.zoom)}")
    old, stats = stitch(args.layer, args.zoom, args.flip_y)
    for k, v in stats.items():
        print(f"  {k:14s} {v}")

    lo, hi, sd = stats["p50_spread"]
    print(f"\n  per-tile median brightness ranges {lo:.1f} .. {hi:.1f} (sd {sd:.1f}) of 255")
    print(f"  per-tile p95 brightness    ranges {stats['p95_spread'][0]:.1f} .. "
          f"{stats['p95_spread'][1]:.1f} (sd {stats['p95_spread'][2]:.1f})")
    print("  ^ each tile carried its own contrast curve -> visible seams, "
          "no comparable colour scale")

    new_path = LAYER_DIR / f"{args.layer}.webp"
    print(f"\nAFTER   single image     {new_path}")
    new = np.array(Image.open(new_path).convert("RGBA"))
    print(f"  canvas         {new.shape[1]} x {new.shape[0]} px")
    print(f"  aspect         {round(new.shape[1] / new.shape[0], 3)}  (true 6618/2258 = 2.931)")
    print(f"  requests       1 image (+1 preview) vs {stats['tiles']} tiles at z{args.zoom} alone")

    a = on_dark(to_width(old, args.width))
    b = on_dark(to_width(new, args.width))
    gap = np.full((14, args.width, 3), 20, np.uint8)
    stack = np.vstack([a, gap, b])
    Image.fromarray(stack).save(OUT_PNG)
    print(f"\nwrote {OUT_PNG}  (top = BEFORE tiles, bottom = AFTER single image)")


if __name__ == "__main__":
    main()
