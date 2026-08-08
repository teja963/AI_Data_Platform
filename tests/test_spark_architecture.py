import inspect

from modules.spark.ui import render_architecture_simulator, render_core


def _state():
    return {
        "transform": "Wide",
        "partition": "Repartition",
        "join": "Shuffle",
        "debug": "Normal",
        "executors": 2,
    }


def test_spark_architecture_preserves_approved_horizontal_proportions():
    source = inspect.getsource(render_architecture_simulator)

    assert "st.columns([5, 3, 12])" in source


def test_executor_cores_use_distinct_theme_aware_boxes():
    core_html = render_core(1, _state(), 1)

    assert "spark-legacy-box" in core_html
    assert "Core 1" in core_html

