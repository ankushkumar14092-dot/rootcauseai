"""Curated realistic sample CI/CD logs for RootCause AI demonstrations."""

SAMPLE_LOGS = {
    "github_actions_coupon": {
        "id": "github_actions_coupon",
        "title": "GitHub Actions: Checkout Coupon Expiry (AssertionError)",
        "repository": "checkout-service",
        "branch": "main",
        "workflow": "CI / pull-request",
        "log": """2026-10-16T10:40:12.392Z ##[group]Run actions/checkout@v4
2026-10-16T10:40:13.104Z Syncing repository: checkout-service
2026-10-16T10:40:13.208Z HEAD is now at a17c9e2 Refactor coupon expiry comparison
2026-10-16T10:40:13.210Z Author: Mina Patel <mina@example.com>
2026-10-16T10:40:13.211Z ##[endgroup]
2026-10-16T10:40:14.000Z ##[group]Set up Python 3.12
2026-10-16T10:40:14.500Z Successfully installed dependencies from requirements.txt
2026-10-16T10:40:14.600Z ##[endgroup]
2026-10-16T10:41:00.120Z ##[group]Run pytest --verbose
2026-10-16T10:41:01.002Z ============================= test session starts ==============================
2026-10-16T10:41:01.005Z platform linux -- Python 3.12.2, pytest-8.1.1, pluggy-1.4.0
2026-10-16T10:41:01.010Z rootdir: /home/runner/work/checkout-service/checkout-service
2026-10-16T10:41:01.012Z collected 4 items
2026-10-16T10:41:01.120Z tests/test_checkout.py::test_calculate_cart_total PASSED              [ 25%]
2026-10-16T10:41:01.150Z tests/test_checkout.py::test_apply_percentage_discount PASSED         [ 50%]
2026-10-16T10:41:01.180Z tests/test_checkout.py::test_checkout_rejects_expired_coupon FAILED   [ 75%]
2026-10-16T10:41:01.210Z tests/test_checkout.py::test_empty_cart_returns_zero PASSED           [100%]
2026-10-16T10:41:01.250Z 
2026-10-16T10:41:01.251Z =================================== FAILURES ===================================
2026-10-16T10:41:01.252Z _________________ test_checkout_rejects_expired_coupon _________________
2026-10-16T10:41:01.253Z 
2026-10-16T10:41:01.254Z     def test_checkout_rejects_expired_coupon():
2026-10-16T10:41:01.255Z         coupon = Coupon(code="FALL2026", valid_until=date(2026, 10, 16))
2026-10-16T10:41:01.256Z         today = date(2026, 10, 16)
2026-10-16T10:41:01.257Z >       assert validate_coupon(coupon.valid_until, today) is False
2026-10-16T10:41:01.258Z E       AssertionError: Expected expired coupon to be rejected; got accepted
2026-10-16T10:41:01.259Z 
2026-10-16T10:41:01.260Z src/checkout.py:38: AssertionError
2026-10-16T10:41:01.300Z =========================== short test summary info ============================
2026-10-16T10:41:01.302Z FAILED tests/test_checkout.py::test_checkout_rejects_expired_coupon - AssertionError: Expected expired coupon to be rejected; got accepted
2026-10-16T10:41:01.310Z ========================= 1 failed, 3 passed in 0.28s =========================
2026-10-16T10:41:01.320Z ##[error]Process completed with exit code 1.
""",
    },
    "github_actions_webhook_timeout": {
        "id": "github_actions_webhook_timeout",
        "title": "GitHub Actions: Payment Webhook Timeout (TimeoutError)",
        "repository": "payments-service",
        "branch": "feature/webhook-retries",
        "workflow": "CI / pull-request",
        "log": """2026-10-17T14:22:01.100Z ##[group]Run actions/checkout@v4
2026-10-17T14:22:01.500Z Syncing repository: payments-service
2026-10-17T14:22:01.620Z HEAD is now at d4e1a0b Reduce webhook connection timeout to 2s
2026-10-17T14:22:01.622Z Author: Alex Chen <alex.chen@example.com>
2026-10-17T14:22:01.624Z ##[endgroup]
2026-10-17T14:22:02.100Z ##[group]Run pytest tests/
2026-10-17T14:22:02.500Z ============================= test session starts ==============================
2026-10-17T14:22:02.505Z rootdir: /home/runner/work/payments-service
2026-10-17T14:22:02.510Z collected 6 items
2026-10-17T14:22:03.100Z tests/test_webhook.py::test_signature_verification PASSED            [ 16%]
2026-10-17T14:22:03.200Z tests/test_webhook.py::test_stripe_webhook_retry FAILED             [ 33%]
2026-10-17T14:22:03.300Z tests/test_webhook.py::test_idempotency_key_cached PASSED           [ 50%]
2026-10-17T14:22:03.400Z 
2026-10-17T14:22:03.450Z =================================== FAILURES ===================================
2026-10-17T14:22:03.452Z ________________________ test_stripe_webhook_retry _________________________
2026-10-17T14:22:03.454Z 
2026-10-17T14:22:03.456Z >       res = handle_webhook_retry(event_id="evt_99812", attempt=2)
2026-10-17T14:22:03.458Z E       TimeoutError: Gateway response exceeded 2000ms deadline during retry
2026-10-17T14:22:03.460Z 
2026-10-17T14:22:03.462Z src/webhook_handler.py:74: TimeoutError
2026-10-17T14:22:03.500Z =========================== short test summary info ============================
2026-10-17T14:22:03.502Z FAILED tests/test_webhook.py::test_stripe_webhook_retry - TimeoutError: Gateway response exceeded 2000ms deadline during retry
2026-10-17T14:22:03.510Z ========================= 1 failed, 5 passed in 1.42s =========================
2026-10-17T14:22:03.520Z ##[error]Process completed with exit code 1.
""",
    },
    "pytest_auth_invalidation": {
        "id": "pytest_auth_invalidation",
        "title": "Pytest CLI: Auth Revoked Token Accepted (AssertionError)",
        "repository": "auth-service",
        "branch": "main",
        "workflow": "CI / unit-tests",
        "log": """Run: CI / unit-tests #2104
Branch: main
Repository: auth-service
[7c3f82a] Optimize token cache validation lookup (Sarah Jenkins)

============================= test session starts ==============================
collected 8 items

tests/test_tokens.py::test_generate_jwt_pair PASSED                           [ 12%]
tests/test_tokens.py::test_expired_token_rejected PASSED                      [ 25%]
tests/test_tokens.py::test_revoked_session_rejected FAILED                    [ 37%]
tests/test_tokens.py::test_refresh_token_rotation PASSED                      [ 50%]

=================================== FAILURES ===================================
_________________________ test_revoked_session_rejected _________________________

    def test_revoked_session_rejected():
        token = create_test_token(user_id="usr_42", session_id="ses_99")
        revoke_session("ses_99")
>       assert verify_session_token(token) is False
E       AssertionError: Revoked session token was accepted from stale cache

src/token_auth.py:59: AssertionError
=========================== short test summary info ============================
FAILED tests/test_tokens.py::test_revoked_session_rejected - AssertionError: Revoked session token was accepted from stale cache
========================= 1 failed, 7 passed in 0.44s =========================
""",
    },
}
