import unittest

from core.kubernetes_simulator import (
    create_cluster,
    create_deployment,
    create_namespace,
    create_pod,
    delete_pod,
    deploy_data_platform_blueprint,
    execute_command,
    execute_pod_command,
    namespace_rows,
    normalize_cluster_state,
    set_node_status,
)


class KubernetesSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.state = create_cluster(
            "test-cluster",
            "On-Premises",
            "local",
            worker_count=2,
            cpu_per_worker=2,
            memory_per_worker_mi=2048,
            storage_per_worker_gi=40,
        )

    def test_controller_reconciles_deleted_pod(self):
        create_deployment(self.state, "api", "example/api:1", replicas=3)
        pod = next(iter(self.state["pods"].values()))
        pod_key = f"{pod['namespace']}/{pod['name']}"

        delete_pod(self.state, pod["name"], pod["namespace"])

        self.assertEqual(len(self.state["pods"]), 3)
        self.assertIn(pod_key, self.state["pods"])
        self.assertIsNot(pod, self.state["pods"][pod_key])

    def test_node_failure_reschedules_managed_workload(self):
        create_deployment(self.state, "worker", "example/worker:1", replicas=4)
        failed_node = next(node for node in self.state["nodes"] if node["role"] == "worker")

        set_node_status(self.state, failed_node["name"], "NotReady")

        self.assertTrue(
            all(pod.get("node") != failed_node["name"] for pod in self.state["pods"].values())
        )
        self.assertEqual(len(self.state["pods"]), 4)

    def test_terminal_mutates_virtual_state(self):
        state, output = execute_command(
            self.state,
            "kubectl create deployment kafka --image=bitnami/kafka:latest --replicas=3",
        )
        self.assertIn("created", output)
        self.assertIn("default/kafka", state["deployments"])
        self.assertEqual(len(state["pods"]), 3)

        state, output = execute_command(state, "kubectl scale deployment/kafka --replicas=5")
        self.assertIn("scaled", output)
        self.assertEqual(state["deployments"]["default/kafka"]["replicas"], 5)

    def test_standalone_pod_can_be_created_in_any_namespace(self):
        create_namespace(self.state, "sandbox")
        pod = create_pod(
            self.state,
            "utility",
            "alpine:latest",
            namespace="sandbox",
        )

        self.assertEqual(pod["namespace"], "sandbox")
        self.assertEqual(pod["name"], "sandbox-utility")
        self.assertIn("sandbox/sandbox-utility", self.state["pods"])

    def test_pod_output_uses_namespace_names_and_concise_columns(self):
        create_namespace(self.state, "development")
        create_deployment(
            self.state,
            "starrocks-cn",
            "starrocks/cn:latest",
            replicas=3,
            namespace="development",
        )

        _, output = execute_command(self.state, "oc get pods -A")
        header = output.splitlines()[0]
        self.assertEqual(header.split(), ["NAME", "READY", "STATUS", "RESTARTS", "NODE"])
        self.assertIn("development-starrocks-cn-01", output)
        self.assertIn("development-starrocks-cn-02", output)
        self.assertIn("development-starrocks-cn-03", output)

    def test_pod_scheduling_ignores_virtual_cpu_and_memory_limits(self):
        pod = create_pod(
            self.state,
            "large",
            "example/large:1",
            cpu_request_m=1_000_000,
            memory_request_mi=1_000_000,
        )

        self.assertEqual(pod["status"], "Running")
        self.assertIsNotNone(pod["node"])

    def test_pod_resource_commands_use_cores_and_gib(self):
        pod = create_pod(
            self.state,
            "metrics",
            "example/metrics:1",
            cpu_request_m=500,
            memory_request_mi=2048,
        )
        top_output = execute_pod_command(
            self.state,
            "default",
            pod["name"],
            "top",
        )
        free_output = execute_pod_command(
            self.state,
            "default",
            pod["name"],
            "free",
        )

        self.assertIn("0.50 cores", top_output)
        self.assertIn("2.00 GiB", top_output)
        self.assertIn("GiB", free_output)
        self.assertNotIn("MiB", top_output)

    def test_manifest_and_helm_are_simulated(self):
        manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: consumer
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: consumer
          image: example/consumer:1
"""
        state, output = execute_command(self.state, "kubectl apply -f -", manifest)
        self.assertIn("configured", output)
        self.assertIn("default/consumer", state["deployments"])

        state, output = execute_command(
            state,
            "helm install airflow apache-airflow/airflow --replica-count=2",
        )
        self.assertIn("deployed", output)
        self.assertIn("default/airflow", state["helm_releases"])

    def test_shell_operators_are_rejected(self):
        state, output = execute_command(self.state, "kubectl get pods; whoami")
        self.assertIs(state, self.state)
        self.assertIn("disabled", output)

    def test_virtual_pod_shell_inspects_container_state(self):
        state, _ = execute_command(
            self.state,
            "kubectl create deployment api --image=example/api:1 --replicas=1 --heap-memory=512",
        )
        pod_name = next(iter(state["pods"].values()))["name"]

        state, output = execute_command(
            state,
            f"kubectl exec {pod_name} -- printenv JAVA_TOOL_OPTIONS",
        )
        self.assertIn("-Xmx512m", output)

        state, output = execute_command(
            state,
            f"kubectl exec {pod_name} -- cat /etc/os-release",
        )
        self.assertIn("Virtual Kubernetes Linux", output)

    def test_common_inspection_and_rollout_commands(self):
        state, _ = execute_command(
            self.state,
            "kubectl create deployment api --image=example/api:1",
        )
        state, output = execute_command(state, "kubectl get deployment api -o json")
        self.assertIn('"image": "example/api:1"', output)

        state, output = execute_command(
            state,
            "kubectl set image deployment/api api=example/api:2",
        )
        self.assertIn("image updated", output)
        self.assertEqual(state["deployments"]["default/api"]["image"], "example/api:2")

        state, output = execute_command(
            state,
            "kubectl rollout status deployment/api",
        )
        self.assertIn("successfully rolled out", output)

    def test_namespace_allows_unlimited_workload_objects(self):
        create_namespace(self.state, "analytics")
        create_deployment(
            self.state,
            "worker",
            "example/worker:1",
            replicas=20,
            namespace="analytics",
            cpu_request_m=1000,
            memory_request_mi=2048,
        )
        self.assertEqual(len(self.state["pods"]), 20)
        self.assertTrue(
            all(pod["status"] == "Running" for pod in self.state["pods"].values())
        )

    def test_initial_state_has_only_unlimited_builtin_namespaces(self):
        self.assertEqual(
            set(self.state["namespaces"]),
            {"default", "kube-system", "kube-public", "kube-node-lease"},
        )
        for namespace in self.state["namespaces"].values():
            self.assertEqual(namespace["cpu_quota_m"], 0)
            self.assertEqual(namespace["memory_quota_mi"], 0)
            self.assertEqual(namespace["storage_quota_gi"], 0)
            self.assertEqual(namespace["pod_quota"], 0)
            self.assertEqual(namespace["default_cpu_m"], 0)
            self.assertEqual(namespace["default_memory_mi"], 0)

    def test_namespace_creation_is_visible_without_resource_allocations(self):
        create_namespace(
            self.state,
            "analytics",
            owner="Data Team",
            labels={"team": "analytics"},
        )

        analytics = next(
            row for row in namespace_rows(self.state)
            if row["Namespace"] == "analytics"
        )
        self.assertEqual(analytics["Owner"], "Data Team")
        self.assertEqual(analytics["Labels"], "team=analytics")
        self.assertNotIn("CPU Allocated", analytics)
        self.assertNotIn("Memory Allocated", analytics)

        state, output = execute_command(self.state, "oc create namespace streaming")
        self.assertIn("streaming", state["namespaces"])
        _, output = execute_command(state, "oc get namespaces")
        self.assertIn("analytics", output)
        self.assertIn("streaming", output)
        self.assertNotIn("CPU", output)
        self.assertNotIn("MEMORY", output)

    def test_data_platform_blueprint_has_standard_components_and_ports(self):
        create_namespace(self.state, "development")
        state = deploy_data_platform_blueprint(
            self.state,
            "development",
            starrocks_compute_nodes=3,
        )
        self.assertEqual(state["deployments"]["development/starrocks-fe"]["replicas"], 3)
        self.assertEqual(state["deployments"]["development/starrocks-cn"]["replicas"], 3)
        self.assertIn("development/postgresql", state["services"])
        self.assertIn("development/flink-jobmanager", state["services"])
        self.assertIn("development/superset", state["services"])
        self.assertNotIn("development/data-api", state["deployments"])
        fe_ports = {
            item["port"]
            for item in state["services"]["development/starrocks-fe"]["ports"]
        }
        self.assertEqual(fe_ports, {8030, 9010, 9020, 9030})

        state = deploy_data_platform_blueprint(
            state,
            "development",
            starrocks_compute_nodes=4,
        )
        self.assertEqual(state["deployments"]["development/starrocks-cn"]["replicas"], 4)
        self.assertTrue(state["last_blueprint_result"]["updated"])

    def test_blueprint_can_deploy_selected_components_only(self):
        create_namespace(self.state, "streaming")
        state = deploy_data_platform_blueprint(
            self.state,
            "streaming",
            components=["Flink"],
        )

        self.assertIn("streaming/flink-jobmanager", state["deployments"])
        self.assertIn("streaming/flink-taskmanager", state["deployments"])
        self.assertNotIn("streaming/postgresql", state["deployments"])
        self.assertNotIn("streaming/starrocks-cn", state["deployments"])

    def test_old_lab_is_reset_during_version_migration(self):
        self.state["simulator_version"] = 2
        self.state["namespaces"]["old-team"] = {"name": "old-team"}
        self.state["pods"]["old-team/old-pod"] = {
            "name": "old-pod",
            "namespace": "old-team",
        }

        migrated = normalize_cluster_state(self.state)

        self.assertNotIn("old-team", migrated["namespaces"])
        self.assertEqual(migrated["pods"], {})

    def test_version_four_lab_is_repaired_without_losing_platform_workloads(self):
        create_namespace(self.state, "analytics")
        self.state = deploy_data_platform_blueprint(
            self.state,
            "analytics",
            components=["PostgreSQL", "Flink", "StarRocks", "Superset"],
        )
        create_deployment(
            self.state,
            "data-api",
            "example/data-api:1",
            replicas=2,
            namespace="analytics",
        )
        for pod in self.state["pods"].values():
            if pod.get("owner") != "data-api":
                pod["status"] = "Pending"
                pod["node"] = None
        self.state["simulator_version"] = 4

        migrated = normalize_cluster_state(self.state)

        self.assertIn("analytics/starrocks-cn", migrated["deployments"])
        self.assertNotIn("analytics/data-api", migrated["deployments"])
        self.assertTrue(migrated["pods"])
        self.assertTrue(
            all(pod["status"] == "Running" for pod in migrated["pods"].values())
        )
        self.assertTrue(
            all(pod.get("owner") != "data-api" for pod in migrated["pods"].values())
        )


if __name__ == "__main__":
    unittest.main()
