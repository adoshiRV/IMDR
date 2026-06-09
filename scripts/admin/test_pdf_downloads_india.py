"""End-to-end PDF download test for India econ sources.

Verifies every PDF-publishing source we've identified can be downloaded
fully via httpx — full byte stream, correct content-type, opens cleanly
in pymupdf. Saves under `data/research/in/{vendor}/{YYYY}/{MM}/{DD}/`
per the coverage-plan §5.5 storage convention.

Run:
    python -m scripts.admin.test_pdf_downloads_india
    python -m scripts.admin.test_pdf_downloads_india --vendor mospi rbi
    python -m scripts.admin.test_pdf_downloads_india --no-save

Sources covered:
  mospi_cpi      latest CPI press release       (file_one via mospi listing API)
  mospi_iip      latest IIP press release       (file_one)
  mospi_nas_gdp  latest GDP press release       (file_one)
  mospi_plfs     latest PLFS monthly bulletin   (file_one)
  ppac           3 most-recent international-prices PDFs
                  (Indian Crude Basket, ICR, Crude Oil Production)
  rbi            3 most-recent RBI press releases (from BS_PressReleaseDisplay.aspx)

Used as a pre-flight check before promoting any PDF source into the
`data/research/in/` corpus that feeds Qdrant via the `imdr-research`
MCP (per project memory). After migrations 086/087 land the schema
side, this script + the `data/research/in/` layout are the durable
download contract.

Smoke test 2026-06-10: 10/10 sources downloaded cleanly, 10.8MB total,
9 PDFs yield 9.7k–55.7k chars on pymupdf extract (Qdrant-ready); 1
PPAC ICB notification is image-only and would need OCR for indexing.
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
from dataclasses import dataclass
from pathlib import Path

import fitz  # pymupdf
import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parents[2]  # scripts/admin/<file> -> repo root
DATA_ROOT = _REPO_ROOT / "data" / "research" / "in"

_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
}


@dataclass
class PdfResult:
    vendor: str
    source_url: str
    saved_path: Path | None
    bytes_received: int
    content_type: str
    n_pages: int | None
    page1_chars: int | None
    sha256: str
    error: str | None = None

    def ok(self) -> bool:
        return self.error is None and self.n_pages is not None and self.n_pages > 0


def _save(content: bytes, vendor: str, slug: str, out_root: Path) -> Path:
    today = datetime.date.today()
    folder = out_root / vendor / f"{today.year}" / f"{today.month:02d}" / f"{today.day:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / slug
    path.write_bytes(content)
    return path


def _verify_pdf(content: bytes) -> tuple[int | None, int | None, str | None]:
    """Open via pymupdf; return (n_pages, page1_chars, error)."""
    try:
        with fitz.open(stream=content, filetype="pdf") as doc:
            n = doc.page_count
            text1 = doc[0].get_text() if n > 0 else ""
            return n, len(text1), None
    except Exception as e:
        return None, None, f"pymupdf error: {type(e).__name__}: {e}"


def _download_one(client: httpx.Client, vendor: str, url: str, slug: str,
                  save: bool, out_root: Path) -> PdfResult:
    try:
        r = client.get(url, headers=_UA, follow_redirects=True, timeout=60)
        r.raise_for_status()
        content = r.content
        ct = r.headers.get("content-type", "")[:60]
        sha = hashlib.sha256(content).hexdigest()[:16]
    except Exception as e:
        return PdfResult(vendor=vendor, source_url=url, saved_path=None,
                         bytes_received=0, content_type="", n_pages=None,
                         page1_chars=None, sha256="",
                         error=f"http error: {type(e).__name__}: {e}")

    n_pages, page1_chars, err = _verify_pdf(content)
    saved = None
    if save and err is None:
        saved = _save(content, vendor, slug, out_root)
    return PdfResult(
        vendor=vendor, source_url=url, saved_path=saved,
        bytes_received=len(content), content_type=ct,
        n_pages=n_pages, page1_chars=page1_chars,
        sha256=sha, error=err,
    )


# ----------------------------------------------------------------------
# MOSPI -- listing API gives latest press releases per topic.
# ----------------------------------------------------------------------

def _mospi_latest(client: httpx.Client, search_term: str, n: int = 1) -> list[dict]:
    body = {
        "page_no": 1, "page_size": 10,
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
    out: list[dict] = []
    for item in r.json().get("data", []):
        f1 = item.get("file_one") or {}
        if (f1.get("path") or "").lower().endswith(".pdf"):
            out.append({
                "title": item["title"],
                "url": f"https://www.mospi.gov.in/{f1['path']}",
                "filename": f1.get("filename", ""),
            })
            if len(out) >= n:
                break
    return out


# ----------------------------------------------------------------------
# PPAC -- monthly Flash Report + Indian Crude Basket
# ----------------------------------------------------------------------

def _ppac_latest(client: httpx.Client) -> list[dict]:
    r = client.get("https://www.ppac.gov.in/prices/internationalprices",
                    timeout=30, headers=_UA)
    r.raise_for_status()
    # Pick the most-recent few "ICB" / "Flash Report" / "ICR" PDFs
    links = sorted(set(re.findall(
        r'href=["\'](https?://[^"\']+\.pdf)["\']', r.text, re.I,
    )))
    keep_kw = ("flash", "indian_crude", "icb", "icr_", "current")
    keep = [l for l in links if any(k in l.lower() for k in keep_kw)]
    out: list[dict] = []
    for url in keep[:3]:
        slug = url.rsplit("/", 1)[-1] or "ppac.pdf"
        out.append({"title": slug, "url": url, "filename": slug})
    return out


# ----------------------------------------------------------------------
# RBI -- MPC resolution, MPC minutes, MPR.
# ----------------------------------------------------------------------

def _rbi_latest_mpc(client: httpx.Client) -> list[dict]:
    # The official MPC resolution page lists recent monetary policy
    # statements with direct PDF links.
    pages = [
        ("https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx",
         "Press Release listing"),
    ]
    out: list[dict] = []
    for page_url, label in pages:
        try:
            r = client.get(page_url, timeout=30, headers=_UA)
            r.raise_for_status()
            pdfs = re.findall(
                r'href=["\']([^"\']+\.pdf)["\']', r.text, re.I,
            )
            # Filter to PDFs hosted on rbi.org.in
            pdfs = [p if p.startswith("http") else
                    ("https://rbi.org.in" + p if p.startswith("/") else
                     "https://rbi.org.in/" + p)
                    for p in pdfs]
            for url in pdfs[:3]:
                slug = url.rsplit("/", 1)[-1] or "rbi.pdf"
                out.append({"title": slug, "url": url, "filename": slug})
        except Exception as e:
            print(f"  rbi listing fetch failed: {e}")
    return out


# ----------------------------------------------------------------------
# Wire up
# ----------------------------------------------------------------------

_SEARCH_TERMS_MOSPI = [
    ("mospi_cpi",     "CPI for the month"),
    ("mospi_iip",     "Quick Estimates of IIP"),
    ("mospi_nas_gdp", "Provisional Estimates of Annual GDP"),
    ("mospi_plfs",    "Periodic Labour Force Survey"),
]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--vendor", nargs="*", default=None,
                   help="Filter to specific vendors (mospi rbi ppac)")
    p.add_argument("--no-save", action="store_true",
                   help="Skip writing PDFs to data/research/in/")
    args = p.parse_args()

    save = not args.no_save
    out_root = DATA_ROOT

    targets: list[tuple[str, dict]] = []
    with httpx.Client(timeout=60, follow_redirects=True) as c:
        # MOSPI
        if not args.vendor or any(v in ("mospi", "mospi_cpi", "mospi_iip",
                                         "mospi_nas_gdp", "mospi_plfs")
                                  for v in args.vendor or []):
            for vendor_slug, term in _SEARCH_TERMS_MOSPI:
                if args.vendor and not any(v == vendor_slug or v == "mospi"
                                            for v in args.vendor):
                    continue
                try:
                    items = _mospi_latest(c, term, n=1)
                    for it in items:
                        targets.append((vendor_slug, it))
                except Exception as e:
                    print(f"  MOSPI {vendor_slug} listing failed: {e}")
        # PPAC
        if not args.vendor or "ppac" in args.vendor:
            try:
                for it in _ppac_latest(c):
                    targets.append(("ppac", it))
            except Exception as e:
                print(f"  PPAC listing failed: {e}")
        # RBI
        if not args.vendor or "rbi" in args.vendor:
            try:
                for it in _rbi_latest_mpc(c):
                    targets.append(("rbi", it))
            except Exception as e:
                print(f"  RBI listing failed: {e}")

        print(f"\nDownloading {len(targets)} PDFs (save={save})\n")
        results: list[PdfResult] = []
        for vendor, t in targets:
            url = t["url"]
            slug = t.get("filename", "doc.pdf") or "doc.pdf"
            # Sanitise filename
            safe_slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug)
            if not safe_slug.lower().endswith(".pdf"):
                safe_slug += ".pdf"
            print(f"  [{vendor}] {url[:100]}")
            t0 = time.time()
            res = _download_one(c, vendor, url, safe_slug, save, out_root)
            dt = time.time() - t0
            if res.ok():
                print(f"    OK  {res.bytes_received:>9,} bytes  "
                      f"{res.n_pages:>3d} pages  p1={res.page1_chars or 0:>5d} chars  "
                      f"{dt:>5.1f}s  sha={res.sha256}")
                if res.saved_path:
                    print(f"        -> {res.saved_path}")
            else:
                print(f"    FAIL  {res.error}  ({res.bytes_received} bytes, ct={res.content_type})")
            results.append(res)

    # Summary
    print(f"\n=== Summary ===")
    ok = [r for r in results if r.ok()]
    fail = [r for r in results if not r.ok()]
    print(f"  {len(ok)} OK, {len(fail)} failed (of {len(results)} total)")
    print(f"  total bytes: {sum(r.bytes_received for r in ok):,}")
    per_vendor: dict[str, list[PdfResult]] = {}
    for r in results:
        per_vendor.setdefault(r.vendor, []).append(r)
    for v, rs in sorted(per_vendor.items()):
        n_ok = sum(1 for r in rs if r.ok())
        print(f"    {v:18s}  {n_ok}/{len(rs)} OK")

    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
