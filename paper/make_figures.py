#!/usr/bin/env python3
"""
Figures for the DFSAR detection-limits manuscript.

Every figure here is computed from a closed form or from a table of measured
scalars quoted in the caption -- none of them needs the rasters, which is why
they can be regenerated anywhere. The figures that DO need the rasters
(the CPR-DOP density, the mask map, the SLC azimuth spectrum) are specified
in the manuscript's OPEN items and must be produced in the project repo.

Print rules applied throughout, per IEEE practice and the dataviz method:
  - no dual axes anywhere; two measures -> two panels
  - identity never carried by colour alone: every series also has a distinct
    marker and linestyle, so the figures survive greyscale printing
  - one hue per sequential meaning; no rainbow
  - recessive grid and axes; thin marks; legend whenever >= 2 series
"""
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from scipy.stats import f as Fdist
from scipy.optimize import brentq

mpl.rcParams.update({
    # IEEE PDF eXpress rejects Type 3 fonts. fonttype 42 embeds TrueType
    # (Type 42) outlines instead. STIX ships inside matplotlib itself, so the
    # figure fonts are identical on every machine that regenerates them.
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "serif",
    "font.serif": ["STIXGeneral", "Times New Roman", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "axes.linewidth": 0.6,
    "grid.linewidth": 0.4,
    "grid.alpha": 0.35,
    "lines.linewidth": 1.2,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

INK   = "#1b1b1b"
ACC1  = "#1f5fa9"   # ordered categorical slot 1
ACC2  = "#a3431f"   # slot 2
MUTED = "#6b6b6b"

COL1 = 3.5    # IEEE single column, inches
COL2 = 7.16   # IEEE double column, inches


def relsd(N):
    return np.sqrt((2 * N - 1) / (N * (N - 2)))


def skewF(N):
    d1 = d2 = 2.0 * N
    return ((2 * d1 + d2 - 2) * np.sqrt(8 * (d2 - 4))) / (
        (d2 - 6) * np.sqrt(d1 * (d1 + d2 - 2)))


def solve(f, target, lo, hi):
    return brentq(lambda N: f(N) - target, lo, hi)


# ----------------------------------------------------------------------
# Fig. 1  The amplitude-only degeneracy: one curve, one ceiling.
# ----------------------------------------------------------------------
def fig_degeneracy(path):
    """
    The analytic curve of (3) with the measured pixels on it.

    The density is read from fig1_density.npz, a 240x240 histogram of
    (DOP_a, log10 CPR_a) over every pixel with non-zero amplitude in both
    channels (2 337 086), written by the block at the end of this file from
    the two sri rasters. Shipping the histogram rather than the rasters keeps
    the figure reproducible without 60 MB of ISRO data in the repository.
    """
    fig, ax = plt.subplots(figsize=(COL1, 2.35))
    dop = np.linspace(1e-4, 0.999, 4000)
    cpr = np.tanh(np.arctanh(dop) / 2) ** 2
    d_th, c_th = 0.13, 1.00
    ceiling = np.tanh(np.arctanh(d_th) / 2) ** 2

    # measured density, if present; drawn first so the curve sits on top
    try:
        z = np.load("fig1_density.npz")
        H, xe, ye = z["H"].astype(float), z["xe"], z["ye"]
        Hm = np.ma.masked_where(H <= 0, H)
        # the density IS the curve, so it is drawn as the visible trace (blue,
        # log-scaled) and the analytic line is laid over it thin and dashed
        pm = ax.pcolormesh(xe, 10 ** ye, Hm.T, cmap="Blues",
                           norm=mpl.colors.LogNorm(vmin=1, vmax=H.max()),
                           rasterized=True, zorder=2, shading="flat")
        n, nb = int(z["n"]), int(z["n_band"])
        ax.plot([], [], color=ACC1, lw=3, alpha=0.85,
                label=f"{n:,} measured pixels (density)")
        ax.text(0.98, 2.2e-4, f"{100*nb/n:.0f}% of pixels lie inside DOP < 0.13",
                fontsize=6.2, color=MUTED, ha="right", va="bottom")
    except FileNotFoundError:
        pass

    ax.plot(dop, cpr, color=INK, lw=0.7, ls="--", zorder=3,
            label=r"analytic curve $\tanh^2(\mathrm{artanh}\,\mathrm{DOP}_a/2)$")
    ax.axvspan(0, d_th, color=ACC2, alpha=0.07, zorder=0)
    ax.axvline(d_th, color=ACC2, lw=0.9, ls="--", zorder=2)
    ax.axhline(c_th, color=ACC1, lw=0.9, ls=":", zorder=2)
    ax.plot([d_th], [ceiling], marker="o", ms=4, mfc="white", mec=INK, mew=1.0, zorder=4)
    ax.annotate(r"ceiling $4.261\times10^{-3}$", xy=(d_th, ceiling), xytext=(0.22, 6e-3),
                fontsize=7, color=INK, arrowprops=dict(arrowstyle="-", lw=0.5, color=INK))
    ax.text(0.135, 1.35, r"threshold $\mathrm{CPR}>1$", fontsize=7, color=ACC1)
    ax.text(0.04, 1.2e-3, "DOP < 0.13", fontsize=7, color=ACC2, rotation=90, va="bottom", ha="center")

    ax.set_yscale("log")
    ax.set_xlim(0, 1.0)
    ax.set_ylim(1e-4, 5)
    ax.set_xlabel(r"$\mathrm{DOP}_a$")
    ax.set_ylabel(r"$\mathrm{CPR}_a$")
    ax.grid(True, which="major", ls="-", color=MUTED)
    ax.legend(loc="lower right", frameon=False, fontsize=6.2, bbox_to_anchor=(1.0, 0.13))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.savefig(path, dpi=600)
    plt.close(fig)


# ----------------------------------------------------------------------
# Fig. 2  ENL by multilooking scheme, each against its own ceiling.
# ----------------------------------------------------------------------
def fig_enl(path):
    labels = ["single look\n(control)",
              "21 looks,\nspatial avg.",
              "21 looks,\nsub-band",
              "delivered\nproduct"]
    measured = [1.04, 4.52, 9.95, 5.83]
    ceiling  = [1.00, 6.77, 21.00, 21.00]
    # spread: min-max over the nine SLC windows for the three SLC-derived
    # products (docs/slc_multilook_control.json); 95 % block-bootstrap
    # interval over 8 337 patches for the delivered product.
    lo = [0.93, 1.50, 4.03, 4.03]
    hi = [1.12, 5.75, 11.08, 6.19]

    fig, ax = plt.subplots(figsize=(COL1, 2.2))
    x = np.arange(len(labels))

    ax.vlines(x, 0, measured, color=MUTED, lw=0.7, zorder=1)
    ax.errorbar(x, measured, yerr=[np.subtract(measured, lo), np.subtract(hi, measured)],
                fmt="none", ecolor=ACC1, elinewidth=0.9, capsize=2.5, zorder=2)
    ax.plot(x, measured, ls="none", marker="o", ms=6, color=ACC1,
            mec="white", mew=0.8, zorder=3, label="measured ENL")
    ax.plot(x, ceiling, ls="none", marker="_", ms=13, mew=1.6,
            color=INK, zorder=3, label="reference value for that scheme")

    for xi, m in zip(x, measured):
        ax.annotate(f"{m:.2f}", (xi, m), textcoords="offset points",
                    xytext=(7, -1), fontsize=6.6, color=INK)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=6.6)
    ax.set_ylabel("equivalent number of looks")
    ax.set_ylim(0, 23)
    ax.grid(True, axis="y", ls="-", color=MUTED)
    ax.set_axisbelow(True)
    # legend above the axes so it never sits on the 21-look ceiling marks
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False,
              ncol=2, borderaxespad=0.2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.savefig(path)
    plt.close(fig)


# ----------------------------------------------------------------------
# Fig. 3  What the look count does to a threshold. Two panels, one axis each.
# ----------------------------------------------------------------------
def fig_detection(path):
    N = np.linspace(3.2, 60, 600)
    floor = Fdist.ppf(0.95, 2 * N, 2 * N)
    fp07 = (1 - Fdist.cdf(1.0 / 0.7, 2 * N, 2 * N)) * 100
    fp05 = (1 - Fdist.cdf(1.0 / 0.5, 2 * N, 2 * N)) * 100

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(COL1, 3.5), sharex=True)

    a1.plot(N, floor, color=INK, lw=1.3)
    a1.axhline(1.0, color=MUTED, lw=0.8, ls=":")
    a1.text(46, 1.05, "threshold 1.00", fontsize=6.6, color=MUTED)
    for n, lab, c in [(13.72, "13.72", ACC1), (21.0, "21", MUTED)]:
        a1.axvline(n, color=c, lw=0.8, ls="--")
        a1.plot([n], [Fdist.ppf(0.95, 2 * n, 2 * n)], marker="o", ms=4,
                mfc="white", mec=c, mew=1.1, zorder=4)
    a1.annotate("1.895", (13.72, 1.895), textcoords="offset points",
                xytext=(6, 5), fontsize=6.8, color=ACC1)
    a1.set_ylabel("one-sided 95% critical value")
    a1.set_ylim(1.0, 3.6)
    a1.grid(True, ls="-", color=MUTED)
    a1.set_axisbelow(True)

    a2.plot(N, fp07, color=INK, lw=1.3, ls="-", marker="None",
            label="true CPR $=0.7$")
    a2.plot(N[::35], fp07[::35], ls="none", marker="s", ms=3.2, color=INK)
    a2.plot(N, fp05, color=ACC2, lw=1.1, ls="--", label="true CPR $=0.5$")
    a2.plot(N[::35], fp05[::35], ls="none", marker="^", ms=3.4, color=ACC2)
    a2.axvline(13.72, color=ACC1, lw=0.8, ls="--")
    a2.plot([13.72], [17.79], marker="o", ms=4, mfc="white", mec=ACC1,
            mew=1.1, zorder=4)
    a2.annotate("17.79%", (13.72, 17.79), textcoords="offset points",
                xytext=(6, 4), fontsize=6.8, color=ACC1)
    a2.set_xlabel("equivalent number of looks $N$")
    a2.set_ylabel("noise exceedance $P(R>1)$ (%)")
    a2.set_xlim(3.2, 60)
    a2.set_ylim(0, 45)
    a2.grid(True, ls="-", color=MUTED)
    a2.set_axisbelow(True)
    a2.legend(loc="upper right", frameon=False)

    for ax in (a1, a2):
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.subplots_adjust(hspace=0.12)
    fig.savefig(path)
    plt.close(fig)


# ----------------------------------------------------------------------
# Fig. 4  External consistency check: two moments of published data, one answer.
#         (Not a validation: the inversion assumes a texture-free surface and
#         recovers a lower bound on N; see Sec. VI of the manuscript.)
# ----------------------------------------------------------------------
def fig_external(path):
    rows = [("Hermite B", 0.97, 0.50, 1.75),
            ("Rozhdestvenskiy N", 0.93, 0.50, 1.83),
            ("Main L", 0.92, 0.48, 1.82),
            ("Schomberger A", 0.99, 0.50, 1.77),
            ("Cardanus E", 0.83, 0.46, 2.19),
            ("Byrgius C", 1.12, 0.59, 1.88),
            ("Dollond E", 1.00, 0.53, 1.85),
            ("Stevinus A", 1.04, 0.56, 1.93)]
    names = [r[0] for r in rows]
    n_sd = [solve(relsd, r[2] / r[1], 2.001, 1e6) for r in rows]
    n_sk = [solve(skewF, r[3], 3.001, 1e6) for r in rows]

    fig, ax = plt.subplots(figsize=(COL1, 2.6))
    y = np.arange(len(rows))[::-1]

    ax.axvspan(8 - 0.001, 8 + 0.001, color=INK)  # documented value
    ax.axvline(8.0, color=INK, lw=1.1, ls="-")
    # No reference number inside the figure: numbering moves when the
    # bibliography changes (it already did once: raney2012 is [9] now, and
    # the old hard-coded "[10]" pointed at a different paper). The caption
    # carries the citation.
    ax.text(8.06, y.max() + 0.55, "8 looks, documented (Raney et al.)",
            fontsize=6.6, color=INK)

    for yi, a, b in zip(y, n_sd, n_sk):
        ax.plot([a, b], [yi, yi], color=MUTED, lw=0.7, zorder=1)
    ax.plot(n_sd, y, ls="none", marker="o", ms=4.6, color=ACC1,
            mec="white", mew=0.7, label=r"from $\sigma$", zorder=3)
    ax.plot(n_sk, y, ls="none", marker="^", ms=4.8, color=ACC2,
            mec="white", mew=0.7, label=r"from skewness", zorder=3)

    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=6.6)
    ax.set_xlabel("inferred equivalent number of looks")
    ax.set_xlim(6.5, 10.5)
    ax.grid(True, axis="x", ls="-", color=MUTED)
    ax.set_axisbelow(True)
    ax.legend(loc="lower left", frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.savefig(path)
    plt.close(fig)


if __name__ == "__main__":
    fig_degeneracy("fig1_degeneracy.pdf")
    fig_enl("fig2_enl.pdf")
    fig_detection("fig3_detection.pdf")
    fig_external("fig4_external.pdf")
    print("wrote fig1..fig4")


# ----------------------------------------------------------------------
# Build fig1_density.npz from the two sri rasters. Needs the ISRO data on
# disk; run once, commit the (small) .npz, never the rasters.
# ----------------------------------------------------------------------
def build_fig1_density(lh_tif, lv_tif, out="fig1_density.npz",
                       g_lh=1.018442, g_lv=1.000923):
    import tifffile
    lh = tifffile.imread(lh_tif).astype(np.float64)
    lv = tifffile.imread(lv_tif).astype(np.float64)
    m = (lh > 0) & (lv > 0)
    ih, iv = (lh[m] / g_lh) ** 2, (lv[m] / g_lv) ** 2   # K and sin(theta) cancel in every ratio
    sh, sv = np.sqrt(ih), np.sqrt(iv)
    cpr = ((sh - sv) / (sh + sv)) ** 2
    dop = np.abs(ih - iv) / (ih + iv)
    xe, ye = np.linspace(0, 1, 241), np.linspace(-6, 0.7, 241)
    lc = np.clip(np.log10(np.clip(cpr, 1e-12, None)), -6 + 1e-9, 0.7 - 1e-9)  # floor bin keeps CPR < 1e-6
    H, _, _ = np.histogram2d(np.clip(dop, 0, 1 - 1e-9), lc, bins=[xe, ye])
    np.savez_compressed(out, H=H.astype(np.int32), xe=xe, ye=ye, n=int(m.sum()),
                        n_band=int((dop < 0.13).sum()), max_cpr_in_band=float(cpr[dop < 0.13].max()))
