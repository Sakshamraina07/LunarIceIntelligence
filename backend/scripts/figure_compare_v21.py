"""
figure_compare_v21.py -- W5 of the v21 work order: the four main figures as
regenerated in paper/ against the copies in Claude outputs/grsl/.

    python backend/scripts/figure_compare_v21.py

For every figure: byte identity; identity after removing the two metadata
fields matplotlib stamps (/CreationDate, /ModDate) and the document ID; identity
of the decompressed page content streams (what is drawn); the fonts and whether
any is Type 3; and the smallest font size in the page's text operators
(`Tf` size times the text-matrix scale, in points, at the size the PDF is
placed in the manuscript: the page is the placed size, the LaTeX includegraphics
width is 0.49 of the text width and the figures are made at that width, so the
number reported is the drawn size). No rendering, no poppler.
Output: docs/figure_compare_v21.json. Draws nothing.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "figure_compare_v21.json"
FIGS = ["fig_scene.pdf", "fig_cpr_dop.pdf", "fig_joint_power.pdf", "fig_region_design.pdf"]
EXTRA = ["fig_n_sensitivity.pdf", "fig_spec_curve.pdf", "fig_overlap.pdf"]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def streams(b: bytes):
    """Every stream of the PDF, Flate-decompressed where it is Flate (a stream is the bytes between `stream` and
    `endstream`; the pattern must not match the `stream` inside `endstream`)."""
    out = []
    for m in re.finditer(rb"[\r\n]stream\r?\n(.*?)\r?\nendstream", b, re.S):
        raw = m.group(1)
        try:
            out.append(zlib.decompress(raw))
        except zlib.error:
            out.append(raw)
    return out


def normalise(b: bytes) -> bytes:
    b = re.sub(rb"/(CreationDate|ModDate)\s*\(D:[^)]*\)", b"", b)
    b = re.sub(rb"/ID\s*\[[^\]]*\]", b"", b)
    return b


def fonts(b: bytes) -> dict:
    names = set(re.findall(rb"/BaseFont\s*/([A-Za-z0-9+\-_,]+)", b))
    sub = re.findall(rb"/Subtype\s*/(Type3|Type1|TrueType|Type0|CIDFontType2|CIDFontType0)", b)
    # font streams inside object streams are also compressed: search the decompressed text too
    allb = b + b"".join(streams(b))
    names |= set(re.findall(rb"/BaseFont\s*/([A-Za-z0-9+\-_,]+)", allb))
    sub += re.findall(rb"/Subtype\s*/(Type3|Type1|TrueType|Type0|CIDFontType2|CIDFontType0)", allb)
    embedded = len(re.findall(rb"/FontFile[23]?\b", allb))
    return {"base_fonts": sorted(n.decode() for n in names), "subtypes": sorted(set(s.decode() for s in sub)),
            "type3": b"/Type3" in allb, "font_file_streams": embedded}


DOUBLE_COLUMN = {"fig_n_sensitivity.pdf", "fig_spec_curve.pdf", "fig_overlap.pdf"}   # figure*: \textwidth
PRINTED_WIDTH_IN = 0.49 * 7.16   # \includegraphics[width=0.49\textwidth]; IEEEtran journal text width 7.16 in (43 pc), assumed, LaTeX is not installed here


def text_sizes(b: bytes, page_w_pt: float):
    """Smallest and largest drawn text size (pt), from `/F<k> size Tf` operators scaled by the text matrix
    (`a b c d e f Tm`, size*|d|) when matplotlib writes one."""
    sizes = []
    for s in streams(b):
        if b"Tf" not in s or b"xmpmeta" in s:
            continue
        txt = s.decode("latin-1", errors="ignore")
        # matplotlib: `BT /F1 10 Tf 0 0 Td ... ET` with a preceding cm that may scale; take the Tf size times |d| of the last Tm/cm
        scale = 1.0
        for ln in txt.splitlines():
            m = re.match(r"\s*(-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) Tm", ln)
            if m:
                scale = abs(float(m.group(4))) or 1.0
            m = re.search(r"/F\d+-?\d* ([\d.]+) Tf", ln) or re.search(r"/F[\w-]+ ([\d.]+) Tf", ln)
            if m:
                sizes.append(float(m.group(1)) * scale)
    hist = {}
    for z in sizes:
        hist[round(z, 2)] = hist.get(round(z, 2), 0) + 1
    return (min(sizes), max(sizes), len(sizes), dict(sorted(hist.items()))) if sizes else (None, None, 0, {})


def mediabox(b: bytes):
    m = re.search(rb"/MediaBox\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\]", b)
    return [float(x) for x in m.groups()] if m else None


def main() -> int:
    rows = {}
    for f in FIGS + EXTRA:
        p, g = BASE_DIR / "paper" / f, BASE_DIR / "Claude outputs" / "grsl" / f
        if not p.is_file():
            continue
        bp = p.read_bytes()
        r = {"paper_sha256": hashlib.sha256(bp).hexdigest(), "bytes": len(bp), "media_box_pt": mediabox(bp)}
        mb = r["media_box_pt"]
        r["placed_width_in"] = round((mb[2] - mb[0]) / 72.0, 3) if mb else None
        r.update({"fonts": fonts(bp)})
        lo, hi, n, hist = text_sizes(bp, (mb[2] - mb[0]) if mb else 0)
        sc = ((7.0 if f in DOUBLE_COLUMN else PRINTED_WIDTH_IN) / r["placed_width_in"]) if r["placed_width_in"] else None
        r["text_size_pt"] = {"min": lo, "max": hi, "operators": n, "histogram_size_pt_count": hist,
                             "printed_scale": sc, "min_at_printed_size": (lo * sc) if lo and sc else None,
                             "sizes_below_7pt_at_printed_size": {str(k): v for k, v in hist.items() if sc and k * sc < 7.0}}
        if g.is_file():
            bg = g.read_bytes()
            sp, sg = streams(bp), streams(bg)
            r["grsl_sha256"] = hashlib.sha256(bg).hexdigest()
            r["byte_identical"] = bp == bg
            r["identical_without_date_and_id"] = normalise(bp) == normalise(bg)
            sp = [x for x in sp if b"xmpmeta" not in x and b"CreationDate" not in x]
            sg = [x for x in sg if b"xmpmeta" not in x and b"CreationDate" not in x]
            r["content_streams_identical"] = (len(sp) == len(sg)) and all(a == c for a, c in zip(sp, sg))
            r["grsl_media_box_pt"] = mediabox(bg)
            r["fonts_grsl"] = fonts(bg)
            if not r["content_streams_identical"]:
                r["content_stream_count"] = [len(sp), len(sg)]
                diff = [i for i, (a, c) in enumerate(zip(sp, sg)) if a != c]
                r["content_streams_differing"] = diff[:20]
        rows[f] = r
        print(f"  {f}: byte-identical {r.get('byte_identical')}; without dates/ID {r.get('identical_without_date_and_id')}; "
              f"content streams identical {r.get('content_streams_identical')}; Type 3 {r['fonts']['type3']}; "
              f"text {lo}-{hi} pt (x{sc:.3f} printed, min {r['text_size_pt']['min_at_printed_size']:.2f} pt); {r['placed_width_in']} in")
    doc = {"schema": "lunar-ice/figure-compare-v21/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/figure_compare_v21.py", "seed": None, "seed_note": "draws nothing",
           "figures": rows, "run_info": run_info()}
    OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
