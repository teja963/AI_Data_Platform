import pytest

from core.practical_learning import (
    AWS_SERVICES,
    apply_lakehouse_operation,
    execute_warehouse_query,
    new_lakehouse_state,
    run_aws_pipeline,
    run_aws_service,
    simulate_dag,
    simulate_ingestion,
)


def test_aws_catalog_covers_requested_data_engineering_services():
    required = {
        "S3",
        "Glue Data Catalog",
        "Glue Crawler",
        "Glue ETL Job",
        "Lake Formation",
        "Lambda",
        "Step Functions",
        "EventBridge",
        "Athena",
        "Redshift",
        "EMR",
        "Kinesis Data Streams",
        "Firehose",
        "MSK",
        "RDS / Aurora",
        "DynamoDB",
        "Neptune",
        "DMS",
        "IAM",
        "KMS",
        "Secrets Manager",
        "CloudWatch",
        "Bedrock Knowledge Bases",
        "OpenSearch",
    }
    assert required <= set(AWS_SERVICES)


def test_aws_execution_and_pipeline_failure_are_deterministic():
    result = run_aws_service("S3", {"bucket": "test"})
    assert result["status"] == "SUCCEEDED"
    rows = run_aws_pipeline("Glue ETL Job")
    assert next(row for row in rows if row["Stage"] == "Glue ETL Job")["Status"] == "FAILED"
    assert next(row for row in rows if row["Stage"] == "Redshift load")["Status"] == "SKIPPED"


def test_ingestion_deduplicates_and_checkpoints_json_lines():
    result = simulate_ingestion(
        "Kafka / MSK",
        "Streaming",
        '{"id": 1}\n{"id": 1}\n{"id": 2}',
        deduplicate=True,
    )
    assert result["input_count"] == 3
    assert result["output_count"] == 2
    assert result["duplicates_removed"] == 1
    assert result["checkpoint"] == 3


def test_warehouse_lab_is_read_only_and_executes_selects():
    result = execute_warehouse_query("SELECT region, SUM(amount) revenue FROM orders GROUP BY region")
    assert {row["region"] for row in result["rows"]} == {"US", "EU", "APAC"}
    assert result["plan"]
    with pytest.raises(ValueError, match="read-only"):
        execute_warehouse_query("DELETE FROM orders")


def test_lakehouse_tracks_snapshots_and_rolls_back():
    state = new_lakehouse_state()
    state = apply_lakehouse_operation(state, "Append", {"status": "NEW", "amount": 99})
    assert len(state["rows"]) == 3
    state = apply_lakehouse_operation(state, "Rollback", {"snapshot_id": 1})
    assert len(state["rows"]) == 2
    assert state["snapshots"][-1]["operation"] == "Rollback"


def test_dag_simulator_propagates_upstream_failure_and_rejects_cycle():
    rows = simulate_dag(
        "extract,transform,load",
        "extract>transform,transform>load",
        fail_task="transform",
        retries=2,
    )
    assert next(row for row in rows if row["Task"] == "transform")["Attempts"] == 3
    assert next(row for row in rows if row["Task"] == "load")["Status"] == "UPSTREAM_FAILED"
    with pytest.raises(ValueError, match="cycle"):
        simulate_dag("a,b", "a>b,b>a")
