# paper/

Figure sources and figure files for the TGRS manuscript and its Supplementary Material. The
manuscript and supplement `.tex` are not tracked here until the submission is tagged; gate G32
reads the authors' copy (see README, *Reproducing*).

## Figures in the submitted manuscript

| Paper | File | Generator | Input |
|---|---|---|---|
| Fig. 1(a) | `fig_scene.pdf` | `make_fig_scene.py` | `data/derived/fig_scene/fig_scene_cache.npz` (needs the scene; written by `backend/scripts/f2_complex_product.py`) |
| Fig. 1(b) | `fig_cpr_dop.pdf` | `make_figures_v12.py` | `fig_cpr_dop_density.npz` (tracked; written by `backend/scripts/stokes_from_slc.py`) |
| Fig. 2(a) | `fig_joint_power.pdf` | `make_figures_v12.py` | `docs/joint_power_curve.json`, `docs/np_power_bound.json` |
| Fig. 2(b) | `fig_region_design.pdf` | `make_fig_region.py` | `docs/region_design_curve.json` |
| Supp. Fig. S1 | `fig1_degeneracy.pdf` | `make_figures.py` | `fig1_density.npz` (tracked; written by `backend/scripts/dop_exclusion.py`) |
| Supp. Fig. S2 | `fig_n_sensitivity.pdf` | `make_fig_n_sensitivity.py` | `docs/n_sensitivity.json` (assembled by `backend/scripts/n_sensitivity_assemble.py`) |
| Supp. Fig. S3 | `fig_spec_curve.pdf` | `make_fig_spec_curve.py` | `docs/shadow_identification.json::B_spec_curve` |

Run from this directory with the environment in `../requirements-analysis.txt`:

```
python make_figures.py && python make_figures_v12.py && python make_fig_region.py
python make_fig_n_sensitivity.py && python make_fig_spec_curve.py
python make_fig_scene.py          # only with the scene cache present
python assert_figures_embed_fonts.py   # gate G26: fonts embedded, no Type 3
```

The tracked PDFs are content-stream-identical to the authors' 4 Oct 2026 manuscript build
(`docs/REPRODUCIBILITY.md` §17); a rebuild differs only in PDF metadata.

## Not used by the submitted manuscript

`fig2_enl.pdf`, `fig3_detection.pdf` and `fig4_external.pdf` are still built by `make_figures.py`
but were removed from the paper in earlier revisions (`docs/REPRODUCIBILITY.md` §17 says when and
why). `make_figures_v12_v21.py` and `make_fig_region_v21.py` are the v21 versions of two generators,
kept so the V21 figure comparison (`docs/figure_compare_v21.json`) can be re-run; the current
generators are the files without the suffix.

## Checks

`check_submission.py` runs the submission-format checks on a manuscript `.tex` (abstract length,
index-term order, every `\cite` and `\ref` defined, AI-use disclosure present) and writes
`submission_check.json` to the working directory (gitignored).
