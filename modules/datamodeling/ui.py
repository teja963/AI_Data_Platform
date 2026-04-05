import streamlit as st
import pandas as pd
from core.components import render_ai_chat
import random
from datetime import datetime

# =========================================================
# 🔹 ENTRY POINT
# =========================================================

def render_datamodeling():

    render_title("📊 Data Modelling")

    tab_labels = [
        "Fundamentals",
        "Dimensional Modeling",
        "Architecture",
        "Distributed",
        "Interview Mode"
    ]

    # =====================================================
    # 🔥 STEP 1: READ FROM URL
    # =====================================================
    query_params = st.query_params

    selected = query_params.get("dm_tab", "Fundamentals")

    if selected not in tab_labels:
        selected = "Fundamentals"

    # =====================================================
    # 🔥 STEP 2: TAB-LIKE UI (REPLACES st.tabs)
    # =====================================================
    selected_tab = st.radio(
        "",
        tab_labels,
        index=tab_labels.index(selected),
        horizontal=True
    )

    # =====================================================
    # 🔥 STEP 3: UPDATE URL (CRITICAL)
    # =====================================================
    st.query_params["dm_tab"] = selected_tab

    # =====================================================
    # 🔥 STEP 4: RENDER CONTENT (NOW WORKS PERFECTLY)
    # =====================================================
    if selected_tab == "Fundamentals":
        show_fundamentals()

    elif selected_tab == "Dimensional Modeling":
        show_dimensional_modeling()

    elif selected_tab == "Architecture":
        show_architecture()

    elif selected_tab == "Distributed":
        show_distributed_modeling()

    elif selected_tab == "Interview Mode":
        show_interview_mode()


# =========================================================
# 🔹 UI COMPONENTS (FULL CONTROL)
# =========================================================

def render_title(text):
    st.markdown(f"<h2>{text}</h2>", unsafe_allow_html=True)

def render_subtitle(text):
    st.markdown(f"<h4 style='margin-top:12px;margin-bottom:6px'>{text}</h4>", unsafe_allow_html=True)

def render_box(text, color="#E8F4FD"):
    st.markdown(
        f"<div class='dm-box' style='padding:10px 12px;border-radius:0;background:{color};margin-bottom:8px'>{text}</div>",
        unsafe_allow_html=True
    )

def render_df(data, columns):
    df = pd.DataFrame(data, columns=columns)
    st.dataframe(df, use_container_width=True, hide_index=True)

def render_side_by_side(title1, data1, title2, data2, columns):
    col1, col2 = st.columns(2)

    with col1:
        render_subtitle(title1)
        render_df(data1, columns)

    with col2:
        render_subtitle(title2)
        render_df(data2, columns)

def render_code(text):
    st.markdown(f"<pre>{text}</pre>", unsafe_allow_html=True)


# =========================================================
# 🔹 ARCHITECTURE HELPERS
# =========================================================

ARCHITECTURE_TONES = {
    "blue": {"fill": "#E9EEF4", "active_fill": "#DCE5EF", "border": "#6B7C93", "text": "#1F2937"},
    "green": {"fill": "#EDF3EA", "active_fill": "#DEEAD8", "border": "#738B6C", "text": "#1F2937"},
    "amber": {"fill": "#F8F1E6", "active_fill": "#F1E4CF", "border": "#B18D59", "text": "#1F2937"},
    "slate": {"fill": "#F3F4F6", "active_fill": "#E5E7EB", "border": "#9AA4B2", "text": "#1F2937"},
    "violet": {"fill": "#F3EEF6", "active_fill": "#E8DEEF", "border": "#8C7A99", "text": "#1F2937"},
    "rose": {"fill": "#F8EDEE", "active_fill": "#F2DDDF", "border": "#B07A82", "text": "#1F2937"},
    "teal": {"fill": "#ECF3F2", "active_fill": "#DEE9E7", "border": "#6D8A86", "text": "#1F2937"},
}


def render_html_panel(body_html, padding=14):
    st.markdown(
        f"""
        <div class='dm-box' style="
            border:1px solid #d1d5db;
            border-radius:0;
            padding:{padding}px;
            box-shadow:none;
            margin-bottom:16px;
        ">
            {body_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def build_architecture_box(
    title,
    details=None,
    tone="blue",
    min_height=0,
    align="center",
    title_size=14,
    active=False,
    subtle=False,
):
    palette = ARCHITECTURE_TONES[tone]
    fill = palette["active_fill"] if active else palette["fill"]
    border = palette["border"]
    text = palette["text"]
    detail_lines = details or []

    if isinstance(detail_lines, str):
        detail_lines = [detail_lines]

    min_height_style = f"min-height:{min_height}px;" if min_height else ""
    opacity = "0.6" if subtle else "1"
    border_width = "3px" if active else "1.5px"
    accent = "box-shadow: inset 0 0 0 1px rgba(31, 41, 55, 0.05);" if active else ""
    detail_html = "".join(
        (
            f"<div style='font-size:11px;font-weight:500;line-height:1.35;"
            f"color:{text};margin-top:4px;opacity:0.92'>{line}</div>"
        )
        for line in detail_lines
        if line
    )

    return (
        f"<div style='background:{fill};border:{border_width} solid {border};border-radius:0;"
        f"padding:10px 12px;box-sizing:border-box;text-align:{align};{min_height_style}"
        f"opacity:{opacity};{accent}'>"
        f"<div style='font-size:{title_size}px;font-weight:700;color:{text};line-height:1.25'>{title}</div>"
        f"{detail_html}"
        f"</div>"
    )


def build_flow_chip(label, tone="slate", active=False, subtle=False):
    palette = ARCHITECTURE_TONES[tone]
    fill = palette["active_fill"] if active else palette["fill"]
    border = palette["border"]
    text = palette["text"]
    shadow = "box-shadow: inset 0 0 0 1px rgba(31, 41, 55, 0.05);" if active else ""
    border_width = "3px" if active else "1.5px"
    opacity = "0.58" if subtle else "1"
    return (
        f"<div style='display:inline-block;background:{fill};border:{border_width} solid {border};"
        f"border-radius:0;padding:7px 10px;font-size:12px;font-weight:700;color:{text};"
        f"margin:2px 4px;opacity:{opacity};{shadow}'>{label}</div>"
    )


def build_arrow(symbol="→", size=22):
    return (
        f"<div style='text-align:center;color:#64748b;font-size:{size}px;"
        f"font-weight:700;line-height:1.1'>{symbol}</div>"
    )


def build_inline_arrow(symbol="→", size=18):
    return (
        f"<span style='display:inline-block;color:#64748b;font-size:{size}px;"
        f"font-weight:700;line-height:1;margin:0 6px;vertical-align:middle;'>{symbol}</span>"
    )


def build_domain_box(name, product, tone):
    return build_architecture_box(
        name,
        [
            product,
            "Owns data end-to-end",
            "Produces + maintains",
        ],
        tone=tone,
        min_height=118,
    )


def render_highlight_table(headers, rows, highlight_index=None, highlight_tone="green"):
    tone = ARCHITECTURE_TONES[highlight_tone]
    header_html = "".join(
        f"<th style='border:1px solid #cbd5e1;padding:8px 10px;text-align:left;background:#e5e7eb;color:#111827;'>{header}</th>"
        for header in headers
    )

    row_html = []
    for idx, row in enumerate(rows):
        background = tone["active_fill"] if idx == highlight_index else "#ffffff"
        weight = "700" if idx == highlight_index else "500"
        row_html.append(
            "<tr>"
            + "".join(
                f"<td style='border:1px solid #d1d5db;padding:8px 10px;background:{background};"
                f"font-size:12px;font-weight:{weight};color:#1f2937;'>{value}</td>"
                for value in row
            )
            + "</tr>"
        )

    st.markdown(
        "<table style='width:100%;border-collapse:collapse;margin:8px 0 14px 0;'>"
        + f"<thead><tr>{header_html}</tr></thead>"
        + f"<tbody>{''.join(row_html)}</tbody></table>",
        unsafe_allow_html=True,
    )


def render_warehouse_architecture_workspace():
    st.markdown("### 7.5 Data Warehouse Architecture & Advanced Modeling")
    st.caption("Enterprise warehouse layers, data mart design, ETL modeling, and operational data quality patterns.")

    with st.container(border=True):
        st.markdown("#### Architecture Simulator")
        c1, c2, c3, c4, c5 = st.columns(5)

        source_system = c1.selectbox(
            "Primary Source",
            ["ERP", "CRM", "Application APIs", "Event Logs"],
            key="dm_arch_source_system",
        )
        warehouse_style = c2.selectbox(
            "Warehouse Style",
            ["Kimball Bus", "Layered Warehouse", "Hybrid"],
            key="dm_arch_warehouse_style",
        )
        load_pattern = c3.selectbox(
            "Load Pattern",
            ["Daily Batch", "Micro-Batch", "Streaming CDC"],
            key="dm_arch_load_pattern",
        )
        order_stage = c4.selectbox(
            "Order Fact Stage",
            ["Created", "Packed", "Shipped", "Delivered"],
            key="dm_arch_order_stage",
        )
        issue_mode = c5.selectbox(
            "Operational Issue",
            ["Healthy Load", "Late Dimension", "Late Fact", "Reconciliation Gap"],
            key="dm_arch_issue_mode",
        )

    action_map = {
        "Healthy Load": "Land the source data, run ETL, and publish marts without remediation.",
        "Late Dimension": "Create a placeholder dimension key, load the fact idempotently, then update the dimension later.",
        "Late Fact": "Reprocess the affected date partition so historical aggregates stay correct.",
        "Reconciliation Gap": "Pause downstream trust, compare counts/hashes, and investigate the mismatch before publish.",
    }
    source_detail_map = {
        "ERP": "ERP | order processing | finance postings",
        "CRM": "CRM | customer profiles | service activity",
        "Application APIs": "REST APIs | operational extracts | partner feeds",
        "Event Logs": "Application events | clickstream | operational logs",
    }
    staging_map = {
        "Daily Batch": ("Staging Layer", "Raw landing | batch window | minimal transforms"),
        "Micro-Batch": ("Staging Layer", "Incremental landing | short SLA | dedupe window"),
        "Streaming CDC": ("CDC Landing", "Continuous capture | replayable log | checkpointing"),
    }
    extract_map = {
        "Daily Batch": "Batch Extract",
        "Micro-Batch": "Incremental Extract",
        "Streaming CDC": "CDC Extract",
    }
    style_explanation = {
        "Kimball Bus": "Conformed marts are primary and the bus is emphasized.",
        "Layered Warehouse": "Enterprise warehouse and presentation layers are emphasized.",
        "Hybrid": "Core warehouse and conformed marts are both emphasized.",
    }
    stage_rows = {
        "Created": ["1001", "20240101", "", "", "1000"],
        "Packed": ["1001", "20240101", "", "", "1000"],
        "Shipped": ["1001", "20240101", "20240103", "", "1000"],
        "Delivered": ["1001", "20240101", "20240103", "20240105", "1000"],
    }
    mart_active = warehouse_style in {"Kimball Bus", "Hybrid"}
    core_active = warehouse_style in {"Layered Warehouse", "Hybrid"}
    bus_active = warehouse_style in {"Kimball Bus", "Hybrid"}
    stage_label, stage_detail = staging_map[load_pattern]
    source_detail = source_detail_map[source_system]
    late_dimension = issue_mode == "Late Dimension"
    late_fact = issue_mode == "Late Fact"
    recon_gap = issue_mode == "Reconciliation Gap"
    healthy_load = issue_mode == "Healthy Load"

    render_box(
        (
            f"<b>Current Simulation:</b> {source_system} lands via <b>{load_pattern}</b> into a "
            f"<b>{warehouse_style}</b> pattern. Current issue mode: <b>{issue_mode}</b>. "
            f"{style_explanation[warehouse_style]} {action_map[issue_mode]}"
        ),
        "#F8FAFC"
    )

    top_left, top_right = st.columns(2)

    with top_left:
        st.markdown("#### 1. Data Mart Design")
        mart_html = (
            build_architecture_box(
                "Data Mart = subject-specific subset of a DW for a department.",
                tone="blue",
                active=True,
            )
            + "<div style='max-width:290px;margin:12px auto 10px auto;'>"
            + build_architecture_box(
                "Enterprise Data Warehouse",
                ["Integrated subject areas", "Shared dimensional definitions"],
                tone="slate",
                active=core_active,
                subtle=not core_active,
            )
            + "</div>"
            + build_arrow("↓")
            + "<div style='display:flex;gap:12px;justify-content:space-between;flex-wrap:wrap;margin-top:8px;'>"
            + "<div style='flex:1;min-width:155px;'>"
            + build_architecture_box(
                "Sales Mart",
                ["Star schema" if mart_active else "Published from presentation layer"],
                tone="green",
                active=mart_active,
                subtle=not mart_active,
            )
            + "<div style='text-align:center;margin-top:8px;'>"
            + build_flow_chip("Customer", "slate", active=mart_active, subtle=not mart_active)
            + build_flow_chip("Sales_Fact", "blue", active=True)
            + build_flow_chip("Product", "slate", active=mart_active, subtle=not mart_active)
            + "</div></div>"
            + "<div style='flex:1;min-width:155px;'>"
            + build_architecture_box(
                "Marketing Mart",
                ["Campaign reporting"],
                tone="amber",
                active=mart_active,
                subtle=not mart_active,
            )
            + "</div>"
            + "<div style='flex:1;min-width:155px;'>"
            + build_architecture_box(
                "Finance Mart",
                ["Department consumption"],
                tone="slate",
                active=mart_active,
                subtle=not mart_active,
            )
            + "</div>"
            + "</div>"
        )
        render_html_panel(mart_html)

    with top_right:
        st.markdown("#### 2. Bus Architecture (Kimball Bus)")
        bus_html = (
            build_architecture_box(
                "Multiple data marts share conformed dimensions.",
                tone="green",
                active=bus_active,
                subtle=not bus_active,
            )
            + "<div style='margin-top:10px;'>"
            + build_architecture_box(
                "Conformed Dims: Date | Product | Customer",
                tone="amber",
                active=bus_active,
                subtle=not bus_active,
            )
            + "</div>"
            + "<div style='display:flex;gap:16px;justify-content:space-between;flex-wrap:wrap;margin-top:14px;'>"
            + "<div style='flex:1;min-width:150px;text-align:center;'>"
            + build_architecture_box("Sales Mart", tone="blue", active=bus_active, subtle=not bus_active)
            + "<div style='font-size:11px;color:#475569;margin-top:4px;'>Sales_Fact</div>"
            + "</div>"
            + "<div style='flex:1;min-width:150px;text-align:center;'>"
            + build_architecture_box("Inventory Mart", tone="green", active=bus_active, subtle=not bus_active)
            + "<div style='font-size:11px;color:#475569;margin-top:4px;'>Inventory_Fact</div>"
            + "</div>"
            + "<div style='flex:1;min-width:150px;text-align:center;'>"
            + build_architecture_box("Shipment Mart", tone="slate", active=bus_active, subtle=not bus_active)
            + "<div style='font-size:11px;color:#475569;margin-top:4px;'>Shipment_Fact</div>"
            + "</div>"
            + "</div>"
            + "<div style='margin-top:12px;font-size:12px;font-weight:700;color:#374151;'>"
            + "Key: Shared dimensions ensure consistent reporting across all marts."
            + "</div>"
        )
        render_html_panel(bus_html)

    middle_left, middle_right = st.columns(2)

    with middle_left:
        st.markdown("#### 3-6. Data Warehouse Layers")
        layer_blocks = [
            ("Source Systems", source_detail, "slate", True, False),
            (stage_label, stage_detail, "amber", True, False),
            ("Core Data Warehouse", "Facts + dimensions | single source of truth", "blue", core_active or recon_gap, not (core_active or recon_gap)),
            ("Presentation Layer", "Data marts | aggregates | BI semantic outputs", "green", mart_active, not mart_active),
            ("BI / Analytics Tools", "PowerBI | Tableau | Looker | Superset", "slate", True, False),
        ]
        layer_html_parts = []
        for index, (title, detail, tone, active, subtle) in enumerate(layer_blocks):
            layer_html_parts.append(
                "<div style='display:grid;grid-template-columns:1.15fr 1fr;gap:10px;align-items:center;'>"
                + build_architecture_box(title, tone=tone, active=active, subtle=subtle)
                + f"<div style='font-size:12px;color:#475569;line-height:1.4'>{detail}</div>"
                + "</div>"
            )
            if index < len(layer_blocks) - 1:
                layer_html_parts.append(build_arrow("↓", size=18))
        render_html_panel("".join(layer_html_parts))

    with middle_right:
        st.markdown("#### 7. Data Modeling for ETL")
        etl_html = (
            "<div style='display:grid;grid-template-columns:0.9fr 1.1fr;gap:14px;align-items:start;'>"
            + "<div>"
            + build_architecture_box("Source Systems", [source_system], tone="slate", active=True)
            + build_arrow("↓", size=18)
            + build_architecture_box(extract_map[load_pattern], [load_pattern], tone="blue", active=True)
            + build_arrow("↓", size=18)
            + build_architecture_box(
                "Transform",
                ["Business rules | surrogate keys" if not recon_gap else "Business rules | mismatch investigation"],
                tone="amber",
                active=True,
            )
            + build_arrow("↓", size=18)
            + build_architecture_box("Load", ["Idempotent merge" if late_fact or late_dimension else "Publish tables"], tone="green", active=True)
            + "</div>"
            + "<div>"
            + build_architecture_box("Sources", [source_detail], tone="slate", active=True)
            + "<div style='margin:6px 0'>"
            + build_architecture_box(stage_label, [stage_detail], tone="amber", active=True)
            + "</div>"
            + build_architecture_box(
                "Transform Logic",
                ["Late-arriving dim handling" if late_dimension else "Conform and validate"],
                tone="blue",
                active=True,
            )
            + "<div style='margin:6px 0'>"
            + build_architecture_box(
                "Dimension Tables",
                ["Placeholder row" if late_dimension else "Conformed dimensions"],
                tone="green",
                active=late_dimension or healthy_load,
                subtle=late_fact or recon_gap,
            )
            + "</div>"
            + build_architecture_box(
                "Fact Tables",
                ["Partition replay" if late_fact else "Facts at declared grain"],
                tone="slate",
                active=late_fact or healthy_load,
                subtle=late_dimension,
            )
            + "</div></div>"
            + "<div style='margin-top:14px;font-size:12px;font-weight:700;color:#475569;'>Example Transform:</div>"
            + "<div style='margin-top:6px;padding:10px;border-radius:0;background:#f8fafc;border:1px solid #d1d5db;"
            + "font-family:monospace;font-size:12px;'>"
            + "order_id | product | price<br>date_id | product_id | sales_amt"
            + "</div>"
        )
        render_html_panel(etl_html)

    bottom_left, bottom_right = st.columns(2)

    with bottom_left:
        st.markdown("#### 8. Slowly Changing Facts")
        stage_tones = {
            "Created": "blue",
            "Packed": "amber",
            "Shipped": "slate",
            "Delivered": "green",
        }
        stage_html = "".join(
            build_flow_chip(stage_name, stage_tones[stage_name], active=stage_name == order_stage)
            for stage_name in ["Created", "Packed", "Shipped", "Delivered"]
        )
        render_html_panel(
            build_architecture_box(
                "Fact values updated when business events evolve (order pipeline).",
                tone="amber",
                active=True,
            )
            + "<div style='text-align:center;margin:12px 0 8px 0;'>"
            + stage_html
            + "</div>"
            + "<div style='font-size:12px;color:#475569;'>"
            + "Often used with accumulating snapshot fact tables."
            + "</div>"
        )
        render_df(
            [stage_rows[order_stage]],
            ["order_id", "order_date", "ship_date", "delivery_date", "amount"]
        )

    with bottom_right:
        st.markdown("#### 9. Handling Late Arriving Facts")
        load_ok_tone = "green" if healthy_load else "slate"
        placeholder_tone = "amber" if late_dimension else "slate"
        update_tone = "green" if late_dimension or late_fact else "slate"
        late_fact_html = (
            build_architecture_box(
                "Fact arrives before dim -> placeholder -> update later.",
                tone="amber",
                active=late_dimension or late_fact or healthy_load,
            )
            + "<div style='text-align:center;margin-top:12px;'>"
            + build_flow_chip("Fact Arrives", "blue", active=True)
            + build_inline_arrow("→", size=18)
            + build_flow_chip("Check Dim", "amber", active=late_dimension or healthy_load, subtle=recon_gap)
            + build_inline_arrow("→", size=18)
            + build_flow_chip("Load OK", load_ok_tone, active=healthy_load, subtle=late_dimension or late_fact or recon_gap)
            + build_inline_arrow("→", size=18)
            + build_flow_chip("Placeholder", placeholder_tone, active=late_dimension, subtle=healthy_load or late_fact or recon_gap)
            + build_inline_arrow("→", size=18)
            + build_flow_chip("Update", update_tone, active=late_dimension or late_fact, subtle=healthy_load or recon_gap)
            + "</div>"
        )
        render_html_panel(late_fact_html)

        if healthy_load:
            render_box("Dimension already exists. Fact lands with the correct surrogate key.", "#E6F4EA")
            render_df([["101", "101", "John"]], ["customer_sk", "customer_id", "name"])
        elif late_dimension:
            render_box(
                "Placeholder dimension keeps the fact load idempotent until the real dimension arrives.",
                "#FFF4E5"
            )
            render_df([["999", "101", "Unknown -> John"]], ["customer_sk", "customer_id", "name"])
        elif late_fact:
            render_box("Fact arrived after the partition closed, so the affected partition needs replay.", "#FFF4E5")
            render_df([["2024-01-01", "reprocess partition", "refresh gold"]], ["event_date", "action", "downstream"])
        else:
            render_box("Reconciliation mismatch found. Validate counts and freeze publish until corrected.", "#FDECEA")
            render_df([["sales_fact", "source 100000", "warehouse 99996"]], ["table_name", "source", "warehouse"])

    st.markdown("#### 10. Data Reconciliation Models")
    recon_checks_html = (
        build_architecture_box(
            "Ensures data consistency between source and warehouse.",
            tone="blue",
            active=True,
        )
        + "<div style='text-align:center;margin:12px 0;'>"
        + build_flow_chip("Source", "slate", active=True)
        + build_inline_arrow("→", size=18)
        + build_flow_chip("ETL", "amber", active=True)
        + build_inline_arrow("→", size=18)
        + build_flow_chip("Warehouse", "blue", active=True if not recon_gap else False, subtle=not recon_gap)
        + build_flow_chip("Mismatch", "rose", active=recon_gap, subtle=not recon_gap)
        + "</div>"
        + "<div style='text-align:center;margin-top:8px;'>"
        + build_flow_chip("Row Counts", "green", active=recon_gap)
        + build_flow_chip("Aggregated Totals", "slate", active=recon_gap)
        + build_flow_chip("Hash Checks", "amber", active=recon_gap)
        + build_flow_chip("Business Rules", "blue", active=True)
        + "</div>"
    )
    render_html_panel(recon_checks_html)

    recon_rows = [
        ["orders", "100000", "100000" if issue_mode != "Reconciliation Gap" else "99996"],
        ["customers", "50000", "50000" if issue_mode != "Reconciliation Gap" else "49998"],
    ]
    render_df(recon_rows, ["table_name", "source_count", "warehouse_count"])

    if issue_mode == "Reconciliation Gap":
        render_box("Mismatch detected -> triggers investigation before BI publish.", "#FDECEA")
    else:
        render_box("Counts and business checks are aligned. Publish to marts and dashboards is safe.", "#E6F4EA")


def render_lakehouse_architecture_workspace():
    st.markdown("### 7.6 Lakehouse Data Modeling")
    st.caption("Unified architecture combining data lake flexibility with data warehouse reliability on object storage.")

    with st.container(border=True):
        st.markdown("#### Lakehouse Simulator")
        c1, c2, c3, c4, c5 = st.columns(5)

        ingestion_mode = c1.selectbox(
            "Ingestion Mode",
            ["Streaming", "Batch", "Hybrid"],
            key="dm_lakehouse_ingestion_mode",
        )
        active_layer = c2.selectbox(
            "Active Layer",
            ["Bronze", "Silver", "Gold"],
            key="dm_lakehouse_active_layer",
        )
        issue_mode = c3.selectbox(
            "Late Data Scenario",
            ["Healthy Load", "Late Dimension", "Late Fact", "Backfill", "Duplicate Replay"],
            key="dm_lakehouse_issue_mode",
        )
        consumer_mode = c4.selectbox(
            "Primary Consumer",
            ["BI Dashboards", "Data Science / ML", "Adhoc SQL Queries", "Real-time Analytics"],
            key="dm_lakehouse_consumer_mode",
        )
        table_format = c5.selectbox(
            "Open Table Format",
            ["Delta", "Iceberg", "Hudi"],
            key="dm_lakehouse_table_format",
        )
    issue_action_map = {
        "Healthy Load": "Write once through Bronze -> Silver -> Gold and publish clean outputs.",
        "Late Dimension": "Use a placeholder dimension, then backfill the clean dimensional record.",
        "Late Fact": "Replay the affected partition and re-aggregate downstream Gold tables.",
        "Backfill": "Run a bounded backfill window with idempotent MERGE logic.",
        "Duplicate Replay": "Enforce idempotent writes so retries do not create duplicate facts.",
    }
    streaming_active = ingestion_mode in {"Streaming", "Hybrid"}
    batch_active = ingestion_mode in {"Batch", "Hybrid"}
    bronze_active = active_layer == "Bronze"
    silver_active = active_layer == "Silver"
    gold_active = active_layer == "Gold"
    consumer_options = [
        "BI Dashboards",
        "Data Science / ML",
        "Adhoc SQL Queries",
        "Real-time Analytics",
    ]

    render_box(
        (
            f"<b>Current Simulation:</b> {ingestion_mode} ingestion into the <b>{active_layer}</b> layer "
            f"using <b>{table_format}</b>. Selected recovery pattern: <b>{issue_mode}</b>. "
            f"{issue_action_map[issue_mode]}"
        ),
        "#F8FAFC"
    )

    sources_html = "".join(
        f"<div style='margin-bottom:8px'>{build_architecture_box(label, tone=tone, active=is_active, subtle=not is_active)}</div>"
        for label, tone, is_active in [
            ("OLTP Databases", "blue", batch_active),
            ("SaaS APIs", "green", batch_active),
            ("Application Logs", "amber", streaming_active),
            ("IoT Streams", "slate", streaming_active),
            ("Files / CSV / JSON", "slate", batch_active),
        ]
    )

    lakehouse_html = (
        "<div style='display:flex;gap:10px;align-items:flex-start;flex-wrap:nowrap;overflow-x:auto;'>"
        + "<div style='flex:1.05;min-width:220px;'>"
        + "<div style='font-size:15px;font-weight:800;color:#374151;margin-bottom:8px;'>SOURCES</div>"
        + sources_html
        + "</div>"
        + "<div style='padding-top:145px;'>"
        + build_arrow("→", size=28)
        + "</div>"
        + "<div style='flex:1.65;min-width:300px;'>"
        + "<div style='font-size:15px;font-weight:800;color:#374151;margin-bottom:8px;'>INGESTION + STORAGE</div>"
        + "<div style='border:1px solid #d1d5db;border-radius:0;padding:12px;background:#fafafa;'>"
        + "<div style='font-size:15px;font-weight:800;color:#374151;text-align:center;'>INGESTION PIPELINE</div>"
        + "<div style='display:flex;gap:10px;margin-top:12px;'>"
        + "<div style='flex:1;'>"
        + build_architecture_box(
            "Streaming",
            ["Kafka | Spark Streaming", "Flink | Debezium CDC"],
            tone="blue",
            min_height=120,
            active=streaming_active,
            subtle=not streaming_active,
        )
        + "</div>"
        + "<div style='flex:1;'>"
        + build_architecture_box(
            "Batch",
            ["Airflow | Batch ETL", "Spark Jobs | dbt"],
            tone="green",
            min_height=120,
            active=batch_active,
            subtle=not batch_active,
        )
        + "</div>"
        + "</div>"
        + "<div style='margin-top:12px;'>"
        + build_architecture_box(
            "STORAGE LAYER",
            ["Amazon S3 | Azure ADLS | Google GCS"],
            tone="amber",
            active=True,
        )
        + "</div>"
        + "</div>"
        + "</div>"
        + "<div style='padding-top:145px;'>"
        + build_arrow("→", size=28)
        + "</div>"
        + "<div style='flex:1.45;min-width:280px;'>"
        + "<div style='font-size:15px;font-weight:800;color:#374151;margin-bottom:8px;'>LAKEHOUSE LAYER</div>"
        + "<div style='border:1px solid #d1d5db;border-radius:0;padding:12px;background:#fafafa;'>"
        + "<div style='font-size:15px;font-weight:800;color:#374151;text-align:center;'>LAKEHOUSE TABLE LAYER</div>"
        + "<div style='font-size:11px;color:#475569;text-align:center;margin-top:4px;'>"
        + f"{table_format} format | ACID | Schema Evolution"
        + "</div>"
        + "<div style='margin-top:12px;'>"
        + build_architecture_box(
            "BRONZE",
            ["Raw | append-only", "Landing zone"],
            tone="amber",
            active=bronze_active or issue_mode == "Duplicate Replay",
            subtle=not (bronze_active or issue_mode == "Duplicate Replay"),
        )
        + "</div>"
        + "<div style='margin-top:10px;'>"
        + build_architecture_box(
            "SILVER",
            ["Cleaned | deduped | conformed", "Late-dimension fixes"],
            tone="slate",
            active=silver_active or issue_mode in {"Late Dimension", "Duplicate Replay"},
            subtle=not (silver_active or issue_mode in {"Late Dimension", "Duplicate Replay"}),
        )
        + "</div>"
        + "<div style='margin-top:10px;'>"
        + build_architecture_box(
            "GOLD",
            ["Facts / dims", "Star schema | BI / ML ready"],
            tone="green",
            active=gold_active or issue_mode in {"Late Fact", "Backfill"},
            subtle=not (gold_active or issue_mode in {"Late Fact", "Backfill"}),
        )
        + "</div>"
        + "</div>"
        + "</div>"
        + "<div style='padding-top:145px;'>"
        + build_arrow("→", size=28)
        + "</div>"
        + "<div style='flex:1.15;min-width:250px;'>"
        + "<div style='font-size:15px;font-weight:800;color:#374151;margin-bottom:8px;'>CONSUMERS</div>"
        + "<div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;'>"
        + "".join(
            build_architecture_box(
                option,
                ["active consumer"] if consumer_mode == option else None,
                tone="green" if option in {"BI Dashboards", "Real-time Analytics"} else "blue",
                min_height=80,
                active=consumer_mode == option,
                subtle=consumer_mode != option,
            )
            for option in consumer_options
        )
        + "</div>"
        + "<div style='margin-top:10px;'>"
        + build_architecture_box(
            "Serving Tools",
            ["Tableau | PowerBI | Spark SQL | Trino"],
            tone="slate",
            active=True,
        )
        + "</div>"
        + "</div>"
    )
    render_html_panel(lakehouse_html)

    st.markdown("#### Why Lakehouse is Needed")
    render_df(
        [
            [
                "Organizations store huge volumes of raw data",
                "Data lakes store raw data but lack governance",
                "Lakehouse adds ACID transactions and schema management",
            ],
            [
                "Data warehouses are expensive for large datasets",
                "Warehouses duplicate data from lakes",
                "Lakehouse uses single unified storage",
            ],
            [
                "Analytics and ML pipelines require different storage",
                "Data must move between lake and warehouse",
                "Lakehouse supports analytics + ML on same platform",
            ],
            [
                "Streaming and batch pipelines become complex",
                "Multiple data copies across systems",
                "Lakehouse supports batch + streaming processing together",
            ],
            [
                "Data quality and schema control missing in lakes",
                "Schema-on-read creates unreliable analytics",
                "Lakehouse introduces schema enforcement and versioning",
            ],
        ],
        ["Why Lakehouse is Needed", "Problems in Traditional Systems", "Lakehouse Solution"]
    )

    st.markdown("#### Late Arriving Data Handling")
    late_col1, late_col2, late_col3 = st.columns(3)

    with late_col1:
        render_html_panel(build_architecture_box("Late Arriving Dimensions", tone="blue", active=issue_mode == "Late Dimension"))
        st.markdown("**Problem Statement:** Fact arrives before dim exists. FK mismatch.")
        st.caption("Example: Sales event arrives but customer dim is missing.")
        render_df([["101", "P100", "500"]], ["customer_id", "product_id", "sales"])
        render_box("Solution 1: Create placeholder dimension record", "#E6F4EA")
        render_df([["999", "101", "Unknown -> John"]], ["customer_sk", "customer_id", "name"])

    with late_col2:
        render_html_panel(build_architecture_box("Late Arriving Facts", tone="amber", active=issue_mode == "Late Fact"))
        st.markdown("**Problem Statement:** Fact event arrives after ETL processed that partition.")
        st.caption("Example: Order on 2024-01-01 but data arrives on 2024-01-04.")
        render_df([["2024-01-01", "P100", "200"]], ["event_date", "product_id", "sales"])
        render_box("Solution 2: Reprocess the affected date partition", "#E6F4EA")
        render_df([["2024-01-01", "P100", "200"]], ["event_date", "product_id", "sales"])

    with late_col3:
        render_html_panel(build_architecture_box("Backfill Strategy", tone="slate", active=issue_mode == "Backfill"))
        st.markdown("**Problem Statement:** Historical partitions processed but new records appear.")
        st.caption("Example: Pipeline processed until 2024-01-02, new data for 2024-01-01.")
        render_df([["2024-01-02", "2024-01-01"]], ["run_date", "partition"])
        render_box("Solution 3: Run backfill pipeline", "#E6F4EA")
        render_df([["2024-01-01", "2024-01-07"]], ["start_date", "end_date"])

    st.markdown("#### Idempotent Processing (Foundation of Late Data Handling)")
    st.caption("All recovery strategies depend on idempotent pipelines: rerunning produces the same result, with no duplicates.")

    idem_col1, idem_col2, idem_col3 = st.columns([1.1, 1.1, 1])

    with idem_col1:
        render_html_panel(build_architecture_box("Bad Pipeline (Duplicates)", tone="amber", active=issue_mode == "Duplicate Replay"))
        duplicate_rows = [["1001", "101", "500"], ["1001", "101", "500"]]
        if issue_mode != "Duplicate Replay":
            duplicate_rows = [["1001", "101", "500"]]
        render_df(duplicate_rows, ["order_id", "customer_id", "sales"])
        if issue_mode == "Duplicate Replay":
            render_box("Duplicates appear when retry logic appends instead of merging.", "#FDECEA")
        else:
            render_box("This is the failure mode to avoid when retries happen.", "#FFF4E5")

    with idem_col2:
        render_html_panel(build_architecture_box("Correct Idempotent Processing", tone="green", active=True))
        render_df([["1001", "101", "500"]], ["order_id", "customer_id", "sales"])
        render_box("MERGE or upsert logic keeps only one correct business record.", "#E6F4EA")

    with idem_col3:
        st.markdown("**MERGE Pattern**")
        st.code(
            """MERGE INTO sales_fact
USING staging_table
ON order_id
WHEN MATCHED THEN UPDATE
WHEN NOT MATCHED THEN INSERT"""
        )
        render_box(issue_action_map[issue_mode], "#F8FAFC")


def render_data_mesh_architecture_workspace():
    st.markdown("### 7.7 Data Mesh Architecture")
    st.caption(
        "Data Mesh is a decentralized data architecture where data ownership is distributed to domain teams "
        "instead of a single central data engineering team."
    )

    with st.container(border=True):
        st.markdown("#### Data Mesh Simulator")
        c1, c2, c3, c4 = st.columns(4)

        operating_model = c1.selectbox(
            "Operating Model",
            ["Traditional Centralized", "Hybrid Federated", "Data Mesh"],
            key="dm_mesh_operating_model",
        )
        domain_count = c2.slider(
            "Domain Teams",
            2, 4, 3,
            key="dm_mesh_domain_count",
        )
        platform_mode = c3.selectbox(
            "Platform Layer",
            ["Basic Shared Infra", "Self-Service Platform"],
            key="dm_mesh_platform_mode",
        )
        governance_mode = c4.selectbox(
            "Governance",
            ["Central Control", "Federated Governance", "Weak Standards"],
            key="dm_mesh_governance_mode",
        )
    standards_map = {
        "Central Control": "Strong standards, slower domain autonomy",
        "Federated Governance": "Shared standards with domain ownership",
        "Weak Standards": "Fast starts, high inconsistency risk",
    }
    centralized_active = operating_model == "Traditional Centralized"
    mesh_active = operating_model == "Data Mesh"
    hybrid_active = operating_model == "Hybrid Federated"

    domain_specs = [
        ("Sales Domain", "Sales Data Product", "green"),
        ("Marketing Domain", "Campaign Data Product", "amber"),
        ("Finance Domain", "Revenue Data Product", "blue"),
        ("HR Domain", "People Data Product", "slate"),
    ][:domain_count]

    left_col, right_col = st.columns(2)

    with left_col:
        st.markdown("#### Traditional Centralized (Problem)")
        centralized_html = (
            "<div style='font-size:13px;font-weight:700;color:#374151;margin-bottom:10px;'>Company Data Sources:</div>"
            + "<div style='display:flex;gap:8px;flex-wrap:wrap;'>"
            + build_flow_chip("Sales", "blue", active=centralized_active or hybrid_active)
            + build_flow_chip("Marketing", "slate", active=centralized_active or hybrid_active)
            + build_flow_chip("Finance", "slate", active=centralized_active or hybrid_active)
            + build_flow_chip("HR", "slate", active=centralized_active or hybrid_active)
            + "</div>"
            + "<div style='text-align:center;margin-top:10px;'>"
            + build_arrow("↓", size=18)
            + "</div>"
            + build_architecture_box(
                "Central Data Team (ALL pipelines & models)" if not hybrid_active else "Shared Central Platform + domain coordination",
                ["Bottleneck: slow delivery, limited domain knowledge"] if not hybrid_active else ["Hybrid: some shared ownership remains"],
                tone="amber",
                min_height=96,
                active=centralized_active or hybrid_active,
                subtle=mesh_active,
            )
            + "<div style='display:flex;gap:10px;margin-top:14px;'>"
            + f"<div style='flex:1'>{build_architecture_box('Data Lake', tone='amber', active=centralized_active, subtle=mesh_active)}</div>"
            + f"<div style='flex:1'>{build_architecture_box('Data Warehouse', tone='blue', active=centralized_active or hybrid_active, subtle=mesh_active)}</div>"
            + "</div>"
            + "<div style='margin-top:12px;'>"
            + build_architecture_box(
                "BI / ML / Analytics Users",
                ["Depend on central team for all datasets"],
                tone="blue",
                active=centralized_active,
                subtle=mesh_active,
            )
            + "</div>"
        )
        render_html_panel(centralized_html)

    with right_col:
        st.markdown("#### Data Mesh Architecture (Solution)")
        mesh_html = (
            build_architecture_box(
                "Data Platform Infrastructure (Self-Service)",
                ["Storage | Compute | Governance | Data Catalog"],
                tone="blue" if platform_mode == "Self-Service Platform" else "slate",
                active=mesh_active or hybrid_active,
                subtle=centralized_active,
            )
            + "<div style='margin-top:8px;'>"
            + build_architecture_box(
                governance_mode,
                [standards_map[governance_mode]],
                tone="green" if governance_mode == "Federated Governance" else "amber" if governance_mode == "Weak Standards" else "slate",
                active=True,
            )
            + "</div>"
            + "<div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;'>"
            + "".join(
                f"<div style='flex:1;min-width:160px'>{build_architecture_box(name, [product, 'Owns data end-to-end', 'Produces + maintains'], tone=tone, min_height=118, active=mesh_active or hybrid_active, subtle=centralized_active)}</div>"
                for name, product, tone in domain_specs
            )
            + "</div>"
        )
        render_html_panel(mesh_html)

    st.markdown("#### Data Mesh Key Principles")
    render_df(
        [
            ["Domain Ownership", "Each domain team owns, produces, and maintains its own data pipelines and products"],
            ["Data as a Product", "Data is discoverable, addressable, trustworthy, self-describing, and interoperable"],
            ["Self-Service Platform", "Shared infrastructure so domains do not reinvent storage, compute, or catalog"],
            ["Federated Governance", "Global standards for security, quality, and interoperability enforced across domains"],
        ],
        ["Principle", "Meaning"]
    )

    st.markdown("#### Data Mesh vs Data Fabric")
    render_df(
        [
            ["Approach", "Decentralized: domain teams own data", "Centralized: metadata-driven integration"],
            ["Ownership", "Domain teams manage their own data", "Central platform manages data access"],
            ["Key Tech", "Self-service platform + governance", "Metadata, AI engine, data virtualization"],
            ["Integration", "Data products published by domains", "Unified access across DW, lake, APIs, SaaS"],
        ],
        ["Aspect", "Data Mesh", "Data Fabric"]
    )

    render_box(
        (
            f"<b>Current Simulation:</b> {operating_model} with <b>{platform_mode}</b> and "
            f"<b>{governance_mode}</b>. {standards_map[governance_mode]}"
        ),
        "#F8FAFC"
    )


def build_partition_strip(count, tone="blue", hot_count=0):
    cells = []
    for index in range(count):
        active = index < hot_count
        cells.append(
            build_flow_chip(
                f"P{index + 1}",
                tone=tone if active else "slate",
                active=active,
                subtle=not active and hot_count > 0,
            )
        )
    return "".join(cells)


def render_distributed_cluster_workspace():
    st.markdown("### Distributed Execution & Partitioning")
    st.caption("Use the controls to see locality, sharding, join strategy, and skew reflected directly in the cluster diagrams.")

    with st.container(border=True):
        st.markdown("#### Distributed Simulator")
        c1, c2, c3, c4, c5 = st.columns(5)

        partitioning = c1.selectbox(
            "Partitioning",
            ["Hash Partitioning", "Range Partitioning", "Consistent Hashing"],
            key="dm_dist_partitioning",
        )
        join_strategy = c2.selectbox(
            "Join Strategy",
            ["Broadcast Join", "Shuffle Join", "Sort-Merge Join"],
            key="dm_dist_join_strategy",
        )
        locality = c3.selectbox(
            "Data Locality",
            ["Co-Located Compute", "Partial Locality", "Remote Reads"],
            key="dm_dist_locality",
        )
        skew_level = c4.selectbox(
            "Skew",
            ["Balanced", "Moderate Skew", "Hot Key"],
            key="dm_dist_skew_level",
        )
        node_count = c5.slider(
            "Worker Nodes",
            3, 5, 4,
            key="dm_dist_node_count",
        )

    distribution_map = {
        "Balanced": [4, 4, 4, 4, 4],
        "Moderate Skew": [6, 5, 4, 3, 3],
        "Hot Key": [9, 4, 3, 2, 2],
    }
    counts = distribution_map[skew_level][:node_count]
    if partitioning == "Range Partitioning":
        counts = sorted(counts, reverse=True)
    if partitioning == "Consistent Hashing":
        counts = [5, 5, 4, 4, 4][:node_count]
        if skew_level == "Hot Key":
            counts[0] += 2
    hot_index = 0 if skew_level == "Hot Key" else None

    render_box(
        (
            f"<b>Current Simulation:</b> {partitioning} with <b>{join_strategy}</b>, "
            f"<b>{locality}</b>, and <b>{skew_level}</b>. The active diagrams below show shard balance, "
            "join movement, and read locality directly."
        ),
        "#F8FAFC"
    )

    top_left, top_right = st.columns(2)

    with top_left:
        st.markdown("#### Cluster Layout")
        node_boxes = []
        for idx, count in enumerate(counts):
            is_hot = hot_index == idx
            tone = "rose" if is_hot else "blue" if idx % 2 == 0 else "green"
            node_boxes.append(
                "<div style='flex:1;min-width:145px;'>"
                + build_architecture_box(
                    f"Node {idx + 1}",
                    [
                        f"{count} active partitions",
                        "HOT KEY pressure" if is_hot else "balanced worker",
                    ],
                    tone=tone,
                    active=is_hot or locality == "Co-Located Compute",
                )
                + "<div style='margin-top:8px;'>"
                + build_partition_strip(count, tone="amber" if is_hot else "blue", hot_count=2 if is_hot else 0)
                + "</div></div>"
            )
        render_html_panel(
            "<div style='display:flex;gap:10px;flex-wrap:wrap;'>"
            + "".join(node_boxes)
            + "</div>"
        )

    with top_right:
        st.markdown("#### Data Locality")
        locality_html = (
            build_architecture_box("Compute Layer", ["Spark / Trino / distributed SQL"], tone="slate", active=True)
            + "<div style='text-align:center;margin:10px 0;'>"
            + build_flow_chip("Node 1", "blue", active=locality == "Co-Located Compute")
            + build_inline_arrow("→")
            + build_flow_chip("Local Blocks", "green", active=locality == "Co-Located Compute", subtle=locality != "Co-Located Compute")
            + build_inline_arrow("||")
            + build_flow_chip("Remote Reads", "amber", active=locality == "Remote Reads", subtle=locality == "Co-Located Compute")
            + build_inline_arrow("→")
            + build_flow_chip("Cross Node Fetch", "rose", active=locality == "Remote Reads" or locality == "Partial Locality", subtle=locality == "Co-Located Compute")
            + "</div>"
            + "<div style='display:flex;gap:10px;flex-wrap:wrap;'>"
            + build_architecture_box("Best Case", ["Move compute to data", "Low network cost"], tone="green", active=locality == "Co-Located Compute", subtle=locality != "Co-Located Compute")
            + build_architecture_box("Middle Case", ["Some blocks local", "Some network transfer"], tone="amber", active=locality == "Partial Locality", subtle=locality != "Partial Locality")
            + build_architecture_box("Worst Case", ["Most reads remote", "High network latency"], tone="rose", active=locality == "Remote Reads", subtle=locality != "Remote Reads")
            + "</div>"
        )
        render_html_panel(locality_html)

    middle_left, middle_right = st.columns(2)

    with middle_left:
        st.markdown("#### Distributed Joins")
        if join_strategy == "Broadcast Join":
            join_html = (
                build_architecture_box("Fact Table", ["large distributed table"], tone="blue", active=True)
                + "<div style='text-align:center;margin:10px 0;'>"
                + build_flow_chip("Small Dimension", "green", active=True)
                + build_inline_arrow("broadcast")
                + build_flow_chip("Node 1", "slate", active=True)
                + build_flow_chip("Node 2", "slate", active=True)
                + build_flow_chip("Node 3", "slate", active=True)
                + "</div>"
                + build_architecture_box("Result", ["No large shuffle", "Best when dimension is small"], tone="green", active=True)
            )
        elif join_strategy == "Shuffle Join":
            join_html = (
                "<div style='display:flex;gap:10px;'>"
                + "<div style='flex:1;'>"
                + build_architecture_box("Fact Partitions", ["hash on join key"], tone="blue", active=True)
                + "</div>"
                + "<div style='flex:1;'>"
                + build_architecture_box("Dim Partitions", ["hash on join key"], tone="amber", active=True)
                + "</div></div>"
                + "<div style='text-align:center;margin:10px 0;'>"
                + build_flow_chip("Shuffle Exchange", "rose", active=True)
                + "</div>"
                + build_architecture_box("Result", ["High network movement", "Sensitive to skew"], tone="rose", active=True)
            )
        else:
            join_html = (
                "<div style='display:flex;gap:10px;'>"
                + "<div style='flex:1;'>"
                + build_architecture_box("Fact", ["partitioned + sorted"], tone="blue", active=True)
                + "</div>"
                + "<div style='flex:1;'>"
                + build_architecture_box("Dimension", ["partitioned + sorted"], tone="green", active=True)
                + "</div></div>"
                + "<div style='text-align:center;margin:10px 0;'>"
                + build_flow_chip("Sort Phase", "amber", active=True)
                + build_inline_arrow("→")
                + build_flow_chip("Merge Join", "slate", active=True)
                + "</div>"
                + build_architecture_box("Result", ["Stable for big-big joins", "More CPU than broadcast"], tone="slate", active=True)
            )
        render_html_panel(join_html)

    with middle_right:
        st.markdown("#### Partitioning Strategy")
        if partitioning == "Hash Partitioning":
            partition_html = (
                build_architecture_box("Hash(key)", ["Even spread when keys are uniform"], tone="blue", active=True)
                + "<div style='text-align:center;margin:12px 0;'>"
                + build_flow_chip("User 101", "slate")
                + build_inline_arrow("→")
                + build_flow_chip("Node 2", "green", active=True)
                + build_inline_arrow("  ")
                + build_flow_chip("User 102", "slate")
                + build_inline_arrow("→")
                + build_flow_chip("Node 4", "green", active=True)
                + "</div>"
                + build_architecture_box("Trade-off", ["Simple, common, but hot keys can overload one node"], tone="amber", active=skew_level != "Balanced")
            )
        elif partitioning == "Range Partitioning":
            partition_html = (
                build_architecture_box("Range Buckets", ["A-F | G-M | N-S | T-Z"], tone="amber", active=True)
                + "<div style='display:flex;gap:8px;margin-top:10px;'>"
                + build_architecture_box("Bucket 1", ["Low values"], tone="blue", active=True)
                + build_architecture_box("Bucket 2", ["Mid values"], tone="slate", active=True)
                + build_architecture_box("Bucket 3", ["High values"], tone="green", active=True)
                + "</div>"
                + "<div style='margin-top:10px;'>"
                + build_architecture_box("Trade-off", ["Fast range scans, but uneven ranges create skew"], tone="rose", active=skew_level != "Balanced")
                + "</div>"
            )
        else:
            partition_html = (
                build_architecture_box("Consistent Hash Ring", ["Minimal reshuffle when a node joins or leaves"], tone="green", active=True)
                + "<div style='text-align:center;margin:12px 0;'>"
                + build_flow_chip("VNode A", "blue", active=True)
                + build_flow_chip("VNode B", "amber", active=True)
                + build_flow_chip("VNode C", "slate", active=True)
                + build_flow_chip("VNode D", "green", active=True)
                + "</div>"
                + build_architecture_box("Rebalance Effect", ["Only nearby keys move to the new node"], tone="slate", active=True)
            )
        render_html_panel(partition_html)

    st.markdown("#### Data Skew")
    skew_rows = [
        ["Balanced", "Uniform key distribution", "Predictable latency and memory usage"],
        ["Moderate Skew", "A few partitions are heavier", "Some tasks lag behind the stage"],
        ["Hot Key", "One key dominates a partition", "One worker becomes a bottleneck"],
    ]
    render_highlight_table(["Scenario", "Pattern", "Impact"], skew_rows, ["Balanced", "Moderate Skew", "Hot Key"].index(skew_level), "rose")


def render_access_patterns_workspace():
    st.markdown("### 7.8 Architecture Patterns & Data Access")
    st.caption("Data fabric, serving layers, Lambda/Kappa, CDC pipelines, and data access optimizations.")

    with st.container(border=True):
        st.markdown("#### Pattern Simulator")
        c1, c2, c3 = st.columns(3)

        pattern_focus = c1.selectbox(
            "Pattern Focus",
            [
                "Data Fabric",
                "Serving Layer",
                "Lambda Architecture",
                "Kappa Architecture",
                "CDC Pipelines",
                "Real-Time Data Architecture",
            ],
            key="dm_access_pattern_focus",
        )
        access_strategy = c2.selectbox(
            "Access Optimization",
            ["Caching (Redis)", "Materialized Views", "Partitioning", "Indexing", "Clustering Keys"],
            key="dm_access_strategy",
        )
        serving_target = c3.selectbox(
            "Serving Target",
            ["Apps", "Dashboards", "ML", "APIs"],
            key="dm_access_serving_target",
        )

    render_box(
        (
            f"<b>Current Simulation:</b> {pattern_focus} is highlighted, serving target is <b>{serving_target}</b>, "
            f"and the access strategy table emphasizes <b>{access_strategy}</b>."
        ),
        "#F8FAFC"
    )

    top_left, top_right = st.columns(2)

    with top_left:
        st.markdown("#### 1. Data Fabric Architecture")
        fabric_html = (
            build_architecture_box(
                "Data Fabric Layer",
                ["Metadata | Catalog | Governance | AI Engine"],
                tone="blue",
                active=pattern_focus == "Data Fabric",
                subtle=pattern_focus != "Data Fabric",
            )
            + "<div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;'>"
            + build_architecture_box("Data Warehouse", tone="slate", active=pattern_focus == "Data Fabric", subtle=pattern_focus != "Data Fabric")
            + build_architecture_box("Data Lake", tone="green", active=pattern_focus == "Data Fabric", subtle=pattern_focus != "Data Fabric")
            + build_architecture_box("APIs", tone="amber", active=pattern_focus == "Data Fabric", subtle=pattern_focus != "Data Fabric")
            + build_architecture_box("SaaS Apps", tone="blue", active=pattern_focus == "Data Fabric", subtle=pattern_focus != "Data Fabric")
            + "</div>"
        )
        render_html_panel(fabric_html)

    with top_right:
        st.markdown("#### 2. Data Serving Layer")
        serving_html = (
            build_architecture_box("DW / Lakehouse", tone="slate", active=pattern_focus == "Serving Layer", subtle=pattern_focus != "Serving Layer")
            + "<div style='text-align:center;margin:8px 0;'>"
            + build_arrow("↓", size=18)
            + "</div>"
            + build_architecture_box(
                "Serving: APIs | Views | Cache",
                [f"Primary target: {serving_target}"],
                tone="green",
                active=pattern_focus == "Serving Layer",
                subtle=pattern_focus != "Serving Layer",
            )
            + "<div style='text-align:center;margin:8px 0;'>"
            + build_arrow("↓", size=18)
            + "</div>"
            + build_architecture_box(
                "Apps / Dashboards / ML",
                ["Fast, low-latency access"],
                tone="blue",
                active=pattern_focus == "Serving Layer",
                subtle=pattern_focus != "Serving Layer",
            )
        )
        render_html_panel(serving_html)

    middle_left, middle_right = st.columns(2)

    with middle_left:
        st.markdown("#### 3. Lambda Architecture (Batch + Stream)")
        lambda_html = (
            build_architecture_box("Data Source", tone="slate", active=pattern_focus == "Lambda Architecture", subtle=pattern_focus != "Lambda Architecture")
            + "<div style='display:flex;justify-content:space-between;gap:14px;margin-top:10px;'>"
            + "<div style='flex:1;'>"
            + build_architecture_box("Batch Layer", tone="blue", active=pattern_focus == "Lambda Architecture", subtle=pattern_focus != "Lambda Architecture")
            + "<div style='margin-top:8px;'>"
            + build_architecture_box("Batch Views", tone="blue", active=pattern_focus == "Lambda Architecture", subtle=pattern_focus != "Lambda Architecture")
            + "</div></div>"
            + "<div style='flex:1;'>"
            + build_architecture_box("Speed Layer", tone="amber", active=pattern_focus == "Lambda Architecture", subtle=pattern_focus != "Lambda Architecture")
            + "<div style='margin-top:8px;'>"
            + build_architecture_box("RT Views", tone="amber", active=pattern_focus == "Lambda Architecture", subtle=pattern_focus != "Lambda Architecture")
            + "</div></div>"
            + "</div>"
            + "<div style='margin-top:10px;'>"
            + build_architecture_box("Serving Layer", tone="green", active=pattern_focus == "Lambda Architecture", subtle=pattern_focus != "Lambda Architecture")
            + "</div>"
        )
        render_html_panel(lambda_html)

    with middle_right:
        st.markdown("#### 4. Kappa Architecture (Stream Only)")
        kappa_html = (
            build_architecture_box("Event Stream (Kafka)", tone="amber", active=pattern_focus == "Kappa Architecture", subtle=pattern_focus != "Kappa Architecture")
            + "<div style='text-align:center;margin:8px 0;'>"
            + build_arrow("↓", size=18)
            + "</div>"
            + build_architecture_box("Stream Process (Flink)", tone="blue", active=pattern_focus == "Kappa Architecture", subtle=pattern_focus != "Kappa Architecture")
            + "<div style='text-align:center;margin:8px 0;'>"
            + build_arrow("↓", size=18)
            + "</div>"
            + build_architecture_box("Database / Serving", tone="green", active=pattern_focus == "Kappa Architecture", subtle=pattern_focus != "Kappa Architecture")
            + "<div style='display:flex;gap:8px;margin-top:10px;'>"
            + build_architecture_box("Lambda: batch + stream", tone="slate", subtle=True)
            + build_architecture_box("Kappa: stream only", tone="amber", active=pattern_focus == "Kappa Architecture", subtle=pattern_focus != "Kappa Architecture")
            + "</div>"
        )
        render_html_panel(kappa_html)

    bottom_left, bottom_right = st.columns(2)

    with bottom_left:
        st.markdown("#### 5. CDC Pipelines (Change Data Capture)")
        cdc_html = (
            "<div style='display:flex;gap:8px;flex-wrap:wrap;'>"
            + build_architecture_box("Source DB", tone="slate", active=pattern_focus == "CDC Pipelines", subtle=pattern_focus != "CDC Pipelines")
            + build_architecture_box("Debezium", tone="amber", active=pattern_focus == "CDC Pipelines", subtle=pattern_focus != "CDC Pipelines")
            + build_architecture_box("Kafka", tone="blue", active=pattern_focus == "CDC Pipelines", subtle=pattern_focus != "CDC Pipelines")
            + build_architecture_box("Process", tone="green", active=pattern_focus == "CDC Pipelines", subtle=pattern_focus != "CDC Pipelines")
            + build_architecture_box("DW / Lake", tone="blue", active=pattern_focus == "CDC Pipelines", subtle=pattern_focus != "CDC Pipelines")
            + "</div>"
        )
        render_html_panel(cdc_html)

    with bottom_right:
        st.markdown("#### 6. Real-Time Data Architecture")
        realtime_html = (
            "<div style='display:flex;gap:8px;flex-wrap:wrap;'>"
            + build_architecture_box("Events", tone="slate", active=pattern_focus == "Real-Time Data Architecture", subtle=pattern_focus != "Real-Time Data Architecture")
            + build_architecture_box("Kafka", tone="amber", active=pattern_focus == "Real-Time Data Architecture", subtle=pattern_focus != "Real-Time Data Architecture")
            + build_architecture_box("Spark / Flink", tone="blue", active=pattern_focus == "Real-Time Data Architecture", subtle=pattern_focus != "Real-Time Data Architecture")
            + build_architecture_box("Druid / ClickHouse", tone="green", active=pattern_focus == "Real-Time Data Architecture", subtle=pattern_focus != "Real-Time Data Architecture")
            + build_architecture_box("Dashboards", tone="blue", active=pattern_focus == "Real-Time Data Architecture", subtle=pattern_focus != "Real-Time Data Architecture")
            + "</div>"
        )
        render_html_panel(realtime_html)

    st.markdown("#### 7. Data Access Optimization Strategies")
    strategy_rows = [
        ["Caching (Redis)", "Store query results in memory. Reduce repeated expensive queries to warehouse."],
        ["Materialized Views", "Precompute aggregates such as monthly_sales. Avoid full scans every query."],
        ["Partitioning", "Split table by key or date. Queries scan only relevant partitions."],
        ["Indexing", "Lookup structures on columns. Faster point lookups for filtered access."],
        ["Clustering Keys", "Physical sort in storage. Efficient range scans in Snowflake, BigQuery, and Redshift."],
    ]
    selected_strategy_index = [row[0] for row in strategy_rows].index(access_strategy)
    render_highlight_table(["Strategy", "How It Works"], strategy_rows, selected_strategy_index, "green")


DM_INTERVIEW_STATE_KEY = "dm_interview_state"
DM_INTERVIEW_REPORT_KEY = "dm_interview_report"
DM_INTERVIEW_DIFFICULTIES = ["Easy", "Medium", "Hard"]

DATA_MODELING_INTERVIEW_BANK = [
    {
        "id": "dm1",
        "category": "Fundamentals",
        "difficulty": "Easy",
        "question": "Explain OLTP vs OLAP and why a team would model them differently.",
        "expected_points": [
            {"label": "Operational vs analytical purpose", "keywords": ["oltp", "operations", "olap", "analytics"]},
            {"label": "Normalized vs denormalized design", "keywords": ["normalized", "3nf", "denormalized", "star schema"]},
            {"label": "Query pattern difference", "keywords": ["point lookup", "transaction", "aggregation", "historical"]},
            {"label": "Real example", "keywords": ["example", "dashboard", "order", "report"]},
        ],
    },
    {
        "id": "dm2",
        "category": "Fundamentals",
        "difficulty": "Medium",
        "question": "How do you convert an ER model into physical tables, especially for many-to-many relationships?",
        "expected_points": [
            {"label": "Entities become tables", "keywords": ["entity", "table", "attribute", "column"]},
            {"label": "Keys and foreign keys", "keywords": ["primary key", "foreign key", "relationship"]},
            {"label": "Bridge table for many-to-many", "keywords": ["bridge", "junction", "many-to-many", "student_course"]},
            {"label": "Cardinality awareness", "keywords": ["1:m", "cardinality", "one-to-many", "many-to-one"]},
        ],
    },
    {
        "id": "dm3",
        "category": "Dimensional Modeling",
        "difficulty": "Easy",
        "question": "What is grain in a fact table and why should it be declared before designing facts and dimensions?",
        "expected_points": [
            {"label": "One row meaning", "keywords": ["one row", "grain", "represents"]},
            {"label": "Controls aggregation accuracy", "keywords": ["aggregation", "double count", "accuracy"]},
            {"label": "Impacts dimension keys and measures", "keywords": ["dimension", "measure", "foreign key"]},
            {"label": "Example of good vs bad grain", "keywords": ["order line", "daily sales", "example"]},
        ],
    },
    {
        "id": "dm4",
        "category": "Dimensional Modeling",
        "difficulty": "Medium",
        "question": "Compare star schema and snowflake schema. When would you choose one over the other?",
        "expected_points": [
            {"label": "Star schema is denormalized", "keywords": ["star schema", "denormalized", "simple joins"]},
            {"label": "Snowflake is normalized dimensions", "keywords": ["snowflake", "normalized", "dimension hierarchy"]},
            {"label": "Trade-off between simplicity and storage", "keywords": ["performance", "storage", "simplicity", "maintenance"]},
            {"label": "Use-case driven choice", "keywords": ["bi", "hierarchy", "governance", "use case"]},
        ],
    },
    {
        "id": "dm5",
        "category": "Dimensional Modeling",
        "difficulty": "Hard",
        "question": "Explain SCD Type 2 end to end, including surrogate keys, effective dates, and query behavior.",
        "expected_points": [
            {"label": "New row instead of overwrite", "keywords": ["new row", "history", "overwrite", "type 2"]},
            {"label": "Surrogate key role", "keywords": ["surrogate key", "business key"]},
            {"label": "Effective dating/current flag", "keywords": ["start_date", "end_date", "current", "effective"]},
            {"label": "Join/query implication", "keywords": ["fact", "point in time", "as of", "history"]},
        ],
    },
    {
        "id": "dm6",
        "category": "Architecture",
        "difficulty": "Medium",
        "question": "How does Kimball bus architecture help multiple data marts stay consistent?",
        "expected_points": [
            {"label": "Conformed dimensions", "keywords": ["conformed dimensions", "shared dimensions"]},
            {"label": "Multiple marts", "keywords": ["multiple marts", "sales mart", "inventory mart", "shipment mart"]},
            {"label": "Consistent reporting", "keywords": ["consistent reporting", "same definition", "same metric"]},
            {"label": "Dimensional bus thinking", "keywords": ["bus architecture", "kimball", "enterprise consistency"]},
        ],
    },
    {
        "id": "dm7",
        "category": "Architecture",
        "difficulty": "Hard",
        "question": "How would you handle late arriving dimensions, late arriving facts, and backfills in a lakehouse sales model?",
        "expected_points": [
            {"label": "Placeholder or unknown dimension row", "keywords": ["placeholder", "unknown", "surrogate key", "late arriving dimension"]},
            {"label": "Partition replay or reprocessing for late facts", "keywords": ["reprocess", "partition", "late fact", "backfill"]},
            {"label": "Idempotent MERGE or upsert", "keywords": ["idempotent", "merge", "upsert", "dedupe"]},
            {"label": "Downstream rebuild or reconciliation", "keywords": ["gold", "aggregate", "reconcile", "rebuild"]},
        ],
    },
    {
        "id": "dm8",
        "category": "Architecture",
        "difficulty": "Medium",
        "question": "Compare centralized data teams, hybrid federated models, and full data mesh.",
        "expected_points": [
            {"label": "Centralized bottleneck", "keywords": ["centralized", "bottleneck", "central team"]},
            {"label": "Domain ownership in mesh", "keywords": ["domain ownership", "data mesh", "domain teams"]},
            {"label": "Self-service platform", "keywords": ["self-service", "platform", "shared infrastructure"]},
            {"label": "Federated governance", "keywords": ["federated governance", "standards", "interoperability"]},
        ],
    },
    {
        "id": "dm9",
        "category": "Distributed",
        "difficulty": "Medium",
        "question": "When would you choose broadcast join versus shuffle join in a distributed warehouse?",
        "expected_points": [
            {"label": "Broadcast for small dimension", "keywords": ["broadcast", "small table", "dimension"]},
            {"label": "Shuffle for larger distributed data", "keywords": ["shuffle", "large table", "distributed"]},
            {"label": "Network or movement trade-off", "keywords": ["network", "data movement", "cost"]},
            {"label": "Skew consideration", "keywords": ["skew", "hot key", "salting"]},
        ],
    },
    {
        "id": "dm10",
        "category": "Distributed",
        "difficulty": "Hard",
        "question": "Explain data locality, consistent hashing, and skew mitigation in distributed data modeling.",
        "expected_points": [
            {"label": "Move compute close to data", "keywords": ["data locality", "compute to data", "remote reads"]},
            {"label": "Consistent hashing reduces reshuffle", "keywords": ["consistent hashing", "minimal movement", "rehash"]},
            {"label": "Skew mitigation techniques", "keywords": ["skew", "salting", "split", "rebalance"]},
            {"label": "Partitioning strategy matters", "keywords": ["partitioning", "hash", "range", "distribution key"]},
        ],
    },
]


def get_filtered_dm_interview_questions(categories=None, difficulties=None):
    selected_categories = set(categories or [])
    selected_difficulties = set(difficulties or [])
    questions = []

    for question in DATA_MODELING_INTERVIEW_BANK:
        if selected_categories and question["category"] not in selected_categories:
            continue
        if selected_difficulties and question["difficulty"] not in selected_difficulties:
            continue
        questions.append(question)

    return questions


def evaluate_dm_answer(question, answer):
    normalized_answer = answer.lower()
    points = question["expected_points"]
    covered = []
    missed = []

    for point in points:
        if any(keyword in normalized_answer for keyword in point["keywords"]):
            covered.append(point["label"])
        else:
            missed.append(point["label"])

    coverage_ratio = len(covered) / max(len(points), 1)
    depth_bonus = 1 if len(answer.split()) >= 90 and coverage_ratio >= 0.5 else 0
    tradeoff_bonus = 1 if any(token in normalized_answer for token in ["trade-off", "tradeoff", "example", "pitfall", "because"]) else 0
    score = min(10, round((coverage_ratio * 8) + depth_bonus + tradeoff_bonus))

    return {
        "score": score,
        "covered": covered,
        "missed": missed,
        "coverage_ratio": coverage_ratio,
    }


def reset_dm_interview(clear_report=False):
    st.session_state.pop(DM_INTERVIEW_STATE_KEY, None)
    if clear_report:
        st.session_state.pop(DM_INTERVIEW_REPORT_KEY, None)


def start_dm_interview(categories, difficulties, question_count):
    pool = get_filtered_dm_interview_questions(categories, difficulties)
    randomized = pool[:]
    random.shuffle(randomized)
    selected = randomized[:question_count]
    reset_dm_interview(clear_report=True)
    st.session_state[DM_INTERVIEW_STATE_KEY] = {
        "questions": selected,
        "current_index": 0,
        "results": {},
        "categories": list(categories),
        "difficulties": list(difficulties),
    }


def finalize_dm_interview():
    state = st.session_state.get(DM_INTERVIEW_STATE_KEY)
    if not state:
        return

    rows = []
    total_score = 0
    for question in state["questions"]:
        result = state["results"].get(question["id"], {})
        score = result.get("score", 0)
        total_score += score
        rows.append({
            "question": question["question"],
            "category": question["category"],
            "difficulty": question["difficulty"],
            "score": score,
            "covered": ", ".join(result.get("covered", [])) or "-",
            "missed": ", ".join(result.get("missed", [])) or "-",
        })

    report = {
        "total_questions": len(state["questions"]),
        "average_score": round(total_score / max(len(state["questions"]), 1), 1),
        "rows": rows,
        "categories": state["categories"],
        "difficulties": state["difficulties"],
    }
    st.session_state[DM_INTERVIEW_REPORT_KEY] = report
    reset_dm_interview(clear_report=False)


def render_dm_interview_setup():
    st.markdown("### Mock Interview Setup")
    categories = sorted({question["category"] for question in DATA_MODELING_INTERVIEW_BANK})

    if "dm_interview_categories" not in st.session_state:
        st.session_state.dm_interview_categories = categories
    if "dm_interview_difficulties" not in st.session_state:
        st.session_state.dm_interview_difficulties = DM_INTERVIEW_DIFFICULTIES
    if "dm_interview_question_count" not in st.session_state:
        st.session_state.dm_interview_question_count = 4

    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.multiselect("Focus Areas", categories, key="dm_interview_categories")
        st.multiselect("Difficulty", DM_INTERVIEW_DIFFICULTIES, key="dm_interview_difficulties")

        filtered = get_filtered_dm_interview_questions(
            st.session_state.dm_interview_categories,
            st.session_state.dm_interview_difficulties,
        )
        max_questions = max(1, len(filtered))
        if st.session_state.dm_interview_question_count > max_questions:
            st.session_state.dm_interview_question_count = max_questions

        st.slider(
            "Questions",
            min_value=1,
            max_value=max_questions,
            key="dm_interview_question_count",
        )

        if st.button("Start Data Modeling Interview", disabled=len(filtered) == 0):
            start_dm_interview(
                st.session_state.dm_interview_categories,
                st.session_state.dm_interview_difficulties,
                st.session_state.dm_interview_question_count,
            )
            st.rerun()

    with right_col:
        filtered = get_filtered_dm_interview_questions(
            st.session_state.dm_interview_categories,
            st.session_state.dm_interview_difficulties,
        )
        st.metric("Available Questions", len(filtered))
        st.metric("Selected Questions", min(st.session_state.dm_interview_question_count, len(filtered) or 1))
        st.metric("Coverage", f"{len(set(st.session_state.dm_interview_categories))} tracks")

    with st.expander("Question Bank Preview", expanded=False):
        preview_rows = [
            [question["category"], question["difficulty"], question["question"]]
            for question in DATA_MODELING_INTERVIEW_BANK
        ]
        render_df(preview_rows, ["Category", "Difficulty", "Question"])


def render_dm_active_interview():
    state = st.session_state.get(DM_INTERVIEW_STATE_KEY)
    if not state:
        return

    current_question = state["questions"][state["current_index"]]
    question_id = current_question["id"]
    current_result = state["results"].get(question_id)

    top_col1, top_col2, top_col3 = st.columns(3)
    top_col1.metric("Question", f"{state['current_index'] + 1} / {len(state['questions'])}")
    top_col2.metric("Category", current_question["category"])
    top_col3.metric("Difficulty", current_question["difficulty"])

    render_html_panel(
        build_architecture_box(
            "Interview Question",
            [current_question["question"]],
            tone="blue",
            active=True,
            align="left",
        ),
        padding=12,
    )

    answer_key = f"dm_interview_answer_{question_id}"
    answer = st.text_area(
        "Your Answer",
        key=answer_key,
        height=220,
        placeholder="Write a structured, interview-style answer with trade-offs and an example.",
    )

    button_col1, button_col2, button_col3 = st.columns(3)
    evaluate = button_col1.button("Evaluate Answer", key=f"dm_eval_{question_id}")
    skip = button_col2.button("Skip", key=f"dm_skip_{question_id}")
    end = button_col3.button("Finish Interview", key="dm_finish_interview")

    if evaluate:
        feedback = evaluate_dm_answer(current_question, answer)
        state["results"][question_id] = {
            "score": feedback["score"],
            "covered": feedback["covered"],
            "missed": feedback["missed"],
            "answer": answer,
        }
        st.session_state[DM_INTERVIEW_STATE_KEY] = state
        current_result = state["results"][question_id]

    if skip:
        state["results"][question_id] = {
            "score": 0,
            "covered": [],
            "missed": [point["label"] for point in current_question["expected_points"]],
            "answer": answer,
        }
        st.session_state[DM_INTERVIEW_STATE_KEY] = state
        current_result = state["results"][question_id]

    if current_result:
        score_color = "#E6F4EA" if current_result["score"] >= 7 else "#FFF4E5" if current_result["score"] >= 4 else "#FDECEA"
        render_box(f"<b>Score:</b> {current_result['score']} / 10", score_color)

        feedback_col1, feedback_col2 = st.columns(2)
        with feedback_col1:
            st.markdown("**Covered Well**")
            for item in current_result["covered"] or ["No strong points captured yet"]:
                st.markdown(f"- {item}")

        with feedback_col2:
            st.markdown("**Still Missing**")
            for item in current_result["missed"] or ["Nothing critical missed"]:
                st.markdown(f"- {item}")

        if st.button(
            "Next Question" if state["current_index"] < len(state["questions"]) - 1 else "Show Final Report",
            key=f"dm_next_{question_id}",
        ):
            if state["current_index"] < len(state["questions"]) - 1:
                state["current_index"] += 1
                st.session_state[DM_INTERVIEW_STATE_KEY] = state
            else:
                finalize_dm_interview()
            st.rerun()

    if end:
        finalize_dm_interview()
        st.rerun()


def render_dm_interview_report():
    report = st.session_state.get(DM_INTERVIEW_REPORT_KEY)
    if not report:
        return

    st.markdown("### Interview Report")
    col1, col2, col3 = st.columns(3)
    col1.metric("Questions", report["total_questions"])
    col2.metric("Average Score", f"{report['average_score']} / 10")
    col3.metric("Coverage", ", ".join(report["categories"]) if report["categories"] else "All")

    render_df(
        [
            [
                row["category"],
                row["difficulty"],
                row["score"],
                row["covered"],
                row["missed"],
            ]
            for row in report["rows"]
        ],
        ["Category", "Difficulty", "Score", "Covered", "Missed"]
    )

    if st.button("Start New Interview", key="dm_restart_interview"):
        reset_dm_interview(clear_report=True)
        st.rerun()

# =========================================================
# 🔹 AI PROMPT (STRONG - FAANG LEVEL)
# =========================================================

def render_ai_chat(section_key, title, topic):
    chat_key = f"{section_key}_chat"
    input_key = f"{section_key}_chat_input"
    submit_key = f"{section_key}_chat_submit"

    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    st.markdown("---")
    with st.expander(f"💬 {title}", expanded=False):
        if st.session_state[chat_key]:
            for chat in st.session_state[chat_key]:
                tone = "#F8FAFC" if chat["role"] == "assistant" else "#EEF2FF"
                label = "Assistant" if chat["role"] == "assistant" else "You"
                st.markdown(
                    f"<div style='border:1px solid #d1d5db;padding:10px 12px;background:{tone};"
                    f"margin-bottom:8px;border-radius:0;'><b>{label}:</b><br>{chat['content']}</div>",
                    unsafe_allow_html=True,
                )

        with st.form(f"{section_key}_ai_form", clear_on_submit=True):
            user_input = st.text_area(
                "Ask anything",
                key=input_key,
                height=100,
                placeholder=f"Ask about {topic}...",
            )
            submitted = st.form_submit_button("Ask AI", use_container_width=True)

        if submitted and user_input.strip():
            cleaned_input = user_input.strip()
            st.session_state[chat_key].append({
                "role": "user",
                "content": cleaned_input
            })

            prompt = f"""
                You are a senior data engineer at Amazon, Google, or Microsoft.

                Answer the following question on {topic}.

                Question:
                {cleaned_input}

                Requirements:
                - Clear and well-detailed structured answer
                - Must include at least 2 real-world examples (different domains if possible)
                - Provide interview-ready explanation with reasoning
                - Include edge cases, trade-offs, or pitfalls if applicable
                - Use bullet points for clarity
                - Keep explanation concise but insightful (avoid unnecessary verbosity)
                - If applicable, include schema/table examples
                - Avoid generic textbook answers — make it practical and scenario-driven

                Format:
                - Definition (if applicable)
                - Explanation
                - Real-world examples
                - Edge cases / interview insights
                """

            response = ask_ai(prompt)
            st.session_state[chat_key].append({
                "role": "assistant",
                "content": response
            })
            st.rerun()

# =========================================================
# 🔹 FUNDAMENTALS
# =========================================================

def show_fundamentals():
    render_title("📘 Data Modeling Fundamentals")

    render_box("""
    Data Modeling = Structuring data to answer business questions efficiently.
    Connects business logic → database schema.
    """)

    render_box("""
    Example:
    Customer → customers  
    Orders → orders  
    Products → products  
    """)

    tab1, tab2, tab3 = st.tabs([
        "Normalization",
        "OLTP vs OLAP",
        "ER Modeling"
    ])

    # =====================================================
    # 🔴 NORMALIZATION
    # =====================================================
    with tab1:
        render_title("Normalization (UNF → BCNF)")

        # ---------------- UNF → 1NF ----------------
        render_subtitle("UNF → 1NF")

        render_side_by_side(
            "❌ Before (UNF)",
            [["101", "John", "DB, ML"], ["102", "Mike", "AI"]],
            "✅ After (1NF)",
            [["101", "John", "DB"], ["101", "John", "ML"], ["102", "Mike", "AI"]],
            ["student_id", "name", "course"]
        )

        render_box("❌ Problem: Multiple values in one column", "#FDECEA")
        render_box("✅ Fix: Split rows into atomic values", "#E6F4EA")

        # ---------------- 1NF → 2NF ----------------
        render_subtitle("1NF → 2NF")

        col1, col2 = st.columns(2)

        with col1:
            render_subtitle("❌ Before")
            render_df(
                [["101", "DB", "John"], ["101", "ML", "John"]],
                ["student_id", "course", "student_name"]
            )
            render_box("Partial dependency: name depends only on student_id", "#FDECEA")

        with col2:
            render_subtitle("✅ After")

            st.markdown("**Students Table**")
            render_df(
                [["101", "John"]],
                ["student_id", "student_name"]
            )

            st.markdown("**Student_Course Table**")
            render_df(
                [["101", "DB"], ["101", "ML"]],
                ["student_id", "course"]
            )

            render_box("Removed partial dependency", "#E6F4EA")

        # ---------------- 2NF → 3NF ----------------
        render_subtitle("2NF → 3NF")

        col1, col2 = st.columns(2)

        with col1:
            render_subtitle("❌ Before")
            render_df(
                [["DB", "Smith", "Computer"]],
                ["course", "instructor", "department"]
            )
            render_box("Transitive dependency: course → instructor → department", "#FDECEA")

        with col2:
            render_subtitle("✅ After")

            st.markdown("**Course Table**")
            render_df(
                [["DB", "Smith"]],
                ["course", "instructor"]
            )

            st.markdown("**Instructor Table**")
            render_df(
                [["Smith", "Computer"]],
                ["instructor", "department"]
            )

            render_box("Removed transitive dependency", "#E6F4EA")

        # ---------------- 3NF → BCNF ----------------
        render_subtitle("3NF → BCNF")

        col1, col2 = st.columns(2)

        with col1:
            render_subtitle("❌ Before")
            render_df(
                [["Smith", "DB"], ["Smith", "ML"]],
                ["instructor", "course"]
            )
            render_box("Instructor determines course (not a candidate key)", "#FDECEA")

        with col2:
            render_subtitle("✅ After")

            render_df(
                [["Smith", "DB"], ["Smith", "ML"]],
                ["instructor", "course"]
            )

            render_box("Ensured determinant is candidate key", "#E6F4EA")

        # ---------------- MEMORY ----------------
        render_box("""
        🧠 Memory:
        1NF → Atomic  
        2NF → No Partial  
        3NF → No Transitive  
        BCNF → Strong Keys  
        """, "#E8F4FD")

        # ---------------- AI ----------------
        st.markdown("---")

        render_ai_chat(
                section_key="normalization",
                title="Ask about Normalization (1NF, 2NF, 3NF, BCNF)",
                topic="Data Modeling Normalization"
            )

    # =====================================================
    # 🟢 OLTP vs OLAP
    # =====================================================
    with tab2:
        render_title("OLTP vs OLAP")

        render_df([
            ["Purpose", "Run operations", "Analyze data"],
            ["Schema", "Normalized (3NF)", "Denormalized (Star Schema)"],
            ["Query", "Point lookup", "Aggregation"],
            ["Data Volume", "Current", "Historical"],
            ["Latency", "Low", "High"],
            ["Tech Stack", "MySQL, PostgreSQL", "StarRocks, BigQuery"],
        ], ["Aspect", "OLTP", "OLAP"])

        olap_col1, olap_col2 = st.columns(2)

        with olap_col1:
            render_box("""
            Example:
            Swiggy order placement → OLTP  
            Monthly analytics dashboard → OLAP  
            """, "#E6F4EA")

        with olap_col2:
            render_box("""
            🧠 Mnemonic:
            OLTP → Run business  
            OLAP → Analyze business  
            """, "#E8F4FD")

        st.markdown("---")

        render_ai_chat(
            section_key="oltp_olap",
            title="Ask about OLTP vs OLAP",
            topic="OLTP vs OLAP systems in real-world data engineering"
        )

    # =====================================================
    # 🔵 ER MODELING
    # =====================================================
    with tab3:
        render_title("ER Modeling")

        # =====================================================
        # 🔹 CONCEPTS (CARD UI)
        # =====================================================
        st.markdown("""
        <table style="width:100%; border-spacing:6px;">
            <tr>
                <td style="padding:8px; background:#E8F4FD; border-radius:0;">
                    <b>Entity</b><br>Real-world object (Customer, Order)
                </td>
                <td style="padding:8px; background:#E6F4EA; border-radius:0;">
                    <b>Attribute</b><br>Properties (name, id)
                </td>
                <td style="padding:8px; background:#FFF4E5; border-radius:0;">
                    <b>Relationship</b><br>Connection between entities
                </td>
            </tr>
        </table>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 VISUAL DIAGRAM
        # =====================================================
        render_subtitle("Visual ER Diagram")

        st.markdown("""
        <table style="width:100%; text-align:center; margin:10px 0;">
            <tr>
                <td style="padding:10px; border:2px solid #4CAF50; border-radius:0;">
                    <b>Customer</b><br>id<br>name
                </td>
                <td style="font-size:16px;">➜ places ➜</td>
                <td style="padding:10px; border:2px solid #2196F3; border-radius:0;">
                    <b>Order</b><br>order_id<br>amount
                </td>
            </tr>
        </table>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="padding:8px; background:#E8F4FD; border-radius:0;">
        Customer places Orders (1:M relationship)
        </div>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 CARDINALITY
        # =====================================================
        render_subtitle("Cardinality")

        st.markdown("""
        <table style="width:100%; text-align:center;">
            <tr>
                <td style="padding:8px; background:#FDECEA; border-radius:0;">
                    1 : 1 → One to One
                </td>
                <td style="padding:8px; background:#E6F4EA; border-radius:0;">
                    1 : M → One to Many
                </td>
                <td style="padding:8px; background:#FFF4E5; border-radius:0;">
                    M : N → Many to Many
                </td>
            </tr>
        </table>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 MANY-TO-MANY EXAMPLE
        # =====================================================
        render_subtitle("Many-to-Many Example")

        st.markdown("""
        <table style="width:100%; text-align:center; margin:10px 0;">
            <tr>
                <td style="padding:10px; border:2px solid #FF9800; border-radius:0;">
                    <b>Student</b>
                </td>
                <td style="font-size:16px;">⇄ enrolls ⇄</td>
                <td style="padding:10px; border:2px solid #9C27B0; border-radius:0;">
                    <b>Course</b>
                </td>
            </tr>
        </table>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="padding:8px; background:#E6F4EA; border-radius:0;">
        Resolved using bridge table (student_course)
        </div>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 TABLE MAPPING
        # =====================================================
        render_subtitle("Mapping ER → Tables")

        render_df(
            [
                ["students", "id, name"],
                ["courses", "id, title"],
                ["student_course", "student_id, course_id"]
            ],
            ["Table", "Columns"]
        )

        st.markdown("""
        <div style="padding:8px; background:#E8F4FD; border-radius:0;">
        🔥 Key Insight: M:N relationships are always broken into bridge tables.
        </div>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 REAL-WORLD EXAMPLE
        # =====================================================
        render_subtitle("Real-world Example")

        st.markdown("""
        <div style="padding:10px; background:#E6F4EA; border-radius:0;">
        <b>Netflix Example</b><br><br>

        - Users watch movies  
        - One user → many movies  
        - Many users → same movie  

        👉 M:N relationship → needs bridge table
        </div>
        """, unsafe_allow_html=True)

        # =====================================================
        # 🔹 AI QUESTIONS (UNCHANGED QUALITY)
        # =====================================================
        st.markdown("---")

        render_ai_chat(
            section_key="er_modeling",
            title="Ask about ER Modeling",
            topic="Entity Relationship Modeling and schema design"
        )

# =========================================================
# 2. DIMENSIONAL MODELING 
# =========================================================
def show_dimensional_modeling():

    st.header("Dimensional Modeling")

    tab1, tab2, tab3 = st.tabs([
        "Core Concepts",
        "Schemas & Dimensions",
        "Dimensional Changes (SCD)"
    ])

    # =====================================================
    # 🔹 TAB 1
    # =====================================================
    with tab1:

        st.markdown("### 🔥 Fact vs Dimension")


        df_compare = pd.DataFrame([
            ["Definition", "Stores measurable metrics for analysis", "Stores descriptive attributes for context"],
            ["Purpose", "Used for aggregations (SUM, COUNT)", "Used for filtering & grouping"],
            ["Data Type", "Numeric values", "Text / categorical"],
            ["Keys", "Contains foreign keys", "Contains primary keys"],
            ["Example", "sales_amt, quantity", "customer_name, city"]
        ], columns=["Aspect", "Fact Table", "Dimension Table"])

        st.dataframe(df_compare, use_container_width=True, hide_index=True)

        # ---------------- EXAMPLE TABLES ----------------
        st.markdown("### 📊 Example Tables")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Fact Table: Sales_Fact**")
            df_fact = pd.DataFrame([
                ["20240101", "P101", "C201", "500"],
                ["20240102", "P102", "C202", "300"]
            ], columns=["date_id", "product_id", "customer_id", "sales_amt"])

            st.dataframe(df_fact, hide_index=True)

        with col2:
            st.markdown("**Dimension Table: Customer_Dim**")
            df_dim = pd.DataFrame([
                ["C201", "John", "Bangalore"],
                ["C202", "Mike", "Chennai"]
            ], columns=["customer_id", "name", "city"])

            st.dataframe(df_dim, hide_index=True)

        # ---------------- VISUAL DIAGRAM ----------------
        st.markdown("### 🔷 Relationship Diagram")

        col_left, col_center, col_right = st.columns([1,2,1])

        with col_center:
            st.markdown("**⬆️ Dimensions connect to Fact**")

            c1, c2, c3 = st.columns(3)

            with c1:
                st.info("Customer_dim")
                st.info("Product_dim")

            with c2:
                st.success("Sales_Fact\n(Metrics)")

            with c3:
                st.info("Date_dim")
                st.info("Store_dim")

        # =====================================================
        # 🔹 KEYS (FIXED CONNECTED ROOT + BETTER DEFINITIONS)
        # =====================================================
        st.subheader("Keys")

        center = st.columns([1,2,1])
        with center[1]:
            st.markdown("""
            <div style="
                text-align:center;
                padding:10px;
                border:2px solid #4CAF50;
                border-radius:8px;
                font-weight:bold;">
                KEYS
            </div>
            """, unsafe_allow_html=True)

        # 🔥 CONNECT ROOT TO LINE (FIX)
        st.markdown("""
        <div style="display:flex;justify-content:center;">
            <div style="width:2px;height:20px;background:#999;"></div>
        </div>
        """, unsafe_allow_html=True)

        # MAIN LINE
        st.markdown("""
        <div style="width:100%;height:2px;background:#999;margin-bottom:5px;"></div>
        """, unsafe_allow_html=True)

        # ARROWS
        arrow_cols = st.columns(7)
        for col in arrow_cols:
            with col:
                st.markdown("""
                <div style="text-align:center;">
                    <div style="width:2px;height:16px;background:#999;margin:auto;"></div>
                    <div style="width:0;height:0;
                        border-left:4px solid transparent;
                        border-right:4px solid transparent;
                        border-top:6px solid #999;
                        margin:auto;"></div>
                </div>
                """, unsafe_allow_html=True)

        # BOXES (DETAILED DEFINITIONS)
        k1,k2,k3,k4,k5,k6,k7 = st.columns(7)

        box = "padding:8px;border:2px solid #2196F3;border-radius:8px;font-size:12px;text-align:center;"

        k1.markdown(f"<div style='{box}'><b>Primary Key</b><br>Uniquely identifies each row</div>", unsafe_allow_html=True)
        k2.markdown(f"<div style='{box}'><b>Foreign Key</b><br>Connects fact & dimension tables</div>", unsafe_allow_html=True)
        k3.markdown(f"<div style='{box}'><b>Natural Key</b><br>Business identifier like email/id</div>", unsafe_allow_html=True)
        k4.markdown(f"<div style='{box}'><b>Surrogate Key</b><br>System-generated key (used in SCD)</div>", unsafe_allow_html=True)
        k5.markdown(f"<div style='{box}'><b>Composite Key</b><br>Combination of multiple columns</div>", unsafe_allow_html=True)
        k6.markdown(f"<div style='{box}'><b>Candidate Key</b><br>Possible primary keys</div>", unsafe_allow_html=True)
        k7.markdown(f"<div style='{box}'><b>Alternate Key</b><br>Unused candidate key</div>", unsafe_allow_html=True)

        # EXAMPLE
        st.markdown("### 📊 Example")

        c1,c2 = st.columns(2)

        c1.dataframe(pd.DataFrame([
            [1,"C101","john@email.com","Bangalore"],
            [2,"C102","mike@email.com","Chennai"]
        ],columns=["cust_key (PK)","cust_id (NK)","email","city"]),hide_index=True)

        c2.dataframe(pd.DataFrame([
            [1,500],
            [2,300]
        ],columns=["cust_key (FK)","sales_amt"]),hide_index=True)


        # =====================================================
        # 🔹 GRAIN + MEASURES (SIDE BY SIDE)
        # =====================================================
        left,right = st.columns(2)

        # ---------------- GRAIN ----------------
        with left:
            st.subheader("Grain")

            st.dataframe(pd.DataFrame([
                ["Definition","Defines what one row represents"],
                ["Purpose","Controls level of detail"],
                ["Impact","Affects aggregation accuracy"]
            ],columns=["Aspect","Explanation"]),hide_index=True)

            st.markdown("**Example**")

            st.dataframe(pd.DataFrame([
                ["1001","iPhone","800"],
                ["1002","Laptop","1200"]
            ],columns=["order_id","product","amount"]),hide_index=True)

            st.dataframe(pd.DataFrame([
                ["2024-01-01","5000"],
                ["2024-01-02","7000"]
            ],columns=["date","total_sales"]),hide_index=True)

            st.dataframe(pd.DataFrame([
                ["Wrong Grain","Incorrect results"],
                ["Too High","Loss of detail"],
                ["Too Low","Performance issues"]
            ],columns=["Scenario","Impact"]),hide_index=True)

        # ---------------- MEASURES ----------------
        with right:
            st.subheader("Measures")

            st.dataframe(pd.DataFrame([
                ["Definition","Numeric values in fact table"],
                ["Usage","Used in aggregations"]
            ],columns=["Aspect","Explanation"]),hide_index=True)

            st.markdown("### Types")

            m1,m2,m3 = st.columns(3)

            m1.markdown("<div class='dm-box' style='border:2px solid #4CAF50;padding:8px;text-align:center'><b>Additive</b><br>Can sum across all dims<br>Ex: sales</div>", unsafe_allow_html=True)
            m2.markdown("<div class='dm-box' style='border:2px solid #ff9800;padding:8px;text-align:center'><b>Semi</b><br>Limited aggregation<br>Ex: balance</div>", unsafe_allow_html=True)
            m3.markdown("<div class='dm-box' style='border:2px solid #f44336;padding:8px;text-align:center'><b>Non</b><br>No aggregation<br>Ex: ratio</div>", unsafe_allow_html=True)


        render_ai_chat("dim_core","Ask about Core Concepts","Dimensional Modeling Core Concepts")


    # =====================================================
    # 🔹 TAB 2
    # =====================================================
    with tab2:

        col1, col2 = st.columns(2)

        # ---------------- STAR ----------------
        with col1:
            st.subheader("Star Schema")

            st.markdown("""
        <div style='text-align:center;font-size:12px'>

        <div class='dm-box' style='padding:6px;border:2px solid #4CAF50;display:inline-block'>
        Date_dim
        </div>

        <div>↓</div>

        <div style='display:flex;justify-content:center;align-items:center;gap:6px'>

        <div class='dm-box' style='padding:6px;border:2px solid #4CAF50'>
        Customer_dim
        </div>

        <div>→</div>

        <div class='dm-box' style='padding:8px;border:2px solid #2196F3;'>
        <b>Sales_fact</b>
        </div>

        <div>←</div>

        <div class='dm-box' style='padding:6px;border:2px solid #4CAF50'>
        Product_dim
        </div>

        </div>

        <div>↑</div>

        <div class='dm-box' style='padding:6px;border:2px solid #4CAF50;display:inline-block'>
        Store_dim
        </div>

        </div>
        """, unsafe_allow_html=True)


        # ---------------- SNOWFLAKE ----------------
        with col2:
            st.subheader("Snowflake Schema")

            st.markdown("""
        <div style='text-align:center;font-size:12px'>

        <div class='dm-box' style='padding:6px;border:2px solid #4CAF50;display:inline-block'>Category</div>
        <div>↓</div>
        <div class='dm-box' style='padding:6px;border:2px solid #4CAF50;display:inline-block'>Product</div>
        <div>↓</div>

        <div style='display:flex;justify-content:center;align-items:center;gap:8px'>

        <div class='dm-box' style='padding:6px;border:2px solid #4CAF50'>Date</div>

        <div>→</div>

        <div class='dm-box' style='padding:8px;border:2px solid #2196F3;'>
        <b>Sales_fact</b>
        </div>

        <div>←</div>

        <div class='dm-box' style='padding:6px;border:2px solid #4CAF50'>Store</div>

        </div>

        <div>↑</div>
        <div class='dm-box' style='padding:6px;border:2px solid #4CAF50;display:inline-block'>Customer</div>
        <div>↑</div>
        <div class='dm-box' style='padding:6px;border:2px solid #4CAF50;display:inline-block'>Region</div>

        </div>
        """, unsafe_allow_html=True)

        render_ai_chat("dim_schema","Ask about Schemas","Star & Snowflake")


    # =====================================================
    # 🔹 TAB 3
    # =====================================================
    with tab3:

        st.subheader("Dimension Types")

        # ROOT
        center = st.columns([1,2,1])
        with center[1]:
            st.markdown("""
            <div style='text-align:center;border:2px solid #4CAF50;padding:10px;font-weight:bold'>
            DIMENSION TYPES
            </div>
            """, unsafe_allow_html=True)

        # CONNECTOR
        st.markdown("""
        <div style='display:flex;justify-content:center'>
            <div style='width:2px;height:20px;background:#999'></div>
        </div>
        """, unsafe_allow_html=True)

        # MAIN LINE
        st.markdown("<div style='width:100%;height:2px;background:#999'></div>", unsafe_allow_html=True)

        # ARROWS
        arrow_cols = st.columns(7)
        for col in arrow_cols:
            col.markdown("""
            <div style="text-align:center;">
                <div style="width:2px;height:14px;background:#999;margin:auto;"></div>
                <div style="width:0;height:0;
                    border-left:4px solid transparent;
                    border-right:4px solid transparent;
                    border-top:6px solid #999;
                    margin:auto;"></div>
            </div>
            """, unsafe_allow_html=True)

        # BOXES WITH BETTER DEFINITIONS
        cols = st.columns(7)

        box = "border:2px solid #4CAF50;padding:8px;font-size:12px;text-align:center"

        cols[0].markdown(f"<div class='dm-box' style='{box}'><b>Conformed</b><br>Shared across multiple fact tables ensuring consistent reporting</div>", unsafe_allow_html=True)
        cols[1].markdown(f"<div class='dm-box' style='{box}'><b>Role Playing</b><br>Same dimension reused for different roles like order_date, ship_date</div>", unsafe_allow_html=True)
        cols[2].markdown(f"<div class='dm-box' style='{box}'><b>Degenerate</b><br>Dimension key stored in fact table without separate dimension table</div>", unsafe_allow_html=True)
        cols[3].markdown(f"<div class='dm-box' style='{box}'><b>Junk</b><br>Combines multiple low-cardinality flags into a single dimension</div>", unsafe_allow_html=True)
        cols[4].markdown(f"<div class='dm-box' style='{box}'><b>Bridge</b><br>Handles many-to-many relationships between dimensions</div>", unsafe_allow_html=True)
        cols[5].markdown(f"<div class='dm-box' style='{box}'><b>Hierarchical</b><br>Represents parent-child relationships like country → state → city</div>", unsafe_allow_html=True)
        cols[6].markdown(f"<div class='dm-box' style='{box}'><b>Factless</b><br>Stores relationships/events without numeric measures</div>", unsafe_allow_html=True)

        # =====================================================
        # 🔥 SCD TYPE 2 (SIMULATOR + FIXED UI + IMPLEMENTATION)
        # =====================================================
        st.subheader("SCD Type 2 Simulator")

        cities = ["Chennai", "Bangalore", "Hyderabad", "Mumbai"]

        # =====================================================
        # 🔹 INIT STATE
        # =====================================================
        if "scd_adv" not in st.session_state:
            st.session_state.scd_adv = pd.DataFrame([
                [1, "John", "Chennai", "2020-01-01", None, "Y"]
            ], columns=["id", "name", "city", "start_date", "end_date", "current"])


        # =====================================================
        # 🔹 FORM (ALIGNMENT FIXED)
        # =====================================================
        with st.form("scd_form"):

            c1, c2 = st.columns([2,1])

            with c1:
                new_city = st.selectbox("New City", cities)

            with c2:
                st.markdown("<br>", unsafe_allow_html=True)
                apply = st.form_submit_button("Apply Movement")


        # =====================================================
        # 🔹 PROCESS LOGIC (UNCHANGED)
        # =====================================================
        before = st.session_state.scd_adv.copy()

        if apply:
            df = before.copy()

            # expire old record
            df.loc[df["current"] == "Y", "end_date"] = str(datetime.now().date())
            df.loc[df["current"] == "Y", "current"] = "N"

            # insert new record
            new_row = pd.DataFrame([
                [1, "John", new_city, str(datetime.now().date()), None, "Y"]
            ], columns=df.columns)

            df = pd.concat([df, new_row], ignore_index=True)

            st.session_state.scd_adv = df

        after = st.session_state.scd_adv


        # =====================================================
        # 🔹 SIDE-BY-SIDE VIEW
        # =====================================================
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("### Before")
            st.dataframe(before, use_container_width=False, hide_index=True)

        with c2:
            st.markdown("### After")
            st.dataframe(after, use_container_width=False, hide_index=True)


        # =====================================================
        # 🔹 FLOW EXPLANATION
        # =====================================================
        st.markdown("""
        **Flow:**
        - Old Row → Expired (end_date updated, current = N)  
        - New Row → Inserted (current = Y)  
        - Full History → Preserved  
        """)


        # =====================================================
        # 🔥 IMPLEMENTATION (OPTIMIZED WITH TOGGLE)
        # =====================================================
        st.subheader("SCD Type 2 Implementation")

        mode = st.radio(
            "Choose Implementation",
            ["SQL", "PySpark"],
            horizontal=True
        )

        # ---------------- SQL ----------------
        if mode == "SQL":
            st.code("""
        -- STEP 1: Expire existing record
        UPDATE dim_customer
        SET end_date = CURRENT_DATE, current = 'N'
        WHERE customer_id = 1 AND current = 'Y';

        -- STEP 2: Insert new record
        INSERT INTO dim_customer (customer_id, name, city, start_date, end_date, current)
        VALUES (1, 'John', 'Bangalore', CURRENT_DATE, NULL, 'Y');
        """)

        # ---------------- PYSPARK ----------------
        else:
            st.code("""
        from pyspark.sql.functions import current_date, lit

        # STEP 1: Separate current and history
        current_df = df.filter("current = 'Y'")
        history_df = df.filter("current = 'N'")

        # STEP 2: Expire current records
        expired_df = current_df.withColumn("end_date", current_date()) \\
                            .withColumn("current", lit("N"))

        # STEP 3: Create new record
        new_data = [(1, "John", "Bangalore", None, None, "Y")]

        new_df = spark.createDataFrame(new_data, df.columns) \\
                    .withColumn("start_date", current_date())

        # STEP 4: Merge all data
        final_df = history_df.union(expired_df).union(new_df)
        """)

        # =====================================================
        # 🔥 KEY TAKEAWAY
        # =====================================================
        st.markdown("""
        ### 🔥 Key Flow

        - Existing active row → **expired (end_date updated)**
        - New row → **inserted with current = Y**
        - Old data → **preserved (history maintained)**

        👉 This is the core of **Slowly Changing Dimension Type 2**
        """)


        render_ai_chat("dim_scd","Ask about SCD","SCD Type 2")
# =========================================================
# 3. DATA WAREHOUSE ARCHITECTURE
# =========================================================
def show_architecture():
    st.header("Architecture")
    st.caption(
        "This section mirrors the core architecture diagrams: warehouse layers, data marts, bus architecture, "
        "lakehouse modeling, late arriving data handling, reconciliation, and data mesh."
    )

    tab1, tab2, tab3 = st.tabs([
        "Warehouse & Advanced Modeling",
        "Lakehouse Data Modeling",
        "Data Mesh Architecture",
    ])

    with tab1:
        render_warehouse_architecture_workspace()

    with tab2:
        render_lakehouse_architecture_workspace()

    with tab3:
        render_data_mesh_architecture_workspace()

    render_ai_chat(
        "dm_architecture",
        "Ask about Data Warehouse, Lakehouse, and Data Mesh Architecture",
        "Data warehouse layers, bus architecture, ETL modeling, late arriving data, lakehouse architecture, and data mesh"
    )


# =========================================================
# 4. DISTRIBUTED MODELING (your page 7.7)
# =========================================================
def show_distributed_modeling():
    st.header("Distributed Data Modeling")
    st.caption(
        "This workspace covers distributed execution, partitioning, skew, data locality, and the serving or "
        "streaming architecture patterns that support distributed analytics."
    )

    tab1, tab2 = st.tabs([
        "Execution & Partitioning",
        "Architecture Patterns & Access",
    ])

    with tab1:
        render_distributed_cluster_workspace()

    with tab2:
        render_access_patterns_workspace()

    render_ai_chat(
        "dm_distributed",
        "Ask about Distributed Data Modeling",
        "data locality, distributed joins, partitioning, skew handling, Lambda, Kappa, CDC, serving layers, and data access optimization"
    )


# =========================================================
# 5. INTERVIEW MODE (STEP 3)
# =========================================================
def show_interview_mode():
    st.header("Interview Mode")
    st.caption(
        "Practice curated data modeling interview questions across fundamentals, dimensional modeling, architecture, "
        "and distributed concepts with deterministic scoring and a final report."
    )

    if st.session_state.get(DM_INTERVIEW_STATE_KEY):
        render_dm_active_interview()
        return

    if st.session_state.get(DM_INTERVIEW_REPORT_KEY):
        render_dm_interview_report()
        return

    render_dm_interview_setup()
