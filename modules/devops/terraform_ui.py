import pandas as pd
import streamlit as st

from core.practice_state import load_practice_state, save_practice_state
from core.terraform_simulator import (
    execute_terraform_command,
    new_terraform_state,
    normalize_terraform_state,
    parse_terraform_resources,
)


TERRAFORM_TEMPLATES = {
    "AWS data lake": """terraform {
  required_providers { aws = { source = "hashicorp/aws" } }
}

provider "aws" { region = "us-east-1" }

resource "aws_s3_bucket" "raw" {
  bucket = "data-platform-raw"
}

resource "aws_glue_catalog_database" "lake" {
  name = "data_lake"
}

resource "aws_iam_role" "glue" {
  name = "glue-etl-role"
}""",
    "Kubernetes namespace": """terraform {
  required_providers { kubernetes = { source = "hashicorp/kubernetes" } }
}

resource "kubernetes_namespace" "data" {
  metadata { name = "data-platform" }
}

resource "kubernetes_deployment" "api" {
  metadata { name = "data-api" }
}""",
    "Azure storage": """provider "azurerm" { features {} }

resource "azurerm_resource_group" "data" {
  name = "rg-data-platform"
  location = "East US"
}

resource "azurerm_storage_account" "lake" {
  name = "datalakeplatform"
  resource_group_name = "rg-data-platform"
  location = "East US"
  account_tier = "Standard"
  account_replication_type = "LRS"
}""",
}


def _render_terraform_styles():
    st.markdown(
        """
        <style>
        .tf-flow{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:.35rem;align-items:stretch;margin:.7rem 0}
        .tf-node{background:var(--secondary-background-color);color:var(--text-color)!important;
            border:1px solid color-mix(in srgb,var(--text-color) 30%,transparent);border-radius:.5rem;
            padding:.7rem .5rem;min-height:5rem;overflow-wrap:anywhere}
        .tf-node strong,.tf-node small{display:block;color:var(--text-color)!important}
        .tf-node strong{font-size:.78rem;margin-bottom:.25rem}.tf-node small{font-size:.7rem;opacity:.82}
        .tf-arrow{display:flex;align-items:center;justify-content:center;color:#8b5cf6;font-size:1.2rem}
        @media(max-width:900px){.tf-flow{grid-template-columns:1fr}.tf-arrow{transform:rotate(90deg);min-height:1.5rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_terraform_flow(state, config):
    desired = parse_terraform_resources(config)
    plan = state.get("last_plan") or []
    create_count = sum(row["action"] == "create" for row in plan)
    destroy_count = sum(row["action"] == "destroy" for row in plan)
    nodes = [
        ("main.tf", f"{len(desired)} desired resources"),
        ("terraform plan", f"+{create_count} create / -{destroy_count} destroy"),
        ("Provider API", "Virtual cloud validation and resource graph"),
        ("terraform.tfstate", f"{len(state['resources'])} tracked resources · {state['workspace']}"),
    ]
    parts = []
    for index, (title, detail) in enumerate(nodes):
        parts.append(f"<div class='tf-node'><strong>{title}</strong><small>{detail}</small></div>")
        if index < len(nodes) - 1:
            parts.append("<div class='tf-arrow'>→</div>")
    st.markdown(f"<div class='tf-flow'>{''.join(parts)}</div>", unsafe_allow_html=True)


def render_terraform_lab():
    username = st.session_state.get("user")
    marker = f"terraform_loaded::{username}"
    state_key = f"terraform_state::{username}"
    if not st.session_state.get(marker):
        saved = load_practice_state(username, "terraform_lab") or {}
        st.session_state[state_key] = normalize_terraform_state(saved.get("state"))
        st.session_state.setdefault("terraform_config", TERRAFORM_TEMPLATES["AWS data lake"])
        st.session_state[marker] = True

    _render_terraform_styles()
    st.subheader("Terraform Virtual Infrastructure Lab")
    st.caption(
        "Practice Terraform lifecycle, state, workspaces and imports without creating billable cloud resources."
    )
    state = st.session_state.get(state_key, new_terraform_state())

    template_col, load_col = st.columns([4, 1], vertical_alignment="bottom")
    template = template_col.selectbox("Configuration template", list(TERRAFORM_TEMPLATES))
    if load_col.button("Load", key="terraform_load_template"):
        st.session_state["terraform_config"] = TERRAFORM_TEMPLATES[template]
        st.rerun()

    config = st.text_area(
        "main.tf",
        key="terraform_config",
        height=320,
        help="All resources are simulated locally; no provider credentials are used.",
    )
    _render_terraform_flow(state, config)

    st.markdown("#### Terraform terminal")
    transcript = state.get("transcript", [])
    if transcript:
        terminal_text = "\n\n".join(
            f"terraform:{state['workspace']}$ {item['command']}\n{item['output']}"
            for item in transcript[-12:]
        )
        st.code(terminal_text, language="text")
    with st.form("terraform_terminal_form", clear_on_submit=True):
        command = st.text_input(
            "Command",
            placeholder="terraform init",
            label_visibility="collapsed",
        )
        execute = st.form_submit_button("Run")
    if execute and command.strip():
        if command.strip() == "clear":
            state["transcript"] = []
        else:
            state, _ = execute_terraform_command(state, command, config)
        st.session_state[state_key] = state
        save_practice_state(username, "terraform_lab", {"state": state})
        st.rerun()

    detail = st.columns(2)
    with detail[0]:
        st.markdown("#### State resources")
        resources = list(state["resources"].values())
        if resources:
            st.dataframe(pd.DataFrame(resources), width="stretch", hide_index=True)
        else:
            st.info("State is empty. Run init → plan → apply.")
    with detail[1]:
        st.markdown("#### Last execution plan")
        if state["last_plan"]:
            st.dataframe(pd.DataFrame(state["last_plan"]), width="stretch", hide_index=True)
        else:
            st.info("Run terraform plan to inspect create, no-op and destroy actions.")

    st.caption(
        "Supported: init, fmt, validate, plan, apply, destroy, show, output, providers, "
        "state list/show/rm, workspace list/new/select, import and clear."
    )
