"""Bulk PDF corpus downloader for India econ + research sources.

Builds on `test_pdf_downloads_india.py` (the pre-flight check) by
downloading the FULL backlog from every PDF-publishing source we've
identified. Saves under
    data/research/in/{vendor}/{YYYY}/{MM}/{DD}/{filename}.pdf
per the coverage-plan §5.5 storage convention.

Idempotent: skips files that already exist on disk with non-zero size.
Polite: ~1s throttle per request inside a vendor; 5s between vendors.

Sources covered (post-2026-06-10 sweep):
  mospi_cpi        MOSPI CPI monthly press releases (N=24 by default)
  mospi_iip        MOSPI IIP monthly press releases (N=24)
  mospi_nas_gdp    MOSPI NAS GDP / quarterly + annual press notes
  mospi_plfs       MOSPI PLFS Annual + Quarterly + Monthly bulletins
  ppac             All PDFs linked from /prices/internationalprices
  rbi_press        RBI press releases (recent monetary policy + ad-hoc)
  rbi_mpc_minutes  RBI MPC minutes (Publication Report ID=911)
  rbi_mpr          RBI Monetary Policy Report (semi-annual)
  rbi_fsr          RBI Financial Stability Report (semi-annual)
  rbi_annual       RBI Annual Report (annual)
  rbi_bulletin     RBI Monthly Bulletin chapters
  rbi_notifs       RBI regulatory Notifications archive
  rbi_speeches     RBI Governor + Deputy Governor speeches
  budget           Union Budget receipts/expenditure books + speech
  econ_survey      Economic Survey + Statistical Appendix
  cga              CGA monthly press notes (companion to A14 XLSM)

Run:
    python -m scripts.admin.download_india_pdf_corpus
    python -m scripts.admin.download_india_pdf_corpus --vendor mospi_cpi rbi_bulletin
    python -m scripts.admin.download_india_pdf_corpus --max-per-vendor 100
    python -m scripts.admin.download_india_pdf_corpus --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import fitz  # pymupdf
import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = _REPO_ROOT / "data" / "research" / "in"

_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
}

THROTTLE_S = 0.8  # within-vendor


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DlResult:
    vendor: str
    url: str
    saved_path: Path | None = None
    bytes_received: int = 0
    n_pages: int | None = None
    sha256: str = ""
    error: str | None = None
    skipped: bool = False

    def ok(self) -> bool:
        return self.error is None and (self.skipped or (self.n_pages is not None and self.n_pages > 0))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s[:160] or "doc.pdf"


def _save(content: bytes, vendor: str, slug: str) -> Path:
    today = datetime.date.today()
    folder = DATA_ROOT / vendor / f"{today.year}" / f"{today.month:02d}" / f"{today.day:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    if not slug.lower().endswith((".pdf",)):
        slug += ".pdf"
    path = folder / slug
    path.write_bytes(content)
    return path


def _existing_path(vendor: str, slug: str) -> Path | None:
    """Check if this file already exists anywhere under data/research/in/{vendor}/...
    Returns the path if found (with non-zero size), else None."""
    safe = _safe_slug(slug)
    if not safe.lower().endswith(".pdf"):
        safe += ".pdf"
    base = DATA_ROOT / vendor
    if not base.exists():
        return None
    for p in base.rglob(safe):
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def _verify(content: bytes) -> tuple[int | None, str | None]:
    try:
        with fitz.open(stream=content, filetype="pdf") as doc:
            return doc.page_count, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _download(client: httpx.Client, vendor: str, url: str, slug: str,
              dry_run: bool = False) -> DlResult:
    safe = _safe_slug(slug)
    existing = _existing_path(vendor, safe)
    if existing:
        return DlResult(vendor=vendor, url=url, saved_path=existing,
                         bytes_received=existing.stat().st_size, skipped=True)
    if dry_run:
        return DlResult(vendor=vendor, url=url, saved_path=None,
                         bytes_received=0, skipped=True)
    try:
        r = client.get(url, headers=_UA, follow_redirects=True, timeout=60)
        r.raise_for_status()
        content = r.content
    except Exception as e:
        return DlResult(vendor=vendor, url=url, saved_path=None,
                         bytes_received=0, error=f"http: {type(e).__name__}: {e}")
    if len(content) < 200:
        return DlResult(vendor=vendor, url=url, saved_path=None,
                         bytes_received=len(content),
                         error=f"tiny body ({len(content)}b) — likely an error page")
    n_pages, err = _verify(content)
    if err:
        return DlResult(vendor=vendor, url=url, saved_path=None,
                         bytes_received=len(content), error=err)
    saved = _save(content, vendor, safe)
    sha = hashlib.sha256(content).hexdigest()[:16]
    return DlResult(vendor=vendor, url=url, saved_path=saved,
                     bytes_received=len(content), n_pages=n_pages, sha256=sha)


# ---------------------------------------------------------------------------
# Per-vendor harvesters: each returns a list of (url, suggested_filename).
# ---------------------------------------------------------------------------

def _mospi_via_listing(client: httpx.Client, search_term: str, n: int) -> list[tuple[str, str]]:
    body = {
        "page_no": 1, "page_size": max(n, 50),
        "search_term": search_term,
        "sort_field": "published_year", "sort_order": "DESC",
        "from_date": "", "to_date": "",
        "lang": "en", "data_source": "web",
    }
    r = client.post(
        "https://www.mospi.gov.in/api/latest-release/get-web-latest-release-list",
        json=body,
        headers={**_UA, "Content-Type": "application/json",
                 "Referer": "https://mospi.gov.in/"},
        timeout=30,
    )
    r.raise_for_status()
    out = []
    for item in r.json().get("data", []):
        f1 = item.get("file_one") or {}
        path = f1.get("path", "")
        if not path.lower().endswith(".pdf"):
            continue
        url = f"https://www.mospi.gov.in/{path}"
        name = f1.get("filename") or path.rsplit("/", 1)[-1]
        out.append((url, name))
        if len(out) >= n:
            break
    return out


def harv_mospi_cpi(client, n):       return _mospi_via_listing(client, "CPI for the month", n)
def harv_mospi_iip(client, n):       return _mospi_via_listing(client, "Quick Estimates of IIP", n)
def harv_mospi_nas_gdp(client, n):
    out = _mospi_via_listing(client, "Provisional Estimates of Annual GDP", n)
    out += _mospi_via_listing(client, "Quarterly Estimates of GDP", n)
    return out[:n]
def harv_mospi_plfs(client, n):      return _mospi_via_listing(client, "Periodic Labour Force", n)


def harv_ppac(client, n):
    url = "https://www.ppac.gov.in/prices/internationalprices"
    r = client.get(url, headers=_UA, timeout=30)
    r.raise_for_status()
    links = sorted(set(re.findall(
        r'href=["\'](https?://(?:www\.)?ppac\.gov\.in/[^"\']*download\.php\?file=[^"\']+\.pdf)["\']',
        r.text, re.I,
    )))
    out = []
    for u in links:
        slug = u.split("file=", 1)[-1].rsplit("/", 1)[-1]
        out.append((u, slug))
    return out[:n]


def _rbi_pdf_links_from_page(client, page_url: str) -> list[tuple[str, str]]:
    """Scrape an RBI listing page; return rbidocs.rbi.org.in PDF links only."""
    r = client.get(page_url, headers=_UA, timeout=30)
    r.raise_for_status()
    pdfs = re.findall(r'href=["\']([^"\']+\.pdf)["\']', r.text, re.I)
    out = []
    for p in pdfs:
        if p.startswith("http"):
            u = p
        elif p.startswith("/"):
            u = "https://rbi.org.in" + p
        else:
            u = "https://rbi.org.in/" + p
        # Filter to rbidocs.rbi.org.in to avoid grabbing footer/random PDFs
        if "rbidocs.rbi.org.in" not in u:
            continue
        slug = u.rsplit("/", 1)[-1]
        out.append((u, slug))
    # Dedupe preserving order
    seen = set()
    deduped = []
    for u, s in out:
        if u in seen:
            continue
        seen.add(u)
        deduped.append((u, s))
    return deduped


def harv_rbi_press(client, n):
    return _rbi_pdf_links_from_page(client,
        "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx")[:n]


def harv_rbi_mpc_minutes(client, n):
    return _rbi_pdf_links_from_page(client,
        "https://www.rbi.org.in/Scripts/PublicationReport.aspx?ID=911")[:n]


def harv_rbi_mpr(client, n):
    return _rbi_pdf_links_from_page(client,
        "https://www.rbi.org.in/Scripts/Publications.aspx?head=Monetary%20Policy%20Report")[:n]


def harv_rbi_fsr(client, n):
    return _rbi_pdf_links_from_page(client,
        "https://www.rbi.org.in/Scripts/Publications.aspx?head=Financial+Stability+Report")[:n]


def harv_rbi_annual(client, n):
    return _rbi_pdf_links_from_page(client,
        "https://www.rbi.org.in/Scripts/AnnualReportPublications.aspx")[:n]


def harv_rbi_bulletin(client, n):
    return _rbi_pdf_links_from_page(client,
        "https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx")[:n]


def harv_rbi_notifs(client, n):
    return _rbi_pdf_links_from_page(client,
        "https://www.rbi.org.in/Scripts/NotificationUser.aspx")[:n]


def harv_rbi_speeches(client, n):
    return _rbi_pdf_links_from_page(client,
        "https://www.rbi.org.in/scripts/BS_speechesview.aspx")[:n]


def harv_budget(client, n):
    base = "https://www.indiabudget.gov.in/"
    r = client.get(base, headers=_UA, timeout=30)
    r.raise_for_status()
    pdfs = sorted(set(re.findall(r'href=["\']([^"\']+\.pdf)["\']', r.text, re.I)))
    out = []
    for p in pdfs:
        u = p if p.startswith("http") else (base + p.lstrip("/"))
        slug = u.rsplit("/", 1)[-1]
        out.append((u, slug))
    return out[:n]


def harv_econ_survey(client, n):
    base = "https://www.indiabudget.gov.in/economicsurvey/"
    r = client.get(base, headers=_UA, timeout=30)
    r.raise_for_status()
    pdfs = sorted(set(re.findall(r'href=["\']([^"\']+\.pdf)["\']', r.text, re.I)))
    out = []
    for p in pdfs:
        if p.startswith("http"):
            u = p
        elif p.startswith("/"):
            u = "https://www.indiabudget.gov.in" + p
        else:
            u = base + p
        slug = u.rsplit("/", 1)[-1]
        out.append((u, slug))
    return out[:n]


def harv_cga_press(client, n):
    """CGA's MonthlyReport.aspx returns a server-rendered table; rebuilt to
    pull all PDFs linked from the page (mostly press notes for Monthly
    Accounts of GoI)."""
    r = client.get("https://cga.nic.in/MonthlyReport.aspx", headers=_UA, timeout=30)
    r.raise_for_status()
    pdfs = sorted(set(re.findall(r'href=["\']([^"\']+\.pdf)["\']', r.text, re.I)))
    out = []
    for p in pdfs:
        u = p if p.startswith("http") else ("https://cga.nic.in" + (p if p.startswith("/") else "/" + p))
        slug = u.rsplit("/", 1)[-1]
        out.append((u, slug))
    return out[:n]


# ---------------------------------------------------------------------------
# Vendor registry
# ---------------------------------------------------------------------------

HARVESTERS: dict[str, Callable] = {
    "mospi_cpi":       harv_mospi_cpi,
    "mospi_iip":       harv_mospi_iip,
    "mospi_nas_gdp":   harv_mospi_nas_gdp,
    "mospi_plfs":      harv_mospi_plfs,
    "ppac":            harv_ppac,
    "rbi_press":       harv_rbi_press,
    "rbi_mpc_minutes": harv_rbi_mpc_minutes,
    "rbi_mpr":         harv_rbi_mpr,
    "rbi_fsr":         harv_rbi_fsr,
    "rbi_annual":      harv_rbi_annual,
    "rbi_bulletin":    harv_rbi_bulletin,
    "rbi_notifs":      harv_rbi_notifs,
    "rbi_speeches":    harv_rbi_speeches,
    "budget":          harv_budget,
    "econ_survey":     harv_econ_survey,
    "cga":             harv_cga_press,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--vendor", nargs="*", default=None,
                   help="Filter to specific vendors (default: all)")
    p.add_argument("--max-per-vendor", type=int, default=50,
                   help="Max PDFs per vendor (default 50)")
    p.add_argument("--dry-run", action="store_true",
                   help="List + size check only, don't download")
    args = p.parse_args()

    vendors = args.vendor or list(HARVESTERS.keys())
    vendors = [v for v in vendors if v in HARVESTERS]
    if not vendors:
        print(f"No matching vendors. Available: {list(HARVESTERS.keys())}")
        return 1

    print(f"Vendors: {', '.join(vendors)}")
    print(f"Max per vendor: {args.max_per_vendor}")
    print(f"Dry run: {args.dry_run}")
    print(f"Saving to: {DATA_ROOT}\n")

    results: list[DlResult] = []
    per_vendor: dict[str, list[DlResult]] = {}

    with httpx.Client(timeout=60, follow_redirects=True) as c:
        for vendor in vendors:
            print(f"\n=== {vendor} ===")
            try:
                targets = HARVESTERS[vendor](c, args.max_per_vendor)
            except Exception as e:
                print(f"  harvester failed: {type(e).__name__}: {e}")
                continue
            print(f"  {len(targets)} candidate PDFs found")
            per_vendor.setdefault(vendor, [])
            for i, (url, slug) in enumerate(targets, 1):
                t0 = time.time()
                res = _download(c, vendor, url, slug, dry_run=args.dry_run)
                results.append(res)
                per_vendor[vendor].append(res)
                if res.skipped:
                    if res.saved_path:
                        print(f"  [{i:>3}/{len(targets)}] SKIP (already on disk): {res.saved_path.name[:80]}")
                    else:
                        print(f"  [{i:>3}/{len(targets)}] DRY-RUN: {url[:80]}")
                elif res.ok():
                    print(f"  [{i:>3}/{len(targets)}] OK   {res.bytes_received:>9,} bytes  "
                          f"{res.n_pages:>3d}p  {time.time()-t0:.1f}s  {res.saved_path.name[:60]}")
                else:
                    print(f"  [{i:>3}/{len(targets)}] FAIL {res.error[:80]}")
                time.sleep(THROTTLE_S)
            time.sleep(2)  # between vendors

    # Summary
    print(f"\n\n=== Summary ===")
    total_ok = sum(1 for r in results if r.ok() and not r.skipped)
    total_skip = sum(1 for r in results if r.skipped)
    total_fail = sum(1 for r in results if not r.ok())
    total_bytes = sum(r.bytes_received for r in results if r.ok())
    print(f"  {total_ok} downloaded, {total_skip} skipped (existing/dry), {total_fail} failed")
    print(f"  total bytes: {total_bytes:,}")
    print(f"\n  per-vendor:")
    for v in vendors:
        rs = per_vendor.get(v, [])
        ok = sum(1 for r in rs if r.ok() and not r.skipped)
        skip = sum(1 for r in rs if r.skipped)
        fail = sum(1 for r in rs if not r.ok())
        bytes_v = sum(r.bytes_received for r in rs if r.ok())
        print(f"    {v:18s}  {ok:>3d} ok, {skip:>3d} skip, {fail:>3d} fail   "
              f"{bytes_v / 1024 / 1024:>6.1f} MB")

    # Write a manifest JSON for downstream Qdrant ingest
    today = datetime.date.today()
    manifest_path = DATA_ROOT / f"_manifest_{today.isoformat()}.json"
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = [
        {"vendor": r.vendor, "url": r.url,
         "saved_path": str(r.saved_path) if r.saved_path else None,
         "bytes": r.bytes_received, "pages": r.n_pages,
         "sha256": r.sha256, "skipped": r.skipped,
         "error": r.error}
        for r in results
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    print(f"\n  manifest -> {manifest_path}")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
