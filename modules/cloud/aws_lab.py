import json

import pandas as pd
import streamlit as st

from core.aws_simulator import (
    AWS_CLI_LABS,
    execute_aws_cli,
    new_aws_cli_state,
    normalize_aws_cli_state,
    service_mastery,
)
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
    st.session_state["aws_cli_state"] = normalize_aws_cli_state(
        saved.get("cli_state", new_aws_cli_state())
    )
    st.session_state["aws_cli_transcript"] = saved.get("cli_transcript", [])
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
            "cli_state": st.session_state.get("aws_cli_state", new_aws_cli_state()),
            "cli_transcript": st.session_state.get("aws_cli_transcript", [])[-100:],
        },
    )


def _run_cli_command(command):
    state, output = execute_aws_cli(
        st.session_state.get("aws_cli_state", new_aws_cli_state()),
        command,
    )
    st.session_state["aws_cli_state"] = state
    st.session_state.setdefault("aws_cli_transcript", []).append(
        f"aws-sim:~$ {command}\n{output}"
    )
    _save_state()


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
    learn_tab, cli_tab, run_tab, pipeline_tab, interview_tab = st.tabs(
        [
            "Master the Service",
            "Guided AWS Shell",
            "Configuration Lab",
            "End-to-End Pipeline",
            "Interview & Failures",
        ]
    )

    with learn_tab:
        st.subheader(service)
        st.write(spec["purpose"])
        mastery_steps = [
            {
                "Stage": "1. Design",
                "What you must decide": f"Why {service}, its boundaries, security, scaling, and cost model.",
            },
            {
                "Stage": "2. Provision",
                "What you must decide": f"Create the {service} resource through AWS CLI with explicit configuration.",
            },
            {
                "Stage": "3. Execute",
                "What you must decide": spec["task"],
            },
            {
                "Stage": "4. Observe",
                "What you must decide": "Inspect status, logs, metrics, output artifacts, and downstream effects.",
            },
            {
                "Stage": "5. Break and recover",
                "What you must decide": spec["failure"],
            },
        ]
        st.dataframe(pd.DataFrame(mastery_steps), width="stretch", hide_index=True)
        st.markdown("**Production implementation checklist**")
        st.write(
            "Least-privilege IAM · KMS encryption · private networking · idempotency · "
            "retry/DLQ strategy · CloudWatch logs/metrics · cost limits · tested recovery runbook"
        )

    with cli_tab:
        cli_state = st.session_state.get("aws_cli_state", new_aws_cli_state())
        mastery = service_mastery(service, cli_state)
        progress_columns = st.columns(4)
        progress_columns[0].metric("Guided commands", mastery["total"])
        progress_columns[1].metric("Completed", mastery["completed"])
        progress_columns[2].metric("Mastery", f"{mastery['percent']}%")
        progress_columns[3].metric(
            "Simulated resources",
            len(cli_state["resources"].get(service, [])),
        )
        st.progress(mastery["percent"] / 100)

        commands = AWS_CLI_LABS[service]
        selected_command = st.selectbox(
            "Guided command",
            commands,
            key=f"aws_guided_command::{service}",
        )
        action_columns = st.columns([1, 1, 3])
        if action_columns[0].button(
            "Run selected",
            type="primary",
            key=f"aws_run_guided::{service}",
        ):
            _run_cli_command(selected_command)
            st.rerun()
        if action_columns[1].button(
            "Run failure",
            key=f"aws_run_failure::{service}",
            help="Runs the selected command with a simulated IAM AccessDenied response.",
        ):
            _run_cli_command(f"{selected_command} --simulate-access-denied")
            st.rerun()

        transcript = "\n\n".join(
            st.session_state.get("aws_cli_transcript", [])[-25:]
        )
        st.html(
            """
            <style>
              div[class*="st-key-aws_cli_terminal"] {
                background:#05080c;
                border:1px solid #263445;
                border-radius:8px;
                padding:12px;
              }
              div[class*="st-key-aws_cli_terminal"] pre {
                max-height:440px;
                overflow:auto;
              }
              div[class*="st-key-aws_cli_terminal"] input {
                color:#fff !important;
                caret-color:#65ff8d !important;
                font-family:SFMono-Regular,Menlo,Monaco,Consolas,monospace !important;
              }
              div[class*="st-key-aws_cli_terminal"] label p {
                color:#6fe58d !important;
                font-family:SFMono-Regular,Menlo,Monaco,Consolas,monospace !important;
              }
            </style>
            """
        )
        with st.container(key="aws_cli_terminal", border=False):
            st.code(transcript or "aws-sim:~$ ", language="shell", wrap_lines=True)
            with st.form(f"aws_shell_form::{service}", clear_on_submit=True):
                command = st.text_input(
                    "aws-sim:~$",
                    placeholder=commands[0],
                )
                execute = st.form_submit_button("Execute")
        if execute and command.strip():
            _run_cli_command(command.strip())
            st.rerun()
        resources = st.session_state.get("aws_cli_state", new_aws_cli_state())[
            "resources"
        ].get(service, [])
        if resources:
            st.markdown("**Live simulated resources**")
            st.dataframe(pd.DataFrame(resources), width="stretch", hide_index=True)
        if mastery["remaining"]:
            st.info("Commands still to master: " + ", ".join(mastery["remaining"]))
        else:
            st.success(f"All guided {service} shell actions completed.")

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
        st.markdown("**Hands-on validation**")
        st.write(
            "You should be able to provision the resource, execute a workload, inspect its "
            "state, trigger AccessDenied, explain the correction, and connect it to the "
            "end-to-end pipeline without reading the command list."
        )
        with st.expander("All-service mastery tracker", expanded=False):
            cli_state = st.session_state.get("aws_cli_state", new_aws_cli_state())
            tracker = []
            for service_name in AWS_CLI_LABS:
                progress = service_mastery(service_name, cli_state)
                tracker.append(
                    {
                        "Service": service_name,
                        "Completed": f"{progress['completed']} / {progress['total']}",
                        "Mastery": f"{progress['percent']}%",
                    }
                )
            st.dataframe(pd.DataFrame(tracker), width="stretch", hide_index=True)
