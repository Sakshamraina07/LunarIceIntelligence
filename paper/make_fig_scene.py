"""
make_fig_scene.py -- the data figure (v17a referee report, P4).

    cd paper && python make_fig_scene.py

fig_scene.pdf, single column: the complex product's sample CPR (log colour)
over the 2020-08-08 frame, in along-track / cross-track map coordinates
(south-polar stereographic, rotated to the frame's long axis), with the LOLA
PSR outline (cyan, 0.5 pt, in both panels and the legend), crater F2's disc and the cells
the published rule selects. Panel (b) lies wholly inside the PSR, so its outline has no edge
there; the nearest edge is 4 km across track.
(a) the whole frame at 100 m bins; (b) 12 x 3.8 km around F2 at 25 m bins (F2 sits on the swath's edge).

Reads data/derived/fig_scene/fig_scene_cache.npz, written by
backend/scripts/f2_complex_product.py (geolocation from the bundle's SLI
tie-point grid). The cache holds binned values derived from ISRO rasters and
stays under the gitignored data/; only the PDF is committed.

STIX, fonttype 42 (no Type 3), every font >= 7 pt; the two CPR images are
rasterized at 300 dpi inside the vector frame, and the strip's 26 462 dots are
drawn into that raster layer.
"""
from pathlib import Path

import numpy as np
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle

mpl.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.family": "serif", "font.serif": ["STIXGeneral"], "mathtext.fontset": "stix",
    "font.size": 7, "axes.labelsize": 7, "legend.fontsize": 7,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.linewidth": 0.6,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / "data" / "derived" / "fig_scene" / "fig_scene_cache.npz"
VMIN, VMAX = float(np.log10(0.03)), float(np.log10(2.0))   # sample CPR 0.03 to 2
PSR_C, F2_C, SEL_C = "#00e5ff", "#ff2d2d", "#ff9f1c"
PSR_LW = 0.5               # pt; the same colour and width on the image and in the legend
LEGEND = ("PSR (LOLA)", "F2 disc", "published rule selects")
ZOOM_Y = (-3.0, 0.8)     # km across track: F2 sits on the swath edge


def filled(a, max_bins=None):
    """Empty bins (no cell fell in them: the cells are ~10 x 23 m, the bins
    25 m) take their nearest bin's value, so the PSR contour traces the mask,
    not the sampling gaps. With max_bins, only gaps within that many bins of
    data are filled; the true no-data area stays empty."""
    from scipy.ndimage import distance_transform_edt
    bad = ~np.isfinite(a)
    if not bad.any():
        return a
    d, idx = distance_transform_edt(bad, return_distances=True, return_indices=True)
    out = a[tuple(idx)]
    if max_bins is not None:
        out = np.where(d <= max_bins, out, np.nan)
    return out


def main(out="fig_scene.pdf"):
    z = np.load(CACHE)
    B, u0, v0 = float(z["bin_m"]), float(z["u0"]), float(z["v0"])
    img = z["log10_cpr"]
    nv, nu = img.shape
    ext = [0, nu * B / 1000, 0, nv * B / 1000]
    fu, fv = (float(z["f2_u"]) - u0) / 1000, (float(z["f2_v"]) - v0) / 1000

    # 3.44 in: the tight bbox then stays under 3.5 in, so at the column width the
    # figure scales UP and the 7 pt text stays at or above 7 pt (v18a N8)
    fig = plt.figure(figsize=(3.44, 1.95))
    gs = fig.add_gridspec(2, 2, height_ratios=[0.45, 1.0], width_ratios=[1.0, 0.035],
                          hspace=0.42, wspace=0.04)
    a1 = fig.add_subplot(gs[0, :])
    a1.imshow(np.ma.masked_invalid(img), origin="lower", extent=ext, cmap="viridis",
              vmin=VMIN, vmax=VMAX, interpolation="nearest", rasterized=True, aspect="equal")
    a1.contour(np.linspace(ext[0], ext[1], nu), np.linspace(ext[2], ext[3], nv),
               np.ma.masked_invalid(filled(z["psr_frac"], 2)), levels=[0.5], colors=PSR_C, linewidths=PSR_LW)
    a1.scatter((z["sel_u"] - u0) / 1000, (z["sel_v"] - v0) / 1000, s=0.04, c=SEL_C, lw=0,
               rasterized=True)
    zw = 6.0
    # the (b) window in (a): white, not the F2-disc colour (v20 S4)
    a1.add_patch(Rectangle((fu - zw, fv + ZOOM_Y[0]), 2 * zw, ZOOM_Y[1] - ZOOM_Y[0], fill=False,
                           ec="white", lw=0.6))
    a1.set_xlabel("along track (km)", labelpad=1)
    a1.set_ylabel("across\n(km)", labelpad=1)
    a1.set_yticks([0, 10])
    a1.text(0.005, 1.04, "(a)", transform=a1.transAxes, va="bottom")

    a2 = fig.add_subplot(gs[1, 0])
    zb, zu0, zv0 = float(z["zoom_bin_m"]), float(z["zoom_u0"]), float(z["zoom_v0"])
    zi = z["zoom_log10_cpr"]
    zext = [(zu0 - float(z["f2_u"])) / 1000, (zu0 + zi.shape[1] * zb - float(z["f2_u"])) / 1000,
            (zv0 - float(z["f2_v"])) / 1000, (zv0 + zi.shape[0] * zb - float(z["f2_v"])) / 1000]
    im = a2.imshow(np.ma.masked_invalid(filled(zi, 2)), origin="lower", extent=zext, cmap="viridis",
                   vmin=VMIN, vmax=VMAX, interpolation="nearest", rasterized=True, aspect="equal")
    a2.contour(np.linspace(zext[0], zext[1], zi.shape[1]), np.linspace(zext[2], zext[3], zi.shape[0]),
               np.ma.masked_invalid(filled(z["zoom_psr_frac"], 2)), levels=[0.5], colors=PSR_C, linewidths=PSR_LW)
    a2.add_patch(Circle((0, 0), float(z["f2_r"]) / 1000, fill=False, ec=F2_C, lw=0.8))
    a2.scatter((z["zoom_sel_u"] - float(z["f2_u"])) / 1000, (z["zoom_sel_v"] - float(z["f2_v"])) / 1000,
               s=1.2, c=SEL_C, lw=0)
    a2.set_xlim(-6, 6)
    a2.set_ylim(*ZOOM_Y)
    a2.set_xlabel("along track from F2 (km)", labelpad=1)
    a2.set_ylabel("across (km)", labelpad=1)
    a2.text(0.005, 1.02, "(b)", transform=a2.transAxes, va="bottom")
    handles = [Line2D([], [], color=PSR_C, lw=PSR_LW, label=LEGEND[0]),
               Line2D([], [], color=F2_C, lw=0.8, label=LEGEND[1]),
               Line2D([], [], color=SEL_C, marker="o", ms=2.5, lw=0, label=LEGEND[2])]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.46, -0.035), ncol=3,
               frameon=False, handletextpad=0.4, columnspacing=1.0, handlelength=1.4)
    ca = fig.add_subplot(gs[1, 1])
    cb = fig.colorbar(im, cax=ca)
    ticks = [0.03, 0.1, 0.3, 1.0, 2.0]
    cb.set_ticks(np.log10(ticks))
    cb.set_ticklabels([f"{t:g}" for t in ticks])
    cb.set_label("sample CPR", labelpad=2)
    fig.savefig(out, dpi=300)
    plt.close(fig)
    return LEGEND


if __name__ == "__main__":
    print(main())
