from modules.spark.ui import (
    _cluster_architecture_html,
    _driver_architecture_html,
    _workers_architecture_html,
)


def _state(**overrides):
    state = {
        "transform": "Narrow",
        "partition": "None",
        "join": "Broadcast",
        "debug": "Normal",
        "executors": 2,
    }
    state.update(overrides)
    return state


def test_spark_architecture_keeps_control_plane_components_distinct():
    html = _driver_architecture_html(_state()) + _cluster_architecture_html()

    for component in (
        "SparkSession",
        "SparkContext",
        "Catalyst Optimizer",
        "DAG Scheduler",
        "YARN",
        "Kubernetes",
        "Standalone",
    ):
        assert component in html
    assert html.count("class='spark-cluster-option'") == 3


def test_worker_architecture_demarcates_executor_resources_and_metrics():
    html = _workers_architecture_html(
        _state(
            transform="Wide",
            partition="Repartition",
            join="Shuffle",
            debug="Spill",
            executors=4,
        )
    )

    assert html.count('class="spark-executor"') == 4
    for label in (
        "Core 1",
        "Core 2",
        "Execution",
        "Storage",
        "Disk",
        "Runtime",
        "Shuffle",
        "Status",
        "Disk spill active",
        "Shuffle exchange active",
    ):
        assert label in html

