"""Regression tests for the Resend email delivery workflows.

The failure modes covered here have all bitten before:
  * payload built with the wrong shape / bad JSON → Resend 422
  * subject extraction returning empty → unlabelled email
  * push-path filters not matching the files the routine actually writes
  * outbound email attempted from the local sandbox, where api.resend.com is
    NOT allowlisted (must only ever happen inside GitHub Actions)
  * GITHUB_TOKEN pushes not triggering downstream email workflows
    (bit on 2026-07-18 — weekly-audit must dispatch them explicitly)

The payload builder is replicated step-for-step from the workflow YAML and run
against the repo's real latest briefing, then validated with jq — same tool
the workflow uses. `base64 -w0` (GNU, ubuntu runner) is replaced with the
portable `base64 | tr -d '\\n'`, which produces identical output.
"""

import base64
import json
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"

# Step script replicated from email-briefing.yml / email-audit.yml
# ("Build Resend payload"), with only the base64 invocation made portable.
BUILD_PAYLOAD = r"""
set -euo pipefail
HTML_FILE="$1"
MD_FILE="$2"
OUT="$3"
FALLBACK_SUBJECT="$4"

SUBJECT=$(awk '/^# /{sub(/^# /,""); print; exit}' "$MD_FILE")
if [ -z "$SUBJECT" ]; then
  SUBJECT="$FALLBACK_SUBJECT"
fi

base64 < "$MD_FILE" | tr -d '\n' > "$OUT.b64"

jq -n \
  --arg subject "$SUBJECT" \
  --arg fn "$(basename "$MD_FILE")" \
  --rawfile html "$HTML_FILE" \
  --rawfile b64 "$OUT.b64" \
  '{
    from: "CCS Briefing <onboarding@resend.dev>",
    to: ["matthias.raab@co2crc.com.au"],
    subject: $subject,
    html: $html,
    attachments: [{filename: $fn, content: $b64}]
  }' > "$OUT"

jq -e . "$OUT" > /dev/null
"""


def _build_payload(html_file: Path, md_file: Path, out: Path, fallback: str) -> dict:
    subprocess.run(
        ["/bin/bash", "-c", BUILD_PAYLOAD, "payload",
         str(html_file), str(md_file), str(out), fallback],
        check=True,
    )
    return json.loads(out.read_text())


def _latest_briefing(repo_root: Path):
    htmls = sorted(repo_root.glob("*-ccs-briefing.html"))
    assert htmls, "no briefing HTML files in repo"
    date = htmls[-1].name.replace("-ccs-briefing.html", "")
    md = repo_root / f"{date}-ccs-briefing.md"
    assert md.exists(), f"{md} missing — email workflow would fail for {date}"
    return htmls[-1], md


# ---------------------------------------------------------------- payloads

def test_payload_from_real_latest_briefing(repo_root, tmp_path):
    html_file, md_file = _latest_briefing(repo_root)
    payload = _build_payload(html_file, md_file, tmp_path / "resend.json",
                             "CCS briefing — fallback")

    assert payload["from"].endswith("<onboarding@resend.dev>")
    assert payload["to"] == ["matthias.raab@co2crc.com.au"]
    # Subject: first H1 of the markdown, never empty.
    first_h1 = next((ln[2:].strip() for ln in md_file.read_text().splitlines()
                     if ln.startswith("# ")), None)
    assert payload["subject"]
    if first_h1:
        assert payload["subject"] == first_h1
    # HTML body is the real file, verbatim.
    assert payload["html"] == html_file.read_text()
    # Attachment round-trips to the exact markdown bytes.
    att = payload["attachments"][0]
    assert att["filename"] == md_file.name
    assert base64.b64decode(att["content"]) == md_file.read_bytes()


def test_payload_subject_falls_back_when_no_h1(tmp_path):
    md = tmp_path / "x.md"
    md.write_text("no heading here\n\njust prose\n")
    html = tmp_path / "x.html"
    html.write_text("<p>hi</p>")
    payload = _build_payload(html, md, tmp_path / "resend.json", "CCS briefing — 2026-07-21")
    assert payload["subject"] == "CCS briefing — 2026-07-21"


def test_payload_survives_quotes_and_unicode(tmp_path):
    md = tmp_path / "x.md"
    md.write_text('# CO₂ "storage" — 100% & <b>bold</b>\n\nbody\n')
    html = tmp_path / "x.html"
    html.write_text("<p>CO₂ & \"quotes\"</p>")
    payload = _build_payload(html, md, tmp_path / "resend.json", "fallback")
    assert payload["subject"] == 'CO₂ "storage" — 100% & <b>bold</b>'
    assert payload["html"] == "<p>CO₂ & \"quotes\"</p>"


def test_latest_audit_report_would_email(repo_root, tmp_path):
    reports = sorted((repo_root / "audit").glob("*-recall-report.md"))
    if not reports:
        pytest.skip("no recall reports yet")
    md = reports[-1]
    html = md.with_suffix(".html")
    assert html.exists(), "recall report md/html pair broken"
    payload = _build_payload(html, md, tmp_path / "resend.json", "fallback")
    assert payload["subject"].startswith("CCS recall audit")


# ---------------------------------------------------------------- workflow YAML

def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def _job_steps(wf: dict) -> list:
    (job,) = wf["jobs"].values()
    return job["steps"]


def _all_run_text(wf: dict) -> str:
    return "\n".join(s.get("run", "") for s in _job_steps(wf))


EMAIL_WORKFLOWS = ["email-briefing.yml", "email-audit.yml", "email-dashboard.yml"]


@pytest.mark.parametrize("name", EMAIL_WORKFLOWS)
def test_email_workflow_contract(name):
    wf = _load(name)
    # `on` parses as boolean True in YAML 1.1 — accommodate both.
    on = wf.get("on") or wf.get(True)
    assert "workflow_dispatch" in on, f"{name}: manual re-send path missing"
    assert on["push"]["branches"] == ["main"]

    run_text = _all_run_text(wf)
    assert "https://api.resend.com/emails" in run_text
    assert "RESEND_API_KEY" in run_text
    # Loud failure when the secret is missing (documented in SETUP.md).
    assert '::error::RESEND_API_KEY secret is not set' in run_text
    # Non-2xx Resend responses must fail the job, not pass silently.
    assert "exit 1" in run_text
    # Payload is validated before sending.
    assert "jq -e" in run_text


def test_briefing_workflow_paths_match_routine_output():
    on = _load("email-briefing.yml").get("on") or _load("email-briefing.yml").get(True)
    paths = on["push"]["paths"]
    assert "*-ccs-briefing.html" in paths and "*-ccs-briefing.md" in paths


def test_audit_workflow_paths_match_audit_output():
    on = _load("email-audit.yml").get("on") or _load("email-audit.yml").get(True)
    paths = on["push"]["paths"]
    assert "audit/*-recall-report.html" in paths and "audit/*-recall-report.md" in paths


def test_weekly_audit_dispatches_email_workflows():
    """Regression for 2026-07-18: pushes made with GITHUB_TOKEN never trigger
    push-path workflows, so weekly-audit must dispatch the two email workflows
    explicitly after committing."""
    run_text = _all_run_text(_load("weekly-audit.yml"))
    assert "gh workflow run email-audit.yml" in run_text
    assert "gh workflow run email-dashboard.yml" in run_text


def test_all_workflows_parse_and_scheduled_ones_allow_manual_run():
    for path in WORKFLOWS.glob("*.yml"):
        wf = yaml.safe_load(path.read_text())
        on = wf.get("on") or wf.get(True)
        assert on, f"{path.name}: no triggers"
        if "schedule" in on:
            assert "workflow_dispatch" in on, \
                f"{path.name}: scheduled workflow with no manual re-run path"


# ------------------------------------------------- network allowlist assumption

def test_no_local_code_calls_resend_directly(repo_root):
    """The sandbox blocks api.resend.com — outbound email must only ever be
    attempted from GitHub Actions. Any hit outside .github/ or docs is a
    regression to the pre-2026-05-25 architecture."""
    offenders = []
    for pattern in ("scripts/*.py", "scripts/*.sh", "*.py", "*.sh"):
        for f in repo_root.glob(pattern):
            if f.name == "preflight.sh":  # the checker itself names the host
                continue
            if "resend.com" in f.read_text(errors="replace"):
                offenders.append(str(f))
    assert not offenders, f"direct Resend usage outside Actions: {offenders}"


def test_collectors_have_no_hardcoded_email_endpoints(repo_root):
    scripts = repo_root / "scripts"
    for f in scripts.glob("*.py"):
        text = f.read_text()
        assert "smtplib" not in text, f"{f.name} sends mail directly"
        assert "api.resend.com" not in text, f"{f.name} calls Resend directly"
