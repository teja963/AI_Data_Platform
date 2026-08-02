import unittest

from core.job_alerts import (
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

    def test_excludes_country_restricted_remote_role(self):
        self.assertFalse(
            is_india_or_eligible_remote("Remote - United States", "remote")
        )
        self.assertFalse(is_india_or_eligible_remote("Germany (remote)", "remote"))


class SourceRegistryTests(unittest.TestCase):
    def test_registry_has_broad_product_company_coverage(self):
        sources = load_job_sources()
        self.assertGreaterEqual(len(sources) + 1, 200)
        keys = {(source["platform"], source["slug"]) for source in sources}
        self.assertEqual(len(keys), len(sources))


if __name__ == "__main__":
    unittest.main()
