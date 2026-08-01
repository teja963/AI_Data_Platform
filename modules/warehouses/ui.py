import pandas as pd
import streamlit as st

from core.practical_learning import WAREHOUSE_ENGINES, execute_warehouse_query
from core.practice_state import load_practice_state, save_practice_state


DEFAULT_QUERY = """SELECT
    region,
    COUNT(*) AS order_count,
    ROUND(SUM(amount), 2) AS revenue
FROM orders
GROUP BY region
ORDER BY revenue DESC;"""


ENGINE_DESIGN = {
    "Amazon Redshift": {
        "distribution": "AUTO or customer_id for colocated customer joins",
        "partitioning": "Sort key on order_date",
        "scaling": "RA3/Serverless, concurrency scaling, WLM",
        "maintenance": "ANALYZE statistics and VACUUM when required",
    },
    "Google BigQuery": {
        "distribution": "Managed distributed storage",
        "partitioning": "PARTITION BY order_date; CLUSTER BY customer_id, region",
        "scaling": "On-demand bytes scanned or slot reservations",
        "maintenance": "Control wildcard scans, partitions, and materialized views",
    },
    "Snowflake": {
        "distribution": "Automatic micro-partitioning",
        "partitioning": "Optional clustering key for persistent pruning problems",
        "scaling": "Independent virtual warehouses and multi-cluster scaling",
        "maintenance": "Monitor pruning, spill, cache, and warehouse sizing",
    },
    "StarRocks": {
        "distribution": "HASH(customer_id) buckets with colocated strategy when useful",
        "partitioning": "Range partition by order_date",
        "scaling": "Add CN/BE capacity; use workload groups",
        "maintenance": "Compaction, tablets, replicas, statistics, materialized views",
    },
    "Athena / Trino": {
        "distribution": "Workers read split files from object storage",
        "partitioning": "Catalog partitions and partition projection",
        "scaling": "Managed/serverless or worker autoscaling",
        "maintenance": "Compact files, use Parquet, and reduce scanned columns",
    },
}


def render_warehouses():
    username = st.session_state.get("user")
    marker = f"warehouse_loaded::{username}"
    if not st.session_state.get(marker):
        saved = load_practice_state(username, "warehouses") or {}
        if saved.get("query"):
            st.session_state["warehouse_query"] = saved["query"]
        if saved.get("result"):
            st.session_state["warehouse_result"] = saved["result"]
        st.session_state[marker] = True
    st.title("Data Warehouses & Query Engines")
    engine = st.selectbox("Engine", list(WAREHOUSE_ENGINES))
    overview_tab, sql_tab, design_tab, troubleshoot_tab = st.tabs(
        ["Learn", "SQL Practice", "Physical Design", "Troubleshoot & Interview"]
    )

    with overview_tab:
        st.subheader(engine)
        st.write(WAREHOUSE_ENGINES[engine])
        comparison = [
            {
                "Engine": name,
                "Primary model": value.split(".")[0],
            }
            for name, value in WAREHOUSE_ENGINES.items()
        ]
        st.dataframe(pd.DataFrame(comparison), width="stretch", hide_index=True)

    with sql_tab:
        st.caption(
            f"The execution engine uses a safe local dataset while the design guidance follows {engine}."
        )
        query = st.text_area(
            "Read-only SQL",
            value=st.session_state.get("warehouse_query", DEFAULT_QUERY),
            height=260,
        )
        if st.button("Run Warehouse Query", type="primary"):
            try:
                st.session_state["warehouse_query"] = query
                st.session_state["warehouse_result"] = execute_warehouse_query(query)
                save_practice_state(
                    username,
                    "warehouses",
                    {
                        "query": query,
                        "result": st.session_state["warehouse_result"],
                    },
                )
            except ValueError as error:
                st.error(str(error))
        result = st.session_state.get("warehouse_result")
        if result:
            st.dataframe(pd.DataFrame(result["rows"]), width="stretch", hide_index=True)
            with st.expander("Execution plan"):
                st.code("\n".join(result["plan"]), language="text")
                st.write(
                    "Translate this logical plan into the selected engine’s concerns: "
                    "scan pruning, redistribution/shuffle, join strategy, spill, slots or WLM."
                )

    with design_tab:
        design = ENGINE_DESIGN[engine]
        rows = [
            {"Decision": key.replace("_", " ").title(), "Recommendation": value}
            for key, value in design.items()
        ]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.markdown("**Design exercise**")
        st.code(
            "FactOrders(order_id, customer_id, product_id, region, amount, order_date)\n"
            "Dimensions: Customer, Product, Calendar",
            language="text",
        )
        st.write(
            "Choose partitioning, distribution/clustering, materialized views, workload isolation, "
            "and retention for a dashboard plus ad-hoc analytics workload."
        )

    with troubleshoot_tab:
        scenarios = {
            "Large scan": "Verify partition filters, selected columns, file format, clustering, and stale statistics.",
            "Data skew": "Inspect key cardinality and worker distribution; salt or choose a better distribution key.",
            "Spill to disk": "Reduce intermediate data, improve joins, increase memory/warehouse size, and isolate workloads.",
            "Queue delay": "Inspect Redshift WLM, Snowflake warehouse concurrency, BigQuery slots, or StarRocks workload groups.",
            "Slow repeated dashboard": "Use aggregate tables/materialized views and validate refresh strategy.",
        }
        scenario = st.selectbox("Scenario", list(scenarios))
        st.warning(scenarios[scenario])
        st.markdown("**Interview answer sequence**")
        st.write(
            "Establish the SLA → inspect scan and plan → identify distribution/partition issue → "
            "measure spill/skew/queueing → apply the smallest change → prove improvement."
        )
