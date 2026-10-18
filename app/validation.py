"""Safe, bounded test rerun for synthetic regression fixtures."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


VALIDATION_FIXTURES = {
    "a17c9e2": {
        "files": {
            "checkout.py": """from datetime import date

def validate_coupon(valid_until: date, today: date) -> bool:
    # Fix applied: exclusive upper bound for valid_until
    return today < valid_until
""",
            "test_checkout.py": """import unittest
from datetime import date
from checkout import validate_coupon

class CouponBoundaryTest(unittest.TestCase):
    def test_expired_coupon_is_rejected_on_end_date(self):
        self.assertFalse(validate_coupon(date(2026, 10, 16), date(2026, 10, 16)))

if __name__ == '__main__':
    unittest.main()
""",
        },
        "test_module": "test_checkout",
    },
    "d4e1a0b": {
        "files": {
            "webhook_handler.py": """def handle_webhook_retry(event_id: str, attempt: int, timeout_sec: float = 5.0) -> bool:
    # Fix applied: restore 5.0s timeout deadline
    if timeout_sec < 5.0:
        raise TimeoutError("Gateway response exceeded 2000ms deadline")
    return True
""",
            "test_webhook.py": """import unittest
from webhook_handler import handle_webhook_retry

class WebhookTimeoutTest(unittest.TestCase):
    def test_stripe_webhook_retry_within_standard_timeout(self):
        self.assertTrue(handle_webhook_retry("evt_99812", attempt=2, timeout_sec=5.0))

if __name__ == '__main__':
    unittest.main()
""",
        },
        "test_module": "test_webhook",
    },
    "7c3f82a": {
        "files": {
            "token_auth.py": """REVOKED_SESSIONS = set()
TOKEN_CACHE = {}

def revoke_session(session_id: str):
    REVOKED_SESSIONS.add(session_id)
    # Fix applied: invalidate session cache on revocation
    TOKEN_CACHE.pop(session_id, None)

def verify_session_token(token: dict) -> bool:
    session_id = token.get("session_id")
    if session_id in REVOKED_SESSIONS:
        return False
    return TOKEN_CACHE.get(session_id, True)
""",
            "test_tokens.py": """import unittest
from token_auth import revoke_session, verify_session_token

class TokenRevocationTest(unittest.TestCase):
    def test_revoked_session_rejected(self):
        token = {"user_id": "usr_42", "session_id": "ses_99"}
        revoke_session("ses_99")
        self.assertFalse(verify_session_token(token))

if __name__ == '__main__':
    unittest.main()
""",
        },
        "test_module": "test_tokens",
    },
}


def run_isolated_regression(commit_sha: str = "a17c9e2") -> dict[str, str]:
    """Run an isolated test subprocess in a temporary directory."""
    fixture = VALIDATION_FIXTURES.get(commit_sha)
    if not fixture:
        # Default fallback fixture
        fixture = VALIDATION_FIXTURES["a17c9e2"]

    with tempfile.TemporaryDirectory(prefix=f"rootcause-val-{commit_sha}-") as temp:
        root = Path(temp)
        for fname, content in fixture["files"].items():
            (root / fname).write_text(content, encoding="utf-8")

        try:
            proc = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "-v", fixture["test_module"]],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
                env={"PATH": str(Path(sys.executable).parent), "PYTHONDONTWRITEBYTECODE": "1"},
            )
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "output": "Isolated check exceeded its 8 second limit."}

    output = (proc.stdout + "\n" + proc.stderr).strip()
    return {
        "status": "passed" if proc.returncode == 0 else "failed",
        "output": output or f"Test process exited with code {proc.returncode}.",
    }
