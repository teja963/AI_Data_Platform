import copy
import json
import re
import sqlite3
from datetime import datetime, timezone


AWS_SERVICES = {
    "S3": {
        "category": "Storage & Lake",
        "purpose": "Durable object storage for raw, curated, and consumption data zones.",
        "task": "Create a versioned data-lake bucket and write a partitioned object.",
        "config": {"bucket": "de-raw-zone", "key": "orders/dt=2026-08-01/orders.json", "versioning": True},
        "interview": "Explain partition design, small-file problems, versioning, lifecycle rules, and encryption.",
        "failure": "AccessDenied when IAM or bucket policy does not allow s3:PutObject.",
    },
    "Glue Data Catalog": {
        "category": "Catalog & Governance",
        "purpose": "Central metadata catalog used by Glue, Athena, EMR, and Lake Formation.",
        "task": "Register an orders table with partition and schema metadata.",
        "config": {"database": "analytics", "table": "orders", "format": "parquet", "partition": "order_date"},
        "interview": "Differentiate a catalog, database, table, crawler, partition, and schema registry.",
        "failure": "Query engines cannot resolve a table when its location or partition metadata is stale.",
    },
    "Glue Crawler": {
        "category": "Catalog & Governance",
        "purpose": "Inspects data locations and creates or updates catalog tables.",
        "task": "Crawl a partitioned S3 prefix and infer an orders schema.",
        "config": {"source": "s3://de-raw-zone/orders/", "database": "analytics", "schedule": "on-demand"},
        "interview": "Explain crawler recrawl policies, schema changes, partitions, and why explicit schemas are safer.",
        "failure": "Crawler succeeds but creates no table when the role cannot list the S3 prefix.",
    },
    "Glue ETL Job": {
        "category": "ETL & Compute",
        "purpose": "Serverless Spark execution for batch ETL and streaming transformations.",
        "task": "Read cataloged JSON, deduplicate orders, and write partitioned Parquet.",
        "config": {"workers": 10, "worker_type": "G.1X", "bookmark": True, "output": "s3://de-curated/orders/"},
        "interview": "Discuss DPUs, worker types, bookmarks, DynamicFrames versus DataFrames, and skew.",
        "failure": "Job retries or fails from executor memory pressure, skew, missing permissions, or invalid bookmarks.",
    },
    "Lake Formation": {
        "category": "Catalog & Governance",
        "purpose": "Fine-grained governance for data-lake databases, tables, columns, and locations.",
        "task": "Grant an analyst SELECT on curated columns while excluding PII.",
        "config": {"database": "analytics", "table": "orders", "principal": "AnalystRole", "columns": ["order_id", "amount"]},
        "interview": "Compare IAM permissions with Lake Formation data permissions.",
        "failure": "Insufficient Lake Formation permission can deny access even when S3 IAM access exists.",
    },
    "Lambda": {
        "category": "Serverless & Events",
        "purpose": "Event-driven compute for lightweight validation, routing, and control-plane automation.",
        "task": "Validate an S3 event and start a Step Functions execution.",
        "config": {"runtime": "python3.12", "memory_mb": 512, "timeout_seconds": 60, "trigger": "S3 ObjectCreated"},
        "interview": "Explain cold starts, concurrency, retries, DLQs, idempotency, and the 15-minute limit.",
        "failure": "Timeouts, throttling, malformed events, or duplicate delivery require idempotent handling.",
    },
    "Step Functions": {
        "category": "Orchestration",
        "purpose": "Coordinates AWS services with retries, branching, parallel states, and execution history.",
        "task": "Orchestrate validation, Glue ETL, Athena quality checks, and Redshift loading.",
        "config": {"type": "STANDARD", "retry_attempts": 3, "backoff_rate": 2.0, "catch": "NotifyFailure"},
        "interview": "Compare Standard and Express workflows, callback patterns, retries, catches, and Map states.",
        "failure": "An uncaught task error stops the execution and leaves downstream states unexecuted.",
    },
    "EventBridge": {
        "category": "Serverless & Events",
        "purpose": "Routes scheduled and event-pattern messages to AWS targets.",
        "task": "Start a pipeline when an ingestion-complete event is published.",
        "config": {"event_source": "company.ingestion", "detail_type": "BatchCompleted", "target": "StepFunctions"},
        "interview": "Compare EventBridge, SNS, SQS, and Kinesis delivery models.",
        "failure": "Events go to a DLQ when target permissions or retry delivery are exhausted.",
    },
    "Athena": {
        "category": "Analytics & Warehouse",
        "purpose": "Serverless SQL over S3 data using Glue Catalog metadata.",
        "task": "Query partitioned Parquet and inspect scanned bytes.",
        "config": {"workgroup": "analytics", "database": "analytics", "format": "parquet", "partition_filter": True},
        "interview": "Explain cost by bytes scanned, partition pruning, columnar formats, CTAS, and workgroups.",
        "failure": "Queries become slow and expensive when reading unpartitioned JSON or many tiny files.",
    },
    "Redshift": {
        "category": "Analytics & Warehouse",
        "purpose": "MPP warehouse for governed SQL analytics and BI workloads.",
        "task": "Load curated orders and choose distribution and sort keys.",
        "config": {"mode": "Serverless", "base_rpu": 32, "distribution": "AUTO", "sort_key": "order_date"},
        "interview": "Explain distribution styles, sort keys, WLM, Spectrum, VACUUM, ANALYZE, and RA3.",
        "failure": "Data redistribution, skew, stale statistics, and queue contention degrade performance.",
    },
    "EMR": {
        "category": "ETL & Compute",
        "purpose": "Managed Spark, Hadoop, Hive, Trino, and Flink on EC2, EKS, or Serverless.",
        "task": "Submit a Spark transformation with managed scaling and Spot task nodes.",
        "config": {"deployment": "EMR Serverless", "engine": "Spark", "executors": 20, "dynamic_allocation": True},
        "interview": "Compare EMR on EC2, EMR on EKS, EMR Serverless, and Glue.",
        "failure": "Jobs fail from Spot loss, bootstrap errors, S3 throttling, skew, or executor sizing.",
    },
    "Kinesis Data Streams": {
        "category": "Streaming",
        "purpose": "Ordered, replayable streaming records partitioned into shards.",
        "task": "Publish order events with customer_id as the partition key.",
        "config": {"mode": "ON_DEMAND", "retention_hours": 24, "partition_key": "customer_id", "consumers": 2},
        "interview": "Explain shards, partition keys, hot shards, enhanced fan-out, retention, and replay.",
        "failure": "A low-cardinality partition key creates a hot shard and write throttling.",
    },
    "Firehose": {
        "category": "Streaming",
        "purpose": "Managed delivery of streaming data to S3, Redshift, OpenSearch, and HTTP endpoints.",
        "task": "Buffer, transform, and deliver Kinesis records to partitioned S3.",
        "config": {"destination": "S3", "buffer_mb": 64, "buffer_seconds": 60, "compression": "GZIP"},
        "interview": "Compare Firehose delivery with Kinesis Data Streams consumers.",
        "failure": "Failed transformations and destination errors are delivered to an S3 error prefix.",
    },
    "MSK": {
        "category": "Streaming",
        "purpose": "Managed Apache Kafka with AWS networking, security, and monitoring integration.",
        "task": "Create a replicated orders topic and configure consumer lag monitoring.",
        "config": {"brokers": 3, "partitions": 12, "replication_factor": 3, "auth": "IAM"},
        "interview": "Explain partitions, consumer groups, ISR, retention, compaction, lag, and MSK Serverless.",
        "failure": "Insufficient partitions, broker imbalance, or slow consumers produce lag and throughput limits.",
    },
    "RDS / Aurora": {
        "category": "Databases",
        "purpose": "Managed relational sources and operational metadata stores.",
        "task": "Configure a PostgreSQL Multi-AZ source for CDC ingestion.",
        "config": {"engine": "Aurora PostgreSQL", "multi_az": True, "backup_days": 7, "logical_replication": True},
        "interview": "Compare RDS and Aurora, read replicas, Multi-AZ, failover, and CDC prerequisites.",
        "failure": "CDC cannot start when logical replication, WAL retention, networking, or privileges are missing.",
    },
    "DynamoDB": {
        "category": "Databases",
        "purpose": "Serverless key-value and document database with predictable low latency.",
        "task": "Model pipeline execution state using partition and sort keys.",
        "config": {"partition_key": "pipeline_id", "sort_key": "execution_ts", "capacity": "ON_DEMAND", "streams": True},
        "interview": "Explain access-pattern-first design, GSIs, hot partitions, Streams, TTL, and consistency.",
        "failure": "Poor key distribution creates hot partitions and throttling.",
    },
    "Neptune": {
        "category": "Databases",
        "purpose": "Managed graph database supporting property graphs and RDF.",
        "task": "Model dataset lineage as Dataset → Job → Dataset relationships.",
        "config": {"model": "Property Graph", "query": "openCypher", "replicas": 2, "use_case": "data lineage"},
        "interview": "Explain when graph traversal is preferable to relational joins.",
        "failure": "Unbounded traversals and missing graph-model constraints create expensive queries.",
    },
    "DMS": {
        "category": "Ingestion & Migration",
        "purpose": "Migrates and continuously replicates databases using full load and CDC.",
        "task": "Replicate PostgreSQL changes to S3 for lake ingestion.",
        "config": {"mode": "Full load + CDC", "source": "PostgreSQL", "target": "S3", "format": "Parquet"},
        "interview": "Explain full load, CDC position, validation, LOB handling, and task recovery.",
        "failure": "Missing source logs or insufficient retention causes unrecoverable CDC gaps.",
    },
    "IAM": {
        "category": "Security & Operations",
        "purpose": "Controls identities, roles, policies, trust relationships, and temporary credentials.",
        "task": "Build a least-privilege Glue execution role.",
        "config": {"principal": "glue.amazonaws.com", "actions": ["s3:GetObject", "s3:PutObject", "glue:GetTable"], "resource_scope": "analytics-only"},
        "interview": "Explain identity policies, resource policies, trust policies, permission boundaries, and SCPs.",
        "failure": "Explicit Deny overrides Allow; incorrect trust prevents role assumption.",
    },
    "KMS": {
        "category": "Security & Operations",
        "purpose": "Manages encryption keys and cryptographic authorization.",
        "task": "Encrypt S3, Glue, Redshift, and log data with a customer-managed key.",
        "config": {"key_type": "SYMMETRIC_DEFAULT", "rotation": True, "administrators": ["PlatformAdmin"], "users": ["PipelineRole"]},
        "interview": "Explain envelope encryption, grants, key policies, rotation, and cross-account use.",
        "failure": "Data access fails when the caller has service permission but lacks kms:Decrypt.",
    },
    "Secrets Manager": {
        "category": "Security & Operations",
        "purpose": "Stores, retrieves, and rotates database/API credentials.",
        "task": "Rotate a Redshift credential without embedding it in a Glue script.",
        "config": {"secret": "analytics/redshift", "rotation_days": 30, "consumer": "GlueRole"},
        "interview": "Compare Secrets Manager, Parameter Store, environment variables, and KMS.",
        "failure": "Rotation can break consumers that cache credentials or lack GetSecretValue.",
    },
    "CloudWatch": {
        "category": "Security & Operations",
        "purpose": "Collects logs, metrics, alarms, dashboards, and event-driven operational signals.",
        "task": "Alarm on Glue failures, Lambda errors, Kinesis lag, and Step Functions failures.",
        "config": {"metric": "PipelineFailures", "threshold": 1, "period_minutes": 5, "target": "SNS"},
        "interview": "Explain metrics versus logs, dimensions, alarms, Logs Insights, and custom metrics.",
        "failure": "Missing dimensions or delayed custom metrics create misleading alarms.",
    },
    "Bedrock Knowledge Bases": {
        "category": "AI & Search",
        "purpose": "Managed retrieval-augmented generation over enterprise documents.",
        "task": "Ingest data-engineering runbooks from S3 and retrieve grounded troubleshooting context.",
        "config": {"source": "S3", "embedding": "Titan Text Embeddings", "vector_store": "OpenSearch Serverless", "chunk_tokens": 500},
        "interview": "Explain chunking, embeddings, vector search, metadata filters, grounding, and evaluation.",
        "failure": "Poor chunking or missing metadata produces irrelevant retrieval and weak grounding.",
    },
    "OpenSearch": {
        "category": "AI & Search",
        "purpose": "Search, log analytics, and vector retrieval.",
        "task": "Index pipeline logs and vectorized runbook chunks.",
        "config": {"deployment": "Serverless", "indexes": ["pipeline-logs", "runbook-vectors"], "replicas": 2},
        "interview": "Explain shards, replicas, mappings, inverted indexes, vector indexes, and refresh cost.",
        "failure": "Mapping explosion, oversized shards, and unbounded high-cardinality fields degrade clusters.",
    },
}


SOURCE_CATALOG = {
    "PostgreSQL / MySQL / Oracle": "Relational source using JDBC snapshots or log-based CDC.",
    "MongoDB / Document DB": "Document source using change streams or connector-based extraction.",
    "REST / GraphQL API": "Request/response ingestion requiring pagination, retries, rate limits, and checkpoints.",
    "Files / S3 / Object Storage": "Batch files requiring schema, partition, format, and small-file controls.",
    "Kafka / MSK": "Partitioned event log with consumer offsets, replay, ordering, and retention.",
    "Kinesis": "Shard-based AWS stream with partition keys, consumers, retention, and replay.",
    "DMS / Debezium CDC": "Database change events preserving inserts, updates, deletes, and source positions.",
}


WAREHOUSE_ENGINES = {
    "Amazon Redshift": "MPP warehouse using distribution, sort keys, WLM, Spectrum, and materialized views.",
    "Google BigQuery": "Serverless warehouse using partitioning, clustering, slots, and bytes-scanned controls.",
    "Snowflake": "Separated storage/compute with virtual warehouses, micro-partitions, caching, and clustering.",
    "StarRocks": "Real-time MPP analytics with FE/CN or FE/BE topology, colocated joins, and materialized views.",
    "Athena / Trino": "Distributed SQL over object storage and catalogs; performance depends on files and pruning.",
}


LAKEHOUSE_FORMATS = {
    "Apache Iceberg": "Snapshot-based open table format with hidden partitioning and partition evolution.",
    "Delta Lake": "Transaction-log table format with MERGE, time travel, schema enforcement, and OPTIMIZE.",
    "Apache Hudi": "Incremental lakehouse format supporting copy-on-write and merge-on-read tables.",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def run_aws_service(service, config, simulate_failure=False):
    spec = AWS_SERVICES[service]
    execution_id = f"{service.lower().replace(' ', '-')}-{datetime.now().strftime('%H%M%S%f')}"
    logs = [
        f"{_now()} START {execution_id}",
        f"{_now()} Validated configuration for {service}.",
    ]
    if simulate_failure:
        logs.extend(
            [
                f"{_now()} ERROR {spec['failure']}",
                f"{_now()} END status=FAILED",
            ]
        )
        return {
            "status": "FAILED",
            "service": service,
            "execution_id": execution_id,
            "logs": logs,
            "artifact": {"configuration": config, "error": spec["failure"]},
        }
    logs.extend(
        [
            f"{_now()} Executed practical task: {spec['task']}",
            f"{_now()} END status=SUCCEEDED",
        ]
    )
    return {
        "status": "SUCCEEDED",
        "service": service,
        "execution_id": execution_id,
        "logs": logs,
        "artifact": {
            "configuration": config,
            "resource_arn": f"arn:aws:simulator:us-east-1:123456789012:{service.lower().replace(' ', '-')}/{execution_id}",
            "result": spec["task"],
        },
    }


def run_aws_pipeline(failure_stage=None):
    stages = [
        "S3 ObjectCreated",
        "Glue Crawler",
        "Glue Data Catalog",
        "Glue ETL Job",
        "Athena query",
        "Redshift load",
        "Lambda notification",
        "Step Functions completion",
        "CloudWatch metrics",
    ]
    rows = []
    blocked = False
    for index, stage in enumerate(stages, start=1):
        if blocked:
            status = "SKIPPED"
        elif stage == failure_stage:
            status = "FAILED"
            blocked = True
        else:
            status = "SUCCEEDED"
        rows.append(
            {
                "Step": index,
                "Stage": stage,
                "Status": status,
                "Duration": f"{index * 3 + 2}s" if status == "SUCCEEDED" else "—",
            }
        )
    return rows


def parse_records(text):
    records = []
    for line_number, line in enumerate((text or "").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"line {line_number}: {error.msg}") from error
        if not isinstance(value, dict):
            raise ValueError(f"line {line_number}: each record must be a JSON object")
        records.append(value)
    return records


def simulate_ingestion(source, mode, text, deduplicate=True):
    records = parse_records(text)
    seen = set()
    output = []
    for index, record in enumerate(records, start=1):
        enriched = dict(record)
        enriched["_source"] = source
        enriched["_ingestion_mode"] = mode
        enriched["_offset"] = index
        key = json.dumps(record, sort_keys=True)
        if deduplicate and key in seen:
            continue
        seen.add(key)
        output.append(enriched)
    return {
        "input_count": len(records),
        "output_count": len(output),
        "duplicates_removed": len(records) - len(output),
        "records": output,
        "checkpoint": output[-1]["_offset"] if output else 0,
    }


def execute_warehouse_query(query):
    cleaned = (query or "").strip()
    if not re.match(r"^(select|with)\b", cleaned, re.IGNORECASE):
        raise ValueError("The warehouse lab is read-only; use SELECT or WITH.")
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(
            """
            CREATE TABLE orders (
                order_id INTEGER,
                customer_id INTEGER,
                region TEXT,
                amount REAL,
                order_date TEXT
            );
            INSERT INTO orders VALUES
                (1, 101, 'US', 120.50, '2026-08-01'),
                (2, 102, 'EU', 80.00, '2026-08-01'),
                (3, 101, 'US', 45.25, '2026-08-02'),
                (4, 103, 'APAC', 220.00, '2026-08-02'),
                (5, 104, 'EU', 140.00, '2026-08-03');
            """
        )
        cursor = connection.execute(cleaned)
        columns = [item[0] for item in cursor.description or []]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        plan_rows = connection.execute(f"EXPLAIN QUERY PLAN {cleaned}").fetchall()
        plan = [" | ".join(str(value) for value in row) for row in plan_rows]
        return {"columns": columns, "rows": rows, "plan": plan}
    except sqlite3.Error as error:
        raise ValueError(str(error)) from error
    finally:
        connection.close()


def new_lakehouse_state():
    rows = [
        {"order_id": 1, "status": "NEW", "amount": 120.5},
        {"order_id": 2, "status": "NEW", "amount": 80.0},
    ]
    return {
        "format": "Apache Iceberg",
        "rows": rows,
        "schema": {"order_id": "long", "status": "string", "amount": "double"},
        "snapshots": [{"id": 1, "operation": "CREATE", "rows": copy.deepcopy(rows)}],
        "files": 2,
    }


def apply_lakehouse_operation(state, operation, payload=None):
    working = copy.deepcopy(state or new_lakehouse_state())
    payload = payload or {}
    if operation == "Append":
        next_id = max((row["order_id"] for row in working["rows"]), default=0) + 1
        working["rows"].append(
            {
                "order_id": next_id,
                "status": payload.get("status", "NEW"),
                "amount": float(payload.get("amount", 100)),
            }
        )
        working["files"] += 1
    elif operation == "MERGE / Upsert":
        order_id = int(payload.get("order_id", 1))
        match = next((row for row in working["rows"] if row["order_id"] == order_id), None)
        if match:
            match.update(
                {
                    "status": payload.get("status", "UPDATED"),
                    "amount": float(payload.get("amount", match["amount"])),
                }
            )
        else:
            working["rows"].append(
                {
                    "order_id": order_id,
                    "status": payload.get("status", "NEW"),
                    "amount": float(payload.get("amount", 100)),
                }
            )
        working["files"] += 2
    elif operation == "Delete":
        order_id = int(payload.get("order_id", 1))
        working["rows"] = [row for row in working["rows"] if row["order_id"] != order_id]
        working["files"] += 1
    elif operation == "Schema Evolution":
        column = payload.get("column", "source")
        working["schema"][column] = payload.get("type", "string")
        for row in working["rows"]:
            row.setdefault(column, None)
    elif operation == "Compact Files":
        working["files"] = max(1, min(2, len(working["rows"])))
    elif operation == "Rollback":
        snapshot_id = int(payload.get("snapshot_id", 1))
        snapshot = next(
            (item for item in working["snapshots"] if item["id"] == snapshot_id),
            None,
        )
        if not snapshot:
            raise ValueError(f"snapshot {snapshot_id} does not exist")
        working["rows"] = copy.deepcopy(snapshot["rows"])
    else:
        raise ValueError(f"unsupported operation: {operation}")
    snapshot_id = max(item["id"] for item in working["snapshots"]) + 1
    working["snapshots"].append(
        {
            "id": snapshot_id,
            "operation": operation,
            "rows": copy.deepcopy(working["rows"]),
        }
    )
    return working


def simulate_dag(tasks, dependency_text, fail_task=None, retries=1):
    task_names = [item.strip() for item in tasks.split(",") if item.strip()]
    if not task_names:
        raise ValueError("provide at least one task")
    dependencies = []
    for item in dependency_text.split(","):
        item = item.strip()
        if not item:
            continue
        if ">" not in item:
            raise ValueError(f"dependency must use upstream>downstream: {item}")
        upstream, downstream = (part.strip() for part in item.split(">", 1))
        if upstream not in task_names or downstream not in task_names:
            raise ValueError(f"dependency references an unknown task: {item}")
        dependencies.append((upstream, downstream))
    pending = set(task_names)
    completed = set()
    rows = []
    while pending:
        runnable = sorted(
            task
            for task in pending
            if all(upstream in completed for upstream, downstream in dependencies if downstream == task)
        )
        if not runnable:
            raise ValueError("DAG contains a cycle or unresolved dependency")
        for task in runnable:
            attempts = retries + 1 if task == fail_task else 1
            status = "FAILED" if task == fail_task else "SUCCESS"
            rows.append(
                {
                    "Task": task,
                    "Status": status,
                    "Attempts": attempts,
                    "Log": (
                        f"{task} failed after {attempts} attempts"
                        if status == "FAILED"
                        else f"{task} completed"
                    ),
                }
            )
            pending.remove(task)
            if status == "SUCCESS":
                completed.add(task)
        if any(row["Status"] == "FAILED" for row in rows):
            for task in sorted(pending):
                rows.append(
                    {
                        "Task": task,
                        "Status": "UPSTREAM_FAILED",
                        "Attempts": 0,
                        "Log": "blocked by an upstream failure",
                    }
                )
            break
    return rows
