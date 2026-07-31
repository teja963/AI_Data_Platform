import html
import json
import shlex

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
    execute_pod_command,
    export_state,
    namespace_rows,
    namespace_usage,
    node_rows,
    normalize_cluster_state,
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
        st.session_state[key] = normalize_cluster_state(
            load_kubernetes_lab(username)
        )
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
    with st.form("virtual_cluster_create_form"):
        profile = st.segmented_control(
            "Cluster size",
            [*CLUSTER_PRESETS, "Custom"],
            default="Medium",
            key="k8s_create_profile",
            help=(
                "Small: 2 × 2 CPU/4 GiB · Medium: 4 × 4 CPU/8 GiB · "
                "Large: 8 × 8 CPU/16 GiB. Selection is applied only when you create the cluster."
            ),
        )
        identity_cols = st.columns(3)
        name = identity_cols[0].text_input("Cluster name", value="data-platform-lab")
        provider = identity_cols[1].selectbox("Provider model", list(PROVIDER_REGIONS))
        region = identity_cols[2].text_input(
            "Region",
            value=PROVIDER_REGIONS[list(PROVIDER_REGIONS)[0]],
            help="A simulated provider region used for learning and display.",
        )
        capacity_cols = st.columns(4)
        custom_workers = capacity_cols[0].number_input(
            "Custom worker nodes", min_value=1, max_value=100, value=4
        )
        custom_cpu = capacity_cols[1].number_input(
            "Custom CPU / worker", min_value=1, max_value=128, value=4
        )
        custom_memory = capacity_cols[2].number_input(
            "Custom memory / worker (Mi)", min_value=512, max_value=1048576, value=8192, step=512
        )
        custom_storage = capacity_cols[3].number_input(
            "Custom storage / worker (Gi)", min_value=10, max_value=65536, value=80, step=10
        )
        create = st.form_submit_button("Create Virtual Cluster", type="primary")
    if create:
        selected_profile = profile or "Medium"
        capacity = (
            {
                "workers": custom_workers,
                "cpu": custom_cpu,
                "memory": custom_memory,
                "storage": custom_storage,
            }
            if selected_profile == "Custom"
            else CLUSTER_PRESETS[selected_profile]
        )
        state = create_cluster(
            name,
            provider,
            region,
            capacity["workers"],
            capacity["cpu"],
            capacity["memory"],
            capacity["storage"],
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
    st.html(_topology_html(state))

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
    cluster_terminal, pod_shell, manifest_tab = st.tabs(
        ["Cluster Terminal", "Pod Shell", "YAML Apply"]
    )
    with cluster_terminal:
        with st.form("sim_terminal_form"):
            quick = st.selectbox(
                "Command template",
                ["Custom command", *QUICK_COMMANDS],
                key="sim_quick_command",
            )
            custom_command = st.text_input(
                "Command",
                value=st.session_state.get(
                    "sim_terminal_command",
                    "kubectl get nodes",
                ),
                placeholder="kubectl create deployment api --image=example/api:1.0 --replicas=3",
            )
            run = st.form_submit_button("Execute", type="primary")
        if run:
            command = custom_command if quick == "Custom command" else quick
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
            st.markdown("##### Terminal Output")
            st.code(st.session_state["sim_last_output"], language="text", wrap_lines=True)

        with st.expander("Supported cluster command examples"):
            st.code(
                """kubectl get pods -A
kubectl get pod POD_NAME -o yaml
kubectl get all -A
kubectl create namespace streaming
kubectl create deployment kafka --image=bitnami/kafka:latest --replicas=3
kubectl expose deployment kafka --port=9092 --target-port=9092
kubectl scale deployment/kafka --replicas=6
kubectl describe pod POD_NAME
kubectl logs POD_NAME
kubectl exec -it POD_NAME -- env
kubectl delete pod POD_NAME
kubectl cordon NODE_NAME
kubectl drain NODE_NAME
kubectl uncordon NODE_NAME
kubectl rollout restart deployment/kafka
kubectl rollout status deployment/kafka
kubectl set image deployment/kafka kafka=bitnami/kafka:latest
kubectl label node NODE_NAME workload=streaming
kubectl top nodes
kubectl api-resources
kubectl explain deployment
kubectl config current-context
kubectl auth can-i create pods
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

    with pod_shell:
        running_pods = [
            pod for pod in state["pods"].values() if pod["status"] == "Running"
        ]
        if not running_pods:
            st.info(
                "Create a workload first. A running pod is required before you can inspect its virtual shell."
            )
        else:
            services = list(state["services"].values())
            shell_commands = [
                "env",
                "printenv JAVA_TOOL_OPTIONS",
                "pwd",
                "ls /",
                "ls /app/config",
                "cat /etc/os-release",
                "cat /app/config/application.properties",
                "cat /proc/meminfo",
                "ps aux",
                "top",
                "df -h",
                "free -m",
                "hostname",
                "java -version",
            ]
            if services:
                shell_commands.extend(
                    [
                        f"nslookup {services[0]['name']}",
                        f"curl http://{services[0]['name']}:{services[0]['port']}",
                    ]
                )
            with st.form("virtual_pod_shell_form"):
                pod = st.selectbox(
                    "Running pod",
                    running_pods,
                    format_func=lambda item: f"{item['namespace']}/{item['name']}",
                )
                template = st.selectbox(
                    "Inside-pod command",
                    ["Custom command", *shell_commands],
                )
                custom_inside = st.text_input(
                    "Custom inside-pod command",
                    value="env",
                    help="This is interpreted by the simulator and never sent to the host shell.",
                )
                execute_inside = st.form_submit_button(
                    "Execute Inside Pod",
                    type="primary",
                )
            if execute_inside:
                inside_command = (
                    custom_inside if template == "Custom command" else template
                )
                full_command = (
                    f"kubectl exec -n {pod['namespace']} {pod['name']} -- "
                    f"{inside_command}"
                )
                new_state, output = execute_command(state, full_command)
                _store_state(username, new_state)
                st.session_state["sim_pod_shell_prompt"] = (
                    f"{pod['name']}:/app$ {inside_command}"
                )
                st.session_state["sim_pod_shell_output"] = output
                st.rerun()
            if st.session_state.get("sim_pod_shell_output"):
                st.code(
                    f"{st.session_state.get('sim_pod_shell_prompt', '')}\n"
                    f"{st.session_state['sim_pod_shell_output']}",
                    language="bash",
                    wrap_lines=True,
                )

    with manifest_tab:
        with st.form("sim_manifest_form"):
            st.text_area(
                "Manifest",
                value=MANIFEST_EXAMPLE,
                height=360,
                key="sim_manifest",
            )
            st.caption("Equivalent terminal command: `kubectl apply -f -`")
            apply_manifest_clicked = st.form_submit_button(
                "Apply Manifest",
                type="primary",
            )
        if apply_manifest_clicked:
            new_state, output = execute_command(
                state,
                "kubectl apply -f -",
                st.session_state.get("sim_manifest", ""),
            )
            _store_state(username, new_state)
            st.session_state["sim_manifest_output"] = output
            st.rerun()
        if st.session_state.get("sim_manifest_output"):
            st.code(
                st.session_state["sim_manifest_output"],
                language="text",
                wrap_lines=True,
            )


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


def _percent(value, maximum):
    if not maximum:
        return 0
    return min(100, round((value / maximum) * 100, 1))


def _render_cluster_monitor(state):
    workers = [node for node in state["nodes"] if node["role"] == "worker"]
    total_cpu = sum(node["cpu_capacity_m"] for node in workers)
    total_memory = sum(node["memory_capacity_mi"] for node in workers)
    total_storage = sum(node["storage_gi"] for node in workers)
    used_cpu = sum(int(pod.get("cpu_request_m", 0)) for pod in state["pods"].values())
    used_memory = sum(
        int(pod.get("memory_request_mi", 0)) for pod in state["pods"].values()
    )
    running = sum(pod["status"] == "Running" for pod in state["pods"].values())
    pending = sum(pod["status"] == "Pending" for pod in state["pods"].values())
    healthy_nodes = sum(node["status"] == "Ready" for node in workers)
    namespace_cards = []
    for namespace in state["namespaces"].values():
        usage = namespace_usage(state, namespace["name"])
        cpu_quota = namespace.get("cpu_quota_m", 0)
        memory_quota = namespace.get("memory_quota_mi", 0)
        pod_quota = namespace.get("pod_quota", 0)
        namespace_cards.append(
            f"""
            <div class="kmon-panel">
              <div class="kmon-title">{html.escape(namespace["name"])}</div>
              <div class="kmon-sub">{html.escape(namespace.get("owner", "Platform Team"))} · {html.escape(namespace.get("environment", "Shared"))}</div>
              <div class="kmon-row"><span>Pods</span><b>{usage["running_pods"]} running · {usage["pending_pods"]} pending · {pod_quota or "∞"} max</b></div>
              <div class="kmon-row"><span>CPU</span><b>{usage["cpu_m"]}m / {str(cpu_quota) + "m" if cpu_quota else "unlimited"}</b></div>
              <div class="kmon-bar"><i style="width:{_percent(usage["cpu_m"], cpu_quota or total_cpu)}%"></i></div>
              <div class="kmon-row"><span>Memory</span><b>{usage["memory_mi"]}Mi / {str(memory_quota) + "Mi" if memory_quota else "unlimited"}</b></div>
              <div class="kmon-bar memory"><i style="width:{_percent(usage["memory_mi"], memory_quota or total_memory)}%"></i></div>
              <div class="kmon-foot">{usage["deployments"]} deployments · {usage["services"]} services</div>
            </div>
            """
        )
    cluster = state["cluster"]
    st.html(
        f"""
        <style>
          .kmon {{font-family:Inter,system-ui,sans-serif;background:#0b1017;color:#e8edf5;border:1px solid #253044;border-radius:10px;padding:13px}}
          .kmon-head {{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:12px}}
          .kmon-cluster {{font-size:.94rem;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
          .kmon-health {{font-size:.76rem;color:#75e39a;white-space:nowrap}}
          .kmon-summary {{display:grid;grid-template-columns:repeat(6,minmax(110px,1fr));gap:7px;margin-bottom:10px}}
          .kmon-stat,.kmon-panel {{background:#111a25;border:1px solid #26364c;border-radius:7px;padding:9px}}
          .kmon-stat small {{display:block;color:#8fa1b8;font-size:.68rem;text-transform:uppercase;letter-spacing:.05em}}
          .kmon-stat strong {{font-size:1.05rem}}
          .kmon-grid {{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px}}
          .kmon-title {{font-size:.9rem;font-weight:700}}
          .kmon-sub,.kmon-foot {{font-size:.68rem;color:#8fa1b8;margin:2px 0 7px}}
          .kmon-row {{display:flex;justify-content:space-between;gap:8px;font-size:.72rem;margin-top:6px}}
          .kmon-row span {{color:#9aaac0}} .kmon-row b {{font-weight:600;text-align:right}}
          .kmon-bar {{height:5px;background:#273244;border-radius:4px;overflow:hidden;margin-top:3px}}
          .kmon-bar i {{display:block;height:100%;background:#51a8ff;border-radius:4px}}
          .kmon-bar.memory i {{background:#b47cff}}
          @media(max-width:900px){{.kmon-summary{{grid-template-columns:repeat(2,1fr)}}}}
        </style>
        <div class="kmon">
          <div class="kmon-head">
            <div class="kmon-cluster">{html.escape(cluster["name"])}</div>
            <div class="kmon-health">● {healthy_nodes}/{len(workers)} workers ready</div>
          </div>
          <div class="kmon-summary">
            <div class="kmon-stat"><small>Namespaces</small><strong>{len(state["namespaces"])}</strong></div>
            <div class="kmon-stat"><small>Pods</small><strong>{running} / {pending}</strong></div>
            <div class="kmon-stat"><small>CPU allocated</small><strong>{_percent(used_cpu,total_cpu)}%</strong></div>
            <div class="kmon-stat"><small>Memory allocated</small><strong>{_percent(used_memory,total_memory)}%</strong></div>
            <div class="kmon-stat"><small>Total CPU</small><strong>{total_cpu // 1000} cores</strong></div>
            <div class="kmon-stat"><small>Storage</small><strong>{total_storage} Gi</strong></div>
          </div>
          <div class="kmon-grid">{''.join(namespace_cards)}</div>
        </div>
        """
    )
    namespace_tab, worker_tab = st.tabs(["Namespace Allocation", "Worker Allocation"])
    with namespace_tab:
        st.dataframe(
            pd.DataFrame(namespace_rows(state)),
            width="stretch",
            hide_index=True,
        )
    with worker_tab:
        st.caption(
            "Workers may have different capacities. Pods from multiple namespaces can share a worker."
        )
        st.dataframe(
            pd.DataFrame(node_rows(state)),
            width="stretch",
            hide_index=True,
        )


def _parse_labels(value):
    labels = {}
    for item in (value or "").split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"label must use key=value format: {item}")
        key, label_value = item.split("=", 1)
        labels[key.strip()] = label_value.strip()
    return labels


def _render_resource_management(username, state):
    namespace_tab, workload_tab, inspect_tab = st.tabs(
        ["Namespaces", "Deployments & Services", "Inspect"]
    )
    with namespace_tab:
        st.caption(
            "A namespace is a cluster-level organizational and policy boundary. "
            "Quotas are enforceable maximums; Kubernetes schedules its pods across available workers."
        )
        with st.form("namespace_policy_form"):
            identity = st.columns(3)
            name = identity[0].text_input("Namespace name", placeholder="data-engineering")
            owner = identity[1].text_input("Owner / team", value="Data Platform")
            environment = identity[2].selectbox(
                "Environment",
                ["Development", "Testing", "Staging", "Production", "Shared"],
            )
            quotas = st.columns(4)
            cpu_cores = quotas[0].number_input("CPU quota (cores)", 0.0, 10000.0, 4.0, step=0.5)
            memory_gi = quotas[1].number_input("Memory quota (Gi)", 0.0, 100000.0, 8.0, step=0.5)
            storage_gi = quotas[2].number_input("Storage quota (Gi)", 0, 1000000, 50)
            max_pods = quotas[3].number_input("Maximum pods", 0, 100000, 20)
            defaults = st.columns(3)
            default_cpu = defaults[0].number_input("Default CPU / pod (m)", 1, 128000, 250)
            default_memory = defaults[1].number_input("Default memory / pod (Mi)", 1, 1048576, 256)
            labels_text = defaults[2].text_input(
                "Labels",
                value="team=data-platform",
                help="Comma-separated key=value labels.",
            )
            create_clicked = st.form_submit_button("Create Namespace", type="primary")
        if create_clicked:
            try:
                create_namespace(
                    state,
                    name,
                    owner,
                    environment,
                    int(cpu_cores * 1000),
                    int(memory_gi * 1024),
                    storage_gi,
                    max_pods,
                    default_cpu,
                    default_memory,
                    _parse_labels(labels_text),
                )
                _store_state(username, state)
                st.rerun()
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
        st.dataframe(pd.DataFrame(namespace_rows(state)), width="stretch", hide_index=True)

    with workload_tab:
        namespaces = sorted(state["namespaces"])
        with st.form("namespace_workload_form"):
            first = st.columns(4)
            namespace = first[0].selectbox("Namespace", namespaces)
            workload_name = first[1].text_input("Workload name", value="data-api")
            image = first[2].text_input("Container image", value="example/data-api:1.0")
            kind = first[3].selectbox("Controller", ["Deployment", "StatefulSet"])
            second = st.columns(4)
            replicas = second[0].number_input("Pods / replicas", 0, 5000, 3)
            cpu = second[1].number_input("CPU / pod (m)", 1, 128000, 250)
            memory = second[2].number_input("Memory / pod (Mi)", 1, 1048576, 256)
            heap = second[3].number_input("JVM heap / pod (Mi)", 0, 1048576, 0)
            create_workload_clicked = st.form_submit_button(
                "Create Workload",
                type="primary",
            )
        if create_workload_clicked:
            try:
                create_deployment(
                    state,
                    workload_name,
                    image,
                    replicas,
                    namespace,
                    cpu,
                    memory,
                    kind,
                    heap,
                )
                _store_state(username, state)
                st.rerun()
            except (ValueError, TypeError) as exc:
                st.error(str(exc))

        deployments = list(state["deployments"].values())
        if deployments:
            with st.form("namespace_service_form"):
                service_fields = st.columns(5)
                target = service_fields[0].selectbox(
                    "Workload",
                    deployments,
                    format_func=lambda item: f"{item['namespace']}/{item['name']}",
                )
                service_name = service_fields[1].text_input("Service name", value="data-api")
                port = service_fields[2].number_input("Service port", 1, 65535, 80)
                target_port = service_fields[3].number_input("Container port", 1, 65535, 8080)
                service_type = service_fields[4].selectbox(
                    "Service type",
                    ["ClusterIP", "NodePort", "LoadBalancer"],
                )
                create_service_clicked = st.form_submit_button("Create Service")
            if create_service_clicked:
                try:
                    create_service(
                        state,
                        service_name,
                        target["name"],
                        port,
                        target_port,
                        service_type,
                        target["namespace"],
                    )
                    _store_state(username, state)
                    st.rerun()
                except (ValueError, TypeError) as exc:
                    st.error(str(exc))

    with inspect_tab:
        namespaces_view, pods_view, deployments_view, services_view = st.tabs(
            ["Namespaces", "Pods", "Deployments", "Services"]
        )
        resources = [
            (namespaces_view, namespace_rows(state), "namespaces"),
            (pods_view, pod_rows(state), "pods"),
            (deployments_view, deployment_rows(state), "deployments"),
            (services_view, service_rows(state), "services"),
        ]
        for tab, rows, label in resources:
            with tab:
                if rows:
                    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
                else:
                    st.info(f"No {label} found.")


def _terminal_prompt(state):
    context = state["terminal_context"]
    if context["mode"] == "pod":
        return f"{context['namespace']}/{context['pod']}:{context.get('cwd', '/app')}$"
    return f"{state['cluster']['name']}[{context['namespace']}]$"


def _terminal_run(state, command):
    context = state["terminal_context"]
    command = command.strip()
    if command == "clear":
        return state, "", True
    if context["mode"] == "pod":
        if command == "exit":
            context.update({"mode": "cluster", "pod": None, "cwd": "/app"})
            return state, "Returned to cluster context.", False
        try:
            output = execute_pod_command(
                state,
                context["namespace"],
                context["pod"],
                command,
            )
            return state, output, False
        except (ValueError, TypeError) as exc:
            return state, f"error: {exc}", False

    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return state, f"error: {exc}", False
    if not tokens:
        return state, "", False
    if tokens[:2] == ["oc", "project"] and len(tokens) >= 3:
        namespace = tokens[2]
        if namespace not in state["namespaces"]:
            return state, f'error: namespace "{namespace}" not found', False
        context["namespace"] = namespace
        return state, f'Now using project "{namespace}".', False
    if (
        len(tokens) >= 4
        and tokens[0] in {"kubectl", "k"}
        and tokens[1:3] == ["config", "set-context"]
    ):
        namespace_arg = next(
            (token.split("=", 1)[1] for token in tokens if token.startswith("--namespace=")),
            None,
        )
        if namespace_arg:
            if namespace_arg not in state["namespaces"]:
                return state, f'error: namespace "{namespace_arg}" not found', False
            context["namespace"] = namespace_arg
            return state, f'Context namespace changed to "{namespace_arg}".', False
    if tokens[:2] == ["oc", "rsh"] and len(tokens) >= 3:
        namespace = context["namespace"]
        if "-n" in tokens:
            namespace = tokens[tokens.index("-n") + 1]
        pod_name = next(
            (
                token for token in tokens[2:]
                if not token.startswith("-") and token != namespace
            ),
            None,
        )
        pod = state["pods"].get(f"{namespace}/{pod_name}")
        if not pod or pod["status"] != "Running":
            return state, f'error: running pod "{pod_name}" not found', False
        context.update(
            {"mode": "pod", "namespace": namespace, "pod": pod_name, "cwd": "/app"}
        )
        return state, f"Connected to {namespace}/{pod_name}. Type exit to return.", False
    if tokens[0] in {"kubectl", "k", "oc"} and len(tokens) > 1 and tokens[1] == "exec":
        if "--" in tokens:
            separator = tokens.index("--")
            inside = tokens[separator + 1 :]
            if inside and inside[0] in {"sh", "bash"}:
                namespace = context["namespace"]
                if "-n" in tokens:
                    namespace = tokens[tokens.index("-n") + 1]
                if "--namespace" in tokens:
                    namespace = tokens[tokens.index("--namespace") + 1]
                candidates = [
                    token
                    for token in tokens[2:separator]
                    if not token.startswith("-") and token != namespace
                ]
                pod_name = candidates[-1] if candidates else None
                pod = state["pods"].get(f"{namespace}/{pod_name}")
                if not pod or pod["status"] != "Running":
                    return state, f'error: running pod "{pod_name}" not found', False
                context.update(
                    {
                        "mode": "pod",
                        "namespace": namespace,
                        "pod": pod_name,
                        "cwd": "/app",
                    }
                )
                return state, f"Connected to {namespace}/{pod_name}. Type exit to return.", False

    effective_command = command
    if tokens[0] in {"kubectl", "k", "oc", "helm"} and "-n" not in tokens and "--namespace" not in tokens:
        if "--" in tokens:
            separator = tokens.index("--")
            namespaced_tokens = [
                *tokens[:separator],
                "-n",
                context["namespace"],
                *tokens[separator:],
            ]
            effective_command = shlex.join(namespaced_tokens)
        else:
            effective_command += f" -n {context['namespace']}"
    new_state, output = execute_command(state, effective_command)
    return new_state, output, False


def _terminal_history_script(history):
    history_json = json.dumps(history[-100:])
    st.iframe(
        f"""
        <script>
        (() => {{
          try {{
            const history = {history_json};
            const root = window.parent.document.querySelector('[class*="st-key-unified_terminal_form"]');
            const input = root && root.querySelector('input');
            if (!input || input.dataset.k8sHistoryBound === '1') return;
            input.dataset.k8sHistoryBound = '1';
            let index = history.length;
            const setValue = (value) => {{
              const setter = Object.getOwnPropertyDescriptor(
                window.parent.HTMLInputElement.prototype, 'value'
              ).set;
              setter.call(input, value);
              input.dispatchEvent(new window.parent.Event('input', {{bubbles:true}}));
            }};
            input.addEventListener('keydown', (event) => {{
              if (event.key === 'ArrowUp' && history.length) {{
                event.preventDefault();
                index = Math.max(0, index - 1);
                setValue(history[index]);
              }} else if (event.key === 'ArrowDown' && history.length) {{
                event.preventDefault();
                index = Math.min(history.length, index + 1);
                setValue(index === history.length ? '' : history[index]);
              }}
            }});
          }} catch (error) {{}}
        }})();
        </script>
        """,
        height=1,
    )


def _render_unified_terminal(username, state):
    prompt = _terminal_prompt(state)
    buffer_key = f"k8s_terminal_buffer::{username}"
    commands_key = f"k8s_terminal_commands::{username}"
    version_key = f"k8s_terminal_input_version::{username}"
    st.session_state.setdefault(buffer_key, [])
    st.session_state.setdefault(commands_key, [])
    st.session_state.setdefault(version_key, 0)
    transcript = "\n".join(st.session_state[buffer_key][-80:])
    st.html(
        f"""
        <style>
          .terminal-window {{height:470px;overflow:auto;background:#05080c;color:#d7e2ef;border:1px solid #263445;border-radius:8px 8px 0 0;padding:12px;font:13px/1.45 SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}}
          .terminal-hint {{color:#8091a7;margin-bottom:8px}}
        </style>
        <div class="terminal-window"><span class="terminal-hint">Virtual Kubernetes terminal · kubectl · oc · helm · pod shell</span>
{html.escape(transcript)}</div>
        """
    )
    st.markdown(
        """
        <style>
        div[class*="st-key-unified_terminal_form"] {
            background:#05080c; border:1px solid #263445; border-top:0;
            border-radius:0 0 8px 8px; padding:.25rem .55rem .5rem;
        }
        div[class*="st-key-unified_terminal_form"] input {
            background:#05080c !important; color:#d7e2ef !important;
            border:0 !important; font-family:SFMono-Regular,Consolas,monospace !important;
        }
        div[class*="st-key-unified_terminal_form"] button {display:none !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.form("unified_terminal_form", clear_on_submit=True):
        command = st.text_input(
            prompt,
            key=f"k8s_terminal_input_{st.session_state[version_key]}",
            placeholder=f"{prompt} enter command",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Run")
    _terminal_history_script(st.session_state[commands_key])
    if submitted and command.strip():
        current_prompt = prompt
        new_state, output, clear_requested = _terminal_run(state, command)
        if clear_requested:
            st.session_state[buffer_key] = []
        else:
            st.session_state[buffer_key].append(
                f"{current_prompt} {command}\n{output}".rstrip()
            )
        st.session_state[commands_key].append(command)
        st.session_state[version_key] += 1
        _store_state(username, new_state)
        st.rerun()


def _render_yaml_apply(username, state):
    with st.form("simulator_yaml_apply_form"):
        manifest = st.text_area(
            "Kubernetes manifest",
            value=st.session_state.get("sim_manifest", MANIFEST_EXAMPLE),
            height=520,
        )
        applied = st.form_submit_button("Apply", type="primary")
    if applied:
        new_state, output = execute_command(state, "kubectl apply -f -", manifest)
        _store_state(username, new_state)
        st.session_state["sim_manifest"] = manifest
        st.session_state["sim_manifest_output"] = output
        st.rerun()
    if st.session_state.get("sim_manifest_output"):
        st.code(st.session_state["sim_manifest_output"], language="text")


def render_kubernetes_simulator():
    username = st.session_state.get("user")
    state = _load_state(username)
    if not state:
        _render_cluster_creator(username)
        return

    tabs = st.tabs(
        [
            "Cluster Monitor",
            "Namespaces & Resources",
            "Terminal",
            "YAML Apply",
        ]
    )
    with tabs[0]:
        _render_cluster_monitor(state)
    with tabs[1]:
        _render_resource_management(username, state)
    with tabs[2]:
        _render_unified_terminal(username, state)
    with tabs[3]:
        _render_yaml_apply(username, state)
