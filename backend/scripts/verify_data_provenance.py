#!/usr/bin/env python3
"""
Verify that the Chandrayaan-2 products on disk are the ones the manuscript
claims, and that they are internally coherent.

This does not ask ISRO to vouch for anything. It asks whether the bundle is
self-consistent across representations that a wrong, truncated, edited or
substituted file could not all satisfy at once:

  T1  The ASCII timestamp in the FILENAME equals the label's start_date_time.
  T2  The per-line zero-Doppler epoch times (a different encoding, written by a
      different part of the processor) reproduce the label's observation window,
      to within the label's own millisecond rounding.
  T3  The declared array geometry predicts the file size on disk exactly, at the
      declared bytes per pixel, leaving only TIFF header overhead.
  T4  Every raster the label's manifest declares is actually present.
  T5  21 x azimuth_look_bandwidth reproduces total_processed_azimuth_bandwidth,
      the internal check the manuscript relies on for the look-count argument.
  T6  SHA-256 of every file, recorded so the claim stays checkable forever.
  T7  File modification times, which arrive from the archive's own packaging and
      are reported for the record (informational, never a pass/fail).

Exit 0 if every applicable test passes, 1 otherwise. Writes
docs/data_provenance.json.

Usage:
    python3 verify_data_provenance.py [RAW_DIR] [--out docs/data_provenance.json]
"""
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

STEM = "ch2_sar_ncxl_20200808t201154198"
BYTES_PER_PIXEL = 2          # UnsignedLSB2, per the label's data_type
RESULTS = []


def check(tid, name, ok, detail, info_only=False):
    RESULTS.append({"id": tid, "check": name,
                    "status": "INFO" if info_only else ("PASS" if ok else "FAIL"),
                    "detail": detail})


def tag(xml, name, all_=False):
    hits = re.findall(rf"<[^>]*\b{name}\b[^>]*>(.*?)</[^>]*\b{name}\b[^>]*>", xml, re.S)
    hits = [" ".join(h.split()) for h in hits if h.strip()]
    return hits if all_ else (hits[0] if hits else None)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    raw = Path(args[0]) if args else Path("data/pradan/raw/data/calibrated/20200808")
    out = Path("docs/data_provenance.json")
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])

    label = raw / f"{STEM}_d_sri_xx_cp_xx_d18.xml"
    if not label.exists():
        print(f"label not found: {label}", file=sys.stderr)
        sys.exit(2)
    xml = label.read_text(encoding="utf-8", errors="replace")

    # ---- T1  filename timestamp vs label start_date_time -------------------
    m = re.search(r"(\d{8})t(\d{2})(\d{2})(\d{2})(\d{3})", STEM)
    fn_dt = dt.datetime.strptime(m.group(1), "%Y%m%d").replace(
        hour=int(m.group(2)), minute=int(m.group(3)), second=int(m.group(4)),
        microsecond=int(m.group(5)) * 1000, tzinfo=dt.timezone.utc)
    start = dt.datetime.fromisoformat(tag(xml, "start_date_time").replace("Z", "+00:00"))
    stop = dt.datetime.fromisoformat(tag(xml, "stop_date_time").replace("Z", "+00:00"))
    d1 = (fn_dt - start).total_seconds()
    check("T1", "filename timestamp == label start_date_time", d1 == 0.0,
          f"{fn_dt.isoformat()} vs {start.isoformat()}, delta {d1:+.6f} s")

    # ---- T2  per-line zero-Doppler epoch times vs the label window ----------
    zd = [float(v) for v in re.findall(r"zero_doppler[^>]*>([\d.]+)<", xml)]
    if len(zd) >= 2:
        t0 = dt.datetime.fromtimestamp(min(zd), dt.timezone.utc)
        t1 = dt.datetime.fromtimestamp(max(zd), dt.timezone.utc)
        e0 = (t0 - start).total_seconds()
        e1 = (t1 - stop).total_seconds()
        dur_lab = (stop - start).total_seconds()
        dur_zd = max(zd) - min(zd)
        ok = abs(e0) < 1e-3 and abs(e1) < 1e-3 and abs(dur_lab - dur_zd) < 1e-3
        check("T2", "per-line epoch times reproduce the label window", ok,
              f"start {e0:+.6f} s, stop {e1:+.6f} s, duration {dur_lab:.6f} vs "
              f"{dur_zd:.6f} s (label rounds to ms)")
    else:
        check("T2", "per-line epoch times reproduce the label window", False,
              f"expected 2 zero_doppler fields, found {len(zd)}")

    # ---- T3  declared geometry predicts the file size ----------------------
    lines = {int(v) for v in re.findall(r"<axis_name>Line</axis_name>\s*<elements>(\d+)</elements>", xml)}
    samps = {int(v) for v in re.findall(r"<axis_name>Sample</axis_name>\s*<elements>(\d+)</elements>", xml)}
    if not lines or not samps:                       # fall back to unordered parse
        blocks = re.findall(r"<Axis_Array>(.*?)</Axis_Array>", xml, re.S)
        lines = {int(re.search(r"<elements>(\d+)", b).group(1)) for b in blocks
                 if "Line" in b and re.search(r"<elements>(\d+)", b)}
        samps = {int(re.search(r"<elements>(\d+)", b).group(1)) for b in blocks
                 if "Sample" in b and re.search(r"<elements>(\d+)", b)}
    L, S = max(lines), max(samps)
    for ch in ("lh", "lv"):
        f = raw / f"{STEM}_d_sri_xx_cp_{ch}_d18.tif"
        if not f.exists():
            check("T3", f"declared geometry predicts size ({ch})", False, "file absent")
            continue
        n = f.stat().st_size
        overhead = n - L * S * BYTES_PER_PIXEL
        ok = 0 < overhead < 65536
        check("T3", f"declared geometry predicts size ({ch})", ok,
              f"{L}x{S}x{BYTES_PER_PIXEL} = {L*S*BYTES_PER_PIXEL:,} B; file {n:,} B; "
              f"TIFF overhead {overhead:,} B")

    # ---- T4  every declared raster present ---------------------------------
    declared = sorted(set(re.findall(r"<file_name>(.*?)</file_name>", xml)))
    missing = [d for d in declared if not (raw / d).exists()]
    check("T4", "every raster in the label manifest is present", not missing,
          f"{len(declared)} declared, {len(declared)-len(missing)} present"
          + (f"; MISSING {missing}" if missing else ""))

    # ---- T5  the look-bandwidth identity the manuscript uses ---------------
    alb = tag(xml, "azimuth_look_bandwidth")
    tot = tag(xml, "total_processed_azimuth_bandwidth")
    az = tag(xml, "azimuth_looks")
    if alb and tot and az:
        lhs = int(az) * float(alb)
        ok = abs(lhs - float(tot)) < 1e-3
        check("T5", "azimuth_looks x look_bandwidth == total processed bandwidth", ok,
              f"{az} x {alb} = {lhs:.6f} Hz vs declared {tot} Hz")
    else:
        check("T5", "azimuth_looks x look_bandwidth == total processed bandwidth",
              False, "label fields absent")

    # ---- T6/T7  fingerprints and delivered timestamps ----------------------
    files = {}
    for f in sorted(raw.glob(f"{STEM}*")):
        b = f.read_bytes()
        files[f.name] = {
            "bytes": len(b),
            "sha256": hashlib.sha256(b).hexdigest(),
            "mtime_utc": dt.datetime.fromtimestamp(f.stat().st_mtime, dt.timezone.utc).isoformat(),
        }
    check("T6", "SHA-256 recorded for every file", bool(files), f"{len(files)} files hashed")
    mts = sorted(v["mtime_utc"] for v in files.values())
    check("T7", "delivered file timestamps (informational)", True,
          f"{mts[0]} .. {mts[-1]}" if mts else "none", info_only=True)

    # ---- report ------------------------------------------------------------
    for r in RESULTS:
        print(f"{r['status']:4}  {r['id']}  {r['check']:52s}  {r['detail']}")
    fails = [r for r in RESULTS if r["status"] == "FAIL"]
    print(f"\n{len(fails)} FAIL, {sum(r['status']=='PASS' for r in RESULTS)} PASS, "
          f"{sum(r['status']=='INFO' for r in RESULTS)} INFO")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "schema": "lunar-ice/data-provenance/1",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "generator": "backend/scripts/verify_data_provenance.py",
        "product_stem": STEM,
        "archive_identifier": tag(xml, "logical_identifier"),
        "provider": "ISRO, via ISSDC PRADAN (https://pradan.issdc.gov.in/ch2/)",
        "observation_start_utc": start.isoformat(),
        "observation_stop_utc": stop.isoformat(),
        "observation_duration_s": (stop - start).total_seconds(),
        "label_created": tag(xml, "modification_date"),
        "geometry": {"lines": L, "samples": S, "bytes_per_pixel": BYTES_PER_PIXEL},
        "files": files,
        "terms": {
            "source": "https://pradan.issdc.gov.in/ch2/disclaimer.xhtml",
            "summary": "Open and free of charge for non-profit scientific use. Data "
                       "remains the property of ISRO. No copying, leasing or loaning "
                       "without prior permission of ISRO/DOS. No commercial use.",
            "redistributed_by_this_repository": False,
            "required_acknowledgement":
                "We acknowledge the use of data from the Chandrayaan-II, second lunar "
                "mission of the Indian Space Research Organisation (ISRO), archived at "
                "the Indian Space Science Data Centre (ISSDC).",
        },
        "checks": RESULTS,
    }, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
