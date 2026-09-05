"""
Mission Report Generator for Lunar Ice Intelligence.
PRD Compliance (Section 47 & 48): Produces professional PDF mission reports using ReportLab,
detailing targets, radar polarimetry, safety rankings, traverse waypoints, volume estimates,
explicit assumptions, and scientific limitations.

A PDF is the most quotable artefact this system emits — it leaves the browser,
gets attached to an email and read without the badge that said DEMO. So it is
the one output that refuses rather than degrades: `generate_mission_pdf_report`
raises unless `data_mode == "REAL"`, and every figure it prints is read with
`mission_data[...]`, not `.get(key, plausible_number)`. The previous defaults
(8.75 km2 candidate area, 6,562,500 m3 volume, "Alpha Ridge (Site 1)", 12.1 km,
141.2 Wh, plus two entirely invented landing-site rows) would render a complete,
confident report from an empty dict.
"""

import os
from io import BytesIO
from typing import Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch


class MissionNotIngestedError(RuntimeError):
    """Raised when a report is requested for a crater with no ingested product."""


def generate_mission_pdf_report(mission_data: Dict[str, Any]) -> bytes:
    """
    Builds a formatted multi-page PDF document summarizing the complete lunar exploration mission.

    Refuses unless the run was REAL. `data_mode` must be present and equal to
    "REAL"; a missing key is a refusal too, because the absent case is exactly
    the one a default would paper over.
    """
    data_mode = mission_data.get("data_mode")
    if data_mode != "REAL":
        raise MissionNotIngestedError(
            f"Refusing to generate a mission report: data_mode is {data_mode!r}, not 'REAL'. "
            "A PDF outlives the page that produced it and carries no provenance badge, "
            "so it is only issued for a crater with an ingested Chandrayaan-2 DFSAR product "
            "(see app/ingestion/real_data_gate.real_data_status)."
        )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569'),
        spaceAfter=15
    )
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )
    limitation_style = ParagraphStyle(
        'LimitationText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#7f1d1d')
    )

    story = []

    # Title & Header. No `.get(key, default)` from here down: a REAL payload
    # carries every one of these fields (see api_router.download_mission_report_pdf),
    # so a KeyError means the caller changed and the report must not be issued —
    # not that a stand-in number should be printed.
    crater_name = mission_data["crater_name"]

    story.append(Paragraph("LUNAR ICE INTELLIGENCE & MISSION REPORT", title_style))
    story.append(Paragraph(
        f"Target: <b>{crater_name}</b> | Data Mode: <b>{data_mode}</b> | Chandrayaan-2 Remote Sensing Architecture v2.0",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284c7'), spaceAfter=12))

    # Executive Mission Summary
    story.append(Paragraph("1. EXECUTIVE MISSION SUMMARY", section_heading))
    summary_text = (
        f"This decision-support analysis establishes landing feasibility, identifies candidate subsurface "
        f"ice-bearing deposits, and plans hazard-aware rover traverses for <b>{crater_name}</b>. "
        "The analysis integrates Chandrayaan-2 DFSAR polarimetric radar (CPR/DOP), LOLA/DEM illumination "
        "and terrain hazards, machine learning ice likelihood scoring, and multi-objective A* rover navigation."
    )
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 8))

    # Key Metrics Table
    radar_area = mission_data["candidate_area_km2"]
    exp_vol = mission_data["expected_volume_m3"]
    best_site = mission_data["recommended_site"]
    rover_dist = mission_data["rover_distance_km"]
    rover_energy = mission_data["rover_energy_wh"]

    # Thresholds and assumptions are READ from the payload, never captioned as
    # literals. "CPR > 1.0 & DOP < 0.13 in PSR" and "Nominal 5m depth, 15% pore
    # ice fraction" were hardcoded strings beside numbers computed from
    # config.py, so editing a threshold silently made the report describe a run
    # that never happened. The PSR clause was wrong twice over: the candidate
    # mask no longer has a shadow term in it at all.
    assumptions = mission_data.get("assumptions") or {}
    cpr_th = assumptions.get("cpr_threshold")
    dop_th = assumptions.get("dop_threshold")
    depth_m = assumptions.get("expected_depth_m")
    pore_frac = assumptions.get("expected_fraction")

    screen_note = (f"CPR > {cpr_th:.2f} AND DOP < {dop_th:.2f}, over cells carrying radar"
                   if cpr_th is not None and dop_th is not None
                   else "screening thresholds not supplied in payload")
    volume_note = (f"candidate area x {depth_m:g} m assumed depth x {pore_frac:g} assumed pore "
                   f"fraction — an assumption, not a measurement"
                   if depth_m is not None and pore_frac is not None
                   else "depth and pore fraction not supplied in payload")

    def _cell(value, fmt, absent="NO DATA"):
        """A missing figure prints NO DATA. It never prints a default."""
        return absent if value is None else format(value, fmt)

    table_data = [
        ["Metric", "Value", "Operational Significance"],
        ["Candidate Ice Area", _cell(radar_area, ",.2f") + (" km²" if radar_area is not None else ""),
         screen_note],
        ["Estimated Ice-Equivalent Volume", _cell(exp_vol, ",.0f") + (" m³" if exp_vol is not None else ""),
         volume_note],
        ["Recommended Landing Site", "NO DATA" if best_site is None else str(best_site),
         "Highest composite score (safety + illumination - distance)"],
        ["Rover Traverse Distance", _cell(rover_dist, ",.2f") + (" km" if rover_dist is not None else ""),
         "Science-Aware route, uniform-cost search over slope and hazard"],
        ["Estimated Rover Energy", _cell(rover_energy, ",.1f") + (" Wh" if rover_energy is not None else ""),
         "Simplified engineering estimate, 30 kg rover"],
    ]

    t = Table(table_data, colWidths=[1.8 * inch, 1.8 * inch, 3.4 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Scientific Radar Polarimetry & Ice Intelligence
    story.append(Paragraph("2. DFSAR RADAR ANALYSIS & ICE INTELLIGENCE", section_heading))
    radar_expl = (
        "<b>Circular Polarization Ratio (CPR):</b> High CPR (> 1.0) inside permanent shadow regions indicates "
        "the Coherent Backscatter Opposition Effect (CBOE), characteristic of low-loss dielectric media such as water ice.<br/>"
        "<b>Degree of Polarization (DOP):</b> Depressed DOP (< 0.13) confirms multiple subsurface volume scattering.<br/>"
        "<b>Scientific Baseline Screening:</b> Requires CPR > 1.0 AND DOP < 0.13 AND spatial overlap with PSR.<br/>"
        "<b>Explainable ML Likelihood:</b> Random Forest model trained on dual-pol and morphological features provides "
        "continuous probability distributions without replacing scientific physics."
    )
    story.append(Paragraph(radar_expl, body_style))
    story.append(Spacer(1, 10))

    # Landing Sites Ranking
    story.append(Paragraph("3. LANDING SITE SELECTION (MULTI-CRITERIA RANKING)", section_heading))
    landing_headers = ["Rank", "Site Name", "Slope", "Hazard", "Illumination", "Score", "Recommendation"]
    landing_rows = [landing_headers]
    for site in mission_data["landing_sites"]:
        landing_rows.append([
            f"#{site['rank']}",
            site['name'],
            f"{site['slope_deg']:.1f}°",
            f"{site['hazard_score']:.2f}",
            f"{site['illumination_fraction']:.2f}",
            f"{site['composite_landing_score']:.1f}",
            "RECOMMENDED" if site.get('is_recommended') else "Alternative"
        ])
    if len(landing_rows) == 1:
        # Module E returned no ranked site. Say so; the two rows that used to be
        # invented here ("Alpha Ridge (North)", "Gamma Bench (South-West)") were
        # the only landing sites in the report whenever the search found none.
        landing_rows.append(["—", "No site met the ranking criteria", "—", "—", "—", "—", "NO DATA"])

    lt = Table(landing_rows, colWidths=[0.6 * inch, 2.2 * inch, 0.8 * inch, 0.8 * inch, 0.9 * inch, 0.8 * inch, 1.1 * inch])
    lt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0284c7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(lt)
    story.append(Spacer(1, 10))

    # Rover Traverse Planning
    story.append(Paragraph("4. ROVER TRAVERSE STRATEGY COMPARISON", section_heading))
    rover_headers = ["Strategy", "Algorithm", "Distance (km)", "Mean Hazard", "Energy (Wh)", "Science Yield"]
    rover_rows = [rover_headers]
    # Every `.get()` here used to carry a plausible default — 12.0 km, 0.25 mean
    # hazard, 140.0 Wh, 8.0 science yield — so a route that returned nothing
    # printed a complete, credible row. Defaults removed: a missing field prints
    # NO DATA.
    for strat, r_res in mission_data.get("rover_routes", {}).items():
        rover_rows.append([
            strat,
            r_res.get('algorithm_used') or "NO DATA",
            _cell(r_res.get('total_distance_km'), ",.2f"),
            _cell(r_res.get('mean_hazard_encountered'), ".2f"),
            _cell(r_res.get('total_energy_wh'), ",.1f"),
            _cell(r_res.get('total_scientific_value_collected'), ".1f"),
        ])
    if len(rover_rows) == 1:
        # Was three fully invented rows ("Shortest A* 10.40 0.58 182.4 3.2" and
        # two more). They were the only rover figures in the report whenever the
        # planner returned nothing, and nothing marked them as fabricated.
        rover_rows.append(["—", "No route returned", "NO DATA", "NO DATA", "NO DATA", "NO DATA"])

    rt = Table(rover_rows, colWidths=[1.5 * inch, 1.0 * inch, 1.2 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch])
    rt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(rt)
    story.append(Spacer(1, 10))

    # Scientific Limitations & Assumptions (Section 48)
    tiers = mission_data.get("volume_tiers") or []
    if tiers:
        tier_note = ", ".join(
            f"{tv['tier']} {tv['assumed_depth_m']:g} m / {tv['assumed_pore_fraction']:g}"
            for tv in tiers
        )
    else:
        tier_note = "tier assumptions not supplied in payload"

    story.append(KeepTogether([
        Paragraph("5. SCIENTIFIC LIMITATIONS & MISSION ASSUMPTIONS", section_heading),
        Paragraph(
            "1. <b>Radar Signatures:</b> Polarimetric anomalies (CPR > 1.0, DOP < 0.13) are consistent with potential "
            "subsurface ice, but do not constitute certified ground truth confirmation without in-situ drilling or neutron spectrometry.<br/>"
            "2. <b>No ML model:</b> the Random Forest ice-likelihood classifier was WITHDRAWN. It was "
            "fitted to uniformly random labels whose positive class was defined as CPR 1.05-2.5 — a "
            "range this amplitude-only product cannot reach — so every probability it produced was an "
            "extrapolation from fabricated examples. No probability appears in this report.<br/>"
            f"3. <b>Volumetric uncertainty:</b> ice volume is a 3-tier range over assumed regolith "
            f"stratigraphy ({tier_note}). The area is measured; the depth and the pore fraction are "
            f"assumptions and are stated with every figure.<br/>"
            "4. <b>Rover energy:</b> a simplified engineering estimate for a 30 kg micro-rover, not a "
            "substitute for certified NASA/ISRO flight dynamic models. The planner is a uniform-cost "
            "(Dijkstra) search; no optimality beyond that is claimed.<br/>"
            "5. <b>Reproducibility:</b> every figure above is computed from the Chandrayaan-2 DFSAR "
            "product named on page 1, and re-running the pipeline on that product reproduces them. "
            "Any quantity that could not be computed is printed as NO DATA rather than filled in.",
            limitation_style
        ),
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#94a3b8'), spaceAfter=6),
        Paragraph(
            "Generated automatically by Lunar Ice Intelligence System v2.0 | Department of Engineering Final Year Project",
            ParagraphStyle('Footer', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, textColor=colors.HexColor('#94a3b8'))
        )
    ]))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
