import unittest
import json
from datetime import datetime
from unittest.mock import patch

from core.job_sources import (
    collect_source_jobs,
    parse_datetime,
    parse_relative_posted_datetime,
)


class JobSourceAdapterTests(unittest.TestCase):
    class _FakeResponse:
        def __init__(self, payload=b""):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.payload

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
                    "first_published": "2026-07-30T08:00:00Z",
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
        self.assertEqual(jobs[0]["posted_at"], datetime(2026, 7, 30, 8))

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
                    "postedOn": "Posted 2 Days Ago",
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
        self.assertIsNotNone(jobs[0]["posted_at"])

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
                    "posted_date": "May 21, 2026",
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
        self.assertEqual(jobs[0]["posted_at"], datetime(2026, 5, 21))
        self.assertEqual(
            jobs[0]["job_url"],
            "https://www.amazon.jobs/en/jobs/A123/ai-platform-engineer",
        )

    @patch("core.job_sources._get_json")
    def test_oracle_hcm_adapter_normalizes_public_requisition(self, get_json):
        get_json.return_value = {
            "items": [
                {
                    "TotalJobsCount": 1,
                    "requisitionList": [
                        {
                            "Id": "210588633",
                            "Title": "Data Engineer",
                            "PostedDate": "2026-08-06",
                            "PrimaryLocation": "Pune, Maharashtra, India",
                            "JobFamily": "Software Engineering",
                            "ShortDescriptionStr": "Build scalable data products.",
                        }
                    ],
                }
            ]
        }
        source = {
            "company": "JPMorgan Chase",
            "platform": "oraclehcm",
            "slug": "jpmc/CX_1001",
            "domain": "jpmc.fa.oraclecloud.com",
            "site_number": "CX_1001",
            "site_path": "CX_1001",
            "queries": ["data engineer"],
        }

        jobs = collect_source_jobs(source)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["external_id"], "210588633")
        self.assertEqual(jobs[0]["posted_at"], datetime(2026, 8, 6))
        self.assertIn("/sites/CX_1001/job/210588633", jobs[0]["job_url"])

    @patch("core.job_sources._get_text")
    def test_apple_adapter_reads_embedded_search_payload(self, get_text):
        payload = {
            "loaderData": {
                "search": {
                    "totalRecords": 1,
                    "searchResults": [
                        {
                            "positionId": "200123456",
                            "postingTitle": "Data Engineer",
                            "jobSummary": "Build Apple data products.",
                            "locations": [{"name": "India"}],
                            "postDateInGMT": "2026-08-05T17:13:13.208Z",
                            "transformedPostingTitle": "data-engineer",
                            "team": {"teamName": "Machine Learning"},
                        }
                    ],
                }
            }
        }
        encoded = json.dumps(json.dumps(payload))
        get_text.return_value = (
            f"<script>window.__staticRouterHydrationData = JSON.parse({encoded})</script>"
        )
        source = {
            "company": "Apple",
            "platform": "apple",
            "slug": "apple-jobs",
            "queries": ["data engineer"],
        }

        jobs = collect_source_jobs(source)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["location"], "India")
        self.assertEqual(jobs[0]["posted_at"], datetime(2026, 8, 5, 17, 13, 13, 208000))

    @patch("core.job_sources.build_opener")
    def test_eightfold_adapter_bootstraps_session_and_normalizes_jobs(self, build_opener):
        payload = json.dumps(
            {
                "status": 200,
                "data": {
                    "positions": [
                        {
                            "id": 123,
                            "name": "AI Platform Engineer",
                            "locations": ["Hyderabad, India"],
                            "positionUrl": "/careers/job/123",
                            "postedTs": 1786060800,
                        }
                    ]
                },
            }
        ).encode()

        class FakeOpener:
            def __init__(self):
                self.calls = 0

            def open(self, *_args, **_kwargs):
                self.calls += 1
                return JobSourceAdapterTests._FakeResponse(
                    b"{}" if self.calls == 1 else payload
                )

        opener = FakeOpener()
        build_opener.return_value = opener
        source = {
            "company": "Qualcomm",
            "platform": "eightfold",
            "slug": "qualcomm.com",
            "base_url": "https://careers.qualcomm.com",
            "domain": "qualcomm.com",
            "locations": ["India"],
            "queries": ["AI platform"],
        }

        jobs = collect_source_jobs(source)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["location"], "Hyderabad, India")
        self.assertEqual(jobs[0]["job_url"], "https://careers.qualcomm.com/careers/job/123")

    @patch("core.job_sources._get_text")
    def test_google_adapter_reads_server_rendered_job_cards(self, get_text):
        get_text.return_value = """
        <li class="lLd3Je">
          <h3 class="QJPWVe">Data Engineer</h3>
          <span class="r0wTof ">Bengaluru, Karnataka, India</span>
          <a href="jobs/results/123-data-engineer?q=data+engineer"></a>
        </li>
        """
        source = {
            "company": "Google",
            "platform": "google",
            "slug": "google-careers",
            "locations": ["India"],
            "queries": ["data engineer"],
        }

        jobs = collect_source_jobs(source)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["external_id"], "123")
        self.assertEqual(jobs[0]["location"], "Bengaluru, Karnataka, India")

    @patch("core.job_sources._post_json")
    def test_walmart_adapter_normalizes_graphql_jobs(self, post_json):
        post_json.return_value = {
            "data": {
                "jobSearch": {
                    "searchResults": [
                        {
                            "jobId": "R-123",
                            "jobTitle": "Data Engineer",
                            "brand": "Walmart",
                            "location": [{"storeName": "BANGALORE GLOBAL TECH"}],
                        }
                    ]
                }
            }
        }
        source = {
            "company": "Walmart",
            "platform": "walmart",
            "slug": "walmart-careers",
            "query_id": "query-id",
            "populations": ["EXTERNAL"],
            "queries": ["data engineer"],
        }

        jobs = collect_source_jobs(source)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["external_id"], "R-123")
        self.assertEqual(jobs[0]["location"], "BANGALORE GLOBAL TECH")

    @patch("core.job_sources._get_text")
    def test_successfactors_rss_adapter_normalizes_jobs(self, get_text):
        get_text.return_value = """
        <rss><channel><item>
          <title>Data Engineer (Bengaluru, India)</title>
          <description>Build data products.</description>
          <pubDate>Sat, 08 Aug 2026 02:00:00 GMT</pubDate>
          <link>https://example.com/job/data-engineer/4079150/</link>
        </item></channel></rss>
        """
        source = {
            "company": "LG",
            "platform": "successfactors_rss",
            "slug": "lg-global",
            "feed_url": "https://example.com/feed",
        }

        jobs = collect_source_jobs(source)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["external_id"], "4079150")
        self.assertEqual(jobs[0]["location"], "Bengaluru, India")
        self.assertEqual(jobs[0]["posted_at"], datetime(2026, 8, 8, 2))

    def test_parses_absolute_and_relative_source_dates(self):
        self.assertEqual(parse_datetime("May 21, 2026"), datetime(2026, 5, 21))
        reference = datetime(2026, 8, 8, 12)
        self.assertEqual(
            parse_relative_posted_datetime("Posted Today", now=reference),
            datetime(2026, 8, 8),
        )
        self.assertEqual(
            parse_relative_posted_datetime("Posted 2 Days Ago", now=reference),
            datetime(2026, 8, 6, 12),
        )


if __name__ == "__main__":
    unittest.main()
