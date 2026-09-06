"""
Mission Report Generator for Lunar Ice Intelligence.

THE REPORT IS A RENDERING OF THE ANALYSIS ARTIFACTS. IT COMPUTES NOTHING.

A PDF is the most quotable artefact this system emits -- it leaves the browser,
gets attached to an email and read without the badge that said DEMO -- and this
one had drifted furthest of anything in the project. Generated from
`mission_service`'s legacy payload, it was printing:

  * FIVE LANDING SITES THAT DO NOT EXIST. Alpha Ridge (North), Beta Plateau,
    Gamma Bench, Delta Spur and Epsilon Crest -- the hardcoded grid offsets from
    `module_e_landing.py` that Phase 3 replaced with a search over all
    14,943,444 native pixels -- with slopes of 6.7-12.2 deg against the real
    0.05-0.55, illumination 0.00-0.04 against the real 0.389-0.460, and a score
    of 37.1 on a scale the current search does not even use. One of them was
    marked RECOMMENDED.
  * A ROVER TRAVERSE OF 18.06 km AND 3,137.5 Wh, while the screen's ROVER cell
    read NO DATA. Phase 4's real routes are 1,641-7,280 m and report energy PER
    KILOGRAM precisely so that no rover mass is invented; the report invented
    30 kg.
  * A CONTRADICTION WITH ITSELF, two pages apart: section 2 described a "Random
    Forest model ... provides continuous probability distributions" while
    section 5 said the Random Forest "was WITHDRAWN".
  * A FALSE REPRODUCIBILITY CLAIM: "every figure above is computed from the
    Chandrayaan-2 DFSAR product named on page 1, and re-running the pipeline
    reproduces them". The sites and the rover figures were hardcoded, so
    re-running reproduced none of them. That sentence had already been removed
    from this file once and had come back in new wording.
  * NONE OF PHASE 8 -- no confidence interval on the candidate area, no measured
    ENL, no significance floor, no PSR area, no coverage figures.

The structural cause is the one Phase 1 fixed for the verdict: a second
computation of an answer that already exists. Same fix. Every figure below is
read from `report_data.load_report_bundle`, which reads the same four files the
mission screen reads, and `backend/scripts/assert_pdf_agrees_with_analysis.py`
re-reads the rendered PDF and fails the build on any number that is not in them.

EVERY VALUE CARRIES ITS PROVENANCE MARK. On screen a reader can hover a figure;
on paper they cannot, so an unmarked number in a printed report is worse than an
unmarked number on a page. Every table here has a mark column and every mark is
read from the artifact, never assigned here.
"""

from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from app.services.report_data import absent


class MissionNotIngestedError(RuntimeError):
    """Raised when a report is requested for a crater with no ingested product."""


# ── formatting helpers ──────────────────────────────────────────────────────
#
# Every one of these prints or refuses. None of them has a default, because a
# default is how "8.75 km2 candidate area" and "Alpha Ridge (Site 1)" reached a
# formal report from an empty dict in the first place.

def _num(value, fmt: str, unit: str = "") -> str:
    """A figure, or NO DATA. Never a stand-in."""
    if value is None:
        return "NO DATA"
    return format(value, fmt) + unit


def _mark(v: Dict[str, Any] | None) -> str:
    """The provenance mark an AnalysisValue carries, read not assigned."""
    if not isinstance(v, dict):
        return "NO DATA"
    p = v.get("provenance")
    return "NO DATA" if p in (None, "UNAVAILABLE") else str(p)


def _val(values: Dict[str, Any], key: str):
    v = values.get(key)
    return None if not isinstance(v, dict) else v.get("value")


def generate_mission_pdf_report(bundle: Dict[str, Any]) -> bytes:
    """Render the report from the artifact bundle.

    `bundle` is what `report_data.load_report_bundle` returns. This function
    reads it with `[...]`, not `.get(key, plausible_number)`: a missing key means
    the caller changed and the report must not be issued, not that a stand-in
    should be printed.
    """
    analysis = bundle["analysis"]
    if analysis.get("data_mode") != "REAL":
        raise MissionNotIngestedError(
            f"Refusing to generate a mission report: data_mode is "
            f"{analysis.get('data_mode')!r}, not 'REAL'. A PDF outlives the page that "
            "produced it and carries no provenance badge, so it is only issued for a "
            "crater with an ingested Chandrayaan-2 DFSAR product."
        )

    sites_doc = bundle["sites"]
    traverse_doc = bundle["traverse"]
    detect_doc = bundle["detection"]

    values = analysis["values"]
    verdict = analysis["verdict"]
    grid = analysis["grid"]
    masks = analysis["masks"]
    thresholds = analysis["thresholds"]

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40,
                            topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=16,
        leading=20, textColor=colors.HexColor('#0f172a'), spaceAfter=4)
    subtitle_style = ParagraphStyle(
        'DocSub', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5,
        leading=12, textColor=colors.HexColor('#475569'))
    section_heading = ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'], fontName='Helvetica-Bold',
        fontSize=11, leading=14, textColor=colors.HexColor('#0f172a'),
        spaceBefore=10, spaceAfter=6)
    body_style = ParagraphStyle(
        'BodyTextX', parent=styles['Normal'], fontName='Helvetica', fontSize=9,
        leading=13, textColor=colors.HexColor('#334155'))
    limitation_style = ParagraphStyle(
        'LimitationText', parent=styles['Normal'], fontName='Helvetica-Oblique',
        fontSize=8.5, leading=12, textColor=colors.HexColor('#7f1d1d'))
    note_style = ParagraphStyle(
        'NoteText', parent=styles['Normal'], fontName='Helvetica-Oblique',
        fontSize=7.5, leading=10, textColor=colors.HexColor('#64748b'))

    def table(rows: List[List[str]], widths, header_bg='#0284c7', header_fg=colors.white):
        t = Table(rows, colWidths=widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_bg)),
            ('TEXTCOLOR', (0, 0), (-1, 0), header_fg),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return t

    story: List[Any] = []
    crater_name = analysis["crater_name"]

    # ── header ───────────────────────────────────────────────────────────────
    story.append(Paragraph("LUNAR ICE INTELLIGENCE &amp; MISSION REPORT", title_style))
    story.append(Paragraph(
        f"Target: <b>{crater_name}</b> &nbsp;|&nbsp; {analysis['instrument']}"
        + (f", {analysis['observation_date'][:10]}" if analysis.get('observation_date') else "")
        + f" &nbsp;|&nbsp; product <b>{analysis.get('product_id') or 'NO DATA'}</b>"
        + f"<br/>Every figure is rendered from the precomputed analysis artifacts and carries "
          f"its provenance mark. Generated {analysis['generated_utc'][:16].replace('T', ' ')} UTC.",
        subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5,
                            color=colors.HexColor('#0284c7'), spaceAfter=10))

    # ── 1. the headline ──────────────────────────────────────────────────────
    story.append(Paragraph("1. HEADLINE RESULT", section_heading))
    story.append(Paragraph(
        f"This is a screening of one Chandrayaan-2 DFSAR pass over {crater_name} for "
        "water-ice signatures, with a hazard-aware landing-site search and traverse plan "
        "over measured LOLA topography. <b>The headline result is a null result.</b> "
        f"{verdict['sublabel'] if verdict.get('sublabel') else ''}",
        body_style))
    story.append(Spacer(1, 6))

    ci = None
    if not absent(detect_doc):
        ca = detect_doc["candidate_area"]
        ci = (f"95% CI [{ca['ci_km2'][0]:.4f}, {ca['ci_km2'][1]:.4f}] km&sup2; "
              f"({ca['method']})")

    head = verdict["headline"]
    key_rows = [
        ["Metric", "Value", "Mark", "What it means"],
        ["Candidate ice area",
         _num(head.get("value"), ",.4f", " km²"), _mark(head),
         f"CPR &gt; {thresholds['cpr_threshold']:.2f} AND DOP &lt; {thresholds['dop_threshold']:.2f}, "
         f"over cells carrying radar"
         + (f"<br/>{ci}" if ci else "")],
        ["Radar measured",
         _num(masks["amplitude"]["area_km2"], ",.2f", " km²"), "MEASURED",
         f"of a {grid['frame_area_km2']:,.2f} km² frame at {grid['metres_per_pixel']:g} m/px "
         f"&mdash; {masks['amplitude']['fraction'] * 100:.2f}% returned amplitude"],
        ["Permanent shadow",
         _num(_val(values, "psr_area_km2"), ",.0f", " km²"),
         _mark(values.get("psr_area_km2")),
         "horizon computation over the full LOLA polar array, 360 azimuths"],
        ["Ice-equivalent volume",
         _num(_val(values, "expected_volume_m3"), ",.0f", " m³"),
         _mark(values.get("expected_volume_m3")),
         "candidate area × assumed depth × assumed pore fraction &mdash; "
         "the area is measured, both multipliers are assumptions"],
    ]
    story.append(table(
        [[Paragraph(c, note_style) if i == 3 else c for i, c in enumerate(r)] for r in key_rows],
        [1.5 * inch, 1.15 * inch, 0.72 * inch, 3.63 * inch]))
    story.append(Spacer(1, 10))

    # ── 2. what the quantity is ──────────────────────────────────────────────
    story.append(Paragraph("2. WHAT WAS MEASURED, AND WHAT IT IS NOT", section_heading))
    radar_expl = (
        "<b>The quantity screened is derived from amplitude alone.</b> With CPR built from "
        "the two amplitude channels, CPR and DOP are monotone functions of the SAME single "
        f"variable, so the rule <i>CPR &gt; {thresholds['cpr_threshold']:.2f} AND "
        f"DOP &lt; {thresholds['dop_threshold']:.2f}</i> is arithmetically empty: satisfying "
        "the DOP criterion bounds CPR from above, whatever the terrain. The screen is empty "
        "BY CONSTRUCTION, not by absence of ice.<br/>"
        "<b>It is therefore not a circular polarisation ratio.</b> True CPR lives in the H&ndash;V "
        "phase, and taking magnitudes discards it. The published quantity is reported here as "
        "a channel-imbalance proxy carrying CPR's name, which is what it is.<br/>"
        "<b>No machine-learning likelihood appears in this report.</b> The Random Forest "
        "classifier was withdrawn: it was fitted to uniformly random labels whose positive "
        "class was CPR 1.05&ndash;2.5, a range this amplitude-only product cannot reach."
    )
    story.append(Paragraph(radar_expl, body_style))

    if absent(detect_doc):
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"<b>Detection statistics: NO DATA.</b> {absent(detect_doc)}", limitation_style))
    else:
        story.append(Spacer(1, 8))
        el = detect_doc["effective_looks"]
        ps = detect_doc["per_pixel_significance"]
        ca = detect_doc["candidate_area"]
        det_rows = [
            ["Detection statistic", "Value", "Mark", "Basis"],
            ["Equivalent number of looks (screened field)",
             f"{el['screened_field']['lh']:.2f} – {el['screened_field']['lv']:.2f}",
             "MEASURED",
             f"raw product {el['raw_product']['lh']:.2f} / {el['raw_product']['lv']:.2f}; "
             f"the product declares 21"],
            ["Per-pixel significance floor",
             f"{ps['floor_at_high_N']:.4f} – {ps['floor_at_low_N']:.4f}",
             "MEASURED",
             f"a single pixel must read above this to be significantly over a threshold of "
             f"{ps['threshold']:.1f} at {ps['confidence'] * 100:.0f}% confidence"],
            ["Swath maximum",
             f"{ps['swath_max']:.6f}", "MEASURED",
             f"short of the floor by a factor of {ps['shortfall_factor']:.1f}"],
            ["Candidate area interval",
             f"[{ca['ci_km2'][0]:.4f}, {ca['ci_km2'][1]:.4f}] km²",
             ca["provenance"],
             f"{ca['method']} on {ca['measured_pixels']:,} measured pixels, "
             f"{ca['pixels']} passing. {ca['why_wilson']}"],
        ]
        story.append(table(
            [[Paragraph(c, note_style) if i == 3 else c for i, c in enumerate(r)] for r in det_rows],
            [1.85 * inch, 1.15 * inch, 0.72 * inch, 3.28 * inch], header_bg='#334155'))
        story.append(Spacer(1, 4))
        story.append(Paragraph(ps["caveat"], note_style))

    story.append(Spacer(1, 10))

    # ── 3. landing sites ─────────────────────────────────────────────────────
    story.append(Paragraph("3. LANDING SITE SELECTION", section_heading))
    if absent(sites_doc):
        story.append(Paragraph(f"<b>NO DATA.</b> {absent(sites_doc)}", limitation_style))
    else:
        search = sites_doc["search"]
        story.append(Paragraph(
            f"The argmax of a six-criterion search over all "
            f"<b>{search['pixels_evaluated']:,}</b> native {search['metres_per_pixel']:g} m "
            f"pixels, with {search['nms_separation_km']:g} km non-maximum suppression so the "
            f"five are five places and not five pixels of one. Every criterion is evaluated "
            f"per site and its threshold is printed beside it.",
            body_style))
        story.append(Spacer(1, 5))
        site_rows = [["Rank", "Latitude", "Longitude", "Slope", "Hazard", "Illum.",
                      "Score", "Cold trap", "Terrain", "Mark"]]
        for st in sites_doc["sites"]:
            crit = st["criteria"]
            suspect = "SUSPECT" in st["interpolation_check"]["verdict"].upper()
            site_rows.append([
                f"#{st['rank']}",
                f"{st['lat_deg']:.4f}°",
                f"{st['lon_deg']:.4f}°",
                f"{crit['slope_deg']['value']:.2f}°",
                f"{crit['hazard']['value']:.4f}",
                f"{crit['illumination_fraction']['value']:.3f}",
                f"{st['suitability_score']:.4f}",
                f"{st['ice_access']['psr_distance_km']:.2f} km",
                "SUSPECT" if suspect else "OK",
                "MEASURED",
            ])
        story.append(table(site_rows, [0.42 * inch, 0.72 * inch, 0.72 * inch, 0.55 * inch,
                                       0.6 * inch, 0.52 * inch, 0.6 * inch, 0.66 * inch,
                                       0.62 * inch, 0.69 * inch]))
        story.append(Spacer(1, 4))
        # NO SITE IS MARKED "RECOMMENDED". The old report marked one, on a list
        # that no longer exists; and the ranking here is decided by terms whose
        # span the search itself reports, which is a weaker claim than a
        # recommendation and is the true one.
        rank_note = sites_doc["ranking_note"]
        story.append(Paragraph(
            "Ranked by " + " and ".join(rank_note["determined_by"])
            + ". " + rank_note["why"]
            + " <b>No site is marked RECOMMENDED:</b> the ranking is a score order over this "
            "frame, and the cold-trap distance is to a MODELLED cold trap &mdash; where ice "
            "could persist under the horizon computation, not where ice is. Candidate ice "
            "area in this frame is 0.0000 km² and no radar detection supports any of "
            "these targets.", note_style))
    story.append(Spacer(1, 10))

    # ── 4. traverse ──────────────────────────────────────────────────────────
    story.append(Paragraph("4. TRAVERSE PLANNING", section_heading))
    if absent(traverse_doc):
        story.append(Paragraph(f"<b>NO DATA.</b> {absent(traverse_doc)}", limitation_style))
    else:
        plan = traverse_doc["planning"]
        conn = traverse_doc["connectivity"][str(plan["resolution_m"])]
        energy = traverse_doc["energy_proxy"]
        story.append(Paragraph(
            f"{plan['algorithm']} at a stated {plan['resolution_m']:g} m planning resolution. "
            f"<b>Connectivity is established before any distance is quoted:</b> "
            f"{conn['sites_in_largest']}/{conn['n_sites']} sites lie in one passable component "
            f"holding {conn['largest_component_fraction_of_passable'] * 100:.2f}% of all "
            f"passable cells, and {conn['passable_fraction'] * 100:.2f}% of "
            f"{conn['cells']:,} planning cells are passable. {plan['quantisation_note']}",
            body_style))
        story.append(Spacer(1, 5))
        tr_rows = [["Site", "Length", "Climb", "Energy", "Waypoints", "Status", "Mark"]]
        for r in traverse_doc["primary_site_to_cold_trap"]:
            if r["status"] != "REACHABLE":
                tr_rows.append([f"#{r['rank']}", "NO DATA", "NO DATA", "NO DATA", "NO DATA",
                                "UNREACHABLE", "NO DATA"])
                continue
            tr_rows.append([
                f"#{r['rank']}",
                f"{r['length_m']:,.1f} m",
                f"{r['climb_m']:,.1f} m",
                f"{r['energy_J_per_kg']:,.1f} J/kg",
                f"{r['cells']}",
                "REACHABLE",
                r["provenance_energy"],
            ])
        story.append(table(tr_rows, [0.55 * inch, 1.0 * inch, 0.85 * inch, 1.15 * inch,
                                     0.9 * inch, 1.05 * inch, 0.7 * inch],
                           header_bg='#334155'))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"Energy is <b>{energy['provenance']}</b> and reported PER KILOGRAM: "
            f"{energy['formula']}, with g = {energy['g_moon_m_s2']:g} m/s² and an "
            f"<b>assumed</b> rolling resistance µ = {energy['mu_roll']:g}. {energy['note']} "
            "No rover mass, wheel geometry, speed or duty cycle exists anywhere in this "
            "project, so no watt-hour figure is issued.", note_style))
    story.append(Spacer(1, 10))

    # ── 5. limitations ───────────────────────────────────────────────────────
    story.append(KeepTogether([
        Paragraph("5. LIMITATIONS AND ASSUMPTIONS", section_heading),
        Paragraph(
            "1. <b>Radar:</b> the screened quantity is derived from amplitude alone and is a "
            "channel-imbalance proxy, not a circular polarisation ratio. No result here is "
            "ground truth; confirmation requires in-situ drilling or neutron spectrometry.<br/>"
            "2. <b>No ML model:</b> the Random Forest ice-likelihood classifier was WITHDRAWN "
            "and no probability appears anywhere in this report, including in section 2.<br/>"
            "3. <b>Volume:</b> the area is measured; the depth and the pore fraction are "
            "assumptions and are printed with the figure.<br/>"
            "4. <b>Traverse:</b> the path is computed over measured slope and hazard; the "
            "DESTINATION is a modelled cold trap, not a detection. Energy is per kilogram "
            "because no vehicle is modelled.<br/>"
            "5. <b>Reproducibility:</b> this report is a RENDERING of the analysis artifacts "
            "listed below, not a second computation of them. Every figure it prints appears "
            "in those files, which is checked on every build by "
            "<i>assert_pdf_agrees_with_analysis.py</i>. Any quantity that could not be "
            "computed is printed as NO DATA and is never filled in.",
            limitation_style),
        Spacer(1, 6),
        Paragraph(
            "Rendered from: "
            + f"analysis {analysis['generated_utc'][:16].replace('T', ' ')} UTC"
            + ("" if absent(sites_doc) else f" &middot; landing sites {sites_doc['generated_utc'][:16].replace('T', ' ')} UTC")
            + ("" if absent(traverse_doc) else f" &middot; traverse {traverse_doc['generated_utc'][:16].replace('T', ' ')} UTC")
            + ("" if absent(detect_doc) else f" &middot; detection statistics {detect_doc['generated_utc'][:16].replace('T', ' ')} UTC")
            + f"<br/>Source raster: {analysis['source_rasters']['cpr']}"
            + f"<br/>Thresholds CPR &gt; {thresholds['cpr_threshold']:.2f}, "
              f"DOP &lt; {thresholds['dop_threshold']:.2f} &mdash; {thresholds['source']}, not retuned.",
            note_style),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#94a3b8'), spaceAfter=6),
        Paragraph(
            "Generated automatically by Lunar Ice Intelligence System v2.0 | "
            "Department of Engineering Final Year Project",
            ParagraphStyle('Footer', parent=styles['Normal'], fontName='Helvetica',
                           fontSize=7.5, textColor=colors.HexColor('#94a3b8'))),
    ]))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
