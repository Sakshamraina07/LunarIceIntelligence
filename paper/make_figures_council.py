"""
make_figures_council.py -- the two figures of the council work order (Task 7).

    cd paper && python make_figures_council.py

  fig_cpr_dop.pdf      2-D log density of the sample (DOP, CPR) over every
                       matched cell of the complex product, with the coupling
                       curve DOP = |1 - CPR|/(1 + CPR), DOP = 0.13, CPR = 1,
                       CPR = 1.2989 and CPR = 1.895
                       (reads fig_cpr_dop_density.npz, written by
                       backend/scripts/stokes_from_slc.py)
  fig_joint_power.pdf  the joint rule's size and in-band power against N, three
                       arms (reads ../docs/joint_power_curve.json, written by
                       backend/scripts/dop_sampling_bias.py --curve)

Kept apart from make_figures.py, which is byte-identical to the copy the
manuscript is built from. Same style block: STIX, fonttype 42 (no Type 3),
single-column width. Writes into the working directory, as make_figures.py does.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

mpl.rcParams.update({
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

INK = "#1b1b1b"
ACC1 = "#1f5fa9"
ACC2 = "#a3431f"
MUTED = "#6b6b6b"
COL1 = 3.5
HERE = Path.cwd()
DOCS = Path(__file__).resolve().parents[1] / "docs"
EDGE = (1 + 0.13) / (1 - 0.13)


def fig_cpr_dop(path="fig_cpr_dop.pdf"):
    z = np.load(HERE / "fig_cpr_dop_density.npz")
    H, xe, ye = z["H"], z["xe"], z["ye"]
    fig, ax = plt.subplots(figsize=(COL1, 2.7))
    Hm = np.ma.masked_where(H.T <= 0, H.T)
    pc = ax.pcolormesh(xe, 10 ** ye, Hm, cmap="Blues", norm=LogNorm(vmin=1, vmax=H.max()),
                       shading="flat", rasterized=True)
    c = np.logspace(-3, 1.5, 800)
    ax.plot(np.abs(1 - c) / (1 + c), c, color=INK, lw=0.9,
            label=r"$\mathrm{DOP}=|1-\mathrm{CPR}|/(1+\mathrm{CPR})$")
    ax.axvline(0.13, color=ACC2, lw=0.8, ls="--")
    ax.axhline(1.0, color=MUTED, lw=0.7, ls=":")
    ax.axhline(EDGE, color=ACC2, lw=0.8, ls="-.")
    ax.axhline(1.895, color=ACC1, lw=0.8, ls="--")
    ax.text(0.14, 2.3e-3, "DOP = 0.13", color=ACC2, fontsize=6.4, rotation=90, va="bottom")
    ax.text(0.985, 0.95, "CPR = 1", color=MUTED, fontsize=6.4, ha="right", va="top")
    ax.text(0.70, EDGE * 0.97, "1.2989", color=ACC2, fontsize=6.4, ha="right", va="top")
    ax.text(0.985, 1.895 * 1.05, "1.895 (crit., $N=13.72$)", color=ACC1, fontsize=6.4,
            ha="right", va="bottom")
    ax.set_yscale("log")
    ax.set_xlim(0, 1)
    ax.set_ylim(10 ** ye[0], 10 ** ye[-1])
    ax.set_xlabel(r"sample DOP $\hat m$")
    ax.set_ylabel(r"sample CPR $R$")
    ax.legend(loc="lower right", frameon=False, fontsize=6.2)
    cb = fig.colorbar(pc, ax=ax, pad=0.02, fraction=0.05)
    cb.set_label("cells per bin", fontsize=7)
    cb.ax.tick_params(labelsize=6.4)
    fig.savefig(HERE / path, dpi=600)
    plt.close(fig)
    return int(z["n"])


def fig_joint_power(path="fig_joint_power.pdf"):
    d = json.loads((DOCS / "joint_power_curve.json").read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(COL1, 2.4))
    styles = {"A": (ACC1, "speckle"), "B": (ACC2, "texture, shape 8"),
              "C": (MUTED, "correlated looks")}
    for arm, (col, lab) in styles.items():
        rows = d["summary"][arm]["by_N"]
        n = np.array([r["N"] for r in rows])
        ax.plot(n, [r["size_percent"] for r in rows], color=col, lw=1.1, label=lab)
        ax.plot(n, [r["power_max_percent"] for r in rows], color=col, lw=0.9, ls="--")
    ax.plot([], [], color=INK, lw=1.1, label="solid: size")
    ax.plot([], [], color=INK, lw=0.9, ls="--", label="dashed: max in-band power")
    ax.axhline(5.0, color=INK, lw=0.6, ls=":")
    ax.axvline(79.6166, color=INK, lw=0.6, ls="-.")
    ax.text(83, 22.0, r"$N\approx80$", fontsize=6.4, color=INK, va="top")
    ax.text(5.3, 5.4, "5 %", fontsize=6.4, color=INK)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"look count $N$")
    ax.set_ylabel(r"$P(\hat m<0.13\ \wedge\ R>1)$ (%)")
    ax.set_xlim(5, 200)
    ax.legend(loc="lower right", frameon=False, fontsize=5.6, ncol=1,
              bbox_to_anchor=(1.0, 0.07))
    fig.savefig(HERE / path)
    plt.close(fig)


def media_box(pdf: Path):
    m = re.search(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", pdf.read_bytes())
    return float(m.group(3)) - float(m.group(1)), float(m.group(4)) - float(m.group(2))


if __name__ == "__main__":
    n = fig_cpr_dop()
    fig_joint_power()
    for f in ("fig_cpr_dop.pdf", "fig_joint_power.pdf"):
        w, h = media_box(HERE / f)
        print(f"{f}: {w:.1f} x {h:.1f} pt; at \\columnwidth (252 pt) the height is "
              f"{h * 252 / w:.1f} pt = {h * 252 / w / 72:.2f} in")
    print(f"fig_cpr_dop.pdf density over {n:,} cells")
