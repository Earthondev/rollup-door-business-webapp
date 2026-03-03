import unittest

from job_tracker.utils import build_job_uid, canonical_url


class UtilsTests(unittest.TestCase):
    def test_canonical_url(self):
        url = "https://www.example.com/jobs/123/?utm_source=test#abc"
        self.assertEqual(canonical_url(url), "https://example.com/jobs/123")

    def test_stable_uid(self):
        a = build_job_uid("jobthai", "ACME", "Chemist", "https://example.com/a?x=1")
        b = build_job_uid("jobthai", "ACME", "Chemist", "https://example.com/a")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
