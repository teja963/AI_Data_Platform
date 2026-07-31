import copy
import json
import shlex
import uuid
from datetime import datetime, timezone

import yaml


SIMULATOR_VERSION = 1
DEFAULT_NAMESPACE = "default"
PROVIDER_REGIONS = {
    "AWS (EKS)": "us-east-1",
    "Google Cloud (GKE)": "us-central1",
    "Azure (AKS)": "eastus",
    "On-Premises": "local-datacenter",
}
CLUSTER_PRESETS = {
    "Small": {"workers": 2, "cpu": 2, "memory": 4096, "storage": 40},
    "Medium": {"workers": 4, "cpu": 4, "memory": 8192, "storage": 80},
    "Large": {"workers": 8, "cpu": 8, "memory": 16384, "storage": 160},
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _token():
    return uuid.uuid4().hex[:5]


def _event(state, reason, message, kind="Normal", obj="cluster"):
    state.setdefault("events", []).append(
        {
            "time": _now(),
            "type": kind,
            "reason": reason,
            "object": obj,
            "message": message,
        }
    )
    state["events"] = state["events"][-200:]


def _node_template(name, role, cpu, memory, storage):
    return {
        "name": name,
        "role": role,
        "status": "Ready",
        "schedulable": role == "worker",
        "cpu_capacity_m": int(cpu) * 1000,
        "memory_capacity_mi": int(memory),
        "storage_gi": int(storage),
        "labels": {
            "kubernetes.io/hostname": name,
            "node-role.kubernetes.io/control-plane" if role == "control-plane" else "node-role.kubernetes.io/worker": "",
        },
        "created_at": _now(),
    }


def create_cluster(
    name,
    provider,
    region,
    worker_count,
    cpu_per_worker,
    memory_per_worker_mi,
    storage_per_worker_gi,
    control_planes=1,
    kubernetes_version="1.33",
):
    name = (name or "learning-cluster").strip().lower().replace(" ", "-")
    state = {
        "simulator_version": SIMULATOR_VERSION,
        "cluster": {
            "name": name,
            "provider": provider,
            "region": region,
            "version": kubernetes_version,
            "status": "Running",
            "control_planes": int(control_planes),
            "created_at": _now(),
        },
        "nodes": [],
        "namespaces": {
            "default": {"name": "default", "status": "Active", "created_at": _now()},
            "kube-system": {"name": "kube-system", "status": "Active", "created_at": _now()},
        },
        "deployments": {},
        "pods": {},
        "services": {},
        "helm_releases": {},
        "events": [],
        "history": [],
        "counters": {"pod": 0, "service_ip": 10},
    }
    for index in range(int(control_planes)):
        state["nodes"].append(
            _node_template(
                f"{name}-control-{index + 1}",
                "control-plane",
                max(2, int(cpu_per_worker)),
                max(2048, int(memory_per_worker_mi)),
                max(20, int(storage_per_worker_gi)),
            )
        )
    for index in range(int(worker_count)):
        state["nodes"].append(
            _node_template(
                f"{name}-worker-{index + 1}",
                "worker",
                cpu_per_worker,
                memory_per_worker_mi,
                storage_per_worker_gi,
            )
        )
    _event(
        state,
        "ClusterCreated",
        f"Virtual {provider} cluster {name} created with {worker_count} worker nodes.",
    )
    return state


def clone_state(state):
    return copy.deepcopy(state)


def _key(namespace, name):
    return f"{namespace}/{name}"


def _namespace(state, requested):
    return requested if requested in state["namespaces"] else DEFAULT_NAMESPACE


def _node_usage(state, node_name):
    pods = [
        pod
        for pod in state["pods"].values()
        if pod.get("node") == node_name and pod.get("status") in {"Running", "Pending", "Unknown"}
    ]
    return {
        "cpu_m": sum(int(pod.get("cpu_request_m", 0)) for pod in pods),
        "memory_mi": sum(int(pod.get("memory_request_mi", 0)) for pod in pods),
        "pods": len(pods),
    }


def node_rows(state):
    rows = []
    for node in state["nodes"]:
        usage = _node_usage(state, node["name"])
        rows.append(
            {
                "Name": node["name"],
                "Role": node["role"],
                "Status": node["status"],
                "Scheduling": "Enabled" if node["schedulable"] else "Disabled",
                "CPU": f"{usage['cpu_m']}m / {node['cpu_capacity_m']}m",
                "Memory": f"{usage['memory_mi']}Mi / {node['memory_capacity_mi']}Mi",
                "Pods": usage["pods"],
            }
        )
    return rows


def pod_rows(state, namespace=None):
    rows = []
    for pod in state["pods"].values():
        if namespace and pod["namespace"] != namespace:
            continue
        rows.append(
            {
                "Namespace": pod["namespace"],
                "Name": pod["name"],
                "Ready": "1/1" if pod["status"] == "Running" else "0/1",
                "Status": pod["status"],
                "Restarts": pod.get("restarts", 0),
                "Node": pod.get("node") or "<none>",
                "Owner": pod.get("owner") or "<none>",
                "CPU": f"{pod.get('cpu_request_m', 0)}m",
                "Memory": f"{pod.get('memory_request_mi', 0)}Mi",
            }
        )
    return sorted(rows, key=lambda item: (item["Namespace"], item["Name"]))


def deployment_rows(state, namespace=None):
    rows = []
    for deployment in state["deployments"].values():
        if namespace and deployment["namespace"] != namespace:
            continue
        owned = [
            pod
            for pod in state["pods"].values()
            if pod.get("owner") == deployment["name"]
            and pod["namespace"] == deployment["namespace"]
        ]
        ready = sum(pod["status"] == "Running" for pod in owned)
        rows.append(
            {
                "Namespace": deployment["namespace"],
                "Name": deployment["name"],
                "Kind": deployment.get("kind", "Deployment"),
                "Ready": f"{ready}/{deployment['replicas']}",
                "Image": deployment["image"],
                "CPU/Pod": f"{deployment['cpu_request_m']}m",
                "Memory/Pod": f"{deployment['memory_request_mi']}Mi",
                "JVM Heap/Pod": (
                    f"{deployment.get('heap_size_mi', 0)}Mi"
                    if deployment.get("heap_size_mi")
                    else "Not set"
                ),
            }
        )
    return sorted(rows, key=lambda item: (item["Namespace"], item["Name"]))


def service_rows(state, namespace=None):
    rows = []
    for service in state["services"].values():
        if namespace and service["namespace"] != namespace:
            continue
        rows.append(
            {
                "Namespace": service["namespace"],
                "Name": service["name"],
                "Type": service["type"],
                "Cluster IP": service["cluster_ip"],
                "Port": f"{service['port']}:{service['target_port']}",
                "Selector": service["selector"],
            }
        )
    return sorted(rows, key=lambda item: (item["Namespace"], item["Name"]))


def _choose_node(state, cpu_request_m, memory_request_mi):
    candidates = []
    for node in state["nodes"]:
        if node["role"] != "worker" or node["status"] != "Ready" or not node["schedulable"]:
            continue
        usage = _node_usage(state, node["name"])
        free_cpu = node["cpu_capacity_m"] - usage["cpu_m"]
        free_memory = node["memory_capacity_mi"] - usage["memory_mi"]
        if free_cpu >= cpu_request_m and free_memory >= memory_request_mi:
            candidates.append((usage["pods"], -free_memory, node["name"]))
    return min(candidates)[2] if candidates else None


def _create_pod(
    state,
    name,
    namespace,
    image,
    owner=None,
    cpu_request_m=250,
    memory_request_mi=256,
    heap_size_mi=0,
):
    pod_name = name
    node_name = _choose_node(state, int(cpu_request_m), int(memory_request_mi))
    status = "Running" if node_name else "Pending"
    pod = {
        "name": pod_name,
        "namespace": namespace,
        "image": image,
        "owner": owner,
        "node": node_name,
        "status": status,
        "restarts": 0,
        "cpu_request_m": int(cpu_request_m),
        "memory_request_mi": int(memory_request_mi),
        "heap_size_mi": int(heap_size_mi),
        "created_at": _now(),
        "logs": [
            f"{_now()} Starting container from image {image}",
            f"{_now()} Application initialized successfully" if node_name else f"{_now()} Waiting for a schedulable node",
        ],
    }
    state["pods"][_key(namespace, pod_name)] = pod
    if node_name:
        _event(state, "Scheduled", f"Assigned {namespace}/{pod_name} to {node_name}.", obj=f"pod/{pod_name}")
    else:
        _event(
            state,
            "FailedScheduling",
            f"No node has enough free CPU and memory for {namespace}/{pod_name}.",
            kind="Warning",
            obj=f"pod/{pod_name}",
        )
    return pod


def _reconcile(state):
    for deployment in list(state["deployments"].values()):
        namespace = deployment["namespace"]
        owned = [
            pod
            for pod in state["pods"].values()
            if pod.get("owner") == deployment["name"] and pod["namespace"] == namespace
        ]
        while len(owned) < int(deployment["replicas"]):
            state["counters"]["pod"] += 1
            pod_name = f"{deployment['name']}-{state['counters']['pod']:04d}-{_token()}"
            pod = _create_pod(
                state,
                pod_name,
                namespace,
                deployment["image"],
                owner=deployment["name"],
                cpu_request_m=deployment["cpu_request_m"],
                memory_request_mi=deployment["memory_request_mi"],
                heap_size_mi=deployment.get("heap_size_mi", 0),
            )
            owned.append(pod)
        while len(owned) > int(deployment["replicas"]):
            pod = owned.pop()
            state["pods"].pop(_key(namespace, pod["name"]), None)
            _event(state, "ScaledDown", f"Removed {pod['name']} during reconciliation.", obj=f"pod/{pod['name']}")

    for pod in state["pods"].values():
        if pod["status"] == "Pending":
            node_name = _choose_node(state, pod["cpu_request_m"], pod["memory_request_mi"])
            if node_name:
                pod["node"] = node_name
                pod["status"] = "Running"
                pod["logs"].append(f"{_now()} Scheduled on {node_name}")
                _event(state, "Scheduled", f"Assigned {pod['namespace']}/{pod['name']} to {node_name}.", obj=f"pod/{pod['name']}")


def create_namespace(state, name):
    name = name.strip().lower()
    if not name:
        raise ValueError("namespace name is required")
    if name in state["namespaces"]:
        raise ValueError(f'namespaces "{name}" already exists')
    state["namespaces"][name] = {"name": name, "status": "Active", "created_at": _now()}
    _event(state, "NamespaceCreated", f"Created namespace {name}.", obj=f"namespace/{name}")
    return state["namespaces"][name]


def create_deployment(
    state,
    name,
    image,
    replicas=1,
    namespace=DEFAULT_NAMESPACE,
    cpu_request_m=250,
    memory_request_mi=256,
    kind="Deployment",
    heap_size_mi=0,
):
    namespace = _namespace(state, namespace)
    key = _key(namespace, name)
    if key in state["deployments"]:
        raise ValueError(f'{kind.lower()}s.apps "{name}" already exists')
    state["deployments"][key] = {
        "name": name,
        "namespace": namespace,
        "kind": kind,
        "image": image,
        "replicas": max(0, int(replicas)),
        "cpu_request_m": max(1, int(cpu_request_m)),
        "memory_request_mi": max(1, int(memory_request_mi)),
        "heap_size_mi": max(0, int(heap_size_mi)),
        "generation": 1,
        "created_at": _now(),
    }
    _event(state, f"{kind}Created", f"Created {kind.lower()} {namespace}/{name}.", obj=f"{kind.lower()}/{name}")
    _reconcile(state)
    return state["deployments"][key]


def scale_deployment(state, name, replicas, namespace=DEFAULT_NAMESPACE):
    deployment = state["deployments"].get(_key(namespace, name))
    if not deployment:
        raise ValueError(f'deployments.apps "{name}" not found')
    deployment["replicas"] = max(0, int(replicas))
    deployment["generation"] += 1
    _event(state, "ScalingReplicaSet", f"Scaled {namespace}/{name} to {replicas} replicas.", obj=f"deployment/{name}")
    _reconcile(state)
    return deployment


def create_service(
    state,
    name,
    selector,
    port,
    target_port,
    service_type="ClusterIP",
    namespace=DEFAULT_NAMESPACE,
):
    namespace = _namespace(state, namespace)
    key = _key(namespace, name)
    if key in state["services"]:
        raise ValueError(f'services "{name}" already exists')
    state["counters"]["service_ip"] += 1
    state["services"][key] = {
        "name": name,
        "namespace": namespace,
        "selector": selector,
        "port": int(port),
        "target_port": int(target_port),
        "type": service_type,
        "cluster_ip": f"10.96.0.{state['counters']['service_ip']}",
        "created_at": _now(),
    }
    _event(state, "ServiceCreated", f"Exposed {selector} through service {name}.", obj=f"service/{name}")
    return state["services"][key]


def add_worker_node(state, cpu, memory, storage):
    cluster_name = state["cluster"]["name"]
    worker_number = 1 + sum(node["role"] == "worker" for node in state["nodes"])
    node = _node_template(f"{cluster_name}-worker-{worker_number}", "worker", cpu, memory, storage)
    state["nodes"].append(node)
    _event(state, "NodeAdded", f"Added virtual worker node {node['name']}.", obj=f"node/{node['name']}")
    _reconcile(state)
    return node


def set_node_status(state, node_name, status):
    node = next((item for item in state["nodes"] if item["name"] == node_name), None)
    if not node:
        raise ValueError(f'nodes "{node_name}" not found')
    node["status"] = status
    if status != "Ready":
        affected = [
            pod
            for pod in list(state["pods"].values())
            if pod.get("node") == node_name
        ]
        for pod in affected:
            state["pods"].pop(_key(pod["namespace"], pod["name"]), None)
            _event(
                state,
                "NodeNotReady",
                f"Evicted {pod['namespace']}/{pod['name']} from unavailable node {node_name}.",
                kind="Warning",
                obj=f"pod/{pod['name']}",
            )
    _event(
        state,
        "NodeStatusChanged",
        f"Node {node_name} is now {status}.",
        kind="Warning" if status != "Ready" else "Normal",
        obj=f"node/{node_name}",
    )
    _reconcile(state)
    return node


def delete_pod(state, name, namespace=DEFAULT_NAMESPACE):
    pod = state["pods"].pop(_key(namespace, name), None)
    if not pod:
        raise ValueError(f'pods "{name}" not found')
    _event(state, "Killing", f"Deleted pod {namespace}/{name}.", obj=f"pod/{name}")
    owner = pod.get("owner")
    _reconcile(state)
    return owner


def restart_pod(state, name, namespace=DEFAULT_NAMESPACE):
    pod = state["pods"].get(_key(namespace, name))
    if not pod:
        raise ValueError(f'pods "{name}" not found')
    pod["restarts"] += 1
    pod["status"] = "Running" if pod.get("node") else "Pending"
    pod["logs"].append(f"{_now()} Container restarted after simulated failure")
    _event(state, "BackOff", f"Container in {name} restarted.", kind="Warning", obj=f"pod/{name}")
    return pod


def _flag(tokens, name, default=None):
    for index, token in enumerate(tokens):
        if token == name and index + 1 < len(tokens):
            return tokens[index + 1]
        if token.startswith(name + "="):
            return token.split("=", 1)[1]
    return default


def _namespace_flag(tokens):
    return _flag(tokens, "--namespace", _flag(tokens, "-n", DEFAULT_NAMESPACE))


def _resource_name(token):
    if "/" in token:
        return token.split("/", 1)
    return None, token


def _format_table(headers, rows):
    if not rows:
        return "No resources found."
    widths = [
        max(len(str(header)), *(len(str(row[index])) for row in rows))
        for index, header in enumerate(headers)
    ]
    lines = ["  ".join(str(value).ljust(widths[index]) for index, value in enumerate(headers))]
    lines.extend(
        "  ".join(str(value).ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    return "\n".join(lines)


def _get_output(state, resource, namespace, all_namespaces=False):
    resource = resource.lower()
    ns = None if all_namespaces else namespace
    if resource in {"node", "nodes", "no"}:
        rows = node_rows(state)
        return _format_table(
            ["NAME", "STATUS", "ROLES", "CPU", "MEMORY"],
            [[row["Name"], row["Status"], row["Role"], row["CPU"], row["Memory"]] for row in rows],
        )
    if resource in {"pod", "pods", "po"}:
        rows = pod_rows(state, ns)
        return _format_table(
            ["NAMESPACE", "NAME", "READY", "STATUS", "RESTARTS", "NODE"],
            [[row["Namespace"], row["Name"], row["Ready"], row["Status"], row["Restarts"], row["Node"]] for row in rows],
        )
    if resource in {"deployment", "deployments", "deploy"}:
        rows = deployment_rows(state, ns)
        return _format_table(
            ["NAMESPACE", "NAME", "READY", "IMAGE"],
            [[row["Namespace"], row["Name"], row["Ready"], row["Image"]] for row in rows],
        )
    if resource in {"service", "services", "svc"}:
        rows = service_rows(state, ns)
        return _format_table(
            ["NAMESPACE", "NAME", "TYPE", "CLUSTER-IP", "PORT"],
            [[row["Namespace"], row["Name"], row["Type"], row["Cluster IP"], row["Port"]] for row in rows],
        )
    if resource in {"namespace", "namespaces", "ns"}:
        return _format_table(
            ["NAME", "STATUS"],
            [[item["name"], item["status"]] for item in state["namespaces"].values()],
        )
    if resource in {"event", "events", "ev"}:
        return _format_table(
            ["TYPE", "REASON", "OBJECT", "MESSAGE"],
            [[event["type"], event["reason"], event["object"], event["message"]] for event in state["events"][-20:]],
        )
    raise ValueError(f'the server does not have a resource type "{resource}"')


def _describe(state, resource, name, namespace):
    resource = resource.lower()
    if resource in {"pod", "pods", "po"}:
        item = state["pods"].get(_key(namespace, name))
    elif resource in {"deployment", "deployments", "deploy"}:
        item = state["deployments"].get(_key(namespace, name))
    elif resource in {"service", "services", "svc"}:
        item = state["services"].get(_key(namespace, name))
    elif resource in {"node", "nodes", "no"}:
        item = next((node for node in state["nodes"] if node["name"] == name), None)
    else:
        item = None
    if not item:
        raise ValueError(f'{resource} "{name}" not found')
    return yaml.safe_dump(item, sort_keys=False)


def _delete_resource(state, resource, name, namespace):
    resource = resource.lower()
    if resource in {"pod", "pods", "po"}:
        owner = delete_pod(state, name, namespace)
        suffix = " (controller created a replacement)" if owner else ""
        return f'pod "{name}" deleted{suffix}'
    if resource in {"deployment", "deployments", "deploy"}:
        deployment = state["deployments"].pop(_key(namespace, name), None)
        if not deployment:
            raise ValueError(f'deployments.apps "{name}" not found')
        for pod_key, pod in list(state["pods"].items()):
            if pod["namespace"] == namespace and pod.get("owner") == name:
                state["pods"].pop(pod_key)
        _event(state, "DeploymentDeleted", f"Deleted deployment {namespace}/{name}.", obj=f"deployment/{name}")
        return f'deployment.apps "{name}" deleted'
    if resource in {"service", "services", "svc"}:
        if not state["services"].pop(_key(namespace, name), None):
            raise ValueError(f'services "{name}" not found')
        _event(state, "ServiceDeleted", f"Deleted service {namespace}/{name}.", obj=f"service/{name}")
        return f'service "{name}" deleted'
    if resource in {"namespace", "namespaces", "ns"}:
        if name in {"default", "kube-system"}:
            raise ValueError(f'namespace "{name}" is protected in this simulator')
        if not state["namespaces"].pop(name, None):
            raise ValueError(f'namespaces "{name}" not found')
        for collection in ("pods", "deployments", "services"):
            for key in list(state[collection]):
                if key.startswith(name + "/"):
                    state[collection].pop(key)
        _event(state, "NamespaceDeleted", f"Deleted namespace {name}.", obj=f"namespace/{name}")
        return f'namespace "{name}" deleted'
    raise ValueError(f'the server does not have a resource type "{resource}"')


def apply_manifest(state, manifest_text, default_namespace=DEFAULT_NAMESPACE):
    if not manifest_text or not manifest_text.strip():
        raise ValueError("paste a YAML manifest before running apply")
    outputs = []
    for document in yaml.safe_load_all(manifest_text):
        if not document:
            continue
        kind = str(document.get("kind", "")).strip()
        metadata = document.get("metadata") or {}
        spec = document.get("spec") or {}
        name = metadata.get("name")
        namespace = metadata.get("namespace", default_namespace)
        if not kind or not name:
            raise ValueError("each YAML document requires kind and metadata.name")
        if kind == "Namespace":
            if name not in state["namespaces"]:
                create_namespace(state, name)
            outputs.append(f'namespace/{name} configured')
        elif kind in {"Deployment", "StatefulSet"}:
            template_spec = ((spec.get("template") or {}).get("spec") or {})
            containers = template_spec.get("containers") or [{}]
            container = containers[0]
            resources = container.get("resources") or {}
            requests = resources.get("requests") or {}
            cpu_text = str(requests.get("cpu", "250m"))
            memory_text = str(requests.get("memory", "256Mi"))
            cpu_m = int(float(cpu_text[:-1])) if cpu_text.endswith("m") else int(float(cpu_text) * 1000)
            memory_mi = int(float(memory_text[:-2])) if memory_text.lower().endswith("mi") else 256
            key = _key(_namespace(state, namespace), name)
            existing = state["deployments"].get(key)
            if existing:
                existing.update(
                    {
                        "replicas": int(spec.get("replicas", 1)),
                        "image": container.get("image", existing["image"]),
                        "cpu_request_m": cpu_m,
                        "memory_request_mi": memory_mi,
                        "kind": kind,
                    }
                )
                existing["generation"] += 1
                _reconcile(state)
            else:
                create_deployment(
                    state,
                    name,
                    container.get("image", "nginx:latest"),
                    spec.get("replicas", 1),
                    namespace,
                    cpu_m,
                    memory_mi,
                    kind,
                )
            outputs.append(f'{kind.lower()}.apps/{name} configured')
        elif kind == "Service":
            ports = spec.get("ports") or [{}]
            port_spec = ports[0]
            key = _key(_namespace(state, namespace), name)
            existing = state["services"].get(key)
            if existing:
                existing.update(
                    {
                        "port": int(port_spec.get("port", 80)),
                        "target_port": int(port_spec.get("targetPort", port_spec.get("port", 80))),
                        "type": spec.get("type", "ClusterIP"),
                    }
                )
            else:
                selectors = spec.get("selector") or {}
                selector = selectors.get("app", next(iter(selectors.values()), name))
                create_service(
                    state,
                    name,
                    selector,
                    port_spec.get("port", 80),
                    port_spec.get("targetPort", port_spec.get("port", 80)),
                    spec.get("type", "ClusterIP"),
                    namespace,
                )
            outputs.append(f'service/{name} configured')
        elif kind == "Pod":
            containers = spec.get("containers") or [{}]
            _create_pod(state, name, _namespace(state, namespace), containers[0].get("image", "nginx:latest"))
            outputs.append(f'pod/{name} created')
        else:
            raise ValueError(f'kind "{kind}" is not supported by the learning simulator')
    return "\n".join(outputs)


def _helm_command(state, tokens):
    if len(tokens) < 2:
        return "Helm simulator supports: install, upgrade, uninstall, list, status"
    action = tokens[1]
    namespace = _namespace_flag(tokens)
    if action == "list":
        releases = [
            release for release in state["helm_releases"].values()
            if release["namespace"] == namespace
        ]
        return _format_table(
            ["NAME", "NAMESPACE", "REVISION", "STATUS", "CHART"],
            [[item["name"], item["namespace"], item["revision"], item["status"], item["chart"]] for item in releases],
        )
    if action in {"install", "upgrade"} and len(tokens) >= 4:
        name, chart = tokens[2], tokens[3]
        replicas = int(_flag(tokens, "--replica-count", _flag(tokens, "--set-replicas", 1)))
        key = _key(namespace, name)
        release = state["helm_releases"].get(key)
        if action == "install" and release:
            raise ValueError(f'cannot re-use a name that is still in use: "{name}"')
        if release:
            release["revision"] += 1
            release["chart"] = chart
            scale_deployment(state, name, replicas, namespace)
            output = f'Release "{name}" has been upgraded'
        else:
            state["helm_releases"][key] = {
                "name": name,
                "namespace": namespace,
                "revision": 1,
                "status": "deployed",
                "chart": chart,
            }
            create_deployment(state, name, f"{chart}:latest", replicas, namespace)
            output = f'NAME: {name}\nSTATUS: deployed\nREVISION: 1'
        _event(state, "HelmRelease", f"{action.title()}ed Helm release {namespace}/{name}.", obj=f"helmrelease/{name}")
        return output
    if action == "uninstall" and len(tokens) >= 3:
        name = tokens[2]
        if not state["helm_releases"].pop(_key(namespace, name), None):
            raise ValueError(f'Release not loaded: {name}')
        if _key(namespace, name) in state["deployments"]:
            _delete_resource(state, "deployment", name, namespace)
        return f'release "{name}" uninstalled'
    if action == "status" and len(tokens) >= 3:
        release = state["helm_releases"].get(_key(namespace, tokens[2]))
        if not release:
            raise ValueError(f'release: not found: "{tokens[2]}"')
        return yaml.safe_dump(release, sort_keys=False)
    raise ValueError(f'helm action "{action}" is not supported by the simulator')


def execute_command(state, command, manifest_text=""):
    command = (command or "").strip()
    if not command:
        return state, ""
    if any(value in command for value in (";", "&&", "||", "|", "`", "$(")):
        return state, "error: shell operators are disabled; run one simulated command at a time"
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return state, f"error: {exc}"
    if not tokens:
        return state, ""

    working = clone_state(state)
    try:
        executable = tokens[0].lower()
        if executable == "helm":
            output = _helm_command(working, tokens)
        elif executable not in {"kubectl", "k", "oc"}:
            raise ValueError("only simulated kubectl, oc, and helm commands are allowed")
        else:
            args = tokens[1:]
            if not args:
                output = "kubectl simulator: use get, create, run, expose, scale, delete, describe, logs, apply, cordon, drain, or rollout"
            else:
                action = args[0].lower()
                namespace = _namespace_flag(args)
                if action == "get" and len(args) >= 2:
                    output = _get_output(working, args[1], namespace, "-A" in args or "--all-namespaces" in args)
                elif action == "create" and len(args) >= 3 and args[1] in {"namespace", "ns"}:
                    create_namespace(working, args[2])
                    output = f'namespace/{args[2]} created'
                elif action == "create" and len(args) >= 3 and args[1] in {"deployment", "deploy"}:
                    name = args[2]
                    image = _flag(args, "--image")
                    if not image:
                        raise ValueError("required flag(s) --image must be specified")
                    replicas = int(_flag(args, "--replicas", 1))
                    heap_size = int(_flag(args, "--heap-memory", 0))
                    create_deployment(
                        working,
                        name,
                        image,
                        replicas,
                        namespace,
                        heap_size_mi=heap_size,
                    )
                    output = f'deployment.apps/{name} created'
                elif action == "run" and len(args) >= 2:
                    name = args[1]
                    image = _flag(args, "--image")
                    if not image:
                        raise ValueError("required flag(s) --image must be specified")
                    _create_pod(working, name, _namespace(working, namespace), image)
                    output = f'pod/{name} created'
                elif action == "expose" and len(args) >= 3:
                    _, name = _resource_name(args[2])
                    port = int(_flag(args, "--port", 80))
                    target_port = int(_flag(args, "--target-port", port))
                    service_type = _flag(args, "--type", "ClusterIP")
                    create_service(working, name, name, port, target_port, service_type, namespace)
                    output = f'service/{name} exposed'
                elif action == "scale" and len(args) >= 2:
                    _, name = _resource_name(args[1])
                    replicas = _flag(args, "--replicas")
                    if replicas is None:
                        raise ValueError("--replicas is required")
                    scale_deployment(working, name, replicas, namespace)
                    output = f'deployment.apps/{name} scaled'
                elif action == "delete" and len(args) >= 3:
                    output = _delete_resource(working, args[1], args[2], namespace)
                elif action == "describe" and len(args) >= 3:
                    output = _describe(working, args[1], args[2], namespace)
                elif action == "logs" and len(args) >= 2:
                    _, name = _resource_name(args[1])
                    pod = working["pods"].get(_key(namespace, name))
                    if not pod:
                        raise ValueError(f'pods "{name}" not found')
                    output = "\n".join(pod["logs"])
                elif action == "apply" and _flag(args, "-f") in {"-", "manifest.yaml", "deployment.yaml"}:
                    output = apply_manifest(working, manifest_text, namespace)
                elif action in {"cordon", "uncordon"} and len(args) >= 2:
                    node = next((item for item in working["nodes"] if item["name"] == args[1]), None)
                    if not node:
                        raise ValueError(f'nodes "{args[1]}" not found')
                    node["schedulable"] = action == "uncordon"
                    output = f'node/{node["name"]} {"uncordoned" if node["schedulable"] else "cordoned"}'
                    _event(working, "NodeSchedulingChanged", output, obj=f"node/{node['name']}")
                elif action == "drain" and len(args) >= 2:
                    node = next((item for item in working["nodes"] if item["name"] == args[1]), None)
                    if not node:
                        raise ValueError(f'nodes "{args[1]}" not found')
                    node["schedulable"] = False
                    for pod in list(working["pods"].values()):
                        if pod.get("node") == node["name"]:
                            working["pods"].pop(_key(pod["namespace"], pod["name"]), None)
                    _event(working, "NodeDrained", f"Drained {node['name']}.", obj=f"node/{node['name']}")
                    _reconcile(working)
                    output = f'node/{node["name"]} drained'
                elif action == "rollout" and len(args) >= 3 and args[1] == "restart":
                    _, name = _resource_name(args[2])
                    deployment = working["deployments"].get(_key(namespace, name))
                    if not deployment:
                        raise ValueError(f'deployments.apps "{name}" not found')
                    for pod_key, pod in list(working["pods"].items()):
                        if pod["namespace"] == namespace and pod.get("owner") == name:
                            working["pods"].pop(pod_key)
                    deployment["generation"] += 1
                    _reconcile(working)
                    output = f'deployment.apps/{name} restarted'
                elif action == "cluster-info":
                    cluster = working["cluster"]
                    output = (
                        f"Kubernetes control plane is running at https://virtual-{cluster['name']}.simulator.local\n"
                        f"Provider: {cluster['provider']}  Region: {cluster['region']}"
                    )
                elif action == "version":
                    output = (
                        "Client Version: v1.33.0-simulator\n"
                        f"Server Version: v{working['cluster']['version']}.0-virtual"
                    )
                elif action == "top" and len(args) >= 2:
                    if args[1] in {"nodes", "node"}:
                        rows = node_rows(working)
                        output = _format_table(
                            ["NAME", "CPU", "MEMORY"],
                            [[row["Name"], row["CPU"], row["Memory"]] for row in rows],
                        )
                    else:
                        rows = pod_rows(working, namespace)
                        output = _format_table(
                            ["NAME", "CPU", "MEMORY"],
                            [[row["Name"], row["CPU"], row["Memory"]] for row in rows],
                        )
                elif executable == "oc" and action == "new-app" and len(args) >= 2:
                    image = args[1]
                    name = _flag(args, "--name", image.split("/")[-1].split(":")[0])
                    create_deployment(working, name, image, 1, namespace)
                    create_service(working, name, name, 8080, 8080, "ClusterIP", namespace)
                    output = f'--> Creating resources ...\ndeployment.apps/{name} created\nservice/{name} created'
                else:
                    raise ValueError(f'command "{command}" is not supported yet by the learning simulator')
        working.setdefault("history", []).append(
            {"time": _now(), "command": command, "output": output, "success": True}
        )
        working["history"] = working["history"][-100:]
        return working, output
    except (ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        output = f"error: {exc}"
        state.setdefault("history", []).append(
            {"time": _now(), "command": command, "output": output, "success": False}
        )
        state["history"] = state["history"][-100:]
        return state, output


def export_state(state):
    return json.dumps(state, indent=2, sort_keys=True)
