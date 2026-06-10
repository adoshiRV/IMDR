"""Bank Indonesia SRBI (Sekuritas Rupiah Bank Indonesia) auction-result parser.

SRBI is BI's sterilisation paper, launched 2023-09-15. Each auction
result is published one-per-page at:

  https://www.bi.go.id/id/publikasi/lelang/operasi-moneter/Pages/
    Hasil-Lelang-SRBI-{D}-{Bulan-ID}-{YYYY}.aspx

Where ``Bulan-ID`` is the Indonesian month name and the day is not
zero-padded. Each page carries a single 11-row HTML table; the canonical
yield series is row ``Rata-Rata Tertimbang Pemenang (%)`` — the
weighted-average winning yield per tenor.

Auctions are roughly twice-weekly (Wed + Fri); the URL responds 200 on
auction days and 302 on non-auction days. Tenors since launch have been
1/3/6/9/12 months; the current cycle (mid-2024 onward) runs 6/9/12 only.
"""

from __future__ import annotations

import datetime
import re
import time
from dataclasses import dataclass

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


MONTH_ID = [
    "",
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

_URL_TEMPLATE = (
    "https://www.bi.go.id/id/publikasi/lelang/operasi-moneter/"
    "Pages/Hasil-Lelang-SRBI-{day}-{bulan}-{year}.aspx"
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# BI's web tier intermittently TLS-resets from corp networks (see
# memory file feedback_kr_govt_flaky_tls_patient_retry.md for the same
# pattern across KR govt sites). 6-retry exponential.
_RETRIES = 6
_BACKOFF_BASE = 1.5

# SRBI's first auction.
LAUNCH_DATE = datetime.date(2023, 9, 15)


@dataclass(frozen=True)
class SrbiAuction:
    auction_date: datetime.date
    tenor_months: int
    days_to_maturity: int
    wa_winning_yield_pct: float


def auction_url(d: datetime.date) -> str:
    return _URL_TEMPLATE.format(day=d.day, bulan=MONTH_ID[d.month], year=d.year)


def _strip(html: str) -> str:
    s = re.sub(r"<[^>]+>", " ", html)
    s = s.replace("&nbsp;", " ").replace("&#160;", " ")
    return re.sub(r"\s+", " ", s).strip()


def _parse_pct(raw: str) -> float | None:
    if not raw or raw.strip() == "-":
        return None
    cleaned = raw.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_tenor(raw: str) -> tuple[int, int] | None:
    m = re.search(r"(\d+)\s*Bulan\s*\((\d+)\s*Hari\)", raw, re.IGNORECASE)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def parse_srbi_page(html: str, auction_date: datetime.date) -> list[SrbiAuction]:
    """Extract per-tenor winning yields from one SRBI auction page HTML."""
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.IGNORECASE | re.DOTALL)
    if not tables:
        return []
    rows_by_label: dict[str, list[str]] = {}
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", tables[0], re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.IGNORECASE | re.DOTALL)
        if not cells:
            continue
        clean = [_strip(c) for c in cells]
        rows_by_label[clean[0]] = clean[1:]

    tenor_row = None
    yield_row = None
    for label, values in rows_by_label.items():
        if "Jangka Waktu" in label and tenor_row is None:
            tenor_row = values
        elif "Rata-Rata Tertimbang Pemenang" in label and yield_row is None:
            yield_row = values

    if tenor_row is None or yield_row is None:
        return []

    out: list[SrbiAuction] = []
    for tenor_raw, yield_raw in zip(tenor_row, yield_row):
        parsed_tenor = _parse_tenor(tenor_raw)
        if parsed_tenor is None:
            continue
        months, days = parsed_tenor
        y = _parse_pct(yield_raw)
        if y is None:
            continue
        out.append(SrbiAuction(
            auction_date=auction_date,
            tenor_months=months,
            days_to_maturity=days,
            wa_winning_yield_pct=y,
        ))
    return out


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept-Language": "id-ID,id;q=0.9,en;q=0.8"})
    return s


def fetch_auction_page(
    session: requests.Session,
    auction_date: datetime.date,
    *,
    timeout: int = 30,
) -> str | None:
    """Return raw HTML for the auction date, or None if no auction that day.

    302 → no auction (BI redirects unknown dates). 200 → page exists.
    Retries transient network errors with exponential backoff.
    """
    url = auction_url(auction_date)
    last_exc: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            r = session.get(url, timeout=timeout, verify=False, allow_redirects=False)
            if r.status_code == 200:
                return r.text
            return None
        except (requests.exceptions.RequestException, OSError) as e:
            last_exc = e
            time.sleep(_BACKOFF_BASE ** attempt)
    if last_exc is not None:
        raise last_exc
    return None


def fetch_srbi_window(
    since: datetime.date,
    until: datetime.date,
    *,
    session: requests.Session | None = None,
    log_every: int = 50,
) -> list[SrbiAuction]:
    """Walk every weekday in [since, until] and collect SRBI auction yields.

    Sleeps 200ms between requests to be polite to BI's web tier.
    """
    sess = session or make_session()
    auctions: list[SrbiAuction] = []
    days_checked = 0
    days_hit = 0
    d = since
    while d <= until:
        if d.weekday() < 5:
            try:
                html = fetch_auction_page(sess, d)
            except Exception as e:
                print(f"  {d}: fetch failed after retries — {e!r}")
                html = None
            days_checked += 1
            if html is not None:
                rows = parse_srbi_page(html, d)
                if rows:
                    auctions.extend(rows)
                    days_hit += 1
            if days_checked % log_every == 0:
                print(f"  ... walked {days_checked} days, {days_hit} auctions hit, last={d}")
            time.sleep(0.2)
        d += datetime.timedelta(days=1)
    print(f"  walked {days_checked} days, {days_hit} auctions hit")
    return auctions
