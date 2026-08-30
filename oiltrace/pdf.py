"""PDF evidence report (spec §29).

Uses reportlab because it is a single pure-Python dependency, works headless
and has no native binaries. The template is a two-page brief: cover page with
the headline finding, then a details page with jurisdiction, alerts, patrol
tasks, ranked suspects and provenance.
"""
from __future__ import annotations

import io
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, Image)


BRAND = colors.HexColor("#3987e5")
INK = colors.HexColor("#0b0b0b")
INK2 = colors.HexColor("#52514e")
MUTED = colors.HexColor("#898781")
CRITICAL = colors.HexColor("#d03b3b")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("H", parent=ss["Heading2"], fontSize=11,
                          textColor=MUTED, spaceAfter=6, leading=13,
                          fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=10,
                          textColor=INK2, leading=14))
    ss.add(ParagraphStyle("Muted", parent=ss["Normal"], fontSize=8.5,
                          textColor=MUTED, leading=11))
    ss.add(ParagraphStyle("Big", parent=ss["Normal"], fontSize=22,
                          textColor=INK, spaceAfter=2, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Label", parent=ss["Normal"], fontSize=8,
                          textColor=MUTED, fontName="Helvetica-Bold",
                          leading=10, spaceAfter=1))
    return ss


def _kv_table(rows):
    t = Table(rows, colWidths=[5.5 * cm, 10.5 * cm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), INK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e1e0d9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def render(rep, incident_dir):
    """Write `<incident_id>.evidence.pdf` next to the JSON pack; return the path."""
    o = rep["oiltrace"]
    d = rep["detections"][0]
    src = rep["source"]
    jur = o["jurisdiction"]
    iid = o["incident_id"]

    out_path = os.path.join(incident_dir, f"{iid}.evidence.pdf")
    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    ss = _styles()
    story = []

    # ---- cover -----------------------------------------------------------
    story.append(Paragraph("OILTRACE · Investigation Package", ss["Muted"]))
    story.append(Paragraph(iid, ss["Big"]))
    story.append(Paragraph(f"<b>{o['scenario']['name']}</b>- {o['scenario']['subtitle']}",
                           ss["Body"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>SIMULATION</b>- decision-support intelligence. "
                           "Not legal evidence.", ss["Muted"]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Headline finding", ss["H"]))
    lead = rep["suspects"][0] if rep["suspects"] else None
    lead_line = (f"Prime attribution candidate: <b>{lead['name']}</b> "
                 f"(MMSI {lead['mmsi']})- score <b>{lead['score']:.2f}</b>."
                 if lead else "No attribution candidate could be scored.")
    story.append(Paragraph(lead_line, ss["Body"]))
    story.append(Spacer(1, 8))

    story.append(_kv_table([
        ["Detected at",          rep["generated_for"] + " UTC"],
        ["Location",             f"{d['centroid_lonlat'][1]:.4f}°N  "
                                 f"{d['centroid_lonlat'][0]:.4f}°E"],
        ["Extent",               f"{d['area_km2']:.1f} km²  ·  "
                                 f"{d['length_km']:.1f} × {d['width_km']:.1f} km"],
        ["P(oil)",               f"{d['p_oil']:.3f}"],
        ["Bonn class",           rep["characterization"]["bonn_class"]],
        ["Volume estimate",      f"{rep['characterization']['volume_m3']:.0f} m³  "
                                 f"({rep['characterization']['tonnes']:.0f} t)"],
        ["Estimated age",        f"{rep['characterization']['age_best_h']:.1f} h  "
                                 f"({rep['characterization']['confidence']} confidence, "
                                 f"×{rep['characterization']['age_uncertainty_factor']:.1f})"],
        ["Jurisdiction",         f"{jur['name']}  ({jur['marpol_regime']})"],
        ["Nearest coast",        f"{o['nearest_coast']['km']:.0f} km · "
                                 f"{o['nearest_coast']['name']}"],
    ]))
    story.append(Spacer(1, 14))

    # Slick + origin PNGs, if they were rendered
    for fn in ("sar.png", "origin.png"):
        p = os.path.join(incident_dir, fn)
        if os.path.exists(p):
            try:
                story.append(Image(p, width=16 * cm, height=16 * cm,
                                   kind="proportional"))
                story.append(Spacer(1, 6))
                story.append(Paragraph(fn, ss["Muted"]))
                break
            except Exception:
                pass

    story.append(PageBreak())

    # ---- page 2: reconstructed origin, attribution, alerts, patrol -------
    story.append(Paragraph("Reconstructed origin", ss["H"]))
    story.append(_kv_table([
        ["Release start", f"{src['t_start']/3600:+.1f} h before acquisition"],
        ["Duration",      f"{src['duration']/3600:.1f} h"],
        ["Course / speed", f"{src['course_deg']:.0f}° · {src['speed_kn']:.1f} kn"],
        ["Start position", f"{src['start_lat']:.3f}, {src['start_lon']:.3f}"],
        ["Inversion fit (IoU)", f"{src['iou']:.3f}"],
        ["Search dispersion",
         f"{src['search_dispersion']['position_sd_km']:.1f} km · "
         f"{src['search_dispersion']['t_start_sd_h']:.1f} h · "
         f"{src['search_dispersion']['course_sd_deg']:.0f}°"],
    ]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Attribution- ranked candidates", ss["H"]))
    hdr = ["Rank", "Vessel", "MMSI", "Type", "Score", "Top evidence"]
    rows = [hdr]
    for i, s in enumerate(rep["suspects"][:6]):
        ev = s["evidence"][0] if s["evidence"] else ""
        rows.append([str(i+1), s["name"], s["mmsi"], s["type_name"],
                     f"{s['score']:.2f}",
                     Paragraph(ev[:110], ss["Muted"])])
    t = Table(rows, colWidths=[1*cm, 3.7*cm, 2.2*cm, 1.8*cm, 1.3*cm, 6*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f4f0")),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e1e0d9")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Alerts", ss["H"]))
    for a in o["alerts"]:
        clr = CRITICAL if a["severity"] == "CRITICAL" else INK
        story.append(Paragraph(
            f'<font color="{clr.hexval()}"><b>{a["severity"]}</b></font> · '
            f'<b>{a["kind"]}</b>- {a["title"]}<br/>'
            f'<font size=8 color="{MUTED.hexval()}">{a["message"]}</font>',
            ss["Body"]))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 6))
    story.append(Paragraph("Patrol tasking", ss["H"]))
    for pt in o["patrol"]:
        story.append(Paragraph(
            f'<b>{pt["priority"]} · {pt["action"]}</b>- {pt["target"]}<br/>'
            f'<font size=8 color="{MUTED.hexval()}">Asset: {pt["asset_class"]} · '
            f'{pt["lat"]:.3f}, {pt["lon"]:.3f} · r={pt["radius_km"]:.0f} km · '
            f'{pt["eta_hint"]}</font><br/>'
            f'<font size=8>{pt["reason"]}</font>',
            ss["Body"]))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Provenance chain", ss["H"]))
    for i, step in enumerate(o["provenance"]["chain"], 1):
        story.append(Paragraph(f"{i}. {step}", ss["Muted"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "This document is decision-support intelligence. It does not establish "
        "an offence under MARPOL or any national law. Enforcement action "
        "requires corroboration- oil fingerprinting, port state inspection, "
        "chain of custody.", ss["Muted"]))

    doc.build(story)
    return out_path
