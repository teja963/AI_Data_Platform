import pandas as pd
import streamlit as st


PROJECTS_CATALOG = {
    "Samsung R&D": [
        {
            "key": "samsung_project_1",
            "title": "Project 1: Real-Time Analytics Pipeline (600 GB/day)",
            "subtitle": "Kafka + Sumo Logic + Airflow + StarRocks for low-latency OLAP dashboards",
            "requirements": [
                "Ingest 600 GB/day from Kafka (400 GB) and Sumo Logic (200 GB).",
                "Keep raw freshness under 5 minutes and aggregated freshness around 52-60 minutes.",
                "Hold 99.8% uptime while staying cheaper than fully managed cloud services.",
            ],
            "storyline": [
                "I built a hybrid ingestion pipeline where Kafka handled high-throughput device traffic and Sumo Logic covered external operational search pulls.",
                "Airflow orchestrated ingestion, validation, silver curation, gold aggregation, and StarRocks loads on a 5-minute cadence.",
                "StarRocks served dashboards and analyst slices with low-latency OLAP behavior while keeping the cost model infra-only instead of per-query.",
                "Reliability came from replay, idempotent event keys, RF=3 / ISR=2 Kafka durability, and partition-aware recovery across the whole DAG.",
            ],
            "comparisons": [
                {
                    "title": "Kafka vs Kinesis vs Pub/Sub",
                    "columns": ["Aspect", "Kafka", "Kinesis", "Pub/Sub"],
                    "rows": [
                        ["Deployment", "Self-hosted on VMs / K8s", "Fully managed AWS", "Fully managed GCP"],
                        ["Core engine", "Distributed log (append-only)", "Sharded stream service", "Message broker abstraction"],
                        ["Ordering + replay", "Strict ordering per partition + offset replay", "Ordering per shard + limited replay", "Ordering keys + time-based replay"],
                        ["Cost model", "Infra only (disk + compute)", "Pay per shard + throughput", "Pay per data volume"],
                        ["Why chosen", "Strict ordering + replay + private cloud fit", "-", "-"],
                    ],
                },
                {
                    "title": "StarRocks vs Redshift vs BigQuery",
                    "columns": ["Aspect", "StarRocks", "Redshift", "BigQuery"],
                    "rows": [
                        ["Deployment", "Self-managed", "AWS managed", "GCP managed"],
                        ["Core engine", "MPP OLAP engine (FE + BE)", "Managed MPP columnar cluster", "Serverless MPP"],
                        ["Execution model", "Vectorized, in-memory, hot data in RAM", "Disk + cache", "Large scan model"],
                        ["Latency", "Milliseconds to seconds", "Seconds", "Seconds to minutes"],
                        ["Cost model", "Infra only", "Pay for cluster", "Pay per data scanned"],
                        ["Why chosen", "Open-source + low-latency OLAP + no per-query cost", "-", "-"],
                    ],
                },
                {
                    "title": "Airflow vs Dagster vs Prefect",
                    "columns": ["Aspect", "Airflow", "Dagster", "Prefect"],
                    "rows": [
                        ["Execution model", "DAG-based scheduler", "Asset-based orchestration", "Flow-based orchestration"],
                        ["Dependency flow", "Task DAG from raw to dashboard", "Asset graph", "Task / flow graph in code"],
                        ["Backfill support", "Native and stable", "Good", "Good"],
                        ["Retry semantics", "Task-level retries", "Asset retries", "Task / flow retries"],
                        ["Scale pattern", "Executor-based (Celery / K8s)", "K8s-native", "K8s-native"],
                        ["Why chosen", "Mature + proven + large operator ecosystem", "-", "-"],
                    ],
                },
            ],
            "sizing": [
                {
                    "title": "Kafka Throughput",
                    "body": "400 GB/day * 1.2 headroom is about 4.8 MB/sec average. Peak at 1.5x is roughly 7.2 MB/sec, so 24 partitions on a 3-broker cluster keeps parallelism and headroom balanced.",
                },
                {
                    "title": "Kafka Reliability",
                    "body": "RF=3 and ISR=2 require at least 3 brokers. The design keeps strict partition replay while still surviving a broker failure without dropping durability guarantees.",
                },
                {
                    "title": "StarRocks Storage",
                    "body": "600-700 GB/day after enrichment for 90 days reaches about 63 TB raw. With roughly 5:1 compression, that is about 12.6 TB stored across 3 BE nodes + 1 FE node.",
                },
                {
                    "title": "Airflow Layout",
                    "body": "One DAG with 6-7 tasks covers Kafka ingest, Sumo ingest, validation, filtering, aggregation, and StarRocks publish. The cluster stays simple because orchestration complexity is low while operational visibility remains high.",
                },
            ],
            "sizing_strategy": [
                {
                    "step": "Start from traffic",
                    "method": "Convert daily GB into average MB/sec, then apply peak headroom.",
                    "decision": "400 GB/day Kafka input becomes ~4.8 MB/sec average and ~7.2 MB/sec peak.",
                },
                {
                    "step": "Map throughput to partitions",
                    "method": "Choose partitions from consumer parallelism, replay needs, and growth headroom.",
                    "decision": "24 partitions support replay, rebalancing, and future scale without oversharding.",
                },
                {
                    "step": "Map durability to brokers",
                    "method": "Replica factor and ISR define the broker floor.",
                    "decision": "RF=3 and ISR=2 mean at least 3 brokers for safe durability.",
                },
                {
                    "step": "Map retention to storage",
                    "method": "Daily curated volume * retention days / compression ratio.",
                    "decision": "63 TB raw at 90 days becomes ~12.6 TB stored after compression.",
                },
            ],
            "architecture_focus": {
                "Ordering & Replay": [
                    "Kafka partition keys preserve per-entity ordering while offsets make replay deterministic.",
                    "Sumo pulls checkpoint windows so retries resume from the exact cursor position.",
                    "Replay is safe because silver dedupes on event_id before gold aggregation.",
                ],
                "Data Quality": [
                    "Validation happens in silver: null checks, ranges, type enforcement, and duplicate filtering.",
                    "Bad records can be quarantined before they pollute dashboard-facing gold tables.",
                    "Load labels and idempotent keys prevent duplicate inserts in StarRocks.",
                ],
                "Latency & Cost": [
                    "Raw freshness is optimized at ingest, while gold freshness trades some delay for stable aggregates.",
                    "StarRocks was chosen to avoid per-query billing while still keeping OLAP response times low.",
                    "Partition pruning and materialized views are the main levers for dashboard speed.",
                ],
                "Reliability": [
                    "Kafka durability comes from RF=3, ISR=2, and acks=all.",
                    "Airflow retries remain safe because each partition window is idempotent.",
                    "Freshness SLA is tracked across lag, DAG latency, and StarRocks load time.",
                ],
            },
            "failure_scenarios": [
                {
                    "name": "Kafka lag spike",
                    "component": "Ingestion",
                    "problem": "Consumers fall behind offsets and the freshness SLA starts drifting.",
                    "fix": "Scale consumers, rebalance, add partitions, and reduce batch size until lag clears.",
                    "example": "Like opening more counters when the cinema line becomes too long.",
                    "interview": [
                        "How do you handle Kafka lag spikes in production?",
                        "How do you track freshness end-to-end when lag rises?",
                    ],
                },
                {
                    "name": "Sumo API throttling",
                    "component": "Ingestion",
                    "problem": "The API rate-limits requests, so batch windows start missing data.",
                    "fix": "Reduce batch size, use exponential backoff, and checkpoint the cursor so retries resume safely.",
                    "example": "Like sending smaller groups through a stadium gate to avoid traffic jams.",
                    "interview": [
                        "How do you handle Sumo API throttling without data loss?",
                        "How do you keep retries idempotent for external APIs?",
                    ],
                },
                {
                    "name": "Airflow worker OOM",
                    "component": "Orchestration",
                    "problem": "A task takes too much memory and the worker dies mid-run.",
                    "fix": "Reduce batch size, split tasks, increase memory, and retry with backoff on the same partition window.",
                    "example": "Like carrying fewer grocery bags so you do not drop everything at once.",
                    "interview": [
                        "How do you handle Airflow failures and retries safely?",
                        "How do you keep a retry from duplicating downstream data?",
                    ],
                },
                {
                    "name": "StarRocks query timeout",
                    "component": "Storage",
                    "problem": "Large joins or scans blow up latency for dashboard users.",
                    "fix": "Partition by date, use materialized views, colocate joins, and prune unused columns.",
                    "example": "Like searching only today's folder instead of the entire cabinet.",
                    "interview": [
                        "How do you optimize StarRocks query latency?",
                        "How do you choose distribution keys in StarRocks?",
                    ],
                },
                {
                    "name": "Backend node down",
                    "component": "Storage",
                    "problem": "A StarRocks BE node fails and replicas must recover before queries stabilize.",
                    "fix": "Rebalance replicas, trigger recovery, and add capacity if the failure exposes low headroom.",
                    "example": "Like moving customers to the other open counters when one closes.",
                    "interview": [
                        "What is your reliability strategy for Kafka and StarRocks?",
                        "How do you reduce cost while maintaining SLA headroom?",
                    ],
                },
            ],
            "code_language": "python",
            "code": """from datetime import datetime, timedelta
import json
import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

SUMO_ENDPOINT = "https://api.sumologic.com/api/v1/search/jobs"
STARROCKS_FE = "http://starrocks-fe:8030"
DB = "analytics"
SILVER_TABLE = "silver_events"
GOLD_TABLE = "gold_kpis"


def pull_sumo():
    payload = {"query": "_sourceCategory=prod", "from": "now-5m", "to": "now"}
    r = requests.post(SUMO_ENDPOINT, json=payload, timeout=30)
    r.raise_for_status()
    job_id = r.json()["id"]
    results = requests.get(f"{SUMO_ENDPOINT}/{job_id}/messages", timeout=30).json()
    write_to_staging("raw_sumo_events", results)


def ingest_kafka():
    events = read_kafka(topic="device_events", max_records=50000)
    write_to_staging("raw_kafka_events", events)


def build_silver():
    raw = read_from_staging(["raw_kafka_events", "raw_sumo_events"])
    cleaned = []
    seen = set()
    for e in raw:
        eid = e.get("event_id")
        if eid in seen:
            continue
        seen.add(eid)
        cleaned.append(
            {
                "event_id": eid,
                "device_id": e.get("device_id"),
                "event_ts": e.get("event_ts"),
                "source": e.get("source"),
                "payload": e.get("payload"),
                "ingest_ts": datetime.utcnow().isoformat(),
            }
        )
    write_to_staging("silver_events", cleaned)


def build_gold():
    silver = read_from_staging(["silver_events"])
    agg = {}
    for e in silver:
        hour = e["event_ts"][:13]
        key = (hour, e["device_id"])
        agg.setdefault(key, {"cnt": 0})
        agg[key]["cnt"] += 1
    gold = [{"hour": k[0], "device_id": k[1], "event_count": v["cnt"]} for k, v in agg.items()]
    write_to_staging("gold_kpis", gold)


def load_starrocks(table, data):
    url = f"{STARROCKS_FE}/api/{DB}/{table}/_stream_load"
    headers = {"label": f"{table}_{int(datetime.utcnow().timestamp())}", "format": "json"}
    r = requests.put(url, data=json.dumps(data), headers=headers, timeout=60)
    r.raise_for_status()


def load_starrocks_task():
    silver = read_from_staging(["silver_events"])
    gold = read_from_staging(["gold_kpis"])
    load_starrocks(SILVER_TABLE, silver)
    load_starrocks(GOLD_TABLE, gold)


default_args = {"retries": 3, "retry_delay": timedelta(minutes=2)}

with DAG(
    dag_id="project1_realtime_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule_interval="*/5 * * * *",
    catchup=False,
    default_args=default_args,
) as dag:
    t1 = PythonOperator(task_id="sumo_pull", python_callable=pull_sumo)
    t2 = PythonOperator(task_id="kafka_ingest", python_callable=ingest_kafka)
    t3 = PythonOperator(task_id="build_silver", python_callable=build_silver)
    t4 = PythonOperator(task_id="build_gold", python_callable=build_gold)
    t5 = PythonOperator(task_id="load_starrocks", python_callable=load_starrocks_task)
    [t1, t2] >> t3 >> t4 >> t5""",
            "code_breakdown": [
                "Parallel raw landing from Sumo and Kafka feeds into staging.",
                "Silver enforces schema normalization and deduplicates by event_id.",
                "Gold aggregates KPI output by hour and device for dashboard consumption.",
                "The final load uses StarRocks stream-load labels so retries stay idempotent.",
            ],
        },
        {
            "key": "samsung_project_2",
            "title": "Project 2: Beam on Spark to S3 (10 TB/day)",
            "subtitle": "Kafka + Schema Registry + Apache Beam on Spark + S3 Parquet for analytics and ML",
            "requirements": [
                "Process 10 TB/day across 3 regions with a 4-hour SLA.",
                "Maintain 96% data quality with schema validation, completeness, null thresholds, range checks, and duplicate control.",
                "Handle schema drift, duplicates, late data, and shuffle-heavy execution while keeping S3 and Athena costs controlled.",
            ],
            "storyline": [
                "I built a Beam pipeline running on Spark so the same logical model could support batch and streaming style processing on one code path.",
                "Kafka handled region-based ingestion, Schema Registry controlled evolution, and Spark executors processed windows, dedupe, enrichment, and aggregates.",
                "S3 stored partitioned Parquet for low-cost retention and Athena or ML consumers read the curated outputs without needing a heavyweight OLAP cluster.",
                "Operational stability came from watermark handling, allowed lateness, dedup keys, regional partitioning, and executor sizing for shuffle-heavy workloads.",
            ],
            "comparisons": [
                {
                    "title": "Beam on Spark vs Pure Spark vs Flink",
                    "columns": ["Aspect", "Beam on Spark", "Pure Spark", "Flink"],
                    "rows": [
                        ["Programming model", "Unified model for batch + streaming", "Spark API", "Native streaming"],
                        ["Abstraction", "PCollection", "RDD / DataFrame", "DataStream"],
                        ["Time semantics", "Event time + watermarks + triggers", "Supported", "Native"],
                        ["Portability", "Runner-based", "Spark only", "Flink only"],
                        ["Why chosen", "Same code supports batch + streaming and stays portable", "-", "-"],
                    ],
                },
                {
                    "title": "S3 + Athena vs Redshift vs BigQuery",
                    "columns": ["Aspect", "S3 + Athena", "Redshift", "BigQuery"],
                    "rows": [
                        ["Storage", "Object store + Parquet", "Managed columnar", "Managed storage"],
                        ["Query cost", "Pay per scanned TB", "Cluster cost", "Pay per scanned TB"],
                        ["Ideal workload", "Batch + ML training", "Low-latency OLAP", "Ad-hoc analytics"],
                        ["Why chosen", "Cheapest fit for 10 TB/day + ML workloads", "-", "-"],
                    ],
                },
            ],
            "sizing": [
                {
                    "title": "Throughput Target",
                    "body": "10 TB in 4 hours means roughly 700 MB/sec sustained throughput through the processing layer.",
                },
                {
                    "title": "Executor Count",
                    "body": "At around 35 MB/sec per executor, 20 executors gives enough working capacity with room for shuffle pressure and regional imbalance.",
                },
                {
                    "title": "Executor Shape",
                    "body": "Executors are sized around 8 vCPU / 32 GB because the pipeline is shuffle-heavy and benefits from memory plus CPU balance.",
                },
                {
                    "title": "Kafka Cluster",
                    "body": "At 700 MB/sec read and about 200 MB/sec per broker, 5 brokers (4 active + 1 HA) and 120 partitions line up with executor parallelism and skew control.",
                },
            ],
            "sizing_strategy": [
                {
                    "step": "Translate SLA into throughput",
                    "method": "Required throughput = total volume / completion window.",
                    "decision": "10 TB in 4 hours drives a sustained target near 700 MB/sec.",
                },
                {
                    "step": "Translate throughput into executors",
                    "method": "Per-executor throughput target * safety margin defines executor count.",
                    "decision": "20 executors at ~35 MB/sec each create room for shuffle-heavy workloads.",
                },
                {
                    "step": "Translate throughput into partitions",
                    "method": "Partitions should exceed active parallel workers so skew and retries stay manageable.",
                    "decision": "120 partitions align with Spark parallelism and cross-region balancing.",
                },
                {
                    "step": "Translate output pattern into storage shape",
                    "method": "Pick file size, partition key, and compaction window from scan-cost goals.",
                    "decision": "dt/hour Parquet with compaction keeps Athena scans and S3 small-file overhead under control.",
                },
            ],
            "architecture_focus": {
                "Schema Drift": [
                    "Schema Registry enforces compatibility and lets new fields land with defaults instead of breaking the pipeline.",
                    "Bad records are quarantined rather than silently dropped into curated data.",
                    "This is the answer path for schema mismatch and evolution interview questions.",
                ],
                "Late Data": [
                    "Beam uses event time, watermarks, and allowed lateness to keep late records inside a controlled window.",
                    "Extreme late arrivals are handled with backfill and replay patterns rather than ad hoc patching.",
                    "The storage layout keeps reprocessing partition-aligned.",
                ],
                "Dedup & Correctness": [
                    "Dedup uses idempotent keys like event_id + device_id inside a window before downstream write.",
                    "Write temp then commit-on-success patterns help keep S3 outputs clean.",
                    "Regional streams stay isolated enough to debug replay safely.",
                ],
                "Cost & Performance": [
                    "Partitioning by dt/hour and compacting to 128-512 MB files keeps Athena scans cheap.",
                    "Beam on Spark avoids locking the team into a single execution engine while keeping Spark's scale characteristics.",
                    "Combiners and pre-aggregation reduce wide shuffle cost.",
                ],
            },
            "failure_scenarios": [
                {
                    "name": "Kafka lag spike",
                    "component": "Ingestion",
                    "problem": "Production events arrive faster than the pipeline can consume them.",
                    "fix": "Scale executors, increase partitions, and verify broker throughput before lag compounds across regions.",
                    "example": "Like adding more chefs and splitting orders when the kitchen gets overloaded.",
                    "interview": [
                        "How do you size the cluster for 700 MB/sec?",
                        "How do you handle backpressure during spikes?",
                    ],
                },
                {
                    "name": "Schema mismatch",
                    "component": "Schema Registry",
                    "problem": "Upstream adds or changes fields and the parser can no longer trust the payload shape.",
                    "fix": "Use schema compatibility rules, defaults, and quarantine for incompatible records.",
                    "example": "Like a new form field appearing while old forms still need to keep working.",
                    "interview": [
                        "How do you manage schema drift safely?",
                        "How do you validate data quality at scale?",
                    ],
                },
                {
                    "name": "Executor OOM",
                    "component": "Processing",
                    "problem": "Shuffle or batch volume blows up executor memory and tasks restart.",
                    "fix": "Reduce micro-batch size, add combiners, increase executor memory, and move off expensive groupByKey patterns.",
                    "example": "Like boiling a smaller pot so it does not overflow.",
                    "interview": [
                        "How do you handle executor OOM errors?",
                        "How do you control shuffle costs?",
                    ],
                },
                {
                    "name": "Data skew",
                    "component": "Processing",
                    "problem": "Hot keys overload a few tasks while the rest of the cluster sits underutilized.",
                    "fix": "Salt keys, repartition by hash(device_id, hour), and avoid groupByKey when combine patterns work.",
                    "example": "Like splitting one huge table into smaller tables so every waiter stays busy.",
                    "interview": [
                        "How do you handle data skew in Spark?",
                        "How do you deduplicate at scale without expensive shuffles?",
                    ],
                },
                {
                    "name": "S3 / Athena cost spike",
                    "component": "Storage",
                    "problem": "Too many small files or poor partitioning makes Athena scan far more data than necessary.",
                    "fix": "Retry temp writes safely, compact files to 128-512 MB, and partition by dt/hour so queries hit only the needed slices.",
                    "example": "Like searching only the right folder instead of scanning the entire drive.",
                    "interview": [
                        "How do you keep S3 costs low at 10 TB/day?",
                        "How do you avoid small files in S3?",
                    ],
                },
            ],
            "code_language": "python",
            "code": """import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.transforms.window import FixedWindows
import json


def parse_event(kv):
    value = kv[1].decode("utf-8")
    e = json.loads(value)
    return {
        "event_id": e["event_id"],
        "device_id": e["device_id"],
        "event_ts": e["event_ts"],
        "region": e.get("region", "unknown"),
        "payload": e.get("payload", {}),
    }


def enrich_event(e):
    e["device_type"] = lookup_device_type(e["device_id"])
    return e


def key_by_device(e):
    return (e["device_id"], e)


def combine_metrics(values):
    return {
        "count": len(values),
        "unique_events": len({v["event_id"] for v in values}),
    }


options = PipelineOptions(streaming=True, save_main_session=True)

with beam.Pipeline(options=options) as p:
    events = (
        p
        | "ReadKafka" >> beam.io.ReadFromKafka(
            consumer_config={"bootstrap.servers": "kafka:9092"},
            topics=["region_logs"],
        )
        | "Parse" >> beam.Map(parse_event)
        | "Window1h" >> beam.WindowInto(FixedWindows(60 * 60))
        | "Dedup" >> beam.Distinct(key=lambda e: (e["event_id"], e["device_id"]))
        | "Enrich" >> beam.Map(enrich_event)
    )

    aggregated = (
        events
        | "KeyByDevice" >> beam.Map(key_by_device)
        | "GroupByDevice" >> beam.GroupByKey()
        | "Aggregate" >> beam.Map(lambda kv: (kv[0], combine_metrics(list(kv[1]))))
    )

    (
        aggregated
        | "WriteParquet" >> WriteToParquet(
            file_path_prefix="s3://bucket/logs/dt=YYYY-MM-DD/",
            file_name_suffix=".parquet",
        )
    )""",
            "code_breakdown": [
                "Kafka input is normalized first so downstream steps use a stable schema.",
                "Windowing and dedup happen before heavy aggregation, which is critical for both correctness and shuffle control.",
                "Enrichment adds metadata needed for ML and analytics without making the raw ingest path more complex.",
                "Partitioned Parquet to S3 is the cost-optimized serving layer for Athena and ML training workloads.",
            ],
        },
    ],
    "Skan AI": [],
}


def build_stage_box(title, lines=None, active=False, emphasis="neutral", min_height=58):
    class_name = "project-card"
    border_width = "1px"

    if emphasis == "focus":
        if active:
            class_name += " project-focus"
            border_width = "2px"
    elif emphasis == "failure":
        if active:
            class_name += " project-failure"
            border_width = "2px"

    details = lines or []
    if isinstance(details, str):
        details = [details]
    body = "".join(
        f"<div style='font-size:10px;line-height:1.2;margin-top:3px;opacity:0.8;'>{line}</div>"
        for line in details
    )
    return (
        f"<div class='{class_name}' style='border-width:{border_width};border-radius:0;"
        f"padding:8px;min-height:{min_height}px;text-align:center;'>"
        f"<div style='font-weight:700;font-size:12px;'>{title}</div>{body}</div>"
    )


def render_panel(body_html):
    st.markdown(
        f"""
        <div class='project-card' style="padding:14px;margin-bottom:14px;">
            {body_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_table(title, columns, rows):
    st.markdown(f"#### {title}")
    st.dataframe(pd.DataFrame(rows, columns=columns), use_container_width=True, hide_index=True)


def render_requirements(project):
    st.markdown("### Client Requirement")
    cols = st.columns(min(len(project["requirements"]), 3))
    for idx, requirement in enumerate(project["requirements"]):
        with cols[idx % len(cols)]:
            st.markdown(
                f"<div class='project-card' style='padding:12px;min-height:108px;'>"
                f"<b>Requirement {idx + 1}</b><br><br>{requirement}</div>",
                unsafe_allow_html=True,
            )


def render_storyline(project):
    st.markdown("### One-Minute Storyline")
    cols = st.columns(4)
    for idx, line in enumerate(project["storyline"]):
        with cols[idx]:
            st.markdown(
                f"<div class='project-card' style='padding:12px;min-height:138px;'>"
                f"<b>Column {idx + 1}</b><br><br>{line}</div>",
                unsafe_allow_html=True,
            )


def render_tradeoffs(project):
    st.markdown("### Technical Comparison and Trade-Offs")
    for comparison in project["comparisons"]:
        render_table(comparison["title"], comparison["columns"], comparison["rows"])


def render_sizing(project):
    st.markdown("### Infrastructure Sizing Strategy")
    strategy_rows = [
        [item["step"], item["method"], item["decision"]]
        for item in project.get("sizing_strategy", [])
    ]
    st.dataframe(
        pd.DataFrame(strategy_rows, columns=["Sizing Step", "How To Derive It", "Applied Decision"]),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Final Numbers and Why They Matter")
    cols = st.columns(2)
    for idx, item in enumerate(project["sizing"]):
        with cols[idx % 2]:
            st.markdown(
                f"<div class='project-card' style='padding:12px;min-height:128px;margin-bottom:12px;'>"
                f"<b>{item['title']}</b><br><br>{item['body']}</div>",
                unsafe_allow_html=True,
            )


def render_code_walkthrough(project):
    st.markdown("### Code and Walkthrough")
    st.code(project["code"], language=project["code_language"])
    st.markdown("#### Why the code is structured this way")
    for item in project["code_breakdown"]:
        st.markdown(f"- {item}")


def render_project_1_architecture(project):
    with st.container(border=True):
        st.markdown("### Architecture Simulator")
        c1, c2, c3, c4 = st.columns(4)
        source_mode = c1.selectbox("Source Mode", ["Devices only", "Sumo API only", "Hybrid blend"], key="project1_source_mode")
        storage_view = c2.selectbox("Storage View", ["Silver", "Gold", "Both"], key="project1_storage_view")
        consumer = c3.selectbox("Primary Consumer", ["Dashboards", "Analysts"], key="project1_consumer")
        focus = c4.selectbox("Interview Lens", list(project["architecture_focus"].keys()), key="project1_focus")

    source_active = {
        "Devices": source_mode in {"Devices only", "Hybrid blend"},
        "Sumo API": source_mode in {"Sumo API only", "Hybrid blend"},
    }
    silver_active = storage_view in {"Silver", "Both"}
    gold_active = storage_view in {"Gold", "Both"}

    architecture_html = (
        "<div style='display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:8px;align-items:start;'>"
        + "<div>"
        + build_stage_box("Sources", ["Devices", "Sumo API"], active=False, min_height=56)
        + "<div style='margin-top:6px;'>"
        + build_stage_box("Devices", ["400 GB/day"], active=source_active["Devices"], emphasis="focus", min_height=48)
        + "</div><div style='margin-top:6px;'>"
        + build_stage_box("Sumo API", ["200 GB/day"], active=source_active["Sumo API"], emphasis="focus", min_height=48)
        + "</div></div>"
        + "<div>"
        + build_stage_box("Ingestion", ["Kafka", "Sumo Puller"], active=False, min_height=56)
        + "</div>"
        + "<div>"
        + build_stage_box("Orchestration", ["Airflow", "5-minute DAG"], active=False, min_height=56)
        + "</div>"
        + "<div>"
        + build_stage_box("Storage", ["StarRocks"], active=False, min_height=56)
        + "<div style='margin-top:6px;'>"
        + build_stage_box("Silver", ["normalized", "deduped"], active=silver_active, emphasis="focus", min_height=48)
        + "</div><div style='margin-top:6px;'>"
        + build_stage_box("Gold", ["hourly KPIs"], active=gold_active, emphasis="focus", min_height=48)
        + "</div></div>"
        + "<div>"
        + build_stage_box("Consumers", ["Dashboards", "Analysts"], active=False, min_height=56)
        + "<div style='margin-top:6px;'>"
        + build_stage_box("Dashboards", ["fresh KPIs"], active=consumer == "Dashboards", emphasis="focus", min_height=48)
        + "</div><div style='margin-top:6px;'>"
        + build_stage_box("Analysts", ["ad hoc"], active=consumer == "Analysts", emphasis="focus", min_height=48)
        + "</div></div>"
        + "</div>"
    )
    render_panel(architecture_html)

    st.markdown("#### Interview coverage inside this simulator state")
    for line in project["architecture_focus"][focus]:
        st.markdown(f"- {line}")


def render_project_2_architecture(project):
    with st.container(border=True):
        st.markdown("### Architecture Simulator")
        c1, c2, c3, c4 = st.columns(4)
        region = c1.selectbox("Active Region", ["Region A", "Region B", "Region C", "All Regions"], key="project2_region")
        processing_view = c2.selectbox("Processing View", ["Read/Parse", "Window/Dedup", "Enrich/Aggregate"], key="project2_processing")
        consumer = c3.selectbox("Primary Consumer", ["Athena", "ML Training"], key="project2_consumer")
        focus = c4.selectbox("Interview Lens", list(project["architecture_focus"].keys()), key="project2_focus")

    region_active = {
        "Region A": region in {"Region A", "All Regions"},
        "Region B": region in {"Region B", "All Regions"},
        "Region C": region in {"Region C", "All Regions"},
    }
    processing_active = {
        "Read/Parse": processing_view == "Read/Parse",
        "Window/Dedup": processing_view == "Window/Dedup",
        "Enrich/Aggregate": processing_view == "Enrich/Aggregate",
    }

    architecture_html = (
        "<div style='display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:8px;align-items:start;'>"
        + "<div>"
        + build_stage_box("Sources", ["Region A", "Region B", "Region C"], active=False, min_height=56)
        + "<div style='margin-top:6px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;'>"
        + build_stage_box("A", ["US"], active=region_active["Region A"], emphasis="focus", min_height=46)
        + build_stage_box("B", ["EU"], active=region_active["Region B"], emphasis="focus", min_height=46)
        + build_stage_box("C", ["APAC"], active=region_active["Region C"], emphasis="focus", min_height=46)
        + "</div></div>"
        + "<div>"
        + build_stage_box("Ingestion", ["Kafka", "Schema Registry"], active=False, min_height=56)
        + "</div>"
        + "<div>"
        + build_stage_box("Processing", ["Beam on Spark"], active=False, min_height=56)
        + "<div style='margin-top:6px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;'>"
        + build_stage_box("Read", ["parse"], active=processing_active["Read/Parse"], emphasis="focus", min_height=46)
        + build_stage_box("Window", ["dedup"], active=processing_active["Window/Dedup"], emphasis="focus", min_height=46)
        + build_stage_box("Enrich", ["aggregate"], active=processing_active["Enrich/Aggregate"], emphasis="focus", min_height=46)
        + "</div></div>"
        + "<div>"
        + build_stage_box("Storage", ["S3 Parquet", "dt/hour"], active=False, min_height=56)
        + "</div>"
        + "<div>"
        + build_stage_box("Consumers", ["Athena", "ML"], active=False, min_height=56)
        + "<div style='margin-top:6px;'>"
        + build_stage_box("Athena", ["queries"], active=consumer == "Athena", emphasis="focus", min_height=46)
        + "</div><div style='margin-top:6px;'>"
        + build_stage_box("ML", ["training"], active=consumer == "ML Training", emphasis="focus", min_height=46)
        + "</div></div>"
        + "</div>"
    )
    render_panel(architecture_html)

    st.markdown("#### Interview coverage inside this simulator state")
    for line in project["architecture_focus"][focus]:
        st.markdown(f"- {line}")


def render_failure_simulator(project):
    with st.container(border=True):
        st.markdown("### Failure Handling Simulator")
        scenario_name = st.selectbox(
            "Failure Scenario",
            [item["name"] for item in project["failure_scenarios"]],
            key=f"{project['key']}_failure",
        )

    scenario = next(item for item in project["failure_scenarios"] if item["name"] == scenario_name)
    affected_component = scenario["component"]

    component_order = ["Sources", "Ingestion", "Schema Registry", "Orchestration", "Processing", "Storage", "Consumers"]
    diagram_boxes = []
    for component in component_order:
        if project["key"] == "samsung_project_1" and component in {"Schema Registry", "Processing"}:
            continue
        if project["key"] == "samsung_project_2" and component == "Orchestration":
            continue
        if project["key"] == "samsung_project_1":
            details = {
                "Sources": ["Devices + Sumo"],
                "Ingestion": ["Kafka + puller"],
                "Orchestration": ["Airflow"],
                "Storage": ["StarRocks"],
                "Consumers": ["Dashboards + analysts"],
            }[component]
        else:
            details = {
                "Sources": ["3 regions"],
                "Ingestion": ["Kafka"],
                "Schema Registry": ["compatibility"],
                "Processing": ["Beam on Spark"],
                "Storage": ["S3 + Athena"],
                "Consumers": ["Athena + ML"],
            }[component]
        diagram_boxes.append(
            f"<div style='flex:1;min-width:112px'>{build_stage_box(component, details, active=component == affected_component, emphasis='failure' if component == affected_component else 'neutral', min_height=56)}</div>"
        )

    render_panel("<div style='display:flex;gap:10px;flex-wrap:wrap;'>" + "".join(diagram_boxes) + "</div>")

    detail_col1, detail_col2 = st.columns(2)
    with detail_col1:
        st.markdown("#### What breaks")
        st.markdown(f"- {scenario['problem']}")
        st.markdown(f"- {scenario['example']}")
    with detail_col2:
        st.markdown("#### What changes in the design")
        st.markdown(f"- {scenario['fix']}")
        st.markdown("#### Interview angle")
        for item in scenario["interview"]:
            st.markdown(f"- {item}")


def render_project(project):
    st.title(project["title"])
    st.caption(project["subtitle"])

    render_requirements(project)

    if project["key"] == "samsung_project_1":
        render_project_1_architecture(project)
    else:
        render_project_2_architecture(project)

    tradeoff_tab, sizing_tab, story_tab, failure_tab, code_tab = st.tabs(
        ["Trade-Offs", "Sizing", "Storyline", "Failure Simulator", "Code Walkthrough"]
    )

    with tradeoff_tab:
        render_tradeoffs(project)
    with sizing_tab:
        render_sizing(project)
    with story_tab:
        render_storyline(project)
    with failure_tab:
        render_failure_simulator(project)
    with code_tab:
        render_code_walkthrough(project)


def render_projects():
    st.sidebar.title("Projects Workspace")
    companies = list(PROJECTS_CATALOG.keys())

    query_params = st.query_params
    selected_company = query_params.get("project_company", companies[0])
    if selected_company not in PROJECTS_CATALOG:
        selected_company = companies[0]

    company = st.sidebar.selectbox("Company", companies, index=companies.index(selected_company))
    st.query_params["project_company"] = company

    company_projects = PROJECTS_CATALOG[company]

    if not company_projects:
        st.title("Projects")
        st.info(f"No projects loaded yet for {company}. Add project dictionaries to PROJECTS_CATALOG to extend the dashboard dynamically.")
        overview_rows = [[name, len(items)] for name, items in PROJECTS_CATALOG.items()]
        st.dataframe(pd.DataFrame(overview_rows, columns=["Company", "Projects"]), use_container_width=True, hide_index=True)
        return

    project_keys = [project["key"] for project in company_projects]
    selected_project = query_params.get("project_name", project_keys[0])
    if selected_project not in project_keys:
        selected_project = project_keys[0]

    project_index = project_keys.index(selected_project)
    project = st.sidebar.radio(
        "Projects",
        company_projects,
        index=project_index,
        format_func=lambda item: item["title"],
    )
    st.query_params["project_name"] = project["key"]

    render_project(project)
