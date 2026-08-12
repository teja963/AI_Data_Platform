import unittest
import json
from pathlib import Path

from core.job_alerts import (
    DEFAULT_SCAN_BATCH_SIZE,
    SCAN_INTERVAL_HOURS,
    _all_scan_targets,
    _execute_scan_targets,
    collect_microsoft_jobs,
    is_india_or_eligible_remote,
    match_job_title,
)
from core.job_sources import load_job_sources


class FakeMicrosoftClient:
    def search(self, query, start=0, sort_by=None):
        if start:
            return {"positions": []}
        return {
            "positions": [
                {
                    "id": 123,
                    "name": "AI Data Engineer II",
                    "locations": ["Remote"],
                    "postedTs": 1785608042,
                    "department": "Data and AI",
                    "workLocationOption": "remote",
                    "positionUrl": "/careers/job/123",
                },
                {
                    "id": 456,
                    "name": "Principal Data Engineer",
                    "locations": ["United States"],
                    "positionUrl": "/careers/job/456",
                },
            ]
        }

    def details(self, position_id):
        return {
            "id": position_id,
            "name": "AI Data Engineer II",
            "locations": ["Remote"],
            "workLocationOption": "remote",
            "department": "Data and AI",
            "postedTs": 1785608042,
            "positionUrl": f"/careers/job/{position_id}",
            "jobDescription": "<p>Build reliable AI data pipelines.</p>",
        }


class JobTitleMatchingTests(unittest.TestCase):
    def test_matches_requested_role(self):
        match = match_job_title("Senior AI Data Engineer")
        self.assertIsNotNone(match)
        self.assertEqual(match["score"], 100)

    def test_matches_related_data_platform_role(self):
        match = match_job_title("Software Engineer II, Data Intelligence")
        self.assertIsNotNone(match)

    def test_matches_ai_platform_engineer_role(self):
        match = match_job_title("AI Platform Engineer")
        self.assertIsNotNone(match)
        self.assertEqual(match["score"], 98)

    def test_excludes_non_midlevel_role(self):
        self.assertIsNone(match_job_title("Principal Data Engineer"))

    def test_excludes_staff_role(self):
        self.assertIsNone(match_job_title("Staff Data Engineer"))


class MicrosoftCollectionTests(unittest.TestCase):
    def test_collects_and_deduplicates_matching_jobs(self):
        jobs = collect_microsoft_jobs(client=FakeMicrosoftClient())
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["external_id"], "123")
        self.assertEqual(jobs[0]["work_mode"], "remote")
        self.assertEqual(jobs[0]["description"], "Build reliable AI data pipelines.")
        self.assertEqual(
            jobs[0]["job_url"],
            "https://apply.careers.microsoft.com/careers/job/123",
        )


class LocationEligibilityTests(unittest.TestCase):
    def test_includes_india_onsite_role(self):
        self.assertTrue(is_india_or_eligible_remote("Bengaluru, India", "onsite"))

    def test_includes_global_remote_role(self):
        self.assertTrue(is_india_or_eligible_remote("Remote", "remote"))

    def test_includes_apac_remote_role(self):
        self.assertTrue(is_india_or_eligible_remote("Remote - APAC", "remote"))

    def test_excludes_foreign_onsite_role(self):
        self.assertFalse(is_india_or_eligible_remote("London, United Kingdom", "onsite"))

    def test_includes_country_restricted_remote_role_for_visibility(self):
        self.assertTrue(
            is_india_or_eligible_remote("Remote - United States", "remote")
        )
        self.assertTrue(is_india_or_eligible_remote("Germany (remote)", "remote"))


class SourceRegistryTests(unittest.TestCase):
    def test_registry_has_broad_product_company_coverage(self):
        sources = load_job_sources()
        self.assertGreaterEqual(len(sources) + 1, 550)
        keys = {(source["platform"], source["slug"]) for source in sources}
        self.assertEqual(len(keys), len(sources))
        self.assertGreaterEqual(
            sum(bool(source.get("remote_friendly")) for source in sources),
            200,
        )

    def test_hourly_batch_refreshes_full_registry_within_scan_interval(self):
        self.assertGreaterEqual(
            DEFAULT_SCAN_BATCH_SIZE * SCAN_INTERVAL_HOURS,
            len(_all_scan_targets()),
        )

    def test_external_source_outage_returns_degraded_result_without_raising(self):
        def unavailable():
            raise RuntimeError("HTTP 404")

        result = _execute_scan_targets([("greenhouse:removed-board", unavailable)])

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["successful_sources"], 0)
        self.assertEqual(result["failed_sources"], 1)
        self.assertEqual(result["failures"][0]["source"], "greenhouse:removed-board")

    def test_every_priority_company_has_an_automated_scanner(self):
        priority_path = Path(__file__).resolve().parents[1] / "data" / "priority_companies.json"
        priority_companies = json.loads(priority_path.read_text(encoding="utf-8"))
        scanner_companies = {
            source["company"].casefold() for source in load_job_sources()
        } | {"microsoft"}

        missing = [
            company["company"]
            for company in priority_companies
            if company["company"].casefold() not in scanner_companies
        ]

        self.assertEqual(missing, [])

    def test_priority_company_sources_are_scanned_first(self):
        sources = load_job_sources()
        priority_path = Path(__file__).resolve().parents[1] / "data" / "priority_companies.json"
        priority_names = {
            company["company"].casefold()
            for company in json.loads(priority_path.read_text(encoding="utf-8"))
        }
        priority_keys = {
            f"{source['platform']}:{source['slug']}"
            for source in sources
            if source["company"].casefold() in priority_names
        }

        target_keys = [source for source, _run in _all_scan_targets()]

        self.assertEqual(target_keys[0], "microsoft_careers")
        self.assertEqual(set(target_keys[1 : len(priority_keys) + 1]), priority_keys)


if __name__ == "__main__":
    unittest.main()
