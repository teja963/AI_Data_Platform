import unittest

from core.job_enrichment import (
    extract_compensation,
    get_company_metadata,
    get_compensation_reports,
    get_interview_process,
)


class CompensationExtractionTests(unittest.TestCase):
    def test_extracts_published_range_and_total_reward_signals(self):
        details = extract_compensation(
            "The base salary is USD 120,000 - 160,000 per year. "
            "This role is eligible for an annual bonus, RSUs, health insurance, "
            "and paid time off."
        )

        self.assertEqual(details["published_ranges"], ["USD 120,000 - 160,000 per year"])
        self.assertTrue(details["equity_mentioned"])
        self.assertTrue(details["bonus_mentioned"])
        self.assertIn("Health insurance", details["benefits"])
        self.assertIn("Paid leave", details["benefits"])

    def test_does_not_invent_unpublished_compensation(self):
        details = extract_compensation("Build reliable batch and streaming pipelines.")
        self.assertEqual(details["published_ranges"], [])
        self.assertFalse(details["equity_mentioned"])
        self.assertFalse(details["bonus_mentioned"])


class CompanyEnrichmentTests(unittest.TestCase):
    def test_resolves_company_career_metadata(self):
        metadata = get_company_metadata("greenhouse:datadog", "Datadog")
        self.assertEqual(metadata["platform"], "Greenhouse")
        self.assertEqual(metadata["ticker"], "DDOG")
        self.assertIn("datadog", metadata["careers_url"])

    def test_does_not_invent_interview_fallback(self):
        process = get_interview_process("Example", "Data Engineer")
        self.assertIsNone(process)

    def test_loads_sourced_company_interview_process(self):
        process = get_interview_process("NielsenIQ", "Senior Data Engineer")
        self.assertTrue(process["is_company_verified"])
        self.assertEqual(process["confidence"], "medium-high")
        self.assertGreaterEqual(len(process["sources"]), 1)
        self.assertIn("Python and SQL", process["question_categories"])
        self.assertIn(
            "Find the longest substring without repeating characters.",
            process["questions"],
        )

    def test_loads_sourced_compensation_reports(self):
        reports = get_compensation_reports("Experian")
        self.assertEqual(reports[0]["role"], "Senior Data Engineer")
        self.assertEqual(reports[0]["minimum_lpa"], 27)
        self.assertIn("ambitionbox.com", reports[0]["url"])


if __name__ == "__main__":
    unittest.main()
