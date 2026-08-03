#!/usr/bin/env python3
"""Fingerprint deterministic authoritative sources and emit change alerts."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "config" / "authoritative-sources.yml"
OUT = ROOT / "dashboard" / "data" / "monitoring"
USER_AGENT = "CCS-Intelligence-Monitor/1.0 (+scheduled GitHub Actions)"


def canonical_bytes(payload: bytes, mode: str) -> bytes:
    if mode == "json":
        value = json.loads(payload.decode("utf-8"))
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return b" ".join(payload.split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--output-dir", type=Path, default=OUT)
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    sources = registry.get("sources", [])
    ids = [source["id"] for source in sources]
    if not sources or len(ids) != len(set(ids)):
        raise ValueError("authoritative source registry is empty or contains duplicate ids")
    required = {"id", "title", "source_class", "geographies", "url", "mode", "human_review_on_change"}
    for source in sources:
        if not required <= set(source) or source["mode"] not in ("page", "json"):
            raise ValueError(f"invalid source registry row: {source}")
    if args.validate_only:
        print(f"Validated {len(sources)} authoritative sources")
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    state_path = args.output_dir / "fingerprints.json"
    previous = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    now = datetime.now(timezone.utc).isoformat()
    current, results = {}, []
    for source in sources:
        request = urllib.request.Request(source["url"], headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                fingerprint = hashlib.sha256(canonical_bytes(payload, source["mode"])).hexdigest()
                status = response.status
                error = ""
                etag = response.headers.get("ETag", "")
                modified = response.headers.get("Last-Modified", "")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            fingerprint, status, etag, modified, error = "", 0, "", "", str(exc)
        prior = previous.get(source["id"], {}).get("sha256", "")
        changed = bool(prior and fingerprint and prior != fingerprint)
        current[source["id"]] = {
            "sha256": fingerprint or prior, "retrieved_at": now,
            "http_status": status, "etag": etag, "last_modified": modified,
            "url": source["url"], "error": error,
        }
        results.append({
            "id": source["id"], "title": source["title"], "source_class": source["source_class"],
            "retrieved_at": now, "http_status": status,
            "status": "retrieval-failed" if error else ("changed" if changed else ("initialised" if not prior else "unchanged")),
            "human_review": bool(changed and source["human_review_on_change"]),
            "old_sha256": prior, "new_sha256": fingerprint, "error": error,
        })
    state_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    report = {"generated_at": now, "results": results}
    (args.output_dir / "latest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Authoritative CCS source monitor", "", f"Retrieved: {now}", ""]
    for row in results:
        marker = "REVIEW" if row["human_review"] else row["status"].upper()
        detail = f" — {row['error']}" if row["error"] else ""
        lines.append(f"- **{marker}** {row['title']}{detail}")
    (args.output_dir / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    failures = sum(row["status"] == "retrieval-failed" for row in results)
    reviews = sum(row["human_review"] for row in results)
    print(f"Monitored {len(results)} sources: {failures} failures; {reviews} human-review alerts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
