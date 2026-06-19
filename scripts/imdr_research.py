"""IMDR Research Orchestrator.

Runs the research ingest pipeline via subprocess and tees output to a
timestamped log under ``logs/``. Mirrors the ``imdr_daily.py`` shape so
it can be scheduled the same way.

Equivalent to:
    python playground\\research\\ingest_today.py --embed 2>&1 | \\
        Tee-Object -FilePath "logs\\research_ingest_$(Get-Date -Format yyyyMMdd_HHmm).log"

Usage:
    python -m scripts.imdr_research
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "logs"

# ============================================================================
# REGISTERED RESEARCH PIPELINES
# ============================================================================

PIPELINES: list[dict] = [
    {"cmd": [sys.executable, "playground/research/ingest_today.py", "--embed"]},
]

# ============================================================================


def main() -> int:
    if not PIPELINES:
        return 0

    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    log_path = LOG_DIR / f"research_ingest_{stamp}.log"
    print(f"Log: {log_path}\n")

    failed: list[str] = []

    with log_path.open("w", encoding="utf-8") as log_fh:
        for entry in PIPELINES:
            cmd = entry["cmd"]
            name = cmd[-2] if cmd[-1].startswith("--") else cmd[-1]

            print(f"RUN   {name}")
            t0 = time.perf_counter()
            proc = subprocess.Popen(
                cmd,
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
            rc = proc.wait()
            elapsed = time.perf_counter() - t0

            if rc != 0:
                print(f"FAIL  {name}  rc={rc}  ({elapsed:.1f}s)")
                failed.append(name)
            else:
                print(f"OK    {name}  ({elapsed:.1f}s)")

    if failed:
        print(f"\n{len(failed)} pipeline(s) failed: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
