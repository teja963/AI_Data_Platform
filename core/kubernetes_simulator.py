import copy
import json
import shlex
import uuid
from datetime import datetime, timezone

import yaml


SIMULATOR_VERSION = 4
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


def _namespace_template(
    name,
    owner="Platform Team",
    environment="Shared",
    cpu_quota_m=0,
    memory_quota_mi=0,
    storage_quota_gi=0,
    pod_quota=0,
    default_cpu_m=250,
    default_memory_mi=256,
    labels=None,
):
    return {
        "name": name,
        "status": "Active",
        "owner": owner,
        "environment": environment,
        "cpu_quota_m": int(cpu_quota_m),
        "memory_quota_mi": int(memory_quota_mi),
        "storage_quota_gi": int(storage_quota_gi),
        "pod_quota": int(pod_quota),
        "default_cpu_m": int(default_cpu_m),
        "default_memory_mi": int(default_memory_mi),
        "labels": labels or {},
        "created_at": _now(),
    }


def _system_namespaces(total_cpu_m, total_memory_mi, total_storage_gi):
    return {
        "default": _namespace_template(
            "default",
            owner="Platform Team",
            environment="Shared",
            default_cpu_m=1000,
            default_memory_mi=2048,
        ),
        "kube-system": _namespace_template(
            "kube-system",
            owner="Kubernetes",
            environment="System",
            default_cpu_m=1000,
            default_memory_mi=1024,
            labels={"kubernetes.io/metadata.name": "kube-system"},
        ),
        "kube-public": _namespace_template(
            "kube-public",
            owner="Kubernetes",
            environment="System",
            default_cpu_m=1000,
            default_memory_mi=1024,
        ),
        "kube-node-lease": _namespace_template(
            "kube-node-lease",
            owner="Kubernetes",
            environment="System",
            default_cpu_m=1000,
            default_memory_mi=1024,
        ),
    }


def normalize_cluster_state(state):
    """Add newly introduced simulator fields to previously saved labs."""
    if not state:
        return state
    if int(state.get("simulator_version", 0)) < SIMULATOR_VERSION:
        workers = [
            node for node in state.get("nodes", [])
            if node.get("role") == "worker"
        ]
        state["namespaces"] = _system_namespaces(
            sum(node.get("cpu_capacity_m", 0) for node in workers),
            sum(node.get("memory_capacity_mi", 0) for node in workers),
            sum(node.get("storage_gi", 0) for node in workers),
        )
        state["deployments"] = {}
        state["pods"] = {}
        state["services"] = {}
        state["helm_releases"] = {}
        state["events"] = []
        state["history"] = []
        state["simulator_version"] = SIMULATOR_VERSION
    for name, namespace in state.setdefault("namespaces", {}).items():
        defaults = _namespace_template(name)
        for key, value in defaults.items():
            namespace.setdefault(key, value)
    state.setdefault(
        "terminal_context",
        {"mode": "cluster", "namespace": DEFAULT_NAMESPACE, "pod": None, "cwd": "/app"},
    )
    return state


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
        "namespaces": _system_namespaces(
            int(worker_count) * int(cpu_per_worker) * 1000,
            int(worker_count) * int(memory_per_worker_mi),
            int(worker_count) * int(storage_per_worker_gi),
        ),
        "deployments": {},
        "pods": {},
        "services": {},
        "helm_releases": {},
        "events": [],
        "history": [],
        "terminal_context": {
            "mode": "cluster",
            "namespace": DEFAULT_NAMESPACE,
            "pod": None,
            "cwd": "/app",
        },
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
                "CPU": f"{usage['cpu_m'] / 1000:.2f} / {node['cpu_capacity_m'] / 1000:.2f} cores",
                "Memory": f"{usage['memory_mi'] / 1024:.2f} / {node['memory_capacity_mi'] / 1024:.2f} GiB",
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
                "CPU": f"{pod.get('cpu_request_m', 0) / 1000:.2f} cores",
                "Memory": f"{pod.get('memory_request_mi', 0) / 1024:.2f} GiB",
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
                "CPU/Pod": f"{deployment['cpu_request_m'] / 1000:.2f} cores",
                "Memory/Pod": f"{deployment['memory_request_mi'] / 1024:.2f} GiB",
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
                "Ports": ", ".join(
                    f"{item['name']} {item['port']}:{item['target_port']}"
                    for item in service.get(
                        "ports",
                        [
                            {
                                "name": "default",
                                "port": service["port"],
                                "target_port": service["target_port"],
                            }
                        ],
                    )
                ),
                "Selector": service["selector"],
            }
        )
    return sorted(rows, key=lambda item: (item["Namespace"], item["Name"]))


def namespace_usage(state, namespace):
    pods = [
        pod for pod in state["pods"].values()
        if pod["namespace"] == namespace
    ]
    return {
        "pods": len(pods),
        "running_pods": sum(pod["status"] == "Running" for pod in pods),
        "pending_pods": sum(pod["status"] == "Pending" for pod in pods),
        "cpu_m": sum(int(pod.get("cpu_request_m", 0)) for pod in pods),
        "memory_mi": sum(int(pod.get("memory_request_mi", 0)) for pod in pods),
        "deployments": sum(
            item["namespace"] == namespace for item in state["deployments"].values()
        ),
        "services": sum(
            item["namespace"] == namespace for item in state["services"].values()
        ),
    }


def namespace_rows(state):
    rows = []
    for namespace in state["namespaces"].values():
        usage = namespace_usage(state, namespace["name"])
        rows.append(
            {
                "Namespace": namespace["name"],
                "Owner": namespace.get("owner", "Platform Team"),
                "Environment": namespace.get("environment", "Shared"),
                "Status": namespace.get("status", "Active"),
                "Pods": usage["pods"],
                "CPU Allocated": f"{usage['cpu_m'] / 1000:.2f} cores",
                "Memory Allocated": f"{usage['memory_mi'] / 1024:.2f} GiB",
                "Default Pod": (
                    f"{namespace.get('default_cpu_m', 1000) / 1000:.2f} CPU / "
                    f"{namespace.get('default_memory_mi', 2048) / 1024:.2f} GiB"
                ),
                "Deployments": usage["deployments"],
                "Services": usage["services"],
            }
        )
    return sorted(rows, key=lambda item: item["Namespace"])


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
    if namespace in state["namespaces"]:
        _validate_namespace_quota(
            state,
            namespace,
            1,
            int(cpu_request_m),
            int(memory_request_mi),
        )
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
        "env": {
            "HOSTNAME": pod_name,
            "POD_NAME": pod_name,
            "POD_NAMESPACE": namespace,
            "NODE_NAME": node_name or "",
            "APP_IMAGE": image,
            "JAVA_TOOL_OPTIONS": f"-Xms{max(128, int(heap_size_mi) // 2)}m -Xmx{int(heap_size_mi)}m"
            if int(heap_size_mi)
            else "",
        },
        "filesystem": {
            "/etc/hostname": pod_name,
            "/etc/os-release": (
                'NAME="Virtual Kubernetes Linux"\n'
                'VERSION="1.0 (Simulator)"\n'
                "ID=virtual-k8s\n"
            ),
            "/app/config/application.properties": (
                f"app.image={image}\n"
                f"kubernetes.namespace={namespace}\n"
                f"kubernetes.pod={pod_name}\n"
            ),
            "/proc/meminfo": (
                f"MemTotal:       {int(memory_request_mi) * 1024} kB\n"
                f"MemAvailable:   {int(memory_request_mi * 0.72) * 1024} kB\n"
            ),
        },
        "processes": [
            {"pid": 1, "user": "app", "command": f"/entrypoint --image {image}"},
            {"pid": 17, "user": "app", "command": "application-worker"},
        ],
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
                pod.setdefault("env", {})["NODE_NAME"] = node_name
                pod["logs"].append(f"{_now()} Scheduled on {node_name}")
                _event(state, "Scheduled", f"Assigned {pod['namespace']}/{pod['name']} to {node_name}.", obj=f"pod/{pod['name']}")


def create_namespace(
    state,
    name,
    owner="Platform Team",
    environment="Development",
    cpu_quota_m=0,
    memory_quota_mi=0,
    storage_quota_gi=0,
    pod_quota=0,
    default_cpu_m=1000,
    default_memory_mi=2048,
    labels=None,
):
    name = name.strip().lower()
    if not name:
        raise ValueError("namespace name is required")
    if name in state["namespaces"]:
        raise ValueError(f'namespaces "{name}" already exists')
    state["namespaces"][name] = _namespace_template(
        name,
        owner,
        environment,
        cpu_quota_m,
        memory_quota_mi,
        storage_quota_gi,
        pod_quota,
        default_cpu_m,
        default_memory_mi,
        labels,
    )
    _event(state, "NamespaceCreated", f"Created namespace {name}.", obj=f"namespace/{name}")
    return state["namespaces"][name]


def _validate_namespace_policy(
    state,
    cpu_quota_m,
    memory_quota_mi,
    storage_quota_gi,
    pod_quota,
    excluding=None,
):
    values = {
        "CPU quota": int(cpu_quota_m),
        "memory quota": int(memory_quota_mi),
        "storage quota": int(storage_quota_gi),
        "pod limit": int(pod_quota),
    }
    for label, value in values.items():
        if value <= 0:
            raise ValueError(f"{label} must be greater than zero")
    workers = [node for node in state["nodes"] if node["role"] == "worker"]
    capacities = {
        "cpu_quota_m": sum(node["cpu_capacity_m"] for node in workers),
        "memory_quota_mi": sum(node["memory_capacity_mi"] for node in workers),
        "storage_quota_gi": sum(node["storage_gi"] for node in workers),
        "pod_quota": len(workers) * 110,
    }
    requested = {
        "cpu_quota_m": int(cpu_quota_m),
        "memory_quota_mi": int(memory_quota_mi),
        "storage_quota_gi": int(storage_quota_gi),
        "pod_quota": int(pod_quota),
    }
    labels = {
        "cpu_quota_m": "CPU millicores",
        "memory_quota_mi": "memory MiB",
        "storage_quota_gi": "storage GiB",
        "pod_quota": "pods",
    }
    for field, capacity in capacities.items():
        allocated = sum(
            int(namespace.get(field, 0))
            for name, namespace in state["namespaces"].items()
            if name != excluding
        )
        if allocated + requested[field] > capacity:
            available = max(0, capacity - allocated)
            raise ValueError(
                f"namespace {labels[field]} allocation exceeds cluster capacity; "
                f"{available} remains available"
            )


def update_namespace(
    state,
    name,
    owner,
    environment,
    cpu_quota_m,
    memory_quota_mi,
    storage_quota_gi,
    pod_quota,
    default_cpu_m,
    default_memory_mi,
    labels=None,
):
    namespace = state["namespaces"].get(name)
    if not namespace:
        raise ValueError(f'namespaces "{name}" not found')
    namespace.update(
        {
            "owner": owner,
            "environment": environment,
            "cpu_quota_m": int(cpu_quota_m),
            "memory_quota_mi": int(memory_quota_mi),
            "storage_quota_gi": int(storage_quota_gi),
            "pod_quota": int(pod_quota),
            "default_cpu_m": int(default_cpu_m),
            "default_memory_mi": int(default_memory_mi),
            "labels": labels or {},
        }
    )
    _event(
        state,
        "NamespaceUpdated",
        f"Updated quotas and defaults for namespace {name}.",
        obj=f"namespace/{name}",
    )
    return namespace


def _validate_namespace_quota(
    state,
    namespace,
    additional_pods,
    additional_cpu_m,
    additional_memory_mi,
):
    policy = state["namespaces"][namespace]
    usage = namespace_usage(state, namespace)
    checks = [
        ("pods", usage["pods"] + additional_pods, policy.get("pod_quota", 0)),
        ("CPU millicores", usage["cpu_m"] + additional_cpu_m, policy.get("cpu_quota_m", 0)),
        (
            "memory Mi",
            usage["memory_mi"] + additional_memory_mi,
            policy.get("memory_quota_mi", 0),
        ),
    ]
    for resource, requested, quota in checks:
        if quota and requested > quota:
            raise ValueError(
                f'exceeded namespace "{namespace}" {resource} quota: '
                f"requested total {requested}, quota {quota}"
            )


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
    _validate_namespace_quota(
        state,
        namespace,
        max(0, int(replicas)),
        max(0, int(replicas)) * max(1, int(cpu_request_m)),
        max(0, int(replicas)) * max(1, int(memory_request_mi)),
    )
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
    replica_delta = max(0, int(replicas) - int(deployment["replicas"]))
    _validate_namespace_quota(
        state,
        namespace,
        replica_delta,
        replica_delta * deployment["cpu_request_m"],
        replica_delta * deployment["memory_request_mi"],
    )
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
    ports=None,
):
    namespace = _namespace(state, namespace)
    key = _key(namespace, name)
    if key in state["services"]:
        raise ValueError(f'services "{name}" already exists')
    state["counters"]["service_ip"] += 1
    normalized_ports = ports or [
        {"name": "default", "port": int(port), "target_port": int(target_port)}
    ]
    normalized_ports = [
        {
            "name": item.get("name", f"port-{item['port']}"),
            "port": int(item["port"]),
            "target_port": int(item.get("target_port", item["port"])),
        }
        for item in normalized_ports
    ]
    state["services"][key] = {
        "name": name,
        "namespace": namespace,
        "selector": selector,
        "port": int(port),
        "target_port": int(target_port),
        "ports": normalized_ports,
        "type": service_type,
        "cluster_ip": f"10.96.0.{state['counters']['service_ip']}",
        "created_at": _now(),
    }
    _event(state, "ServiceCreated", f"Exposed {selector} through service {name}.", obj=f"service/{name}")
    return state["services"][key]


def deploy_data_platform_blueprint(
    state,
    namespace,
    postgres_replicas=2,
    api_replicas=2,
    flink_taskmanagers=3,
    starrocks_compute_nodes=3,
    superset_replicas=2,
):
    """Create a standard PostgreSQL, Flink, StarRocks, and Superset learning stack."""
    working = clone_state(state)
    workloads = [
        ("postgresql", "postgres:latest", postgres_replicas, 2, 4, "StatefulSet"),
        ("data-api", "example/data-api:1.0", api_replicas, 1, 2, "Deployment"),
        ("flink-operator", "apache/flink-kubernetes-operator:latest", 1, 1, 2, "Deployment"),
        ("flink-jobmanager", "apache/flink:latest", 1, 2, 4, "Deployment"),
        ("flink-taskmanager", "apache/flink:latest", flink_taskmanagers, 2, 4, "Deployment"),
        ("starrocks-fe", "starrocks/fe-ubuntu:latest", 3, 2, 4, "StatefulSet"),
        ("starrocks-cn", "starrocks/cn-ubuntu:latest", starrocks_compute_nodes, 4, 8, "Deployment"),
        ("superset", "apache/superset:latest", superset_replicas, 1, 2, "Deployment"),
    ]
    for name, image, replicas, cpu, memory, kind in workloads:
        create_deployment(
            working,
            name,
            image,
            replicas,
            namespace,
            cpu * 1000,
            memory * 1024,
            kind,
        )
    services = [
        ("postgresql", "postgresql", [{"name": "sql", "port": 5432, "target_port": 5432}]),
        ("data-api", "data-api", [{"name": "http", "port": 8080, "target_port": 8080}]),
        (
            "flink-operator",
            "flink-operator",
            [
                {"name": "metrics", "port": 8080, "target_port": 8080},
                {"name": "webhook", "port": 9443, "target_port": 9443},
            ],
        ),
        (
            "flink-jobmanager",
            "flink-jobmanager",
            [
                {"name": "rpc", "port": 6123, "target_port": 6123},
                {"name": "blob", "port": 6124, "target_port": 6124},
                {"name": "web-ui", "port": 8081, "target_port": 8081},
            ],
        ),
        (
            "flink-taskmanager",
            "flink-taskmanager",
            [{"name": "rpc", "port": 6122, "target_port": 6122}],
        ),
        (
            "starrocks-fe",
            "starrocks-fe",
            [
                {"name": "http", "port": 8030, "target_port": 8030},
                {"name": "edit-log", "port": 9010, "target_port": 9010},
                {"name": "rpc", "port": 9020, "target_port": 9020},
                {"name": "mysql", "port": 9030, "target_port": 9030},
            ],
        ),
        (
            "starrocks-cn",
            "starrocks-cn",
            [
                {"name": "http", "port": 8040, "target_port": 8040},
                {"name": "heartbeat", "port": 9050, "target_port": 9050},
                {"name": "thrift", "port": 9060, "target_port": 9060},
                {"name": "brpc", "port": 8060, "target_port": 8060},
                {"name": "starlet", "port": 9070, "target_port": 9070},
            ],
        ),
        ("superset", "superset", [{"name": "web-ui", "port": 8088, "target_port": 8088}]),
    ]
    for name, selector, ports in services:
        first = ports[0]
        create_service(
            working,
            name,
            selector,
            first["port"],
            first["target_port"],
            "ClusterIP",
            namespace,
            ports=ports,
        )
    _event(
        working,
        "BlueprintDeployed",
        f"Deployed the standard data platform blueprint in namespace {namespace}.",
        obj=f"namespace/{namespace}",
    )
    return working


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
            [[row["Namespace"], row["Name"], row["Type"], row["Cluster IP"], row["Ports"]] for row in rows],
        )
    if resource in {"namespace", "namespaces", "ns"}:
        rows = namespace_rows(state)
        return _format_table(
            ["NAME", "STATUS", "PODS", "CPU", "MEMORY", "OWNER"],
            [
                [
                    item["Namespace"],
                    item["Status"],
                    item["Pods"],
                    item["CPU Allocated"],
                    item["Memory Allocated"],
                    item["Owner"],
                ]
                for item in rows
            ],
        )
    if resource in {"event", "events", "ev"}:
        return _format_table(
            ["TYPE", "REASON", "OBJECT", "MESSAGE"],
            [[event["type"], event["reason"], event["object"], event["message"]] for event in state["events"][-20:]],
        )
    if resource == "all":
        return "\n\n".join(
            [
                "PODS\n" + _get_output(state, "pods", namespace, all_namespaces),
                "DEPLOYMENTS\n" + _get_output(state, "deployments", namespace, all_namespaces),
                "SERVICES\n" + _get_output(state, "services", namespace, all_namespaces),
            ]
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
    elif resource in {"namespace", "namespaces", "ns"}:
        item = state["namespaces"].get(name)
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


def execute_pod_command(state, namespace, pod_name, command):
    pod = state["pods"].get(_key(namespace, pod_name))
    if not pod:
        raise ValueError(f'pods "{pod_name}" not found')
    if pod["status"] != "Running":
        raise ValueError(f'unable to execute command: pod {pod_name} is {pod["status"]}')
    command = (command or "").strip()
    if not command:
        raise ValueError("an in-pod command is required after --")
    if any(value in command for value in (";", "&&", "||", "|", "`", "$(")):
        raise ValueError("shell operators are disabled in the virtual pod shell")
    tokens = shlex.split(command)
    executable = tokens[0]
    args = tokens[1:]
    env = pod.setdefault("env", {})
    filesystem = pod.setdefault("filesystem", {})

    if executable in {"sh", "bash"}:
        return (
            f"Connected to virtual pod {namespace}/{pod_name}.\n"
            "Use the Pod Shell panel for commands such as env, ls, cat, ps, df, free, "
            "hostname, curl, and nslookup."
        )
    if executable == "pwd":
        return "/app"
    if executable == "whoami":
        return "app"
    if executable == "id":
        return "uid=1000(app) gid=1000(app) groups=1000(app)"
    if executable == "hostname":
        return pod_name
    if executable == "date":
        return _now()
    if executable == "uname":
        return "Linux virtual-k8s 6.8.0-simulator #1 SMP x86_64 GNU/Linux"
    if executable in {"env", "printenv"}:
        if args:
            variable = args[0]
            if variable not in env:
                raise ValueError(f"{variable}: environment variable not found")
            return env[variable]
        return "\n".join(f"{key}={value}" for key, value in sorted(env.items()))
    if executable == "echo":
        values = []
        for value in args:
            if value.startswith("$"):
                values.append(env.get(value[1:], ""))
            else:
                values.append(value)
        return " ".join(values)
    if executable == "ls":
        requested = next((arg for arg in args if not arg.startswith("-")), "/app")
        requested = requested.rstrip("/") or "/"
        entries = set()
        for path in filesystem:
            if requested == "/":
                remainder = path.lstrip("/")
            elif path == requested:
                entries.add(requested.rsplit("/", 1)[-1])
                continue
            elif path.startswith(requested + "/"):
                remainder = path[len(requested) + 1 :]
            else:
                continue
            entries.add(remainder.split("/", 1)[0])
        if not entries:
            raise ValueError(f"ls: cannot access '{requested}': No such file or directory")
        return "\n".join(sorted(entries))
    if executable == "cat":
        if not args:
            raise ValueError("cat: missing file operand")
        path = args[0]
        if path not in filesystem:
            raise ValueError(f"cat: {path}: No such file or directory")
        return filesystem[path]
    if executable == "ps":
        return _format_table(
            ["PID", "USER", "COMMAND"],
            [[item["pid"], item["user"], item["command"]] for item in pod.get("processes", [])],
        )
    if executable == "df":
        node = next((item for item in state["nodes"] if item["name"] == pod.get("node")), None)
        storage = int(node["storage_gi"]) if node else 20
        used = max(1, int(storage * 0.28))
        return _format_table(
            ["Filesystem", "Size", "Used", "Avail", "Use%", "Mounted on"],
            [["virtual-overlay", f"{storage}G", f"{used}G", f"{storage - used}G", "28%", "/"]],
        )
    if executable == "free":
        total = int(pod.get("memory_request_mi", 256))
        used = max(1, int(total * 0.28))
        return _format_table(
            ["", "total", "used", "free", "available"],
            [["Mem:", total, used, total - used, int(total * 0.72)]],
        )
    if executable == "top":
        return (
            f"top - virtual pod {pod_name}\n"
            f"Tasks: {len(pod.get('processes', []))} total, 1 running\n"
            f"CPU request: {pod.get('cpu_request_m', 0)}m  "
            f"Memory request: {pod.get('memory_request_mi', 0)}Mi\n\n"
            + _format_table(
                ["PID", "USER", "%CPU", "%MEM", "COMMAND"],
                [
                    [item["pid"], item["user"], "3.2", "8.4", item["command"]]
                    for item in pod.get("processes", [])
                ],
            )
        )
    if executable in {"curl", "wget"}:
        if not args:
            raise ValueError(f"{executable}: URL is required")
        target = args[-1].replace("http://", "").replace("https://", "")
        host = target.split("/", 1)[0].split(":", 1)[0]
        service = next(
            (
                item
                for item in state["services"].values()
                if item["name"] == host
                and item["namespace"] in {namespace, DEFAULT_NAMESPACE}
            ),
            None,
        )
        if not service:
            raise ValueError(f"Could not resolve host: {host}")
        endpoints = [
            item
            for item in state["pods"].values()
            if item["namespace"] == service["namespace"]
            and item.get("owner") == service["selector"]
            and item["status"] == "Running"
        ]
        if not endpoints:
            raise ValueError(f"connection to {host}:{service['port']} failed: no ready endpoints")
        return (
            "HTTP/1.1 200 OK\n"
            "Content-Type: application/json\n\n"
            + json.dumps(
                {
                    "service": host,
                    "served_by": endpoints[0]["name"],
                    "status": "ok",
                },
                indent=2,
            )
        )
    if executable in {"nslookup", "getent"}:
        host = args[-1] if args else ""
        service = next(
            (item for item in state["services"].values() if item["name"] == host),
            None,
        )
        if not service:
            raise ValueError(f"server can't find {host}: NXDOMAIN")
        return f"Name: {host}.{service['namespace']}.svc.cluster.local\nAddress: {service['cluster_ip']}"
    if executable == "java" and args == ["-version"]:
        return (
            'openjdk version "21.0.8" 2026-07-15\n'
            "OpenJDK Runtime Environment (Virtual Kubernetes Simulator)"
        )
    raise ValueError(
        f'pod command "{executable}" is not supported; try env, printenv, pwd, ls, cat, '
        "ps, top, df, free, hostname, curl, nslookup, java -version, or echo"
    )


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
                    resource_name = next(
                        (
                            token
                            for token in args[2:]
                            if not token.startswith("-")
                            and token
                            not in {
                                namespace,
                                _flag(args, "-o"),
                                _flag(args, "--output"),
                            }
                        ),
                        None,
                    )
                    if resource_name and args[1] not in {"all", "events", "event"}:
                        rendered = _describe(working, args[1], resource_name, namespace)
                        output_format = _flag(args, "-o", _flag(args, "--output", ""))
                        if output_format == "json":
                            output = json.dumps(yaml.safe_load(rendered), indent=2)
                        else:
                            output = rendered
                    else:
                        output = _get_output(
                            working,
                            args[1],
                            namespace,
                            "-A" in args or "--all-namespaces" in args,
                        )
                elif action == "create" and len(args) >= 3 and args[1] in {"namespace", "ns"}:
                    create_namespace(
                        working,
                        args[2],
                        owner=_flag(args, "--owner", "Platform Team"),
                        environment=_flag(args, "--environment", "Development"),
                        cpu_quota_m=0,
                        memory_quota_mi=0,
                        storage_quota_gi=0,
                        pod_quota=0,
                        default_cpu_m=int(_flag(args, "--default-cpu", 1000)),
                        default_memory_mi=int(_flag(args, "--default-memory", 2048)),
                    )
                    output = f'namespace/{args[2]} created'
                elif action == "create" and len(args) >= 3 and args[1] in {"deployment", "deploy"}:
                    name = args[2]
                    image = _flag(args, "--image")
                    if not image:
                        raise ValueError("required flag(s) --image must be specified")
                    replicas = int(_flag(args, "--replicas", 1))
                    heap_size = int(_flag(args, "--heap-memory", 0))
                    namespace_policy = working["namespaces"].get(
                        namespace,
                        working["namespaces"][DEFAULT_NAMESPACE],
                    )
                    cpu_request = int(
                        _flag(args, "--cpu", namespace_policy.get("default_cpu_m", 250))
                    )
                    memory_request = int(
                        _flag(
                            args,
                            "--memory",
                            namespace_policy.get("default_memory_mi", 256),
                        )
                    )
                    create_deployment(
                        working,
                        name,
                        image,
                        replicas,
                        namespace,
                        cpu_request,
                        memory_request,
                        heap_size_mi=heap_size,
                    )
                    output = f'deployment.apps/{name} created'
                elif action == "run" and len(args) >= 2:
                    name = args[1]
                    image = _flag(args, "--image")
                    if not image:
                        raise ValueError("required flag(s) --image must be specified")
                    target_namespace = _namespace(working, namespace)
                    policy = working["namespaces"][target_namespace]
                    _create_pod(
                        working,
                        name,
                        target_namespace,
                        image,
                        cpu_request_m=int(
                            _flag(args, "--cpu", policy.get("default_cpu_m", 250))
                        ),
                        memory_request_mi=int(
                            _flag(
                                args,
                                "--memory",
                                policy.get("default_memory_mi", 256),
                            )
                        ),
                    )
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
                elif action == "exec":
                    if "--" not in args:
                        raise ValueError("exec requires POD_NAME -- COMMAND")
                    separator = args.index("--")
                    pre_command = args[1:separator]
                    pod_name = None
                    skip_next = False
                    for index, token in enumerate(pre_command):
                        if skip_next:
                            skip_next = False
                            continue
                        if token in {"-n", "--namespace", "-c", "--container"}:
                            skip_next = True
                            continue
                        if token.startswith("-"):
                            continue
                        pod_name = token
                        break
                    if not pod_name:
                        raise ValueError("pod name is required for exec")
                    inside_command = " ".join(args[separator + 1 :])
                    output = execute_pod_command(
                        working,
                        namespace,
                        pod_name,
                        inside_command,
                    )
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
                elif action == "rollout" and len(args) >= 3 and args[1] in {"status", "history"}:
                    _, name = _resource_name(args[2])
                    deployment = working["deployments"].get(_key(namespace, name))
                    if not deployment:
                        raise ValueError(f'deployments.apps "{name}" not found')
                    if args[1] == "history":
                        output = (
                            f"deployment.apps/{name}\n"
                            f"REVISION  CHANGE-CAUSE\n{deployment['generation']}         <simulated>"
                        )
                    else:
                        ready = sum(
                            pod["status"] == "Running"
                            for pod in working["pods"].values()
                            if pod["namespace"] == namespace and pod.get("owner") == name
                        )
                        output = (
                            f'deployment "{name}" successfully rolled out'
                            if ready == deployment["replicas"]
                            else f"Waiting for deployment: {ready} of {deployment['replicas']} replicas are ready"
                        )
                elif action == "set" and len(args) >= 4 and args[1] == "image":
                    _, name = _resource_name(args[2])
                    deployment = working["deployments"].get(_key(namespace, name))
                    if not deployment:
                        raise ValueError(f'deployments.apps "{name}" not found')
                    image_assignment = args[3]
                    if "=" not in image_assignment:
                        raise ValueError("set image requires CONTAINER=IMAGE")
                    deployment["image"] = image_assignment.split("=", 1)[1]
                    deployment["generation"] += 1
                    for pod_key, pod in list(working["pods"].items()):
                        if pod["namespace"] == namespace and pod.get("owner") == name:
                            working["pods"].pop(pod_key)
                    _reconcile(working)
                    output = f'deployment.apps/{name} image updated'
                elif action in {"label", "annotate"} and len(args) >= 4:
                    resource, name, assignment = args[1], args[2], args[3]
                    if "=" not in assignment:
                        raise ValueError(f"{action} requires KEY=VALUE")
                    key_name, value = assignment.split("=", 1)
                    if resource in {"node", "nodes"}:
                        item = next((node for node in working["nodes"] if node["name"] == name), None)
                    elif resource in {"pod", "pods"}:
                        item = working["pods"].get(_key(namespace, name))
                    elif resource in {"deployment", "deployments"}:
                        item = working["deployments"].get(_key(namespace, name))
                    else:
                        item = None
                    if not item:
                        raise ValueError(f'{resource} "{name}" not found')
                    item.setdefault("annotations" if action == "annotate" else "labels", {})[key_name] = value
                    output = f'{resource}/{name} {action}d'
                elif action == "config":
                    subcommand = args[1] if len(args) > 1 else ""
                    cluster_name = working["cluster"]["name"]
                    if subcommand == "current-context":
                        output = f"{cluster_name}-simulator"
                    elif subcommand == "get-contexts":
                        output = (
                            "CURRENT  NAME                       CLUSTER\n"
                            f"*        {cluster_name}-simulator  {cluster_name}"
                        )
                    elif subcommand == "view":
                        output = yaml.safe_dump(
                            {
                                "current-context": f"{cluster_name}-simulator",
                                "clusters": [{"name": cluster_name, "cluster": {"server": f"https://virtual-{cluster_name}.simulator.local"}}],
                            },
                            sort_keys=False,
                        )
                    else:
                        raise ValueError(f'config subcommand "{subcommand}" is not supported')
                elif action == "api-resources":
                    output = _format_table(
                        ["NAME", "SHORTNAMES", "APIVERSION", "NAMESPACED", "KIND"],
                        [
                            ["pods", "po", "v1", "true", "Pod"],
                            ["services", "svc", "v1", "true", "Service"],
                            ["namespaces", "ns", "v1", "false", "Namespace"],
                            ["deployments", "deploy", "apps/v1", "true", "Deployment"],
                            ["statefulsets", "sts", "apps/v1", "true", "StatefulSet"],
                            ["nodes", "no", "v1", "false", "Node"],
                        ],
                    )
                elif action == "explain" and len(args) >= 2:
                    resource = args[1]
                    output = (
                        f"KIND: {resource.title()}\n"
                        "DESCRIPTION:\n"
                        f"  Virtual schema help for Kubernetes resource {resource}.\n"
                        "FIELDS:\n"
                        "  apiVersion <string>\n  kind <string>\n  metadata <Object>\n  spec <Object>"
                    )
                elif action == "auth" and len(args) >= 3 and args[1] == "can-i":
                    output = "yes"
                elif action == "port-forward" and len(args) >= 3:
                    output = (
                        f"Forwarding from 127.0.0.1:{args[2].split(':')[0]} "
                        f"-> {args[2].split(':')[-1]} (simulated; no real socket opened)"
                    )
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
