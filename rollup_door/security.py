from __future__ import annotations

import hashlib
import hmac
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class SecurityConfig:
    access_key_id: str
    access_key_secret: str
    timestamp_tolerance_seconds: int = 300
    rate_limit_per_minute: int = 180


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = max(limit_per_minute, 1)
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allowed(self, key: str, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        window_start = now - 60.0
        q = self._events[key]
        while q and q[0] < window_start:
            q.popleft()
        if len(q) >= self.limit_per_minute:
            return False
        q.append(now)
        return True



def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()



def build_signature(
    secret: str,
    timestamp: str,
    method: str,
    path: str,
    body: bytes,
) -> str:
    body_hash = _sha256_hex(body)
    message = f"{timestamp}.{method.upper()}.{path}.{body_hash}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return digest



def validate_request(
    headers: dict[str, str],
    method: str,
    path: str,
    body: bytes,
    client_ip: str,
    config: SecurityConfig,
    limiter: InMemoryRateLimiter,
    now: float | None = None,
) -> str | None:
    now = now if now is not None else time.time()

    if not limiter.allowed(client_ip, now=now):
        return "rate_limit_exceeded"

    key_id = headers.get("x-access-key", "")
    ts = headers.get("x-timestamp", "")
    sig = headers.get("x-signature", "")

    if key_id != config.access_key_id:
        return "invalid_access_key"

    try:
        ts_value = int(ts)
    except (TypeError, ValueError):
        return "invalid_timestamp"

    if abs(int(now) - ts_value) > config.timestamp_tolerance_seconds:
        return "timestamp_out_of_range"

    expected = build_signature(
        secret=config.access_key_secret,
        timestamp=ts,
        method=method,
        path=path,
        body=body,
    )

    if not hmac.compare_digest(expected, sig):
        return "invalid_signature"

    return None
