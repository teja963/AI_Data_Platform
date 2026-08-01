import unittest

from core.kubernetes_capacity import calculate_capacity, profile_inputs


class KubernetesCapacityTests(unittest.TestCase):
    def test_100_tb_profile_uses_throughput_and_retention_math(self):
        plan = calculate_capacity(
            provider="AWS (EKS)",
            **profile_inputs("100 TB / Day"),
        )
        self.assertAlmostEqual(plan["average_mb_s"], 1157.407, places=2)
        self.assertAlmostEqual(plan["peak_mb_s"], 5208.333, places=2)
        self.assertEqual(plan["retained_tb"], 40500)

    def test_large_plan_scales_streaming_and_analytics_components(self):
        plan = calculate_capacity(
            provider="Google Cloud (GKE)",
            **profile_inputs("Large Production"),
        )
        components = {
            item["component"]: item for item in plan["components"]
        }
        self.assertGreater(components["Flink TaskManager"]["replicas"], 3)
        self.assertEqual(components["StarRocks FE"]["replicas"], 3)
        self.assertGreaterEqual(components["StarRocks CN"]["replicas"], 3)
        self.assertNotIn("Data API", components)
        self.assertTrue(all(item["basis"] for item in plan["components"]))

    def test_state_and_hot_data_assumptions_scale_recommendations(self):
        baseline = calculate_capacity(
            provider="AWS (EKS)",
            **profile_inputs("Medium Production"),
            flink_state_hours=1,
            flink_state_ratio_percent=1,
            hot_data_percent=5,
        )
        state_heavy = calculate_capacity(
            provider="AWS (EKS)",
            **profile_inputs("Medium Production"),
            flink_state_hours=24,
            flink_state_ratio_percent=30,
            hot_data_percent=50,
            starrocks_cache_percent=50,
        )
        baseline_components = {
            item["component"]: item for item in baseline["components"]
        }
        heavy_components = {
            item["component"]: item for item in state_heavy["components"]
        }
        self.assertGreater(
            heavy_components["Flink TaskManager"]["replicas"],
            baseline_components["Flink TaskManager"]["replicas"],
        )
        self.assertGreater(
            heavy_components["StarRocks CN"]["replicas"],
            baseline_components["StarRocks CN"]["replicas"],
        )

    def test_plan_has_three_separate_node_pools(self):
        plan = calculate_capacity(
            provider="Azure (AKS)",
            **profile_inputs("Medium Production"),
        )
        self.assertEqual(
            {item["pool"] for item in plan["node_pools"]},
            {"System / general", "Flink streaming", "StarRocks analytics"},
        )
        self.assertTrue(all(item["nodes"] >= 3 for item in plan["node_pools"]))


if __name__ == "__main__":
    unittest.main()
