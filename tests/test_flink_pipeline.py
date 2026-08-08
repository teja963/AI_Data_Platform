from modules.spark.flink_pipeline import (
    calculate_flink_execution,
    drawio_flink_cluster_html,
)


def _snapshot(
    transformation="Stateless Map / Filter",
    exchange="Forward",
    failure="Normal",
):
    return calculate_flink_execution(
        input_rate=30_000,
        parallelism=8,
        transformation=transformation,
        exchange=exchange,
        checkpoint_seconds=30,
        failure=failure,
    )


def test_forward_stateless_flow_avoids_managed_keyed_state():
    snapshot = _snapshot()

    assert snapshot["stateful"] is False
    assert snapshot["backpressure"] == 0
    assert "one-to-one" in snapshot["network_pattern"].lower()


def test_keyby_aggregation_creates_state_and_network_exchange():
    snapshot = _snapshot("Keyed Aggregation", "KeyBy")

    assert snapshot["stateful"] is True
    assert snapshot["state_size_mib"] > 0
    assert "hash partition" in snapshot["network_pattern"].lower()


def test_slow_sink_propagates_backpressure():
    snapshot = _snapshot(failure="Slow sink / backpressure")

    assert snapshot["backpressure"] > 0
    assert snapshot["processed_rate"] < 30_000


def test_checkpoint_timeout_preserves_running_job_for_recovery():
    snapshot = _snapshot(failure="Checkpoint timeout")

    assert snapshot["checkpoint_status"] == "FAILED"
    assert snapshot["job_status"] == "RUNNING"


def test_taskmanager_failure_reduces_capacity_and_recovers():
    snapshot = _snapshot(failure="TaskManager failure")

    assert snapshot["job_status"] == "RECOVERING"
    assert snapshot["effective_capacity"] < snapshot["capacity"]


def test_matrix_diagram_preserves_control_and_taskmanager_positions():
    html = drawio_flink_cluster_html("Group by key", "Backpressure", 3)

    for label in (
        "Flink Operator",
        "JobManager",
        "Checkpoint Coordinator",
        "TaskManager",
        "Source Records",
        "KeyBy + State",
        "Managed State",
        "Network Buffers",
        "JVM Heap",
        "Sink",
    ):
        assert label in html
    assert "grid-template-columns:30% 70%" in html
    assert "flink-drawio-backpressure" in html
    assert "flink-processing-keyed" in html
    assert "flink-record-arrow" in html
    for bright_color in ("#d97706", "#8b5cf6", "#2563eb", "#16a34a", "#dc2626"):
        assert bright_color not in html
    assert "▣ durable checkpoint storage" in html


def test_parallelism_replicates_operator_subtasks_and_arrow_tracks():
    html = drawio_flink_cluster_html("Simple transform", "Normal flow", 4)

    for prefix in ("S", "T", "K"):
        for index in range(1, 5):
            assert f">{prefix}{index}<" in html
    assert html.count('class="flink-record-arrow"') == 2
    assert html.count("<span style=\"animation-delay:") == 8


def test_runtime_cases_explain_cause_and_solution():
    runtime_cases = (
        "Backpressure",
        "Data skew",
        "Slot exhaustion",
        "Network congestion",
        "JVM heap pressure",
        "State growth",
        "Late events",
        "Task failure",
        "Checkpoint failure",
    )

    for runtime_case in runtime_cases:
        html = drawio_flink_cluster_html("Time window", runtime_case, 2)
        assert "Why it happens" in html
        assert "Recommended solution" in html

