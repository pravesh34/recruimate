"""Jobs CLI integration tests.

A stub binary stands in for the real ``jobs-cli`` so the suite never needs
the CLI installed, a LinkedIn session or network access. The stub records the
arguments it was called with so the tests can assert on the safety rules
(no shell, no apply commands, read-only allow-list, per-user isolation).
"""
from __future__ import annotations

import json
import os
import stat
import uuid
from pathlib import Path

import pytest

from app.config import settings

STUB_LOG = Path(os.environ.get("JOBS_CLI_STUB_LOG", "/tmp/jobs-cli-stub.log"))


def _email() -> str:
    return f"cli-{uuid.uuid4().hex[:10]}@example.com"


def _headers(client) -> dict:
    tokens = client.post(
        "/api/auth/register",
        json={"email": _email(), "password": "Str0ngPassw0rd", "display_name": "CLI"},
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture(scope="session")
def stub_cli(tmp_path_factory):
    """Install a fake jobs-cli that returns a canned JSON envelope."""
    directory = tmp_path_factory.mktemp("jobs-cli")
    log = directory / "calls.log"
    script = directory / "jobs-cli"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, os\n"
        f"open({str(log)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
        "args = sys.argv[1:]\n"
        "if args and args[0] == 'doctor':\n"
        "    payload = {'ok': True, 'data': {'status': 'ok', 'cli': 'stub'},\n"
        "              'meta': {'command': 'doctor', 'duration_ms': 1}}\n"
        "elif args and args[0] == 'sources':\n"
        "    payload = {'ok': True, 'data': {'sources': ['indeed', 'linkedin']},\n"
        "              'meta': {'command': 'sources status', 'duration_ms': 1}}\n"
        "else:\n"
        "    jobs = [\n"
        "        {'id': 'linkedin:111', 'source': 'linkedin', 'source_job_id': '111',\n"
        "         'title': 'Backend Engineer', 'employer': 'Acme',\n"
        "         'location': 'Remote', 'remote': True, 'description': 'Python and FastAPI work.',\n"
        "         'posted_date': '2026-09-20', 'employment_type': 'Full-Time', 'level': 'Senior',\n"
        "         'tags': ['Python'], 'source_url': 'https://linkedin.com/jobs/111',\n"
        "         'application_url': 'https://boards.greenhouse.io/acme/jobs/111',\n"
        "         'compensation': {'amounts': [{'kind': 'range', 'min': 100000, 'max': 140000}],\n"
        "                            'currency': 'CAD', 'interval': 'year', 'summary': 'CA$100k-140k a year'}},\n"
        "        {'id': 'indeed:222', 'source': 'indeed', 'source_job_id': '222',\n"
        "         'title': 'Backend Engineer', 'employer': 'Acme',\n"
        "         'location': 'Remote', 'remote': True, 'description': 'Python and FastAPI work.',\n"
        "         'posted_date': '2026-09-21', 'employment_type': 'Full-Time',\n"
        "         'tags': ['Python'], 'source_url': 'https://indeed.com/viewjob?jk=222',\n"
        "         'application_url': 'https://indeed.com/viewjob?jk=222',\n"
        "         'compensation': {'amounts': [{'kind': 'range', 'min': 100000, 'max': 140000}],\n"
        "                            'currency': 'CAD', 'interval': 'year', 'summary': 'CA$100k-140k a year'}},\n"
        "    ]\n"
        "    payload = {'ok': True,\n"
        "              'data': {'partitions': [{'source': 'linkedin', 'jobs': [jobs[0]],\n"
        "                                       'pagination': {'limit': 25, 'offset': 0, 'total': 1,\n"
        "                                                      'has_more': False}},\n"
        "                                      {'source': 'indeed', 'jobs': [jobs[1]],\n"
        "                                       'pagination': {'limit': 25, 'offset': 0, 'total': 1,\n"
        "                                                      'has_more': False}}]},\n"
        "              'meta': {'command': 'search', 'duration_ms': 5}}\n"
        "sys.stdout.write(json.dumps(payload))\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    settings.jobs_cli_enabled = True
    settings.jobs_cli_bin = str(script)
    settings.jobs_cli_cache_ttl = 0
    settings.jobs_cli_rate_limit_per_minute = 100
    yield {"path": str(script), "log": log}
    settings.jobs_cli_enabled = False
    settings.jobs_cli_bin = ""


def _calls(stub) -> list[str]:
    if not stub["log"].exists():
        return []
    return stub["log"].read_text().splitlines()


def test_status_reports_availability(client, stub_cli):
    headers = _headers(client)
    response = client.get("/api/jobs-cli/status", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["auto_apply"] is False
    assert payload["read_only"] is True


def test_search_is_read_only_and_persists_nothing(client, stub_cli):
    from app.database.models import JobPosting, SessionLocal

    headers = _headers(client)
    before = SessionLocal().query(JobPosting).count()
    response = client.post(
        "/api/jobs-cli/search",
        json={"query": "backend engineer", "location": "Remote", "sources": ["linkedin", "indeed"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["listings"]) == 2
    assert SessionLocal().query(JobPosting).count() == before

    # The CLI was called with --json and only read-only commands.
    calls = _calls(stub_cli)
    assert calls
    assert all("apply" not in call for call in calls)
    assert all("--json" in call for call in calls)


def test_search_does_not_use_a_shell(client, stub_cli):
    """A query containing shell metacharacters must be passed through as a
    single argument, never interpreted."""
    headers = _headers(client)
    client.post(
        "/api/jobs-cli/search",
        json={"query": "backend; rm -rf /", "sources": ["linkedin"]},
        headers=headers,
    )
    calls = _calls(stub_cli)
    assert calls
    assert "backend; rm -rf /" in calls[-1]


def test_import_deduplicates_across_sources(client, stub_cli):
    headers = _headers(client)
    search = client.post(
        "/api/jobs-cli/search",
        json={"query": "backend", "sources": ["linkedin", "indeed"]},
        headers=headers,
    ).json()
    listing = search["listings"][0]
    other = search["listings"][1]

    first = client.post("/api/jobs-cli/import", json={"listings": [listing]}, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 1

    # The same role from the other source must not be added twice.
    second = client.post("/api/jobs-cli/import", json={"listings": [other]}, headers=headers)
    assert second.json()["created"] == 0
    assert second.json()["updated"] == 1
    pool = client.get("/api/jobs/pool", headers=headers).json()
    titles = [job["title"] for job in pool["jobs"]]
    assert titles.count("Backend Engineer") == 1


def test_imported_job_keeps_source_attribution_and_apply_link(client, stub_cli):
    headers = _headers(client)
    listing = client.post(
        "/api/jobs-cli/search", json={"query": "backend", "sources": ["linkedin"]}, headers=headers
    ).json()["listings"][0]
    client.post("/api/jobs-cli/import", json={"listings": [listing]}, headers=headers)
    pool = client.get("/api/jobs/pool", headers=headers).json()["jobs"]
    assert len(pool) == 1
    row = pool[0]
    assert row["source"] == "linkedin"
    assert row["apply_url"] == "https://boards.greenhouse.io/acme/jobs/111"
    assert row["remote"] is True
    assert row["salary_min"] == 100000
    assert row["salary_max"] == 140000
    assert row["salary_currency"] == "CAD"
    assert row["posted_at"] == "2026-09-20"
    assert row["employment_type"] == "Full-Time"
    assert row["experience_level"] == "Senior"


def test_listings_filters_and_pagination(client, stub_cli):
    headers = _headers(client)
    listing = client.post(
        "/api/jobs-cli/search", json={"query": "backend", "sources": ["linkedin"]}, headers=headers
    ).json()["listings"][0]
    client.post("/api/jobs-cli/import", json={"listings": [listing]}, headers=headers)

    listings = client.get("/api/jobs-cli/listings", headers=headers).json()
    assert listings["total"] == 1
    assert listings["page"] == 1

    assert client.get("/api/jobs-cli/listings?remote=true", headers=headers).json()["total"] == 1
    assert client.get("/api/jobs-cli/listings?remote=false", headers=headers).json()["total"] == 0
    assert client.get("/api/jobs-cli/listings?source=indeed", headers=headers).json()["total"] == 0
    assert client.get("/api/jobs-cli/listings?q=acme", headers=headers).json()["total"] == 1
    assert client.get("/api/jobs-cli/listings?q=nothing", headers=headers).json()["total"] == 0
    assert client.get("/api/jobs-cli/listings?min_salary=120000", headers=headers).json()["total"] == 1
    assert client.get("/api/jobs-cli/listings?min_salary=200000", headers=headers).json()["total"] == 0
    assert client.get("/api/jobs-cli/listings?posted_after=2026-09-21", headers=headers).json()["total"] == 0


def test_bookmarks_and_tracking_are_user_scoped(client, stub_cli):
    owner = _headers(client)
    listing = client.post(
        "/api/jobs-cli/search", json={"query": "backend", "sources": ["linkedin"]}, headers=owner
    ).json()["listings"][0]
    client.post("/api/jobs-cli/import", json={"listings": [listing]}, headers=owner)
    job_id = client.get("/api/jobs/pool", headers=owner).json()["jobs"][0]["id"]

    assert client.post("/api/jobs-cli/bookmark", json={"job_posting_id": job_id}, headers=owner).status_code == 200
    assert client.post("/api/jobs-cli/track", json={"job_posting_id": job_id}, headers=owner).status_code == 200

    other = _headers(client)
    assert client.get("/api/jobs-cli/bookmarks", headers=other).json()["bookmarks"] == []
    assert client.post("/api/jobs-cli/bookmark", json={"job_posting_id": job_id}, headers=other).status_code == 404
    assert client.post("/api/jobs-cli/track", json={"job_posting_id": job_id}, headers=other).status_code == 404
    assert client.get("/api/jobs-cli/listings", headers=other).json()["total"] == 0


def test_apply_commands_are_refused(client, stub_cli):
    """The runner must refuse anything outside the read-only allow-list."""
    import asyncio

    from app.services import jobs_cli

    with pytest.raises(jobs_cli.JobsCliError) as exc:
        asyncio.run(jobs_cli.run_cli(["apply", "submit", "--confirm"]))
    assert exc.value.code == "READ_ONLY_VIOLATION"


def test_integration_is_optional_when_cli_missing(client):
    settings.jobs_cli_enabled = True
    settings.jobs_cli_bin = "/nonexistent/jobs-cli"
    try:
        headers = _headers(client)
        response = client.get("/api/jobs-cli/status", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["available"] is False
        assert "not found" in payload["reason"]
        assert client.post("/api/jobs-cli/search", json={"query": "x"}, headers=headers).status_code == 503
    finally:
        settings.jobs_cli_bin = ""
        settings.jobs_cli_enabled = False


def test_disabled_integration_reports_reason(client):
    settings.jobs_cli_enabled = False
    headers = _headers(client)
    payload = client.get("/api/jobs-cli/status", headers=headers).json()
    assert payload["available"] is False
    assert "disabled" in payload["reason"].lower()
