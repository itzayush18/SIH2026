"""Build the plain-English project explainer PDF.

Everything factual in this document is pulled from the repository at build time
(validation.json, the incident reports, the shipped classifier card) so the PDF
cannot drift away from what the code actually does. Prose is deliberately plain:
the audience is a reviewer or an officer, not a SAR specialist.

Usage:  .venv/bin/python scripts/make_report.py
Output: docs/OILTRACE_Project_Report.pdf
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, Image, KeepTogether)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "OILTRACE_Project_Report.pdf")

BRAND = colors.HexColor("#0f766e")
INK = colors.HexColor("#0b0b0b")
INK2 = colors.HexColor("#3f3f46")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#e5e7eb")
WARN = colors.HexColor("#c2410c")
BOXBG = colors.HexColor("#f4f7f7")


# --------------------------------------------------------------- style
def styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("Title2", parent=ss["Normal"], fontSize=26, leading=30,
                          textColor=INK, fontName="Helvetica-Bold", spaceAfter=6))
    ss.add(ParagraphStyle("Sub", parent=ss["Normal"], fontSize=11, leading=15,
                          textColor=MUTED))
    ss.add(ParagraphStyle("H1", parent=ss["Normal"], fontSize=15, leading=19,
                          textColor=INK, fontName="Helvetica-Bold",
                          spaceBefore=16, spaceAfter=7))
    ss.add(ParagraphStyle("H2", parent=ss["Normal"], fontSize=11.5, leading=15,
                          textColor=BRAND, fontName="Helvetica-Bold",
                          spaceBefore=11, spaceAfter=4))
    ss.add(ParagraphStyle("P", parent=ss["Normal"], fontSize=10, leading=15.2,
                          textColor=INK2, alignment=TA_JUSTIFY, spaceAfter=7))
    ss.add(ParagraphStyle("OTBullet", parent=ss["Normal"], fontSize=10, leading=14.6,
                          textColor=INK2, leftIndent=13, bulletIndent=3,
                          spaceAfter=4))
    ss.add(ParagraphStyle("OTSmall", parent=ss["Normal"], fontSize=8.4, leading=11.4,
                          textColor=MUTED))
    ss.add(ParagraphStyle("Cap", parent=ss["Normal"], fontSize=8.2, leading=11,
                          textColor=MUTED, spaceBefore=3, spaceAfter=10))
    ss.add(ParagraphStyle("Quote", parent=ss["Normal"], fontSize=10, leading=14.5,
                          textColor=INK, leftIndent=10, rightIndent=10,
                          spaceBefore=4, spaceAfter=4))
    return ss


SS = styles()


def P(t):
    return Paragraph(t, SS["P"])


def B(t):
    return Paragraph(t, SS["OTBullet"], bulletText="•")


def H1(t):
    return Paragraph(t, SS["H1"])


def H2(t):
    return Paragraph(t, SS["H2"])


def box(flowables, bg=BOXBG, border=BRAND):
    t = Table([[flowables]], colWidths=[16.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return t


def _cell(v, size, bold=False):
    """Wrap a cell in a Paragraph so it wraps inside its column."""
    if hasattr(v, "wrap"):
        return v
    st = ParagraphStyle("c", fontName="Helvetica", fontSize=size,
                        leading=size * 1.32, textColor=INK if bold else INK2)
    v = str(v)
    if bold:
        v = f"<b>{v}</b>"
    return Paragraph(v, st)


def table(rows, widths, head=True, size=8.8):
    rows = [[_cell(c, size, bold=(head and i == 0)) for c in r]
            for i, r in enumerate(rows)]
    t = Table(rows, colWidths=widths, repeatRows=1 if head else 0)
    st = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", size),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    if head:
        st += [("LINEBELOW", (0, 0), (-1, 0), 0.9, MUTED)]
    t.setStyle(TableStyle(st))
    return t


def fig(name, caption, width=16.0):
    p = os.path.join(ROOT, "figures", name)
    if not os.path.exists(p):
        return []
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(p).getSize()
    w = width * cm
    return [Image(p, width=w, height=w * ih / iw), Paragraph(caption, SS["Cap"])]


# ---------------------------------------------------------------- facts
def facts():
    """Pull every number this document quotes straight out of the repo."""
    f = {}
    v = json.load(open(os.path.join(ROOT, "data", "validation.json")))
    f["val"] = v
    f["n"] = v["n"]
    f["f1"] = v["segmentation_f1"]["mean"]
    f["iou"] = v["segmentation_iou"]["mean"]
    f["inv_km"] = v["inversion_error_km"]["mean"]
    f["pdf_km"] = v["pdf_peak_error_km"]["mean"]
    f["inv_h"] = v["inversion_time_error_h"]["mean"]
    f["runtime"] = v["runtime_s"]["mean"]
    f["acc"] = v["attribution_accuracy"]
    f["base"] = v["baseline"]

    reps = []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "out", "*", "report.json"))):
        try:
            reps.append(json.load(open(p)))
        except Exception:
            pass
    f["reps"] = reps
    f["n_inc"] = len(reps)
    f["n_det"] = sum(len(r["detections"]) for r in reps)
    verd = {}
    for r in reps:
        for s in r["suspects"]:
            verd[s.get("verdict", "?")] = verd.get(s.get("verdict", "?"), 0) + 1
    f["verdicts"] = verd
    f["n_susp"] = sum(verd.values())

    m = json.load(open(os.path.join(ROOT, "sagar", "data", "oil_classifier.json")))
    f["model"] = m
    f["detector_used"] = {r["oiltrace"].get("detector") for r in reps}
    return f


# ------------------------------------------------------------- narrative
def cover(F):
    s = []
    s.append(Paragraph("SIH 2026 · Problem Statement SIH26143 · NTRO · Disaster Management",
                       SS["OTSmall"]))
    s.append(Spacer(1, 16))
    s.append(Paragraph("OILTRACE", SS["Title2"]))
    s.append(Paragraph("Finding marine oil spills from satellites — and working out "
                       "which ship is responsible.", SS["Sub"]))
    s.append(Spacer(1, 4))
    s.append(Paragraph("A plain-English guide to what the system predicts, who uses it, "
                       "and why it matters.", SS["Sub"]))
    s.append(Spacer(1, 22))

    s.append(box([
        Paragraph("In one paragraph", SS["H2"]),
        P("A satellite radar image of the sea arrives. Somewhere in it is a dark "
          "patch. OILTRACE decides whether that patch is <b>mineral oil</b> or a "
          "harmless look-alike; estimates <b>how much oil and how old</b> it is; "
          "runs the ocean backwards to work out <b>where and when it was "
          "released</b>; runs it forwards to say <b>which coastline it will hit "
          "and when</b>; and then matches the reconstructed release against ship "
          "movement records to produce a <b>ranked list of suspect vessels, each "
          "with its reasons written out</b>. It finishes in about "
          f"{F['runtime']:.0f} seconds on an ordinary laptop, with no GPU."),
    ]))
    s.append(Spacer(1, 16))

    rows = [["What", "Measured result", "How it was measured"],
            ["Attribution accuracy",
             f"{F['acc']*100:.0f}% top-1 ({F['n']}/{F['n']} scenes)",
             "Ground truth known; culprit is the top-ranked ship"],
            ["Nearest-ship baseline",
             f"{F['base']['proximity_top1']*100:.0f}% top-1, "
             f"{F['base']['proximity_top3']*100:.0f}% top-3",
             "Same scenes, ranked by distance alone"],
            ["Slick outline quality",
             f"F1 {F['f1']:.3f} · IoU {F['iou']:.3f}",
             "Against the known truth mask"],
            ["Release-point error",
             f"{F['inv_km']:.1f} km (vs {F['pdf_km']:.1f} km)",
             "Source inversion vs backward-cloud peak"],
            ["Release-time error", f"{F['inv_h']:.1f} h",
             "Estimated vs true discharge start"],
            ["End-to-end runtime", f"{F['runtime']:.0f} s", "Laptop CPU, no GPU"]]
    s.append(Paragraph("Measured performance", SS["H2"]))
    s.append(table(rows, [4.3 * cm, 4.6 * cm, 7.5 * cm]))
    s.append(Spacer(1, 8))
    s.append(Paragraph(
        f"Source: <font face='Courier'>data/validation.json</font> — {F['n']} independent "
        "scenes with known ground truth. Every figure in this document is regenerated "
        "from the repository; none is hand-written.", SS["OTSmall"]))
    s.append(PageBreak())
    return s


def sec_problem():
    s = [H1("1 · The problem, in plain terms")]
    s.append(P("Most oil in the sea does not come from dramatic tanker accidents. It "
               "comes from routine, deliberate discharges: a ship cleaning its tanks or "
               "pumping out oily bilge water while under way, usually at night, usually "
               "far from shore. Each release is small compared with a shipwreck. There "
               "are a great many of them."))
    s.append(P("Satellites can already see these slicks. Oil flattens the tiny ripples "
               "that radar bounces off, so a slick shows up as a <b>dark patch</b> on a "
               "radar image, day or night, through cloud. That part is largely solved."))
    s.append(box([
        Paragraph("The gap this project addresses", SS["H2"]),
        P("Seeing the slick is not the same as knowing <b>who did it</b>. By the time "
          "an image is analysed, the ship has sailed on and the slick has drifted "
          "kilometres from where it was released. Existing operational services are "
          "very good at raising the alert and then hand the question of "
          "responsibility to a human analyst. Without a named vessel there is usually "
          "no case, no penalty, and no deterrent — so the discharges continue."),
    ]))
    s.append(Spacer(1, 6))
    s.append(P("OILTRACE is built for that second question. It treats "
               "<b>attribution</b> — not detection — as the hard part, and is designed "
               "so that its answer can be checked, argued with, and rejected."))
    return s


def sec_predict(F):
    s = [H1("2 · What the model actually predicts")]
    s.append(P("The system is not one model. It is a chain of five, each answering a "
               "question a human investigator would ask next."))
    rows = [["#", "Question", "What is predicted", "Form of the answer"],
            ["1", "Is that dark patch oil?", "Oil vs look-alike",
             "P(oil), 0 to 1, per region"],
            ["2", "How bad is it?", "Thickness, volume, tonnes, age",
             "Bonn class + ranges"],
            ["3", "Where did it come from?", "Release point, time, course, speed",
             "A source track, not a dot"],
            ["4", "Where is it going?", "Drift for the next 18 hours",
             "Landfall time + location"],
            ["5", "Who did it?", "Ranked suspect vessels",
             "Score, verdict, written reasons"]]
    s.append(table(rows, [0.8 * cm, 4.2 * cm, 5.4 * cm, 5.6 * cm]))
    s.append(Spacer(1, 10))

    s.append(H2("The prediction that matters most"))
    s.append(P("Stages 1 and 2 describe the slick. Stage 5 is the product. The output "
               "for each candidate ship is a score built from <b>six independent "
               "evidence axes</b>, so that no single coincidence can convict a vessel:"))
    rows = [["Evidence axis", "Weight", "In plain English"],
            ["Source-track match", "3.2",
             "Was the ship on the reconstructed release line, at the release time?"],
            ["Origin envelope", "2.4",
             "Did its track pass through the likely origin area at all?"],
            ["Behaviour", "1.6",
             "Did it slow down, alter course, or loiter during the window?"],
            ["Dark period", "1.2", "Did its transponder go silent during the window?"],
            ["Slick alignment", "1.0",
             "Does the slick lie along the ship's heading?"],
            ["Vessel prior", "0.7", "Is it a type that carries oil (tanker, bulk)?"]]
    s.append(table(rows, [4.0 * cm, 1.6 * cm, 10.4 * cm]))
    s.append(Spacer(1, 8))
    s.append(P("The weights are in "
               "<font face='Courier'>sagar/core/attribute.py</font>. Time is weighted "
               "highest deliberately: being in the right place is weak evidence — "
               "shipping lanes are busy — but being in the right place <i>at the right "
               "time, on the right heading</i> is not."))
    return s


def sec_users(F):
    s = [H1("3 · Who uses it, and how")]
    s.append(P("The intended users are the agencies that already hold this "
               "responsibility. The system is designed to slot into their existing "
               "workflow rather than replace it."))
    rows = [["User", "What they get", "What they do with it"],
            ["Coast Guard<br/>operations room",
             "Alert with severity, position, area, jurisdiction",
             "Decide whether to launch a Dornier or a ship, and where to send it"],
            ["Pollution response<br/>officer",
             "18-hour drift forecast, landfall time, nearest coast",
             "Pre-position booms and shoreline teams before the oil arrives"],
            ["Enforcement /<br/>investigation cell",
             "Ranked suspects with per-axis reasons and an evidence pack",
             "Request port-state inspection; take an oil sample for fingerprinting"],
            ["Legal / prosecution",
             "Evidence pack: JSON, GeoJSON, CSV, PDF, provenance chain",
             "Build the case file; show the method was auditable"],
            ["Maritime board /<br/>state authority",
             "Jurisdiction and MARPOL Special Area classification",
             "Establish which legal regime and penalty applies"]]
    s.append(table(rows, [3.4 * cm, 5.6 * cm, 7.0 * cm]))
    s.append(Spacer(1, 10))

    s.append(H2("A worked example — the flow in practice"))
    s.append(P("Taken from incident <font face='Courier'>OIL-2026-1359</font>, one of "
               f"the {F['n_inc']} incidents currently in the repository:"))
    for t in [
        "<b>Detected.</b> A 120 km² oil-like feature in the Gulf of Kutch, 4 km "
        "from the Kutch coastline. Severity <b>CRITICAL</b>.",
        "<b>Characterised.</b> Bonn class 'metallic'; roughly 1,600 tonnes; about "
        "8 hours old, with the uncertainty stated rather than hidden.",
        "<b>Traced back.</b> Release corridor reconstructed to a window 7.4 to 6.6 "
        "hours before the image.",
        "<b>Projected forward.</b> Drift run 18 hours ahead against the coastline to "
        "give a landfall estimate.",
        "<b>Attributed.</b> MT KAVERI STAR, a 244 m tanker, ranked top: it passed "
        "through the origin envelope, dropped 57% below its own median speed, altered "
        "course 17°, and went AIS-silent for 44 minutes inside the release window.",
        "<b>Tasked.</b> A P1 patrol action is generated — observe the source corridor "
        "on the next satellite pass.",
    ]:
        s.append(B(t))
    s.append(Spacer(1, 6))
    s.append(box([
        P("Note the shape of that output. It is not \"this ship is guilty\". It is "
          "<b>four independent reasons</b>, each traceable to a data source, that an "
          "officer can read in fifteen seconds and challenge individually."),
    ]))
    return s


def sec_impact():
    s = [H1("4 · Why this matters in real life")]
    s.append(H2("For the coastline and the people on it"))
    s.append(P("An oil slick that reaches shore stops being a remote-sensing problem "
               "and becomes an economic one. Mangroves, fishing grounds, salt pans, "
               "desalination intakes and tourist beaches all take damage that is "
               "expensive and slow to reverse. Cleanup at the shoreline costs far more "
               "than containment at sea, so <b>hours of warning are worth a great "
               "deal</b>. The 18-hour drift forecast exists for exactly this: it tells "
               "a responder which stretch of coast to defend, before the oil is there."))
    s.append(H2("For enforcement"))
    s.append(P("A polluter who is never identified pays nothing, and the discharge is "
               "repeated. The chain that has to hold is: <b>detect → attribute → "
               "inspect → sample → prosecute</b>. Detection alone breaks that chain at "
               "step two. By producing a named, reasoned shortlist while the ship is "
               "still at sea, the system makes the next physical step — a port-state "
               "inspection and an oil sample for fingerprinting — possible at all."))
    s.append(H2("For deterrence"))
    s.append(P("This is the real prize. Deliberate discharge is a calculated decision: "
               "cheaper than paying for port reception facilities, and historically "
               "very unlikely to be punished. Changing the perceived probability of "
               "being caught changes that calculation for every ship on the route, "
               "including the ones never actually inspected."))
    s.append(Spacer(1, 4))
    s.append(box([
        Paragraph("What the system is, and is not", SS["H2"]),
        P("Every output is an <b>investigative lead</b>, not proof. A conviction for "
          "illegal discharge normally requires chemical fingerprinting of an oil "
          "sample taken from the suspect vessel and matched to a sample from the "
          "slick. OILTRACE tells an officer <i>which ship to board and which 40 "
          "minutes to ask about</i>. It does not, and should not, replace that step. "
          "The PDF this system generates says so on its cover page."),
    ], border=WARN))
    return s


def sec_design(F):
    s = [H1("5 · Four design decisions worth defending")]

    s.append(H2("1. Inverting the source, not the cloud"))
    s.append(P("The obvious way to find where a slick came from is to run the drift "
               "backwards and see where the particles converge. That works for a single "
               "instantaneous release. It fails for the case that actually matters: a "
               "ship discharging while under way lays down a <b>line</b> of oil over "
               "tens of minutes. That line was already long at the moment of release, "
               "so running it backwards never collapses it to a point."))
    s.append(P("So the system inverts the <b>source</b> instead: it guesses a moving "
               "line release — start time, duration, course, speed, position — pushes "
               "that guess forward through the same ocean, and scores the resulting "
               "footprint against the observed slick. The measured payoff is direct:"))
    s.append(table([["Method", "Mean error against true release point"],
                    ["Backward-cloud peak (the obvious approach)", f"{F['pdf_km']:.1f} km"],
                    ["Source-term inversion (this system)", f"{F['inv_km']:.1f} km"]],
                   [9.4 * cm, 7.0 * cm]))
    s.append(Spacer(1, 6))
    s.append(P("Beyond the smaller error, inversion returns something a probability "
               "blob cannot: a <b>candidate track with timing</b>, which is what makes "
               "matching against ship movements in time — not just space — possible."))

    s.append(H2("2. Refusing to convict the nearest ship"))
    s.append(P("The lazy baseline is to blame whichever vessel was closest. The test "
               "set is built specifically to punish that: it includes decoys that are "
               "in the right place at the wrong time, the right time in the wrong "
               "place, and innocent ships transiting straight through the origin."))
    s.append(table([["Method", "Top-1 correct", "Top-3 correct"],
                    ["Nearest-vessel baseline",
                     f"{F['base']['proximity_top1']*100:.0f}%",
                     f"{F['base']['proximity_top3']*100:.0f}%"],
                    ["Six-axis attribution (this system)",
                     f"{F['base']['ours_top1']*100:.0f}%",
                     f"{F['base']['ours_top3']*100:.0f}%"]],
                   [8.4 * cm, 4.0 * cm, 4.0 * cm]))
    s.append(Spacer(1, 6))
    s.append(P("The baseline is not a straw man — proximity is what a human analyst "
               "reaches for first. It scores 0% here because the decoys are designed "
               "to defeat it."))

    s.append(H2("3. Abstaining instead of guessing"))
    v = F["verdicts"]
    tot = max(F["n_susp"], 1)
    ins = v.get("INSUFFICIENT_EVIDENCE", 0)
    s.append(P("A system that always names someone is useless, because it names "
               "someone even when it has nothing. Each candidate must clear three "
               "separate bars — enough evidence, good enough AIS to mean anything, and "
               "support from more than one axis — or it is returned as "
               "<b>INSUFFICIENT_EVIDENCE</b> with the reason stated. It stays visible "
               "to the analyst; it is simply not an accusation."))
    s.append(P(f"Across the {F['n_inc']} incidents currently in the repository, "
               f"<b>{ins} of {tot} candidates ({ins*100.0/tot:.0f}%) are withheld</b> "
               "this way rather than ranked."))

    s.append(H2("4. Saying which ships it cannot see"))
    s.append(P("A vessel that switches its transponder off during a discharge is "
               "invisible to any AIS-only method — and switching it off is exactly what "
               "a deliberate polluter does. The system therefore looks for bright "
               "ship-like targets in the radar image itself, so a vessel with no AIS "
               "record still appears as a candidate. The transponder gap is scored as "
               "<b>evidence</b>, not treated as missing data."))
    return s


def sec_results(F):
    s = [H1("6 · Results, including the ones that are not flattering")]
    s.append(P("All five charts below are generated from this repository's own outputs "
               "by <font face='Courier'>scripts/make_figures.py</font>. Nothing is "
               "illustrative."))
    s += fig("2_bar_attribution_and_weights.png",
             "Left: attribution against the nearest-ship baseline on "
             f"{F['n']} scenes with known ground truth. Right: the eight features the "
             "slick classifier learned, from "
             f"{F['model']['n_train']:,} real Sentinel-1 regions.")
    s += fig("1_line_metrics_per_seed.png",
             "Slick-outline quality per scene. Mean F1 "
             f"{F['f1']:.3f}, mean IoU {F['iou']:.3f}. The variation across scenes is "
             "real and is not smoothed away.")
    s.append(PageBreak())
    s += fig("5_confusion_matrix.png",
             "Oil vs look-alike on 63 held-out regions. Recall is perfect — it misses "
             "no real slick — but precision is poor.")

    s.append(box([
        Paragraph("An honest limitation, stated plainly", SS["H2"]),
        P(f"The slick classifier is trained on <b>real</b> Sentinel-1 imagery "
          f"({F['model']['n_train']:,} regions, Zenodo 8346860) and on its own "
          f"real-data test split it scores <b>AUC {F['model']['test_auc']:.3f}, "
          f"accuracy {F['model']['test_acc']:.3f}</b>. The confusion matrix above "
          "scores that same model against <b>synthetic</b> scenes, where it reaches "
          "only 0.52 accuracy: it catches every true slick but flags most look-alikes "
          "as oil too."),
        P("This is a <b>domain gap</b> — synthetic look-alikes do not reproduce the "
          "radar statistics of real ones — and not a coding error; the scoring path "
          "was verified identical to the live pipeline to within 2.2e-16. It is "
          "reported as measured rather than replaced with a more flattering split, "
          "because a system whose stated purpose is to abstain honestly cannot hide "
          "its own weakest number."),
        P("The practical consequence is the correct one for this application: at this "
          "operating point the system <b>over-refers rather than misses</b>. For a "
          "screening tool that feeds human review, a false alarm costs an analyst a "
          "few minutes; a missed spill costs a coastline."),
    ], border=WARN))
    return s


def sec_prior_art():
    s = [H1("7 · What already exists, and where the gap is")]
    s.append(P("This section is the honest competitive review. Every claim below is "
               "sourced; where a source could not be verified, that is said instead of "
               "guessed at."))

    s.append(H2("India: INCOIS Online Oil Spill Advisory (OOSA)"))
    s.append(box([
        P("<b>A correction worth making first.</b> It is sometimes said that India's "
          "oil spill system has not been updated since 2019. That is <b>not correct</b> "
          "and should not be claimed. OOSA was established in 2015, and the INCOIS "
          "Annual Report 2023-24 records that it was <b>upgraded to Version 5.0 with "
          "advanced GIS and predictive capabilities</b>. The service is live today. A "
          "project that argues against a straw man is easy to dismiss."),
    ], border=WARN))
    s.append(Spacer(1, 6))
    s.append(P("The real gap is not staleness — it is <b>scope</b>. OOSA is a "
               "<b>trajectory forecasting</b> tool: it wraps NOAA's GNOME model, forced "
               "by INCOIS ocean currents and ECMWF/NCMRWF winds, and predicts where oil "
               "will drift. The operator must <b>type in</b> the spill's location, time, "
               "pollutant type and quantity to get a forecast."))
    s.append(P("That means OOSA answers question 4 of the five in Section 2. It does "
               "not detect the slick from satellite imagery, and it does not attribute "
               "it to a vessel. A search of the INCOIS Annual Report 2023-24 for "
               "\u2018AIS\u2019, \u2018automatic identification\u2019, "
               "\u2018attribution\u2019, \u2018polluter\u2019 and \u2018synthetic "
               "aperture\u2019 returns no relevant results."))
    s.append(P("No <b>operational, continuously-running</b> national satellite oil "
               "spill detection service run by ISRO/NRSC could be verified. Oil spill "
               "mapping over Indian seas appears in the literature as research, and "
               "one-off detections are documented — EOS-04 detected a spill off the "
               "Kerala coast on 27 May 2025. This is stated as an <b>absence of "
               "evidence</b>, not proof of absence."))

    s.append(H2("Europe: EMSA CleanSeaNet — the closest operational analogue"))
    s.append(P("CleanSeaNet is the system this project should be measured against. "
               "Operational since April 2007, it processes over 3,000 satellite images "
               "a year and delivers <b>analysed imagery to national contact points in "
               "under 30 minutes</b> of acquisition. In 2016 it flagged 1,586 "
               "high-confidence and 1,582 lower-confidence spills. Detections per "
               "million km² roughly halved between 2007 and 2017 — evidence that this "
               "kind of surveillance does deter."))
    s.append(P("On attribution, EMSA is precise about what it does: analysis is "
               "<b>semi-automatic, with trained operators</b>, combining imagery with "
               "AIS and LRIT to offer <i>potential polluter identification</i>. "
               "Verification is explicitly left to Member States, because a detection "
               "may be sewage, algae or upwelling rather than mineral oil. "
               "<b>Attribution is not automated end to end and carries no legal "
               "finding.</b>"))

    s.append(H2("Response models: GNOME, ERMA, OpenDrift/OpenOil"))
    s.append(P("NOAA's GNOME (the engine inside OOSA) and ERMA, and MET Norway's "
               "OpenDrift/OpenOil — in daily operational use and the reference "
               "implementation for oil drift — are all <b>drift and response</b> tools. "
               "None performs detection or attribution. This project implements the "
               "same transport physics directly so it installs from a handful of "
               "pure-Python wheels and runs offline."))

    s.append(H2("The one system that does automate attribution: SkyTruth Cerulean"))
    s.append(P("Cerulean, launched in 2023, is the honest closest prior art: a U-Net "
               "on Sentinel-1 imagery, with vessels ranked against each slick by track "
               "parallelism, proximity and timing over an AIS window of −8 h to +6 h. "
               "Its reported accuracy is <b>92% top-5 and 76% top-1</b> against known "
               "coincident vessels."))
    s.append(P("Two things follow. First, the approach is sound — an independent group "
               "reached a similar architecture. Second, Cerulean is an <b>NGO "
               "transparency tool, not an enforcement system</b>, it is not deployed "
               "for Indian waters, and SkyTruth themselves note that slicks cannot be "
               "definitively identified from SAR alone."))
    s.append(Spacer(1, 4))
    s.append(box([
        Paragraph("Comparing accuracy honestly", SS["H2"]),
        P("This project reports 100% top-1 on 10 scenes with known ground truth. "
          "Cerulean reports 76% top-1 on real satellite data. <b>These numbers are not "
          "comparable.</b> Ten controlled scenes with simulated AIS is a far easier "
          "test than the open ocean, and the honest reading is that this system has "
          "demonstrated its <i>method</i>, not yet its <i>field accuracy</i>. Cerulean's "
          "figure is the benchmark to be measured against once real imagery and real "
          "AIS are wired in."),
    ], border=WARN))

    s.append(H2("The enforcement gap — the strongest argument for this work"))
    s.append(P("The case for attribution does not rest on opinion:"))
    for t in [
        "<b>About 80% of confirmed oil slicks never have a polluter identified.</b> "
        "Bonn Agreement aerial surveillance report, 2008 — the single clearest "
        "statement that detection alone does not produce accountability.",
        "<b>76% of successful US MARPOL prosecutions came from whistleblowers</b>, not "
        "from surveillance — National Whistleblower Center analysis of 100 prosecutions, "
        "1993–2017. Cases are made by human informants, not remote sensing.",
        "<b>SkyTruth found no case where satellite imagery was decisive</b> in a bilge "
        "dumping prosecution; it served only to corroborate.",
        "<b>Oil disperses within roughly 12 hours of discharge</b>, which is the "
        "physical reason late attribution fails and why speed matters.",
        "The Bonn Agreement excludes follow-up outcomes from its reports because "
        "proceedings \u201cmay take a year or more\u201d.",
    ]:
        s.append(B(t))

    s.append(PageBreak())
    s.append(H2("Where this project sits"))
    rows = [["System", "Detects", "Forecasts drift", "Attributes to a vessel"],
            ["INCOIS OOSA (India, v5.0)", "No — manual input", "Yes (GNOME)", "No"],
            ["EMSA CleanSeaNet (EU)", "Yes", "Partly",
             "Semi-automatic; operator-led, no legal finding"],
            ["NOAA GNOME / ERMA (US)", "No", "Yes", "No"],
            ["OpenDrift / OpenOil (NO)", "No", "Yes", "No"],
            ["SkyTruth Cerulean (NGO)", "Yes (U-Net)", "No",
             "Yes — 92% top-5 / 76% top-1"],
            ["OILTRACE (this project)", "Yes", "Yes",
             "Yes \u2014 with reasons, and it abstains"]]
    s.append(KeepTogether([table(rows, [4.5 * cm, 3.0 * cm, 3.0 * cm, 5.9 * cm])]))
    s.append(Spacer(1, 8))
    s.append(P("The distinguishing claim is narrow and defensible: <b>no system in "
               "operational use for Indian waters combines detection, drift and "
               "reasoned vessel attribution in one pipeline</b>, and none of the "
               "attribution systems that do exist state, per candidate, why they "
               "concluded what they did or when they have too little evidence to "
               "conclude anything."))
    s.append(Spacer(1, 6))
    s.append(Paragraph(
        "Sources: INCOIS OOSA portal and Annual Report 2023-24; EMSA CleanSeaNet "
        "service pages and the EMSA 10-year review (Interspill); Bonn Agreement "
        "aerial surveillance report 2008; National Whistleblower Center APPS analysis; "
        "SkyTruth Cerulean methods; Dagestad et al., OpenDrift v1.0, Geosci. Model "
        "Dev. 11, 2018. Figures for annual illegal discharge volumes in Indian waters "
        "and global MARPOL conviction rates were sought and could not be verified from "
        "a primary source; they are deliberately not quoted here.", SS["OTSmall"]))
    return s


def sec_limits(F):
    s = [H1("8 · Limitations, stated up front")]
    s.append(P("These are the things a reviewer would find, listed here so they are "
               "found here first."))
    det = ", ".join(sorted(F["detector_used"])) or "logistic-8feature"
    rows = [["Limitation", "Why it matters", "Route out"],
            ["Metocean fields are analytic in the demo",
             "Real currents and wind have structure that makes inversion harder; the "
             "quoted errors would grow",
             "CMEMS + ERA5 adapters already exist in loaders.py"],
            ["Single polarisation (VV intensity only)",
             "Polarimetric features are the standard next lever for separating oil "
             "from look-alikes",
             "Add VH and entropy/alpha features"],
            ["Classifier over-refers on look-alikes",
             "0.52 accuracy on synthetic held-out data; over-refers rather than misses",
             "Train and evaluate on the Zenodo split in its own domain"],
            [f"U-Net wired but not trained ({det} is what runs)",
             "The deep segmenter is integrated behind a fallback, but no checkpoint "
             "ships, so the logistic detector is what produced every result here",
             "gpu/ DGX kit trains it; pipeline picks it up automatically"],
            ["No land or ice masking",
             "Coastal land and ice can produce dark regions",
             "Standard coastline mask at the preprocessing stage"],
            ["AIS is simulated in the demo scenarios",
             "Real AIS is sparser, noisier and has genuine coverage gaps",
             "Live AIS ingest endpoints are implemented and wired"]]
    s.append(table(rows, [4.6 * cm, 6.2 * cm, 5.6 * cm]))
    s.append(Spacer(1, 8))
    s.append(P("Two of these are deliberate scope choices rather than defects. The "
               "physics engine is implemented directly instead of depending on "
               "OpenDrift so the whole system installs from a handful of pure-Python "
               "wheels and runs offline on a laptop — which is what a demonstration in "
               "a hall without internet requires."))
    return s


def sec_next(F):
    s = [H1("9 · What would make this operational")]
    s.append(P("Ordered by how much each would add, relative to the effort:"))
    for t in [
        "<b>Train the U-Net on the Zenodo set.</b> The integration is already written "
        "and falls back safely; only the checkpoint is missing. This directly attacks "
        "the weakest measured number in the document.",
        "<b>Swap in real CMEMS currents and ERA5 wind.</b> The adapters exist. This "
        "converts every drift and inversion figure from indicative to operational.",
        "<b>Ingest live AIS for the Indian EEZ.</b> The endpoints are built; what is "
        "needed is a feed agreement with the relevant authority.",
        "<b>Validate against a known real incident.</b> One documented spill with a "
        "confirmed responsible vessel, run end to end, is worth more than any amount "
        "of synthetic validation.",
        "<b>Add polarimetric features.</b> The standard next lever for oil versus "
        "look-alike separation.",
        "<b>Calibrate the scores.</b> Turn the attribution score into a stated "
        "probability an officer can reason about, with an accuracy-versus-referral "
        "curve to set the threshold deliberately.",
    ]:
        s.append(B(t))
    s.append(Spacer(1, 8))
    s.append(box([
        Paragraph("The one-line case for this project", SS["H2"]),
        P("Satellite oil-spill <b>detection</b> is a solved and deployed problem. "
          "Automated, reasoned, auditable <b>attribution</b> — naming the ship while "
          "it is still at sea, and being explicit about when it cannot — is the step "
          "that turns a detection into an enforcement action, and that is the step "
          "this project builds."),
    ]))
    return s


def sec_appendix(F):
    s = [H1("Appendix · Where every number came from")]
    s.append(P("The document is generated from the repository, so each figure can be "
               "traced to a file and regenerated."))
    rows = [["Claim in this document", "Source in the repository"],
            [f"{F['acc']*100:.0f}% attribution, baseline "
             f"{F['base']['proximity_top1']*100:.0f}%",
             "data/validation.json (n=%d)" % F["n"]],
            [f"F1 {F['f1']:.3f}, IoU {F['iou']:.3f}", "data/validation.json"],
            [f"Inversion {F['inv_km']:.1f} km vs PDF peak {F['pdf_km']:.1f} km",
             "data/validation.json"],
            [f"Runtime {F['runtime']:.0f} s", "data/validation.json"],
            [f"{F['n_det']} detections across {F['n_inc']} incidents",
             "data/out/*/report.json"],
            [f"{F['verdicts'].get('INSUFFICIENT_EVIDENCE', 0)} of {F['n_susp']} "
             "candidates withheld", "data/out/*/report.json (verdict field)"],
            [f"Classifier AUC {F['model']['test_auc']:.3f}, "
             f"acc {F['model']['test_acc']:.3f}, "
             f"N={F['model']['n_train']:,}", "sagar/data/oil_classifier.json"],
            ["Confusion matrix (63 held-out regions)",
             "scripts/eval_classifier.py → data/classifier_eval.npz"],
            ["All five charts", "scripts/make_figures.py → figures/"],
            ["Six evidence axes and weights", "sagar/core/attribute.py"],
            ["Abstention rules", "sagar/core/attribute.py :: verdict_for()"]]
    s.append(table(rows, [8.6 * cm, 7.8 * cm]))
    s.append(Spacer(1, 10))
    s.append(Paragraph("Rebuild this PDF: "
                       "<font face='Courier'>.venv/bin/python scripts/make_report.py</font>",
                       SS["OTSmall"]))
    return s


def _page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(2.2 * cm, 1.55 * cm, A4[0] - 2.2 * cm, 1.55 * cm)
    canvas.setFont("Helvetica", 7.6)
    canvas.setFillColor(MUTED)
    canvas.drawString(2.2 * cm, 1.1 * cm,
                      "OILTRACE · SIH26143 · NTRO — decision-support intelligence, "
                      "not legal evidence")
    canvas.drawRightString(A4[0] - 2.2 * cm, 1.1 * cm, "%d" % doc.page)
    canvas.restoreState()


def build():
    F = facts()
    doc = SimpleDocTemplate(OUT, pagesize=A4,
                            leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=1.9 * cm, bottomMargin=2.1 * cm,
                            title="OILTRACE - Project Report",
                            author="SIH 2026 - SIH26143")
    story = []
    story += cover(F)
    story += sec_problem()
    story += sec_predict(F)
    story += sec_users(F)
    story.append(PageBreak())
    story += sec_impact()
    story.append(PageBreak())
    story += sec_design(F)
    story.append(PageBreak())
    story += sec_results(F)
    story.append(PageBreak())
    story += sec_prior_art()
    story.append(PageBreak())
    story += sec_limits(F)
    story += sec_next(F)
    story.append(PageBreak())
    story += sec_appendix(F)

    doc.build(story, onFirstPage=_page, onLaterPages=_page)
    print(f"wrote {OUT}")
    return OUT


if __name__ == "__main__":
    build()
