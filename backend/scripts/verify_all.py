"""
verify_all.py -- every gate's evidence, in one command, mapped to the PRD.

    python -u backend/scripts/verify_all.py [--skip-slow]

WHAT THIS IS FOR
----------------
PRD section 6 lists the statements the project is done when all of them are
true -- the count is READ from PRD.md, never spelled here,
"and each is backed by a number in a report". Those numbers exist, but they were
spread across eight scripts and a browser verifier, so "is the project done" was
a question you answered by remembering where to look.

This runs them, collects the verdicts, and prints ONE table whose rows are the
those statements. It writes docs/verification.json.

THREE OUTCOMES, NEVER TWO (V25)
-------------------------------
    PASS                 the gate ran on its inputs and its check held.
    REQUIRES LOCAL DATA  an input the gate reads does not exist on this machine (a PRADAN scene, a provenance file under
                         data/, the untracked manuscript .tex, a local build or cache). The gate did NOT run and
                         therefore verified nothing: it is counted separately and never printed as PASS.
    FAIL                 the inputs exist and the check is wrong, or a gate that should have run did not.

A gate is REQUIRES LOCAL DATA only when something it needs is ABSENT (the NEEDS table below, checked before the gate runs,
or the gate itself exiting 77). A present input is never excused: if the files exist the gate runs, and a wrong one FAILS.
The exit status is non-zero ONLY for FAIL. On the author's machine (everything present) every gate is PASS; in a fresh
clone the answer is 0 FAIL plus the list of what each REQUIRES LOCAL DATA gate needs.

IT ASSERTS NOTHING OF ITS OWN. Every verdict here is produced by the gate that
owns it; this script's only job is to run them all and map each to the statement
it backs. A verifier that computed its own opinion would be a seventh source of
truth, and this project has spent long enough removing those.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent
REQUIRES_LOCAL_DATA_RC = 77   # a gate (or this table) says: an input does not exist here

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

#: (id, PRD statement, the gate that backs it, argv, slow?)
# The stamped-artifact count is READ from the registry, never written here. It
# was "15 artifacts" and went stale the moment a sixteenth was added -- METHODS
# section 0, first pattern, inside the file whose job is to catch it.
sys.path.insert(0, str(SCRIPTS))
from stamp_methods import ARTIFACTS as _STAMPED  # noqa: E402
_N_STAMPED = len(_STAMPED)


def _prd_statement_count() -> int:
    """How many statements PRD section 6 actually lists, read from the file.

    It said "six" while the section listed nine, for the same reason METHODS
    section 0's first pattern exists: a human wrote a count once and nothing
    afterwards made it agree with the thing counted. Both of the other counts in
    this file are read (the stamped artifacts, the gate rows); this one was the
    last one spelled.
    """
    text = (BASE_DIR / "PRD.md").read_text(encoding="utf-8")
    sec = text.split("## 6 · Definition of done", 1)
    if len(sec) < 2:
        return 0
    body = re.split(r"\n## ", sec[1], maxsplit=1)[0]
    return len(re.findall(r"^(\d+)\. ", body, flags=re.M))


GATES = [
    ("G1", "Every number on #mission carries a mark and resolves to a raster "
           "read or an explicit absent state",
     "emit_provenance.py — six assertions, each injection-tested",
     [sys.executable, str(SCRIPTS / "emit_provenance.py"), "faustini"], False),

    ("G2", "PSR, cold-trap overlap and illumination come from a horizon "
           "computation over the full LOLA array at a stated resolution",
     "validate_psr_vs_lola.py — against the LOLA team's own published mask",
     [sys.executable, str(SCRIPTS / "validate_psr_vs_lola.py")], True),

    ("G3", "Landing sites are the argmax of a six-criterion search over 14.9 M "
           "native cells with stated NMS and per-criterion evidence",
     "search_landing_sites.py — plus the interpolation guard",
     [sys.executable, str(SCRIPTS / "search_landing_sites.py"), "--top", "5"], True),

    ("G4", "The traverse is Dijkstra over a slope-and-hazard cost surface at a "
           "stated planning resolution, with UNREACHABLE a real state",
     "plan_traverse.py — connectivity reported before any distance",
     [sys.executable, str(SCRIPTS / "plan_traverse.py")], True),

    ("G5", "CPR is an explicitly-labelled amplitude-only ratio with the claim "
           "withdrawn, and CANDIDATE AREA is a measurement including a zero",
     "detection_statistics.py — the critical value, the table, and the withdrawn interval",
     [sys.executable, str(SCRIPTS / "detection_statistics.py")], False),

    ("G6", "The map's relief is real at 25 m, lit from more than one direction, "
           "and the base filter is set from a histogram rather than by eye",
     "hillshade_histogram.py + composite_contrast.py",
     [sys.executable, str(SCRIPTS / "hillshade_histogram.py")], False),

    ("G6b", "(same statement) the science layers composite over that relief "
            "without hiding it",
     "composite_contrast.py — retention AND correlation with the base",
     [sys.executable, str(SCRIPTS / "composite_contrast.py"), "--opacity", "0.45"], False),

    ("G7", "The API and the static analysis agree on every terrain quantity "
           "they both report",
     "assert_paths_agree.py — in-process, needs no server",
     [sys.executable, str(SCRIPTS / "assert_paths_agree.py")], False),

    ("G8", "Every measured figure quoted in METHODS.md still matches the "
           "artifact it was transcribed from",
     f"stamp_methods.py --check — {_N_STAMPED} artifacts",
     [sys.executable, str(SCRIPTS / "stamp_methods.py"), "--check"], False),

    # G7 compares the API against the analysis on slope, roughness and hazard.
    # It has never looked at the PDF, which is how a formal report came to print
    # five landing sites that Phase 3 deleted, one of them marked RECOMMENDED,
    # beside a rover figure the screen reports as NO DATA. Third time two
    # surfaces have disagreed; this closes the last one.
    ("G9", "The PDF report prints nothing the analysis artifacts do not contain",
     "assert_pdf_agrees_with_analysis.py — the rendered bytes, not the inputs",
     [sys.executable, str(SCRIPTS / "assert_pdf_agrees_with_analysis.py")], False),

    # A figure that is an upper bound and a figure that is a rate are different
    # claims, and the difference is one phrase -- exactly the kind of thing that
    # survives one edit and is gone by the third.
    ("G10", "A figure that is an upper bound is never quoted as if it were a rate",
     "assert_upper_bounds_labelled.py — every occurrence, every tracked source",
     [sys.executable, str(SCRIPTS / "assert_upper_bounds_labelled.py")], False),

    # sin(theta) = ((R+h)/R) sin(eta) with (R+h)/R > 1 is an identity on a convex
    # body. The project shipped a criterion built on a field where 80.53 % of the
    # values sat below the look angle, and nothing checked it because nothing had
    # ever needed to. And there is one CPR field with one look count: the
    # narrative quoted N ~ 5 while the artifact published 13.72.
    ("G12", "There is one incidence field, it satisfies incidence > look angle, "
            "and nothing consumes a field that does not",
     "assert_incidence_geometry.py --only g12 — the identity, and every consumer",
     [sys.executable, str(SCRIPTS / "assert_incidence_geometry.py"),
      "--only", "g12"], False),

    ("G13", "There is one CPR field and every consumer reads the same look count "
            "for it",
     "assert_incidence_geometry.py --only g13 — read from the pipeline, not inferred",
     [sys.executable, str(SCRIPTS / "assert_incidence_geometry.py"),
      "--only", "g13"], False),

    # The deployed page was blank: one uncaught throw in one effect unmounted the
    # whole tree. No gate had ever loaded the BUILT application, and the dev
    # server cannot see it -- the crash needs the production bundle and the
    # production API base. This builds it, serves it against a stub returning the
    # exact degraded payload the deployed backend returns, and refuses a blank
    # page or a single console error.
    ("G15", "The production build mounts and renders against a backend that "
            "answers 200 and says it has no data",
     "verify_production.mjs --all-states — the built bundle, all three backend states",
     ["node", str(BASE_DIR / "frontend" / "scripts" / "verify_production.mjs"),
      "--all-states"], True),

    # The report is the one artefact that leaves the browser, and it must obey
    # the same three-state rule the screen does: on a host that answers but
    # holds no ARTIFACTS, NO PDF IS ISSUED -- 409 -- and a PDF that IS issued
    # says what it was rendered from.
    #
    # This comment used to end "the deployed backend is in exactly that state,
    # so this gate, and the PDF fix it guards, are VERIFIABLE LOCALLY ONLY."
    # That was false: the precondition is the committed artifacts, not the
    # rasters, and the deployed host serves the report with HTTP 200. METHODS
    # and PRD were corrected when the claim was withdrawn; this line was missed,
    # and G19 found it.
    ("G16", "A report is issued only on a host that holds the artifacts, and it "
            "names the state it was issued under",
     "assert_pdf_refuses_without_rasters.py — the loader, the 409, the rendered bytes",
     [sys.executable, str(SCRIPTS / "assert_pdf_refuses_without_rasters.py")], False),

    # Stage 09's sliders stopped re-querying a host that has no rasters and now
    # read a precomputed grid. That removed a dependency and introduced a new way
    # to be wrong: a grid of identical cells is a control surface over a criterion
    # that does not discriminate. A CPR axis spanning the PUBLISHED threshold is
    # exactly that -- nothing here comes within 235x of it -- so the axis is built
    # from the measured field, and this asserts it still is.
    ("G17", "The precomputed sweep discriminates on both axes, its axes are built "
            "from the measured field, and it agrees with the analysis",
     "assert_sweep_grid_discriminates.py - agreement, measured axes, it moves, the crossing",
     [sys.executable, str(SCRIPTS / "assert_sweep_grid_discriminates.py")], False),

    # The Report control said "NEEDS AN INGESTED HOST" while the host it named was
    # serving that report with HTTP 200. It derived its state from the MISSION
    # endpoint, which recomputes and needs the rasters; the report renders
    # committed artifacts and needs none. One boolean, two capabilities -- and the
    # same false premise reached the report's own front page, METHODS and PRD.
    # It survived because it made the project look WORSE than it is, and nothing
    # here is tuned to notice modesty.
    ("G18", "The report's availability is measured at its own endpoint and never "
            "inferred from the mission endpoint's state",
     "assert_report_state_is_its_own.py - independent, not derived, honest doc, probe works",
     [sys.executable, str(SCRIPTS / "assert_report_state_is_its_own.py")], False),

    # Eight claims have been withdrawn after being measured wrong, each recorded
    # in METHODS section 0. A withdrawal only holds if the claim cannot come
    # back, and prose is copied forward -- one of these was found still alive in
    # THIS FILE's own comment when the gate was written.
    #
    # Every term names a CLAIM, never a figure. An ad-hoc predecessor rejected
    # the bare string "8.75", which is simultaneously a deleted fabrication, the
    # measured 8.75 km amplitude ribbon, and a look count derivable from Fa &
    # Cai 2013. A scan that fires on a bare number either blocks correct work or
    # gets disabled, and both are worse than one that names what it forbids.
    ("G19", "A claim this project withdrew cannot reappear in a tracked source, "
            "and every scan term names a claim rather than a figure",
     "assert_withdrawn_claims_absent.py --list prints each term with the sentence it forbids",
     [sys.executable, str(SCRIPTS / "assert_withdrawn_claims_absent.py")], False),

    # METHODS section 1's identity is ALGEBRA, so it cannot depend on which
    # acquisition it is evaluated on. A second, independent product is therefore
    # a real check on whether these files are being read correctly at all, and a
    # POSITIVE result rather than an absence. If it ever fails to replicate, the
    # finding is that we are reading the file wrong -- this gate forces that
    # conclusion rather than leaving it available.
    ("G20", "The CPR/DOP degeneracy replicates on an independent acquisition and "
            "the measured crossing sits on the closed form",
     "assert_degeneracy_replicates.py — 2020-03-05, a different orbit, look angle, PRF and grid",
     [sys.executable, str(SCRIPTS / "assert_degeneracy_replicates.py")], True),

    # The candidate-area interval was taken on 2,337,086 raw pixels while 7.9.1
    # measured 61.42 px per independent sample, so it came out ~61x too narrow.
    # A confidence interval that is too narrow is worse than none: it states a
    # precision the data does not have, on the one number this project exists to
    # report honestly.
    ("G23", "No interval is reported on the candidate area, the withdrawal is on "
            "the record, and the effective-sample count is read not copied",
     "assert_wilson_on_effective_samples.py - no interval on a structural zero, "
     "38,050 effective samples",
     [sys.executable, str(SCRIPTS / "assert_wilson_on_effective_samples.py")], False),

    # METHODS 3 said the frame DEM was LDEM_80S_80M at 80 m; it is LDEM_80S_20M
    # at 20 m. Section 3 described the product Phase 8 replaced and was never
    # updated, so the document contradicted itself -- 3 said 80, 8 said 20. There
    # are TWO LOLA products here (frame DEM 20 m, horizon 80 m) and the defect is
    # quoting one for the other.
    ("G24", "The frame DEM's product and post spacing are read from its "
            "provenance file, and the horizon's remain distinct",
     "assert_lola_product_agrees.py - two products, never confused",
     [sys.executable, str(SCRIPTS / "assert_lola_product_agrees.py")], False),

    # viva.md said "Nine gates" and "five times the apparatus was wrong"; README
    # said "nineteen gates". There were twenty-one and METHODS 0 records seven.
    # Three numbers, three documents, all stale, none wrong when written --
    # section 0's FIRST pattern, and nothing was checking.
    ("G25", "No document spells a count it could read from the thing it counts",
     "assert_counts_are_read.py - gate count and apparatus failures, read not spelled",
     [sys.executable, str(SCRIPTS / "assert_counts_are_read.py")], False),

    # Is the bundle on disk the product the paper claims? Seven checks across
    # representations a wrong, truncated, edited or substituted file could not
    # all satisfy at once -- filename timestamp against the label, per-line
    # epoch times against the observation window, declared geometry against the
    # byte count, the manifest, the look-bandwidth identity, and SHA-256.
    ("G27", "The Chandrayaan-2 bundle on disk is the product the manuscript "
            "names, and is internally coherent",
     "verify_data_provenance.py - 7 checks, emits docs/data_provenance.json",
     [sys.executable, str(SCRIPTS / "verify_data_provenance.py")], False),

    # Does the repository contain what the paper promises? Includes C7, which
    # reads the whole of git HISTORY -- a raster committed once and deleted
    # later is still in history and would become public with the repository.
    ("G28", "The repository contains what the paper promises, and its history "
            "carries no data or secret",
     "check_repo_complete.py - C1-C7, C7 scans every path ever committed",
     [sys.executable, str(SCRIPTS / "check_repo_complete.py")], False),

    # matplotlib emits Type 3 fonts by default and IEEE PDF eXpress rejects
    # them. That make_figures.py sets pdf.fonttype=42 is a claim about the
    # script; this regenerates the figures and inspects the bytes.
    ("G26", "Every figure regenerates, embeds its fonts, and carries no Type 3",
     "paper/assert_figures_embed_fonts.py - rebuilt, then read from the PDF itself",
     [sys.executable, str(BASE_DIR / "paper" / "assert_figures_embed_fonts.py")], True),

    # Seven artifacts were emitted so the manuscript's sensitivity sentences
    # (Slepian ceiling, patch bias, stationarity, background sweep, correlated
    # ratio, joint criterion, K-clutter) had a source. An artifact nobody
    # asserts against is a file. This asserts each CLAIM against its artifact;
    # where the digits depend on RNG state the claim is gated, not the digit.
    ("G30", "Every sensitivity claim in Sections V-VI is the number its artifact holds",
     "assert_manuscript_claims.py - S1-S14, the CURRENT claims, not remembered digits",
     [sys.executable, str(SCRIPTS / "assert_manuscript_claims.py")], False),

    # The degeneracy is a property of the computation, not of these data, so it
    # must survive the data being wrong: shuffled, mis-scaled, replaced by
    # noise. The manuscript says so; this breaks the data nine ways and checks.
    ("G31", "The amplitude-CPR ceiling survives shuffled, mis-scaled and random inputs, "
            "and no pixel passes in any case",
     "robustness_gate.py - nine corruptions, crossing within 1e-4, zero passing",
     [sys.executable, str(SCRIPTS / "robustness_gate.py")], False),

    # Three gates were written with numbers and docstrings and never added to
    # this list -- G21, G22 and G29 passed on the days they were written and
    # were never run again by anything. A gate nobody runs is a file. They are
    # wired here under the numbers their scripts already carry.
    ("G21", "Every artifact with a stated reproduction command holds the number "
            "of runs that command produces",
     "assert_artifact_matches_repro_command.py - the artifact is the run METHODS names",
     [sys.executable, str(SCRIPTS / "assert_artifact_matches_repro_command.py")], False),
    ("G22", "Every ENL ceiling is predicted from its own product's own label",
     "assert_ceilings_have_own_label.py - no ceiling borrowed from another product",
     [sys.executable, str(SCRIPTS / "assert_ceilings_have_own_label.py")], False),
    ("G29", "The literature-search record holds the counts the manuscript claims, "
            "and no relevant paper reports any of the three criteria",
     "literature_search_gate.py - counts read from the screening CSV",
     [sys.executable, str(SCRIPTS / "literature_search_gate.py")], False),

    # The number audit compares a printed figure against a STORED value, which
    # is blind to an artifact and a manuscript inheriting the same arithmetic
    # error from the same script. This recomputes all 74 cells of the three
    # closed-form tables from the pipeline's own functions, reading nothing
    # from an artifact, and diffs them against the .tex.
    ("G32", "Every cell of the manuscript's closed-form tables recomputes from "
            "the pipeline's own functions",
     "recompute_manuscript_tables.py - Tables II, III and IV, cell by cell",
     [sys.executable, str(SCRIPTS / "recompute_manuscript_tables.py"),
      "--assert-none-differ"], False),
    ("G33", "The council analyses reproduce their anchors: the joint rule's size at "
            "N = 14, no significant joint selection below N = 79.6, and the F2 null's "
            "86.3 % and 7.76 %",
     "assert_council_anchors.py - recomputed from the stored cells, every arm",
     [sys.executable, str(SCRIPTS / "assert_council_anchors.py")], False),
]

# WHY THE SEQUENCE SKIPS G11 AND G14.
#
# It skips them because they were never allocated. No gate was written under
# either number, no gate was deleted, and nothing was quietly dropped: G12 and
# G13 were named as a pair when the two incidence defects were found, and G15
# was named when the blank production page needed one. The numbers in between
# were simply never used.
#
# This note exists because a gap in a numbered sequence of checks reads like a
# check that used to pass and does not any more, which is the most misleading
# shape a verification table can have. The gap is stated rather than closed:
# renumbering would silently move G12, G13 and G15, which are cited by number in
# METHODS, in docs/testing.md and in the commit history, and a citation that
# resolves to a different gate is worse than a documented gap.
_NEVER_ALLOCATED = ("G11", "G14")
assert not {g[0] for g in GATES} & set(_NEVER_ALLOCATED), (
    "G11/G14 are documented as never allocated; a gate now uses one of them, so "
    "either the note is wrong or the number is")


# ---------------------------------------------------------------------------------------------------------------------
# WHAT EACH GATE NEEDS THAT THE REPOSITORY DOES NOT CONTAIN (V25).
#
# Measured, not remembered: every gate was run on the author's machine with an audit hook logging each file the python
# process opened, and the files that git does not track are listed here, per gate. A gate whose entry has an ABSENT file
# prints REQUIRES LOCAL DATA and is not run; a gate whose entries are all present runs, and a wrong input FAILS it.
# The ISRO products themselves are not in the repository (DATA.md: ISRO keeps the copyright; the PRADAN terms forbid
# redistributing them), so the gates below that read them cannot run in a clone until the author's PRADAN scene is placed
# under data/pradan/raw/ as README.md "Reproducing" describes.
# ---------------------------------------------------------------------------------------------------------------------
_SCENE = "data/pradan/raw/data/calibrated/20200808/ch2_sar_ncxl_20200808t201154198_d_"
_SC_LH = (_SCENE + "sri_xx_cp_lh_d18.tif", "PRADAN scene ch2_sar_ncxl_20200808t201154198 (sri, LH channel)")
_SC_LV = (_SCENE + "sri_xx_cp_lv_d18.tif", "PRADAN scene ch2_sar_ncxl_20200808t201154198 (sri, LV channel)")
_SC_XML = (_SCENE + "sri_xx_cp_xx_d18.xml", "PRADAN scene ch2_sar_ncxl_20200808t201154198 (sri PDS4 label)")
_LOLA_SIDE = ("data/pradan/lola/ldem_frame_25m.provenance.json", "LOLA frame-DEM provenance sidecar (ingest_lola_polar_dem.py)")
_HOR_SIDE = ("data/pradan/lola/horizon_240m.provenance.json", "horizon provenance sidecar (compute_horizon.py)")
_HOR_NPZ = ("data/pradan/lola/horizon_240m.npz", "LOLA horizon product (compute_horizon.py)")
_DEM_NAT = ("data/pradan/native/dem_native.tif", "LOLA DEM on the DFSAR 25 m grid (ingest_lola_polar_dem.py)")
_VALID = ("data/pradan/native/valid_native.tif", "DFSAR valid-amplitude mask (process_real_sar_pipeline.py)")
_BROWSER = (lambda: _find_browser(), "a Chrome or Edge executable (or VERIFY_BROWSER=<path>)")

NEEDS: dict[str, list] = {
    "G1": [_LOLA_SIDE],
    "G2": [_HOR_NPZ, _HOR_SIDE,
           ("data/pradan/lola/illumination/LPSR_75S_120M_201608.IMG", "NASA PDS LOLA PSR product"),
           ("data/pradan/lola/illumination/AVGVISIB_75S_120M_201608.IMG", "NASA PDS LOLA average-visibility product"),
           _SC_LH, _SC_XML],
    "G3": [_HOR_NPZ, _HOR_SIDE, _LOLA_SIDE, _DEM_NAT, _VALID, _SC_LH, _SC_XML],
    "G4": [_HOR_NPZ, _HOR_SIDE, _DEM_NAT, _VALID, _SC_LH, _SC_XML],
    "G5": [("data/pradan/native/cpr_native.tif", "amplitude-CPR raster (process_real_sar_pipeline.py)"),
           ("data/pradan/native/dop_native.tif", "DOP raster (process_real_sar_pipeline.py)"), _VALID],
    "G6b": [("frontend/public/layers/cpr_heatmap.webp", "the author's local 25 m CPR layer (render_layers.py; removed from git in V24)"),
            ("frontend/public/layers/dop_heatmap.webp", "the author's local 25 m DOP layer (render_layers.py; removed from git in V24)")],
    "G7": [("data/pradan/dem/faustini_lola_dem.tif", "sanity_check_sar.py output"),
           ("data/pradan/dfsar/cpr_real.tif", "sanity_check_sar.py output"),
           ("data/pradan/dfsar/dop_real.tif", "sanity_check_sar.py output"),
           ("data/pradan/dfsar/metadata_real.json", "process_real_sar_pipeline.py output"),
           _HOR_NPZ, _HOR_SIDE, _LOLA_SIDE, _DEM_NAT],
    "G8": [_HOR_SIDE, _LOLA_SIDE],
    "G15": [("frontend/node_modules", "installed front-end dependencies (npm install in frontend/)"), _BROWSER],
    "G20": [("data/generality/20200305/data/calibrated/20200305/ch2_sar_ncxl_20200305t114902885_d_sri_xx_cp_lh_d18.tif",
             "PRADAN scene ch2_sar_ncxl_20200305t114902885 (LH)"),
            ("data/generality/20200305/data/calibrated/20200305/ch2_sar_ncxl_20200305t114902885_d_sri_xx_cp_lv_d18.tif",
             "PRADAN scene ch2_sar_ncxl_20200305t114902885 (LV)"), _SC_LH, _SC_LV],
    "G24": [_HOR_SIDE, _LOLA_SIDE],
    "G26": [("data/derived/fig_scene/fig_scene_cache.npz", "binned scene cache for paper/make_fig_scene.py (f2_complex_product.py)")],
    "G27": [(_SCENE + "gri_xx_cp_lh_d18.tif", "PRADAN scene, gri LH"), (_SCENE + "gri_xx_cp_lv_d18.tif", "PRADAN scene, gri LV"),
            (_SCENE + "gri_in_cp_xx_d18.tif", "PRADAN scene, gri incidence"), (_SCENE + "gri_xx_cp_xx_d18.xml", "PRADAN scene, gri label"),
            (_SCENE + "sli_xx_cp_lh_d18.tif", "PRADAN scene, sli LH"), (_SCENE + "sli_xx_cp_lv_d18.tif", "PRADAN scene, sli LV"),
            (_SCENE + "sli_xx_cp_xx_d18.xml", "PRADAN scene, sli label"), (_SCENE + "sri_in_cp_xx_d18.tif", "PRADAN scene, sri incidence"),
            (_SCENE + "sri_ma_cp_xx_d18.tif", "PRADAN scene, sri mask"), _SC_LH, _SC_LV, _SC_XML],
    "G31": [_SC_LH, _SC_LV],
    "G32": [("Claude outputs/grsl/dfsar_detection_limits_submission.tex", "the manuscript source (untracked; see README \"Reproducing\")"),
            ("Claude outputs/grsl/dfsar_detection_limits_supplement.tex", "the supplement source (untracked)")],
}
# G28 (the repository check) decides for itself: its C8b exits 77 when data/local_layers/ is absent. G9, G10, G12, G13, G16-G19,
# G21-G23, G25, G29, G30 and G33 read tracked files only and need nothing; G10 and G19 scan the working tree and read one
# untracked per-cell file when it exists, which is not an input to their claim.


def _find_browser() -> bool:
    import os
    cands = [os.environ.get("VERIFY_BROWSER"),
             "C:/Program Files/Google/Chrome/Application/chrome.exe",
             "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
             f"{os.environ.get('LOCALAPPDATA', '')}/Google/Chrome/Application/chrome.exe",
             "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
             "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
             "/usr/bin/google-chrome", "/usr/bin/chromium"]
    return any(c and Path(c).exists() for c in cands)


def missing_inputs(gid: str) -> list[tuple[str, str]]:
    """The inputs of a gate that are ABSENT on this machine. Presence only: a present file is never excused here."""
    out = []
    for need, what in NEEDS.get(gid, []):
        if callable(need):
            if not need():
                out.append((what, "a tool, not a file"))
        elif not (BASE_DIR / need).exists():
            out.append((need, what))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-slow", action="store_true",
                    help="skip the gates that re-read multi-gigabyte rasters")
    ap.add_argument("--out", default="docs/verification.json")
    args = ap.parse_args()

    print("=" * 78)
    print("VERIFY ALL — every gate, mapped to PRD section 6")
    print("=" * 78)
    print("  This script asserts nothing of its own. Each verdict is produced by")
    print("  the gate that owns it; this only runs them and maps each to the")
    print("  statement it backs.\n")

    rows = []
    for gid, statement, owner, argv, slow in GATES:
        if slow and args.skip_slow:
            print(f"  {gid:>4}  SKIPPED (--skip-slow)   {owner}")
            rows.append({"id": gid, "statement": statement, "gate": owner,
                         "verdict": "SKIPPED", "seconds": 0.0})
            continue
        absent = missing_inputs(gid)
        if absent:
            print(f"  {gid:>4}  REQUIRES LOCAL DATA   {owner}")
            for path, what in absent:
                print(f"          needs {path}  --  {what}")
            rows.append({"id": gid, "statement": statement, "gate": owner, "verdict": REQUIRES_LOCAL_DATA,
                         "seconds": 0.0, "needs": [{"path": a, "what": b} for a, b in absent]})
            continue
        t0 = time.time()
        proc = subprocess.run(argv, cwd=str(BASE_DIR), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        dt = time.time() - t0
        if proc.returncode == 0:
            verdict = "PASS"
        elif proc.returncode == REQUIRES_LOCAL_DATA_RC:
            verdict = REQUIRES_LOCAL_DATA
        else:
            verdict = "FAIL"
        rows.append({"id": gid, "statement": statement, "gate": owner, "verdict": verdict,
                     "returncode": proc.returncode, "seconds": round(dt, 1)})
        print(f"  {gid:>4}  {verdict if verdict != REQUIRES_LOCAL_DATA else 'REQUIRES LOCAL DATA'}  {dt:>6.1f}s   {owner}")
        if verdict == "FAIL":
            tail = (proc.stdout or "").strip().splitlines()[-6:]
            for line in tail:
                print(f"          {line}")
        elif verdict == REQUIRES_LOCAL_DATA:
            said = [l for l in (proc.stdout or "").splitlines() if "REQUIRES LOCAL DATA" in l][-3:]
            rows[-1]["needs"] = [{"path": None, "what": l.strip()} for l in said]
            for line in said:
                print(f"          {line.strip()}")

    print("\n" + "=" * 78)
    _n_prd = _prd_statement_count()
    print(f"PRD SECTION 6 — the {_n_prd} statements the project is done when true")
    print("=" * 78)
    for r in rows:
        mark = {"PASS": "[x]", "FAIL": "[ ] FAILED", "SKIPPED": "[?] not run",
                REQUIRES_LOCAL_DATA: "[~] no input"}[r["verdict"]]
        print(f"  {mark:>11}  {r['id']:>4}  {r['statement']}")
        print(f"               backed by: {r['gate']}")

    failed = [r for r in rows if r["verdict"] == "FAIL"]
    skipped = [r for r in rows if r["verdict"] == "SKIPPED"]
    needs = [r for r in rows if r["verdict"] == REQUIRES_LOCAL_DATA]
    passed = [r for r in rows if r["verdict"] == "PASS"]
    print()
    print(f"  TOTALS  PASS {len(passed)}   REQUIRES LOCAL DATA {len(needs)}   FAIL {len(failed)}"
          + (f"   SKIPPED {len(skipped)}" if skipped else "") + f"   (of {len(rows)} gates)")
    if failed:
        print(f"  NOT DONE — {len(failed)} gate(s) failing: "
              f"{', '.join(r['id'] for r in failed)}")
    if needs:
        print(f"  {len(needs)} gate(s) could NOT RUN here because an input is not in this checkout; they verified nothing "
              "and are UNVERIFIED here, not passed:")
        for r in needs:
            for n in (r.get("needs") or [{"path": None, "what": "see the gate's own message"}]):
                print(f"      {r['id']:>4}  {(n['path'] + '  --  ') if n.get('path') else ''}{n['what']}")
    if skipped:
        print(f"  {len(skipped)} skipped (--skip-slow) and therefore UNVERIFIED, not passed.")
    if not (failed or needs or skipped):
        print(f"  ALL {len(rows)} GATES PASS. Every statement in PRD section 6 is")
        print("  backed by a number produced in this run.")

    doc = {"generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/verify_all.py", "gates": rows,
           "totals": {"pass": len(passed), "requires_local_data": len(needs), "fail": len(failed), "skipped": len(skipped)},
           "all_pass": not failed and not skipped and not needs}
    (BASE_DIR / args.out).write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"\n  wrote {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
