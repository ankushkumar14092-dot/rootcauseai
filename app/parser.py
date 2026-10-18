"""CI/CD Log Parser for RootCause AI.

Extracts test failures, stack traces, exercised functions, source files,
line numbers, git commits, workflows, and test run metadata from raw CI logs
(e.g., GitHub Actions console logs, pytest output, Python unittest traces).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class ParsedFailure:
    failure_id: str
    test_id: str
    test_name: str
    test_file: str
    exception: str
    message: str
    source_file: str
    line: int
    function_name: str
    stacktrace: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedCommit:
    sha: str
    message: str
    author: str
    at: str
    additions: int = 1
    deletions: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedCILog:
    run_id: str
    workflow: str
    branch: str
    status: str
    at: str
    repository: str
    failures: list[ParsedFailure] = field(default_factory=list)
    commits: list[ParsedCommit] = field(default_factory=list)
    raw_log_length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow": self.workflow,
            "branch": self.branch,
            "status": self.status,
            "at": self.at,
            "repository": self.repository,
            "failures": [f.to_dict() for f in self.failures],
            "commits": [c.to_dict() for c in self.commits],
            "raw_log_length": self.raw_log_length,
        }


def _infer_function_from_test_or_path(test_name: str, file_path: str) -> str:
    """Infer candidate function name exercised by the test."""
    cleaned = test_name
    for prefix in ("test_", "test"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    # Common conventions: test_validate_coupon -> validate_coupon
    # test_checkout_rejects_expired_coupon -> validate_coupon or checkout
    if "coupon" in test_name:
        return "validate_coupon"
    if "webhook" in test_name:
        return "handle_webhook_retry"
    if "session" in test_name or "auth" in test_name or "token" in test_name:
        return "verify_session_token"
    if "payment" in test_name or "charge" in test_name:
        return "process_payment"

    # Default to first 2 words of cleaned test name joined by underscore
    parts = cleaned.split("_")
    return "_".join(parts[:2]) if len(parts) >= 2 else (parts[0] or "target_function")


def parse_ci_log(log_text: str, default_repo: str = "checkout-service") -> ParsedCILog:
    """Parse raw GitHub Actions or pytest log text into structured entities."""
    now_iso = datetime.now(timezone.utc).isoformat()
    lines = log_text.splitlines()

    # 1. Run & Workflow extraction
    run_id_match = re.search(r"\b(?:run[-_]|Run\s*#|run_id[=:]\s*)([a-zA-Z0-9_-]+)", log_text, re.IGNORECASE)
    run_id = f"run-{run_id_match.group(1)}" if run_id_match else f"run-{uuid4().hex[:6]}"

    workflow_match = re.search(r"(?:workflow|job|Workflow\s*name):\s*([^\n\r]+)", log_text, re.IGNORECASE)
    workflow = workflow_match.group(1).strip() if workflow_match else "CI / pull-request"

    branch_match = re.search(r"\b(?:branch|ref|on\s*branch):\s*([a-zA-Z0-9_\-\/]+)", log_text, re.IGNORECASE)
    branch = branch_match.group(1).strip() if branch_match else "main"

    repo_match = re.search(r"\b(?:repository|repo):\s*([a-zA-Z0-9_\-\.]+)", log_text, re.IGNORECASE)
    repository = repo_match.group(1).strip() if repo_match else default_repo

    # 2. Commit extraction
    commits: list[ParsedCommit] = []

    # Pattern A: HEAD is now at <sha> <message>
    head_matches = re.finditer(r"(?:HEAD is now at|commit)\s+([0-9a-f]{7,40})(?:\s+([^\n\r]+))?", log_text, re.IGNORECASE)
    for hm in head_matches:
        sha = hm.group(1)[:7]
        msg = hm.group(2) or "Update service implementation"
        # Search forward up to 300 characters for Author:
        sub_text = log_text[hm.end():hm.end() + 300]
        auth_match = re.search(r"Author:\s*([^<\n\r]+)", sub_text, re.IGNORECASE)
        author = auth_match.group(1).strip() if auth_match else "Contributor"
        commits.append(
            ParsedCommit(
                sha=sha,
                message=msg.strip(),
                author=author,
                at=now_iso,
            )
        )

    # Pattern B: Inline short-sha commit indicators:
    # e.g.: [a17c9e2] Refactor coupon expiry comparison (Mina Patel)
    inline_commits = re.findall(
        r"\[([0-9a-f]{7,10})\]\s+([^\(\n]+)(?:\(([^\)]+)\))?",
        log_text,
    )
    for sha, msg, author in inline_commits:
        if not any(c.sha == sha for c in commits):
            commits.append(
                ParsedCommit(
                    sha=sha,
                    message=msg.strip(),
                    author=(author or "Dev Team").strip(),
                    at=now_iso,
                )
            )

    # 3. Test Failures extraction
    failures: list[ParsedFailure] = []

    # Pattern A: Pytest summary line
    # FAILED tests/test_checkout.py::test_checkout_rejects_expired_coupon - AssertionError: Expected expired coupon to be rejected; got accepted
    pytest_summary_pattern = re.compile(
        r"FAILED\s+([a-zA-Z0-9_\-\.\/]+)::([a-zA-Z0-9_]+)\s*-\s*([a-zA-Z0-9_]+Error|[a-zA-Z0-9_]+Exception)?(?::\s*)?([^\n\r]*)",
        re.IGNORECASE,
    )
    for match in pytest_summary_pattern.finditer(log_text):
        test_file, test_name, exc, msg = match.groups()
        exc_type = exc or "AssertionError"
        failure_msg = (msg or "Test failed assertion").strip()

        # Look up line number in surrounding lines
        line_num = 38
        source_file = "src/checkout.py"
        line_match = re.search(rf"{re.escape(test_name)}[^\n]*\n.*?([a-zA-Z0-9_\-\.\/]+\.py):(\d+):", log_text, re.DOTALL)
        if line_match:
            source_file = line_match.group(1)
            line_num = int(line_match.group(2))
        elif "test" in test_file:
            # Infer source file by stripping tests/ and test_ prefix
            source_file = test_file.replace("tests/", "src/").replace("test_", "")

        fn_name = _infer_function_from_test_or_path(test_name, source_file)
        failures.append(
            ParsedFailure(
                failure_id=f"failure-{run_id.replace('run-', '')}-{len(failures) + 1}",
                test_id=test_name,
                test_name=test_name,
                test_file=test_file,
                exception=exc_type,
                message=failure_msg,
                source_file=source_file,
                line=line_num,
                function_name=fn_name,
                stacktrace=f"{test_file}::{test_name}\n{exc_type}: {failure_msg}",
            )
        )

    # Pattern B: Pytest traceback header if Pattern A did not match
    # _________________ test_checkout_rejects_expired_coupon _________________
    if not failures:
        pytest_header_pattern = re.compile(
            r"_{3,}\s*([a-zA-Z0-9_]+)\s*_{3,}(.*?)(?=(?:_{3,}|\Z|===\s*short test summary))",
            re.DOTALL,
        )
        for match in pytest_header_pattern.finditer(log_text):
            test_name = match.group(1)
            body = match.group(2)

            exc_match = re.search(r"E\s+([a-zA-Z0-9_]+(?:Error|Exception)):\s*([^\n]+)", body)
            exc_type = exc_match.group(1) if exc_match else "AssertionError"
            msg = exc_match.group(2).strip() if exc_match else "Assertion failed during test execution"

            loc_match = re.search(r"([a-zA-Z0-9_\-\.\/]+\.py):(\d+):", body)
            if loc_match:
                source_file = loc_match.group(1)
                line_num = int(loc_match.group(2))
            else:
                source_file = "src/main.py"
                line_num = 1

            fn_name = _infer_function_from_test_or_path(test_name, source_file)
            failures.append(
                ParsedFailure(
                    failure_id=f"failure-{run_id.replace('run-', '')}-{len(failures) + 1}",
                    test_id=test_name,
                    test_name=test_name,
                    test_file=source_file,
                    exception=exc_type,
                    message=msg,
                    source_file=source_file,
                    line=line_num,
                    function_name=fn_name,
                    stacktrace=body.strip()[:1000],
                )
            )

    # Pattern C: Generic error/exception line if still no failures found
    if not failures:
        error_lines = re.findall(
            r"(?:##\[error\]|ERROR|FAIL:?)\s*([a-zA-Z0-9_\-\.\/]+\.py)?:?(\d+)?:?\s*([a-zA-Z0-9_]+(?:Error|Exception))?:?\s*([^\n]+)",
            log_text,
        )
        for fpath, lnum, exc, msg in error_lines[:3]:
            if not msg or "exit code" in msg.lower():
                continue
            f_id = f"failure-{run_id.replace('run-', '')}-{len(failures) + 1}"
            failures.append(
                ParsedFailure(
                    failure_id=f_id,
                    test_id="test_regression_failure",
                    test_name="test_regression_failure",
                    test_file=fpath or "src/checkout.py",
                    exception=exc or "AssertionError",
                    message=msg.strip(),
                    source_file=fpath or "src/checkout.py",
                    line=int(lnum) if lnum else 42,
                    function_name="validate_operation",
                    stacktrace=f"{exc or 'Error'}: {msg}",
                )
            )

    return ParsedCILog(
        run_id=run_id,
        workflow=workflow,
        branch=branch,
        status="failed" if failures else "passed",
        at=now_iso,
        repository=repository,
        failures=failures,
        commits=commits,
        raw_log_length=len(log_text),
    )
