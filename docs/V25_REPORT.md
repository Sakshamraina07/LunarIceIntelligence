# V25 report — second purge, an honest fresh clone, the deployed site, the wording

Order: V25. Permission used: ordinary commits, plain pushes of `main`, and, in Part A only, a rewrite of all refs and a `--force-with-lease` push of each. Nothing else: no tag, no release, no Zenodo, nothing sent to GitHub, nothing downloaded, the deployed site never contacted, no `.tex` edited.

## 0. The seven lines

1. **Part A list:** 190 paths removed in V25 (170 tile files of the CPR/DOP pyramid + 20 images), 200 blob versions, 113 distinct blobs, 33,261,527 bytes counted per version (31,687,254 bytes of distinct blobs across V24 and V25 together, with the two V24 layer files). Pixel sizes: tiles 27.6 x 80.8 m/px at zoom 3 (coarser below); images 28.6 (8 files), 40.4 (2), 57.1 (8), 80.8 (2), 141.8 (2), 144.0 (8) m/px; the two V24 layer files 25.0.
2. **Part A proof:** `git rev-list --all --objects` = 0 matches by name and 0 by blob id (115 recorded ids), locally after `reflog expire` + `gc --prune=now`, again after the push and fetch, and in a fresh clone (deleted). Forks 0, network 0, pull requests 0. New `main` tip of the rewrite `436dd46b7304aa1ca2cdd8ceffdc6e3cab90bae3`; tag `v1.0-submittable` object `bf42951f0af1d10d9996485fa29eae451a587f98` -> commit `3298175d7fc0591a58375d0f5cec7127bba4d373`. Backup `D:\FYP_backup_pre_v25.bundle` (146 MB, `git bundle verify` OK). **The proof found six files my first name list had missed**; see §1.
3. **verify_all.py:** author's machine **PASS 32, REQUIRES LOCAL DATA 0, FAIL 0** (exit 0). Fresh clone of the same commit **PASS 16, REQUIRES LOCAL DATA 16, FAIL 0** (exit 0). REQUIRES LOCAL DATA in the clone: G1, G2, G3, G4, G5, G6b, G7, G8, G15, G20, G24, G26, G27, G28, G31, G32 (the file each needs is in §2.3).
4. **Tracking the manuscript `.tex`:** recommended, for the two final files only, after a decision on preprints; not done. §2.4.
5. **Part C:** current `HEAD` would serve nothing finer than 200 m from DFSAR (frontend: the two CPR/DOP previews at about 258 m/px; backend: no static root, no tile route, `/mission` resamples to 100 x 100). **Not checkable from the repo:** older Vercel deployments built from commits before V24 contained the two 25 m layer files and stay addressable until deleted. §3.
6. **Old and new data sentence:** §4.
7. **Not checkable / open:** whether GitHub still serves the old objects by SHA, the Vercel and Render deployment history, and **TWO FINER-THAN-200 M ITEMS THAT REMAIN BY THE ORDER'S OWN SCOPE** (§5).

## 1. Part A — second purge

### 1.1 Order of work, as run

1. Backup `D:\FYP_backup_pre_v25.bundle` (`git bundle create --all`, verified).
2. The list was built before anything changed: `backend/scripts/purge_manifest_v25.py` read every blob version of every matching path on the remote-tracking refs (the pre-rewrite history) and wrote `docs/removed_native_renderings.json`: path, git blob id, sha256, bytes, first commit before the purge, image size in pixels, and the pixel size. The pixel size is a measurement chain, not an estimate: tile size and zoom for the pyramid; for screenshots the application's recorded map zoom (`docs/gate6/capture.*.json`, `docs/verify_map.json`, `docs/verify_v8_view*.json`) through the frame's 646.289 m per CRS unit, m/px = 646.289 / 2^zoom. The 2^zoom values: zoom 4.5 gives 28.6, 4 gives 40.4, 3.5 gives 57.1, 3 gives 80.8, 2.19 gives 141.8, 2.166 gives 144.0.
3. Every gate or script that depended on a removed image now depends on the sha256 + pixel size in that tracked JSON. Local copies are kept in `data/local_layers/` (gitignored) and `D:\FYP_local_layers\removed_v25\`. G28 C8b verifies them when present and reports REQUIRES LOCAL DATA when not.
4. `docs/propagation_ddop_map.png` is `export-ignore`d (checked: `git archive HEAD` does not list it, nor `frontend/public/layers/`, `probe_grid.bin`, `docs/gate6`, `docs/evidence`).
5. G28 was extended (C1, C8, C8b). Tested by forcing `frontend/public/layers/cpr_heatmap.webp`, one tile and `docs/gate6/before.detail.radar-signals-cpr.png` into the index: C1 FAILED on the layer file and C8 FAILED on all three; then undone (`git rm --cached`, files deleted, `git status` clean). **My clean-up also deleted the author's local, gitignored `cpr_heatmap.webp`; I restored it from `data/local_layers/` and checked it by sha256 against the recorded value and `D:\FYP_local_layers\cpr_heatmap.webp` (all three identical).**
6. Forks 0, network 0, pull requests 0 (public API, read-only; `gh` is not installed), checked twice, before the rewrite and before the push. Origin matched the lease values.
7. Rewrite and proof, below.

### 1.2 THE FIRST PASS MISSED SIX FILES. THE BLOB-ID PROOF CAUGHT THEM.

After the first rewrite (filter by path) the proof by name was clean (0) but **the proof by blob id was not: 6 of the 115 recorded blobs were still reachable under other names.** Four were gate-6 captures stored a second time as `docs/gate6/before.{detail,full}.{radar-signals-cpr,degree-of-polarisation}.png` (the same bytes as the `...cpr_heatmap.png` / `...dop_heatmap.png` files; the layers were renamed between commits), and two were old versions of `docs/v8_after_reset.png` and `docs/v8_full_extent.png` equal to the purged `.before` captures (CPR proxy drawn, 80.8 and 141.8 m/px). Nothing had been pushed. I recorded them in the manifest, extended the filter to remove by blob id and by name, rewrote again, and repeated the proof: 0 and 0. The current versions of the two `v8_*` files stay (hillshade only; checked by a saturation scan of every historical version). G28 C8 now checks by blob id as well as by name, so the same miss cannot recur.

### 1.3 Rewrite, proof, push

`git filter-branch --index-filter` (127 commits, all four branches and the annotated tag, remote-tracking refs left alone); `git filter-repo` is not installed. `refs/original` deleted; `git reflog expire --expire=now --all`; `git gc --prune=now`.

| step | by name | by blob id |
|---|---|---|
| local refs after expire + gc (`--branches --tags`) | 0 | 0 |
| after the push and `git fetch --prune`, expire + gc, `--all` | 0 | 0 (0 of the 115 ids in the object store) |
| fresh clone of origin into a temp folder outside `D:\FYP`, `--all` (pack 113.8 MiB), deleted afterwards | 0 | 0 |

Force-pushed one ref at a time, each with `--force-with-lease=<ref>:<old value>` (every lease held):

| ref | old (before V25) | new |
|---|---|---|
| `refs/heads/main` | 90e13a5e6e5d3d2704e8f6f17adfe51a18c84e7b | **436dd46b7304aa1ca2cdd8ceffdc6e3cab90bae3** (later plain pushes only add descendants) |
| `refs/heads/parked/nextjs-scaffold` | 2d8110c66e115f6a51fa8131bdc04ac15f242ada | 2ccafbe19bd2809c4481c211221615e1d3de34c6 |
| `refs/heads/parked/root-public-assets` | 9d80d8303d2937db65baaf98e7c5e491f92b5e2e | fd4ec19d092720b176a0bf40166cda4150268c05 |
| `refs/heads/parked/tile-pyramid` | d88e16f2be3eb609faf123eb612f113d48b2d2dd | e9787429cda8ca241a2b5a50b271552e48bb1260 |
| `refs/tags/v1.0-submittable` (annotated) | tag object 68c013dcb4cb33c7614f3dd1c5d47134c733eb04 -> commit fe39d7537a4710018d67b39e154553e478937ed7 | tag object **bf42951f0af1d10d9996485fa29eae451a587f98** -> commit **3298175d7fc0591a58375d0f5cec7127bba4d373** |

**First changed commit on every ref: the root commit, old `93fab624c1c71dda4307a9a73daa44bafe3d717c` (2026-08-30, "first commit"), because the tile pyramid was in it; every commit hash has changed since the V24 state.** The new root is `fbf1a67b97b9c2ffe4fcdaf466581e6ae29127af`.

## 2. Part B — an honest fresh clone

### 2.1 How the needs were found (measured, not remembered)

The 14 failing gates of V24 were a symptom; the first fresh-clone run of this order showed 14 failing, 18 passing. Instead of guessing each gate's missing input, **every gate was run on the author's machine under a python audit hook that logs every file the process opens**, and the files git does not track were listed per gate (the node gate G15 was read from its source). That table is `NEEDS` in `backend/scripts/verify_all.py`. Comparing it with the clone run found three things that a list of failing gates would not:

* **G1 printed PASS on a missing input.** In the clean clone it wrote `docs/PROVENANCE.md` with "SOURCE NOT VERIFIED" in 18 terrain rows and passed. It now exits 77 (REQUIRES LOCAL DATA) before writing anything, and a present but unreadable sidecar is a FAIL.
* **G28 printed PASS while its C8b (local copies of the removed renderings) could not run.** It now exits 77 in that case, and 1 on any real failure.
* **G18 differs between the two machines but is legitimate in a clone**: all four of its assertions ran on both; with the rasters absent the mission endpoint answers NOT_INGESTED, which is the stricter case for "the report is served independently of the mission state". G10 and G19 differ only by one gitignored per-cell file they happen to scan.

### 2.2 What `verify_all.py` does now

PASS, REQUIRES LOCAL DATA, FAIL. **REQUIRES LOCAL DATA only when something the gate needs is absent** (the `NEEDS` table, checked before the gate runs, or the gate exiting 77); then the gate is not run and the table says which file. If the files exist the gate runs, and a wrong input FAILS. Exit status is non-zero only on FAIL. Totals are printed; `docs/verification.json` carries them and `all_pass` is true only if every gate passed. `--only G1,G24` runs a subset.

### 2.3 Runs

* **Present but wrong must FAIL (tested):** in a fresh clone I created a junk file at every path in `NEEDS`, an empty `frontend/node_modules` and a wrong local copy of one removed layer. Result: **PASS 16, REQUIRES LOCAL DATA 0, FAIL 16**; every gate that has a declared need FAILED, none passed, none reported REQUIRES LOCAL DATA; the 16 that read tracked files only still passed. G28 failed on exactly the planted wrong local copy.
* **A fresh clone with nothing:** first run of this code, from a clone of the local commit: **PASS 16, REQUIRES LOCAL DATA 16, FAIL 0**, exit 0. The 16 passing: G6, G9, G10, G12, G13, G16, G17, G18, G19, G21, G22, G23, G25, G29, G30, G33.
* **Author's machine, tree of commit `0f51576`** (everything present; the full run, about 12 minutes): **PASS 32, REQUIRES LOCAL DATA 0, FAIL 0**, exit 0; `docs/verification.json` records it. **Fresh clone of that commit** (`git clone` into a temp folder outside `D:\FYP`, deleted afterwards): **PASS 16, REQUIRES LOCAL DATA 16, FAIL 0**, exit 0. The last commit changes only this report and `docs/verification.json`; G10, G19, G25 and G28 were re-run on it.

REQUIRES LOCAL DATA in a fresh clone, with the file each needs (`NEEDS` has the full paths):

| gate | needs |
|---|---|
| G1 | `data/pradan/lola/ldem_frame_25m.provenance.json` |
| G2 | `horizon_240m.npz` and its sidecar, `illumination/LPSR_75S_120M_201608.IMG`, `illumination/AVGVISIB_75S_120M_201608.IMG`, the PRADAN scene `..._d_sri_xx_cp_lh_d18.tif` and `..._xx_d18.xml` |
| G3 | the same horizon files, the LOLA sidecar, `native/dem_native.tif`, `native/valid_native.tif`, the scene LH tif and label |
| G4 | the horizon files, `dem_native.tif`, `valid_native.tif`, the scene LH tif and label |
| G5 | `native/cpr_native.tif`, `native/dop_native.tif`, `native/valid_native.tif` |
| G6b | the author's local `frontend/public/layers/cpr_heatmap.webp` and `dop_heatmap.webp` |
| G7 | `dem/faustini_lola_dem.tif`, `dfsar/cpr_real.tif`, `dfsar/dop_real.tif`, `dfsar/metadata_real.json`, the horizon files, the LOLA sidecar, `dem_native.tif` |
| G8, G24 | `horizon_240m.provenance.json` and `ldem_frame_25m.provenance.json` |
| G15 | `frontend/node_modules` (`npm install`) and a Chrome or Edge executable |
| G20 | the 2020-03-05 scene LH and LV tifs, and the 2020-08-08 scene LH and LV tifs |
| G26 | `data/derived/fig_scene/fig_scene_cache.npz` |
| G27 | the 2020-08-08 `gri`, `sli` and `sri` bundles (tifs and labels), 12 files |
| G28 | `data/local_layers/` (check C8b; checks C1 to C8 ran and passed) |
| G31 | the 2020-08-08 scene LH and LV tifs |
| G32 | `Claude outputs/grsl/dfsar_detection_limits_submission.tex` and `..._supplement.tex` |

### 2.4 Should the submission and supplement `.tex` be tracked under `paper/manuscript/`? (NOT DONE; needs the author's yes)

**Recommendation: yes, for those two files only, once the preprint question is settled.**

For: G32 (every cell of the closed-form tables recomputed against the `.tex`) then runs in anyone's clone and stops being the one gate whose evidence is invisible to a reviewer; the number audits can be rerun; the text the artifacts were stamped against is versioned with them; and "which draft did the numbers come from" gets an answer in git.

Downside, plainly:

1. **It publishes the submission text.** Whether that is acceptable depends on the venue's preprint policy and on the author's wishes; GRSL-type venues generally allow a preprint, but this is the author's call, not mine.
2. **Git history is permanent.** Anything in a committed draft (comments, reviewer-facing remarks, an earlier wording) is public from the push on, and removing it later means a third history rewrite like V24 and V25.
3. **Copyright after acceptance.** A tracked `.tex` becomes the publisher's text after a copyright transfer; the MIT licence on the repository would need a line saying it does not cover the manuscript.
4. **Two sources of truth.** `paper/` already holds untracked `_v20`, `_v21` and `_full` variants; tracking one pair invites drift unless the others are deleted or ignored.
5. **Paths.** G32 and the audit scripts read `Claude outputs/grsl/`; moving the files means editing those paths (scripts, not `.tex`), and the gate's `NEEDS` entry.

If yes: add `paper/manuscript/{submission,supplement}.tex`, point the readers at them, and keep `Claude outputs/`, `docs/gate10/` and the `_v20`/`_v21`/`_full` files untracked.

### 2.5 README

New section "Reproducing": which gates run with nothing downloaded; which need the PRADAN scene, by identifier (`ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_xx_d18`, archive `urn:isro:isda:ch2_cho:sar_calibrated`, plus the second scene `ch2_sar_ncxl_20200305t114902885_*`) and where each goes; what else is local; and why the ISRO rasters are not in the repository. It contains no instruction to obtain ISRO data other than from PRADAN under its terms.

## 3. Part C — deployed site, from the repository only (nothing changed, the site not contacted)

* `frontend/vercel.json` holds cache headers only: `/`, `/index.html`, `/assets/*`, `/analysis/*`, `/layers/*`. No rewrite, no function, no ignore rule. There is no Render configuration file in the repository (`render.yaml`, Dockerfile, Procfile: none tracked).
* **Frontend from `HEAD`.** What Vite publishes is `frontend/public/`: `layers/` (four LOLA layers of 6618 x 2258 px at 25 m, **not DFSAR**; `cpr_heatmap.preview.webp` and `dop_heatmap.preview.webp`, 640 x 218 px = about 258 m/px, **coarser than 200 m**; `layers.json`), `analysis/` (JSON, and `probe_grid.bin` at 200 m, not finer), `lunar-dem.png`, icons. **Nothing finer than 200 m from DFSAR.** `layers.json` still lists the two 6618-px files; the map paints the preview and then requests `/layers/cpr_heatmap.webp`, which does not exist in a build from git (a 404 and a console error, the preview stays). `layers.json` also carries the valid-footprint polygon (coverage geometry, not a rendered quantity).
* **Backend from `HEAD`.** `backend/app/main.py` has no `StaticFiles` mount and `api_router.py` has no tile or file route; the XYZ tile endpoint was deleted (`frontend/src/landing/services/lunarBasemap.ts` says so). Routes: `/health`, `/craters`, `/mission/{crater}`, `/sensitivity/{parameter}`, `/report/status/{crater}`, `/report/pdf/{crater}`, `/ingest/status`, `/ingest/generate-samples`, `/copilot/ask`. `/mission` builds CPR and DOP PNGs at runtime, but from the local rasters, which a host built from git does not have (it answers NOT_INGESTED), and even where they exist it resamples to a 100 x 100 grid (`frame.metres_per_pixel((100, 100))`: about 1.65 km along and 0.56 km across the swath per cell). The PDF renders from the committed analysis JSON, no per-pixel image. **Nothing finer than 200 m.**
* **NOT CHECKABLE FROM THE REPOSITORY, AND THE ONE THING TO DO ABOUT IT.** A Vercel deployment is immutable. Every deployment built from a commit between `4a683ea` (2026-09-05, which added the two layer files) and the V24 force-push contained `/layers/cpr_heatmap.webp` and `/layers/dop_heatmap.webp` at 25 m, and such a deployment (a preview or an older production one) stays addressable by its own URL until it is deleted; the production alias stops serving them only when a build from the new `main` becomes current. I did not look. If the project is deployed with the Vercel CLI from this folder rather than from git, the local gitignored copies of those two files sit in `frontend/public/layers/` and the CLI's ignore rules decide whether they upload; a `.vercelignore` listing them would remove the doubt. A Render service built from a commit that still had a tile route would still serve it until redeployed.

## 4. Part D — wording true for the final tree

| where | old (V24) | new |
|---|---|---|
| `DATA.md` | "It contains no Chandrayaan-2 or LOLA source product (...) and no native-resolution rendering of a DFSAR-derived quantity as a layer file." and "application screenshots kept as verification evidence (`docs/gate6/`, `docs/map_*_cpr.png` and similar) can show the amplitude-derived CPR and DOP proxy layers at the application's map zoom, up to about 29 m/px. They are pictures of the interface, not data files." | "It contains no Chandrayaan-2 or LOLA source product (...) and no layer file, tile or screenshot that renders a DFSAR-derived quantity at a pixel size finer than 200 m." plus a "What was removed" paragraph (what, how, the manifest, the gate) and **two stated exceptions not removed** (§5). |
| `README.md` | "The ~9 GB of Chandrayaan-2 and LOLA rasters are gitignored." | "...are not in this repository: they are gitignored, none was ever committed (`check_repo_complete.py` reads all of history), and the repository holds no layer, tile or screenshot that renders a DFSAR-derived quantity finer than 200 m per pixel, apart from the two exceptions `DATA.md` states." and the "Reproducing" section. |
| `CITATION.cff` abstract | "Contains no Chandrayaan-2 or LOLA source products and no native-resolution rendering of a DFSAR-derived quantity: it holds code, derived numerical results, figures, coarse aggregate layers (about 200 m and coarser) and LOLA-only map layers." | "Contains no Chandrayaan-2 or LOLA source products and no layer, tile or screenshot rendering a DFSAR-derived quantity at a pixel size finer than 200 m, with two stated exceptions (DATA.md): a 125 m per pixel delta-DOP map on GitHub that is not in the release archive, and one panel of a manuscript figure at 25 m bins. It holds ..." |
| `.zenodo.json` | "This record contains no Chandrayaan-2 or LOLA source products and no native-resolution rendering of a DFSAR-derived quantity." | "This record contains no Chandrayaan-2 or LOLA source products and no layer, tile or screenshot rendering a DFSAR-derived quantity at a pixel size finer than 200 m, with one stated exception: panel (b) of the manuscript figure `paper/fig_scene.pdf`, the sample CPR at 25 m bins over a 12 x 3.8 km window." (the archive excludes the 125 m map, so only one exception applies to it) |

The old sentences were true only of "layer files"; the screenshots and the tile pyramid were still in the tree and in history. The new ones are true of the final tree and are checked by G28 C1, C8 and C8b.

### GitHub Support draft (NOT SENT; covers both purges and every first-changed commit)

> Subject: Request to purge cached views and refs after removing third-party copyrighted satellite-data renderings, in two history rewrites — Sakshamraina07/LunarIceIntelligence
>
> Repository: https://github.com/Sakshamraina07/LunarIceIntelligence (public, 0 forks, network count 0, 0 pull requests).
> I removed renderings of data derived from the Chandrayaan-2 Dual-Frequency SAR product distributed by ISRO through PRADAN, whose copyright remains with ISRO, from all branches and the release tag by rewriting history and force-pushing, twice.
> **Rewrite 1 (V24):** `frontend/public/layers/cpr_heatmap.webp` and `frontend/public/layers/dop_heatmap.webp` (6618 x 2258 px, 25 m/px). Old blob ids 25e989d5014b25c9607e8f098f0787d4a3c13513 and fc65c9dca918f8e8cd6d79595645d4cfe523003b, added in 4a683ea. First changed commit: d88e16f2be3eb609faf123eb612f113d48b2d2dd (old 4a683ea). Old tips: main 5dfde50, parked/nextjs-scaffold 29bf48c, parked/root-public-assets ebf75c7, parked/tile-pyramid 4a683ea, tag v1.0-submittable 4817c00. Tips after it: main 90e13a5e6e5d3d2704e8f6f17adfe51a18c84e7b, parked/nextjs-scaffold 2d8110c66e115f6a51fa8131bdc04ac15f242ada, parked/root-public-assets 9d80d8303d2937db65baaf98e7c5e491f92b5e2e, parked/tile-pyramid d88e16f2be3eb609faf123eb612f113d48b2d2dd, tag object 68c013dcb4cb33c7614f3dd1c5d47134c733eb04.
> **Rewrite 2 (V25):** the CPR and DOP map-tile pyramid (`backend/tiles/faustini/cpr_heatmap/**` and `dop_heatmap/**`, 170 files) and 20 screenshot paths under `docs/` (`docs/gate6/*cpr_heatmap*`, `*dop_heatmap*`, `*radar-signals-cpr*`, `*degree-of-polarisation*`; `docs/map_before_cpr.png`, `docs/map_after_cpr.png`; `docs/v8_opening_view.png`, `docs/v8_opening_view.before.png`, `docs/v8_after_reset.before.png`, `docs/v8_full_extent.before.png`, and one old version each of `docs/v8_after_reset.png` and `docs/v8_full_extent.png`). 113 distinct blob ids, listed with sha256, size and pixel size in `docs/removed_native_renderings.json` in the repository; ids are those recorded under the V25 rewrite's `git_blob` fields. **First changed commit: the root commit, old 93fab624c1c71dda4307a9a73daa44bafe3d717c (2026-08-30), new fbf1a67b97b9c2ffe4fcdaf466581e6ae29127af; every commit id changed on every ref.** Tips before: the four listed under Rewrite 1 "after". Tips after: main 436dd46b7304aa1ca2cdd8ceffdc6e3cab90bae3, parked/nextjs-scaffold 2ccafbe19bd2809c4481c211221615e1d3de34c6, parked/root-public-assets fd4ec19d092720b176a0bf40166cda4150268c05, parked/tile-pyramid e9787429cda8ca241a2b5a50b271552e48bb1260, tag object bf42951f0af1d10d9996485fa29eae451a587f98 (commit 3298175d7fc0591a58375d0f5cec7127bba4d373).
> Affected pull requests: none. Forks: none.
> Please run garbage collection on the repository so that the old objects (both rewrites) are not retrievable by URL or by SHA, and clear cached views of the removed paths and of the old commits. Thank you.

## 5. FLAGS

* **PAPER/FIG_SCENE.PDF PANEL (B) IS A 25 M-BIN RENDERING OF THE SAMPLE CPR (A DFSAR-DERIVED QUANTITY) OVER 12 x 3.8 KM, TRACKED, AND IN THE RELEASE ARCHIVE. THE ORDER SAYS KEEP THE PAPER FIGURES; THE STANDING RULE SAYS NO NATIVE-RESOLUTION RENDERING IN ANYTHING PUBLISHED. THOSE TWO CONTRADICT EACH OTHER. I DID NOT REMOVE OR EXPORT-IGNORE IT; I STATED IT IN THE DATA SENTENCE.** Options: regenerate panel (b) at 200 m or coarser (a script change in `paper/make_fig_scene.py`, no `.tex` edit), or accept it knowingly, or `export-ignore` the PDF (keeps it off Zenodo, not off GitHub).
* **`docs/propagation_ddop_map.png` (about 125 m/px, a delta-DOP perturbation map) STAYS ON GITHUB, `export-ignore`d, AS ORDERED; THAT IS ALSO FINER THAN 200 M.** Stated in `DATA.md`.
* **The V24 judgement call stands:** every historical blob of `docs/v8_opening_view.png` was removed because one version showed the CPR proxy at 57.1 m/px; the file is gone from the tree.
* **Kept on purpose:** `docs/evidence/traverse/*` (LOLA relief and single-cell probe read-outs; I looked at one: no CPR or DOP layer is on the map, but a single cell's CPR and DOP values are printed), `probe_grid.bin` (200 m), the previews (about 258 m), the four LOLA layers.
* The previous V24 report said no gate prints REQUIRES LOCAL DATA; that was true then and is superseded here.
* Not checkable: whether GitHub still serves the old objects by SHA or in cached views (only Support can clear them; the draft above is unsent); the Vercel and Render deployment history (§3).

## 6. Files changed by V25

`backend/scripts/purge_manifest_v25.py` (new), `docs/removed_native_renderings.json` (new), `backend/scripts/check_repo_complete.py` (C1, C8, C8b, exit 77), `backend/scripts/verify_all.py` (three outcomes, `NEEDS`, `--only`), `backend/scripts/emit_provenance.py` (G1: absent -> 77, unreadable -> FAIL), `.gitattributes` (`propagation_ddop_map.png`), `README.md`, `DATA.md`, `CITATION.cff`, `.zenodo.json`, `docs/verification.json`, this report. Untracked and left untracked: `Claude outputs/`, `docs/gate10/`, `frontend/scripts/layout_metrics.mjs`, `frontend/scripts/text_inventory.mjs`, `submission_check.json`, and the `.tex` files in `paper/`.
