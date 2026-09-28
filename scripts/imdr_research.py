"""IMDR Research Orchestrator.

Runs the research ingest pipelines as named, tracked steps and tees output to a
timestamped log under ``logs/``. Mirrors the ``imdr_daily.py`` shape so it can
be scheduled the same way (Windows task ``IMDR_research``, every 3h).

Two lanes:

* **portal** — ``playground/research/ingest_today.py`` crawls the vendor portals.
* **email**  — ``outlook_mapi_pull.py`` stages the research mailbox off local
  Outlook via MAPI, then ``ingest_outlook.py --load`` chunks/embeds/loads it.

The email lane is two steps because they fail for unrelated reasons: the
producer depends on a responsive local Outlook, the ingest depends on the DB
and Qdrant. ``requires`` stops us loading a stale staging dir when the producer
never ran.

History note — this file previously carried the email steps but was never
committed, so a working-tree revert on 2026-07-01 silently removed them. The
scheduled task kept running the portal lane and looked healthy while the email
lane was dark for 85 days. Keep this file TRACKED.

Usage:
    python -m scripts.imdr_research
    python -m scripts.imdr_research --list
    python -m scripts.imdr_research --only email-stage,email-ingest
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "logs"

# Vendor titles carry en-dashes and CJK; the Windows console is cp1252 and
# sys.stdout.write would raise UnicodeEncodeError mid-run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Producer exit code for "Outlook is not reachable" — an environment condition
# (Outlook closed, mid-update, parked on a profile dialog), not a code fault.
# Reported as UNAVAILABLE so a genuine break stays visible against the noise.
RC_COM_UNAVAILABLE = 3

# ============================================================================
# REGISTERED RESEARCH PIPELINES
# ============================================================================

PIPELINES: list[dict] = [
    {
        "name": "portal-research",
        "cmd": [sys.executable, "playground/research/ingest_today.py", "--embed"],
        # ingest_today ends with a per-vendor table whose last row is the
        # TOTAL line — it does not print a bracketed tag like the email lane.
        "summary_re": r"^TOTAL\s+\d+.*$",
    },
    {
        "name": "email-stage",
        "cmd": [sys.executable, "playground/research/outlook/outlook_mapi_pull.py"],
        "summary_re": r"^\[done\].*$",
    },
    {
        "name": "email-ingest",
        "cmd": [sys.executable, "playground/research/ingest_outlook.py", "--load"],
        "requires": "email-stage",
        "summary_re": r"^\[LOAD\].*$",
    },
]

# ============================================================================


def _run_step(entry: dict, log_fh) -> dict:
    """Run one step, teeing stdout to console + log, returning its record."""
    name = entry["name"]
    print(f"RUN   {name}")
    t0 = time.perf_counter()
    summary = ""
    pattern = re.compile(entry["summary_re"], re.MULTILINE) if entry.get("summary_re") else None

    proc = subprocess.Popen(
        entry["cmd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(REPO_ROOT),
        bufsize=1,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        log_fh.write(line)
        log_fh.flush()
        if pattern and pattern.match(line.strip()):
            summary = line.strip()
    rc = proc.wait()
    elapsed = time.perf_counter() - t0

    if rc == 0:
        status = "OK"
    elif name == "email-stage" and rc == RC_COM_UNAVAILABLE:
        status = "UNAVAILABLE"
    else:
        status = "FAIL"

    marker = {"OK": "OK   ", "UNAVAILABLE": "UNAVL", "FAIL": "FAIL "}[status]
    print(f"{marker} {name}  rc={rc}  ({elapsed:.1f}s)  {summary}")
    return {
        "name": name,
        "rc": rc,
        "elapsed_s": round(elapsed, 1),
        "status": status,
        "summary": summary,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated step names to run")
    ap.add_argument("--list", action="store_true", help="list step names and exit")
    args = ap.parse_args()

    if args.list:
        for entry in PIPELINES:
            req = f"  (requires {entry['requires']})" if entry.get("requires") else ""
            print(f"{entry['name']}{req}")
        return 0

    selected = PIPELINES
    if args.only:
        wanted = {n.strip() for n in args.only.split(",") if n.strip()}
        unknown = wanted - {e["name"] for e in PIPELINES}
        if unknown:
            print(f"unknown step(s): {', '.join(sorted(unknown))}")
            return 2
        selected = [e for e in PIPELINES if e["name"] in wanted]

    if not selected:
        return 0

    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    log_path = LOG_DIR / f"research_ingest_{stamp}.log"
    summary_path = LOG_DIR / f"research_ingest_{stamp}.summary.json"
    print(f"Log: {log_path}\n")

    selected_names = {e["name"] for e in selected}
    records: list[dict] = []
    ok_steps: set[str] = set()

    with log_path.open("w", encoding="utf-8") as log_fh:
        for entry in selected:
            # `requires` is only enforced when the prerequisite is part of THIS
            # run, so `--only email-ingest` against an already-staged dir works.
            req = entry.get("requires")
            if req and req in selected_names and req not in ok_steps:
                print(f"SKIP  {entry['name']}  (requires {req})")
                records.append({
                    "name": entry["name"], "rc": None, "elapsed_s": 0.0,
                    "status": "SKIP", "summary": f"requires {req}",
                })
                continue

            rec = _run_step(entry, log_fh)
            records.append(rec)
            if rec["status"] == "OK":
                ok_steps.add(entry["name"])

    failed = [r["name"] for r in records if r["status"] == "FAIL"]
    unavailable = [r["name"] for r in records if r["status"] == "UNAVAILABLE"]
    skipped = [r["name"] for r in records if r["status"] == "SKIP"]

    summary_path.write_text(
        json.dumps(
            {
                "stamp": stamp,
                "steps": records,
                "failed": failed,
                "unavailable": unavailable,
                "skipped": skipped,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSummary: {summary_path}")

    if unavailable:
        print(f"{len(unavailable)} step(s) unavailable: {', '.join(unavailable)}")
    if failed:
        print(f"{len(failed)} step(s) failed: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
