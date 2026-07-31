import html
import json

import pandas as pd
import streamlit as st

from core.kubernetes_lab import (
    delete_kubernetes_lab,
    load_kubernetes_lab,
    save_kubernetes_lab,
)
from core.kubernetes_simulator import (
    CLUSTER_PRESETS,
    PROVIDER_REGIONS,
    add_worker_node,
    create_cluster,
    create_deployment,
    create_namespace,
    create_service,
    delete_pod,
    deployment_rows,
    execute_command,
    export_state,
    node_rows,
    pod_rows,
    restart_pod,
    service_rows,
    set_node_status,
)


MANIFEST_EXAMPLE = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: kafka-consumer
  namespace: default
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: consumer
          image: example/kafka-consumer:1.0
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
---
apiVersion: v1
kind: Service
metadata:
  name: kafka-consumer
spec:
  selector:
    app: kafka-consumer
  ports:
    - port: 8080
      targetPort: 8080
"""

QUICK_COMMANDS = [
    "kubectl get nodes",
    "kubectl get pods -A",
    "kubectl get deployments -A",
    "kubectl get services -A",
    "kubectl get events",
    "kubectl top nodes",
    "kubectl cluster-info",
    "helm list",
]


def _state_key(username):
    return f"kubernetes_simulator_state::{username}"


def _loaded_key(username):
    return f"kubernetes_simulator_loaded::{username}"


def _load_state(username):
    key = _state_key(username)
    if not st.session_state.get(_loaded_key(username)):
        st.session_state[key] = load_kubernetes_lab(username)
        st.session_state[_loaded_key(username)] = True
    return st.session_state.get(key)


def _store_state(username, state):
    st.session_state[_state_key(username)] = state
    save_kubernetes_lab(username, state)


def _safe_action(username, state, action, success_message):
    try:
        action()
        _store_state(username, state)
        st.success(success_message)
        return True
    except (ValueError, TypeError) as exc:
        st.error(str(exc))
        return False


def _render_cluster_creator(username):
    st.subheader("Create a Virtual Kubernetes Cluster")
    st.caption(
        "This creates an in-memory learning model only. It does not provision cloud resources, "
        "start containers, or execute commands on the server."
    )
    profile = st.segmented_control(
        "Cluster size",
        list(CLUSTER_PRESETS),
        default="Medium",
        key="k8s_create_profile",
    )
    profile = profile or "Medium"
    defaults = CLUSTER_PRESETS[profile]
    with st.form("virtual_cluster_create_form"):
        identity_cols = st.columns(3)
        name = identity_cols[0].text_input("Cluster name", value="data-platform-lab")
        provider = identity_cols[1].selectbox("Provider model", list(PROVIDER_REGIONS))
        region = identity_cols[2].text_input(
            "Region",
            value=PROVIDER_REGIONS[list(PROVIDER_REGIONS)[0]],
            help="A simulated provider region used for learning and display.",
        )
        capacity_cols = st.columns(4)
        workers = capacity_cols[0].number_input(
            "Worker nodes", min_value=1, max_value=100, value=defaults["workers"]
        )
        cpu = capacity_cols[1].number_input(
            "CPU per worker", min_value=1, max_value=128, value=defaults["cpu"]
        )
        memory = capacity_cols[2].number_input(
            "Memory per worker (Mi)", min_value=512, max_value=1048576, value=defaults["memory"], step=512
        )
        storage = capacity_cols[3].number_input(
            "Storage per worker (Gi)", min_value=10, max_value=65536, value=defaults["storage"], step=10
        )
        create = st.form_submit_button("Create Virtual Cluster", type="primary")
    if create:
        state = create_cluster(
            name,
            provider,
            region,
            workers,
            cpu,
            memory,
            storage,
        )
        _store_state(username, state)
        st.rerun()


def _topology_html(state):
    pods_by_node = {}
    for pod in state["pods"].values():
        pods_by_node.setdefault(pod.get("node") or "Pending", []).append(pod)
    cards = []
    for node in state["nodes"]:
        status_class = "ready" if node["status"] == "Ready" else "failed"
        pods = pods_by_node.get(node["name"], [])
        pod_chips = "".join(
            (
                f'<span class="sim-pod {html.escape(pod["status"].lower())}" '
                f'title="{html.escape(pod["image"])}">{html.escape(pod["name"])}</span>'
            )
            for pod in pods
        ) or '<span class="sim-empty">No scheduled pods</span>'
        cards.append(
            f"""
            <div class="sim-node {status_class}">
              <div class="sim-node-title">{html.escape(node["name"])}</div>
              <div class="sim-node-meta">{html.escape(node["role"])} · {html.escape(node["status"])}</div>
              <div class="sim-pods">{pod_chips}</div>
            </div>
            """
        )
    pending = pods_by_node.get("Pending", [])
    if pending:
        cards.append(
            '<div class="sim-node pending"><div class="sim-node-title">Pending Queue</div>'
            '<div class="sim-node-meta">Waiting for capacity</div><div class="sim-pods">'
            + "".join(
                f'<span class="sim-pod pending">{html.escape(pod["name"])}</span>'
                for pod in pending
            )
            + "</div></div>"
        )
    cluster = state["cluster"]
    return f"""
    <style>
      .sim-cluster {{ border:1px solid rgba(128,128,128,.45); border-radius:10px; padding:12px; }}
      .sim-cluster-head {{ font-weight:700; margin-bottom:10px; }}
      .sim-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:9px; }}
      .sim-node {{ border:1px solid #5b8def; border-left:4px solid #2f6fed; border-radius:8px; padding:9px; min-height:94px; }}
      .sim-node.failed {{ border-color:#dc3545; border-left-color:#dc3545; }}
      .sim-node.pending {{ border-color:#e6a700; border-left-color:#e6a700; }}
      .sim-node-title {{ font-weight:650; overflow-wrap:anywhere; }}
      .sim-node-meta {{ opacity:.72; font-size:.82rem; margin:2px 0 8px; }}
      .sim-pods {{ display:flex; flex-wrap:wrap; gap:5px; }}
      .sim-pod {{ border-radius:12px; background:rgba(47,111,237,.14); padding:3px 7px; font-size:.75rem; overflow-wrap:anywhere; }}
      .sim-pod.pending {{ background:rgba(230,167,0,.17); }}
      .sim-pod.failed, .sim-pod.unknown {{ background:rgba(220,53,69,.16); }}
      .sim-empty {{ opacity:.55; font-size:.78rem; }}
    </style>
    <div class="sim-cluster">
      <div class="sim-cluster-head">{html.escape(cluster["name"])} · {html.escape(cluster["provider"])} · {html.escape(cluster["region"])}</div>
      <div class="sim-grid">{''.join(cards)}</div>
    </div>
    """


def _render_overview(username, state):
    cluster = state["cluster"]
    workers = [node for node in state["nodes"] if node["role"] == "worker"]
    running_pods = sum(pod["status"] == "Running" for pod in state["pods"].values())
    pending_pods = sum(pod["status"] == "Pending" for pod in state["pods"].values())
    metrics = st.columns(5)
    metrics[0].metric("Provider", cluster["provider"])
    metrics[1].metric("Workers", len(workers))
    metrics[2].metric("Running Pods", running_pods)
    metrics[3].metric("Pending Pods", pending_pods)
    metrics[4].metric("Services", len(state["services"]))

    st.markdown("#### Live Virtual Topology")
    st.markdown(_topology_html(state), unsafe_allow_html=True)

    st.markdown("#### Node Capacity")
    st.dataframe(pd.DataFrame(node_rows(state)), width="stretch", hide_index=True)

    with st.expander("Add virtual worker node"):
        with st.form("add_virtual_worker"):
            cols = st.columns(3)
            cpu = cols[0].number_input("CPU cores", 1, 128, 4)
            memory = cols[1].number_input("Memory (Mi)", 512, 1048576, 8192, step=512)
            storage = cols[2].number_input("Storage (Gi)", 10, 65536, 80, step=10)
            submitted = st.form_submit_button("Add Worker")
        if submitted and _safe_action(
            username,
            state,
            lambda: add_worker_node(state, cpu, memory, storage),
            "Virtual worker added.",
        ):
            st.rerun()


def _render_workloads(username, state):
    namespaces = sorted(state["namespaces"])
    create_tab, inspect_tab = st.tabs(["Create Resources", "Inspect Resources"])
    with create_tab:
        namespace_col, deployment_col = st.columns([0.8, 2.2])
        with namespace_col:
            st.markdown("##### Namespace")
            with st.form("create_namespace_form"):
                namespace_name = st.text_input("Name", placeholder="data-engineering")
                namespace_submit = st.form_submit_button("Create")
            if namespace_submit and _safe_action(
                username,
                state,
                lambda: create_namespace(state, namespace_name),
                f"Namespace {namespace_name} created.",
            ):
                st.rerun()
        with deployment_col:
            st.markdown("##### Deployment / StatefulSet")
            with st.form("create_workload_form"):
                row1 = st.columns(4)
                name = row1[0].text_input("Name", value="spark-worker")
                image = row1[1].text_input("Image", value="apache/spark:latest")
                namespace = row1[2].selectbox("Namespace", namespaces)
                kind = row1[3].selectbox("Controller", ["Deployment", "StatefulSet"])
                row2 = st.columns(4)
                replicas = row2[0].number_input("Replicas", 0, 500, 3)
                cpu = row2[1].number_input("CPU request (millicores)", 1, 128000, 500, step=100)
                memory = row2[2].number_input("Memory request (Mi)", 1, 1048576, 512, step=128)
                heap = row2[3].number_input(
                    "JVM heap per pod (Mi)",
                    0,
                    1048576,
                    0,
                    step=128,
                    help="Optional simulated -Xmx value for JVM workloads such as Spark or Kafka.",
                )
                workload_submit = st.form_submit_button("Create Workload", type="primary")
            if workload_submit and _safe_action(
                username,
                state,
                lambda: create_deployment(
                    state,
                    name,
                    image,
                    replicas,
                    namespace,
                    cpu,
                    memory,
                    kind,
                    heap,
                ),
                f"{kind} {name} created.",
            ):
                st.rerun()

        st.markdown("##### Service")
        deployments = list(state["deployments"].values())
        if not deployments:
            st.info("Create a deployment before exposing it as a service.")
        else:
            with st.form("create_service_form"):
                row = st.columns(5)
                selected = row[0].selectbox(
                    "Deployment",
                    deployments,
                    format_func=lambda item: f"{item['namespace']}/{item['name']}",
                )
                service_name = row[1].text_input("Service name", value=selected["name"])
                port = row[2].number_input("Port", 1, 65535, 80)
                target_port = row[3].number_input("Target port", 1, 65535, 8080)
                service_type = row[4].selectbox("Type", ["ClusterIP", "NodePort", "LoadBalancer"])
                service_submit = st.form_submit_button("Create Service")
            if service_submit and _safe_action(
                username,
                state,
                lambda: create_service(
                    state,
                    service_name,
                    selected["name"],
                    port,
                    target_port,
                    service_type,
                    selected["namespace"],
                ),
                f"Service {service_name} created.",
            ):
                st.rerun()

    with inspect_tab:
        resource = st.segmented_control(
            "Resource",
            ["Pods", "Deployments", "Services"],
            default="Pods",
            key="sim_inspect_resource",
        )
        if resource == "Deployments":
            rows = deployment_rows(state)
        elif resource == "Services":
            rows = service_rows(state)
        else:
            rows = pod_rows(state)
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        else:
            st.info(f"No {resource.lower()} have been created.")


def _render_terminal(username, state):
    st.caption(
        "Safe simulator terminal: commands are parsed against the virtual state. "
        "No host shell, cloud account, or real Kubernetes API is contacted."
    )
    quick = st.selectbox("Quick command", QUICK_COMMANDS, key="sim_quick_command")
    if st.button("Place in terminal", key="sim_place_quick"):
        st.session_state["sim_terminal_command"] = quick

    with st.form("sim_terminal_form"):
        command = st.text_input(
            "Terminal",
            value=st.session_state.get("sim_terminal_command", "kubectl get nodes"),
            placeholder="kubectl create deployment api --image=example/api:1.0 --replicas=3",
        )
        run = st.form_submit_button("Run Simulated Command", type="primary")
    if run:
        new_state, output = execute_command(
            state,
            command,
            st.session_state.get("sim_manifest", ""),
        )
        _store_state(username, new_state)
        st.session_state["sim_terminal_command"] = command
        st.session_state["sim_last_output"] = output
        st.rerun()

    if st.session_state.get("sim_last_output"):
        st.code(st.session_state["sim_last_output"], language="text", wrap_lines=True)

    with st.expander("YAML manifest editor", expanded=False):
        st.text_area(
            "Manifest",
            value=MANIFEST_EXAMPLE,
            height=360,
            key="sim_manifest",
        )
        st.caption("Apply it with: `kubectl apply -f -`")

    with st.expander("Supported command examples"):
        st.code(
            """kubectl get pods -A
kubectl create namespace streaming
kubectl create deployment kafka --image=bitnami/kafka:latest --replicas=3 -n default
kubectl run debug --image=busybox:latest
kubectl expose deployment kafka --port=9092 --target-port=9092
kubectl scale deployment/kafka --replicas=6
kubectl describe pod POD_NAME
kubectl logs POD_NAME
kubectl delete pod POD_NAME
kubectl cordon NODE_NAME
kubectl drain NODE_NAME
kubectl uncordon NODE_NAME
kubectl rollout restart deployment/kafka
kubectl top nodes
kubectl apply -f -
helm install airflow apache-airflow/airflow --replica-count=3
helm upgrade airflow apache-airflow/airflow --replica-count=5
helm list
helm uninstall airflow
oc new-app example/data-api:1.0 --name=data-api""",
            language="bash",
        )

    history = state.get("history", [])
    if history:
        st.markdown("#### Command History")
        for entry in reversed(history[-12:]):
            status = "✓" if entry["success"] else "✗"
            with st.expander(f"{status} {entry['command']}"):
                st.code(entry["output"], language="text", wrap_lines=True)


def _render_failures(username, state):
    node_names = [node["name"] for node in state["nodes"] if node["role"] == "worker"]
    pod_names = [f"{pod['namespace']}/{pod['name']}" for pod in state["pods"].values()]
    node_col, pod_col = st.columns(2)
    with node_col:
        st.markdown("#### Node Operations")
        node_name = st.selectbox("Worker node", node_names, key="failure_node")
        controls = st.columns(4)
        if controls[0].button("Fail", key="fail_node"):
            if _safe_action(username, state, lambda: set_node_status(state, node_name, "NotReady"), "Node failed; managed pods were rescheduled."):
                st.rerun()
        if controls[1].button("Recover", key="recover_node"):
            if _safe_action(username, state, lambda: set_node_status(state, node_name, "Ready"), "Node recovered."):
                st.rerun()
        if controls[2].button("Cordon", key="cordon_node"):
            node = next(item for item in state["nodes"] if item["name"] == node_name)
            node["schedulable"] = False
            _store_state(username, state)
            st.rerun()
        if controls[3].button("Uncordon", key="uncordon_node"):
            node = next(item for item in state["nodes"] if item["name"] == node_name)
            node["schedulable"] = True
            _store_state(username, state)
            st.rerun()
    with pod_col:
        st.markdown("#### Pod Operations")
        if not pod_names:
            st.info("Create a workload to practice pod failures.")
        else:
            pod_ref = st.selectbox("Pod", pod_names, key="failure_pod")
            namespace, pod_name = pod_ref.split("/", 1)
            controls = st.columns(2)
            if controls[0].button("Crash / Restart", key="crash_pod"):
                if _safe_action(username, state, lambda: restart_pod(state, pod_name, namespace), "Container restart simulated."):
                    st.rerun()
            if controls[1].button("Delete Pod", key="delete_pod"):
                if _safe_action(username, state, lambda: delete_pod(state, pod_name, namespace), "Pod deleted; its controller reconciled desired replicas."):
                    st.rerun()

    st.markdown("#### Cluster Events")
    events = list(reversed(state.get("events", [])[-50:]))
    if events:
        st.dataframe(pd.DataFrame(events), width="stretch", hide_index=True)


def _render_guided_labs(state):
    running = [pod for pod in state["pods"].values() if pod["status"] == "Running"]
    has_three_replica_workload = any(
        deployment["replicas"] >= 3 for deployment in state["deployments"].values()
    )
    has_service = bool(state["services"])
    has_failed_node = any(node["status"] != "Ready" for node in state["nodes"])
    has_helm = bool(state["helm_releases"])
    challenges = [
        (
            "Deploy a resilient application",
            "Create a deployment with at least three replicas.",
            has_three_replica_workload,
            "kubectl create deployment api --image=example/api:1.0 --replicas=3",
        ),
        (
            "Expose the application",
            "Create a service targeting one of your deployments.",
            has_service,
            "kubectl expose deployment api --port=80 --target-port=8080",
        ),
        (
            "Practice reconciliation",
            "Delete a managed pod and observe its replacement in topology and events.",
            any(event["reason"] == "Killing" for event in state["events"]),
            "kubectl delete pod POD_NAME",
        ),
        (
            "Recover from node failure",
            "Fail a worker and verify workloads continue on healthy workers.",
            has_failed_node and bool(running),
            "Use Fail in the Failure Lab, then run kubectl get pods -A",
        ),
        (
            "Manage a Helm release",
            "Install or upgrade a simulated Helm chart.",
            has_helm,
            "helm install airflow apache-airflow/airflow --replica-count=3",
        ),
    ]
    completed = sum(item[2] for item in challenges)
    st.progress(completed / len(challenges), text=f"{completed} of {len(challenges)} guided labs completed")
    for title, description, complete, command in challenges:
        icon = "✅" if complete else "⬜"
        with st.expander(f"{icon} {title}"):
            st.write(description)
            st.code(command, language="bash")


def _render_lab_toolbar(username, state):
    cluster = state["cluster"]
    top = st.columns([4, 1, 1])
    top[0].caption(
        f"Virtual cluster: `{cluster['name']}` · Kubernetes `{cluster['version']}` · "
        f"state is saved per user"
    )
    top[1].download_button(
        "Export State",
        export_state(state),
        file_name=f"{cluster['name']}-simulator.json",
        mime="application/json",
        width="stretch",
    )
    with top[2].popover("Reset Lab", width="stretch"):
        confirm = st.checkbox("Delete this virtual cluster", key="confirm_reset_sim")
        if st.button("Reset", disabled=not confirm, type="primary"):
            delete_kubernetes_lab(username)
            st.session_state[_state_key(username)] = None
            st.session_state["sim_last_output"] = ""
            st.rerun()


def render_kubernetes_simulator():
    username = st.session_state.get("user")
    state = _load_state(username)
    if not state:
        _render_cluster_creator(username)
        return

    _render_lab_toolbar(username, state)
    tabs = st.tabs(
        [
            "Cluster Overview",
            "Workloads & Services",
            "Terminal & YAML",
            "Failure Lab",
            "Guided Practice",
        ]
    )
    with tabs[0]:
        _render_overview(username, state)
    with tabs[1]:
        _render_workloads(username, state)
    with tabs[2]:
        _render_terminal(username, state)
    with tabs[3]:
        _render_failures(username, state)
    with tabs[4]:
        _render_guided_labs(state)
