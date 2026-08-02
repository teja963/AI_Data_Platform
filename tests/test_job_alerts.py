import unittest

from core.job_alerts import collect_microsoft_jobs, match_job_title


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


if __name__ == "__main__":
    unittest.main()
