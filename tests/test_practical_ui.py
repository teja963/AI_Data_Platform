import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize(
    ("import_path", "function_name", "expected_title"),
    [
        ("modules.cloud.aws_lab", "render_aws_practical_lab", "AWS Data Engineering Practice Lab"),
        ("modules.data_sources.ui", "render_data_sources", "Data Sources & Ingestion"),
        ("modules.warehouses.ui", "render_warehouses", "Data Warehouses & Query Engines"),
        ("modules.lakehouse.ui", "render_lakehouse", "Lakehouse & Table Formats"),
        ("modules.orchestration.ui", "render_orchestration", "Orchestration"),
        ("modules.spark.ui", "render_spark", "Spark / Flink"),
    ],
)
def test_practical_sections_render_without_runtime_errors(
    import_path,
    function_name,
    expected_title,
):
    app = AppTest.from_string(
        f"""
import streamlit as st
st.session_state["user"] = None
from {import_path} import {function_name}
{function_name}()
"""
    )
    app.run(timeout=10)
    assert not app.exception
    rendered_titles = [item.value for item in [*app.title, *app.header]]
    assert expected_title in rendered_titles
