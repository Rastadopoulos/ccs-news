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


def _job_steps(wf: dict, job=None) -> list:
    """Steps of the named job, or of the only job when a workflow has just one.
    weekly-audit.yml gained a second job (notify-failure) once a red Saturday
    started emailing an alert, so callers targeting it must name their job."""
    if job is not None:
        return wf["jobs"][job]["steps"]
    (only,) = wf["jobs"].values()
    return only["steps"]


def _all_run_text(wf: dict, job=None) -> str:
    return "\n".join(s.get("run", "") for s in _job_steps(wf, job))


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
    run_text = _all_run_text(_load("weekly-audit.yml"), "audit")
    assert "gh workflow run email-audit.yml" in run_text
    assert "gh workflow run email-dashboard.yml" in run_text


def test_weekly_audit_gates_on_tests_before_rebuild_and_commit():
    """Regression for 2026-07-28: weekly-audit used to rebuild, commit and
    dispatch the board email regardless of test status — a failing
    data-integrity test (e.g. the double-count or unreviewed-money guards)
    would not have blocked publication.

    Extended 2026-08-25: gating only BEFORE the rebuild is not enough. That pass
    runs against data the rebuild is about to overwrite, so it cannot speak for
    what the rebuild produces — a bad derived figure was committed by the very
    run that generated it and only went red a week later. The suite must run on
    both sides of the rebuild, and the commit must sit after both."""
    steps = _job_steps(_load("weekly-audit.yml"), "audit")
    idx = {s["id"]: i for i, s in enumerate(steps) if "id" in s}
    names = [s.get("name", "") for s in steps]
    rebuild_idx = next(i for i, n in enumerate(names) if n.lower().startswith("rebuild"))

    for step_id in ("tests", "tests_post", "capture", "commit"):
        assert step_id in idx, f"weekly-audit lost its '{step_id}' step"
    assert idx["tests"] < rebuild_idx < idx["tests_post"] < idx["commit"], (
        "the suite must gate the rebuild on both sides, and commit must follow both")
    assert idx["tests_post"] < idx["capture"], (
        "capture must see the post-rebuild results or it cannot name them")

    # Both passes must actually run the suite, and must not let tee mask the
    # exit code — without pipefail a red suite reports success and ships.
    for step_id, log in (("tests", "pytest-inputs.txt"), ("tests_post", "pytest-rebuilt.txt")):
        run = steps[idx[step_id]]["run"]
        assert "pytest tests/" in run, f"{step_id} does not run the suite"
        assert "set -o pipefail" in run, f"{step_id}: tee would mask a red suite"
        assert log in run, f"{step_id} must tee to {log} for the alert to name failures"

    # The post-rebuild pass is worthless if the rebuild's output is committed
    # regardless, so the commit must not opt out of the default success() gate.
    assert "if" not in steps[idx["commit"]], "commit must stay gated on prior steps passing"

    install_text = "\n".join(s.get("run", "") for s in steps if "install" in s.get("name", "").lower())
    assert "pytest" in install_text, "pytest must actually be installed before it's run"


def test_weekly_audit_emails_on_failure():
    """Regression for 2026-08-08/-15/-22: the audit failed three Saturdays running
    and nothing reached a human, because the only symptom was an email that never
    arrived. A red scheduled run must actively alert."""
    wf = _load("weekly-audit.yml")
    assert "notify-failure" in wf["jobs"], "no failure-alert job on the weekly audit"
    job = wf["jobs"]["notify-failure"]
    assert job["needs"] == "audit"
    # Must fire only on a red run, and only for unattended (scheduled) ones.
    assert "failure()" in job["if"]
    assert "schedule" in job["if"]

    run_text = _all_run_text(wf, "notify-failure")
    assert "https://api.resend.com/emails" in run_text
    assert '::error::RESEND_API_KEY secret is not set' in run_text

    # The alert must name what broke, not just that something did — and the names
    # must be handed forward as a job output, not read back from the run log:
    # `gh run view --log-failed` refuses while the run is in progress, which it
    # always is when notify-failure runs (observed 2026-08-25).
    assert "--log-failed" not in run_text, "log-fetch race reintroduced"
    alert = next(s for s in _job_steps(wf, "notify-failure") if "run" in s)
    assert "needs.audit.outputs.failed_tests" in alert["env"]["FAILED_TESTS"]

    # The alert must say WHICH side of the rebuild failed: a red input gate and
    # a red rebuilt-data gate need different responses (fix the corpus/curation
    # vs fix what the build produced), and main is left in a different state.
    assert "needs.audit.outputs.failed_phase" in alert["env"]["FAILED_PHASE"]
    assert wf["jobs"]["audit"]["outputs"]["failed_phase"] == "${{ steps.capture.outputs.phase }}"
    assert "rebuilt data" in alert["run"]
    assert wf["jobs"]["audit"]["outputs"]["failed_tests"] == "${{ steps.capture.outputs.failed }}"
    audit_steps = _job_steps(wf, "audit")
    capture = next(s for s in audit_steps if s.get("id") == "capture")
    assert capture["if"] == "failure()"
    # Ordering, the tee targets and pipefail on both passes are pinned by
    # test_weekly_audit_gates_on_tests_before_rebuild_and_commit.


CRON_GATED = {
    # workflow -> {Melbourne UTC offset: the cron that must act at that offset}
    "late-file-check.yml": {"+1100": "50 20 * * 0-4", "+1000": "50 21 * * 0-4"},
    "deadman-check.yml": {"+1100": "30 21 * * 0-4", "+1000": "30 22 * * 0-4"},
}


@pytest.mark.parametrize("name", sorted(CRON_GATED))
def test_dst_guard_keys_on_which_cron_fired_not_the_clock(name):
    """Regression for 2026-08-25: both crons are registered and the job self-gates
    so exactly one acts per day. Gating on the Melbourne hour was not drift-proof —
    GitHub ran the out-of-phase cron 15 min late, it landed inside hour 07, passed
    an hour-only guard and nudged 45 min early while the 07:00 routine was still
    running. github.event.schedule is the cron literal that fired, so scheduler
    drift cannot spoof it."""
    wf = _load(name)
    declared = {c["cron"] for c in (wf.get("on") or wf.get(True))["schedule"]}
    guard = "\n".join(s.get("run", "") for s in _job_steps(wf))

    assert "github.event.schedule" in yaml.dump(wf), f"{name}: guard must see which cron fired"
    assert "date +%H" not in guard, f"{name}: still gating on the local hour"

    for offset, cron in CRON_GATED[name].items():
        assert cron in declared, f"{name}: guard references undeclared cron {cron!r}"
        assert f"{offset}) WANT='{cron}'" in guard, (
            f"{name}: at {offset} the guard must accept only {cron!r}")


def test_storage_baseline_check_never_auto_writes_storage_baseline_json():
    """This workflow is detection-only (mirrors imperial-register-check.yml):
    it may commit its own seen-state dotfile, but must never write
    storage-baseline.json itself -- a human always reviews and edits it."""
    wf = _load("storage-baseline-check.yml")
    on = wf.get("on") or wf.get(True)
    assert "workflow_dispatch" in on, "manual re-run path missing"
    assert "schedule" in on

    run_text = _all_run_text(wf)
    assert "check_storage_baseline_freshness.py" in run_text
    assert "storage-project-alerts-seen.json" in run_text
    # The only git-add target may be the seen-state file, never the curated JSON.
    add_lines = [ln for ln in run_text.splitlines() if ln.strip().startswith("git add")]
    assert add_lines, "expected a git add step for the seen-state file"
    for ln in add_lines:
        assert "storage-baseline.json" not in ln, \
            f"workflow must never git-add the curated JSON directly: {ln}"

    assert "RESEND_API_KEY" in run_text
    assert '::error::RESEND_API_KEY secret is not set' in run_text
    assert "exit 1" in run_text


def test_reconcile_workflow_delivers_routine_branch_pushes():
    """Regression for 2026-07-17/20/21: the scheduled routine runs on an isolated
    claude/* working branch, so its `git push origin main` lands on that branch,
    not main — email-briefing never fires and deadman reports a false no-fire.
    reconcile-routine-branch.yml brings routine-authored dated files onto main
    and dispatches the briefing email."""
    wf = _load("reconcile-routine-branch.yml")
    on = wf.get("on") or wf.get(True)
    assert "claude/**" in on["push"]["branches"], "must watch routine branches"
    assert "workflow_dispatch" in on, "manual reconcile path missing"

    # Must be able to write main and dispatch the email workflow.
    perms = wf.get("permissions", {})
    assert perms.get("contents") == "write"
    assert perms.get("actions") == "write"

    run_text = _all_run_text(wf)
    # Only routine-authored commits are ever merged to main.
    assert "ccs-news-routine@co2crc.com.au" in run_text
    assert "ccs-news-shadow@co2crc.com.au" in run_text
    # Never clobber a file already on main (protects manual backfills).
    assert "git cat-file -e" in run_text
    # GITHUB_TOKEN pushes don't trigger email-briefing, so it must be dispatched.
    assert "gh workflow run email-briefing.yml" in run_text


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
