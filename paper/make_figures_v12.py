"""
make_figures_v12.py -- Figs. 2 and 3 of manuscript v12.

  fig_cpr_dop.pdf     2-D log density of sample (DOP, CPR) over every matched
                      cell of the complex product (fig_cpr_dop_density.npz,
                      written by backend/scripts/stokes_from_slc.py), with the
                      coupling curve, DOP = 0.13, CPR = 1, the band edge 1.2989
                      and the one-sided 95 % F(2N,2N) critical values at the
                      complex product's
                      log-ratio look count (39.4, docs/enl_logratio.json), with an
                      inset on DOP 0-0.2, R 0.7-1.5 and the band 1 < R < 1.2989 shaded.
  fig_joint_power.pdf the joint rule's size and largest in-band selection rate
                      against look count (docs/joint_power_curve.json); the
                      correlated-looks arm is plotted at its effective look
                      count (arms.C.look_correlation.*.effective_looks); a thin
                      curve, the Neyman-Pearson upper bound on the power of any
                      level-5 % per-cell test (docs/np_power_bound.json).

Style as make_figures.py: STIX, fonttype 42 (no Type 3), single column.
"""
import json
from pathlib import Path
import numpy as np
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from scipy import stats

mpl.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.family": "serif", "font.serif": ["STIXGeneral"],
    "mathtext.fontset": "stix", "font.size": 8, "axes.labelsize": 8,
    "legend.fontsize": 6.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.linewidth": 0.6, "lines.linewidth": 1.1,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
INK, ACC1, ACC2, MUTED = "#1b1b1b", "#1f5fa9", "#a3431f", "#6b6b6b"
COL1 = 3.5
HERE = Path(__file__).resolve().parent
#: the repository's docs/, resolved from this file. The copy made outside the
#: repository read a hard-coded /mnt/user-data/... path; replaced 2026-09-23.
DOCS = HERE.parent / "docs"
EDGE = 1.13 / 0.87


def crit(n):
    return stats.f.ppf(0.95, 2 * n, 2 * n)


def fig_cpr_dop(npz, out="fig_cpr_dop.pdf", n_ratio=39.436):
    z = np.load(npz)
    H, xe, ye = z["H"], z["xe"], z["ye"]
    fig, ax = plt.subplots(figsize=(COL1, 2.35))
    Hm = np.ma.masked_where(H.T <= 0, H.T)
    norm = LogNorm(vmin=1, vmax=H.max())
    pc = ax.pcolormesh(xe, 10 ** ye, Hm, cmap="Blues", norm=norm, shading="flat", rasterized=True)
    c = np.logspace(-3, 1.5, 800)
    ax.plot(np.abs(1 - c) / (1 + c), c, color=INK, lw=0.9)
    ax.axvline(0.13, color=ACC2, lw=0.8, ls="--")
    ax.axhline(1.0, color=MUTED, lw=0.7, ls=":", label="CPR = 1")
    ax.axhline(EDGE, color=ACC2, lw=0.8, ls="-.", label="band edge 1.2989")
    c2 = crit(n_ratio)
    ax.axhline(c2, color=ACC1, lw=0.8, ls="--", label=f"crit. {c2:.3f}, $N={n_ratio:.1f}$")
    ax.plot([], [], color=INK, lw=0.9, label=r"$\mathrm{DOP}=|1-\mathrm{CPR}|/(1+\mathrm{CPR})$")
    ax.text(0.145, 3.2, "DOP = 0.13", color=ACC2, fontsize=6.2, rotation=90, va="bottom")
    ax.legend(loc="upper left", bbox_to_anchor=(0.2, 1.0), frameon=True, framealpha=1.0,
              facecolor="white", edgecolor="none", fontsize=5.9)
    ax.set_yscale("log")
    ax.set_xlim(0, 1)
    ax.set_ylim(10 ** ye[0], 10 ** ye[-1])
    ax.set_xlabel(r"sample DOP $\hat m$")
    ax.set_ylabel(r"sample CPR $R$")
    # inset: the joint criterion's corner, DOP 0-0.2 and R 0.7-1.5, the band shaded
    ia = ax.inset_axes([0.075, 0.075, 0.40, 0.42])
    ia.pcolormesh(xe, 10 ** ye, Hm, cmap="Blues", norm=norm, shading="flat", rasterized=True)
    ia.axhspan(1.0, EDGE, color=ACC2, alpha=0.18, lw=0)
    ia.plot(np.abs(1 - c) / (1 + c), c, color=INK, lw=0.8)
    ia.axvline(0.13, color=ACC2, lw=0.7, ls="--")
    ia.axhline(1.0, color=MUTED, lw=0.6, ls=":")
    ia.axhline(EDGE, color=ACC2, lw=0.7, ls="-.")
    ia.axhline(c2, color=ACC1, lw=0.7, ls="--")
    ia.set_xlim(0, 0.2)
    ia.set_ylim(0.7, 1.5)
    ia.set_xticks([0, 0.1, 0.2])
    ia.set_yticks([0.8, 1.0, 1.2, 1.4])
    ia.tick_params(labelsize=5.8, length=2, pad=1)
    for sp in ia.spines.values():
        sp.set_linewidth(0.5)
    ia.text(0.004, 1.02, "band", fontsize=5.8, color=ACC2, va="bottom")
    cb = fig.colorbar(pc, ax=ax, pad=0.02, fraction=0.05)
    cb.set_label("cells per bin", fontsize=7)
    cb.ax.tick_params(labelsize=6.2)
    fig.savefig(out, dpi=600)
    plt.close(fig)
    return int(z["n"]), c2, c2


def fig_joint_power(js, out="fig_joint_power.pdf"):
    d = json.loads(Path(js).read_text(encoding="utf-8"))
    eff = d["arms"]["C"]["look_correlation"]
    fig, ax = plt.subplots(figsize=(COL1, 2.2))
    styles = {"A": (ACC1, "speckle"), "B": (ACC2, "texture, shape 8"),
              "C": (MUTED, "correlated looks, at effective $N$")}
    for arm, (col, lab) in styles.items():
        rows = d["summary"][arm]["by_N"]
        n = np.array([r["N"] for r in rows], float)
        if arm == "C":
            n = np.array([eff[str(r["N"])]["effective_looks"] for r in rows])
        strict = [[b["power_percent"] for b in r["band"]
                   if "DOP 0.13" not in b["population"] and "1.299" not in b["population"]]
                  for r in rows]
        ax.plot(n, [r["size_percent"] for r in rows], color=col, lw=1.1, label=lab)
        ax.plot(n, [max(v) for v in strict], color=col, lw=0.8, ls="--")
        if arm == "A":
            ax.plot(n, [min(v) for v in strict], color=col, lw=0.7, ls=":", marker="o", ms=1.8,
                    mfc="white", mew=0.5)
    nb = DOCS / "np_power_bound.json"
    if nb.is_file():
        # the Neyman-Pearson bound: no level-5 % per-cell test of the criterion
        # has higher power anywhere on the band grid (np_power_bound.py)
        cv = sorted(json.loads(nb.read_text(encoding="utf-8"))["curve"], key=lambda c: c["N"])
        ax.plot([c["N"] for c in cv], [c["bound_percent"] for c in cv], color=INK, lw=0.5,
                label="upper bound, any level-5 % test")
    ax.plot([], [], color=INK, lw=1.1, label="size (CPR 1.00): solid")
    ax.plot([], [], color=INK, lw=0.8, ls="--", label="in-band max: dashed")
    ax.plot([], [], color=INK, lw=0.7, ls=":", marker="o", ms=1.8, mfc="white", mew=0.5,
            label="in-band min: dotted, markers")
    # the 5 % reference: a dash-dot-dot line no curve uses
    ax.axhline(5.0, color=MUTED, lw=0.6, ls=(0, (5, 1.5, 1, 1.5, 1, 1.5)))
    for x, lab in ((39.4, "39.4"), (79.6166, "79.6")):
        ax.axvline(x, color=INK, lw=0.5, ls="-.")
        ax.text(x, 1.01, lab, fontsize=6.0, color=INK, ha="center", va="bottom",
                transform=mpl.transforms.blended_transform_factory(ax.transData, ax.transAxes))
    ax.axvspan(218, 254, color=MUTED, alpha=0.25, lw=0)
    ax.text(236, 1.01, "IUT", fontsize=6.0, color=INK, ha="center", va="bottom",
            transform=mpl.transforms.blended_transform_factory(ax.transData, ax.transAxes))
    ax.text(120, 4.6, "5 %", fontsize=6.2, color=INK, va="top")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1.4, 300)
    ax.set_ylim(0.04, 100)
    ax.set_xlabel(r"look count $N$")
    ax.set_ylabel(r"$P(\hat m<0.13\ \wedge\ R>1)$ (%)")
    ax.legend(loc="lower right", bbox_to_anchor=(0.93, 0.0), frameon=True, framealpha=1.0, edgecolor="none", fontsize=5.8)
    fig.savefig(out)
    plt.close(fig)


if __name__ == "__main__":
    n, c1, c2 = fig_cpr_dop("fig_cpr_dop_density.npz")
    fig_joint_power(DOCS / "joint_power_curve.json")
    print(n, round(c1, 4), round(c2, 4))
