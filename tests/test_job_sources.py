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

    @patch("core.job_sources._post_json")
    def test_workday_adapter_searches_and_deduplicates_jobs(self, post_json):
        post_json.return_value = {
            "total": 1,
            "jobPostings": [
                {
                    "title": "Senior Data Engineer",
                    "externalPath": "/job/India/Senior-Data-Engineer_JR123",
                    "locationsText": "Bengaluru, India",
                }
            ],
        }
        source = {
            "company": "Example Workday",
            "platform": "workday",
            "slug": "example/External",
            "host": "example.wd1.myworkdayjobs.com",
            "tenant": "example",
            "site": "External",
        }

        jobs = collect_source_jobs(source)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["source"], "workday:example/External")
        self.assertEqual(jobs[0]["external_id"], "Senior-Data-Engineer_JR123")
        self.assertIn("/en-US/External/job/", jobs[0]["job_url"])

    @patch("core.job_sources._get_json")
    def test_amazon_adapter_normalizes_public_search_result(self, get_json):
        get_json.return_value = {
            "hits": 1,
            "jobs": [
                {
                    "id_icims": "A123",
                    "title": "AI Platform Engineer",
                    "location": "IND, KA, Bangalore",
                    "job_path": "/en/jobs/A123/ai-platform-engineer",
                    "description_short": "<p>Build AI data platforms.</p>",
                    "posted_date": "2026-08-01T12:00:00Z",
                }
            ],
        }
        source = {
            "company": "Amazon",
            "platform": "amazon",
            "slug": "amazon-jobs",
        }

        jobs = collect_source_jobs(source)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["external_id"], "A123")
        self.assertEqual(jobs[0]["description"], "Build AI data platforms.")
        self.assertEqual(
            jobs[0]["job_url"],
            "https://www.amazon.jobs/en/jobs/A123/ai-platform-engineer",
        )


if __name__ == "__main__":
    unittest.main()
