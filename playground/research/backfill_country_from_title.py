"""Heuristic country_id backfill from report titles (sell-side NULLs only).

The tag-based backfill (backfill_region_country.py) can't help the ~3.9k
sell-side reports that never carried a country signal. Many are genuinely
multi-country ("Asia ex-Japan Equity Strategy") and SHOULD stay NULL — but a
chunk have an unambiguous single-country anchor in the title (BoJ, RBA,
FOMC, ...). This assigns country_id for those, conservatively.

Rules:
  * only reports with country_id IS NULL are considered;
  * a report is assigned a country only if EXACTLY ONE country's pattern
    matches its title;
  * regional / multi-country titles are vetoed by ``_VETO`` (ex-Japan,
    Asia, global, EM, G10, ...) so we never pin a single country on a
    cross-region piece.

DRY-RUN by default; --commit to write. Prints sample assignments so the
heuristic can be eyeballed before committing.
"""
from __future__ import annotations

import argparse
import re
from collections import Counter

from sqlalchemy import text

from backfill_region_country import _research_engine

# country code -> compiled title pattern (unambiguous anchors only)
_PATTERNS: dict[str, re.Pattern[str]] = {
    "JP": re.compile(r"\b(bo[j]|jgb|jpy)\b|bank of japan|usd/jpy|tokyo cpi|\bueda\b", re.I),
    "AU": re.compile(r"\b(rba|aud)\b|reserve bank of australia|\baustralia\b|aussie", re.I),
    "US": re.compile(r"\bfomc\b|federal reserve|\bfed\b|\bust\b|jackson hole|powell|\bwarsh\b", re.I),
    "NZ": re.compile(r"\b(rbnz|nzd)\b|reserve bank of new zealand|new zealand", re.I),
    "CN": re.compile(r"\b(pboc|cny|rmb)\b|people'?s bank of china|onshore china", re.I),
    "IN": re.compile(r"\b(rbi)\b|reserve bank of india", re.I),
}

# regional / multi-country signals — veto a single-country assignment
_VETO = re.compile(
    r"ex[\s-]?japan|ex[\s-]?china|asia|apac|global|world|emea|\bem\b|"
    r"g-?10|g-?7|emerging|cross[\s-]?asset|latam|americas|europe",
    re.I,
)


def _infer(title: str) -> str | None:
    if _VETO.search(title):
        return None
    hits = [code for code, pat in _PATTERNS.items() if pat.search(title)]
    return hits[0] if len(hits) == 1 else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--samples", type=int, default=8,
                    help="sample titles to print per inferred country")
    args = ap.parse_args()

    from imdr.config.settings import get_settings  # noqa: PLC0415

    engine = _research_engine(get_settings())
    with engine.begin() as conn:
        cid_by_code = {
            code: cid for cid, code in conn.execute(
                text("SELECT id, country_code FROM dbo.dim_country")
            )
        }
        rows = conn.execute(text(
            "SELECT id, title FROM research.dim_report WHERE country_id IS NULL"
        )).fetchall()

        updates: dict[int, int] = {}
        samples: dict[str, list[str]] = {}
        for rid, title in rows:
            code = _infer(title or "")
            if code and code in cid_by_code:
                updates[rid] = cid_by_code[code]
                samples.setdefault(code, [])
                if len(samples[code]) < args.samples:
                    samples[code].append(title)

        code_by_cid = {v: k for k, v in cid_by_code.items()}
        print(f"Scanned {len(rows)} NULL-country reports; {len(updates)} assignable.\n")
        for cid, n in Counter(updates.values()).most_common():
            code = code_by_cid[cid]
            print(f"  {code}: {n}")
            for tt in samples.get(code, []):
                print(f"       - {tt[:90]}")
            print()

        if not args.commit:
            print("DRY-RUN — no rows written. Re-run with --commit to apply.")
            return

        conn.execute(
            text("UPDATE research.dim_report SET country_id=:cid, "
                 "updated_at=SYSDATETIMEOFFSET() WHERE id=:id"),
            [{"id": rid, "cid": cid} for rid, cid in updates.items()],
        )
        print(f"COMMITTED — country_id set on {len(updates)} reports.")


if __name__ == "__main__":
    main()
