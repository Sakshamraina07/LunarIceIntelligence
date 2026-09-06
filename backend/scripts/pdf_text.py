"""
pdf_text.py -- pull the visible text out of a PDF, with no new dependencies.

    python backend/scripts/pdf_text.py docs/evidence/pdf/report.before.pdf

WHY THIS EXISTS
---------------
The gate in `assert_pdf_agrees_with_analysis.py` has to read what the report
actually prints, not what the generator was asked to print. Checking the
generator's inputs would be checking the same assumption twice -- METHODS 0's
second pattern -- so the check reads the rendered bytes.

No pypdf, no pdfminer: nothing new in requirements.txt. ReportLab writes Flate-
compressed content streams containing Helvetica text in `(...) Tj` and
`[(..) n (..)] TJ` operators, both of which are recoverable with `zlib` and the
PDF string-escaping rules from the spec. That is all this parses, and it is all
this project's reports contain -- no embedded fonts, no CID encoding, no
ToUnicode maps.

WHAT IT DOES NOT DO, stated so the gate is not over-trusted: it does not lay text
out. Words come back in content-stream order, which for a table is row-major and
for a paragraph is reading order, but no coordinate is consulted, so it cannot
tell a table cell from a caption. The gate compares NUMBERS, and a number is the
same number wherever on the page it sits.
"""
from __future__ import annotations

import base64
import re
import sys
import zlib
from pathlib import Path

# ── PDF string escapes, from the spec's table of literal-string escapes ──────
_ESCAPES = {
    b'n': b'\n', b'r': b'\r', b't': b'\t', b'b': b'\b', b'f': b'\f',
    b'(': b'(', b')': b')', b'\\': b'\\',
}


def _unescape(raw: bytes) -> str:
    out = bytearray()
    i = 0
    while i < len(raw):
        c = raw[i:i + 1]
        if c == b'\\' and i + 1 < len(raw):
            nxt = raw[i + 1:i + 2]
            if nxt in _ESCAPES:
                out += _ESCAPES[nxt]
                i += 2
                continue
            if nxt.isdigit():                       # \ddd octal
                j = i + 1
                digits = b''
                while j < len(raw) and len(digits) < 3 and raw[j:j + 1].isdigit():
                    digits += raw[j:j + 1]
                    j += 1
                out.append(int(digits, 8) & 0xFF)
                i = j
                continue
            if nxt == b'\n':                        # line continuation
                i += 2
                continue
        out += c
        i += 1
    # ReportLab writes WinAnsi for the base-14 fonts; latin-1 is the right
    # decode for everything this project prints (degree signs, superscripts).
    return out.decode('latin-1', errors='replace')


def _decode(raw: bytes) -> bytes:
    """Undo whatever filter chain the writer used.

    ReportLab's default is `/Filter [/ASCII85Decode /FlateDecode]`, so a plain
    zlib attempt returns nothing -- and, this being the point, returns nothing
    QUIETLY. The first version of this file did exactly that and reported a full
    report as empty text.

    ORDER MATTERS AND IS THE SECOND BUG THIS FUNCTION HAD. The chains are tried
    MOST-DECODED FIRST, not first-plausible-wins, because ASCII85 output is made
    of printable letters and a 3 kB block of it contains the byte pairs "BT" and
    "TJ" by chance. Accepting the undecoded stream on that evidence produced a
    "successful" extraction of 3,156 bytes of noise -- a check that passes on
    garbage, which is worse than one that fails.
    """
    def plausible(b: bytes) -> bool:
        return b"BT" in b and b"ET" in b and (b"Tj" in b or b"TJ" in b)

    body = raw.strip()
    attempts = []
    a85 = body if body.startswith(b"<~") else b"<~" + body
    if not a85.endswith(b"~>"):
        a85 += b"~>"
    un85 = None
    try:
        un85 = base64.a85decode(a85, adobe=True)
    except ValueError:
        pass
    if un85 is not None:
        try:
            attempts.append(zlib.decompress(un85))   # ASCII85 then Flate
        except zlib.error:
            pass
    try:
        attempts.append(zlib.decompress(body))       # Flate alone
    except zlib.error:
        pass
    if un85 is not None:
        attempts.append(un85)                        # ASCII85 alone
    attempts.append(body)                            # no filter

    for cand in attempts:
        if plausible(cand):
            return cand
    return b""


def _streams(data: bytes) -> list[bytes]:
    """Every content stream that decodes to something readable.

    The lookbehind is not decoration: `stream\\r?\\n` also matches the tail of
    `endstream\\n`, so the naive pattern found four "streams" in a two-page
    report and two of them were the cross-reference table.
    """
    out = []
    for m in re.finditer(rb"(?<![A-Za-z])stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        got = _decode(data[start:end])
        if got:
            out.append(got)
    return out


def extract_text(pdf: bytes) -> str:
    """Visible text, in content-stream order, one token per line."""
    parts: list[str] = []
    for st in _streams(pdf):
        # `(...) Tj` and `(...) '` / `(...) "` show one string.
        # `[ (a) -30 (b) ] TJ` shows several with kerning between them; the
        # numbers are horizontal adjustments and are dropped, which is why the
        # words in one TJ array are joined without a space.
        for m in re.finditer(rb'\[(.*?)\]\s*TJ|\((?:\\.|[^\\()])*\)\s*(?:Tj|\'|\")',
                             st, re.S):
            if m.group(1) is not None:
                chunk = ''
                for s in re.finditer(rb'\(((?:\\.|[^\\()])*)\)', m.group(1), re.S):
                    chunk += _unescape(s.group(1))
                parts.append(chunk)
            else:
                s = re.search(rb'\(((?:\\.|[^\\()])*)\)', m.group(0), re.S)
                if s:
                    parts.append(_unescape(s.group(1)))
    return '\n'.join(parts)


def numbers(text: str) -> list[str]:
    """Every numeric literal the report prints, as written.

    Kept as STRINGS, not floats: "0.00" and "0.0" are the same number and a
    different claim about precision, and the gate compares what is printed.
    Thousands separators are stripped so 1,460.68 matches 1460.68.
    """
    out = []
    for m in re.finditer(r'(?<![\w.])(\d[\d,]*(?:\.\d+)?)', text):
        out.append(m.group(1).replace(',', ''))
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    p = Path(sys.argv[1])
    txt = extract_text(p.read_bytes())
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print(txt)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
