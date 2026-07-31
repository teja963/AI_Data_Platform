import math


CAPACITY_PROFILES = {
    "Learning": {
        "daily_tb": 0.01,
        "peak_factor": 2.0,
        "retention_days": 1,
        "replication": 1,
        "concurrent_jobs": 1,
        "concurrent_users": 5,
        "zones": 1,
        "growth_percent": 10,
    },
    "Development": {
        "daily_tb": 0.5,
        "peak_factor": 2.0,
        "retention_days": 7,
        "replication": 1,
        "concurrent_jobs": 3,
        "concurrent_users": 15,
        "zones": 1,
        "growth_percent": 20,
    },
    "Medium Production": {
        "daily_tb": 10,
        "peak_factor": 3.0,
        "retention_days": 30,
        "replication": 2,
        "concurrent_jobs": 10,
        "concurrent_users": 50,
        "zones": 3,
        "growth_percent": 30,
    },
    "Large Production": {
        "daily_tb": 50,
        "peak_factor": 3.0,
        "retention_days": 60,
        "replication": 3,
        "concurrent_jobs": 30,
        "concurrent_users": 200,
        "zones": 3,
        "growth_percent": 40,
    },
    "100 TB / Day": {
        "daily_tb": 100,
        "peak_factor": 3.0,
        "retention_days": 90,
        "replication": 3,
        "concurrent_jobs": 50,
        "concurrent_users": 500,
        "zones": 3,
        "growth_percent": 50,
    },
    "Petabyte Retained": {
        "daily_tb": 20,
        "peak_factor": 4.0,
        "retention_days": 180,
        "replication": 3,
        "concurrent_jobs": 40,
        "concurrent_users": 300,
        "zones": 3,
        "growth_percent": 50,
    },
}


CLOUD_NODE_PROFILES = {
    "AWS (EKS)": {
        "system": {"name": "m7i.xlarge", "cpu": 4, "memory": 16, "storage": 100},
        "streaming": {"name": "r7i.4xlarge", "cpu": 16, "memory": 128, "storage": 500},
        "analytics": {"name": "i4i.4xlarge", "cpu": 16, "memory": 128, "storage": 3750},
        "billing": (
            "EKS control-plane hours, EC2 node hours, EBS volumes, snapshots, "
            "load balancers, cross-zone traffic and internet egress."
        ),
    },
    "Google Cloud (GKE)": {
        "system": {"name": "n2-standard-4", "cpu": 4, "memory": 16, "storage": 100},
        "streaming": {"name": "n2-highmem-16", "cpu": 16, "memory": 128, "storage": 500},
        "analytics": {"name": "c3-highmem-22", "cpu": 22, "memory": 176, "storage": 3000},
        "billing": (
            "GKE cluster-management tier, Compute Engine node hours, Persistent "
            "Disk, load balancers, inter-zone traffic and network egress."
        ),
    },
    "Azure (AKS)": {
        "system": {"name": "Standard_D4s_v5", "cpu": 4, "memory": 16, "storage": 100},
        "streaming": {"name": "Standard_E16s_v5", "cpu": 16, "memory": 128, "storage": 500},
        "analytics": {"name": "Standard_L16s_v3", "cpu": 16, "memory": 128, "storage": 1900},
        "billing": (
            "AKS tier/control-plane, Virtual Machine Scale Set node hours, "
            "managed disks, load balancers, availability-zone traffic and egress."
        ),
    },
    "On-Premises": {
        "system": {"name": "General worker", "cpu": 4, "memory": 16, "storage": 100},
        "streaming": {"name": "Memory worker", "cpu": 16, "memory": 128, "storage": 500},
        "analytics": {"name": "NVMe compute worker", "cpu": 16, "memory": 128, "storage": 2000},
        "billing": (
            "Hardware acquisition, support, power, cooling, rack space, storage, "
            "networking, replacement capacity and operations staff."
        ),
    },
}


def profile_inputs(profile):
    return dict(CAPACITY_PROFILES[profile])


def _component_recommendations(
    daily_tb,
    peak_mb_s,
    concurrent_jobs,
    concurrent_users,
    zones,
):
    taskmanagers = max(
        zones,
        math.ceil(peak_mb_s / 80),
        math.ceil(concurrent_jobs / 2),
    )
    starrocks_compute = max(
        3,
        zones,
        math.ceil(peak_mb_s / 150),
        math.ceil(concurrent_users / 25),
    )
    high_scale = daily_tb >= 50
    medium_scale = daily_tb >= 10
    return [
        {
            "component": "PostgreSQL",
            "controller": "StatefulSet",
            "replicas": 3 if zones >= 3 else 2,
            "cpu_each": 16 if high_scale else 8 if medium_scale else 4,
            "memory_each_gib": 64 if high_scale else 32 if medium_scale else 16,
            "role": "Metadata, configuration and transactional state—not the raw petabyte analytical store.",
            "ports": "5432 SQL",
        },
        {
            "component": "Data API",
            "controller": "Deployment",
            "replicas": max(2, zones),
            "cpu_each": 4 if high_scale else 2,
            "memory_each_gib": 8 if high_scale else 4,
            "role": "Application/API access to platform services.",
            "ports": "8080 HTTP",
        },
        {
            "component": "Flink Operator",
            "controller": "Deployment",
            "replicas": 2 if zones >= 3 else 1,
            "cpu_each": 2,
            "memory_each_gib": 4,
            "role": "Reconciles Flink Kubernetes resources.",
            "ports": "8080 metrics, 9443 webhook",
        },
        {
            "component": "Flink JobManager",
            "controller": "Deployment",
            "replicas": 2 if zones >= 3 else 1,
            "cpu_each": 4 if high_scale else 2,
            "memory_each_gib": 16 if high_scale else 8,
            "role": "Coordinates jobs, checkpoints and recovery.",
            "ports": "6123 RPC, 6124 BLOB, 8081 Web UI",
        },
        {
            "component": "Flink TaskManager",
            "controller": "Deployment",
            "replicas": taskmanagers,
            "cpu_each": 16 if high_scale else 8 if medium_scale else 4,
            "memory_each_gib": 64 if high_scale else 32 if medium_scale else 16,
            "role": "Processes streaming records; scale from measured throughput and backpressure.",
            "ports": "6122 RPC/data",
        },
        {
            "component": "StarRocks FE",
            "controller": "StatefulSet",
            "replicas": 3,
            "cpu_each": 16 if high_scale else 8 if medium_scale else 4,
            "memory_each_gib": 64 if high_scale else 32 if medium_scale else 16,
            "role": "Metadata, SQL planning and cluster coordination.",
            "ports": "8030 HTTP, 9010 edit log, 9020 RPC, 9030 MySQL",
        },
        {
            "component": "StarRocks CN",
            "controller": "Deployment",
            "replicas": starrocks_compute,
            "cpu_each": 32 if high_scale else 16 if medium_scale else 8,
            "memory_each_gib": 128 if high_scale else 64 if medium_scale else 32,
            "role": "Shared-data query and ingestion compute; scale with concurrency and scan throughput.",
            "ports": "8040 HTTP, 9050 heartbeat, 9060 Thrift, 8060 bRPC, 9070 Starlet",
        },
        {
            "component": "Superset",
            "controller": "Deployment",
            "replicas": max(2, math.ceil(concurrent_users / 100)),
            "cpu_each": 8 if concurrent_users >= 200 else 4 if concurrent_users >= 50 else 2,
            "memory_each_gib": 16 if concurrent_users >= 200 else 8 if concurrent_users >= 50 else 4,
            "role": "Dashboard and SQL exploration web tier.",
            "ports": "8088 Web UI",
        },
    ]


def calculate_capacity(
    provider,
    daily_tb,
    peak_factor,
    retention_days,
    replication,
    concurrent_jobs,
    concurrent_users,
    zones,
    growth_percent,
):
    daily_tb = max(float(daily_tb), 0.001)
    peak_factor = max(float(peak_factor), 1)
    retention_days = max(int(retention_days), 1)
    replication = max(int(replication), 1)
    zones = max(int(zones), 1)
    growth_multiplier = 1 + max(float(growth_percent), 0) / 100
    average_mb_s = daily_tb * 1_000_000 / 86_400
    peak_mb_s = average_mb_s * peak_factor * growth_multiplier
    retained_tb = daily_tb * retention_days * replication * growth_multiplier
    components = _component_recommendations(
        daily_tb,
        peak_mb_s,
        int(concurrent_jobs),
        int(concurrent_users),
        zones,
    )
    cloud = CLOUD_NODE_PROFILES[provider]
    component_cpu = sum(
        item["replicas"] * item["cpu_each"] for item in components
    )
    component_memory = sum(
        item["replicas"] * item["memory_each_gib"] for item in components
    )
    system_nodes = max(3 if zones >= 3 else 1, zones)
    streaming_cpu = sum(
        item["replicas"] * item["cpu_each"]
        for item in components
        if item["component"].startswith("Flink")
    )
    analytics_cpu = sum(
        item["replicas"] * item["cpu_each"]
        for item in components
        if item["component"].startswith("StarRocks")
    )
    general_cpu = max(1, component_cpu - streaming_cpu - analytics_cpu)
    node_pools = [
        {
            "pool": "System / general",
            "node_type": cloud["system"]["name"],
            "nodes": max(system_nodes, math.ceil(general_cpu / (cloud["system"]["cpu"] * 0.7))),
            **cloud["system"],
        },
        {
            "pool": "Flink streaming",
            "node_type": cloud["streaming"]["name"],
            "nodes": max(zones, math.ceil(streaming_cpu / (cloud["streaming"]["cpu"] * 0.7))),
            **cloud["streaming"],
        },
        {
            "pool": "StarRocks analytics",
            "node_type": cloud["analytics"]["name"],
            "nodes": max(zones, math.ceil(analytics_cpu / (cloud["analytics"]["cpu"] * 0.7))),
            **cloud["analytics"],
        },
    ]
    return {
        "provider": provider,
        "average_mb_s": average_mb_s,
        "peak_mb_s": peak_mb_s,
        "retained_tb": retained_tb,
        "daily_tb": daily_tb,
        "total_component_cpu": component_cpu,
        "total_component_memory_gib": component_memory,
        "components": components,
        "node_pools": node_pools,
        "billing": cloud["billing"],
        "assumptions": [
            "1 TB uses decimal capacity (1,000,000 MB).",
            f"Peak throughput = average throughput × {peak_factor:g} peak factor × {growth_multiplier:.2f} growth headroom.",
            f"Retained storage = {daily_tb:g} TB/day × {retention_days} days × {replication} replicas × {growth_multiplier:.2f}.",
            "Worker sizing targets approximately 70% allocatable CPU to preserve failure and rollout headroom.",
            "Final production sizing must be validated with load tests, checkpoint duration, backpressure, query latency and cloud monitoring.",
        ],
    }
