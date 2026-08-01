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
    retained_tb,
    concurrent_jobs,
    concurrent_users,
    zones,
    event_size_kb,
    flink_state_hours,
    flink_state_ratio_percent,
    flink_state_memory_percent,
    hot_data_percent,
    compression_ratio,
    starrocks_cache_percent,
):
    records_per_second = peak_mb_s * 1024 / max(event_size_kb, 0.1)
    flink_parallelism = max(
        zones * 2,
        math.ceil(peak_mb_s / 12),
        concurrent_jobs * 2,
    )
    flink_state_gib = (
        peak_mb_s
        * 3600
        * max(flink_state_hours, 0)
        / 1024
        * max(flink_state_ratio_percent, 0)
        / 100
    )
    taskmanager_cpu = 8 if peak_mb_s >= 250 else 4
    taskmanager_memory = 64 if flink_state_gib >= 256 else 32 if peak_mb_s >= 100 else 16
    slots_per_taskmanager = max(2, taskmanager_cpu // 2)
    taskmanagers = max(
        zones,
        math.ceil(flink_parallelism / slots_per_taskmanager),
        math.ceil(flink_state_gib / 500),
        math.ceil(
            flink_state_gib
            * max(flink_state_memory_percent, 0)
            / 100
            / max(taskmanager_memory * 0.6, 1)
        ),
    )
    logical_hot_gib = (
        retained_tb
        * 1024
        * max(hot_data_percent, 0)
        / 100
        / max(compression_ratio, 1)
    )
    starrocks_cpu = 32 if peak_mb_s >= 500 or concurrent_users >= 200 else 16
    starrocks_memory = 128 if starrocks_cpu == 32 else 64
    starrocks_compute = max(
        3,
        zones,
        math.ceil(peak_mb_s / 100),
        math.ceil(concurrent_users / 20),
        math.ceil(
            logical_hot_gib
            * max(starrocks_cache_percent, 0)
            / 100
            / 2000
        ),
    )
    high_scale = peak_mb_s >= 500 or daily_tb >= 50
    postgres_connections = max(50, concurrent_users * 3 + concurrent_jobs * 5)
    superset_replicas = max(2, zones, math.ceil(concurrent_users / 40))
    return [
        {
            "component": "PostgreSQL",
            "controller": "StatefulSet",
            "replicas": 3 if zones >= 3 else 2,
            "cpu_each": 8 if postgres_connections >= 500 else 4,
            "memory_each_gib": 32 if postgres_connections >= 500 else 16,
            "role": "Metadata, configuration and transactional state—not the raw petabyte analytical store.",
            "ports": "5432 SQL",
            "basis": f"Approximately {postgres_connections} metadata/application connections with HA.",
        },
        {
            "component": "Flink Operator",
            "controller": "Deployment",
            "replicas": 2 if zones >= 3 else 1,
            "cpu_each": 2,
            "memory_each_gib": 4,
            "role": "Reconciles Flink Kubernetes resources.",
            "ports": "8080 metrics, 9443 webhook",
            "basis": "One active operator plus an HA replica for multi-zone production.",
        },
        {
            "component": "Flink JobManager",
            "controller": "Deployment",
            "replicas": 2 if zones >= 3 else 1,
            "cpu_each": 8 if concurrent_jobs >= 30 else 4,
            "memory_each_gib": min(64, max(8, math.ceil(8 + concurrent_jobs * 0.5))),
            "role": "Coordinates jobs, checkpoints and recovery.",
            "ports": "6123 RPC, 6124 BLOB, 8081 Web UI",
            "basis": f"{concurrent_jobs} concurrent jobs; JobManagers coordinate but do not process records.",
        },
        {
            "component": "Flink TaskManager",
            "controller": "Deployment",
            "replicas": taskmanagers,
            "cpu_each": taskmanager_cpu,
            "memory_each_gib": taskmanager_memory,
            "role": "Processes streaming records; scale from measured throughput and backpressure.",
            "ports": "6122 RPC/data",
            "basis": (
                f"{peak_mb_s:.1f} MB/s peak, ~{records_per_second:,.0f} events/s, "
                f"parallelism {flink_parallelism}, {flink_state_gib:,.0f} GiB state "
                f"with {flink_state_memory_percent:g}% expected in memory."
            ),
        },
        {
            "component": "StarRocks FE",
            "controller": "StatefulSet",
            "replicas": 3,
            "cpu_each": 16 if high_scale else 8,
            "memory_each_gib": 32 if high_scale else 16,
            "role": "Metadata, SQL planning and cluster coordination.",
            "ports": "8030 HTTP, 9010 edit log, 9020 RPC, 9030 MySQL",
            "basis": "Three FE replicas provide quorum; FE capacity follows catalog and planning load.",
        },
        {
            "component": "StarRocks CN",
            "controller": "Deployment",
            "replicas": starrocks_compute,
            "cpu_each": starrocks_cpu,
            "memory_each_gib": starrocks_memory,
            "role": "Shared-data query and ingestion compute; scale with concurrency and scan throughput.",
            "ports": "8040 HTTP, 9050 heartbeat, 9060 Thrift, 8060 bRPC, 9070 Starlet",
            "basis": (
                f"{logical_hot_gib:,.0f} GiB compressed hot working set, "
                f"{starrocks_cache_percent:g}% local-cache coverage, "
                f"{concurrent_users} users and {peak_mb_s:.1f} MB/s ingestion."
            ),
        },
        {
            "component": "Superset",
            "controller": "Deployment",
            "replicas": superset_replicas,
            "cpu_each": 4 if concurrent_users >= 100 else 2,
            "memory_each_gib": 8 if concurrent_users >= 100 else 4,
            "role": "Dashboard and SQL exploration web tier.",
            "ports": "8088 Web UI",
            "basis": f"Approximately 40 active dashboard users per web/worker replica.",
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
    event_size_kb=1.0,
    flink_state_hours=6.0,
    flink_state_ratio_percent=10.0,
    flink_state_memory_percent=10.0,
    hot_data_percent=20.0,
    compression_ratio=3.0,
    starrocks_cache_percent=5.0,
    target_utilization_percent=65.0,
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
        retained_tb,
        int(concurrent_jobs),
        int(concurrent_users),
        zones,
        float(event_size_kb),
        float(flink_state_hours),
        float(flink_state_ratio_percent),
        float(flink_state_memory_percent),
        float(hot_data_percent),
        float(compression_ratio),
        float(starrocks_cache_percent),
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
    streaming_memory = sum(
        item["replicas"] * item["memory_each_gib"]
        for item in components
        if item["component"].startswith("Flink")
    )
    analytics_memory = sum(
        item["replicas"] * item["memory_each_gib"]
        for item in components
        if item["component"].startswith("StarRocks")
    )
    general_memory = max(
        1,
        component_memory - streaming_memory - analytics_memory,
    )
    utilization = min(0.85, max(0.3, float(target_utilization_percent) / 100))

    def required_nodes(pool, cpu, memory, minimum):
        return max(
            minimum,
            math.ceil(cpu / (pool["cpu"] * utilization)),
            math.ceil(memory / (pool["memory"] * utilization)),
        )

    node_pools = [
        {
            "pool": "System / general",
            "node_type": cloud["system"]["name"],
            "nodes": required_nodes(
                cloud["system"],
                general_cpu,
                general_memory,
                system_nodes,
            ),
            **cloud["system"],
        },
        {
            "pool": "Flink streaming",
            "node_type": cloud["streaming"]["name"],
            "nodes": required_nodes(
                cloud["streaming"],
                streaming_cpu,
                streaming_memory,
                zones,
            ),
            **cloud["streaming"],
        },
        {
            "pool": "StarRocks analytics",
            "node_type": cloud["analytics"]["name"],
            "nodes": required_nodes(
                cloud["analytics"],
                analytics_cpu,
                analytics_memory,
                zones,
            ),
            **cloud["analytics"],
        },
    ]
    return {
        "provider": provider,
        "average_mb_s": average_mb_s,
        "peak_mb_s": peak_mb_s,
        "peak_events_per_second": peak_mb_s * 1024 / max(float(event_size_kb), 0.1),
        "flink_state_gib": (
            peak_mb_s
            * 3600
            * max(float(flink_state_hours), 0)
            / 1024
            * max(float(flink_state_ratio_percent), 0)
            / 100
        ),
        "starrocks_hot_gib": (
            retained_tb
            * 1024
            * max(float(hot_data_percent), 0)
            / 100
            / max(float(compression_ratio), 1)
        ),
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
            f"Flink assumes {event_size_kb:g} KiB events, {flink_state_hours:g} state hours and {flink_state_ratio_percent:g}% state retention.",
            f"Flink assumes {flink_state_memory_percent:g}% of managed state is memory-resident; the remainder uses local state disks and checkpoints.",
            f"StarRocks assumes {hot_data_percent:g}% hot data, {compression_ratio:g}:1 compression and {starrocks_cache_percent:g}% local-cache coverage in shared-data mode.",
            f"Worker sizing targets {target_utilization_percent:g}% CPU and memory utilization to preserve failure and rollout headroom.",
            "Final production sizing must be validated with load tests, checkpoint duration, backpressure, query latency and cloud monitoring.",
        ],
    }
