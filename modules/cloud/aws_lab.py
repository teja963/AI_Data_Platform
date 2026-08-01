import json

import pandas as pd
import streamlit as st

from core.practical_learning import AWS_SERVICES, run_aws_pipeline, run_aws_service
from core.practice_state import load_practice_state, save_practice_state


def _service_label(service):
    return f"{AWS_SERVICES[service]['category']} · {service}"


def _load_saved_state():
    username = st.session_state.get("user")
    marker = f"aws_practice_loaded::{username}"
    if st.session_state.get(marker):
        return
    saved = load_practice_state(username, "aws") or {}
    if saved.get("pipeline_rows"):
        st.session_state["aws_pipeline_rows"] = saved["pipeline_rows"]
    for service, result in saved.get("service_results", {}).items():
        if service in AWS_SERVICES:
            st.session_state[f"aws_result::{service}"] = result
    st.session_state[marker] = True


def _save_state():
    service_results = {
        service: st.session_state[f"aws_result::{service}"]
        for service in AWS_SERVICES
        if f"aws_result::{service}" in st.session_state
    }
    save_practice_state(
        st.session_state.get("user"),
        "aws",
        {
            "service_results": service_results,
            "pipeline_rows": st.session_state.get("aws_pipeline_rows", []),
        },
    )


def render_aws_practical_lab():
    _load_saved_state()
    st.header("AWS Data Engineering Practice Lab")
    service = st.selectbox(
        "AWS service",
        list(AWS_SERVICES),
        format_func=_service_label,
        key="aws_practical_service",
    )
    spec = AWS_SERVICES[service]
    learn_tab, run_tab, pipeline_tab, interview_tab = st.tabs(
        ["Learn", "Configure & Run", "End-to-End Pipeline", "Interview & Failures"]
    )

    with learn_tab:
        st.subheader(service)
        st.write(spec["purpose"])
        st.markdown("**Practical objective**")
        st.write(spec["task"])
        st.markdown("**Where it fits**")
        st.info(
            f"{spec['category']} service. Practice its configuration, execution logs, "
            "failure behavior, and integration with the wider AWS data platform."
        )

    with run_tab:
        config_key = f"aws_config::{service}"
        if config_key not in st.session_state:
            st.session_state[config_key] = json.dumps(spec["config"], indent=2)
        with st.form(f"aws_service_run::{service}"):
            config_text = st.text_area(
                "Configuration",
                value=st.session_state[config_key],
                height=260,
            )
            simulate_failure = st.checkbox("Simulate the common failure")
            run_clicked = st.form_submit_button("Run Service Simulation", type="primary")
        if run_clicked:
            try:
                config = json.loads(config_text)
                if not isinstance(config, dict):
                    raise ValueError("configuration must be a JSON object")
                st.session_state[config_key] = json.dumps(config, indent=2)
                st.session_state[f"aws_result::{service}"] = run_aws_service(
                    service,
                    config,
                    simulate_failure,
                )
                _save_state()
            except (json.JSONDecodeError, ValueError) as error:
                st.error(str(error))
        result = st.session_state.get(f"aws_result::{service}")
        if result:
            if result["status"] == "SUCCEEDED":
                st.success(f"{service} execution succeeded.")
            else:
                st.error(f"{service} execution failed as requested.")
            st.code("\n".join(result["logs"]), language="text")
            st.json(result["artifact"], expanded=False)

    with pipeline_tab:
        stages = [
            "No failure",
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
        failure = st.selectbox("Failure injection", stages)
        if st.button("Execute S3 → Glue → Athena → Redshift Pipeline", type="primary"):
            st.session_state["aws_pipeline_rows"] = run_aws_pipeline(
                None if failure == "No failure" else failure
            )
            _save_state()
        rows = st.session_state.get("aws_pipeline_rows", run_aws_pipeline())
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        statuses = {row["Status"] for row in rows}
        if "FAILED" in statuses:
            st.warning(
                "The failed stage stops dependent work. Inspect its logs, correct permissions "
                "or configuration, and restart from the failed checkpoint."
            )
        else:
            st.success("The complete simulated AWS data pipeline succeeded.")

    with interview_tab:
        st.markdown("**Interview focus**")
        st.write(spec["interview"])
        st.markdown("**Failure to diagnose**")
        st.warning(spec["failure"])
        st.markdown("**Answer structure**")
        st.code(
            "Requirement → service choice → configuration → security → scaling → "
            "observability → failure recovery → cost trade-off",
            language="text",
        )
