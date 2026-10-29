#!/usr/bin/env python3
"""
Backend smoke test for a running local API in mock mode (./scripts/dev.sh).

    python scripts/smoke_test.py                      # API on http://localhost:8000
    python scripts/smoke_test.py --api http://localhost:8000 --user-id <uuid>

Standard library only. It acts as the seeded admin via the dev mock auth headers and:
  1. checks GET /health (dev mock auth on);
  2. creates a case with intake fields and uploads samples/rfq_apex.md and the
     password-locked samples/apex_census_locked.xlsx;
  3. checks POST /process answers 423 (password needed), then 202 with the password;
  4. polls GET /pipeline-status until all 4 stages are done, then spot-checks the results.
The case it creates ("Smoke Test …") is left in place for inspection in the browser.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
ENV_FILE = ROOT / "services" / "backend" / ".env.backend.local"
CENSUS_PASSWORD = "Apex@2026"  # samples/README.md


class SmokeFailure(Exception):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)
    print(f"  ✓ {message}")


def seed_admin_id() -> str:
    """The seeded admin's users.id, read with psql (FORCE RLS: admin context set first)."""
    url = os.environ.get("DATABASE_URL")
    if not url and ENV_FILE.exists():
        m = re.search(r"^DATABASE_URL=\"?([^\"\n]+)\"?", ENV_FILE.read_text(), re.M)
        url = m and m.group(1)
    if not url:
        raise SmokeFailure("DATABASE_URL not found; pass --user-id <seed admin users.id>")
    sql = (
        "select set_config('app.current_user_role', 'admin', false);"
        "select id from users where clerk_user_id = 'seed_admin';"
    )
    try:
        out = subprocess.run(
            ["psql", url, "-Atqc", sql], capture_output=True, text=True, check=True
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SmokeFailure(
            f"Could not query the seed admin with psql ({exc}); use --user-id"
        ) from None
    ids = [line for line in out if re.fullmatch(r"[0-9a-f-]{36}", line)]
    if not ids:
        raise SmokeFailure("No seed_admin user; run `cd apps/web && bun run seed`")
    return ids[0]


class Api:
    def __init__(self, base: str, user_id: str | None):
        self.base = base.rstrip("/") + "/api/v1"
        self.headers = {"X-Dev-User-Id": user_id, "X-Dev-User-Role": "admin"} if user_id else {}

    def call(self, method: str, path: str, body: dict | None = None, files=None):
        headers = dict(self.headers)
        data = None
        if files is not None:
            boundary = uuid.uuid4().hex
            parts = []
            for name, content in files:
                parts.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="files"; '
                    f'filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                    + content
                    + b"\r\n"
                )
            data = b"".join(parts) + f"--{boundary}--\r\n".encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return res.status, json.loads(res.read() or b"null")
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read() or b"null")
        except urllib.error.URLError as err:
            raise SmokeFailure(
                f"API not reachable at {self.base} ({err.reason}); run ./scripts/dev.sh"
            ) from None


def run(api_base: str, user_id: str | None, timeout: float) -> None:
    print("1. Health")
    status, health = Api(api_base, None).call("GET", "/health")
    check(status == 200 and health["status"] == "healthy", f"GET /health → {health}")
    check(health.get("dev_mock_auth") is True, "dev mock auth is enabled on the API")
    api = Api(api_base, user_id or seed_admin_id())

    print("2. Intake")
    status, case = api.call("POST", "/cases", {
        "company_name": f"Smoke Test {time.strftime('%d-%m-%Y %H:%M:%S')}",
        "proposal_start_date": "2026-12-01",
        "incumbent_insurer": "ICICI Lombard General Insurance",
        "brokerage_pct": "7.50",
        "pincode": "400051",
    })  # fmt: skip
    check(status == 201, f"POST /cases → 201 ({case if status != 201 else case['case_number']})")
    case_id = case["id"]
    status, uploaded = api.call("POST", f"/cases/{case_id}/upload", files=[
        ("rfq_apex.md", (SAMPLES / "rfq_apex.md").read_bytes()),
        ("apex_census_locked.xlsx", (SAMPLES / "apex_census_locked.xlsx").read_bytes()),
    ])  # fmt: skip
    check(status == 201 and len(uploaded["files"]) == 2, "uploaded 2 sample files")
    locked = [f for f in uploaded["files"] if f["is_encrypted"]]
    check(len(locked) == 1, "the census was detected as password-protected")

    print("3. Process")
    status, body = api.call("POST", f"/cases/{case_id}/process", {})
    check(status == 423 and body["detail"]["code"] == "password_required",
          "POST /process without a password → 423 password_required")  # fmt: skip
    status, body = api.call(
        "POST", f"/cases/{case_id}/process",
        {"passwords": {locked[0]["id"]: CENSUS_PASSWORD}},
    )  # fmt: skip
    check(status == 202, f"POST /process with the password → 202 ({status})")
    check(len(body["stages"]) == 4, "the response lists the 4 pipeline stages")
    check(CENSUS_PASSWORD not in json.dumps(body), "the password is not echoed back")

    print("4. Pipeline")
    deadline = time.monotonic() + timeout
    while True:
        status, pipe = api.call("GET", f"/cases/{case_id}/pipeline-status")
        if pipe["terminal"] or time.monotonic() > deadline:
            break
        time.sleep(1)
    for stage in pipe["stages"]:
        print(f"     {stage['state']:<8} {stage['label']}: {stage['detail'] or ''}")
    check(pipe["terminal"], f"pipeline finished within {timeout:.0f} s")
    check(pipe["error"] is None, f"no pipeline error ({pipe['error']})")
    check([s["state"] for s in pipe["stages"]] == ["done"] * 4, "all 4 stages are done")
    check(pipe["status"] in {"review_required", "ready_for_quote"},
          f"case status is {pipe['status']}")  # fmt: skip

    print("5. Results")
    _, detail = api.call("GET", f"/cases/{case_id}")
    check(detail["counts"]["members"] > 0, f"{detail['counts']['members']} demography records")
    check(detail["counts"]["fields"] > 0, f"{detail['counts']['fields']} quote fields")
    _, grid = api.call("GET", f"/cases/{case_id}/extractions")
    quote_cols = ["Quote Fields", "Coverage Details", "Proposed Details", "Source Status",
                  "Confidence"]  # fmt: skip
    check(grid["columns"] == quote_cols, "strict 5-column quote grid")
    _, roster = api.call("GET", f"/cases/{case_id}/demography?page_size=1")
    roster_cols = ["Age", "Date of Birth", "Sum Insured", "Relationship", "Name", "EmpCode",
                   "Gender"]  # fmt: skip
    check(roster["columns"] == roster_cols, "strict 7-column demography grid")
    print(f"\nSMOKE TEST PASSED · case {detail['case_number']} → "
          f"http://localhost:3000/cases/{case_id}/quote")  # fmt: skip


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default="http://localhost:8000", help="API origin")
    parser.add_argument("--user-id", help="users.id to act as (default: the seeded admin)")
    parser.add_argument("--timeout", type=float, default=120, help="pipeline wait, seconds")
    args = parser.parse_args()
    try:
        run(args.api, args.user_id, args.timeout)
    except SmokeFailure as exc:
        print(f"\n  ✗ {exc}\nSMOKE TEST FAILED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
