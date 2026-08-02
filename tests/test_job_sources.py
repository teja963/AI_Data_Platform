import unittest
from unittest.mock import patch

from core.job_sources import collect_source_jobs


class JobSourceAdapterTests(unittest.TestCase):
    @patch("core.job_sources._get_json")
    def test_greenhouse_adapter_normalizes_job(self, get_json):
        get_json.return_value = {
            "jobs": [
                {
                    "id": 101,
                    "title": "Data Engineer",
                    "location": {"name": "Bengaluru, India"},
                    "content": "<p>Build data pipelines.</p>",
                    "absolute_url": "https://example.com/jobs/101",
                    "updated_at": "2026-08-01T12:00:00Z",
                }
            ]
        }
        source = {
            "company": "Example",
            "platform": "greenhouse",
            "slug": "example",
        }

        jobs = collect_source_jobs(source)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["source"], "greenhouse:example")
        self.assertEqual(jobs[0]["location"], "Bengaluru, India")
        self.assertEqual(jobs[0]["description"], "Build data pipelines.")

    @patch("core.job_sources._get_json")
    def test_ashby_adapter_normalizes_remote_job(self, get_json):
        get_json.return_value = {
            "jobs": [
                {
                    "id": "abc",
                    "title": "AI Data Engineer",
                    "location": "Remote",
                    "workplaceType": "Remote",
                    "descriptionPlain": "Build AI data products.",
                    "jobUrl": "https://jobs.ashbyhq.com/example/abc",
                    "publishedAt": "2026-08-01T12:00:00Z",
                }
            ]
        }
        source = {
            "company": "Example AI",
            "platform": "ashby",
            "slug": "example-ai",
        }

        jobs = collect_source_jobs(source)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["work_mode"], "Remote")
        self.assertEqual(jobs[0]["company"], "Example AI")


if __name__ == "__main__":
    unittest.main()
