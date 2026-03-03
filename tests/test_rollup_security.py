import time
import unittest

from rollup_door.security import InMemoryRateLimiter, SecurityConfig, build_signature, validate_request


class RollupSecurityTests(unittest.TestCase):
    def setUp(self):
        self.config = SecurityConfig(
            access_key_id="k1",
            access_key_secret="s1",
            timestamp_tolerance_seconds=300,
            rate_limit_per_minute=10,
        )
        self.limiter = InMemoryRateLimiter(limit_per_minute=10)

    def test_valid_signature(self):
        ts = str(int(time.time()))
        body = b'{"a":1}'
        sig = build_signature("s1", ts, "POST", "/api/v1/cases", body)
        err = validate_request(
            headers={"x-access-key": "k1", "x-timestamp": ts, "x-signature": sig},
            method="POST",
            path="/api/v1/cases",
            body=body,
            client_ip="1.1.1.1",
            config=self.config,
            limiter=self.limiter,
        )
        self.assertIsNone(err)

    def test_invalid_signature(self):
        ts = str(int(time.time()))
        err = validate_request(
            headers={"x-access-key": "k1", "x-timestamp": ts, "x-signature": "bad"},
            method="POST",
            path="/api/v1/cases",
            body=b"{}",
            client_ip="1.1.1.2",
            config=self.config,
            limiter=self.limiter,
        )
        self.assertEqual(err, "invalid_signature")


if __name__ == "__main__":
    unittest.main()
