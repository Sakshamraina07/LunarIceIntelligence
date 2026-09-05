"""
print_footprint_polygon.py -- emit the REAL DFSAR amplitude footprint as a
Leaflet-CRS polygon, ready to paste into frontend/src/mission/MissionMap.tsx.

Why this exists
---------------
The Chandrayaan-2 DFSAR pass of 2020-08-08 records amplitude on only 15.64 % of
its own 2258 x 6618 sri raster. That is not a processing loss -- both L-band and
S-band `xx_cp_lh` / `xx_cp_lv` products are nonzero on exactly 15.64 % of pixels,
and every nonzero pixel lies inside the ISRO `sri_ma` flag layer. The swath is a
dense, contiguous band roughly 351 native pixels (8.8 km) thick that runs the
full 6618-sample length while sliding 1222 lines downward, i.e. a diagonal
ribbon across an axis-aligned projected frame.

A diagonal ribbon has a bounding box that is almost the whole frame (1783 x 6606,
still only 19.8 % valid), so cropping cannot fix the emptiness. What the map CAN
do is stop pretending the empty 84 % is terrain: this script exports the ribbon
outline so MissionMap.tsx can draw it and dim everything outside it.

Output is in Leaflet CRS.Simple units, matching MissionMap.tsx exactly:

    lng = sample / 2**MAX_NATIVE
    lat = (NATIVE_LINES - line) / 2**MAX_NATIVE      # data is bottom-aligned

Run:  python backend/scripts/print_footprint_polygon.py
"""
from __future__ import annotations

import pathlib

import numpy as np
import tifffile

BASE_DIR = pathlib.Path(__file__).resolve().parents[2]
VALID_TIF = BASE_DIR / "data" / "pradan" / "native" / "valid_native.tif"

MAX_NATIVE = 5
SCALE = float(2 ** MAX_NATIVE)
STEP = 64          # sample columns between polygon vertices
MIN_RUN = 8        # ignore columns with fewer valid pixels than this


def main() -> None:
    valid = tifffile.imread(str(VALID_TIF)) > 0
    lines, samples = valid.shape

    print("=" * 74)
    print("REAL DFSAR AMPLITUDE FOOTPRINT")
    print("=" * 74)
    print(f"raster           {lines} lines x {samples} samples")
    print(f"valid amplitude  {valid.mean() * 100:.2f} % of the raster")

    rs = np.flatnonzero(valid.any(axis=1))
    cs = np.flatnonzero(valid.any(axis=0))
    box = valid[rs[0]:rs[-1] + 1, cs[0]:cs[-1] + 1]
    print(f"bounding box     lines {rs[0]}..{rs[-1]}  samples {cs[0]}..{cs[-1]}"
          f"  ({box.shape[0]} x {box.shape[1]})")
    print(f"  valid inside it {box.mean() * 100:.2f} %  <- why cropping does not help")

    # Per-column band edges. The band is dense, so first/last valid line bound it.
    cols, top, bot, thick = [], [], [], []
    for c in range(0, samples, STEP):
        idx = np.flatnonzero(valid[:, c])
        if idx.size < MIN_RUN:
            continue
        cols.append(c)
        top.append(int(idx[0]))
        bot.append(int(idx[-1]))
        thick.append(int(idx.size))

    cols_a = np.asarray(cols)
    thick_a = np.asarray(thick)
    density = thick_a / np.maximum(np.asarray(bot) - np.asarray(top) + 1, 1)
    print(f"\nband thickness   median {np.median(thick_a):.0f} px "
          f"= {np.median(thick_a) * 25 / 1000:.2f} km   "
          f"(p10 {np.percentile(thick_a, 10):.0f}, p90 {np.percentile(thick_a, 90):.0f})")
    print(f"band density     {density.mean() * 100:.2f} % of pixels between the two "
          "edges are valid (a solid ribbon, not speckle)")
    print(f"vertices         {len(cols)} per edge, every {STEP} samples")

    def to_crs(line: int, sample: int) -> tuple[float, float]:
        return round((lines - line) / SCALE, 4), round(sample / SCALE, 4)

    # Closed ring: along the top edge left->right, back along the bottom edge.
    ring = [to_crs(t, c) for c, t in zip(cols, top)]
    ring += [to_crs(b, c) for c, b in zip(reversed(cols), reversed(bot))]

    print("\n--- paste into frontend/src/mission/MissionMap.tsx ---\n")
    print("const FOOTPRINT_RING: [number, number][] = [")
    for i in range(0, len(ring), 6):
        chunk = ", ".join(f"[{a}, {b}]" for a, b in ring[i:i + 6])
        print(f"  {chunk},")
    print("];")
    print(f"\n// {len(ring)} vertices; encloses "
          f"{valid.mean() * 100:.2f} % of the frame ({thick_a.mean() * 25 / 1000:.2f} km "
          f"mean ribbon thickness at 25 m/px)")


if __name__ == "__main__":
    main()
