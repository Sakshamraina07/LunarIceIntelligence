# Second-scene runbook (v21 work order, W4.2)

Status: **prepared, nothing downloaded.** No file is fetched by anything in this
document; every download below needs the author's explicit yes in chat.

## 0. What is already on disk, and what the chain has been run on

`data/` holds (sizes from disk, 2026-10-01):

| scene | product | where | chain status |
|---|---|---|---|
| 2020-08-08 20:11:54 | L-band SLI + SRI + GRI, S-band SLI + SRI + GRI (`ncxl_…`, `ncxs_…`) | `data/pradan/raw/` | L: everything (pass 1); S: everything since v20 (`20200808S`) |
| 2020-03-05 11:49:02 | L-band (`ncxl_…t114902885`) and S-band (`ncxs_…t114902885`) SLI + SRI + GRI | `data/generality/20200305/` | L: everything (pass 2). **S: stokes_from_slc, discs and frame statistics run in the v21 pass** (`docs/stokes_from_slc_20200305S*.json`, `docs/disc_table_v21.json::discs.S_20200305S`); same acquisition as L pass 2, so **not an independent replication** |
| 2020-03-05 15:45:39 | `ch2_sar_ncls_20200305t154539649_d_cp_d18.zip` | `data/generality/20200305/` | **0 bytes** — an interrupted download; contains nothing; not usable |
| 2025-11-06 22:10:14 | `ch2_sar_nrxl_20251106t221014810` (L0B **raw** `.dat`, 2.4 GB, plus label) | `data/generality/20251106/` | **not chain-compatible** (raw level 0, no focused SLC, no label gains); inspected and rejected as not comparable (`docs/REPRODUCIBILITY.md`, S-VI) |

Conclusion: no compact-pol product on disk is both unprocessed and independent.
The only complex compact-pol L/S products are the two acquisitions already used.
A second scene therefore has to come from PRADAN.

## 1. What to search for on PRADAN (Chandrayaan-2 → SAR)

The filter names below are the ones the file names on disk imply; the portal's
exact menu labels are for the author to confirm when logged in (this was not
browsed).

* Instrument: DFSAR (SAR), L-band **and** S-band.
* Mode: **circular transmit, compact (hybrid) polarimetry** — the `cp` in
  `…_cp_…` (not full-pol `fp`, not the L0B raw `r0b`).
* Level: calibrated / **Level 2**, both the `sli` (single-look complex) **and**
  `sri` (ortho-rectified amplitude) and the `gri` / geometry files. The
  criterion cannot be evaluated without the SLC (`sli`, both channels `lh`, `lv`).
* Region: south polar, Faustini (87.3° S, 77° E) and Shackleton; the frame must
  cover F2 (`docs/f2_footprint.json`: lat −87.29, lon 82.31) if F2 is to be
  re-tested, and must put PSR and sunlit terrain in the frame for the disc
  analysis.
* Date: any acquisition **other than 2020-08-08 and 2020-03-05**; to be
  independent of pass 1 it should differ in date **and** in viewing geometry
  (look direction / incidence), because geometry was the adjustment variable that
  moved the shadow odds ratio. Prefer the L-band full swath over the south pole.
* File to get per scene (names follow the ones on disk):
  `ch2_sar_ncxl_<yyyymmdd>t<hhmmssmmm>_d_sli_xx_cp_{lh,lv}_d18.tif` (≈2.1 GB each
  at pass-1 size), `…_d_sri_xx_cp_{lh,lv}_d18.tif`, `…_d_sri_ma_cp_xx_d18.tif`,
  `…_d_sri_in_cp_xx_d18.tif`, the `…_d_*_xx_cp_xx_d18.xml` labels, and
  `ch2_sar_ncxl_<…>_g_{sli,sri,gri}_xx_cp_xx_d18.csv` + `_g_xxx_xx_cp_xx_d18.xml`
  geometry. Expect ≈4.5–5 GB per band for a full-swath pass (pass 1: 2.07 GB × 2
  SLI + ≈0.15 GB of the rest). Or the bundle `ch2_sar_ncls_<…>_d_cp_d18.zip`
  (≈1 GB on disk for 2020-03-05; ≈6 GB expected for a full swath).
* Place **without staging** under `data/generality/<yyyymmdd>/` exactly as
  2020-03-05 is laid out (`data/calibrated/<yyyymmdd>/…`, `geometry/calibrated/<yyyymmdd>/…`).
  `data/` is gitignored; nothing there is ever `git add`ed (`*.tif`, `*.zip`, `*.dat`
  are ignored too).

## 2. End-to-end commands (run from the repository root)

Register the pass (two one-line additions, no other code changes):

1. `backend/scripts/stokes_from_slc.py::PRODUCTS["<id>"]` with `raw`, `stem`, `out`,
   `out_perturb` (copy the `20200305` entry).
2. `backend/scripts/f2_complex_product.py`: `GEOM["<id>"]` (the geometry directory)
   and `PASS_STEM["<id>"]`.

Then, in this order (times measured on this machine, 8 cores, 16 GB; a full-swath
scene like pass 1 is the reference; a narrow pass is proportionally faster):

```bash
python backend/scripts/stokes_from_slc.py --product <id>            # ~1 min : Stokes, coherence, band identity, 64x64 low-CV blocks
python backend/scripts/stokes_from_slc.py --product <id> --block 32 # ~1 min : only where no 64x64 tile fits
python backend/scripts/enl_logratio.py                              # ~16 min: log-ratio look count N-hat, blocks, per-cell
python backend/scripts/f2_complex_product.py                        # ~36 min: F2 signal cells, rule, IUT; discs by class; crater_level_real
python backend/scripts/decision_rule.py                             # ~13 min: IUT selections, local N-hat counts
python backend/scripts/v21_extract.py                               # ~5-6 min: disc table (with terrain), selected cells
python backend/scripts/n_sensitivity_real.py                        # ~3 min: the per-N override on the new scene
python backend/scripts/shadow_identification.py                     # ~1-2 h on 8 cores: ladder, specification curve, overlap, permutation
python backend/scripts/verify_all.py                                # gates
```

`v21_extract.py` reads the pass list from its `PASSES` constant; add `("L", "<id>")`.
Artifacts written: `docs/stokes_from_slc_<id>*.json`, `docs/phase_gain_perturbation_<id>.json`,
`docs/enl_logratio.json::pass_<id>`, `docs/f2_complex_product.json::passes.<id>`,
`docs/disc_table_v21.json::discs.L_<id>`, `docs/selected_cells_v21.json::passes.L_<id>` (local only: gitignored, per-cell values are not published).

## 3. Numbers to compare with v21 (the replication checklist)

| quantity | v21 value (source) | replicates if |
|---|---|---|
| DOP < 0.13 fraction of cells | 1.50 % (`stokes_from_slc.json::results.invariant.dop_below_threshold.fraction`) | same order; it moves with relative gain (±0.5 dB: 1.03–1.74 %) |
| joint-rule fraction | 0.45 % | same order |
| band identity residual | every cell inside CPR ≤ 1.2989 at DOP < 0.13 | **exact** (an identity) |
| coherence, median | 0.658 frame, 0.174 in the homogeneous windows | reported, not compared |
| oversampling factor, 2WT | 3.10, 6.77 | predicted from the label before opening the product |
| log-ratio N-hat, blocks | 39.4 (28.5–46.0) | reported; decides whether 79.6 is reachable |
| selected cells significant at local N | 2 of 26 462 (and none in F2) | **the IUT selects 0 while N-hat < 218** |
| F2: signal / selected / significant | 663 / 50 / 0 | only if F2 is in the frame |
| discs: sunlit / shadowed / mixed rates | 5.7 / 14.2 / 6.2 % (two passes); L pass 1 8.8 / 14.8 % | shadow contrast direction and crude OR (a) ≈ 1.8 |
| shadow OR ladder (a) (c) (e0) | 1.79 (0.90–3.50), 0.67 (0.28–1.56), 1.01 (0.49–2.38) | **new scene's (c) and (e0) intervals include 1 again** ⇒ same conclusion |
| MH over coherence strata | 0.59 (0.31–1.06); pass 1 0.44 (0.23–0.79) | sign of the pass-1 reversal |
| region-mean null, 260 cells | 28 % at 39 looks | it is a simulation; independent of the scene |

## 4. Mini-RF products for an independent check on Faustini (not downloaded)

From the PDS Geosciences Node (search-result pages read, not downloaded):

* `LRO-L-MRFLRO-4-CDR-V1.0` — Level 1 calibrated data records: SAR images in
  range/azimuth geometry, β⁰, radiometrically and polarimetrically calibrated;
  each pixel is four 4-byte floats (H and V receive intensities, real and
  imaginary part of the H–V cross power) — i.e. exactly the coherency elements
  the criterion needs, at S-band (Mini-RF; hybrid-polarity, circular transmit; the 14.8 m products of Fa and Cai are zoom-mode). Archive volumes `lromrf_0001`…
  (several volumes). **Approximate size per observation: not verified** (a
  typical CDR strip is hundreds of MB to ~1 GB; the order asks for a figure
  and the catalogue pages read here do not state one, so none is given).
* Level 2 derived products (Stokes, CPR, m-χ mosaics) exist for the polar
  mosaics; their exact data-set IDs and volumes were **not** confirmed and are
  left to the author / the ODE search (<https://ode.rsl.wustl.edu/moon/>: select
  Mini-RF, CDR, and a footprint over Faustini).
* What to ask ODE for: products whose footprint contains F2 (−87.29°, 82.31°E);
  note the mode (the v21 supplement takes 8 nominal looks for the zoom mode from
  Raney et al. and 6.7 effective from Spudis et al.) — the look count matters to
  every statement that depends on N (Table II of v21).

No download is started. Yes / no from the author is required.

## 5. Which v21 sentences change

**If a second scene replicates** (identities exact; IUT empty at N-hat < 218; shadow contrast present
in the crude rate, and absent once coherence or geometry is added):

* Sec. VI-D, limitations "the disc models … rest on 96 to 133 firing discs per band,
  and the S-band pass shares the L-band pass's scene and geometry" — the last clause
  weakens (a third, independent acquisition), the firing-disc counts grow.
* Sec. VI-D conclusion ("the data neither attribute it to shadow nor rule shadow out")
  — stands, with a stated number of independent scenes.
* "What replicates" (limitations): add the scene to the list.
* Abstract "over 1888 crater-sized regions of real data": the count changes.
* Table III / S3: a third column.

**If it does not replicate** (for instance the IUT selects a cell, or the shadowed-disc
rate is not above the sunlit one, or the pass-1 MH reversal disappears):

* the identities cannot fail; any sentence resting on them is unchanged;
* "shadowed regions satisfy the rule more often than sunlit ones" (abstract, VI-D,
  conclusion) must be qualified as a property of this scene;
* "What replicates" must say which results did not;
* the limitation "a single pass" becomes a finding.
