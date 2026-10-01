"""
make_fig_spec_curve.py -- fig_spec_curve.pdf (v21 work order, W2B).

The specification curve of the shadowed-versus-sunlit odds ratio: every subset of
ten covariates {ln N-hat, coherence, min SNR, spatial trend, slant-range sample,
incidence, LOLA local incidence, slope, roughness, PSR fraction}, class and pass
always in (docs/shadow_identification.json::B_spec_curve). Top: the odds ratio of
each specification, sorted, with its 95 % block-bootstrap interval (B = 500),
specifications that include coherence in orange and the others in blue; the
horizontal line is 1. Bottom: which covariates the specification contains.
Left L-band, two passes (1888 discs); right S-band pass 1 (1300 discs).

Style as make_fig_n_sensitivity.py: STIX, fonttype 42, every text at least 7 pt at
the printed width (7.0 in, double column), no mathtext sub- or superscripts.
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
    "axes.linewidth": 0.6, "lines.linewidth": 1.0,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
INK, ACC1, ACC2, MUTED = "#1b1b1b", "#1f5fa9", "#c4561f", "#6b6b6b"
HERE = Path(__file__).resolve().parent
DOCS = HERE.parent / "docs"
LABELS = ["ln N-hat", "coherence", "min SNR", "position", "slant range", "incidence", "local incidence", "slope", "roughness",
          "PSR fraction"]
SETS = (("L_two_passes", "L-band, two passes"), ("S_pass1", "S-band, pass 1"))


def main(out="fig_spec_curve.pdf"):
    d = json.loads((DOCS / "shadow_identification.json").read_text(encoding="utf-8"))["B_spec_curve"]
    fig = plt.figure(figsize=(7.0, 4.1))
    gs = fig.add_gridspec(2, 2, height_ratios=[2.2, 1.6], hspace=0.06, wspace=0.42)
    for j, (key, title) in enumerate(SETS):
        rows = [r for r in d[key]["specifications"] if r.get("or_ci95_block_bootstrap")]
        rows.sort(key=lambda r: r["odds_ratio"])
        x = np.arange(len(rows))
        lo = np.array([r["or_ci95_block_bootstrap"][0] for r in rows]); hi = np.array([r["or_ci95_block_bootstrap"][1] for r in rows])
        orr = np.array([r["odds_ratio"] for r in rows]); coh = np.array([r["has_coherence"] for r in rows])
        a = fig.add_subplot(gs[0, j])
        a.vlines(x[~coh], lo[~coh], hi[~coh], color=ACC1, lw=0.35, alpha=0.35)
        a.vlines(x[coh], lo[coh], hi[coh], color=ACC2, lw=0.35, alpha=0.35)
        a.plot(x[~coh], orr[~coh], ".", color=ACC1, ms=1.6, label="without coherence")
        a.plot(x[coh], orr[coh], ".", color=ACC2, ms=1.6, label="with coherence")
        a.axhline(1.0, color=INK, lw=0.6)
        a.set_yscale("log"); a.set_xlim(-1, len(rows))
        t = [0.1, 0.2, 0.5, 1, 2, 5, 10]
        a.yaxis.set_major_locator(FixedLocator(t)); a.yaxis.set_major_formatter(FixedFormatter([str(v) for v in t]))
        a.yaxis.set_minor_locator(NullLocator()); a.yaxis.set_minor_formatter(NullFormatter())
        a.set_xticks([])
        a.set_ylabel("shadowed / sunlit odds ratio")
        a.set_title(f"{title}, {len(rows)} specifications", loc="left", fontsize=7.5)
        if j == 0:
            a.legend(loc="upper left", frameon=False, markerscale=3, borderaxespad=0.2)
        m = fig.add_subplot(gs[1, j], sharex=a)
        M = np.array([r["mask"] for r in rows]).T
        m.imshow(M, aspect="auto", cmap="Greys", interpolation="nearest", vmin=0, vmax=1.4, extent=(-1, len(rows), len(LABELS) - 0.5, -0.5))
        m.set_yticks(range(len(LABELS))); m.set_yticklabels(LABELS)
        m.set_xlabel("specifications, sorted by odds ratio")
        for sp in ("top", "right"):
            m.spines[sp].set_visible(False)
    fig.savefig(HERE / out)
    print("  wrote", out)


if __name__ == "__main__":
    main()
