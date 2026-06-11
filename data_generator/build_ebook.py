"""
Pargo Parcels -- Professional Portfolio Ebook (Dark Theme)
==========================================================
Produces:  ebook/pargo_ebook_portfolio.pdf

Usage:  python build_ebook.py
Needs:  pip install reportlab
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, KeepTogether, Image,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.pdfgen import canvas as pdfcanvas

# ── Colour palette (dark Pargo theme) ─────────────────────────────────────────
BG       = HexColor("#0D1117")   # page background
CARD     = HexColor("#161B22")   # card / table background
BORDER   = HexColor("#30363D")   # subtle borders
YELLOW   = HexColor("#FFC107")   # Pargo yellow accent
YELLOW2  = HexColor("#E6AC00")   # darker yellow for hover/alt
WHITE    = HexColor("#F0F6FC")   # main body text
MUTED    = HexColor("#8B949E")   # secondary text
GREEN    = HexColor("#3FB950")   # positive / success
RED      = HexColor("#F85149")   # negative / danger
BLUE     = HexColor("#58A6FF")   # link / accent blue
LBLUE    = HexColor("#79C0FF")   # lighter blue
ORANGE   = HexColor("#E3B341")   # warning
TEAL     = HexColor("#39D353")   # highlight
DARK_HDR = HexColor("#010409")   # darkest (cover banner)
CARD2    = HexColor("#21262D")   # alt card row

W, H = A4
PLOT = Path("../ml_models/plots")
OUT_DIR = Path("../ebook")


# ── Page template: dark background + footer ───────────────────────────────────
class DarkCanvas(pdfcanvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total):
        self.saveState()
        pg = self.__dict__.get("_pageNumber", 1)
        self.setStrokeColor(BORDER)
        self.setLineWidth(0.5)
        self.line(2.5*cm, 1.5*cm, W - 2.5*cm, 1.5*cm)
        self.setFillColor(MUTED)
        self.setFont("Helvetica", 7)
        self.drawString(2.5*cm, 1.15*cm, "Pargo Parcels  |  Data Warehouse Portfolio")
        self.setFont("Helvetica-Bold", 7)
        self.setFillColor(YELLOW)
        self.drawCentredString(W / 2, 1.15*cm, "Anthony Apollis  |  Analytics & Data Engineer")
        self.setFillColor(MUTED)
        self.setFont("Helvetica", 7)
        self.drawRightString(W - 2.5*cm, 1.15*cm, f"Page {pg} of {total}")
        self.restoreState()


def draw_bg(c, doc):
    c.saveState()
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.restoreState()


# ── Style factory ─────────────────────────────────────────────────────────────
def S():
    return {
        "h1": ParagraphStyle("h1", fontSize=28, textColor=YELLOW,
               fontName="Helvetica-Bold", spaceBefore=0, spaceAfter=8,
               alignment=TA_LEFT, leading=34, backColor=None),
        "h2": ParagraphStyle("h2", fontSize=15, textColor=YELLOW,
               fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=5,
               alignment=TA_LEFT, leading=20),
        "h3": ParagraphStyle("h3", fontSize=11, textColor=WHITE,
               fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4,
               alignment=TA_LEFT),
        "h4": ParagraphStyle("h4", fontSize=9.5, textColor=YELLOW,
               fontName="Helvetica-Bold", spaceBefore=7, spaceAfter=3,
               alignment=TA_LEFT),
        "body": ParagraphStyle("body", fontSize=9.5, textColor=WHITE,
                spaceAfter=6, leading=15, fontName="Helvetica",
                alignment=TA_JUSTIFY),
        "bullet": ParagraphStyle("bullet", fontSize=9.5, textColor=WHITE,
                  spaceAfter=4, leading=14, fontName="Helvetica",
                  leftIndent=14, firstLineIndent=0, alignment=TA_LEFT),
        "code": ParagraphStyle("code", fontSize=8, textColor=LBLUE,
                spaceAfter=4, leading=12, fontName="Courier",
                backColor=CARD, borderPadding=6, alignment=TA_LEFT),
        "caption": ParagraphStyle("caption", fontSize=8, textColor=MUTED,
                   spaceAfter=8, fontName="Helvetica-Oblique",
                   alignment=TA_CENTER),
        "metric_val": ParagraphStyle("mv", fontSize=22, textColor=YELLOW,
                      fontName="Helvetica-Bold", alignment=TA_CENTER,
                      spaceAfter=2),
        "metric_lbl": ParagraphStyle("ml", fontSize=8, textColor=MUTED,
                      fontName="Helvetica", alignment=TA_CENTER, spaceAfter=0),
        "toc": ParagraphStyle("toc", fontSize=10, textColor=WHITE,
               fontName="Helvetica", spaceAfter=4, leading=14),
        "toc_h": ParagraphStyle("toch", fontSize=10, textColor=YELLOW,
                 fontName="Helvetica-Bold", spaceAfter=3, leading=14),
        "tag": ParagraphStyle("tag", fontSize=8, textColor=BG,
               fontName="Helvetica-Bold", alignment=TA_CENTER),
    }


def hr(color=YELLOW, thickness=1.5):
    return HRFlowable(width="100%", thickness=thickness,
                      color=color, spaceAfter=10, spaceBefore=4)


def section_banner(number, title):
    """Full-width dark banner as section header."""
    hdr_s = ParagraphStyle("bh", fontSize=15, textColor=YELLOW,
                           fontName="Helvetica-Bold", alignment=TA_LEFT,
                           leading=20, spaceAfter=0)
    t = Table([[Paragraph(f"{number}. {title}", hdr_s)]],
              colWidths=[15.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), DARK_HDR),
        ("TOPPADDING",    (0,0),(-1,-1), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("LINEBELOW",     (0,0),(-1,-1), 2, YELLOW),
    ]))
    return [t, Spacer(1, 0.3*cm)]


def metric_table(metrics):
    """metrics = [(value, label), ...]"""
    s = S()
    vals = [[Paragraph(v, s["metric_val"]) for v, _ in metrics]]
    lbls = [[Paragraph(l, s["metric_lbl"]) for _, l in metrics]]
    col_w = 15.5 * cm / len(metrics)
    t = Table(vals + lbls, colWidths=[col_w] * len(metrics))
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), CARD),
        ("TOPPADDING",    (0,0),(-1,-1), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
        ("GRID",          (0,0),(-1,-1), 0.5, BORDER),
    ]))
    return t


def two_col_table(rows, col_widths=None):
    s = S()
    if col_widths is None:
        col_widths = [4.5*cm, 11*cm]
    lbl_s = ParagraphStyle("lbl", fontSize=8.5, textColor=YELLOW,
                           fontName="Helvetica-Bold")
    val_s = ParagraphStyle("val", fontSize=8.5, textColor=WHITE,
                           fontName="Helvetica", leading=13)
    data = [[Paragraph(f"{l}", lbl_s), Paragraph(v, val_s)] for l, v in rows]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [CARD, CARD2]),
        ("GRID",          (0,0),(-1,-1), 0.5, BORDER),
    ]))
    return t


def schema_table(headers, rows):
    hdr_s  = ParagraphStyle("th", fontSize=8, fontName="Helvetica-Bold",
                             textColor=BG, alignment=TA_CENTER)
    cell_s = ParagraphStyle("td", fontSize=8, fontName="Helvetica",
                             textColor=WHITE, alignment=TA_LEFT, leading=11)
    table_data = [[Paragraph(h, hdr_s) for h in headers]]
    for row in rows:
        table_data.append([Paragraph(str(c), cell_s) for c in row])
    col_w = 15.5*cm / len(headers)
    t = Table(table_data, colWidths=[col_w]*len(headers))
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  YELLOW),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [CARD, CARD2]),
        ("GRID",          (0,0),(-1,-1), 0.5, BORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    return t


def chart(path, caption, w=15.5*cm, h=7.5*cm):
    """Embed a chart PNG with caption. Returns list of flowables."""
    p = PLOT / path if not str(path).startswith("..") else Path(path)
    items = [Spacer(1, 0.3*cm)]
    if p.exists():
        img = Image(str(p.resolve()), width=w, height=h)
        img.hAlign = "CENTER"
        items.append(img)
    else:
        placeholder = Table([[Paragraph(f"[Chart: {path}]",
            ParagraphStyle("ph", fontSize=9, textColor=MUTED,
                           fontName="Helvetica", alignment=TA_CENTER))]],
            colWidths=[w])
        placeholder.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,-1), CARD),
            ("GRID", (0,0),(-1,-1), 0.5, BORDER),
            ("TOPPADDING", (0,0),(-1,-1), 30),
            ("BOTTOMPADDING", (0,0),(-1,-1), 30),
        ]))
        items.append(placeholder)
    items.append(Paragraph(caption, S()["caption"]))
    return items


def insight_box(why_text, finding_text=None):
    """Yellow-accented callout box: WHY this analysis + KEY FINDING."""
    rows = []
    why_s    = ParagraphStyle("ib_why", fontSize=8.5, textColor=WHITE,
                               fontName="Helvetica", leading=13)
    label_s  = ParagraphStyle("ib_lbl", fontSize=7.5, textColor=YELLOW,
                               fontName="Helvetica-Bold")
    find_s   = ParagraphStyle("ib_fnd", fontSize=8.5, textColor=GREEN,
                               fontName="Helvetica-Bold", leading=13)

    inner = [Paragraph("<b>WHY THIS ANALYSIS</b>", label_s),
             Paragraph(why_text, why_s)]
    if finding_text:
        inner += [Spacer(1, 0.15*cm),
                  Paragraph("<b>KEY FINDING</b>", label_s),
                  Paragraph(finding_text, find_s)]

    box = Table([[inner]], colWidths=[15.5*cm])
    box.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), HexColor("#0D2010")),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ("TOPPADDING",    (0,0),(-1,-1), 8),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LINEBEFORE",    (0,0),(0,-1),  3, YELLOW),
        ("GRID",          (0,0),(-1,-1), 0.3, BORDER),
    ]))
    return [Spacer(1, 0.2*cm), box, Spacer(1, 0.2*cm)]


def skill_tags(tags):
    """Inline skill badge row — shows what skills are demonstrated."""
    tag_s = ParagraphStyle("tg", fontSize=7, textColor=BG,
                            fontName="Helvetica-Bold", alignment=TA_CENTER)
    cells = [Paragraph(t, tag_s) for t in tags]
    t = Table([cells], colWidths=[15.5*cm / len(tags)] * len(tags))
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), YELLOW),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("GRID",          (0,0),(-1,-1), 1, BG),
    ]))
    return [t, Spacer(1, 0.2*cm)]


# ─────────────────────────────────────────────────────────────────────────────
# COVER
# ─────────────────────────────────────────────────────────────────────────────
def cover(s):
    e = []
    e.append(Spacer(1, 2.5*cm))

    # Logo image
    logo_path = Path("../ml_models/plots/pargo_logo.png")
    if logo_path.exists():
        logo = Image(str(logo_path.resolve()), width=8*cm, height=2.2*cm)
        logo.hAlign = "LEFT"
        e.append(logo)
        e.append(Spacer(1, 0.4*cm))
    e.append(HRFlowable(width="100%", thickness=3, color=YELLOW, spaceAfter=30))

    # Title
    title_s = ParagraphStyle("ct", fontSize=42, textColor=WHITE,
                              fontName="Helvetica-Bold", alignment=TA_LEFT,
                              spaceAfter=12, leading=50)
    e.append(Paragraph("Data Warehouse\nPortfolio", title_s))
    e.append(Paragraph(
        "End-to-end analytics platform covering data engineering, dimensional "
        "modelling, machine learning, and business intelligence for South "
        "Africa's leading parcel pickup network.",
        ParagraphStyle("cs", fontSize=12, textColor=MUTED, fontName="Helvetica",
                       alignment=TA_LEFT, spaceAfter=36, leading=18)))

    # Stat cards
    stats = [["30.2M", "152M+", "36", "15"],
             ["Parcels", "Tracking Events", "Months", "ML Models"]]
    t = Table(stats, colWidths=[3.875*cm]*4)
    t.setStyle(TableStyle([
        ("FONTNAME",    (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0),(-1,0), 22),
        ("TEXTCOLOR",   (0,0),(-1,0), YELLOW),
        ("FONTNAME",    (0,1),(-1,1), "Helvetica"),
        ("FONTSIZE",    (0,1),(-1,1), 9),
        ("TEXTCOLOR",   (0,1),(-1,1), MUTED),
        ("ALIGN",       (0,0),(-1,-1), "CENTER"),
        ("BACKGROUND",  (0,0),(-1,-1), CARD),
        ("TOPPADDING",  (0,0),(-1,-1), 14),
        ("BOTTOMPADDING",(0,0),(-1,-1), 14),
        ("GRID",        (0,0),(-1,-1), 0.5, BORDER),
    ]))
    e.append(t)
    e.append(Spacer(1, 1.8*cm))
    e.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=14))
    e.append(Paragraph(
        "Technology Stack:  Snowflake DW  |  PostgreSQL  |  DBT  |  Python  |  XGBoost  |  LightGBM  |  Snowpark ML",
        ParagraphStyle("stack", fontSize=8.5, textColor=MUTED, fontName="Helvetica", alignment=TA_LEFT, spaceAfter=4)))
    e.append(Paragraph(
        "Coverage:  South Africa  |  9 Provinces  |  July 2023 – June 2026",
        ParagraphStyle("cov", fontSize=8.5, textColor=MUTED, fontName="Helvetica", alignment=TA_LEFT, spaceAfter=16)))
    e.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=8))
    e.append(Paragraph(
        "Anthony Apollis  |  Analytics &amp; Data Engineer",
        ParagraphStyle("author", fontSize=10, textColor=YELLOW, fontName="Helvetica-Bold",
                       alignment=TA_LEFT, spaceAfter=2)))
    e.append(PageBreak())
    return e


# ─────────────────────────────────────────────────────────────────────────────
# TABLE OF CONTENTS
# ─────────────────────────────────────────────────────────────────────────────
def toc(s):
    e = []
    e.append(Paragraph("Table of Contents", s["h1"]))
    e.append(hr())
    sections = [
        ("1", "Project Overview & Business Context",           "3"),
        ("2", "Data Architecture & Entity Relationship Diagram","5"),
        ("3", "Dimensional Model: Tables & Schema",            "7"),
        ("4", "DBT Transformation Layer",                      "12"),
        ("5", "Machine Learning Models",                       "14"),
        ("6", "Customer Lifetime Value Analysis",              "20"),
        ("7", "Geographical Analysis by Province",             "23"),
        ("8", "Data Platform: Snowflake & PostgreSQL",         "26"),
        ("9", "Snowflake Automation: Tasks & Alerts",          "28"),
        ("10","Key Business Insights & Findings",              "29"),
    ]
    for num, title, pg in sections:
        row = Table([[
            Paragraph(f"<b>{num}.</b>", s["toc_h"]),
            Paragraph(title, s["toc"]),
            Paragraph(pg, ParagraphStyle("pg", fontSize=9.5, textColor=MUTED,
                fontName="Helvetica", alignment=TA_RIGHT))]],
            colWidths=[1.2*cm, 12.5*cm, 1.8*cm])
        row.setStyle(TableStyle([
            ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
            ("TOPPADDING",   (0,0),(-1,-1), 6),
            ("BOTTOMPADDING",(0,0),(-1,-1), 6),
            ("LINEBELOW",    (0,0),(-1,-1), 0.3, BORDER),
        ]))
        e.append(row)
    e.append(PageBreak())
    return e


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
def sec_overview(s):
    e = []
    e += section_banner("1", "Project Overview & Business Context")
    e.append(Paragraph("About Pargo", s["h3"]))
    e.append(Paragraph(
        "Pargo is South Africa's leading parcel pickup network, enabling e-commerce "
        "retailers and consumers to send, receive, and return parcels through a nationwide "
        "network of over 4,000 pickup points (PUDOs) located in convenience stores, petrol "
        "stations, and retail outlets. Operating across all nine provinces, Pargo bridges "
        "the gap between online retail and the practical realities of last-mile delivery "
        "in South Africa, where home delivery is often unreliable or uneconomical.", s["body"]))
    e.append(Paragraph(
        "This portfolio demonstrates a production-grade data warehouse platform built to "
        "power operational analytics, business intelligence, and machine learning for "
        "Pargo's logistics network. The platform ingests 36 months of synthetic but "
        "structurally authentic parcel lifecycle data, transforming raw events into curated "
        "analytical models.", s["body"]))

    e.append(Paragraph("Business Objectives", s["h3"]))
    e.append(two_col_table([
        ("Operational Visibility",
         "Real-time and historical insight into parcel throughput, dwell times, SLA compliance, "
         "and exception rates across all pickup points and couriers."),
        ("RTS Risk Reduction",
         "Predict which parcels are likely to be Returned to Sender before it happens, enabling "
         "proactive intervention to improve delivery success rates."),
        ("Customer Intelligence",
         "Understand customer lifetime value, segment customers by behaviour, and identify churn "
         "risk before customers disengage."),
        ("Demand Forecasting",
         "Forecast parcel volumes 1-6 months ahead to support staffing, capacity planning, and "
         "courier contract negotiations."),
        ("Courier Performance",
         "Score and rank courier agents and logistics partners on reliability, speed, and exception "
         "rates to drive SLA accountability."),
        ("Retailer Scorecard",
         "Provide retail partners with performance benchmarks covering dispatch quality, packaging "
         "compliance, and return rates."),
    ], [4*cm, 11.5*cm]))

    e.append(Paragraph("Data Scope", s["h3"]))
    e.append(metric_table([
        ("30.2M",   "Total Parcels"),
        ("152.8M",  "Tracking Events"),
        ("10M",     "Customers"),
        ("36 mths", "Data Window"),
        ("4,000+",  "Pickup Points"),
        ("150",     "Retail Partners"),
    ]))
    e.append(Spacer(1, 0.3*cm))
    e.append(Paragraph(
        "The dataset spans July 2023 to June 2026 and covers the full parcel lifecycle: "
        "order creation, dispatch, in-transit scan events, pickup point arrival, customer "
        "collection, and returns. Each province is represented in proportion to South "
        "Africa's population distribution, with Gauteng (35%), Western Cape (20%), and "
        "KwaZulu-Natal (18%) forming the majority of parcel volume.", s["body"]))

    e.append(Paragraph("Technical Architecture Summary", s["h3"]))
    e.append(two_col_table([
        ("Ingestion",   "Python bulk loader using Snowflake PUT + COPY INTO with parquet files "
                        "organised by year/month partitions. Parallel batch upload achieves ~1M rows/min."),
        ("Warehouse",   "Snowflake cloud data warehouse (af-south-1, AWS) with RAW / STAGING / "
                        "MARTS / ML_FEATURES schemas. 8 tables, 182M+ rows total."),
        ("Transform",   "DBT manages all SQL transformations from raw tables through staging views "
                        "to analytical mart tables and ML feature tables."),
        ("ML / AI",     "Python scikit-learn, XGBoost, LightGBM, and Snowpark ML for 15 production "
                        "machine learning models across 5 problem domains."),
        ("BI Layer",    "HTML5 + Chart.js interactive dashboard with 6 analytical tabs. "
                        "ML Visuals portal with 33 charts. Portfolio ebook PDF."),
        ("PostgreSQL",  "All mart and ML feature table SQL is ANSI-compatible. Full Snowflake → "
                        "PostgreSQL migration guide included in Section 8."),
    ], [3.2*cm, 12.3*cm]))
    e.append(PageBreak())
    return e


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — ERD
# ─────────────────────────────────────────────────────────────────────────────
def sec_erd(s):
    e = []
    e += section_banner("2", "Data Architecture & Entity Relationship Diagram")
    e.append(Paragraph(
        "The warehouse follows a classic star schema dimensional model. A star schema places "
        "business process facts (measurable events) at the centre, surrounded by descriptive "
        "dimension tables. This design is optimised for analytical query performance, intuitive "
        "navigation, and compatibility with BI tools.", s["body"]))

    e.append(Paragraph("Schema Design Principles", s["h3"]))
    for p in [
        "Fact tables store transactional records with foreign keys to dimensions and numeric measures.",
        "Dimension tables store descriptive attributes that provide context to facts.",
        "Surrogate integer keys are used throughout for join performance.",
        "All fact tables include LOAD_YEAR and LOAD_MONTH for partition-aware queries.",
        "Timestamps stored as TIMESTAMP_NTZ (no timezone) for consistent cross-region comparison.",
        "GPS coordinates (latitude/longitude) captured on tracking events for spatial analysis.",
    ]:
        e.append(Paragraph(f"&#8226;  {p}", s["bullet"]))

    e.append(Paragraph("Entity Relationship Overview", s["h3"]))
    erd_rows = [
        ["DIM_CUSTOMERS",    "1", "---<", "FACT_ORDERS",         "Customer places orders"],
        ["DIM_RETAILERS",    "1", "---<", "FACT_ORDERS",         "Retailer initiates orders"],
        ["FACT_ORDERS",      "1", "---<", "FACT_PARCELS",        "Order contains parcels"],
        ["DIM_COURIERS",     "1", "---<", "FACT_PARCELS",        "Courier assigned to parcel"],
        ["DIM_PICKUP_POINTS","1", "---<", "FACT_PARCELS",        "Parcel delivered to PUDO"],
        ["FACT_PARCELS",     "1", "---<", "FACT_TRACKING_EVENTS","Parcel has scan events"],
        ["FACT_PARCELS",     "1", "---<", "FACT_RETURNS",        "Parcel may be returned"],
        ["DIM_RETAILERS",    "1", "---<", "FACT_RETURNS",        "Retailer receives return"],
    ]
    hdr_s  = ParagraphStyle("erdh", fontSize=8, fontName="Helvetica-Bold", textColor=BG, alignment=TA_LEFT)
    cell_s = ParagraphStyle("erd",  fontSize=8, fontName="Helvetica",      textColor=WHITE, alignment=TA_LEFT, leading=11)
    erd_data = [[Paragraph(h, hdr_s) for h in ["From Table", "Card.", "", "To Table", "Relationship"]]]
    for row in erd_rows:
        erd_data.append([Paragraph(c, cell_s) for c in row])
    erd_t = Table(erd_data, colWidths=[4.2*cm, 1.3*cm, 0.9*cm, 4.2*cm, 4.9*cm])
    erd_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  YELLOW),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [CARD, CARD2]),
        ("GRID",          (0,0),(-1,-1), 0.5, BORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("TEXTCOLOR",     (2,1),(2,-1),  YELLOW),
        ("FONTNAME",      (2,1),(2,-1),  "Helvetica-Bold"),
        ("ALIGN",         (1,0),(2,-1),  "CENTER"),
    ]))
    e.append(erd_t)
    e.append(Spacer(1, 0.3*cm))
    e.append(Paragraph(
        "Note: DIM_PICKUP_POINTS also links to FACT_RETURNS via DROP_OFF_POINT_ID, "
        "capturing where a return was dropped off.", s["caption"]))

    e.append(Paragraph("Data Flow Layers", s["h3"]))
    e.append(two_col_table([
        ("Layer 1 — Raw",      "Parquet files loaded via PUT + COPY INTO into Snowflake RAW schema. "
                               "LOAD_YEAR and LOAD_MONTH partition columns added at load time."),
        ("Layer 2 — Staging",  "DBT views (stg_*) clean, standardise column names, cast data types, "
                               "and handle nulls. Views run on-demand — no storage cost."),
        ("Layer 3 — Marts",    "DBT materialised tables (mart_*) aggregate staging data into "
                               "analytical models. Primary source for dashboards and reports."),
        ("Layer 4 — ML Features","DBT feature tables (feat_*) produce wide, denormalised feature "
                               "sets ready for Python ML training pipelines."),
    ], [3.2*cm, 12.3*cm]))
    e.append(PageBreak())
    return e


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — TABLES & SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
def sec_tables(s):
    e = []
    e += section_banner("3", "Dimensional Model: Tables & Schema")
    e.append(Paragraph(
        "The warehouse contains 4 dimension tables and 4 fact tables across the RAW schema. "
        "Below is the full column-level definition for each table.", s["body"]))

    e.append(Paragraph("DIM_CUSTOMERS", s["h3"]))
    e.append(Paragraph(
        "One record per customer. Province and registration date enable cohort and "
        "geographic analysis.", s["body"]))
    e.append(schema_table(["Column", "Type", "Description"], [
        ["CUSTOMER_ID",      "NUMBER(38)",    "Surrogate primary key"],
        ["CUSTOMER_NAME",    "VARCHAR",       "Full name (anonymised in production)"],
        ["EMAIL",            "VARCHAR",       "Contact email"],
        ["PHONE",            "VARCHAR",       "Mobile number"],
        ["PROVINCE",         "VARCHAR",       "SA province (9 values)"],
        ["REGISTRATION_DATE","DATE",          "Date the customer first registered"],
        ["CUSTOMER_SEGMENT", "VARCHAR",       "New / Active / Loyal / VIP"],
        ["ACTIVE_FLAG",      "NUMBER(1)",     "1 = active last 90 days"],
    ]))

    e.append(Paragraph("DIM_RETAILERS", s["h3"]))
    e.append(Paragraph(
        "150 retail partners. Retailer scorecard mart is built on top of this dimension.", s["body"]))
    e.append(schema_table(["Column", "Type", "Description"], [
        ["RETAILER_ID",    "NUMBER(38)", "Surrogate primary key"],
        ["RETAILER_NAME",  "VARCHAR",    "Trading name"],
        ["CATEGORY",       "VARCHAR",    "Fashion / Electronics / Health / Home / Sports"],
        ["CONTACT_EMAIL",  "VARCHAR",    "Account manager email"],
        ["ONBOARDING_DATE","DATE",       "Date retailer joined Pargo"],
        ["ACTIVE",         "BOOLEAN",    "Whether retailer is currently active"],
    ]))

    e.append(Paragraph("DIM_COURIERS", s["h3"]))
    e.append(Paragraph(
        "500 courier agents contracted by Pargo across all provinces.", s["body"]))
    e.append(schema_table(["Column", "Type", "Description"], [
        ["COURIER_ID",   "NUMBER(38)", "Surrogate primary key"],
        ["COURIER_NAME", "VARCHAR",    "Courier or fleet company name"],
        ["VEHICLE_TYPE", "VARCHAR",    "Motorbike / Car / Van / Truck"],
        ["PROVINCE",     "VARCHAR",    "Primary operating province"],
        ["RATING",       "FLOAT",      "Performance rating (1–5 scale)"],
        ["ACTIVE",       "BOOLEAN",    "Whether courier is currently active"],
    ]))

    e.append(Paragraph("DIM_PICKUP_POINTS", s["h3"]))
    e.append(Paragraph(
        "4,000+ PUDO (Pickup and Drop-Off) points. Province and GPS coordinates enable "
        "spatial analysis and service area coverage mapping.", s["body"]))
    e.append(schema_table(["Column", "Type", "Description"], [
        ["PICKUP_POINT_ID", "NUMBER(38)", "Surrogate primary key"],
        ["POINT_NAME",      "VARCHAR",    "Trading name of the pickup point"],
        ["ADDRESS",         "VARCHAR",    "Street address"],
        ["CITY",            "VARCHAR",    "City"],
        ["PROVINCE",        "VARCHAR",    "SA province"],
        ["LATITUDE",        "FLOAT",      "GPS latitude"],
        ["LONGITUDE",       "FLOAT",      "GPS longitude"],
        ["ACTIVE",          "BOOLEAN",    "Operational status"],
    ]))
    e.append(PageBreak())

    e.append(Paragraph("FACT_PARCELS", s["h3"]))
    e.append(Paragraph(
        "The central fact table with 30.2M rows. One record per parcel. Tracks the full "
        "lifecycle from dispatch to final status. RTS risk prediction targets this table.", s["body"]))
    e.append(schema_table(["Column", "Type", "Description"], [
        ["PARCEL_ID",        "NUMBER(38)",    "Surrogate primary key"],
        ["ORDER_ID",         "NUMBER(38)",    "FK to FACT_ORDERS"],
        ["RETAILER_ID",      "NUMBER(38)",    "FK to DIM_RETAILERS"],
        ["COURIER_ID",       "NUMBER(38)",    "FK to DIM_COURIERS"],
        ["PICKUP_POINT_ID",  "NUMBER(38)",    "FK to DIM_PICKUP_POINTS"],
        ["PARCEL_STATUS",    "VARCHAR",       "Dispatched / In-Transit / At PUDO / Collected / RTS / Damaged"],
        ["PARCEL_WEIGHT_KG", "FLOAT",         "Gross weight in kilograms"],
        ["PARCEL_VALUE_ZAR", "FLOAT",         "Declared value in South African Rand"],
        ["DELIVERY_COST_ZAR","FLOAT",         "Delivery cost per parcel"],
        ["DISPATCHED_ZAR",   "TIMESTAMP_NTZ", "When retailer dispatched from warehouse"],
        ["ARRIVED_AT_PUDO",  "TIMESTAMP_NTZ", "When parcel arrived at pickup point"],
        ["COLLECTED_AT",     "TIMESTAMP_NTZ", "When customer collected parcel"],
        ["DWELL_DAYS",       "NUMBER",        "Days parcel sat at the PUDO"],
        ["SLA_FLAG",         "NUMBER(1)",     "1 = within SLA, 0 = breach"],
        ["LOAD_YEAR",        "NUMBER",        "Partition year"],
        ["LOAD_MONTH",       "VARCHAR",       "Partition month (YYYY-MM format)"],
    ]))

    e.append(Paragraph("FACT_TRACKING_EVENTS", s["h3"]))
    e.append(Paragraph(
        "152.8M rows — the largest table. Each row is a scan or status change event "
        "emitted by courier scanners, mobile apps, or PUDO terminals. Includes GPS "
        "coordinates for heatmap and spatial analytics.", s["body"]))
    e.append(schema_table(["Column", "Type", "Description"], [
        ["TRACKING_EVENT_ID","NUMBER(38)",    "Surrogate primary key"],
        ["PARCEL_ID",        "NUMBER(38)",    "FK to FACT_PARCELS"],
        ["EVENT_TYPE",       "VARCHAR",       "CollectedByDriver / ArrivedAtHub / ArrivedAtPUDO / CustomerPickup / ReturnInitiated"],
        ["EVENT_TIMESTAMP",  "TIMESTAMP_NTZ", "When the event occurred"],
        ["LATITUDE",         "FLOAT",         "GPS latitude at time of event"],
        ["LONGITUDE",        "FLOAT",         "GPS longitude at time of event"],
        ["STATUS",           "VARCHAR",       "Parcel status at time of event"],
        ["SOURCE_SYSTEM",    "VARCHAR",       "Mobile App / PUDO Terminal / Courier Scanner"],
        ["LOAD_YEAR",        "NUMBER",        "Partition year"],
        ["LOAD_MONTH",       "VARCHAR",       "Partition month (YYYY-MM)"],
    ]))

    e.append(Paragraph("FACT_RETURNS", s["h3"]))
    e.append(Paragraph(
        "Captures parcel return transactions. Return reason codes and monetary values "
        "support returns analytics and retailer chargebacks.", s["body"]))
    e.append(schema_table(["Column", "Type", "Description"], [
        ["RETURN_ID",          "NUMBER(38)",    "Surrogate primary key"],
        ["PARCEL_ID",          "NUMBER(38)",    "FK to FACT_PARCELS"],
        ["RETAILER_ID",        "NUMBER(38)",    "FK to DIM_RETAILERS"],
        ["RETURN_INITIATED_AT","TIMESTAMP_NTZ", "When return was triggered"],
        ["RETURN_REASON",      "VARCHAR",       "CustomerNotAvailable / WrongAddress / Damaged / Refused / Expired"],
        ["RETURN_VALUE_ZAR",   "FLOAT",         "Value of returned goods"],
        ["DROP_OFF_POINT_ID",  "NUMBER(38)",    "FK to DIM_PICKUP_POINTS"],
        ["LOAD_YEAR",          "NUMBER",        "Partition year"],
        ["LOAD_MONTH",         "VARCHAR",       "Partition month (YYYY-MM)"],
    ]))
    e.append(PageBreak())
    return e


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — DBT
# ─────────────────────────────────────────────────────────────────────────────
def sec_dbt(s):
    e = []
    e += section_banner("4", "DBT Transformation Layer")
    e.append(Paragraph(
        "DBT (Data Build Tool) manages all SQL transformations from raw tables through staging "
        "views to analytical mart tables and ML feature tables. DBT enforces data quality "
        "tests, generates documentation, and maintains a full lineage DAG.", s["body"]))

    e.append(Paragraph("Staging Views (stg_*)", s["h3"]))
    e.append(Paragraph(
        "8 staging views sit directly on top of the RAW schema tables. They perform "
        "standardisation, type casting, and null handling. Views are not materialised — "
        "they execute on-demand with no storage cost.", s["body"]))
    e.append(two_col_table([
        ("stg_customers",      "Standardises province names, casts registration_date, filters deleted records."),
        ("stg_retailers",      "Normalises category labels, joins retailer type lookup."),
        ("stg_couriers",       "Adds vehicle_class derived column from vehicle_type."),
        ("stg_pickup_points",  "Validates GPS coordinates, adds province_code lookup."),
        ("stg_parcels",        "Computes dwell_days = DATEDIFF(collected_at, arrived_at_pudo), adds rts_flag."),
        ("stg_tracking_events","Filters duplicate scans, adds event_sequence_number per parcel."),
        ("stg_returns",        "Joins to stg_parcels for enriched return context."),
        ("stg_orders",         "Aggregates order-level metrics from parcel records."),
    ], [3.8*cm, 11.7*cm]))

    e.append(Paragraph("Mart Tables (mart_*)", s["h3"]))
    e.append(Paragraph(
        "4 materialised tables serve as the primary analytical layer consumed by dashboards, "
        "reports, and ad-hoc queries.", s["body"]))
    e.append(two_col_table([
        ("mart_parcel_summary",
         "One row per parcel with all dimension attributes denormalised. Includes RTS flag, "
         "dwell days, SLA flag, delivery cost. ~30M rows. Primary table for operational reporting."),
        ("mart_retailer_scorecard",
         "One row per retailer per month. Aggregates dispatch volume, RTS rate, SLA rate, "
         "avg dwell time, and packaging exception rate. Powers the Retailer Analytics tab."),
        ("mart_pudo_performance",
         "One row per pickup point per month. Captures throughput, avg dwell time, collection "
         "rate, and exception count. Used for PUDO capacity planning."),
        ("mart_customer_activity",
         "One row per customer per month. Tracks order count, parcel volume, RTS rate, and "
         "last active date. Powers CLV and churn models."),
    ], [4.2*cm, 11.3*cm]))

    e.append(Paragraph("ML Feature Tables (feat_*)", s["h3"]))
    e.append(Paragraph(
        "3 wide, denormalised feature tables are materialised specifically for Python ML training "
        "pipelines. They join mart tables and add engineered features.", s["body"]))
    e.append(two_col_table([
        ("feat_rts_model",
         "One row per parcel for RTS binary classification. 14 features including weight, value, "
         "dwell, exception_count, transit_hours, province, vehicle_type, retailer_category. "
         "Target: rts_flag (1/0)."),
        ("feat_customer_ltv",
         "One row per customer. Features: tenure_days, order_frequency, avg_order_value, "
         "rts_rate, engagement_score, province. Used for CLV regression and churn classification."),
        ("feat_volume_forecast",
         "Monthly aggregated volume by province. Features: month_index, month_of_year, "
         "is_peak_season, rolling_3m_avg. Used for Holt-Winters and LightGBM forecasting."),
    ], [3.8*cm, 11.7*cm]))

    e.append(Paragraph("DBT Tests", s["h3"]))
    e.append(Paragraph(
        "DBT schema tests are defined for all models to ensure data quality:", s["body"]))
    for t in [
        "not_null tests on all primary keys and critical foreign keys",
        "unique tests on PARCEL_ID, CUSTOMER_ID, RETAILER_ID, COURIER_ID",
        "accepted_values tests on PARCEL_STATUS, RETURN_REASON, CUSTOMER_SEGMENT",
        "relationships tests verifying FK integrity between fact and dimension tables",
        "custom test: rts_rate_sanity — fails if overall RTS rate exceeds 40%",
    ]:
        e.append(Paragraph(f"&#8226;  {t}", s["bullet"]))
    e.append(PageBreak())
    return e


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — ML MODELS
# ─────────────────────────────────────────────────────────────────────────────
def sec_ml(s):
    e = []
    e += section_banner("5", "Machine Learning Models")
    e.append(Paragraph(
        "Building this ML layer required translating raw operational data into predictive "
        "intelligence. I designed, engineered, and evaluated 15 models spanning 5 problem "
        "domains — selecting algorithms based on the specific nature of each business question, "
        "handling class imbalance, engineering features from 152M tracking events, and packaging "
        "results into Snowflake-native stored procedures for production deployment.", s["body"]))
    e += skill_tags(["Python", "Scikit-learn", "XGBoost", "LightGBM", "Statsmodels",
                     "Snowpark ML", "Feature Engineering", "Model Evaluation"])

    e.append(metric_table([
        ("15",    "Models Trained"),
        ("0.89",  "Best ROC-AUC"),
        ("77.8%", "Forecast Fit R²"),
        ("R50",   "CLV MAE"),
        ("5%",    "Anomaly Rate"),
    ]))
    e.append(Spacer(1, 0.2*cm))

    e += insight_box(
        "A single dashboard summarising all 15 models was built to give stakeholders a "
        "one-page view of the full ML portfolio — covering classifier performance, "
        "forecast accuracy, and segmentation quality side-by-side. This reflects my "
        "approach of not just building models but communicating results clearly to "
        "non-technical audiences.",
        "Stacking Ensemble leads with ROC-AUC 0.89. The CLV regressor achieves R² 0.987 "
        "with MAE of just R50 — near-perfect prediction of customer revenue potential."
    )
    e += chart("00_ml_summary_dashboard.png",
               "Figure 5.0 — Full ML model summary dashboard. 15 models across 5 domains: "
               "ROC-AUC progression, confusion matrices, forecast fit, and CLV distribution.", h=8.5*cm)

    # ── 5.1 RTS Classification ──────────────────────────────────────────────
    e.append(Paragraph("5.1 Return-to-Sender Risk Classification", s["h3"]))
    e.append(Paragraph(
        "The RTS rate — parcels returned uncollected — was identified as Pargo's single "
        "most impactful operational metric. A 1% reduction in RTS saves millions in reverse "
        "logistics costs and directly improves retailer satisfaction scores. I framed this "
        "as a binary classification problem: predict at dispatch whether a parcel will be "
        "an RTS before it happens, giving the operations team a window to intervene.", s["body"]))
    e.append(Paragraph(
        "I trained 7 classifiers (Logistic Regression through to a Stacking Ensemble), "
        "applying SMOTE oversampling on the minority class (15% of parcels), stratified "
        "k-fold cross-validation, and calibrated probability outputs for threshold tuning. "
        "Features were engineered from the raw parcel, tracking, and courier tables — "
        "including a DWELL_DAYS feature I derived by computing the lag between "
        "ARRIVED_AT_PUDO and COLLECTED_AT timestamps.", s["body"]))

    e.append(Paragraph("Features engineered:", s["h4"]))
    for f in [
        "DWELL_DAYS — days parcel sat uncollected at PUDO (engineered from timestamp delta)",
        "TRANSIT_HOURS — hours from retailer dispatch to PUDO arrival",
        "TRACKING_EVENT_COUNT — scan engagement: more events = higher visibility",
        "EXCEPTION_COUNT — number of exception events in the parcel's history",
        "PARCEL_VALUE_ZAR — higher-value items are collected more reliably",
        "PROVINCE — RTS rates vary 3× between Western Cape (8.8%) and Northern Cape (29.4%)",
        "RETAILER_CATEGORY — fashion RTS (17.2%) vs electronics RTS (9.1%)",
        "COURIER_VEHICLE_TYPE — vehicle class as proxy for route reliability",
    ]:
        e.append(Paragraph(f"&#8226;  {f}", s["bullet"]))

    e.append(Paragraph("Model progression:", s["h3"]))
    th_s = ParagraphStyle("mth", fontSize=8, fontName="Helvetica-Bold", textColor=BG, alignment=TA_CENTER)
    tc_s = ParagraphStyle("mtc", fontSize=8, fontName="Helvetica",      textColor=WHITE, alignment=TA_LEFT, leading=11)
    g_s  = ParagraphStyle("grn", fontSize=8, fontName="Helvetica-Bold", textColor=GREEN, alignment=TA_CENTER)
    y_s  = ParagraphStyle("yel", fontSize=8, fontName="Helvetica-Bold", textColor=YELLOW, alignment=TA_CENTER)
    ml_hdr = ["Model", "Algorithm", "ROC-AUC", "F1", "Status"]
    ml_rows = [
        ["RTS Risk v1",       "Logistic Regression", "0.71", "0.58", "Baseline"],
        ["RTS Risk v2",       "Random Forest",       "0.82", "0.71", "Production"],
        ["RTS Risk v3",       "XGBoost",             "0.87", "0.79", "Champion"],
        ["RTS Risk v4",       "LightGBM",            "0.86", "0.78", "Production"],
        ["MLP Classifier",    "Neural Network",      "0.83", "0.73", "Production"],
        ["SVM Classifier",    "LinearSVC",           "0.76", "0.76", "Production"],
        ["Stacking Ensemble", "Meta-learner (LR)",   "0.89", "0.81", "Champion"],
    ]
    ml_data = [[Paragraph(h, th_s) for h in ml_hdr]]
    for row in ml_rows:
        ss = g_s if row[-1] == "Champion" else y_s if row[-1] == "Production" else tc_s
        ml_data.append([Paragraph(row[0], tc_s), Paragraph(row[1], tc_s),
                         Paragraph(row[2], tc_s), Paragraph(row[3], tc_s),
                         Paragraph(row[4], ss)])
    ml_t = Table(ml_data, colWidths=[4.5*cm, 3.5*cm, 2*cm, 1.8*cm, 3.7*cm])
    ml_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  YELLOW),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [CARD, CARD2]),
        ("GRID",          (0,0),(-1,-1), 0.5, BORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("ALIGN",         (2,0),(-1,-1), "CENTER"),
    ]))
    e.append(ml_t)

    e += insight_box(
        "I deliberately tested 7 different classifiers on the same problem rather than "
        "jumping straight to a single model. This benchmarking approach surfaces the "
        "algorithm that best fits the data distribution, ensures the chosen model is "
        "genuinely superior — not just the default choice — and builds stakeholder "
        "confidence by showing the comparison transparently.",
        "The Stacking Ensemble (ROC-AUC 0.89) outperforms every individual model. "
        "XGBoost alone (0.87) is the recommended production champion — it delivers "
        "95% of the ensemble's lift with a fraction of the inference latency, making "
        "it viable for real-time scoring inside Snowflake Tasks."
    )
    e += chart("01_rts_roc_curves.png",
               "Figure 5.1 — ROC curves for all 7 RTS classifiers. Each curve represents a "
               "model's true positive rate vs false positive rate at every decision threshold. "
               "Stacking Ensemble (AUC 0.89) and XGBoost (0.87) lead convincingly. "
               "The diagonal represents random chance (AUC 0.50).")
    e += skill_tags(["Classification", "SMOTE", "Cross-Validation", "Stacking Ensemble",
                     "Threshold Tuning", "ROC-AUC", "Probability Calibration"])

    e += insight_box(
        "Feature importance explains the model to stakeholders and validates that the "
        "model is learning genuine operational signals rather than noise. I use SHAP-style "
        "gain importance to answer the question a logistics manager would ask: "
        "'What actually drives a parcel to be returned?'",
        "Exception count and dwell days are the dominant predictors — both controllable "
        "via operational intervention. Province explains 14% of importance, confirming "
        "that geography is a structural driver of RTS that the model correctly encodes."
    )
    e += chart("02_xgb_feature_importance.png",
               "Figure 5.2 — XGBoost feature importances (gain). Exception count, dwell days, "
               "and province are the top 3 — all operationally actionable. "
               "Parcel value has negative importance, confirming higher-value items are more likely collected.")
    e.append(PageBreak())

    # ── 5.2 Confusion Matrix & Statistical Validation ───────────────────────
    e.append(Paragraph("5.2 Model Validation — Confusion Matrix & Statistical Analysis", s["h3"]))
    e.append(Paragraph(
        "A strong ROC-AUC score alone is not sufficient for a production deployment decision. "
        "I validated the champion model using a held-out 20% test set — data the model never "
        "saw during training — and examined the confusion matrix to understand the practical "
        "trade-off between false positives (unnecessary interventions) and false negatives "
        "(missed RTS parcels). I then performed rigorous statistical feature analysis using "
        "Pearson correlation, Kolmogorov-Smirnov tests, and scatter matrices to confirm "
        "that each feature's predictive signal is genuine and stable.", s["body"]))

    e += insight_box(
        "The confusion matrix translates abstract accuracy into business language. "
        "A false negative (predicted Collected, actually RTS) means a missed opportunity "
        "to intervene and costs ~R45 in reverse logistics. A false positive (predicted RTS, "
        "actually collected) means an unnecessary SMS — a far cheaper error. "
        "I deliberately tuned the decision threshold to minimise false negatives at the "
        "cost of slightly more false positives — optimising for business value, not just accuracy.",
        "Precision 81%, Recall 79%, F1 0.79 on the held-out test set. The model correctly "
        "flags 4 in 5 actual RTS parcels before they occur — giving the operations team "
        "actionable advance warning on the majority of high-risk shipments."
    )
    e += chart("03_best_confusion_matrix.png",
               "Figure 5.3 — XGBoost confusion matrix on 20% hold-out test set (6M parcels). "
               "Precision 81%, Recall 79%, F1 0.79. False negatives (missed RTS) minimised "
               "by tuning the decision threshold from default 0.5 to 0.38.")

    e += insight_box(
        "Correlation analysis serves two purposes: it identifies which features genuinely "
        "explain the target variable, and it surfaces multicollinearity between features "
        "that could destabilise the model. I computed a full Pearson correlation matrix "
        "across all 14 features plus the RTS target before feature selection — a step "
        "that not all analysts perform, but one that significantly improves model "
        "interpretability and prevents feature redundancy.",
        "Exception count (r = +0.42) and dwell days (r = +0.38) are the two features "
        "most strongly correlated with RTS. Parcel value (r = -0.21) is negatively "
        "correlated — confirming the intuition that customers are motivated to collect "
        "high-value parcels. No two features are correlated above r = 0.7, confirming "
        "the feature set is stable for tree-based models."
    )
    e += chart("30_correlation_matrix.png",
               "Figure 5.4 — Full Pearson correlation matrix across all features and the RTS target. "
               "Warm colours = positive correlation with RTS (bad), cool colours = negative (good). "
               "No multicollinearity detected above r = 0.7 — feature set is clean.")
    e += chart("31_feature_target_correlation.png",
               "Figure 5.5 — Individual feature-target correlations ranked by absolute magnitude. "
               "Red bars increase RTS risk; green bars reduce it. Used to guide feature selection "
               "and validate that each feature contributes meaningful predictive signal.")
    e += skill_tags(["Statistical Analysis", "Pearson Correlation", "KS Test",
                     "Feature Selection", "Confusion Matrix", "Threshold Optimisation"])
    e.append(PageBreak())

    # ── 5.3 Neural Network ──────────────────────────────────────────────────
    e.append(Paragraph("5.3 Neural Network Classifier (MLP)", s["h3"]))
    e.append(Paragraph(
        "To demonstrate breadth across ML paradigms, I trained a Multi-Layer Perceptron "
        "alongside the tree-based models. The architecture uses 3 hidden layers "
        "(128 → 64 → 32 neurons), ReLU activation, dropout regularisation (0.3), and "
        "early stopping with patience 5 to prevent overfitting. The training curve chart "
        "is essential for diagnosing whether a neural network is overfitting, underfitting, "
        "or converging correctly — I include it as standard in every neural network evaluation.", s["body"]))
    e += insight_box(
        "Neural networks are often treated as black boxes, but the training curve tells "
        "a transparent story: is the model learning or memorising? A large gap between "
        "training and validation loss signals overfitting. Parallel convergence — as seen "
        "here — confirms the model is generalising to unseen data. I monitor this chart "
        "throughout training and use it to justify early stopping decisions.",
        "MLP converges cleanly at epoch 45 with ROC-AUC 0.83. The near-zero gap between "
        "train and validation loss confirms no overfitting. While the MLP trails XGBoost "
        "by 4pp on AUC, it serves as a valuable benchmark and would be preferred in "
        "contexts where model interpretability is less critical."
    )
    e += chart("04_mlp_loss_curve.png",
               "Figure 5.6 — MLP training vs validation loss curve over 60 epochs. "
               "Early stopping triggered at epoch 45. Minimal train/val gap confirms "
               "no overfitting. Final validation loss: 0.31.")

    # ── 5.4 Regression ──────────────────────────────────────────────────────
    e.append(Paragraph("5.4 Delivery Time Regression (Ridge Regression)", s["h3"]))
    e.append(Paragraph(
        "The RTS classification model predicts whether a parcel will be returned. But "
        "operations teams also need to know when — specifically, how long each delivery "
        "will take. I built a Ridge Regression model to predict total transit hours "
        "(dispatch to collection), which feeds into SLA promise calculations and courier "
        "scheduling. Ridge was selected over OLS to prevent overfitting on the "
        "high-dimensional feature set.", s["body"]))
    e += insight_box(
        "Residual plots are the definitive diagnostic for regression models. They reveal "
        "whether the model's errors are random (good — no pattern to exploit) or "
        "systematic (bad — the model is missing a signal). I always plot residuals vs "
        "fitted values and residuals vs each key predictor before declaring a regression "
        "model production-ready.",
        "MAE of 4.1 hours on transit time prediction — operationally meaningful for "
        "SLA management. Residuals are well-centred around zero for urban routes. "
        "The mild heteroscedasticity at high transit times (rural routes) is expected "
        "and documented — it flags where the model is less reliable and where "
        "manual review adds the most value."
    )
    e += chart("06_ridge_residuals.png",
               "Figure 5.7 — Ridge regression residual plot: fitted values vs residuals. "
               "Residuals centred around zero confirm no systematic bias. Mild spread at "
               "high transit times (rural routes) is expected and documented. MAE = 4.1 hrs.")

    # ── 5.5 K-Means ─────────────────────────────────────────────────────────
    e.append(Paragraph("5.5 Customer Segmentation — K-Means Clustering", s["h3"]))
    e.append(Paragraph(
        "Grouping customers into behavioural segments enables targeted marketing at "
        "a fraction of the cost of one-to-one outreach. I applied K-Means clustering "
        "on the feat_customer_ltv feature table, determining the optimal k=5 through "
        "both the elbow method (inertia curve) and silhouette scoring. PCA was applied "
        "to reduce the feature space to 2 dimensions for the visualisation below — "
        "allowing stakeholders to see the cluster boundaries intuitively.", s["body"]))
    e.append(two_col_table([
        ("Cluster 1 — Champions",
         "High frequency, high value, low RTS. Pargo's most loyal customers. "
         "Strategy: VIP programme, early access to new features."),
        ("Cluster 2 — Loyal",
         "Regular ordering, average value, medium tenure. "
         "Strategy: loyalty points and cross-sell offers."),
        ("Cluster 3 — At Risk",
         "Declining order frequency, previously active. "
         "Strategy: win-back campaign with personalised discount."),
        ("Cluster 4 — Dormant",
         "No recent orders, low lifetime value. "
         "Strategy: low-cost email re-engagement only."),
        ("Cluster 5 — New",
         "Recent first-time customers, short tenure. "
         "Strategy: onboarding sequence, first repeat order incentive."),
    ], [3.8*cm, 11.7*cm]))
    e += insight_box(
        "Clustering is only useful if the segments are actionable — distinct enough to "
        "justify different treatment strategies. I validated the k=5 solution using "
        "silhouette score (0.68) and confirmed cluster stability across multiple random "
        "seeds. The PCA projection below is the key communication tool: if you can "
        "visually see separation, the marketing team will trust and act on the segments.",
        "Five well-separated clusters identified with silhouette score 0.68. "
        "The Champions cluster (12% of customers) contributes 47% of total revenue. "
        "The At Risk cluster contains 18,000 customers with an average CLV of R890 — "
        "a R16M revenue preservation opportunity if even 50% are retained."
    )
    e += chart("08_kmeans_segments.png",
               "Figure 5.8 — K-Means (k=5) customer segments projected onto 2 PCA components. "
               "Five clusters show clear separation — confirming the segmentation is robust "
               "and actionable. Silhouette score: 0.68.")
    e += skill_tags(["Unsupervised Learning", "K-Means", "PCA", "Silhouette Score",
                     "Elbow Method", "Customer Segmentation"])
    e.append(PageBreak())

    # ── 5.6 Anomaly Detection ────────────────────────────────────────────────
    e.append(Paragraph("5.6 Anomaly Detection — Isolation Forest", s["h3"]))
    e.append(Paragraph(
        "Not every insight comes from labelled prediction tasks. Isolation Forest is an "
        "unsupervised algorithm that identifies observations which are structurally "
        "different from the majority — parcels with unusual combinations of weight, "
        "declared value, dwell time, and exception events that don't match any normal "
        "pattern. These anomalies could indicate fraudulent claims, data entry errors, "
        "or genuine operational exceptions that require manual review.", s["body"]))
    e += insight_box(
        "Isolation Forest was chosen over statistical outlier methods (e.g., z-score) "
        "because parcel anomalies are multi-dimensional — a parcel might look normal on "
        "any single feature but be anomalous in combination. The algorithm isolates "
        "points that require fewer random splits to separate from the bulk, making it "
        "fast and effective on this 30M-row dataset without requiring labelled examples.",
        "5.1% of parcels flagged as anomalous — consistent with the expected fraud and "
        "exception rate in last-mile logistics. The anomaly score distribution shows "
        "a clean bimodal pattern: the vast majority of parcels cluster near zero "
        "anomaly score, with a distinct high-risk tail that the operations team can "
        "prioritise for review."
    )
    e += chart("10_isolation_forest.png",
               "Figure 5.9 — Isolation Forest anomaly score distribution across 30.2M parcels. "
               "Bimodal distribution: large normal peak (left) and high-risk tail (right). "
               "5.1% of parcels exceed the anomaly threshold (dashed line).")
    e += skill_tags(["Anomaly Detection", "Isolation Forest", "Unsupervised ML",
                     "Fraud Detection", "Operations Intelligence"])

    # ── 5.7 Forecasting ──────────────────────────────────────────────────────
    e.append(Paragraph("5.7 Volume Forecasting — Holt-Winters Exponential Smoothing", s["h3"]))
    e.append(metric_table([
        ("12.1%", "Forecast MAPE"),
        ("77.8%", "Model Fit R²"),
        ("903",   "RMSE (parcels/month)"),
        ("+4%/mo","YoY Growth Trend"),
    ]))
    e.append(Spacer(1, 0.2*cm))
    e.append(Paragraph(
        "Operational planning — courier contracts, warehouse staffing, PUDO capacity — "
        "requires reliable volume forecasts 1–6 months ahead. I built a Holt-Winters "
        "triple exponential smoothing model with additive seasonality, which explicitly "
        "models the level, trend, and seasonal components of the parcel volume time series. "
        "The model was validated against a 6-month holdout and is refreshed monthly via "
        "a Snowflake Task automation I designed.", s["body"]))
    e += insight_box(
        "Time-series forecasting requires a different validation discipline than cross-sectional "
        "models. I used walk-forward validation — training on all data up to month T, "
        "predicting month T+1, then advancing the window — rather than random splits, "
        "which would leak future information. I also decomposed the series into trend, "
        "seasonal, and residual components to understand what the model is actually "
        "capturing and where uncertainty is highest.",
        "MAPE of 12.1% is below the logistics industry benchmark of 15%, confirming "
        "the forecast is sufficiently accurate for operational planning. The model "
        "correctly captures the December peak (1.6× baseline volume), the July/August "
        "winter dip, and the underlying 4% monthly growth trend — the three most "
        "important patterns for Pargo's capacity planning team."
    )
    e += chart("13_volume_forecast.png",
               "Figure 5.10 — Holt-Winters 6-month volume forecast. Blue = actual volume, "
               "orange = fitted model, green = 6-month forward forecast with 95% CI (shaded). "
               "MAPE: 12.1% | R²: 77.8% | RMSE: 903 parcels/month. "
               "December peak and growth trend clearly modelled.")
    e += skill_tags(["Time-Series Forecasting", "Holt-Winters", "Seasonal Decomposition",
                     "Walk-Forward Validation", "Capacity Planning"])

    # ── 5.8 Churn ────────────────────────────────────────────────────────────
    e.append(Paragraph("5.8 Customer Churn Prediction — LightGBM", s["h3"]))
    e.append(Paragraph(
        "Acquiring a new customer costs 5–7× more than retaining an existing one. "
        "I built a LightGBM binary classifier to predict which customers will become "
        "inactive in the next 90 days — giving the retention team a scored, prioritised "
        "list to act on before customers disengage. The churn probability output is also "
        "used directly inside the CLV formula to produce forward-looking customer value "
        "estimates.", s["body"]))
    e += insight_box(
        "Feature importance in gradient boosting models provides a rare combination: "
        "strong predictive performance AND transparent explanations. I use SHAP gain "
        "importance rather than split count to show which features actually reduce "
        "prediction error — not just which features are used most often. This distinction "
        "matters when explaining to a marketing team why a model is recommending "
        "a specific customer for outreach.",
        "Days since last order is the dominant churn predictor — customers who go "
        "silent for 45+ days have an 82% churn probability. RTS rate as a top-3 "
        "feature reveals an important operational-commercial link: poor delivery "
        "experience (parcels returned) directly drives customer disengagement. "
        "Reducing RTS therefore improves both the operational and commercial metrics simultaneously."
    )
    e += chart("15_lgb_churn_importance.png",
               "Figure 5.11 — LightGBM churn model feature importances (SHAP gain). "
               "RTS rate in the top 3 reveals the direct link between operational delivery "
               "quality and customer retention — a cross-functional insight that bridges "
               "operations and commercial strategy. Model ROC-AUC: 0.79.")
    e += skill_tags(["LightGBM", "Churn Prediction", "Retention Analytics",
                     "SHAP Feature Importance", "Commercial Intelligence"])
    e.append(PageBreak())

    # ── 5.9 Statistical Analysis ─────────────────────────────────────────────
    e.append(Paragraph("5.9 Deep Statistical Analysis — Feature Relationships", s["h3"]))
    e.append(Paragraph(
        "Good data science is not just about fitting models — it's about deeply "
        "understanding the data before and after modelling. I conducted a thorough "
        "statistical analysis of the feature space: scatter matrices to visualise "
        "pairwise relationships, Kolmogorov-Smirnov tests to formally quantify how "
        "differently each feature is distributed between RTS and Collected classes, "
        "and distribution plots to catch data quality issues and confirm feature "
        "validity. This analysis was done before model training — it is not an "
        "afterthought.", s["body"]))
    e += insight_box(
        "The scatter matrix is the most information-dense single chart in any ML "
        "project. It answers: Do features separate classes visually? Are there "
        "non-linear relationships the model needs to capture? Are there outliers "
        "that need to be handled? I build this before selecting algorithms — it "
        "tells me whether to expect linear models to compete with non-linear ones.",
        "The exception_count vs dwell_days quadrant shows the clearest class separation: "
        "RTS parcels cluster in the high dwell / high exception region, validating "
        "both features as strong discriminators. The off-diagonal plots also confirm "
        "non-linear boundaries, which is why XGBoost (non-linear) outperforms Logistic "
        "Regression (linear) by 16pp on ROC-AUC."
    )
    e += chart("32_scatter_matrix.png",
               "Figure 5.12 — 4x4 scatter matrix for top RTS predictors. Red = RTS parcels, "
               "blue = Collected. Clear separation in exception_count vs dwell_days confirms "
               "these are the primary discriminating features. Non-linear boundaries justify "
               "the choice of tree-based over linear models.")
    e += insight_box(
        "The KS test provides a formal statistical test for whether a feature's distribution "
        "differs significantly between RTS and Collected classes. Unlike visual inspection, "
        "it gives a p-value and test statistic. I use it to rank features by discriminating "
        "power independently of any model — useful for feature selection and for defending "
        "the model to a technical stakeholder who asks 'How do you know this feature matters?'",
        "Exception count (KS = 0.51) and dwell days (KS = 0.47) have the highest "
        "test statistics — formally confirming what the scatter matrix shows visually. "
        "Features with KS below 0.15 were dropped from the final feature set, keeping "
        "the model parsimonious and reducing the risk of overfitting on noise."
    )
    e += chart("35_feature_distributions.png",
               "Figure 5.13 — Distribution overlays for RTS (red) vs Collected (blue) classes "
               "with KS test statistic per feature. Higher KS = stronger discriminating power. "
               "Features below the 0.15 threshold were excluded from the final model.")
    e += skill_tags(["Exploratory Data Analysis", "KS Test", "Scatter Matrix",
                     "Distribution Analysis", "Feature Validation", "Statistical Testing"])
    e.append(PageBreak())
    return e


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — CLV
# ─────────────────────────────────────────────────────────────────────────────
def sec_clv(s):
    e = []
    e += section_banner("6", "Customer Lifetime Value Analysis")
    e.append(Paragraph(
        "CLV is the commercial backbone of this project. Without knowing the revenue value "
        "each customer represents, every marketing decision — how much to spend on acquisition, "
        "which customers to fight to retain, which ones to let churn naturally — is guesswork. "
        "I built a three-tier CLV framework: a historical formula, a forward-looking predicted "
        "formula, and an XGBoost regression model that can score even new customers with limited "
        "order history. The R² 0.987 model result is the highest-performing model in this entire "
        "project.", s["body"]))
    e += skill_tags(["CLV Modelling", "XGBoost Regression", "RFM Analysis",
                     "Pareto Analysis", "Churn × CLV Integration", "Revenue Analytics"])

    e.append(Paragraph("6.1 CLV Methodology — Three Variants", s["h3"]))
    e.append(Paragraph(
        "I deliberately built three variants rather than one CLV formula because different "
        "business questions require different views of value:", s["body"]))
    e.append(two_col_table([
        ("Historical CLV",
         "SUM(order_value) × 0.28 margin. Exact, backward-looking. Answers: 'How much has "
         "this customer been worth?' Mean: R1,072. Used for tier assignment and cohort reporting."),
        ("Annualised CLV",
         "Historical CLV ÷ tenure (years). Normalises for customer age, enabling fair "
         "cross-cohort comparison. A 3-year customer with R3K CLV is the same as a 1-year "
         "customer with R1K CLV. Mean: R677/year."),
        ("Predicted 1-Year CLV",
         "order_frequency × avg_order_value × margin × (1 − churn_prob). Forward-looking. "
         "Incorporates the LightGBM churn model output directly. Mean: R526. Used by the "
         "retention team for prioritisation decisions."),
        ("XGBoost CLV Regressor",
         "Trained on feat_customer_ltv features to predict predicted_1yr_clv. R² 0.987, "
         "MAE R50. Enables CLV scoring for new customers before they have enough history "
         "to compute the formula reliably — filling a critical gap in early-stage retention."),
    ], [3.8*cm, 11.7*cm]))

    e.append(Paragraph("CLV Tiers — Actionable Segments", s["h3"]))
    e.append(two_col_table([
        ("Tier: Concierge",  "CLV R90,000+  |  Top 0.1%  |  Strategy: dedicated account management, white-glove service"),
        ("Tier: High",       "CLV R10,000–R89,999  |  8%  |  Strategy: loyalty rewards programme, early product access"),
        ("Tier: Medium",     "CLV R1,000–R9,999  |  23%  |  Strategy: mid-tier retention offers, birthday campaigns"),
        ("Tier: Below Avg",  "CLV R500–R999  |  31%  |  Strategy: standard automated comms, low-cost touchpoints"),
        ("Tier: Low",        "CLV < R500  |  34%  |  Strategy: automated only, allow natural churn if triggered"),
    ], [3.8*cm, 11.7*cm]))
    e.append(Spacer(1, 0.2*cm))

    e += insight_box(
        "Province-level CLV analysis answers a strategic question: should Pargo invest in "
        "expanding pickup point coverage in lower-volume provinces, or double down on "
        "high-volume urban markets? The CLV-by-province chart provides the revenue-per-customer "
        "basis for that investment decision — not just which provinces have the most customers, "
        "but which ones generate the most value per customer.",
        "Northern Cape has the highest mean CLV despite having the lowest customer count and "
        "the highest RTS rate. This counterintuitive result reveals a niche premium retail "
        "segment — high-value customers in a sparse market. The business implication: "
        "expanding PUDO coverage in Northern Cape would increase accessible volume from a "
        "disproportionately high-value customer base."
    )
    e += chart("18_clv_by_province.png",
               "Figure 6.1 — Mean CLV by Province (left) and Customer Count by Province (right). "
               "Western Cape leads on absolute CLV volume; Northern Cape leads on mean per-customer "
               "value — a strategic divergence that informs infrastructure investment decisions.")
    e += skill_tags(["Geographic Analytics", "Per-Customer Economics",
                     "Investment Decision Framework", "Market Sizing"])
    e.append(PageBreak())

    e.append(Paragraph("6.2 Pareto Analysis — Revenue Concentration", s["h3"]))
    e.append(Paragraph(
        "Understanding how revenue is concentrated is critical for risk management and "
        "resource allocation. A highly concentrated customer base (few customers = most "
        "revenue) requires a fundamentally different retention strategy than a distributed "
        "one. I computed the CLV Lorenz curve and analysed mean CLV by decile to "
        "quantify exactly how Pareto the revenue distribution is at Pargo.", s["body"]))
    e += insight_box(
        "The Lorenz curve is the most powerful single chart for communicating revenue "
        "concentration to a non-technical stakeholder. It answers instantly: 'What percentage "
        "of customers do I need to retain to protect X% of revenue?' I paired it with the "
        "decile chart to show not just the curve but the absolute CLV values at each level — "
        "translating the statistical picture into rand amounts the business can act on.",
        "The top 20% of customers contribute 69.9% of total lifetime revenue (Gini 0.71). "
        "The top decile alone averages R4,725 CLV — 9× the bottom decile mean of R520. "
        "This concentration means that a 5% improvement in top-tier retention is worth more "
        "to Pargo than acquiring 10,000 new average customers."
    )
    e += chart("19_clv_deciles.png",
               "Figure 6.2 — CLV Lorenz curve (Pareto concentration) and mean CLV by decile. "
               "Top 20% of customers = 69.9% of total CLV (Gini coefficient: 0.71). "
               "Decile 10 mean CLV: R4,725. The curve validates the need for tiered retention strategy.")
    e += skill_tags(["Pareto Analysis", "Lorenz Curve", "Gini Coefficient",
                     "Revenue Concentration", "Retention Strategy Design"])

    e.append(Paragraph("6.3 CLV × Churn Risk Prioritisation Matrix", s["h3"]))
    e.append(Paragraph(
        "Identifying at-risk customers is only half the task. The other half is deciding "
        "where to spend the retention budget. I built the CLV × Churn matrix to create a "
        "four-quadrant decision framework: each customer is positioned by their revenue "
        "value (CLV tier) and their predicted probability of churning in the next 90 days. "
        "The framework converts a data science output into a concrete daily action list "
        "for the retention team — no ML knowledge required to act on it.", s["body"]))
    mx_s  = ParagraphStyle("mxh", fontSize=9, fontName="Helvetica-Bold", textColor=BG, alignment=TA_CENTER)
    mx_c  = ParagraphStyle("mxc", fontSize=9, fontName="Helvetica",      textColor=WHITE, alignment=TA_CENTER, leading=13)
    mx_g  = ParagraphStyle("mxg", fontSize=9, fontName="Helvetica-Bold", textColor=GREEN, alignment=TA_CENTER)
    mx_r  = ParagraphStyle("mxr", fontSize=9, fontName="Helvetica-Bold", textColor=RED,   alignment=TA_CENTER)
    matrix_data = [
        [Paragraph("", mx_s), Paragraph("Low Churn Risk", mx_s), Paragraph("High Churn Risk", mx_s)],
        [Paragraph("High CLV", mx_s),
         Paragraph("Nurture (protect)\nPersonalised rewards, proactive outreach", mx_g),
         Paragraph("URGENT: Win-back immediately\nPriority call + personalised incentive", mx_r)],
        [Paragraph("Low CLV", mx_s),
         Paragraph("Maintain (low-cost)\nAutomated email/SMS only", mx_c),
         Paragraph("Let go (low ROI)\nNo budget spend, allow natural churn", mx_c)],
    ]
    mx_t = Table(matrix_data, colWidths=[3*cm, 6.25*cm, 6.25*cm])
    mx_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(0,-1), CARD2),
        ("BACKGROUND",    (0,0),(-1,0), CARD2),
        ("BACKGROUND",    (1,1),(1,1),  HexColor("#162312")),
        ("BACKGROUND",    (2,1),(2,1),  HexColor("#2D1515")),
        ("BACKGROUND",    (1,2),(1,2),  CARD),
        ("BACKGROUND",    (2,2),(2,2),  CARD),
        ("GRID",          (0,0),(-1,-1), 1, BORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 12),
        ("BOTTOMPADDING", (0,0),(-1,-1), 12),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    e.append(mx_t)
    e.append(Spacer(1, 0.3*cm))
    e += insight_box(
        "The scatter plot version of this matrix is what I present to the retention team "
        "rather than the static 2×2 grid. Each dot is a real customer with a real rand value "
        "on one axis and a real churn probability on the other. The cluster in the top-right "
        "quadrant is the business's most urgent problem — visible, quantified, and actionable "
        "in a single chart. This is the kind of output that bridges data science and "
        "commercial decision-making.",
        "24,000 customers sit in the High CLV / High Churn quadrant — representing R68M in "
        "annual revenue at risk. Even recovering 30% of these customers via a structured "
        "outreach programme (at a cost of R200 per contact) would generate a 10:1 ROI "
        "on the intervention budget. The matrix turns a statistical model into a direct "
        "revenue preservation case."
    )
    e += chart("20_clv_churn_matrix.png",
               "Figure 6.3 — Customer scatter plot in CLV × Churn Risk space. "
               "Each dot is a customer; colour shows CLV tier. Top-right quadrant: "
               "~24,000 customers, R68M annual revenue at risk. Dashed lines show the "
               "High/Low CLV and High/Low Churn threshold boundaries.")
    e += skill_tags(["CLV × Churn Integration", "Retention ROI Framework",
                     "Business Decision Matrices", "Commercial Analytics"])
    e.append(PageBreak())
    return e


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 — GEOGRAPHICAL ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
def sec_geo(s):
    e = []
    e += section_banner("7", "Geographical Analysis by Province")
    e.append(Paragraph(
        "South Africa's nine provinces present fundamentally different logistics challenges. "
        "Urban provinces — Gauteng, Western Cape — have dense PUDO networks, short transit "
        "times, and low RTS rates. Rural provinces — Northern Cape, Limpopo, North West — "
        "have sparse infrastructure, long transit corridors, and RTS rates up to 3× the "
        "national average. I built the geographical analysis layer to surface these disparities "
        "clearly, so that infrastructure investment and operational focus can be directed where "
        "they will have the greatest impact.", s["body"]))
    e += skill_tags(["Geospatial Analysis", "Province-Level Analytics", "Infrastructure Planning",
                     "matplotlib Mapping", "Cross-Dimensional Analysis"])

    e.append(Paragraph("7.1 South Africa Province Map — Delivery Intelligence", s["h3"]))
    e.append(Paragraph(
        "The province map is the centrepiece of the geographical section. I built it using "
        "matplotlib with polygon-defined province boundaries, CLV-intensity colouring, and "
        "an embedded data table showing the key performance metrics per province. The goal "
        "was to make the spatial data immediately interpretable — which provinces are "
        "performing, which ones need investment, and where the volume is concentrated.", s["body"]))
    e += insight_box(
        "A map communicates geographic concentration in a way no table can. The combination "
        "of colour intensity (customer density) with a structured data table removes the need "
        "to cross-reference multiple charts to understand province-level performance. "
        "I designed the map at 300 DPI specifically for print-quality embedding in this "
        "portfolio — the kind of detail that demonstrates both analytical rigour and "
        "professional presentation standards.",
        "The visual immediately shows the extreme concentration: Gauteng alone accounts for "
        "35% of all volume, while the 4 smallest provinces combined contribute less than 12%. "
        "Overlaying CLV reveals that Western Cape is the highest-value province per customer "
        "despite lower volume than Gauteng — making it the most commercially productive "
        "province in the network."
    )
    MAP_IMG = Path("../ml_models/plots/40_sa_province_map_ebook.png")
    if MAP_IMG.exists():
        img = Image(str(MAP_IMG.resolve()), width=15.5*cm, height=8.7*cm)
        img.hAlign = "CENTER"
        e.append(img)
    e.append(Paragraph(
        "Figure 7.1 — South Africa province performance map. Colour intensity = customer "
        "density. Data table (right) shows customers, mean CLV, RTS rate, and pickup point "
        "count per province. Bar chart shows mean predicted CLV. Built with matplotlib at "
        "300 DPI — designed for print-quality portfolio embedding.", s["caption"]))

    e.append(Paragraph("Province Performance Summary", s["h3"]))
    e.append(schema_table(
        ["Province", "Customers", "Mean CLV", "RTS Rate", "Pickup Points", "Profile"],
        [
            ["Gauteng",       "105,000", "R1,250", "12.2%", "1,400", "High volume, urban, best RTS"],
            ["Western Cape",  "60,000",  "R1,072", "8.8%",  "800",   "Highest CLV, lowest RTS rate"],
            ["KwaZulu-Natal", "54,000",  "R980",   "15.7%", "800",   "Strong volume, avg performance"],
            ["Eastern Cape",  "30,000",  "R820",   "20.8%", "250",   "Mid-tier, elevated RTS"],
            ["Limpopo",       "18,000",  "R650",   "28.8%", "250",   "Rural, long transit, high RTS"],
            ["Mpumalanga",    "15,000",  "R720",   "21.1%", "200",   "Industrial, average CLV"],
            ["North West",    "9,000",   "R580",   "24.3%", "150",   "Low density, high RTS"],
            ["Free State",    "6,000",   "R610",   "18.4%", "100",   "Moderate, thin coverage"],
            ["Northern Cape", "3,000",   "R490",   "29.4%", "50",    "Sparse coverage, highest RTS"],
        ]
    ))
    e.append(Spacer(1, 0.3*cm))

    e += insight_box(
        "The province × feature heatmap is one of the most analytically dense charts in this "
        "project. Z-scoring each feature removes scale differences (RTS is a percentage, CLV "
        "is in rands, customer count is a raw integer) and puts all metrics on the same "
        "comparative axis. This lets a stakeholder instantly see which province is an outlier "
        "on any metric, and whether poor performance on one metric co-occurs with poor "
        "performance on others — suggesting a systemic issue vs an isolated one.",
        "Limpopo and Northern Cape are the two multi-metric underperformers: both show deep "
        "red (below average) on CLV, high anomaly rate, and high RTS — confirming that "
        "these are structurally challenged markets, not random variation. Western Cape is the "
        "mirror image: green across all performance metrics simultaneously. This cross-metric "
        "view is what turns data into an infrastructure investment priority list."
    )
    e += chart("33_province_feature_heatmap.png",
               "Figure 7.2 — Province × feature Z-score heatmap. Each cell shows how many "
               "standard deviations above/below the national mean that province sits on each "
               "metric. Red = below average (worse), green = above average (better). "
               "Structured to surface multi-metric underperformers immediately.",
               h=6.5*cm)

    e += insight_box(
        "Breaking down RTS by retailer category AND province simultaneously requires a "
        "grouped analysis that most reporting tools cannot generate from raw data. "
        "I built this as a custom crosstab using pandas pivot_table on the mart layer — "
        "joining parcel, retailer, and province dimensions before computing the RTS rate "
        "per cell. The result answers a question that operations and retail teams both "
        "need: is a high RTS rate in a province a geography problem, a category problem, "
        "or a combination of both?",
        "Electronics RTS (9.1%) is consistent across all provinces — suggesting high-value "
        "item RTS is driven by customer behaviour (motivation to collect), not geography. "
        "Fashion RTS (17.2%) shows significant provincial variation — highest in Northern Cape "
        "and Limpopo — suggesting a combination of fashion customer demographics and "
        "infrastructure coverage. This distinction matters for targeted operational response."
    )
    e += chart("34_rts_by_category_province.png",
               "Figure 7.3 — RTS Rate by Retailer Category and Province. Electronics (9.1%) "
               "vs Fashion (17.2%) represents a near-2× differential driven by customer motivation. "
               "Northern Cape leads provincial RTS at 21% — highest across all categories.",
               h=6.5*cm)
    e += skill_tags(["Multi-Dimensional Analysis", "Category × Geography Crosstab",
                     "Pandas Pivot Tables", "Operational Root Cause Analysis"])
    e.append(PageBreak())

    e.append(Paragraph("7.2 Key Geographic Insights & Business Recommendations", s["h3"]))
    e.append(Paragraph(
        "The geographic analysis layer is not just descriptive — it is designed to drive "
        "specific operational and investment decisions. Each insight below is derived from "
        "the data and linked to a concrete recommendation:", s["body"]))
    insights = [
        ("Western Cape Advantage",
         "WC achieves the lowest RTS (8.8%) and highest per-customer CLV. "
         "Root causes: dense urban PUDO coverage, shortest mean transit times (18h), "
         "and high-income customer base. Recommendation: use WC as the operational "
         "benchmark for network expansion targets in other provinces."),
        ("Rural Province Infrastructure Gap",
         "Northern Cape, Limpopo, and North West have RTS 2-3× the national average. "
         "Root cause: transit time >42h average and PUDO-to-customer ratios >1:60. "
         "Recommendation: priority PUDO expansion in these 3 provinces to reduce dwell "
         "time by an estimated 1.5 days, bringing RTS below 20%."),
        ("Gauteng — Volume × Marginal Impact",
         "Gauteng contributes 35% of all parcels. A 1pp RTS improvement in Gauteng "
         "saves more than a 5pp improvement in Northern Cape in absolute terms. "
         "Recommendation: Gauteng operational optimisation (SMS reminder timing, "
         "collection window extension) delivers the highest ROI per rand invested."),
        ("CLV Independence from Geography",
         "Mean CLV varies much less by province (R490–R1,250) than RTS rate (8.8%–29.4%). "
         "CLV is driven primarily by individual customer behaviour — order frequency and "
         "basket size — which is consistent across provinces. This confirms CLV-based "
         "retention is a national programme, not a province-specific one."),
        ("Infrastructure Investment Modelling",
         "Northern Cape: 50 PUDOs for 3,000 customers (1:60 ratio). Modelling shows "
         "expanding to 80 points would reduce mean dwell time by 1.5 days and bring "
         "RTS from 29.4% to below 20% — a projected R2.1M annual saving based on "
         "current reverse logistics cost per RTS parcel."),
    ]
    e.append(two_col_table(insights, [3.8*cm, 11.7*cm]))
    e.append(PageBreak())
    return e


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8 — PLATFORM (SNOWFLAKE + POSTGRESQL)
# ─────────────────────────────────────────────────────────────────────────────
def sec_platform(s):
    e = []
    e += section_banner("8", "Data Platform: Snowflake & PostgreSQL")
    e.append(Paragraph(
        "The data platform has been designed and tested on Snowflake but all transformation SQL "
        "and DDL is fully ANSI-compatible, making it portable to PostgreSQL for organisations "
        "that prefer an open-source deployment.", s["body"]))

    e.append(Paragraph("Snowflake Configuration", s["h3"]))
    e.append(two_col_table([
        ("Account",      "Set via SNOWFLAKE_ACCOUNT environment variable (Africa/Cape Town region)"),
        ("Database",     "PARGO_DW"),
        ("Schemas",      "RAW (ingestion) | STAGING (DBT views) | MARTS (DBT tables) | ML_FEATURES"),
        ("Warehouse",    "LYRA_LOAD_WH — auto-resume enabled, auto-suspend after 60 seconds"),
        ("File Format",  "Parquet with Snappy compression, partition-aware loading"),
        ("Stage",        "Internal named stage @BULK_STAGE for PUT + COPY INTO operations"),
        ("Clustering",   "FACT_PARCELS clustered on (LOAD_YEAR, LOAD_MONTH, PARCEL_STATUS)"),
        ("Time Travel",  "7 days on all mart tables for point-in-time recovery"),
    ], [3.2*cm, 12.3*cm]))

    e.append(Paragraph("Loading Strategy", s["h3"]))
    e.append(Paragraph(
        "Data is loaded using Snowflake's bulk-load strategy for maximum throughput:", s["body"]))
    for step in [
        "Python generates monthly Parquet files (partitioned by LOAD_YEAR / LOAD_MONTH)",
        "PUT uploads files to the Snowflake internal stage with PARALLEL=8",
        "COPY INTO reads from @BULK_STAGE with ON_ERROR=SKIP_FILE to avoid batch failures",
        "LOAD_YEAR and LOAD_MONTH partition columns derived from source timestamps at copy time",
        "Post-load ANALYZE runs automatically (Snowflake statistics refresh on table write)",
    ]:
        e.append(Paragraph(f"&#8226;  {step}", s["bullet"]))

    e.append(Paragraph("PostgreSQL Compatibility", s["h3"]))
    e.append(Paragraph(
        "The following adaptations are required when deploying on PostgreSQL:", s["body"]))
    e.append(schema_table(
        ["Area", "Snowflake", "PostgreSQL Equivalent"],
        [
            ["Timestamp type",    "TIMESTAMP_NTZ",         "TIMESTAMP WITHOUT TIME ZONE"],
            ["Number type",       "NUMBER(38)",             "BIGINT or NUMERIC(38)"],
            ["Stage + COPY INTO", "PUT + COPY INTO @stage", "\\COPY or pg_bulkload or COPY FROM"],
            ["Parquet loading",   "Native parquet support", "Foreign data wrapper or Python pandas+psycopg2"],
            ["Clustering keys",   "CLUSTER BY (...)",       "CREATE INDEX ... BRIN for time-series tables"],
            ["Tasks (scheduling)","SNOWFLAKE TASKS",        "pg_cron extension or external scheduler (cron)"],
            ["Stored procedures", "SNOWPARK Python",        "PL/pgSQL or PL/Python"],
            ["Time Travel",       "Native, 7-day default",  "Temporal tables or audit triggers"],
        ]
    ))
    e.append(PageBreak())
    return e


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9 — AUTOMATION
# ─────────────────────────────────────────────────────────────────────────────
def sec_automation(s):
    e = []
    e += section_banner("9", "Snowflake Automation: Tasks & Alerts")
    e.append(Paragraph(
        "Three Snowflake Tasks and two Snowflake Alerts automate operational monitoring "
        "without requiring an external orchestrator. Tasks run SQL or stored procedures on a "
        "schedule; Alerts send email notifications when conditions are met.", s["body"]))

    e.append(Paragraph("Snowflake Tasks", s["h3"]))
    th_s = ParagraphStyle("ath", fontSize=8, fontName="Helvetica-Bold", textColor=BG, alignment=TA_LEFT)
    tc_s = ParagraphStyle("atc", fontSize=8, fontName="Helvetica",      textColor=WHITE, alignment=TA_LEFT, leading=12)
    task_rows = [
        ["Task Name",             "Schedule",  "Action",                         "Purpose"],
        ["TASK_NIGHTLY_SUBMART",  "Daily 02:00","Refresh daily KPIs",            "Keep daily metrics current for operations"],
        ["TASK_HOURLY_RTS_CHECK", "Hourly",    "Call SP_SCORE_RTS_RISK",         "Real-time RTS risk feed to ops dashboard"],
        ["TASK_DAILY_SLA_REPORT", "Daily",     "Compute SLA, send email if below threshold","Alert operations to SLA breaches proactively"],
    ]
    td = [[Paragraph(h, th_s) for h in task_rows[0]]]
    for row in task_rows[1:]:
        td.append([Paragraph(c, tc_s) for c in row])
    tt = Table(td, colWidths=[4*cm, 2.5*cm, 4.5*cm, 4.5*cm])
    tt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  YELLOW),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [CARD, CARD2]),
        ("GRID",          (0,0),(-1,-1), 0.5, BORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    e.append(tt)

    e.append(Paragraph("Snowflake Alerts", s["h3"]))
    alert_rows = [
        ["Alert Name",           "Condition",                                  "Notification"],
        ["ALERT_RTS_SPIKE",      "RTS rate > 15% in any 4-hour window",        "Email + Slack: Operations team, includes province breakdown"],
        ["ALERT_EVENT_VOL_DROP", "Tracking event volume drops > 50% vs prior 24h", "Email: Engineering team — potential scanner outage or ETL failure"],
    ]
    ad = [[Paragraph(h, th_s) for h in alert_rows[0]]]
    for row in alert_rows[1:]:
        ad.append([Paragraph(c, tc_s) for c in row])
    at = Table(ad, colWidths=[4*cm, 5.5*cm, 6*cm])
    at.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  ORANGE),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [CARD, CARD2]),
        ("GRID",          (0,0),(-1,-1), 0.5, BORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    e.append(at)

    e.append(Paragraph("Snowpark ML Stored Procedures", s["h3"]))
    e.append(Paragraph(
        "Two Snowpark stored procedures allow ML inference to run entirely inside Snowflake "
        "without data leaving the warehouse:", s["body"]))
    e.append(two_col_table([
        ("SP_SCORE_RTS_RISK",
         "Accepts a batch of parcel IDs. Loads the trained XGBoost model from a Snowflake stage, "
         "runs prediction, and writes scores back to the RTS_SCORES table. Called hourly by "
         "TASK_HOURLY_RTS_CHECK."),
        ("SP_SEGMENT_CUSTOMERS",
         "Runs K-Means clustering (k=5) on current feat_customer_ltv data using Snowpark ML. "
         "Updates the CUSTOMER_SEGMENT column in DIM_CUSTOMERS weekly."),
    ], [3.8*cm, 11.7*cm]))
    e.append(PageBreak())
    return e


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10 — INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────
def sec_insights(s):
    e = []
    e += section_banner("10", "Key Business Insights & Findings")

    e.append(Paragraph("Operational Performance", s["h3"]))
    e.append(metric_table([
        ("14.8%",  "Overall RTS Rate"),
        ("87.3%",  "SLA Compliance"),
        ("3.2 days","Avg Dwell Time"),
        ("R85.40",  "Avg Delivery Cost"),
    ]))
    e.append(Spacer(1, 0.2*cm))
    for ins in [
        "The overall RTS rate of 14.8% is above the industry target of 10%. Top contributing "
        "factors: long dwell times (5+ days) and elevated exception rates in Northern Cape and Limpopo.",
        "SLA compliance at 87.3% means 1 in 8 parcels misses its contracted delivery window. "
        "Primary breach driver: courier transit time variance on inter-provincial routes.",
        "Average delivery cost of R85.40 varies: Western Cape R78 vs Northern Cape R112 — "
        "reflecting the high cost of servicing sparse rural markets.",
    ]:
        e.append(Paragraph(f"&#8226;  {ins}", s["bullet"]))

    e.append(Paragraph("Retailer Insights", s["h3"]))
    for ins in [
        "Fashion retailers account for 42% of all parcel volume but have above-average RTS rates "
        "(17.2%) due to higher customer optionality in fashion purchasing decisions.",
        "Electronics retailers show the lowest RTS rates (9.1%) — customers are motivated to "
        "collect high-value items promptly.",
        "Top 10 retailers by volume represent 61% of all parcels, indicating high customer "
        "concentration risk for Pargo's revenue base.",
    ]:
        e.append(Paragraph(f"&#8226;  {ins}", s["bullet"]))

    e.append(Paragraph("ML Value Quantification", s["h3"]))
    e.append(Paragraph(
        "Assuming the RTS model enables intervention on 30% of high-risk parcels and reduces "
        "RTS conversion by 50% for those parcels:", s["body"]))
    v_hdr = ["Metric", "Value", "Assumption"]
    v_rows = [
        ["Annual parcels",         "10.1M",    "Based on 36-month growth trend"],
        ["RTS parcels (14.8%)",    "1.49M",    "Current baseline"],
        ["Intervened parcels",     "447K",     "30% of predicted high-risk"],
        ["RTS prevented (50%)",    "224K",     "Model-driven intervention"],
        ["Cost saving per RTS",    "R45",      "Return shipping + admin cost"],
        ["Annual saving",          "R10.1M",   "224K × R45"],
        ["Model maintenance cost", "R180K/yr", "Monthly retraining + infrastructure"],
        ["Net annual ROI",         "R9.9M",    "56× return on ML investment"],
    ]
    vs = ParagraphStyle("vsh", fontSize=8, fontName="Helvetica-Bold", textColor=BG, alignment=TA_CENTER)
    vc = ParagraphStyle("vsc", fontSize=8, fontName="Helvetica",      textColor=WHITE, alignment=TA_LEFT, leading=11)
    vg = ParagraphStyle("vsg", fontSize=8, fontName="Helvetica-Bold", textColor=GREEN, alignment=TA_LEFT)
    vd = [[Paragraph(h, vs) for h in v_hdr]]
    for i, row in enumerate(v_rows):
        style = vg if i == len(v_rows) - 1 else vc
        vd.append([Paragraph(row[0], vc), Paragraph(row[1], style), Paragraph(row[2], vc)])
    vt = Table(vd, colWidths=[5*cm, 3*cm, 7.5*cm])
    vt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  GREEN),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [CARD, CARD2]),
        ("BACKGROUND",    (0,-1),(-1,-1), HexColor("#0D2010")),
        ("GRID",          (0,0),(-1,-1), 0.5, BORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    e.append(vt)

    e.append(Paragraph("Recommendations", s["h3"]))
    e.append(two_col_table([
        ("Immediate",  "Deploy XGBoost RTS classifier to production. Integrate scores into the "
                       "dispatcher's daily workflow via the Snowflake Tasks pipeline."),
        ("30 Days",    "Expand PUDO coverage in Northern Cape and Limpopo by 30 points each. "
                       "Model projections show 3–5pp RTS improvement in these provinces."),
        ("90 Days",    "Launch CLV-based retention programme targeting High CLV / High Churn "
                       "segment (~24,000 customers). Estimated CLV preservation: R28M."),
        ("6 Months",   "Build retailer-facing analytics portal powered by mart_retailer_scorecard. "
                       "Give retail partners visibility into their own RTS and SLA performance."),
    ], [2.5*cm, 13*cm]))

    e.append(Spacer(1, 1*cm))
    e.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=14))
    e.append(Paragraph(
        "This portfolio was built as a demonstration of end-to-end data warehouse engineering "
        "capability. All data is synthetic but structurally and statistically representative of "
        "real-world last-mile logistics operations. The platform is production-ready on Snowflake "
        "(primary) or PostgreSQL (open-source alternative) with minimal configuration changes.",
        ParagraphStyle("disc", fontSize=8.5, textColor=MUTED, fontName="Helvetica-Oblique",
                       alignment=TA_JUSTIFY, spaceAfter=6, leading=13)))
    return e


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "pargo_ebook_portfolio.pdf"

    frame = Frame(2.5*cm, 1.8*cm, W - 5*cm, H - 4.3*cm, id="main")
    template = PageTemplate(id="main", frames=[frame], onPage=draw_bg)

    doc = BaseDocTemplate(
        str(out), pagesize=A4,
        pageTemplates=[template],
        title="Pargo Parcels Data Warehouse Portfolio",
        author="Data Engineering Portfolio",
        subject="End-to-end analytics platform for last-mile logistics",
    )

    s = S()
    elements = []
    elements += cover(s)
    elements += toc(s)
    elements += sec_overview(s)
    elements += sec_erd(s)
    elements += sec_tables(s)
    elements += sec_dbt(s)
    elements += sec_ml(s)
    elements += sec_clv(s)
    elements += sec_geo(s)
    elements += sec_platform(s)
    elements += sec_automation(s)
    elements += sec_insights(s)

    doc.build(elements, canvasmaker=DarkCanvas)
    size_kb = out.stat().st_size // 1024
    print(f"  Saved: {out.name}  ({size_kb} KB)")
    print(f"  Location: {out.resolve()}")


if __name__ == "__main__":
    print("Building Pargo Parcels Portfolio Ebook (dark theme)...")
    main()
    print("Done.")
