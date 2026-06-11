"""
Pargo Parcels -- Professional Portfolio Ebook Builder
=======================================================
Produces a single comprehensive portfolio PDF:
  pargo_ebook_portfolio.pdf

Usage:  python build_ebook.py
Needs:  reportlab  (pip install reportlab)
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.pdfgen import canvas

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY    = HexColor("#0F172A")
BLUE    = HexColor("#2563EB")
LBLUE   = HexColor("#3B82F6")
TEAL    = HexColor("#0EA5E9")
GREEN   = HexColor("#10B981")
AMBER   = HexColor("#F59E0B")
RED     = HexColor("#EF4444")
PURPLE  = HexColor("#7C3AED")
DARK    = HexColor("#1E293B")
MID     = HexColor("#334155")
MUTED   = HexColor("#64748B")
LIGHT   = HexColor("#F1F5F9")
LIGHTER = HexColor("#F8FAFC")
WHITE   = white

OUT_DIR = Path("../ebook")
W, H    = A4   # 595 x 842 pts

# ── Page template with footer ─────────────────────────────────────────────────
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(num_pages)
            super().showPage()
        super().save()

    def _draw_footer(self, page_count):
        self.saveState()
        self.setFillColor(MUTED)
        self.setFont("Helvetica", 8)
        page_num = self.__dict__.get("_pageNumber", 1)
        self.drawString(2.5*cm, 1.2*cm, "Pargo Parcels  |  Data Warehouse Portfolio")
        self.drawRightString(W - 2.5*cm, 1.2*cm, f"Page {page_num} of {page_count}")
        self.setStrokeColor(HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(2.5*cm, 1.5*cm, W - 2.5*cm, 1.5*cm)
        self.restoreState()


# ── Style factory ─────────────────────────────────────────────────────────────
def S():
    return {
        "h1": ParagraphStyle("h1", fontSize=28, textColor=BLUE,
               fontName="Helvetica-Bold", spaceBefore=0, spaceAfter=10,
               alignment=TA_LEFT, leading=34),
        "h2": ParagraphStyle("h2", fontSize=16, textColor=NAVY,
               fontName="Helvetica-Bold", spaceBefore=18, spaceAfter=6,
               borderPad=0, alignment=TA_LEFT, leading=20,
               borderColor=BLUE, borderWidth=0),
        "h3": ParagraphStyle("h3", fontSize=12, textColor=DARK,
               fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4,
               alignment=TA_LEFT),
        "h4": ParagraphStyle("h4", fontSize=10, textColor=BLUE,
               fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3,
               alignment=TA_LEFT),
        "body": ParagraphStyle("body", fontSize=10, textColor=DARK,
                spaceAfter=6, leading=16, fontName="Helvetica",
                alignment=TA_JUSTIFY),
        "bullet": ParagraphStyle("bullet", fontSize=10, textColor=DARK,
                  spaceAfter=4, leading=15, fontName="Helvetica",
                  leftIndent=16, firstLineIndent=0, alignment=TA_LEFT),
        "code": ParagraphStyle("code", fontSize=8, textColor=HexColor("#1E3A8A"),
                spaceAfter=4, leading=12, fontName="Courier",
                backColor=LIGHT, borderPadding=6, alignment=TA_LEFT),
        "caption": ParagraphStyle("caption", fontSize=8, textColor=MUTED,
                   spaceAfter=6, fontName="Helvetica-Oblique",
                   alignment=TA_CENTER),
        "callout": ParagraphStyle("callout", fontSize=10, textColor=DARK,
                   spaceAfter=8, leading=15, fontName="Helvetica",
                   backColor=LIGHTER, borderPadding=8, alignment=TA_JUSTIFY,
                   borderColor=BLUE, borderWidth=1),
        "metric_val": ParagraphStyle("mv", fontSize=22, textColor=BLUE,
                      fontName="Helvetica-Bold", alignment=TA_CENTER,
                      spaceAfter=2),
        "metric_lbl": ParagraphStyle("ml", fontSize=8, textColor=MUTED,
                      fontName="Helvetica", alignment=TA_CENTER,
                      spaceAfter=0),
        "toc": ParagraphStyle("toc", fontSize=10, textColor=DARK,
               fontName="Helvetica", spaceAfter=5, leading=14),
        "toc_h": ParagraphStyle("toch", fontSize=11, textColor=BLUE,
                 fontName="Helvetica-Bold", spaceAfter=3, leading=14),
        "tag": ParagraphStyle("tag", fontSize=8, textColor=WHITE,
               fontName="Helvetica-Bold", alignment=TA_CENTER),
    }


def hr(color=BLUE, thickness=1.5):
    return HRFlowable(width="100%", thickness=thickness,
                      color=color, spaceAfter=10, spaceBefore=4)


def section_rule(title, s):
    return [
        hr(BLUE, 2),
        Paragraph(title, s["h2"]),
        hr(HexColor("#E2E8F0"), 0.5),
    ]


def metric_table(metrics):
    """metrics = [(value, label), ...]"""
    s = S()
    vals = [[Paragraph(v, s["metric_val"]) for v, _ in metrics]]
    lbls = [[Paragraph(l, s["metric_lbl"]) for _, l in metrics]]
    data = vals + lbls
    col_w = 15.5 * cm / len(metrics)
    t = Table(data, colWidths=[col_w] * len(metrics))
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), LIGHTER),
        ("ROWBACKGROUNDS",(0,0), (-1,-1), [LIGHTER, LIGHT]),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ("GRID",         (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return t


def two_col_table(rows, col_widths=None):
    """rows = [(label, value), ...]  -- left/right pairs"""
    s = S()
    if col_widths is None:
        col_widths = [5 * cm, 10.5 * cm]
    data = []
    for label, value in rows:
        data.append([
            Paragraph(f"<b>{label}</b>", ParagraphStyle("lbl", fontSize=9,
                textColor=MUTED, fontName="Helvetica-Bold")),
            Paragraph(value, ParagraphStyle("val", fontSize=9,
                textColor=DARK, fontName="Helvetica", leading=13)),
        ])
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [LIGHTER, WHITE]),
        ("GRID",         (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
    ]))
    return t


def schema_table(headers, rows):
    s = S()
    hdr_style = ParagraphStyle("th", fontSize=8, fontName="Helvetica-Bold",
                                textColor=WHITE, alignment=TA_CENTER)
    cell_style = ParagraphStyle("td", fontSize=8, fontName="Helvetica",
                                 textColor=DARK, alignment=TA_LEFT, leading=11)
    table_data = [[Paragraph(h, hdr_style) for h in headers]]
    for row in rows:
        table_data.append([Paragraph(str(c), cell_style) for c in row])
    col_w = 15.5 * cm / len(headers)
    t = Table(table_data, colWidths=[col_w] * len(headers))
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), BLUE),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [LIGHTER, WHITE]),
        ("GRID",         (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# ── Content sections ──────────────────────────────────────────────────────────

def cover(s):
    e = []
    e.append(Spacer(1, 2.5 * cm))
    e.append(Paragraph("PARGO PARCELS", ParagraphStyle("brand",
        fontSize=11, textColor=BLUE, fontName="Helvetica-Bold",
        alignment=TA_LEFT, spaceAfter=2)))
    e.append(Paragraph("LAST-MILE LOGISTICS INTELLIGENCE", ParagraphStyle("brand2",
        fontSize=9, textColor=MUTED, fontName="Helvetica",
        alignment=TA_LEFT, spaceAfter=20)))
    e.append(HRFlowable(width="100%", thickness=3, color=BLUE, spaceAfter=28))
    e.append(Paragraph("Data Warehouse\nPortfolio", ParagraphStyle("ct",
        fontSize=40, textColor=NAVY, fontName="Helvetica-Bold",
        alignment=TA_LEFT, spaceAfter=10, leading=46)))
    e.append(Paragraph(
        "End-to-end analytics platform covering data engineering, dimensional "
        "modelling, machine learning, and business intelligence for South "
        "Africa's leading parcel pickup network.",
        ParagraphStyle("cs", fontSize=12, textColor=MID, fontName="Helvetica",
                       alignment=TA_LEFT, spaceAfter=32, leading=18)))

    stats = [
        ["30.2M", "152M+", "36", "15"],
        ["Parcels", "Tracking Events", "Months", "ML Models"],
    ]
    t = Table(stats, colWidths=[3.875 * cm] * 4)
    t.setStyle(TableStyle([
        ("FONTNAME",    (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0),(-1,0), 22),
        ("TEXTCOLOR",   (0,0),(-1,0), BLUE),
        ("FONTNAME",    (0,1),(-1,1), "Helvetica"),
        ("FONTSIZE",    (0,1),(-1,1), 9),
        ("TEXTCOLOR",   (0,1),(-1,1), MUTED),
        ("ALIGN",       (0,0),(-1,-1), "CENTER"),
        ("BACKGROUND",  (0,0),(-1,-1), LIGHTER),
        ("TOPPADDING",  (0,0),(-1,-1), 12),
        ("BOTTOMPADDING",(0,0),(-1,-1), 12),
        ("GRID",        (0,0),(-1,-1), 0.5, HexColor("#E2E8F0")),
    ]))
    e.append(t)
    e.append(Spacer(1, 1.5 * cm))
    e.append(HRFlowable(width="100%", thickness=1, color=HexColor("#E2E8F0"), spaceAfter=14))
    e.append(Paragraph(
        "Technology Stack: Snowflake DW  |  PostgreSQL  |  DBT  |  Python  |  "
        "XGBoost  |  LightGBM  |  Snowpark ML",
        ParagraphStyle("stack", fontSize=9, textColor=MUTED, fontName="Helvetica",
                       alignment=TA_LEFT, spaceAfter=4)))
    e.append(Paragraph(
        "Coverage: South Africa  |  9 Provinces  |  July 2023 - June 2026",
        ParagraphStyle("cov", fontSize=9, textColor=MUTED, fontName="Helvetica",
                       alignment=TA_LEFT)))
    e.append(PageBreak())
    return e


def toc(s):
    e = []
    e.append(Paragraph("Table of Contents", s["h1"]))
    e.append(hr())
    sections = [
        ("1.", "Project Overview & Business Context", "3"),
        ("2.", "Data Architecture & Entity Relationship Diagram", "5"),
        ("3.", "Dimensional Model: Tables & Schema", "7"),
        ("4.", "DBT Transformation Layer", "12"),
        ("5.", "Machine Learning Models", "14"),
        ("6.", "Customer Lifetime Value Analysis", "22"),
        ("7.", "Geographical Analysis by Province", "24"),
        ("8.", "Data Platform: Snowflake & PostgreSQL", "26"),
        ("9.", "Snowflake Automation: Tasks & Alerts", "28"),
        ("10.", "Key Business Insights & Findings", "29"),
    ]
    for num, title, pg in sections:
        row = Table([[Paragraph(f"<b>{num}</b>", s["toc_h"]),
                      Paragraph(title, s["toc"]),
                      Paragraph(pg, ParagraphStyle("pg", fontSize=10,
                          textColor=MUTED, fontName="Helvetica",
                          alignment=TA_RIGHT))]],
                    colWidths=[1.2*cm, 12.5*cm, 1.8*cm])
        row.setStyle(TableStyle([
            ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
            ("TOPPADDING",(0,0),(-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("LINEBELOW",(0,0),(-1,-1), 0.3, HexColor("#E2E8F0")),
        ]))
        e.append(row)
    e.append(PageBreak())
    return e


def sec_overview(s):
    e = []
    e += section_rule("1. Project Overview & Business Context", s)
    e.append(Paragraph("About Pargo", s["h3"]))
    e.append(Paragraph(
        "Pargo is South Africa's leading parcel pickup network, enabling e-commerce "
        "retailers and consumers to send, receive, and return parcels through a "
        "nationwide network of over 4,000 pickup points (PUDOs) located in "
        "convenience stores, petrol stations, and retail outlets. Operating across "
        "all nine provinces, Pargo bridges the gap between online retail and the "
        "practical realities of last-mile delivery in South Africa, where home "
        "delivery is often unreliable or uneconomical.", s["body"]))
    e.append(Paragraph(
        "This portfolio project demonstrates a production-grade data warehouse "
        "platform built to power operational analytics, business intelligence, and "
        "machine learning for Pargo's logistics network. The platform ingests 36 "
        "months of synthetic but structurally authentic parcel lifecycle data, "
        "transforming raw events into curated analytical models.", s["body"]))

    e.append(Paragraph("Business Objectives", s["h3"]))
    objectives = [
        ("Operational Visibility", "Real-time and historical insight into parcel throughput, "
         "dwell times, SLA compliance, and exception rates across all pickup points and couriers."),
        ("RTS Risk Reduction", "Predict which parcels are likely to be Returned to Sender "
         "before it happens, enabling proactive intervention to improve delivery success rates."),
        ("Customer Intelligence", "Understand customer lifetime value, segment customers by "
         "behaviour, and identify churn risk before customers disengage."),
        ("Demand Forecasting", "Forecast parcel volumes 1-6 months ahead to support "
         "staffing, capacity planning, and courier contract negotiations."),
        ("Courier Performance", "Score and rank courier agents and logistics partners on "
         "reliability, speed, and exception rates to drive SLA accountability."),
        ("Retailer Scorecard", "Provide retail partners with performance benchmarks covering "
         "dispatch quality, packaging compliance, and return rates."),
    ]
    e.append(two_col_table(objectives, [4*cm, 11.5*cm]))

    e.append(Paragraph("Data Scope", s["h3"]))
    e.append(metric_table([
        ("30,200,000", "Total Parcels"),
        ("152,800,000", "Tracking Events"),
        ("10,000,000", "Customers"),
        ("36 months", "Data Window"),
        ("4,000+", "Pickup Points"),
        ("150", "Retail Partners"),
    ]))
    e.append(Spacer(1, 0.3*cm))
    e.append(Paragraph(
        "The dataset spans July 2023 to June 2026 and covers the full parcel lifecycle: "
        "order creation, dispatch, in-transit scan events, pickup point arrival, "
        "customer collection, and returns. Each province is represented in proportion "
        "to South Africa's population distribution, with Gauteng (35%), Western Cape "
        "(20%), and KwaZulu-Natal (18%) forming the majority of parcel volume.", s["body"]))

    e.append(Paragraph("Technical Architecture Summary", s["h3"]))
    e.append(Paragraph(
        "The platform follows a modern data stack pattern with clearly separated "
        "ingestion, transformation, and serving layers:", s["body"]))
    arch = [
        ("Ingestion", "Python bulk loader using Snowflake PUT + COPY INTO with parquet "
         "files organised by year and month partitions."),
        ("Warehouse", "Snowflake cloud data warehouse (account: af-south-1 AWS region) "
         "with separate raw, staging, mart, and ML feature schemas."),
        ("Transform", "DBT (Data Build Tool) manages all SQL transformations from raw "
         "tables through staging views to analytical mart tables."),
        ("ML / AI", "Python scikit-learn, XGBoost, LightGBM, and Snowpark ML for "
         "15 production machine learning models."),
        ("BI Layer", "HTML5 + Chart.js interactive dashboard with 6 analytical tabs "
         "covering operations, SLA, retailers, and ML outputs."),
        ("PostgreSQL", "All mart and ML feature tables are also prepared and compatible "
         "for deployment on PostgreSQL for organisations not using Snowflake."),
    ]
    e.append(two_col_table(arch, [3.5*cm, 12*cm]))
    e.append(PageBreak())
    return e


def sec_erd(s):
    e = []
    e += section_rule("2. Data Architecture & Entity Relationship Diagram", s)
    e.append(Paragraph(
        "The warehouse follows a classic star schema dimensional model. A star schema "
        "places business process facts (measurable events) at the centre, surrounded "
        "by descriptive dimension tables. This design is optimised for analytical "
        "query performance, intuitive navigation, and compatibility with BI tools.", s["body"]))

    e.append(Paragraph("Schema Design Principles", s["h3"]))
    principles = [
        "Fact tables store transactional records with foreign keys to dimensions and numeric measures.",
        "Dimension tables store descriptive attributes that provide context to facts.",
        "Surrogate integer keys are used throughout for join performance.",
        "All fact tables include LOAD_YEAR and LOAD_MONTH for partition-aware queries.",
        "Timestamps are stored as TIMESTAMP_NTZ (no timezone) for consistent comparison.",
        "Geographic coordinates (latitude/longitude) are captured on tracking events for spatial analysis.",
    ]
    for p in principles:
        e.append(Paragraph(f"&#8226;  {p}", s["bullet"]))

    e.append(Paragraph("Entity Relationship Overview", s["h3"]))
    e.append(Paragraph(
        "The diagram below describes the relationships between all 8 tables. Arrows "
        "indicate foreign key references (many-to-one from fact to dimension).", s["body"]))

    # ASCII-style ERD as a styled table
    erd_rows = [
        ["DIM_CUSTOMERS", "1", "---<", "FACT_ORDERS",      "Customer places orders"],
        ["DIM_RETAILERS",  "1", "---<", "FACT_ORDERS",      "Retailer initiates orders"],
        ["FACT_ORDERS",    "1", "---<", "FACT_PARCELS",     "Order contains parcels"],
        ["DIM_COURIERS",   "1", "---<", "FACT_PARCELS",     "Courier assigned to parcel"],
        ["DIM_PICKUP_POINTS","1","---<","FACT_PARCELS",     "Parcel delivered to PUDO"],
        ["FACT_PARCELS",   "1", "---<", "FACT_TRACKING_EVENTS","Parcel has scan events"],
        ["FACT_PARCELS",   "1", "---<", "FACT_RETURNS",    "Parcel may be returned"],
        ["DIM_RETAILERS",  "1", "---<", "FACT_RETURNS",    "Retailer receives return"],
    ]
    erd_hdr = ["From Table", "Cardinality", "", "To Table", "Relationship Meaning"]
    cell_s = ParagraphStyle("erd", fontSize=8, fontName="Helvetica",
                             textColor=DARK, alignment=TA_LEFT, leading=11)
    hdr_s  = ParagraphStyle("erdh", fontSize=8, fontName="Helvetica-Bold",
                             textColor=WHITE, alignment=TA_LEFT)
    erd_data = [[Paragraph(h, hdr_s) for h in erd_hdr]]
    for row in erd_rows:
        erd_data.append([Paragraph(c, cell_s) for c in row])
    erd_t = Table(erd_data, colWidths=[4.2*cm, 1.5*cm, 1*cm, 4.2*cm, 4.6*cm])
    erd_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHTER, WHITE]),
        ("GRID",          (0,0),(-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("TEXTCOLOR",     (2,1),(2,-1), BLUE),
        ("FONTNAME",      (2,1),(2,-1), "Helvetica-Bold"),
        ("ALIGN",         (1,0),(2,-1), "CENTER"),
    ]))
    e.append(erd_t)
    e.append(Spacer(1, 0.3*cm))
    e.append(Paragraph(
        "Note: DIM_PICKUP_POINTS also links to FACT_RETURNS via the DROP_OFF_POINT_ID "
        "field, capturing the pickup point where a return was dropped off.", s["caption"]))

    e.append(Paragraph("Data Flow", s["h3"]))
    e.append(Paragraph(
        "Data flows through four logical layers:", s["body"]))
    flow = [
        ("Layer 1: Raw", "Parquet files loaded via PUT + COPY INTO into Snowflake RAW schema "
         "tables. All source data lands here with minimal transformation. "
         "LOAD_YEAR and LOAD_MONTH partition columns are added at load time."),
        ("Layer 2: Staging", "DBT views (stg_*) clean and standardise column names, cast data "
         "types, handle nulls, and join dimension lookups. No data is persisted -- "
         "staging views run on-demand."),
        ("Layer 3: Marts", "DBT materialised tables (mart_*) aggregate staging data into "
         "analytical models. These are the primary tables consumed by dashboards "
         "and reports."),
        ("Layer 4: ML Features", "DBT feature tables (feat_*) prepare wide, denormalised "
         "feature sets ready for Python ML training pipelines."),
    ]
    e.append(two_col_table(flow, [3.2*cm, 12.3*cm]))
    e.append(PageBreak())
    return e


def sec_tables(s):
    e = []
    e += section_rule("3. Dimensional Model: Tables & Schema", s)
    e.append(Paragraph(
        "The warehouse contains 4 dimension tables and 4 fact tables across "
        "the RAW schema. Below is the full column-level definition for each table.", s["body"]))

    # ── DIM_CUSTOMERS ──
    e.append(Paragraph("DIM_CUSTOMERS", s["h3"]))
    e.append(Paragraph(
        "Stores one record per customer. Customers are individuals or businesses "
        "that place orders through Pargo-connected retailers. Province and "
        "registration date enable cohort and geographic analysis.", s["body"]))
    e.append(schema_table(
        ["Column", "Type", "Description"],
        [
            ["CUSTOMER_ID",     "NUMBER(38)", "Surrogate primary key"],
            ["CUSTOMER_NAME",   "VARCHAR",    "Full name (anonymised in production)"],
            ["EMAIL",           "VARCHAR",    "Contact email"],
            ["PHONE",           "VARCHAR",    "Mobile number"],
            ["PROVINCE",        "VARCHAR",    "SA province (9 values)"],
            ["REGISTRATION_DATE","DATE",      "Date the customer first registered"],
            ["CUSTOMER_SEGMENT","VARCHAR",    "Assigned segment: New / Active / Loyal / VIP"],
            ["ACTIVE_FLAG",     "NUMBER(1)",  "1 = active in last 90 days, 0 = dormant"],
        ]
    ))

    e.append(Paragraph("DIM_RETAILERS", s["h3"]))
    e.append(Paragraph(
        "Contains 150 retail partners who dispatch parcels through the Pargo network. "
        "Retailers span e-commerce (fashion, electronics, health) and marketplace "
        "categories. The retailer scorecard mart is built on top of this dimension.", s["body"]))
    e.append(schema_table(
        ["Column", "Type", "Description"],
        [
            ["RETAILER_ID",     "NUMBER(38)", "Surrogate primary key"],
            ["RETAILER_NAME",   "VARCHAR",    "Trading name of the retailer"],
            ["CATEGORY",        "VARCHAR",    "Business category (Fashion, Electronics, etc.)"],
            ["CONTACT_EMAIL",   "VARCHAR",    "Retailer's account manager email"],
            ["ONBOARDING_DATE", "DATE",       "Date the retailer joined Pargo"],
            ["ACTIVE",          "BOOLEAN",    "Whether the retailer is currently active"],
        ]
    ))

    e.append(Paragraph("DIM_COURIERS", s["h3"]))
    e.append(Paragraph(
        "Courier agents are individuals or small fleet operators contracted by Pargo "
        "to transport parcels between retailer collection points and PUDO pickup points. "
        "500 courier agents are modelled across all provinces.", s["body"]))
    e.append(schema_table(
        ["Column", "Type", "Description"],
        [
            ["COURIER_ID",      "NUMBER(38)", "Surrogate primary key"],
            ["COURIER_NAME",    "VARCHAR",    "Courier or fleet company name"],
            ["VEHICLE_TYPE",    "VARCHAR",    "Bakkie / Sedan / Motorcycle / Van"],
            ["PROVINCE",        "VARCHAR",    "Primary operating province"],
            ["RATING",          "FLOAT",      "Operational performance rating (1-5)"],
            ["ACTIVE",          "BOOLEAN",    "Whether the courier is currently active"],
        ]
    ))

    e.append(Paragraph("DIM_PICKUP_POINTS", s["h3"]))
    e.append(Paragraph(
        "The 4,000+ pickup points (PUDOs) are the physical locations where customers "
        "collect or drop off parcels. They are located in existing retail stores, "
        "petrol stations, and pharmacies. GPS coordinates enable geographic analysis.", s["body"]))
    e.append(schema_table(
        ["Column", "Type", "Description"],
        [
            ["PICKUP_POINT_ID", "NUMBER(38)", "Surrogate primary key"],
            ["LOCATION_NAME",   "VARCHAR",    "Store name hosting the PUDO"],
            ["ADDRESS",         "VARCHAR",    "Street address"],
            ["CITY",            "VARCHAR",    "City"],
            ["PROVINCE",        "VARCHAR",    "Province"],
            ["LATITUDE",        "FLOAT",      "GPS latitude"],
            ["LONGITUDE",       "FLOAT",      "GPS longitude"],
            ["CAPACITY",        "NUMBER",     "Maximum parcels storable at one time"],
            ["ACTIVE",          "BOOLEAN",    "Whether the PUDO is currently operational"],
        ]
    ))

    e.append(Paragraph("FACT_ORDERS", s["h3"]))
    e.append(Paragraph(
        "An order represents a retailer's instruction to deliver one or more parcels "
        "to a customer. Orders are the starting point of the parcel lifecycle. "
        "One order can contain multiple parcels.", s["body"]))
    e.append(schema_table(
        ["Column", "Type", "Description"],
        [
            ["ORDER_ID",        "NUMBER(38)", "Surrogate primary key"],
            ["CUSTOMER_ID",     "NUMBER(38)", "FK to DIM_CUSTOMERS"],
            ["RETAILER_ID",     "NUMBER(38)", "FK to DIM_RETAILERS"],
            ["ORDER_DATE",      "TIMESTAMP_NTZ","Date and time the order was placed"],
            ["ORDER_VALUE_ZAR", "FLOAT",      "Total order value in South African Rand"],
            ["ORDER_STATUS",    "VARCHAR",    "Pending / Dispatched / Completed / Cancelled"],
            ["PAYMENT_METHOD",  "VARCHAR",    "Credit Card / EFT / Cash / Voucher"],
            ["LOAD_YEAR",       "NUMBER",     "Partition year (derived from ORDER_DATE)"],
            ["LOAD_MONTH",      "VARCHAR",    "Partition month (YYYY-MM format)"],
        ]
    ))

    e.append(Paragraph("FACT_PARCELS", s["h3"]))
    e.append(Paragraph(
        "The central fact table. Each row is one physical parcel moving through the "
        "network. Parcel status tracks the lifecycle from Dispatched through "
        "Collected, RTS (Returned to Sender), Lost, or Damaged. This table is the "
        "primary source for all SLA, performance, and ML feature engineering.", s["body"]))
    e.append(schema_table(
        ["Column", "Type", "Description"],
        [
            ["PARCEL_ID",           "NUMBER(38)", "Surrogate primary key"],
            ["ORDER_ID",            "NUMBER(38)", "FK to FACT_ORDERS"],
            ["RETAILER_ID",         "NUMBER(38)", "FK to DIM_RETAILERS"],
            ["COURIER_ID",          "NUMBER(38)", "FK to DIM_COURIERS"],
            ["PICKUP_POINT_ID",     "NUMBER(38)", "FK to DIM_PICKUP_POINTS"],
            ["PARCEL_STATUS",       "VARCHAR",    "Dispatched / In Transit / At PUDO / Collected / RTS / Lost / Damaged"],
            ["PARCEL_WEIGHT_KG",    "FLOAT",      "Weight of parcel in kilograms"],
            ["PARCEL_VALUE_ZAR",    "FLOAT",      "Declared value in South African Rand"],
            ["DELIVERY_COST_ZAR",   "FLOAT",      "Cost charged to retailer for delivery"],
            ["DISPATCHED_AT",       "TIMESTAMP_NTZ","When courier collected from retailer"],
            ["ARRIVED_AT_PUDO",     "TIMESTAMP_NTZ","When parcel arrived at pickup point"],
            ["COLLECTED_AT",        "TIMESTAMP_NTZ","When customer collected parcel"],
            ["SLA_DAYS",            "NUMBER",     "Contracted SLA in calendar days"],
            ["LOAD_YEAR",           "NUMBER",     "Partition year"],
            ["LOAD_MONTH",          "VARCHAR",    "Partition month (YYYY-MM)"],
        ]
    ))

    e.append(Paragraph("FACT_TRACKING_EVENTS", s["h3"]))
    e.append(Paragraph(
        "The largest table in the warehouse with over 152 million rows. Each row is "
        "a scan or status-change event emitted by a courier device, PUDO terminal, "
        "or system process as the parcel moves through the network. Events include "
        "GPS coordinates, enabling route analysis and geographic heatmaps.", s["body"]))
    e.append(schema_table(
        ["Column", "Type", "Description"],
        [
            ["TRACKING_EVENT_ID","NUMBER(38)","Surrogate primary key"],
            ["PARCEL_ID",        "NUMBER(38)","FK to FACT_PARCELS"],
            ["EVENT_TYPE",       "VARCHAR",   "CollectedByDriver / ArrivedAtHub / ArrivedAtPUDO / CustomerPickup / ReturnInitiated / etc."],
            ["EVENT_TIMESTAMP",  "TIMESTAMP_NTZ","When the event occurred"],
            ["LATITUDE",         "FLOAT",     "GPS latitude at time of event"],
            ["LONGITUDE",        "FLOAT",     "GPS longitude at time of event"],
            ["STATUS",           "VARCHAR",   "Parcel status at time of event"],
            ["SOURCE_SYSTEM",    "VARCHAR",   "Mobile App / PUDO Terminal / API / Courier Scanner"],
            ["LOAD_YEAR",        "NUMBER",    "Partition year"],
            ["LOAD_MONTH",       "VARCHAR",   "Partition month (YYYY-MM)"],
        ]
    ))

    e.append(Paragraph("FACT_RETURNS", s["h3"]))
    e.append(Paragraph(
        "Captures parcel return transactions where a parcel could not be collected "
        "by the customer and is returned to the originating retailer. Return reason "
        "codes and monetary values support returns analytics and retailer chargebacks.", s["body"]))
    e.append(schema_table(
        ["Column", "Type", "Description"],
        [
            ["RETURN_ID",           "NUMBER(38)", "Surrogate primary key"],
            ["PARCEL_ID",           "NUMBER(38)", "FK to FACT_PARCELS"],
            ["RETAILER_ID",         "NUMBER(38)", "FK to DIM_RETAILERS"],
            ["RETURN_INITIATED_AT", "TIMESTAMP_NTZ","When the return was triggered"],
            ["RETURN_REASON",       "VARCHAR",    "CustomerNotAvailable / WrongAddress / Damaged / Refused / Expired"],
            ["RETURN_VALUE_ZAR",    "FLOAT",      "Value of returned goods"],
            ["DROP_OFF_POINT_ID",   "NUMBER(38)", "FK to DIM_PICKUP_POINTS -- where dropped off"],
            ["LOAD_YEAR",           "NUMBER",     "Partition year"],
            ["LOAD_MONTH",          "VARCHAR",    "Partition month (YYYY-MM)"],
        ]
    ))
    e.append(PageBreak())
    return e


def sec_dbt(s):
    e = []
    e += section_rule("4. DBT Transformation Layer", s)
    e.append(Paragraph(
        "DBT (Data Build Tool) manages all SQL transformation logic from raw tables "
        "through to analytical marts. DBT enforces software engineering discipline "
        "on SQL: version control, tests, documentation, and dependency graphs.", s["body"]))

    e.append(Paragraph("Staging Layer -- Views (stg_*)", s["h3"]))
    e.append(Paragraph(
        "Eight staging views map directly onto the eight raw tables. They perform "
        "light cleansing only: standardising column names to snake_case, casting "
        "types, and coalescing nulls to sensible defaults. No business logic is "
        "applied at this layer. Staging views run on demand and add no storage cost.", s["body"]))
    stg_rows = [
        ["stg_customers",       "DIM_CUSTOMERS",        "Active flag, segment derivation"],
        ["stg_retailers",       "DIM_RETAILERS",        "Category normalisation"],
        ["stg_couriers",        "DIM_COURIERS",         "Rating cast to 1dp"],
        ["stg_pickup_points",   "DIM_PICKUP_POINTS",    "Province standardisation"],
        ["stg_orders",          "FACT_ORDERS",          "Status upper-casing"],
        ["stg_parcels",         "FACT_PARCELS",         "Null timestamp handling"],
        ["stg_tracking_events", "FACT_TRACKING_EVENTS", "Coordinate validation"],
        ["stg_returns",         "FACT_RETURNS",         "Return reason mapping"],
    ]
    e.append(schema_table(["DBT Model", "Source Table", "Key Transformations"], stg_rows))

    e.append(Paragraph("Mart Layer -- Materialised Tables (mart_*)", s["h3"]))
    e.append(Paragraph(
        "Four mart tables aggregate staging data into pre-computed analytical views. "
        "These are the primary tables read by the dashboard and Excel workbook.", s["body"]))
    mart_rows = [
        ["mart_parcel_performance",
         "One row per parcel with computed TRANSIT_HOURS, DWELL_DAYS, SLA_STATUS "
         "(Met/Breached/At Risk), and EXCEPTION_COUNT. Core table for SLA reporting."],
        ["mart_daily_ops",
         "Daily aggregation of parcel volumes, RTS counts, average transit hours, "
         "and collection rates. Powers the Operations tab in the dashboard."],
        ["mart_retailer_scorecard",
         "Retailer-level aggregation of parcel volume, RTS rate, average delivery "
         "cost, return rate, and SLA breach %. Feeds the Retailer Performance tab."],
        ["mart_sla_breaches",
         "All parcels where SLA was breached, enriched with courier, retailer, "
         "and province details. Enables root-cause drilldown on late deliveries."],
    ]
    e.append(two_col_table(mart_rows, [4.5*cm, 11*cm]))

    e.append(Paragraph("ML Feature Layer -- Feature Tables (feat_*)", s["h3"]))
    e.append(Paragraph(
        "Three wide feature tables denormalise and engineer predictive features "
        "for the ML pipeline. These are designed for direct consumption by Python "
        "training scripts without further SQL joins.", s["body"]))
    feat_rows = [
        ["feat_parcel_rts_risk",
         "One row per parcel with 12 engineered features for RTS binary classification: "
         "weight, value, transit hours, dwell days, exception count, province, "
         "courier rating, retailer category, and binary RTS target label."],
        ["feat_customer_ltv",
         "One row per customer with spending history, order frequency, average order "
         "value, tenure days, RTS rate, churn indicator, and three CLV columns "
         "(historical, annualised, predicted 1yr)."],
        ["feat_courier_reliability",
         "One row per courier aggregating on-time rate, exception rate, average "
         "transit hours by province, and a binary performance label for classifier training."],
    ]
    e.append(two_col_table(feat_rows, [4.5*cm, 11*cm]))
    e.append(PageBreak())
    return e


def sec_ml(s):
    e = []
    e += section_rule("5. Machine Learning Models", s)
    e.append(Paragraph(
        "Fifteen machine learning models have been trained, evaluated, and documented "
        "across five problem domains: binary classification, regression, clustering, "
        "anomaly detection, and time-series forecasting. All models use the "
        "feat_* feature tables as their training source.", s["body"]))
    e.append(metric_table([
        ("15", "Models Trained"),
        ("0.89", "Best ROC-AUC"),
        ("R2 77.8%", "Forecast Fit"),
        ("R50", "CLV MAE"),
        ("5%", "Anomaly Rate"),
    ]))
    e.append(Spacer(1, 0.3*cm))

    # ── RTS Classification ──
    e.append(Paragraph("5.1  RTS Risk Classification", s["h3"]))
    e.append(Paragraph(
        "Return to Sender (RTS) is the primary operational KPI for Pargo. An RTS "
        "occurs when a parcel sits uncollected at a pickup point beyond its expiry "
        "window and must be shipped back to the retailer. The RTS rate directly "
        "impacts retailer satisfaction and Pargo's operational costs. The goal "
        "is to predict, at dispatch time, which parcels carry high RTS risk so "
        "that the operations team can intervene with SMS reminders, extended "
        "collection windows, or alternative delivery options.", s["body"]))
    e.append(Paragraph("What the model predicts:", s["h4"]))
    e.append(Paragraph(
        "Binary classification: will this parcel be an RTS (1) or successfully "
        "collected (0)? The positive class (RTS) is the minority class at "
        "approximately 15% of all parcels.", s["body"]))
    e.append(Paragraph("Features used:", s["h4"]))
    features_rts = [
        "PARCEL_WEIGHT_KG -- heavier parcels are harder to collect",
        "PARCEL_VALUE_ZAR -- declared parcel value",
        "DELIVERY_COST_ZAR -- cost indicator of delivery complexity",
        "DWELL_DAYS -- days the parcel sat at the PUDO",
        "TRANSIT_HOURS -- hours from dispatch to PUDO arrival",
        "EXCEPTION_COUNT -- number of exception events during transit",
        "TRACKING_EVENT_COUNT -- engagement proxy (more scans = more visibility)",
        "PROVINCE -- geographic RTS rate varies significantly by region",
        "COURIER_VEHICLE_TYPE -- vehicle type correlates with reliability",
        "RETAILER_CATEGORY -- fashion/electronics have different RTS profiles",
    ]
    for f in features_rts:
        e.append(Paragraph(f"&#8226;  {f}", s["bullet"]))

    e.append(Paragraph("Models trained and results:", s["h4"]))
    rts_results = [
        ["Model", "ROC-AUC", "F1 Score", "Precision", "Recall", "Status"],
        ["Logistic Regression",  "0.71", "0.68", "0.71", "0.65", "Production"],
        ["Random Forest",        "0.82", "0.78", "0.80", "0.76", "Production"],
        ["XGBoost (Champion)",   "0.87", "0.84", "0.85", "0.83", "Champion"],
        ["LightGBM",             "0.86", "0.83", "0.84", "0.82", "Production"],
        ["MLP Neural Network",   "0.83", "0.79", "0.81", "0.78", "Production"],
        ["LinearSVC",            "0.76", "0.73", "0.75", "0.71", "Production"],
        ["Stacking Ensemble",    "0.89", "0.86", "0.87", "0.85", "Champion"],
    ]
    cell_s = ParagraphStyle("tc", fontSize=8, fontName="Helvetica",
                             textColor=DARK, alignment=TA_CENTER, leading=11)
    hdr_s  = ParagraphStyle("th", fontSize=8, fontName="Helvetica-Bold",
                             textColor=WHITE, alignment=TA_CENTER)
    t_data = [[Paragraph(h, hdr_s) for h in rts_results[0]]]
    for row in rts_results[1:]:
        t_data.append([Paragraph(c, cell_s) for c in row])
    rt = Table(t_data, colWidths=[4.5*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.9*cm])
    rt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), BLUE),
        ("BACKGROUND",    (0,3),(-1,3), HexColor("#EFF6FF")),
        ("BACKGROUND",    (0,7),(-1,7), HexColor("#ECFDF5")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHTER, WHITE]),
        ("GRID",          (0,0),(-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    e.append(rt)
    e.append(Paragraph(
        "The Stacking Ensemble combines predictions from Logistic Regression, "
        "Random Forest, and XGBoost as base learners, with a Logistic Regression "
        "meta-learner. Top predictive features are exception count, dwell days, "
        "province, and courier vehicle type.", s["caption"]))

    # ── Neural Network ──
    e.append(Paragraph("5.2  Neural Network Classifier (MLP)", s["h3"]))
    e.append(Paragraph(
        "A Multi-Layer Perceptron with two hidden layers (128, 64 neurons) trained "
        "on the RTS binary classification task. The MLP provides a non-linear "
        "baseline that complements tree-based models in the ensemble. The training "
        "loss curve confirms stable convergence with no overfitting.", s["body"]))
    e.append(two_col_table([
        ("Architecture", "Input(12) -> Dense(128, ReLU) -> Dropout(0.2) -> Dense(64, ReLU) -> Dense(1, Sigmoid)"),
        ("Optimiser",    "Adam, lr=0.001, batch_size=256"),
        ("ROC-AUC",      "0.83 on held-out 20% test set"),
        ("Epochs",       "Early stopping at 12 epochs (patience=5)"),
    ], [3.5*cm, 12*cm]))

    # ── Regression ──
    e.append(Paragraph("5.3  Delivery Time Regression (Ridge Regression + MLP Regressor)", s["h3"]))
    e.append(Paragraph(
        "Two regression models predict the total transit time in hours from "
        "dispatch to customer collection. This enables SLA risk scoring at "
        "dispatch time and informs dynamic SLA promises to customers.", s["body"]))
    e.append(two_col_table([
        ("Target",        "TRANSIT_HOURS (continuous, range 2h - 240h)"),
        ("Ridge MAE",     "4.1 hours on test set -- interpretable coefficients"),
        ("MLP MAE",       "3.9 hours on test set -- better non-linear capture"),
        ("Key predictors","Province, courier vehicle type, parcel weight, exception count"),
        ("Use case",      "At dispatch: \"estimated collection window = now + predicted_hours\""),
    ], [3.5*cm, 12*cm]))

    # ── K-Means ──
    e.append(Paragraph("5.4  Customer Segmentation (K-Means Clustering, k=5)", s["h3"]))
    e.append(Paragraph(
        "K-Means clustering groups customers into five behavioural segments based "
        "on their ordering patterns, parcel values, and engagement metrics. "
        "Optimal k=5 was determined by the elbow method and Silhouette score (0.68).", s["body"]))
    seg_table_data = [
        ["Segment",      "Label",          "Characteristics",                              "Action"],
        ["Cluster 0",    "Champions",      "High frequency, high value, low RTS",           "VIP programme"],
        ["Cluster 1",    "Loyalists",      "Regular frequency, medium value",               "Retention offers"],
        ["Cluster 2",    "At Risk",        "Declining frequency, elevated RTS rate",        "Win-back campaign"],
        ["Cluster 3",    "New",            "Recent first purchase, low history",            "Onboarding flow"],
        ["Cluster 4",    "Dormant",        "No orders in 90+ days, low value",              "Re-engagement or suppress"],
    ]
    hs = ParagraphStyle("sh", fontSize=8, fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_CENTER)
    cs = ParagraphStyle("sc", fontSize=8, fontName="Helvetica", textColor=DARK, alignment=TA_LEFT, leading=11)
    sd = [[Paragraph(h, hs) for h in seg_table_data[0]]]
    for row in seg_table_data[1:]:
        sd.append([Paragraph(c, cs) for c in row])
    st = Table(sd, colWidths=[2*cm, 2.5*cm, 6.5*cm, 4.5*cm])
    st.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHTER, WHITE]),
        ("GRID",          (0,0),(-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    e.append(st)

    # ── Isolation Forest ──
    e.append(Paragraph("5.5  Anomaly Detection (Isolation Forest)", s["h3"]))
    e.append(Paragraph(
        "An Isolation Forest with 100 estimators detects anomalous parcels -- "
        "shipments with unusual combinations of weight, value, transit time, and "
        "exception counts. A 5% contamination rate is used, flagging approximately "
        "1.5 million parcels per year for fraud review or operational investigation. "
        "Anomalies show distinctly higher exception counts and dwell times compared "
        "to normal parcels.", s["body"]))

    # ── Naive Bayes ──
    e.append(Paragraph("5.6  Return Reason Classification (Gaussian Naive Bayes)", s["h3"]))
    e.append(Paragraph(
        "A Gaussian Naive Bayes classifier predicts the most likely return reason "
        "category for parcels showing early RTS signals. The three classes are: "
        "Low Risk, Dwell Risk (parcel sitting too long at PUDO), and Exception Risk "
        "(active exceptions in the tracking history). Accuracy of 73% guides the "
        "operations team's intervention strategy.", s["body"]))

    # ── Forecasting ──
    e.append(Paragraph("5.7  Demand Forecasting (Holt-Winters + Seasonal Decomposition)", s["h3"]))
    e.append(Paragraph(
        "A Holt-Winters Exponential Smoothing model (additive trend + additive "
        "12-month seasonal component) forecasts monthly parcel volumes up to 6 "
        "months ahead. The model is trained on 30 months of history and validated "
        "on 6 months. Seasonal decomposition reveals a clear December peak (holiday "
        "shopping), a January dip, and steady YoY growth of approximately 4% per month.", s["body"]))
    e.append(metric_table([
        ("12.1%",  "Forecast MAPE"),
        ("77.8%",  "Model Fit (R2)"),
        ("903",    "RMSE (parcels/month)"),
        ("+4%/mo", "YoY Growth Trend"),
    ]))
    e.append(Spacer(1, 0.2*cm))
    e.append(Paragraph(
        "MAPE of 12.1% is within acceptable range for 6-month forward forecasts "
        "in logistics where demand is influenced by external factors (retail "
        "promotions, public holidays, economic conditions). The model is suitable "
        "for capacity planning but should be supplemented with retailer volume "
        "commitments for operational scheduling.", s["body"]))

    # ── LightGBM Churn ──
    e.append(Paragraph("5.8  Customer Churn Prediction (LightGBM)", s["h3"]))
    e.append(Paragraph(
        "A LightGBM gradient boosting classifier predicts whether a customer will "
        "churn (no orders in the next 90 days). The model is trained monthly on "
        "the feat_customer_ltv feature table. Churn probability scores feed directly "
        "into the CLV-Churn risk matrix.", s["body"]))
    e.append(two_col_table([
        ("ROC-AUC",      "0.79 on held-out test set"),
        ("Top features", "Order frequency, days since last order, tenure, RTS rate, "
                         "average order value"),
        ("Threshold",    "0.45 probability threshold for churn flag (optimised for recall)"),
        ("Output",       "Churn probability score (0-1) stored in feat_customer_ltv"),
    ], [3.5*cm, 12*cm]))
    e.append(PageBreak())
    return e


def sec_clv(s):
    e = []
    e += section_rule("6. Customer Lifetime Value Analysis", s)
    e.append(Paragraph(
        "Customer Lifetime Value (CLV) quantifies the total net revenue a customer "
        "generates over their relationship with Pargo. CLV is the single most "
        "important metric for prioritising marketing spend, retention programmes, "
        "and customer service quality tiers. Three CLV variants are computed.", s["body"]))

    e.append(Paragraph("CLV Methodology", s["h3"]))
    e.append(two_col_table([
        ("Historical CLV",
         "Total lifetime spend x margin (28%). Backward-looking, exact. "
         "Formula: SUM(order_value) * 0.28. Mean: R1,072 per customer."),
        ("Annualised CLV",
         "Historical CLV divided by tenure in years. Normalises for customer age, "
         "enabling fair comparison across cohorts. Mean: R677/year."),
        ("Predicted 1-Year CLV",
         "Forward-looking estimate: order_frequency x avg_order_value x margin x "
         "(1 - churn_probability). Mean: R526. Accounts for churn risk."),
        ("XGBoost CLV Regressor",
         "A supervised regression model (XGBoost) trained to predict historical CLV "
         "from customer features. R2 = 0.987, MAE = R50. Used to score new customers "
         "who have limited purchase history."),
    ], [3.5*cm, 12*cm]))

    e.append(Paragraph("CLV Distribution & Tiers", s["h3"]))
    e.append(Paragraph(
        "The CLV distribution is right-skewed -- the majority of customers have "
        "modest lifetime values while a small group of high-frequency buyers "
        "contribute disproportionately to total revenue:", s["body"]))
    e.append(metric_table([
        ("R203",    "Median Historical CLV"),
        ("R1,072",  "Mean Historical CLV"),
        ("69.9%",   "Top 20% Share of Total CLV"),
        ("R526",    "Mean Predicted 1yr CLV"),
    ]))
    e.append(Spacer(1, 0.2*cm))
    clv_tiers = [
        ["Tier",      "Historical CLV Range", "% of Customers", "% of Revenue", "Strategy"],
        ["VIP",       "R5,000+",              "4%",             "28%",          "Concierge, priority support"],
        ["High",      "R2,000 - R4,999",      "8%",             "22%",          "Loyalty rewards programme"],
        ["Average",   "R800 - R1,999",        "23%",            "25%",          "Upsell & cross-sell"],
        ["Below Avg", "R300 - R799",          "31%",            "18%",          "Engagement campaigns"],
        ["Low",       "< R300",               "34%",            "7%",           "Low-cost automation only"],
    ]
    hs = ParagraphStyle("ch", fontSize=8, fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_CENTER)
    cs = ParagraphStyle("cc", fontSize=8, fontName="Helvetica", textColor=DARK, alignment=TA_CENTER, leading=11)
    cd = [[Paragraph(h, hs) for h in clv_tiers[0]]]
    for row in clv_tiers[1:]:
        cd.append([Paragraph(c, cs) for c in row])
    ct = Table(cd, colWidths=[2*cm, 3.5*cm, 2.8*cm, 2.8*cm, 4.4*cm])
    ct.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), BLUE),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHTER, WHITE]),
        ("GRID",          (0,0),(-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    e.append(ct)

    e.append(Paragraph("CLV x Churn Risk Matrix", s["h3"]))
    e.append(Paragraph(
        "Combining CLV tier with churn probability creates an actionable 2x2 "
        "prioritisation matrix:", s["body"]))
    matrix = [
        ["",               "Low Churn Risk",        "High Churn Risk"],
        ["High CLV",       "Nurture (protect)",      "URGENT: Win-back immediately"],
        ["Low CLV",        "Maintain (low-cost)",    "Let go (low ROI)"],
    ]
    ms = ParagraphStyle("ms", fontSize=9, fontName="Helvetica", textColor=DARK,
                         alignment=TA_CENTER, leading=13)
    mhs = ParagraphStyle("mhs", fontSize=9, fontName="Helvetica-Bold", textColor=DARK,
                          alignment=TA_CENTER)
    md = []
    for i, row in enumerate(matrix):
        md.append([Paragraph(c, mhs if i==0 else ms) for c in row])
    mt = Table(md, colWidths=[3*cm, 6.25*cm, 6.25*cm])
    mt.setStyle(TableStyle([
        ("BACKGROUND",  (1,1),(1,1), HexColor("#ECFDF5")),
        ("BACKGROUND",  (2,1),(2,1), HexColor("#FEF2F2")),
        ("BACKGROUND",  (1,2),(1,2), HexColor("#F0F9FF")),
        ("BACKGROUND",  (2,2),(2,2), HexColor("#FAFAFA")),
        ("BACKGROUND",  (0,0),(-1,0), LIGHT),
        ("BACKGROUND",  (0,1),(0,-1), LIGHT),
        ("GRID",        (0,0),(-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING",  (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("VALIGN",      (0,0),(-1,-1), "MIDDLE"),
    ]))
    e.append(mt)
    e.append(PageBreak())
    return e


def sec_geo(s):
    e = []
    e += section_rule("7. Geographical Analysis by Province", s)
    e.append(Paragraph(
        "All customer and parcel data includes province-level geography, enabling "
        "spatial analysis of performance metrics across South Africa's nine provinces. "
        "Province is a first-class dimension captured on customers, pickup points, "
        "couriers, and tracking events.", s["body"]))

    e.append(Paragraph("Province Performance Summary", s["h3"]))
    province_data = [
        ["Province",       "Customers",  "Mean CLV", "RTS Rate", "Pickup Points", "Profile"],
        ["Gauteng",        "105,000",    "R1,250",   "14.2%",    "1,400",         "Highest volume, urban, lowest RTS"],
        ["Western Cape",   "60,000",     "R1,320",   "11.8%",    "800",           "Highest CLV, best collection rates"],
        ["KwaZulu-Natal",  "54,000",     "R980",     "16.1%",    "700",           "Strong volume, average performance"],
        ["Eastern Cape",   "30,000",     "R820",     "18.3%",    "400",           "Mid-tier, elevated RTS"],
        ["Limpopo",        "18,000",     "R650",     "19.8%",    "250",           "Rural, longest transit times"],
        ["Mpumalanga",     "15,000",     "R720",     "17.5%",    "200",           "Industrial, mixed performance"],
        ["North West",     "9,000",      "R580",     "19.1%",    "130",           "Sparse, higher exceptions"],
        ["Free State",     "6,000",      "R610",     "17.2%",    "100",           "Small market, stable"],
        ["Northern Cape",  "3,000",      "R490",     "21.0%",    "60",            "Lowest volume, highest RTS"],
    ]
    hs = ParagraphStyle("gh", fontSize=8, fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_CENTER)
    cs = ParagraphStyle("gc", fontSize=8, fontName="Helvetica", textColor=DARK, alignment=TA_CENTER, leading=11)
    ls = ParagraphStyle("gl", fontSize=8, fontName="Helvetica", textColor=DARK, alignment=TA_LEFT, leading=11)
    gd = [[Paragraph(h, hs) for h in province_data[0]]]
    for row in province_data[1:]:
        gd.append([Paragraph(row[0], ls)] + [Paragraph(c, cs) for c in row[1:5]] + [Paragraph(row[5], ls)])
    gt = Table(gd, colWidths=[2.8*cm, 2*cm, 1.8*cm, 1.8*cm, 2.2*cm, 4.9*cm])
    gt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHTER, WHITE]),
        ("GRID",          (0,0),(-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    e.append(gt)

    e.append(Paragraph("Key Geographic Insights", s["h3"]))
    insights = [
        "Gauteng and Western Cape together account for 55% of total customer base and 58% of total CLV.",
        "Western Cape has the highest mean CLV (R1,320) and lowest RTS rate (11.8%), reflecting a more urban, "
        "digitally-engaged consumer base with reliable collection behaviour.",
        "Northern Cape has the highest RTS rate (21.0%) and lowest mean CLV (R490), driven by sparse PUDO "
        "coverage (60 points) and longer transit distances creating customer abandonment.",
        "RTS rate is strongly inversely correlated with PUDO density: more pickup points = shorter dwell "
        "distances = better collection rates.",
        "Provinces with Rural profile (Limpopo, Northern Cape, North West) show transit times 40-60% longer "
        "than urban provinces, inflating SLA breach rates.",
        "A geo-expansion strategy focusing on increasing PUDO density in Limpopo and Northern Cape by 30% "
        "is projected to reduce RTS rates by 3-5 percentage points in those provinces.",
    ]
    for ins in insights:
        e.append(Paragraph(f"&#8226;  {ins}", s["bullet"]))

    e.append(Paragraph("Geographic ML Outputs", s["h3"]))
    e.append(Paragraph(
        "Province is a high-importance feature in all RTS classification models "
        "(top 5 by XGBoost gain score). The CLV model generates province-level "
        "CLV distributions visualised as choropleth maps (plots 18 and 22-23 in "
        "the ML visual portfolio). Geographic segmentation enables targeted "
        "operational interventions at a province level.", s["body"]))
    e.append(PageBreak())
    return e


def sec_platform(s):
    e = []
    e += section_rule("8. Data Platform: Snowflake & PostgreSQL", s)
    e.append(Paragraph(
        "The data platform has been designed and tested on Snowflake but all "
        "transformation SQL and DDL is standard ANSI SQL, making it fully portable "
        "to PostgreSQL for organisations that prefer an open-source deployment.", s["body"]))

    e.append(Paragraph("Snowflake Configuration", s["h3"]))
    e.append(two_col_table([
        ("Account",     "Set via SNOWFLAKE_ACCOUNT environment variable (Africa/Cape Town region for data residency)"),
        ("Database",    "PARGO_DW"),
        ("Schemas",     "RAW (ingestion), STAGING (DBT views), MARTS (DBT tables), ML_FEATURES (feature tables)"),
        ("Warehouse",   "LYRA_LOAD_WH (loading) -- auto-suspend 60 seconds, auto-resume enabled"),
        ("File Format", "Parquet with Snappy compression, vectorised scanner enabled"),
        ("Stage",       "Internal named stage @BULK_STAGE for PUT + COPY INTO batch loading"),
        ("Clustering",  "Fact tables clustered on (LOAD_YEAR, date_trunc('day', timestamp_col)) for partition pruning"),
        ("Time Travel", "7 days on all mart tables for point-in-time recovery"),
    ], [3.2*cm, 12.3*cm]))

    e.append(Paragraph("Loading Strategy", s["h3"]))
    e.append(Paragraph(
        "Data is loaded using Snowflake's staged bulk-load pattern, which achieves "
        "the best throughput for large parquet datasets:", s["body"]))
    load_steps = [
        "1. Python generates monthly parquet files partitioned by year/month.",
        "2. PUT command uploads files to the internal @BULK_STAGE with PARALLEL=8.",
        "3. COPY INTO reads from the stage using explicit column mapping and ON_ERROR=SKIP_FILE "
        "   to handle any corrupt files without failing the entire batch.",
        "4. LOAD_YEAR and LOAD_MONTH partition columns are derived from the source data "
        "   year/month fields at copy time.",
        "5. A post-load ANALYZE equivalent (table statistics refresh) is triggered automatically.",
    ]
    for step in load_steps:
        e.append(Paragraph(step, s["bullet"]))

    e.append(Paragraph("PostgreSQL Compatibility", s["h3"]))
    e.append(Paragraph(
        "All DDL and DML in this project has been written to be PostgreSQL-compatible "
        "with minimal changes. The following adaptations are required when deploying "
        "to PostgreSQL:", s["body"]))
    pg_changes = [
        ["Area",                    "Snowflake",                "PostgreSQL Equivalent"],
        ["Timestamp type",          "TIMESTAMP_NTZ",            "TIMESTAMP WITHOUT TIME ZONE"],
        ["Number type",             "NUMBER(38)",               "BIGINT or NUMERIC(20)"],
        ["Stage + COPY INTO",       "PUT + COPY INTO @stage",   "\\COPY or pg_bulkload or COPY FROM"],
        ["Parquet loading",         "Native parquet support",   "Use foreign data wrapper or import via Python pandas + psycopg2"],
        ["Clustering keys",         "CLUSTER BY (...)",         "CREATE INDEX ... BRIN for time-series tables"],
        ["Tasks (scheduling)",      "SNOWFLAKE TASKS",          "pg_cron extension or external scheduler"],
        ["Stored procedures",       "SNOWPARK Python",          "PL/pgSQL or PL/Python"],
        ["Time Travel",             "Native, 7-day default",    "Use temporal tables or audit triggers"],
    ]
    phs = ParagraphStyle("pgh", fontSize=8, fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_CENTER)
    pcs = ParagraphStyle("pgc", fontSize=8, fontName="Helvetica", textColor=DARK, alignment=TA_LEFT, leading=11)
    pd_data = [[Paragraph(h, phs) for h in pg_changes[0]]]
    for row in pg_changes[1:]:
        pd_data.append([Paragraph(c, pcs) for c in row])
    pg_t = Table(pd_data, colWidths=[3.5*cm, 4*cm, 8*cm])
    pg_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), TEAL),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHTER, WHITE]),
        ("GRID",          (0,0),(-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    e.append(pg_t)
    e.append(PageBreak())
    return e


def sec_automation(s):
    e = []
    e += section_rule("9. Snowflake Automation: Tasks & Alerts", s)
    e.append(Paragraph(
        "Three Snowflake Tasks and two Snowflake Alerts automate operational "
        "monitoring without requiring an external orchestrator. Tasks run SQL or "
        "call stored procedures on a schedule; Alerts send notifications when "
        "conditions are met.", s["body"]))

    e.append(Paragraph("Snowflake Tasks", s["h3"]))
    task_rows = [
        ["Task Name",                "Schedule",   "Action",                                                    "Purpose"],
        ["TASK_NIGHTLY_SUMMARY",     "Daily 02:00","Refresh mart_daily_ops, mart_parcel_performance",            "Keep marts current for morning reports"],
        ["TASK_HOURLY_RTS_CHECK",    "Hourly",     "Call SP_SCORE_RTS_RISK -- scores new parcels for RTS risk",  "Real-time RTS risk feed to operations"],
        ["TASK_DAILY_SLA_REPORT",    "Daily 06:00","Refresh mart_sla_breaches, send email summary via Notification","Morning SLA breach report"],
    ]
    ths = ParagraphStyle("ath", fontSize=8, fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_CENTER)
    tcs = ParagraphStyle("atc", fontSize=8, fontName="Helvetica", textColor=DARK, alignment=TA_LEFT, leading=11)
    td_data = [[Paragraph(h, ths) for h in task_rows[0]]]
    for row in task_rows[1:]:
        td_data.append([Paragraph(c, tcs) for c in row])
    tt = Table(td_data, colWidths=[3.8*cm, 2*cm, 5.5*cm, 4.2*cm])
    tt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), BLUE),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHTER, WHITE]),
        ("GRID",          (0,0),(-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    e.append(tt)

    e.append(Paragraph("Snowflake Alerts", s["h3"]))
    alert_rows = [
        ["Alert Name",           "Condition",                                "Notification"],
        ["ALERT_RTS_SPIKE",      "RTS rate > 15% in any 4-hour window",      "Email + Slack: Operations team, includes province breakdown"],
        ["ALERT_EVENT_VOL_DROP", "Tracking event volume drops > 50% vs prior 24h", "Email: Engineering team -- potential scanner outage or ETL failure"],
    ]
    ad_data = [[Paragraph(h, ths) for h in alert_rows[0]]]
    for row in alert_rows[1:]:
        ad_data.append([Paragraph(c, tcs) for c in row])
    at = Table(ad_data, colWidths=[4*cm, 6*cm, 5.5*cm])
    at.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), AMBER),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHTER, WHITE]),
        ("GRID",          (0,0),(-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    e.append(at)

    e.append(Paragraph("Snowpark ML Stored Procedures", s["h3"]))
    e.append(Paragraph(
        "Two Snowpark stored procedures allow ML inference to run entirely inside "
        "Snowflake without data leaving the warehouse:", s["body"]))
    e.append(two_col_table([
        ("SP_SCORE_RTS_RISK",
         "Accepts a batch of parcel IDs. Loads the trained XGBoost model from a "
         "Snowflake stage, runs prediction, and writes scores back to a RTS_SCORES "
         "table. Called hourly by TASK_HOURLY_RTS_CHECK."),
        ("SP_SEGMENT_CUSTOMERS",
         "Runs K-Means clustering (k=5) on current feat_customer_ltv data using "
         "Snowpark ML. Updates the CUSTOMER_SEGMENT column in DIM_CUSTOMERS weekly."),
    ], [3.8*cm, 11.7*cm]))
    e.append(PageBreak())
    return e


def sec_insights(s):
    e = []
    e += section_rule("10. Key Business Insights & Findings", s)

    e.append(Paragraph("Operational Performance", s["h3"]))
    e.append(metric_table([
        ("14.8%",  "Overall RTS Rate"),
        ("87.3%",  "SLA Compliance"),
        ("3.2 days","Avg Dwell Time"),
        ("R85.40",  "Avg Delivery Cost"),
    ]))
    e.append(Spacer(1, 0.2*cm))
    op_insights = [
        "The overall RTS rate of 14.8% is above the industry target of 10%. The top contributing "
        "factors are long dwell times (parcels sitting uncollected for 5+ days) and elevated "
        "exception rates in Northern Cape and Limpopo.",
        "SLA compliance at 87.3% means 1 in 8 parcels misses its contracted delivery window. "
        "The primary SLA breach driver is courier transit time variance, particularly on "
        "inter-provincial routes.",
        "Average delivery cost of R85.40 varies significantly: Western Cape R78, Northern Cape R112 -- "
        "reflecting the high cost of servicing sparse rural markets.",
    ]
    for ins in op_insights:
        e.append(Paragraph(f"&#8226;  {ins}", s["bullet"]))

    e.append(Paragraph("Retailer Insights", s["h3"]))
    retailer_insights = [
        "Fashion retailers (led by Bash, Zando, Superbalist) account for 42% of all parcel volume "
        "but have above-average RTS rates (17.2%) due to higher customer optionality in fashion.",
        "Electronics retailers show the lowest RTS rates (9.1%) -- customers are motivated to "
        "collect high-value items promptly.",
        "The top 10 retailers by volume represent 61% of all parcels, indicating high customer "
        "concentration risk for Pargo.",
    ]
    for ins in retailer_insights:
        e.append(Paragraph(f"&#8226;  {ins}", s["bullet"]))

    e.append(Paragraph("ML Model Value Quantification", s["h3"]))
    e.append(Paragraph(
        "Assuming the RTS classification model enables intervention on 30% of predicted "
        "high-risk parcels and reduces RTS conversion by 50% for those parcels:", s["body"]))
    value_table = [
        ["Metric",                    "Value",      "Assumption"],
        ["Annual parcels",            "10.1M",      "Based on 36-month growth trend"],
        ["RTS parcels (14.8%)",       "1.49M",      "Current baseline"],
        ["Intervened parcels",        "447K",        "30% of predicted high-risk"],
        ["RTS prevented (50%)",       "224K",        "Model-driven intervention"],
        ["Cost saving per RTS",       "R45",         "Return shipping + admin cost"],
        ["Annual saving",             "R10.1M",      "224K x R45"],
        ["Model maintenance cost",    "R180K/yr",    "Monthly retraining, infrastructure"],
        ["Net annual ROI",            "R9.9M",       "56x return on ML investment"],
    ]
    vs = ParagraphStyle("vsh", fontSize=8, fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_CENTER)
    vc = ParagraphStyle("vsc", fontSize=8, fontName="Helvetica", textColor=DARK, alignment=TA_LEFT, leading=11)
    vd = [[Paragraph(h, vs) for h in value_table[0]]]
    for row in value_table[1:]:
        vd.append([Paragraph(c, vc) for c in row])
    vt = Table(vd, colWidths=[5*cm, 3*cm, 7.5*cm])
    vt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), GREEN),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHTER, WHITE]),
        ("BACKGROUND",    (0,-1),(-1,-1), HexColor("#ECFDF5")),
        ("GRID",          (0,0),(-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    e.append(vt)

    e.append(Paragraph("Recommendations", s["h3"]))
    recs = [
        ("Immediate", "Deploy the XGBoost RTS classifier to production. Integrate scores into "
         "the dispatcher's daily workflow via the Snowflake Tasks pipeline."),
        ("30 Days", "Expand PUDO coverage in Northern Cape and Limpopo by 30 points each. "
         "Model projections show 3-5pp RTS improvement in these provinces."),
        ("90 Days", "Launch CLV-based retention programme targeting High CLV / High Churn "
         "segment (approximately 24,000 customers). Estimated CLV preservation: R28M."),
        ("6 Months", "Build retailer-facing analytics portal powered by mart_retailer_scorecard. "
         "Give retail partners visibility into their own RTS and SLA performance."),
    ]
    e.append(two_col_table(recs, [2.5*cm, 13*cm]))

    e.append(Spacer(1, 1*cm))
    e.append(hr(HexColor("#E2E8F0"), 0.5))
    e.append(Paragraph(
        "This portfolio was built as a demonstration of end-to-end data warehouse "
        "engineering capability. All data is synthetic but structurally and "
        "statistically representative of real-world last-mile logistics operations. "
        "The platform is ready for deployment on Snowflake (primary) or PostgreSQL "
        "(open-source alternative) with minimal configuration changes.",
        ParagraphStyle("disc", fontSize=9, textColor=MUTED, fontName="Helvetica-Oblique",
                       alignment=TA_JUSTIFY, spaceAfter=6, leading=13)))
    return e


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "pargo_ebook_portfolio.pdf"

    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2.5*cm,
        topMargin=2.5*cm, bottomMargin=2.2*cm,
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

    doc.build(elements, canvasmaker=NumberedCanvas)
    size_kb = out.stat().st_size // 1024
    print(f"  Saved: {out.name} ({size_kb}KB)")
    print(f"  Location: {out.resolve()}")


if __name__ == "__main__":
    print("Building Pargo Parcels Portfolio Ebook...")
    main()
    print("Done.")
