"""
make_fig_region.py -- regional design curve (Fig. 4 of v19).

Power of the regional intersection-union test (IUT; conditioned estimate)
and the Neyman-Pearson bound on any level-5 % test of the criterion's null,
against the pooled look count N_eff, for true CPR 1.05, 1.1, 1.2 and 1.25 at
their minimum admissible DOP. Reads docs/region_design_curve.json
(keys N_eff_grid, iut_power, np_bound_percent, translation). Marks F2 on this
pass (262 looks) and a fully imaged F2 (about 900-1400 looks).
Style as make_figures_v12.py: STIX, fonttype 42, single column.
"""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt

mpl.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.family": "serif", "font.serif": ["STIXGeneral"],
    "mathtext.fontset": "stix", "font.size": 8, "axes.labelsize": 8,
    "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.linewidth": 0.6, "lines.linewidth": 1.1,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
HERE = Path(__file__).resolve().parent
DOCS = HERE.parent / "docs"


def val(x):
    return x["conditioned"]["percent"] if "conditioned" in x else x["percent"]


def main(js, out="fig_region_design.pdf"):
    d = json.loads(Path(js).read_text(encoding="utf-8"))
    n = np.array(d["N_eff_grid"], float)
    cols = {"CPR 1.05 DOP min": "#6b6b6b", "CPR 1.1 DOP min": "#1f5fa9",
            "CPR 1.2 DOP min": "#a3431f", "CPR 1.25 DOP min": "#2e7d32"}
    fig, ax = plt.subplots(figsize=(3.44, 2.1))
    for key, c in cols.items():
        lab = "CPR " + key.split()[1]
        ax.plot(n, [val(x) for x in d["iut_power"][key]], color=c, lw=1.1, label=lab)
        ax.plot(n, d["np_bound_percent"][key], color=c, lw=0.8, ls="--")
    ax.plot([], [], color="#1b1b1b", lw=1.1, label="IUT")
    ax.plot([], [], color="#1b1b1b", lw=0.8, ls="--", label="bound, any level-5 % test")
    ax.axhline(80, color="#1b1b1b", lw=0.5, ls=(0, (1, 1)))
    f2 = d["translation"]["crater_F2"]["complex_product"]["N_eff_at_39p4"]
    ax.axvline(f2, color="#1b1b1b", lw=0.6, ls="-.")
    ax.text(f2 * 1.06, 55, "F2, this pass", fontsize=7, rotation=90, va="bottom")
    ax.axvspan(900, 1400, color="#6b6b6b", alpha=0.18, lw=0)
    ax.text(1120, 2, "F2, full", fontsize=7, rotation=90, va="bottom", ha="center")
    ax.set_xscale("log")
    ax.set_xlim(200, 10000)
    ax.set_ylim(0, 100)
    ax.set_xlabel(r"pooled look count $N_{\mathrm{eff}}$")
    ax.set_ylabel("power at minimum DOP (%)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), frameon=False, ncol=3, handlelength=1.8, columnspacing=1.0)
    fig.savefig(out)
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DOCS / "region_design_curve.json")
