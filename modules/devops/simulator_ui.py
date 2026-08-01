import html
import json
import shlex
import uuid

import pandas as pd
import streamlit as st

from core.kubernetes_lab import (
    delete_kubernetes_lab,
    load_kubernetes_lab,
    save_kubernetes_lab,
)
from core.kubernetes_capacity import (
    CAPACITY_PROFILES,
    calculate_capacity,
    profile_inputs,
)
from core.kubernetes_simulator import (
    CLUSTER_PRESETS,
    PROVIDER_REGIONS,
    add_worker_node,
    create_cluster,
    create_deployment,
    create_namespace,
    create_pod,
    create_service,
    delete_pod,
    deployment_rows,
    deploy_data_platform_blueprint,
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
    update_namespace,
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

_TERMINAL_INPUT_BEHAVIOR = st.components.v2.component(
    "kubernetes_terminal_input_behavior",
    html="<span></span>",
    js="""
    export default function({data, parentElement}) {
      const documentRoot = parentElement.ownerDocument;
      const terminal = documentRoot.querySelector(
        `[class*="st-key-${data.shellKey}"]`
      );
      const input = terminal && terminal.querySelector("input");
      if (!input) return;
      input.focus();
      input.scrollIntoView({block: "nearest"});
      if (input.dataset.k8sTerminalBound === "1") return;
      input.dataset.k8sTerminalBound = "1";
      let index = data.history.length;
      input.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
        if (!data.history.length) return;
        event.preventDefault();
        if (event.key === "ArrowUp") {
          index = Math.max(0, index - 1);
        } else {
          index = Math.min(data.history.length, index + 1);
        }
        const value = index === data.history.length ? "" : data.history[index];
        const setter = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype, "value"
        ).set;
        setter.call(input, value);
        input.dispatchEvent(new Event("input", {bubbles: true}));
        input.setSelectionRange(value.length, value.length);
      });
    }
    """,
)


def _state_key(username):
    return f"kubernetes_simulator_state::{username}"


def _loaded_key(username):
    return f"kubernetes_simulator_loaded::{username}"


def _load_state(username):
    key = _state_key(username)
    if not st.session_state.get(_loaded_key(username)):
        loaded_state = load_kubernetes_lab(username)
        previous_version = (
            loaded_state.get("simulator_version", 0)
            if loaded_state
            else None
        )
        st.session_state[key] = normalize_cluster_state(loaded_state)
        if (
            st.session_state[key]
            and previous_version != st.session_state[key].get("simulator_version")
        ):
            save_kubernetes_lab(username, st.session_state[key])
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
    return round((value / maximum) * 100, 1)


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
        namespace_cards.append(
            f"""
            <div class="kmon-panel">
              <div class="kmon-title">{html.escape(namespace["name"])}</div>
              <div class="kmon-sub">{html.escape(namespace.get("owner", "Platform Team"))} · {html.escape(namespace.get("environment", "Shared"))}</div>
              <div class="kmon-row"><span>Pods</span><b>{usage["running_pods"]} running · {usage["pending_pods"]} pending</b></div>
              <div class="kmon-row"><span>CPU allocated</span><b>{usage["cpu_m"] / 1000:.2f} cores</b></div>
              <div class="kmon-bar"><i style="width:{_percent(usage["cpu_m"], total_cpu)}%"></i></div>
              <div class="kmon-row"><span>Memory allocated</span><b>{usage["memory_mi"] / 1024:.2f} GiB</b></div>
              <div class="kmon-bar memory"><i style="width:{_percent(usage["memory_mi"], total_memory)}%"></i></div>
              <div class="kmon-foot">{usage["deployments"]} deployments · {usage["services"]} services · default pod {namespace.get("default_cpu_m", 1000) / 1000:.0f} CPU / {namespace.get("default_memory_mi", 2048) / 1024:.0f} GiB</div>
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


def _render_capacity_planner(username, state):
    plan_key = f"k8s_capacity_plan::{username}"
    with st.form("kubernetes_capacity_planner"):
        first = st.columns(3)
        profile = first[0].selectbox(
            "Sizing profile",
            [*CAPACITY_PROFILES, "Custom"],
        )
        provider_options = list(PROVIDER_REGIONS)
        current_provider = state["cluster"].get("provider", provider_options[0])
        provider = first[1].selectbox(
            "Cloud / platform",
            provider_options,
            index=(
                provider_options.index(current_provider)
                if current_provider in provider_options
                else 0
            ),
        )
        volume_unit = first[2].selectbox("Custom ingestion unit", ["TB/day", "GB/day", "PB/day"])
        load = st.columns(4)
        custom_volume = load[0].number_input(
            "Custom daily ingestion",
            min_value=0.001,
            value=10.0,
            step=1.0,
        )
        peak_factor = load[1].number_input(
            "Peak multiplier",
            min_value=1.0,
            value=3.0,
            step=0.5,
        )
        retention_days = load[2].number_input(
            "Retention days",
            min_value=1,
            value=30,
        )
        replication = load[3].number_input(
            "Storage replication",
            min_value=1,
            value=3,
        )
        demand = st.columns(4)
        concurrent_jobs = demand[0].number_input(
            "Concurrent Flink jobs",
            min_value=1,
            value=10,
        )
        concurrent_users = demand[1].number_input(
            "Concurrent dashboard/query users",
            min_value=1,
            value=50,
        )
        zones = demand[2].number_input(
            "Availability zones",
            min_value=1,
            max_value=10,
            value=3,
        )
        growth = demand[3].number_input(
            "Growth headroom (%)",
            min_value=0,
            max_value=500,
            value=30,
        )
        with st.expander("Workload behavior and sizing assumptions"):
            behavior = st.columns(8)
            event_size_kb = behavior[0].number_input(
                "Average event size (KiB)",
                min_value=0.1,
                value=1.0,
                step=0.1,
            )
            flink_state_hours = behavior[1].number_input(
                "Flink state window (hours)",
                min_value=0.0,
                value=6.0,
                step=1.0,
            )
            flink_state_ratio = behavior[2].number_input(
                "State retained (%)",
                min_value=0.0,
                max_value=100.0,
                value=10.0,
            )
            flink_state_memory = behavior[3].number_input(
                "State in memory (%)",
                min_value=0.0,
                max_value=100.0,
                value=10.0,
            )
            hot_data_percent = behavior[4].number_input(
                "StarRocks hot data (%)",
                min_value=0.0,
                max_value=100.0,
                value=20.0,
            )
            compression_ratio = behavior[5].number_input(
                "Compression ratio",
                min_value=1.0,
                value=3.0,
                step=0.5,
            )
            starrocks_cache = behavior[6].number_input(
                "Local cache coverage (%)",
                min_value=0.0,
                max_value=100.0,
                value=5.0,
            )
            target_utilization = behavior[7].number_input(
                "Target utilization (%)",
                min_value=30.0,
                max_value=85.0,
                value=65.0,
            )
        calculate = st.form_submit_button("Calculate Capacity", type="primary")
    if calculate:
        if profile == "Custom":
            unit_multiplier = {"GB/day": 0.001, "TB/day": 1, "PB/day": 1000}
            inputs = {
                "daily_tb": custom_volume * unit_multiplier[volume_unit],
                "peak_factor": peak_factor,
                "retention_days": retention_days,
                "replication": replication,
                "concurrent_jobs": concurrent_jobs,
                "concurrent_users": concurrent_users,
                "zones": zones,
                "growth_percent": growth,
            }
        else:
            inputs = profile_inputs(profile)
        inputs.update(
            {
                "event_size_kb": event_size_kb,
                "flink_state_hours": flink_state_hours,
                "flink_state_ratio_percent": flink_state_ratio,
                "flink_state_memory_percent": flink_state_memory,
                "hot_data_percent": hot_data_percent,
                "compression_ratio": compression_ratio,
                "starrocks_cache_percent": starrocks_cache,
                "target_utilization_percent": target_utilization,
            }
        )
        st.session_state[plan_key] = calculate_capacity(provider=provider, **inputs)

    if plan_key not in st.session_state:
        st.session_state[plan_key] = calculate_capacity(
            provider=state["cluster"].get("provider", "On-Premises"),
            **profile_inputs("Development"),
        )
    plan = st.session_state[plan_key]
    st.html(
        f"""
        <style>
          .capacity-summary {{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:8px;background:#0b1017;padding:10px;border:1px solid #26364c;border-radius:8px;color:#e8edf5}}
          .capacity-summary div {{background:#111a25;border:1px solid #26364c;border-radius:6px;padding:9px}}
          .capacity-summary small {{display:block;color:#8fa1b8;font-size:.68rem;text-transform:uppercase}}
          .capacity-summary strong {{font-size:1rem}}
          @media(max-width:900px){{.capacity-summary{{grid-template-columns:repeat(2,1fr)}}}}
        </style>
        <div class="capacity-summary">
          <div><small>Daily ingestion</small><strong>{plan["daily_tb"]:.2f} TB</strong></div>
          <div><small>Average throughput</small><strong>{plan["average_mb_s"]:.1f} MB/s</strong></div>
          <div><small>Designed peak</small><strong>{plan["peak_mb_s"]:.1f} MB/s</strong></div>
          <div><small>Peak events</small><strong>{plan["peak_events_per_second"]:,.0f}/s</strong></div>
          <div><small>Retained with replicas</small><strong>{plan["retained_tb"] / 1000:.2f} PB</strong></div>
          <div><small>Estimated Flink state</small><strong>{plan["flink_state_gib"] / 1024:.2f} TiB</strong></div>
          <div><small>StarRocks hot set</small><strong>{plan["starrocks_hot_gib"] / 1024:.2f} TiB</strong></div>
          <div><small>Workload allocation</small><strong>{plan["total_component_cpu"]} CPU / {plan["total_component_memory_gib"]} GiB</strong></div>
        </div>
        """
    )
    component_rows = [
        {
            "Component": item["component"],
            "Controller": item["controller"],
            "Replicas": item["replicas"],
            "CPU each": f"{item['cpu_each']} cores",
            "Memory each": f"{item['memory_each_gib']} GiB",
            "Ports": item["ports"],
            "Sizing basis": item["basis"],
            "Purpose": item["role"],
        }
        for item in plan["components"]
    ]
    st.markdown("#### Recommended workload sizing")
    st.dataframe(pd.DataFrame(component_rows), width="stretch", hide_index=True)
    node_rows_data = [
        {
            "Node pool": item["pool"],
            "Provider example": item["node_type"],
            "Nodes": item["nodes"],
            "CPU / node": item["cpu"],
            "Memory / node": f"{item['memory']} GiB",
            "Storage / node": f"{item['storage']} GiB",
        }
        for item in plan["node_pools"]
    ]
    st.markdown("#### Recommended node pools")
    st.dataframe(pd.DataFrame(node_rows_data), width="stretch", hide_index=True)
    with st.expander("Calculation assumptions"):
        for assumption in plan["assumptions"]:
            st.markdown(f"- {assumption}")
    with st.expander("Cloud cost model"):
        st.write(plan["billing"])
        st.caption(
            "Kubernetes workloads are primarily billed by provisioned cluster resources. "
            "Serverless warehouses and query services may instead charge by compute time, "
            "capacity units or bytes scanned; those are separate services from the Kubernetes cluster."
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
    namespace_tab, workload_tab = st.tabs(["Namespaces", "Deployments & Services"])
    with namespace_tab:
        with st.form("namespace_policy_form"):
            identity = st.columns(3)
            name = identity[0].text_input("Namespace name", placeholder="data-engineering")
            owner = identity[1].text_input("Owner / team", value="Data Platform")
            environment = identity[2].selectbox(
                "Environment",
                ["Development", "Testing", "Staging", "Production", "Shared"],
            )
            quotas = st.columns(4)
            cpu_cores = quotas[0].number_input(
                "CPU quota (cores)", 0.1, 10000.0, 1.0, step=0.1
            )
            memory_gi = quotas[1].number_input(
                "Memory quota (GiB)",
                0.1,
                100000.0,
                2.0,
                step=0.1,
                help="1 GiB equals 1024 MiB.",
            )
            storage_gi = quotas[2].number_input("Storage quota (GiB)", 1, 1000000, 10)
            max_pods = quotas[3].number_input("Maximum pods", 1, 100000, 10)
            defaults = st.columns(3)
            default_cpu_cores = defaults[0].number_input(
                "Default CPU per pod (cores)", 0.01, 128.0, 0.25, step=0.05
            )
            default_memory_gi = defaults[1].number_input(
                "Default memory per pod (GiB)",
                0.01,
                1024.0,
                0.25,
                step=0.05,
                help="0.25 GiB equals 256 MiB.",
            )
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
                    int(default_cpu_cores * 1000),
                    int(default_memory_gi * 1024),
                    _parse_labels(labels_text),
                )
                _store_state(username, state)
                st.rerun()
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
        st.dataframe(pd.DataFrame(namespace_rows(state)), width="stretch", hide_index=True)
        for namespace_name, policy in state["namespaces"].items():
            with st.expander(f"Adjust {namespace_name}"):
                with st.form(f"edit_namespace_{namespace_name}"):
                    identity = st.columns(2)
                    edit_owner = identity[0].text_input(
                        "Owner / team",
                        value=policy.get("owner", "Platform Team"),
                        key=f"owner_{namespace_name}",
                    )
                    environments = [
                        "Development",
                        "Testing",
                        "Staging",
                        "Production",
                        "Shared",
                        "System",
                    ]
                    current_environment = policy.get("environment", "Shared")
                    edit_environment = identity[1].selectbox(
                        "Environment",
                        environments,
                        index=(
                            environments.index(current_environment)
                            if current_environment in environments
                            else environments.index("Shared")
                        ),
                        key=f"environment_{namespace_name}",
                    )
                    quotas = st.columns(4)
                    edit_cpu = quotas[0].number_input(
                        "CPU quota (cores)",
                        min_value=0.1,
                        value=policy["cpu_quota_m"] / 1000,
                        step=0.1,
                        key=f"cpu_quota_{namespace_name}",
                    )
                    edit_memory = quotas[1].number_input(
                        "Memory quota (GiB)",
                        min_value=0.1,
                        value=policy["memory_quota_mi"] / 1024,
                        step=0.1,
                        key=f"memory_quota_{namespace_name}",
                    )
                    edit_storage = quotas[2].number_input(
                        "Storage quota (GiB)",
                        min_value=1,
                        value=policy["storage_quota_gi"],
                        key=f"storage_quota_{namespace_name}",
                    )
                    edit_pods = quotas[3].number_input(
                        "Maximum pods",
                        min_value=1,
                        value=policy["pod_quota"],
                        key=f"pod_quota_{namespace_name}",
                    )
                    defaults = st.columns(3)
                    edit_default_cpu = defaults[0].number_input(
                        "Default CPU per pod (cores)",
                        min_value=0.01,
                        value=policy["default_cpu_m"] / 1000,
                        step=0.05,
                        key=f"default_cpu_{namespace_name}",
                    )
                    edit_default_memory = defaults[1].number_input(
                        "Default memory per pod (GiB)",
                        min_value=0.01,
                        value=policy["default_memory_mi"] / 1024,
                        step=0.05,
                        key=f"default_memory_{namespace_name}",
                    )
                    edit_labels = defaults[2].text_input(
                        "Labels",
                        value=",".join(
                            f"{key}={value}"
                            for key, value in policy.get("labels", {}).items()
                        ),
                        key=f"labels_{namespace_name}",
                    )
                    save_namespace = st.form_submit_button("Save Changes")
                if save_namespace:
                    try:
                        update_namespace(
                            state,
                            namespace_name,
                            edit_owner,
                            edit_environment,
                            int(edit_cpu * 1000),
                            int(edit_memory * 1024),
                            edit_storage,
                            edit_pods,
                            int(edit_default_cpu * 1000),
                            int(edit_default_memory * 1024),
                            _parse_labels(edit_labels),
                        )
                        _store_state(username, state)
                        st.rerun()
                    except (ValueError, TypeError) as exc:
                        st.error(str(exc))

    with workload_tab:
        st.caption(
            "Deployment keeps the requested number of pods running. "
            "Service gives those pods a stable network name and port."
        )
        namespaces = sorted(state["namespaces"])
        with st.form("namespace_workload_form"):
            first = st.columns(4)
            namespace = first[0].selectbox("Namespace", namespaces)
            workload_name = first[1].text_input("Workload name", value="data-api")
            image = first[2].text_input("Container image", value="example/data-api:1.0")
            kind = first[3].selectbox("Controller", ["Deployment", "StatefulSet"])
            second = st.columns(3)
            replicas = second[0].number_input("Pods / replicas", 0, 5000, 3)
            cpu_cores = second[1].number_input(
                "CPU per pod (cores)", 0.01, 128.0, 0.25, step=0.05
            )
            memory_gi = second[2].number_input(
                "Memory per pod (GiB)", 0.01, 1024.0, 0.25, step=0.05
            )
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
                    int(cpu_cores * 1000),
                    int(memory_gi * 1024),
                    kind,
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


RESOURCE_PROFILES = {
    "Standard — 1 CPU / 2 GiB": (1, 2),
    "Lightweight — 1 CPU / 1 GiB": (1, 1),
    "Database — 2 CPU / 4 GiB": (2, 4),
    "Streaming — 2 CPU / 4 GiB": (2, 4),
    "Analytics / Compute — 4 CPU / 8 GiB": (4, 8),
}


def _profile_capacity(profile, custom_cpu, custom_memory):
    if profile == "Custom":
        return int(custom_cpu), int(custom_memory)
    return RESOURCE_PROFILES[profile]


def _render_resource_management_unlimited(username, state):
    namespace_tab, workload_tab = st.tabs(["Namespaces", "Deployments & Services"])
    with namespace_tab:
        with st.form("simple_namespace_form"):
            identity = st.columns(3)
            name = identity[0].text_input("Namespace name", placeholder="development")
            owner = identity[1].text_input("Owner / team", value="Data Platform")
            labels_text = identity[2].text_input(
                "Labels",
                value="team=data-platform",
                help="Optional comma-separated key=value labels.",
            )
            create_namespace_clicked = st.form_submit_button(
                "Create Namespace",
                type="primary",
            )
        if create_namespace_clicked:
            try:
                create_namespace(
                    state,
                    name,
                    owner=owner,
                    labels=_parse_labels(labels_text),
                )
                _store_state(username, state)
                st.rerun()
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
        st.dataframe(
            pd.DataFrame(namespace_rows(state)),
            width="stretch",
            hide_index=True,
        )

    with workload_tab:
        namespaces = sorted(state["namespaces"])
        st.caption(
            "Pod runs one container. Deployment keeps replicated pods running. "
            "Service gives a pod or deployment a stable network endpoint."
        )
        pod_tab, deployment_tab, service_tab, platform_tab = st.tabs(
            ["Create Pod", "Create Deployment", "Create Service", "Data Platform"]
        )
        with pod_tab:
            with st.form("simple_pod_form"):
                fields = st.columns(3)
                pod_namespace = fields[0].selectbox("Namespace", namespaces)
                pod_name = fields[1].text_input(
                    "Pod name",
                    placeholder="postgresql-utility",
                )
                pod_image = fields[2].text_input(
                    "Container image",
                    placeholder="postgres:latest",
                )
                with st.expander("Advanced resources (optional)"):
                    advanced = st.columns(2)
                    pod_cpu = advanced[0].number_input(
                        "CPU request (cores)",
                        min_value=0.05,
                        value=0.25,
                        step=0.05,
                    )
                    pod_memory = advanced[1].number_input(
                        "Memory request (GiB)",
                        min_value=0.05,
                        value=0.25,
                        step=0.05,
                    )
                create_pod_clicked = st.form_submit_button(
                    "Create Pod",
                    type="primary",
                )
            if create_pod_clicked:
                try:
                    create_pod(
                        state,
                        pod_name,
                        pod_image,
                        pod_namespace,
                        int(pod_cpu * 1000),
                        int(pod_memory * 1024),
                    )
                    _store_state(username, state)
                    st.rerun()
                except (ValueError, TypeError) as exc:
                    st.error(str(exc))

        with deployment_tab:
            with st.form("simple_deployment_form"):
                fields = st.columns(5)
                deployment_namespace = fields[0].selectbox(
                    "Namespace",
                    namespaces,
                    key="deployment_namespace",
                )
                deployment_name = fields[1].text_input(
                    "Deployment name",
                    placeholder="flink-worker",
                )
                deployment_image = fields[2].text_input(
                    "Container image",
                    placeholder="apache/flink:latest",
                )
                deployment_kind = fields[3].selectbox(
                    "Controller",
                    ["Deployment", "StatefulSet"],
                )
                deployment_replicas = fields[4].number_input(
                    "Replicas",
                    min_value=0,
                    max_value=100000,
                    value=1,
                )
                with st.expander("Advanced resources (optional)"):
                    advanced = st.columns(2)
                    deployment_cpu = advanced[0].number_input(
                        "CPU per pod (cores)",
                        min_value=0.05,
                        value=0.5,
                        step=0.05,
                    )
                    deployment_memory = advanced[1].number_input(
                        "Memory per pod (GiB)",
                        min_value=0.05,
                        value=0.5,
                        step=0.05,
                    )
                create_deployment_clicked = st.form_submit_button(
                    "Create Deployment",
                    type="primary",
                )
            if create_deployment_clicked:
                try:
                    create_deployment(
                        state,
                        deployment_name,
                        deployment_image,
                        deployment_replicas,
                        deployment_namespace,
                        int(deployment_cpu * 1000),
                        int(deployment_memory * 1024),
                        deployment_kind,
                    )
                    _store_state(username, state)
                    st.rerun()
                except (ValueError, TypeError) as exc:
                    st.error(str(exc))

        with service_tab:
            targets = [
                {
                    "namespace": item["namespace"],
                    "name": item["name"],
                    "label": f"Deployment · {item['namespace']}/{item['name']}",
                }
                for item in state["deployments"].values()
            ]
            targets.extend(
                {
                    "namespace": item["namespace"],
                    "name": item["name"],
                    "label": f"Pod · {item['namespace']}/{item['name']}",
                }
                for item in state["pods"].values()
                if not item.get("owner")
            )
            if not targets:
                st.info("Create a pod or deployment before creating a service.")
            else:
                with st.form("simple_service_form"):
                    fields = st.columns(5)
                    target = fields[0].selectbox(
                        "Target",
                        targets,
                        format_func=lambda item: item["label"],
                    )
                    service_name = fields[1].text_input(
                        "Service name",
                        placeholder="flink-web",
                    )
                    service_port = fields[2].number_input(
                        "Service port",
                        1,
                        65535,
                        80,
                    )
                    container_port = fields[3].number_input(
                        "Container port",
                        1,
                        65535,
                        8080,
                    )
                    service_type = fields[4].selectbox(
                        "Service type",
                        ["ClusterIP", "NodePort", "LoadBalancer"],
                    )
                    create_service_clicked = st.form_submit_button(
                        "Create Service",
                        type="primary",
                    )
                if create_service_clicked:
                    try:
                        create_service(
                            state,
                            service_name,
                            target["name"],
                            service_port,
                            container_port,
                            service_type,
                            target["namespace"],
                        )
                        _store_state(username, state)
                        st.rerun()
                    except (ValueError, TypeError) as exc:
                        st.error(str(exc))

        with platform_tab:
            plan = st.session_state.get(
                f"k8s_capacity_plan::{username}",
                calculate_capacity(
                    provider=state["cluster"].get("provider", "On-Premises"),
                    **profile_inputs("Development"),
                ),
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Component": item["component"],
                            "Replicas": item["replicas"],
                            "CPU each": f"{item['cpu_each']} cores",
                            "Memory each": f"{item['memory_each_gib']} GiB",
                            "Ports": item["ports"],
                        }
                        for item in plan["components"]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            with st.form("data_platform_blueprint_form"):
                selected_components = st.multiselect(
                    "Components",
                    ["PostgreSQL", "Flink", "StarRocks", "Superset"],
                    default=["PostgreSQL", "Flink", "StarRocks", "Superset"],
                )
                use_plan = st.checkbox(
                    "Use Capacity Planner recommendations",
                    value=True,
                )
                blueprint = st.columns(5)
                blueprint_namespace = blueprint[0].selectbox(
                    "Namespace",
                    namespaces,
                    key="blueprint_namespace",
                )
                postgres_replicas = blueprint[1].number_input(
                    "PostgreSQL pods",
                    min_value=1,
                    value=2,
                )
                flink_taskmanagers = blueprint[2].number_input(
                    "Flink TaskManagers",
                    min_value=1,
                    value=3,
                )
                starrocks_compute = blueprint[3].number_input(
                    "StarRocks compute nodes",
                    min_value=3,
                    max_value=1000,
                    value=3,
                )
                superset_replicas = blueprint[4].number_input(
                    "Superset pods",
                    min_value=1,
                    value=2,
                )
                deploy_blueprint = st.form_submit_button(
                    "Deploy PostgreSQL + Flink + StarRocks + Superset",
                    type="primary",
                )
            if deploy_blueprint:
                try:
                    if not selected_components:
                        raise ValueError("select at least one component")
                    recommendations = {
                        item["component"]: item for item in plan["components"]
                    }
                    if use_plan:
                        postgres_replicas = recommendations["PostgreSQL"]["replicas"]
                        flink_taskmanagers = recommendations["Flink TaskManager"]["replicas"]
                        starrocks_compute = recommendations["StarRocks CN"]["replicas"]
                        superset_replicas = recommendations["Superset"]["replicas"]
                    resource_names = {
                        "PostgreSQL": "postgresql",
                        "Flink Operator": "flink-operator",
                        "Flink JobManager": "flink-jobmanager",
                        "Flink TaskManager": "flink-taskmanager",
                        "StarRocks FE": "starrocks-fe",
                        "StarRocks CN": "starrocks-cn",
                        "Superset": "superset",
                    }
                    component_resources = {
                        resource_names[name]: (
                            item["cpu_each"],
                            item["memory_each_gib"],
                        )
                        for name, item in recommendations.items()
                    }
                    new_state = deploy_data_platform_blueprint(
                        state,
                        blueprint_namespace,
                            postgres_replicas=postgres_replicas,
                            flink_taskmanagers=flink_taskmanagers,
                            starrocks_compute_nodes=starrocks_compute,
                            superset_replicas=superset_replicas,
                            flink_operator_replicas=recommendations[
                                "Flink Operator"
                            ]["replicas"],
                            flink_jobmanagers=recommendations[
                                "Flink JobManager"
                            ]["replicas"],
                            starrocks_frontends=recommendations[
                                "StarRocks FE"
                            ]["replicas"],
                            component_resources=component_resources,
                            components=selected_components,
                    )
                    _store_state(username, new_state)
                    st.rerun()
                except (ValueError, TypeError) as exc:
                    st.error(str(exc))
            result = state.get("last_blueprint_result")
            if result:
                st.success(
                    f"Created {len(result['created'])}, updated "
                    f"{len(result['updated'])}, unchanged "
                    f"{len(result['unchanged'])} resources."
                )

        st.markdown("##### Current resources")
        inspect_pods, inspect_deployments, inspect_services = st.tabs(
            ["Pods", "Deployments", "Services"]
        )
        with inspect_pods:
            st.dataframe(
                pd.DataFrame(pod_rows(state)),
                width="stretch",
                hide_index=True,
            )
        with inspect_deployments:
            st.dataframe(
                pd.DataFrame(deployment_rows(state)),
                width="stretch",
                hide_index=True,
            )
        with inspect_services:
            st.dataframe(
                pd.DataFrame(service_rows(state)),
                width="stretch",
                hide_index=True,
            )


def _terminal_prompt(state, context=None):
    context = context or state["terminal_context"]
    if context["mode"] == "pod":
        return f"{context['namespace']}/{context['pod']}:{context.get('cwd', '/app')}$"
    return f"{state['cluster']['name']}:{context['namespace']}$"


def _terminal_run(state, command, context=None):
    context = context or state["terminal_context"]
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


def _terminal_input_script(shell_key, history):
    _TERMINAL_INPUT_BEHAVIOR(
        key=f"terminal_input_behavior::{shell_key}",
        data={"shellKey": shell_key, "history": history[-100:]},
        height=0,
    )


def _submit_terminal_command(
    username,
    state,
    input_key,
    buffer_key,
    commands_key,
    context=None,
):
    command = st.session_state.get(input_key, "").strip()
    if not command:
        return
    current_prompt = _terminal_prompt(state, context)
    new_state, output, clear_requested = _terminal_run(state, command, context)
    if clear_requested:
        st.session_state[buffer_key] = []
    else:
        st.session_state[buffer_key].append(
            f"{current_prompt}{command}\n{output}".rstrip()
        )
    st.session_state[commands_key].append(command)
    st.session_state[input_key] = ""
    _store_state(username, new_state)


def _terminal_transcript_html(transcript):
    rendered = []
    success_words = (
        " created",
        " configured",
        " deployed",
        " scaled",
        " deleted",
        " restarted",
        " updated",
        " successfully",
    )
    for line in transcript.splitlines():
        escaped = html.escape(line)
        lowered = line.lower()
        if "$" in line:
            prompt, command = line.split("$", 1)
            rendered.append(
                '<span class="term-line"><span class="term-prompt">'
                f"{html.escape(prompt)}$</span>"
                f'<span class="term-command">{html.escape(command)}</span></span>'
            )
        elif lowered.startswith(("error:", "error ", "failed", "fatal")):
            rendered.append(f'<span class="term-line term-error">{escaped}</span>')
        elif lowered.startswith(("warning", "warn:")) or " pending" in lowered:
            rendered.append(f'<span class="term-line term-warning">{escaped}</span>')
        elif any(word in lowered for word in success_words):
            rendered.append(f'<span class="term-line term-success">{escaped}</span>')
        elif line.startswith(
            ("NAME ", "NAMESPACE ", "TYPE ", "LAST SEEN ", "REVISION ")
        ):
            rendered.append(f'<span class="term-line term-header">{escaped}</span>')
        else:
            rendered.append(f'<span class="term-line term-output">{escaped}</span>')
    return "".join(rendered)


def _render_unified_terminal(username, state, terminal_id="main"):
    suffix = f"{username}::{terminal_id}"
    context_key = f"k8s_terminal_context::{suffix}"
    st.session_state.setdefault(
        context_key,
        {
            "mode": "cluster",
            "namespace": "default",
            "pod": None,
            "cwd": "/app",
        },
    )
    context = st.session_state[context_key]
    prompt = _terminal_prompt(state, context)
    buffer_key = f"k8s_terminal_buffer::{suffix}"
    commands_key = f"k8s_terminal_commands::{suffix}"
    input_key = f"k8s_terminal_input::{suffix}"
    st.session_state.setdefault(buffer_key, [])
    st.session_state.setdefault(commands_key, [])
    transcript = "\n".join(st.session_state[buffer_key][-80:])
    st.markdown(
        """
        <style>
        div[class*="st-key-k8s_terminal_bridge"] {display:none !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="k8s_terminal_bridge"):
        st.text_input(
            "Terminal bridge",
            key=input_key,
            label_visibility="collapsed",
        )
        st.button(
            "Send terminal command",
            key=f"k8s_terminal_send::{suffix}",
            on_click=_submit_terminal_command,
            args=(username, state, input_key, buffer_key, commands_key, context),
        )
    prompt_json = json.dumps(prompt).replace("<", "\\u003c")
    history_json = json.dumps(st.session_state[commands_key][-100:]).replace(
        "<", "\\u003c"
    )
    st.iframe(
        f"""
        <!doctype html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            * {{box-sizing:border-box}}
            html,body {{margin:0;width:100%;height:100%;background:#05080c;color:#d9f7df}}
            body {{font:14px/1.5 SFMono-Regular,Menlo,Monaco,Consolas,monospace}}
            #terminal {{height:100%;display:flex;flex-direction:column;border:1px solid #263445;border-radius:8px;overflow:hidden}}
            #toolbar {{height:34px;display:flex;align-items:center;justify-content:space-between;padding:0 10px;background:#111720;border-bottom:1px solid #263445}}
            #dots {{display:flex;gap:6px}} #dots i {{width:10px;height:10px;border-radius:50%;display:block}}
            #dots i:nth-child(1){{background:#ff5f57}} #dots i:nth-child(2){{background:#febc2e}} #dots i:nth-child(3){{background:#28c840}}
            #title {{color:#94a4b8;font-size:12px}}
            #expand {{border:0;background:transparent;color:#b8c5d6;font-size:17px;cursor:pointer}}
            #screen {{flex:1;overflow:auto;padding:12px;cursor:text}}
            #scrollback {{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;color:#d9f7df}}
            #prompt-row {{display:flex;align-items:center;gap:8px;min-height:25px}}
            #prompt {{color:#6fe58d;white-space:nowrap;font-weight:600}}
            #command {{flex:1;border:0;outline:0;background:transparent;color:#f2f7fb;font:inherit;caret-color:#65ff8d;padding:0}}
            #status {{color:#7d8da3;font-size:11px;padding:0 12px 8px}}
            :fullscreen #terminal {{border-radius:0;border:0}} :fullscreen body {{padding:0}}
          </style>
        </head>
        <body>
          <div id="terminal">
            <div id="toolbar">
              <span id="dots"><i></i><i></i><i></i></span>
              <span id="title">Kubernetes Simulator Terminal</span>
              <button id="expand" title="Fullscreen">⛶</button>
            </div>
            <div id="screen">
              <pre id="scrollback">{html.escape(transcript)}</pre>
              <div id="prompt-row">
                <span id="prompt"></span>
                <input id="command" autocomplete="off" autocapitalize="off" spellcheck="false" autofocus>
              </div>
            </div>
            <div id="status">Enter: execute · ↑/↓: command history · kubectl exec -it POD -- sh: pod shell</div>
          </div>
          <script>
            const promptText = {prompt_json};
            const history = {history_json};
            const prompt = document.getElementById("prompt");
            const command = document.getElementById("command");
            const screen = document.getElementById("screen");
            prompt.textContent = promptText;
            let historyIndex = history.length;
            const setBridgeValue = (value) => {{
              const root = window.parent.document.querySelector('[class*="st-key-k8s_terminal_bridge"]');
              const bridge = root && root.querySelector('input');
              const send = root && root.querySelector('button');
              if (!bridge || !send) return false;
              const setter = Object.getOwnPropertyDescriptor(
                window.parent.HTMLInputElement.prototype, "value"
              ).set;
              setter.call(bridge, value);
              bridge.dispatchEvent(new window.parent.Event("input", {{bubbles:true}}));
              bridge.dispatchEvent(new window.parent.Event("change", {{bubbles:true}}));
              setTimeout(() => send.click(), 80);
              return true;
            }};
            command.addEventListener("keydown", (event) => {{
              if (event.key === "Enter") {{
                event.preventDefault();
                const value = command.value.trim();
                if (!value) return;
                command.disabled = true;
                if (!setBridgeValue(value)) {{
                  command.disabled = false;
                  document.getElementById("status").textContent = "Terminal bridge unavailable. Refresh once.";
                }}
              }} else if (event.key === "ArrowUp" && history.length) {{
                event.preventDefault();
                historyIndex = Math.max(0, historyIndex - 1);
                command.value = history[historyIndex];
                command.setSelectionRange(command.value.length, command.value.length);
              }} else if (event.key === "ArrowDown" && history.length) {{
                event.preventDefault();
                historyIndex = Math.min(history.length, historyIndex + 1);
                command.value = historyIndex === history.length ? "" : history[historyIndex];
              }}
            }});
            document.getElementById("terminal").addEventListener("click", () => command.focus());
            document.getElementById("expand").addEventListener("click", async () => {{
              if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
              else await document.exitFullscreen();
              command.focus();
            }});
            screen.scrollTop = screen.scrollHeight;
            command.focus();
          </script>
        </body>
        </html>
        """,
        height=640,
    )


def _render_reliable_terminal(username, state, terminal_id, title):
    suffix = f"{username}::{terminal_id}"
    context_key = f"k8s_terminal_context::{suffix}"
    buffer_key = f"k8s_terminal_buffer::{suffix}"
    commands_key = f"k8s_terminal_commands::{suffix}"
    input_key = f"k8s_terminal_input::{suffix}"
    st.session_state.setdefault(
        context_key,
        {
            "mode": "cluster",
            "namespace": "default",
            "pod": None,
            "cwd": "/app",
        },
    )
    st.session_state.setdefault(buffer_key, [])
    st.session_state.setdefault(commands_key, [])
    context = st.session_state[context_key]
    prompt = _terminal_prompt(state, context)
    transcript = "\n".join(st.session_state[buffer_key][-100:])
    shell_key = f"k8s_terminal_shell_{terminal_id}"
    st.html(
        f"""
        <style>
        div[class*="st-key-{shell_key}"] {{
          height: min(72vh, 720px);
          min-height: 560px;
          padding: 0 !important;
          overflow-x: hidden !important;
          overflow-y: auto !important;
          border: 1px solid #263445;
          border-radius: 8px;
          background: #05080c;
        }}
        div[class*="st-key-{shell_key}"] > div[data-testid="stVerticalBlock"] {{
          gap: 0 !important;
        }}
        div[class*="st-key-{shell_key}"] div[data-testid="stTextInput"] {{
          display: flex;
          align-items: center;
          gap: 0;
          margin: 0 12px 8px;
        }}
        div[class*="st-key-{shell_key}"] div[data-testid="stTextInput"] > div {{
          flex: 1 1 auto;
        }}
        div[class*="st-key-{shell_key}"] div[data-baseweb="input"],
        div[class*="st-key-{shell_key}"] div[data-baseweb="base-input"],
        div[class*="st-key-{shell_key}"] .react-aria-TextField,
        div[class*="st-key-{shell_key}"] div[data-testid="stTextInputRootElement"] {{
          border: 0 !important;
          background: transparent !important;
          box-shadow: none !important;
          outline: 0 !important;
        }}
        div[class*="st-key-{shell_key}"] div[data-testid="stTextInput"] input {{
          border: 0 !important;
          background: transparent !important;
          color: #67d8ff !important;
          caret-color: #65ff8d !important;
          font: 14px/1.5 SFMono-Regular, Menlo, Monaco, Consolas, monospace;
          box-shadow: none !important;
          margin: 0 !important;
          padding: 0 !important;
        }}
        div[class*="st-key-{shell_key}"] div[data-testid="stTextInput"] label {{
          flex: 0 0 auto;
          margin: 0 !important;
          padding: 0 !important;
          color: #6fe58d !important;
          font: 600 14px/1.5 SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }}
        div[class*="st-key-{shell_key}"] div[data-testid="stTextInput"] label p {{
          color: #6fe58d !important;
          font: inherit !important;
        }}
        div[class*="st-key-{shell_key}"] div[data-testid="InputInstructions"] {{
          display: none !important;
        }}
        div[class*="st-key-{shell_key}"] .term-line {{
          display: block;
          min-height: 1.5em;
        }}
        div[class*="st-key-{shell_key}"] .term-prompt,
        div[class*="st-key-{shell_key}"] .term-success {{
          color: #6fe58d;
        }}
        div[class*="st-key-{shell_key}"] .term-command,
        div[class*="st-key-{shell_key}"] .term-header {{
          color: #67d8ff;
        }}
        div[class*="st-key-{shell_key}"] .term-warning {{
          color: #ffd166;
        }}
        div[class*="st-key-{shell_key}"] .term-error {{
          color: #ff6b6b;
        }}
        div[class*="st-key-{shell_key}"] .term-output {{
          color: #d9f7df;
        }}
        </style>
        """
    )
    scrollback_padding = "12px 12px 0" if transcript else "0"
    with st.container(key=shell_key, border=False):
        st.html(
            f"""
            <div style="height:34px;display:flex;align-items:center;
              justify-content:space-between;padding:0 10px;background:#111720;
              border-bottom:1px solid #263445;font-family:SFMono-Regular,Menlo,
              Monaco,Consolas,monospace">
              <span style="display:flex;gap:6px">
                <i style="width:10px;height:10px;border-radius:50%;background:#ff5f57"></i>
                <i style="width:10px;height:10px;border-radius:50%;background:#febc2e"></i>
                <i style="width:10px;height:10px;border-radius:50%;background:#28c840"></i>
              </span>
              <span style="color:#94a4b8;font-size:12px">{html.escape(title)}</span>
              <span style="width:44px"></span>
            </div>
            <pre class="k8s-terminal-scrollback" style="min-height:0;margin:0;
              padding:{scrollback_padding};
              overflow:visible;background:#05080c;
              color:#d9f7df;white-space:pre-wrap;overflow-wrap:anywhere;
              font:14px/1.5 SFMono-Regular,Menlo,Monaco,Consolas,monospace"
              >{_terminal_transcript_html(transcript)}</pre>
            """
        )
        st.text_input(
            prompt,
            key=input_key,
            placeholder="",
            on_change=_submit_terminal_command,
            args=(
                username,
                state,
                input_key,
                buffer_key,
                commands_key,
                context,
            ),
        )
        _terminal_input_script(shell_key, st.session_state[commands_key])


def _terminal_sessions_key(username):
    return f"k8s_terminal_sessions::{username}"


def _active_terminal_key(username):
    return f"k8s_active_terminal::{username}"


def _ensure_terminal_sessions(username):
    sessions_key = _terminal_sessions_key(username)
    if not st.session_state.get(sessions_key):
        terminal_id = uuid.uuid4().hex[:8]
        st.session_state[sessions_key] = [
            {"id": terminal_id, "title": "Terminal 1"}
        ]
        st.session_state[_active_terminal_key(username)] = terminal_id
    return st.session_state[sessions_key]


def _add_terminal(username):
    sessions = _ensure_terminal_sessions(username)
    terminal_id = uuid.uuid4().hex[:8]
    sessions.append(
        {"id": terminal_id, "title": f"Terminal {len(sessions) + 1}"}
    )
    st.session_state[_active_terminal_key(username)] = terminal_id


def _close_terminal(username):
    sessions = _ensure_terminal_sessions(username)
    active_key = _active_terminal_key(username)
    active = st.session_state.get(active_key)
    if len(sessions) == 1:
        return
    st.session_state[_terminal_sessions_key(username)] = [
        item for item in sessions if item["id"] != active
    ]
    st.session_state[active_key] = st.session_state[
        _terminal_sessions_key(username)
    ][-1]["id"]


@st.fragment
def _render_multi_terminal_workspace(username):
    state = st.session_state.get(_state_key(username))
    if not state:
        st.info("Create the virtual cluster before opening terminals.")
        return
    sessions = _ensure_terminal_sessions(username)
    controls = st.columns([5, 1, 1])
    with controls[1]:
        st.button(
            "＋ Terminal",
            key=f"add_terminal::{username}",
            on_click=_add_terminal,
            args=(username,),
            width="stretch",
        )
    with controls[2]:
        st.button(
            "Close",
            key=f"close_terminal::{username}",
            on_click=_close_terminal,
            args=(username,),
            disabled=len(sessions) == 1,
            width="stretch",
        )
    sessions = _ensure_terminal_sessions(username)
    active_key = _active_terminal_key(username)
    valid_ids = [item["id"] for item in sessions]
    if st.session_state.get(active_key) not in valid_ids:
        st.session_state[active_key] = valid_ids[0]
    title_by_id = {item["id"]: item["title"] for item in sessions}
    with controls[0]:
        active_terminal = st.segmented_control(
            "Open terminals",
            valid_ids,
            format_func=lambda terminal_id: title_by_id[terminal_id],
            key=active_key,
            label_visibility="collapsed",
        )
    active_terminal = active_terminal or valid_ids[0]
    _render_reliable_terminal(
        username,
        state,
        active_terminal,
        title_by_id[active_terminal],
    )


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
            "Capacity Planning",
            "Namespaces & Resources",
            "Terminal",
            "YAML Apply",
        ]
    )
    with tabs[0]:
        _render_cluster_monitor(state)
    with tabs[1]:
        _render_capacity_planner(username, state)
    with tabs[2]:
        _render_resource_management_unlimited(username, state)
    with tabs[3]:
        _render_multi_terminal_workspace(username)
    with tabs[4]:
        _render_yaml_apply(username, state)
