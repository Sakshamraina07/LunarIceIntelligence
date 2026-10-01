#!/usr/bin/env python3
"""
Does the public repository actually contain what the paper promises?

The manuscript's Data Availability section says "The analysis code, every
artifact quoted in this paper, the literature-search record, and the
verification gates are in the author's repository". A reviewer may clone it and
check. This script checks it for you, from inside the repo:

  C1  Nothing under data/, and no raster, is tracked by git.
      (ISRO: "users do not have the right to copy, lease or loan the satellite
      data without the prior permission of ISRO/DOS".)
  C2  No source file is excluded by .gitignore. Data must be ignored; code
      must not. This catches the accident where a broad pattern swallows a
      script.
  C3  Every script named in the `generator` field of a docs/*.json artifact
      exists AND is tracked by git. An artifact whose generator is missing is
      an unreproducible number.
  C4  Every path mentioned in README.md and docs/METHODS.md that looks like a
      repo file exists. Catches documentation drifting ahead of the code.
  C5  A LICENSE exists, and a note saying the data is not covered by it.
  C6  No secret is tracked (.env and friends).

Run from the repository root:
    python3 check_repo_complete.py
Exit 0 if clean, 1 otherwise.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

R = []
SOURCE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".json", ".md",
              ".yaml", ".yml", ".toml", ".cfg", ".txt", ".csv", ".sh"}
DATA_EXT = {".tif", ".tiff", ".img", ".IMG", ".h5", ".nc", ".hdf"}
#: Files that are DATA although they have a source-like extension: per-cell values from Chandrayaan-2 products
#: (V23b). They must be gitignored and must NOT be tracked (C1), and are not "source" for C2.
LOCAL_ONLY = ("docs/selected_cells_v21.json",)


def rec(cid, name, ok, detail, warn=False):
    R.append({"id": cid, "check": name,
              "status": "PASS" if ok else ("WARN" if warn else "FAIL"),
              "detail": detail})


def git(*args):
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
        return out.stdout.splitlines()
    except FileNotFoundError:
        return None


def main():
    tracked = git("ls-files")
    if tracked is None:
        print("git not available", file=sys.stderr)
        sys.exit(2)
    tracked_set = set(tracked)
    print(f"{len(tracked_set)} files tracked by git\n")

    # C1 — no data, no rasters, tracked
    bad = [p for p in tracked_set
           if p.startswith("data/") or Path(p).suffix in DATA_EXT or p in LOCAL_ONLY]
    rec("C1", "no ISRO/LOLA data or rasters tracked", not bad,
        f"{len(bad)} offending path(s): {bad[:5]}" if bad else "clean")

    # C2 — no source file ignored
    on_disk = [str(p) for p in Path(".").rglob("*")
               if p.is_file()
               and not str(p).startswith(".git/")
               and "node_modules" not in str(p)
               and "__pycache__" not in str(p)]
    # SEPARATOR-AGNOSTIC. `p.startswith("data/")` never matched on Windows,
    # where rglob yields "data\...", so twenty correctly-ignored ISRO/LOLA files
    # were reported as ignored SOURCE -- a false FAIL on the one check whose
    # whole point is "data must be ignored; code must not".
    # Build output and tool caches are not source either, by that same intent.
    _NOT_SOURCE = ("data/", "frontend/dist/", ".claude/", "Claude outputs/")
    src = [p for p in on_disk if Path(p).suffix in SOURCE_EXT
           and not Path(p).as_posix().startswith(_NOT_SOURCE)
           and Path(p).as_posix() not in LOCAL_ONLY
           and ".pytest_cache/" not in Path(p).as_posix()]
    ignored = set(git("check-ignore", "--no-index", *src) or []) if src else set()
    # .env files are meant to be ignored; exclude them from the complaint
    ignored = {p for p in ignored if ".env" not in Path(p).name}
    rec("C2", "no source file excluded by .gitignore", not ignored,
        f"{len(ignored)} source file(s) ignored: {sorted(ignored)[:5]}"
        if ignored else f"{len(src)} source files, none ignored")

    # C3 — every artifact generator exists and is tracked
    missing_gen, untracked_gen = [], []
    for j in sorted(Path("docs").glob("*.json")) if Path("docs").is_dir() else []:
        try:
            d = json.loads(j.read_text())
        except Exception:
            continue
        # docs/rover_coverage.json is a top-level LIST, so .get() raised and the
        # whole check crashed before reaching C4-C7. Guarded rather than
        # rewritten: an artifact with no dict at its root simply declares no
        # generator, which is a different finding from a broken run.
        if not isinstance(d, dict):
            continue
        g = d.get("generator") or d.get("computed_by") or d.get("generated_by")
        if not g or not g.endswith(".py"):
            continue
        if not Path(g).exists():
            missing_gen.append(f"{j.name} -> {g}")
        elif g not in tracked_set:
            untracked_gen.append(f"{j.name} -> {g}")
    rec("C3a", "every artifact's generator script exists", not missing_gen,
        f"{len(missing_gen)} missing: {missing_gen[:4]}" if missing_gen else "all present")
    rec("C3b", "every generator script is tracked by git", not untracked_gen,
        f"{len(untracked_gen)} untracked: {untracked_gen[:4]}" if untracked_gen else "all tracked")

    # C4 — paths named in the docs actually exist
    named, missing_doc = set(), []
    for doc in ("README.md", "docs/METHODS.md", "docs/viva.md", "docs/testing.md"):
        if not Path(doc).exists():
            continue
        text = Path(doc).read_text(errors="replace")
        for m in re.finditer(r"`([A-Za-z0-9_./-]+\.(?:py|json|csv|md|ts|tsx))`", text):
            p = m.group(1)
            if p.startswith(("http", "//")) or " " in p:
                continue
            named.add(p)
    for p in sorted(named):
        hits = [t for t in tracked_set if t == p or t.endswith("/" + p)]
        if not hits and not Path(p).exists():
            missing_doc.append(p)
    rec("C4", "paths named in README/METHODS exist", not missing_doc,
        f"{len(missing_doc)} of {len(named)} named paths missing: {missing_doc[:6]}"
        if missing_doc else f"all {len(named)} named paths resolve", warn=True)

    # C5 — licence, and a data note
    has_lic = any(Path(n).exists() for n in ("LICENSE", "LICENSE.md", "LICENSE.txt"))
    rec("C5a", "a LICENSE for the code exists", has_lic,
        "present" if has_lic else "absent - add one; without it nobody may legally reuse the code")
    note = any(Path(n).exists() for n in ("DATA.md", "DATA.txt", "docs/DATA.md"))
    rec("C5b", "a note separating code licence from data terms exists", note,
        "present" if note else "absent - add DATA.md so the code licence is not read as covering ISRO data",
        warn=True)

    # C6 — no secrets tracked
    secrets = [p for p in tracked_set
               if Path(p).name.startswith(".env") or Path(p).name in
               {"credentials.json", "secrets.json", "id_rsa"}]
    rec("C6", "no secrets tracked", not secrets,
        f"TRACKED SECRET: {secrets}" if secrets else "clean")

    # C7 - HISTORY. Making a repo public exposes every commit ever made, not
    # just the current tree. A raster committed once and deleted later is still
    # in history and becomes public with it. This is the check people skip.
    hist = git("rev-list", "--objects", "--all")
    if hist is None:
        rec("C7", "no data or secret anywhere in git history", False, "could not read history")
    else:
        paths = [l.split(" ", 1)[1] for l in hist if " " in l]
        hits = sorted({p for p in paths
                       if p.startswith("data/")
                       or Path(p).suffix in DATA_EXT
                       or Path(p).name.startswith(".env")})
        rec("C7", "no data or secret anywhere in git history", not hits,
            (f"{len(hits)} path(s) EVER committed: {hits[:6]}"
             " -- these become public the moment the repo does; rewrite history "
             "(git filter-repo) or start a clean repo before publishing")
            if hits else f"{len(set(paths))} distinct paths in history, none are data or secrets")

    for r in R:
        print(f"{r['status']:4}  {r['id']:4} {r['check']:48s}  {r['detail']}")
    f = sum(x["status"] == "FAIL" for x in R)
    w = sum(x["status"] == "WARN" for x in R)
    print(f"\n{f} FAIL, {w} WARN, {sum(x['status']=='PASS' for x in R)} PASS")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
