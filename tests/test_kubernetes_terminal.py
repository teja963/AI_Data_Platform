import unittest

from core.kubernetes_simulator import (
    create_cluster,
    create_deployment,
    create_namespace,
)
from modules.devops.simulator_ui import _terminal_run


class KubernetesTerminalContextTests(unittest.TestCase):
    def setUp(self):
        self.state = create_cluster(
            "terminal-test",
            "On-Premises",
            "local",
            2,
            4,
            8192,
            80,
        )
        create_namespace(self.state, "analytics")
        create_deployment(
            self.state,
            "api",
            "example/api:1",
            1,
            "analytics",
        )
        self.first = {
            "mode": "cluster",
            "namespace": "default",
            "pod": None,
            "cwd": "/app",
        }
        self.second = dict(self.first)

    def test_terminal_namespace_contexts_are_independent(self):
        self.state, output, _ = _terminal_run(
            self.state,
            "oc project analytics",
            self.first,
        )
        self.assertIn("analytics", output)
        self.assertEqual(self.first["namespace"], "analytics")
        self.assertEqual(self.second["namespace"], "default")

    def test_only_selected_terminal_enters_pod_shell(self):
        pod_name = next(
            pod["name"]
            for pod in self.state["pods"].values()
            if pod["namespace"] == "analytics"
        )
        self.first["namespace"] = "analytics"
        self.state, output, _ = _terminal_run(
            self.state,
            f"kubectl exec -it {pod_name} -- sh",
            self.first,
        )
        self.assertIn("Connected", output)
        self.assertEqual(self.first["mode"], "pod")
        self.assertEqual(self.second["mode"], "cluster")


if __name__ == "__main__":
    unittest.main()
