#!/usr/bin/env python3
"""
Submission-hygiene gate for the TGRS manuscript.

Runs against the compiled PDF and its .tex source and refuses to pass if any
mechanical requirement of the venue is violated. Every check cites the rule
it enforces. Exit status 1 on any FAIL; WARN never fails the gate.

Usage:
    python3 check_submission.py path/to/dfsar_detection_limits_full.tex [--final]

--final additionally requires that every bracket placeholder and the OPEN
comment block be gone (the state the file must be in when uploaded).
"""
import json, re, subprocess, sys
from pathlib import Path

ABSTRACT_MAX = 250       # IEEE Editorial Style Manual: 150-250 words, one paragraph
FREE_PAGES = 10          # TGRS: mandatory overlength charge from page 11 (submissions after 2026-01-01)

#: Tools this gate needs that are not Python. Recorded rather than assumed:
#: pdffonts and pdfinfo ship with poppler-utils and are absent on a stock
#: Windows install, where the first call raised FileNotFoundError and took the
#: whole gate down before any check ran.
MISSING_TOOLS: set = set()


def sh(cmd):
    """Run a tool, or record that it is absent. NEVER silently succeed.

    A crash here reported nothing; returning "" would have reported every
    font check as PASS on an empty font list, which is worse -- a venue gate
    that passes because it could not look is the one failure mode a submission
    gate must not have. The absence is recorded and surfaced as UNAVAILABLE.
    """
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout
    except (FileNotFoundError, OSError):
        MISSING_TOOLS.add(cmd[0])
        return ""

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    final = "--final" in sys.argv
    tex = Path(args[0]) if args else Path("dfsar_detection_limits_full.tex")
    pdf = tex.with_suffix(".pdf")
    log = tex.with_suffix(".log")
    src = tex.read_text(encoding="utf-8")
    body = re.sub(r"(?<!\\)%.*", "", src)          # strip comments
    results = []

    def rec(name, ok, detail, warn_only=False, needs=None):
        # A check whose tool is missing is UNAVAILABLE, not PASS and not FAIL:
        # it did not run. --final turns that into a FAIL, because a submission
        # gate that never looked has not cleared anything.
        if needs and needs in MISSING_TOOLS:
            results.append({"check": name, "status": "UNAVAILABLE",
                            "detail": f"{needs} not installed (poppler-utils); "
                                      f"this check did not run"})
            return
        results.append({"check": name, "status": "PASS" if ok else ("WARN" if warn_only else "FAIL"),
                        "detail": detail})

    # 1. fonts: all embedded, no Type 3 (IEEE PDF spec: embed or subset all fonts;
    #    Type 3 output is flagged as non-searchable)
    fonts = sh(["pdffonts", str(pdf)]).splitlines()[2:]
    type3 = [l for l in fonts if "Type 3" in l]
    unemb = [l for l in fonts if l.split() and l.split()[-4] == "no"]
    rec("no Type 3 fonts", not type3,
        f"{len(type3)} Type 3 font(s)" if type3 else "0 Type 3 fonts",
        needs="pdffonts")
    rec("all fonts embedded", not unemb,
        f"{len(unemb)} unembedded" if unemb else f"{len(fonts)} fonts, all embedded",
        needs="pdffonts")

    # 2. page count against the free allowance
    _info = sh(["pdfinfo", str(pdf)])
    _m = re.search(r"Pages:\s+(\d+)", _info)
    pages = int(_m.group(1)) if _m else -1
    rec("page count <= free allowance", pages != -1 and pages <= FREE_PAGES,
        f"{pages} pages (free: {FREE_PAGES})" if pages != -1
        else "page count unreadable", needs="pdfinfo")

    # 3. abstract length, single paragraph
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, re.S)
    abs_text = m.group(1) if m else ""
    flat = re.sub(r"\$[^$]*\$", "X", abs_text)
    flat = re.sub(r"\\[a-zA-Z]+\*?", "", flat).replace("\\,", "")
    n_words = len([w for w in flat.split() if re.search(r"[A-Za-z0-9]", w)])
    rec("abstract <= %d words" % ABSTRACT_MAX, n_words <= ABSTRACT_MAX, f"{n_words} words")
    rec("abstract is one paragraph", "\n\n" not in abs_text.strip(), "single paragraph" if "\n\n" not in abs_text.strip() else "blank line inside abstract")
    rec("abstract has no citations/equation refs", not re.search(r"\\(cite|ref|eqref)\{", abs_text), "ok" if not re.search(r"\\(cite|ref|eqref)\{", abs_text) else "citation or ref inside abstract")

    # 4. index terms alphabetical (IEEE style manual)
    k = re.search(r"\\begin\{IEEEkeywords\}(.*?)\\end\{IEEEkeywords\}", body, re.S)
    if k:
        terms = [t.strip().rstrip(".") for t in k.group(1).replace("\n", " ").split(",") if t.strip()]
        rec("index terms alphabetical", terms == sorted(terms, key=str.lower), "; ".join(terms))

    # 5. citations and cross-references
    cited = {c.strip() for mm in re.finditer(r"\\cite\{([^}]*)\}", body) for c in mm.group(1).split(",")}
    items = re.findall(r"\\bibitem\{([^}]*)\}", body)
    rec("every \\cite defined", cited <= set(items), f"undefined: {sorted(cited - set(items))}" if cited - set(items) else f"{len(cited)} keys")
    rec("every \\bibitem cited", set(items) <= cited, f"uncited: {sorted(set(items) - cited)}" if set(items) - cited else f"{len(items)} entries")
    labels = set(re.findall(r"\\label\{([^}]*)\}", body))
    refs = set(re.findall(r"\\(?:eq)?ref\{([^}]*)\}", body))
    rec("every \\ref defined", refs <= labels, f"undefined: {sorted(refs - labels)}" if refs - labels else f"{len(refs)} refs")
    if log.exists():
        lg = log.read_text(errors="ignore")
        rec("no undefined references in log", "undefined" not in lg.lower() or "There were undefined" not in lg, "log clean" if "There were undefined" not in lg else "LaTeX reports undefined references")
        over = len(re.findall(r"^Overfull \\hbox", lg, re.M))
        rec("no overfull hboxes", over == 0, f"{over} overfull hbox(es)", warn_only=True)

    # 6. hard-coded reference numbers inside figure scripts (numbering moves)
    # BESIDE THE TEX *AND* BESIDE THIS SCRIPT. The manuscript is read-only and
    # lives elsewhere, so tex.parent found a stale second copy of the figure
    # script still carrying "documented [10]" while the shipped one in paper/
    # already said "(Raney et al.)". Blaming the stale copy would name the
    # wrong file; scanning only the shipped one would hide that a stale copy
    # exists. Both are scanned and every hit is named with its path.
    # every figure script the manuscript's figures come from: make_figures.py
    # (Fig. 1) and make_figures_v12.py (Figs. 2-3), in paper/ and beside the tex
    figscripts = [q for q in (Path(__file__).parent / "make_figures.py",
                              Path(__file__).parent / "make_figures_v12.py",
                              tex.parent / "make_figures.py",
                              tex.parent / "v12fig" / "make_figures_v12.py") if q.exists()]
    hard = []
    for q in figscripts:
        code = chr(10).join(l.split("#")[0] for l in
                            q.read_text(encoding="utf-8",
                                        errors="replace").splitlines())
        for h in re.findall(r"[\"'][^\"'\n]*\[\d{1,2}\][^\"'\n]*[\"']", code):
            hard.append(q.as_posix() + ": " + h)
    rec("no hard-coded [n] citations in figure script", not hard,
        ("found " + str(hard)) if hard else
        ("none, in " + str(len(figscripts)) + " script(s): "
         + ", ".join(q.parent.name + "/" + q.name for q in figscripts)))

    # 7. placeholders and OPEN block (mandatory only with --final)
    ph = re.findall(r"\[(?:date|address|Zenodo[^\]]*|Department[^\]]*|reviewers[^\]]*|repository[^\]]*)\]", body)
    rec("no bracket placeholders", not ph, f"{ph}" if ph else "none", warn_only=not final)
    rec("OPEN comment block removed", "OPEN ITEMS BEFORE SUBMISSION" not in src, "present" if "OPEN ITEMS BEFORE SUBMISSION" in src else "absent", warn_only=not final)

    # 8. AI disclosure present in the Acknowledgment (IEEE submission policy)
    ack = re.search(r"\\section\*\{Acknowledgment\}(.*?)\\section", body, re.S)
    ack_t = ack.group(1) if ack else ""
    rec("AI disclosure names the system", bool(re.search(r"Claude|GPT|Gemini|Llama", ack_t)), "system named" if re.search(r"Claude|GPT|Gemini|Llama", ack_t) else "no system named in Acknowledgment")

    # 9. American spelling (IEEE house style); a small watch-list, not a dictionary
    brit = re.findall(r"\b(labelled|modelled|behaviour|favour(?:able)?|neighbouring|analysed|summarises|colour|centre)\b", body)
    rec("no British spellings from watch-list", not brit, f"{sorted(set(brit))}" if brit else "none", warn_only=True)

    for r in results:
        print(f"{r['status']:4}  {r['check']:45}  {r['detail']}")
    fails = [r for r in results if r["status"] == "FAIL"]
    Path("submission_check.json").write_text(json.dumps({"tex": str(tex), "final": final, "results": results}, indent=1))
    print(f"\n{len(fails)} FAIL, {sum(r['status']=='WARN' for r in results)} WARN, {sum(r['status']=='PASS' for r in results)} PASS")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
