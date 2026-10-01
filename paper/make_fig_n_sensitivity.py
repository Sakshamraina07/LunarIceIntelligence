"""
make_fig_n_sensitivity.py -- fig_n_sensitivity.pdf (v21 work order, W1H).

  left   the Neyman-Pearson power bound (any level-5 % test, one cell) and the
         published rule's size and its power at CPR 1.1, minimum DOP, against the
         look count N, with markers at 14, 21, 39.4, 69.7 and 79.6
         (docs/n_sensitivity.json rows; bands: 2 Monte Carlo SE);
  right  the region-mean null, the unconditional probability that a region of
         260 or 3647 cells has a mean sample DOP below 0.13 over its pixels of
         sample CPR >= 1 (ice-free terrain at CPR 0.7, DOP 0.176), correlated
         cells, against the achieved log-ratio look count, with 2 SE bands
         (docs/n_sensitivity_region.json via n_sensitivity.json).

Style as make_figures_v12.py (STIX, fonttype 42, no Type 3) but every text is at
least 7 pt at the printed size: the figure is drawn at its printed width of 7.0 in
(double column), no mathtext sub- or superscripts (they render at 70 %), legend
7 pt. Double-column figure: 7.0 in wide.
"""
import json
from pathlib import Path

import numpy as np
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedFormatter, FixedLocator, NullFormatter, NullLocator

mpl.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.family": "serif", "font.serif": ["STIXGeneral"],
    "mathtext.fontset": "stix", "font.size": 7.5, "axes.labelsize": 7.5,
    "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.linewidth": 0.6, "lines.linewidth": 1.1,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
INK, ACC1, ACC2, ACC3, MUTED = "#1b1b1b", "#1f5fa9", "#a3431f", "#2f7d4f", "#6b6b6b"
HERE = Path(__file__).resolve().parent
DOCS = HERE.parent / "docs"
MARKS = ((14.0, "14"), (21.0, "21"), (39.4, "39.4"), (69.7, "69.7"), (79.6, "79.6"))


def logticks(ax):
    """Log x axis with plain-text tick labels (the default 10^k labels are mathtext superscripts, drawn at 70 % size)."""
    ax.set_xscale("log"); ax.set_xlim(5, 220)
    t = [5, 10, 20, 50, 100, 200]
    ax.xaxis.set_major_locator(FixedLocator(t)); ax.xaxis.set_major_formatter(FixedFormatter([str(v) for v in t]))
    ax.xaxis.set_minor_locator(NullLocator()); ax.xaxis.set_minor_formatter(NullFormatter())


def main(out="fig_n_sensitivity.pdf"):
    d = json.loads((DOCS / "n_sensitivity.json").read_text(encoding="utf-8"))
    rows = d["rows"]
    N = np.array([r["N"] for r in rows])
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.75))
    # ---- left
    npb = np.array([np.nan if r.get("np_bound_percent") is None else r["np_bound_percent"] for r in rows])
    sz = np.array([r["rule_size_percent"] for r in rows]); se = np.array([r["rule_size_mc_se_percent"] for r in rows])
    pw = np.array([r["rule_power_cpr1p1_min_dop_percent"] for r in rows])
    a.plot(N, npb, "-o", color=INK, ms=2.2, label="power bound, any level-5 % test")
    a.fill_between(N, sz - 2 * se, sz + 2 * se, color=ACC1, alpha=0.25, lw=0)
    a.plot(N, sz, "-", color=ACC1, label="size of the published rule")
    a.plot(N, pw, "--", color=ACC2, label="its power, CPR 1.1 at minimum DOP")
    a.axhline(5.0, color=MUTED, lw=0.5, ls=":")
    for x, t in MARKS:
        a.axvline(x, color=MUTED, lw=0.5, ls=":")
        a.text(x * 1.02, 98, t, rotation=90, va="top", ha="left", fontsize=7, color=MUTED)
    logticks(a); a.set_ylim(0, 100)
    a.set_xlabel("look count N"); a.set_ylabel("per cent")
    a.legend(loc="center left", frameon=False, borderaxespad=0.2, bbox_to_anchor=(0.02, 0.62))
    a.set_title("(a) one cell", loc="left", fontsize=7.5)
    # ---- right
    cols = {260: ACC1, 3647: ACC3}
    for sz_, c in cols.items():
        pts = sorted({(r[f"region_null_{sz_}_cells_correlated"]["achieved_log_ratio_N"],
                       r[f"region_null_{sz_}_cells_correlated"]["unconditional_percent"],
                       r[f"region_null_{sz_}_cells_correlated"]["unconditional_mc_se_percent"])
                      for r in rows if f"region_null_{sz_}_cells_correlated" in r})
        x, y, s = (np.array(v) for v in zip(*pts))
        b.fill_between(x, y - 2 * s, y + 2 * s, color=c, alpha=0.25, lw=0)
        b.plot(x, y, "-o", color=c, ms=2.2, label=f"{sz_} cells, correlated")
    p = sorted({(r["region_null_260_cells_independent"]["unconditional_percent"], r["N"]) for r in rows if "region_null_260_cells_independent" in r}, key=lambda t: t[1])
    b.plot([t[1] for t in p], [t[0] for t in p], ":", color=INK, lw=0.9, label="260 cells, independent cells (N as set)")
    b.axhline(5.0, color=MUTED, lw=0.5, ls=":")
    for x, t in MARKS[:3]:
        b.axvline(x, color=MUTED, lw=0.5, ls=":")
    logticks(b); b.set_ylim(0, 100)
    b.set_xlabel("look count N (achieved, log-ratio)"); b.set_ylabel("regions with mean DOP < 0.13, per cent")
    b.legend(loc="upper left", frameon=False, borderaxespad=0.2)
    b.set_title("(b) ice-free region, CPR 0.7, DOP 0.176", loc="left", fontsize=7.5)
    fig.tight_layout(pad=0.4, w_pad=1.0)
    fig.savefig(HERE / out)
    print("  wrote", out)


if __name__ == "__main__":
    main()
