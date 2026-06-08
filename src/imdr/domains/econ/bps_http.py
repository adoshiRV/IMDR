"""HTTP helper for BPS (Badan Pusat Statistik) Web API.

BPS Web API base: ``https://webapi.bps.go.id/v1/api/``
Auth: query-string key (``?key={IMDR_BPS_API_KEY}``).

Three distinct sub-paths:
  - /v1/api/domain  — master domain catalogue (4-digit BPS web-domain IDs)
  - /v1/api/list    — catalogue + data listings, discriminated by ?model=...
  - /v1/api/view    — single-resource detail by ID

This module owns:
  - Loading ``IMDR_BPS_API_KEY`` from env or .env
  - A throttled requests.Session with the key cached
  - Thin GET helpers per endpoint family that mask the key in logs
  - A paginator that walks the ``list``-family ``[meta, rows]`` envelope
  - ``bps_fetch_data_chunked`` that splits multi-year requests around the
    server's 3-year ``th`` cap and parses ``datacontent`` via cartesian-
    product reverse-map (composite keys have variable-width IDs)
  - ``turtahun_to_period`` translating BPS turtahun IDs to (month, freq)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Iterator

import requests


_BPS_BASE = "https://webapi.bps.go.id/v1/api/"
_REPO_ROOT = Path(__file__).resolve().parents[4]

_RETRIES = 4
_RETRY_SLEEP_S = 2.0
_THROTTLE_S = 1.0


def load_bps_key() -> str:
    """Read IMDR_BPS_API_KEY from env, falling back to .env file."""
    key = os.environ.get("IMDR_BPS_API_KEY")
    if key:
        return key
    env_path = _REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("IMDR_BPS_API_KEY="):
                v = line.split("=", 1)[1].strip()
                if v:
                    return v
    raise RuntimeError("IMDR_BPS_API_KEY not set in env or .env")


def make_session() -> requests.Session:
    """Return a requests.Session with the key cached and a polite UA."""
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 IMDR-bps"
    s.headers["X-IMDR-BPS-Key"] = load_bps_key()
    return s


def _mask(params: dict) -> dict:
    return {k: ("***" if k == "key" else v) for k, v in params.items()}


def _get(session: requests.Session, url: str, params: dict, timeout: int) -> Any:
    last_err: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            time.sleep(_THROTTLE_S)
            resp = session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
            if isinstance(payload, dict) and payload.get("status") == "Error":
                raise RuntimeError(
                    f"BPS API error on {url} (params={_mask(params)}): "
                    f"{payload.get('message') or payload.get('data') or payload!r}"
                )
            return payload
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as e:
            last_err = e
            if attempt == _RETRIES:
                break
            time.sleep(_RETRY_SLEEP_S * attempt)
    raise RuntimeError(
        f"BPS connection failed after {_RETRIES} attempts for {url} "
        f"(params={_mask(params)}): {last_err}"
    )


def bps_domain(
    session: requests.Session,
    *,
    type: str = "prov",
    prov: str | None = None,
    timeout: int = 30,
) -> Any:
    """GET /v1/api/domain — the master domain catalogue.

    type: 'all' | 'prov' | 'kab' | 'kabbyprov'
    prov: required when type='kabbyprov' (4-digit province domain ID)
    """
    params: dict[str, Any] = {
        "type": type,
        "key": session.headers["X-IMDR-BPS-Key"],
    }
    if prov is not None:
        params["prov"] = prov
    return _get(session, _BPS_BASE + "domain", params, timeout)


def bps_list(
    session: requests.Session,
    *,
    model: str,
    domain: str = "0000",
    extra: dict[str, Any] | None = None,
    lang: str = "ind",
    page: int | None = None,
    timeout: int = 30,
) -> Any:
    """GET /v1/api/list?model=… — catalogue + data listings.

    For model='data', the response has its own (non-paginated) shape with
    ``datacontent`` plus per-axis catalogues. For everything else, the
    response is the standard paginated ``[meta, rows]`` envelope.
    """
    params: dict[str, Any] = {
        "model": model,
        "domain": domain,
        "lang": lang,
        "key": session.headers["X-IMDR-BPS-Key"],
    }
    if page is not None:
        params["page"] = page
    if extra:
        params.update(extra)
    return _get(session, _BPS_BASE + "list", params, timeout)


def bps_view(
    session: requests.Session,
    *,
    model: str,
    domain: str = "0000",
    id: int | str,
    lang: str = "ind",
    timeout: int = 30,
) -> Any:
    """GET /v1/api/view?model=… — single-resource detail by ID."""
    params: dict[str, Any] = {
        "model": model,
        "domain": domain,
        "id": id,
        "lang": lang,
        "key": session.headers["X-IMDR-BPS-Key"],
    }
    return _get(session, _BPS_BASE + "view", params, timeout)


def iter_list_pages(
    session: requests.Session,
    *,
    model: str,
    domain: str = "0000",
    extra: dict[str, Any] | None = None,
    lang: str = "ind",
    timeout: int = 30,
) -> Iterator[dict]:
    """Iterate all rows of a paginated list endpoint.

    Walks page=1..pages and yields each row dict. For ``model=data`` the
    response is non-paginated — use bps_list() directly.
    """
    page = 1
    while True:
        payload = bps_list(
            session, model=model, domain=domain,
            extra=extra, lang=lang, page=page, timeout=timeout,
        )
        envelope = payload.get("data")
        if not isinstance(envelope, list) or len(envelope) < 2:
            return
        meta, rows = envelope[0], envelope[1]
        if not isinstance(rows, list):
            return
        for row in rows:
            yield row
        if not isinstance(meta, dict):
            return
        total_pages = meta.get("pages") or 1
        if page >= total_pages:
            return
        page += 1


def all_th_ids(session: requests.Session, var_id: int) -> list[int]:
    """Return all th_ids available for a variable, sorted ascending.

    Raises RuntimeError if the period catalogue is empty.
    """
    rows = list(iter_list_pages(
        session, model="th", domain="0000",
        extra={"var": str(var_id)}, lang="ind",
    ))
    if not rows:
        raise RuntimeError(f"BPS var={var_id} has no period catalogue (th)")
    return sorted(int(r["th_id"]) for r in rows)


_DATA_TH_MAX_PER_REQUEST = 3  # Live-API limit (undocumented but enforced).


_MONTH_BY_INDONESIAN_LABEL = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
}


def turtahun_to_period(turtahun_id: int, label: str = "") -> tuple[int, str] | None:
    """Map a BPS turtahun_id (+ optional label) to (period_start_month, frequency).

    Returns (month_int, freq) where freq is 'MONTHLY' | 'QUARTERLY' |
    'SEMIANNUAL' | 'ANNUAL'. Returns None to signal "skip" for annual
    rollups embedded in higher-cadence variables (e.g. turtahun_id 13
    'Tahunan' inside a monthly var, or 35 inside a quarterly var).

    For Sakernas (id 188-193) the label is required to map to Feb (2)
    or Aug (8); falls back to Feb if label is empty.
    """
    if 1 <= turtahun_id <= 12:
        return (turtahun_id, "MONTHLY")
    if 31 <= turtahun_id <= 34:
        return ((turtahun_id - 31) * 3 + 1, "QUARTERLY")
    if 321 <= turtahun_id <= 324:
        # Post-2024 base-revision alternate quarterly IDs (Export/Import Price
        # Index 2023=100 — vars 2487-2492).
        return ((turtahun_id - 321) * 3 + 1, "QUARTERLY")
    if turtahun_id == 0:
        return (1, "ANNUAL")
    # Sakernas semi-annual uses scattered IDs — discriminate by label.
    cleaned = label.strip().lower()
    if cleaned in {"februari", "agustus"}:
        return (_MONTH_BY_INDONESIAN_LABEL[cleaned], "SEMIANNUAL")
    if 188 <= turtahun_id <= 193:
        return (_MONTH_BY_INDONESIAN_LABEL.get(cleaned, 2), "SEMIANNUAL")
    return None  # 13, 35, or anything unknown → skip


def bps_fetch_data_chunked(
    session: requests.Session,
    *,
    var: int | str,
    th_ids: list[int],
    domain: str = "0000",
    turvar: int | str | None = None,
    vervar: int | str | None = None,
    turth: int | str | None = None,
    lang: str = "ind",
    timeout: int = 60,
) -> list[dict]:
    """Fetch a multi-year ``model=data`` cut by chunking the ``th`` axis.

    The live API enforces a 3-year cap on ``th``; requests spanning more
    return an error. This helper splits into chunks of ≤3, runs
    ``parse_datacontent`` per response, and concatenates rows.
    """
    if not th_ids:
        return []
    sorted_ids = sorted(set(int(i) for i in th_ids))
    all_rows: list[dict] = []
    for i in range(0, len(sorted_ids), _DATA_TH_MAX_PER_REQUEST):
        chunk = sorted_ids[i:i + _DATA_TH_MAX_PER_REQUEST]
        if len(chunk) == 1:
            th_param = str(chunk[0])
        elif len(chunk) == max(chunk) - min(chunk) + 1:
            th_param = f"{chunk[0]}:{chunk[-1]}"
        else:
            th_param = ";".join(str(c) for c in chunk)
        extra: dict[str, Any] = {"var": str(var), "th": th_param}
        if turvar is not None:
            extra["turvar"] = str(turvar)
        if vervar is not None:
            extra["vervar"] = str(vervar)
        if turth is not None:
            extra["turth"] = str(turth)
        payload = bps_list(session, model="data", domain=domain,
                           extra=extra, lang=lang, timeout=timeout)
        all_rows.extend(parse_datacontent(payload))
    return all_rows


def parse_datacontent(payload: dict) -> list[dict]:
    """Parse a `model=data` response into long-format rows.

    The `datacontent` dict keys are a string concatenation of five IDs:
        {vervar}{var}{turvar}{tahun}{turtahun}

    Component widths are variable (no zero-padding) so a naive split is
    ambiguous. The strategy: enumerate the cartesian product of the five
    axis catalogues to build a reverse map ``concat_str → tuple``. Even
    a deep cut (514 regencies × 13 months × 5 years × …) is only ~35k
    tuples; worst-case memory is a few MB.

    Raises RuntimeError if any composite key fails to map.
    """
    datacontent = payload.get("datacontent") or {}
    if not datacontent:
        return []

    def _catalog(key: str) -> dict[int, str]:
        rows = payload.get(key) or []
        out: dict[int, str] = {}
        for r in rows:
            v = r.get("val")
            if v is None:
                continue
            try:
                vid = int(v)
            except (TypeError, ValueError):
                continue
            out[vid] = r.get("label") or ""
        return out

    vervar = _catalog("vervar")
    var = _catalog("var")
    turvar = _catalog("turvar")
    tahun = _catalog("tahun")
    turtahun = _catalog("turtahun")
    if not (vervar and var and tahun):
        raise RuntimeError(
            f"BPS payload missing axis catalogues: "
            f"vervar={len(vervar)} var={len(var)} tahun={len(tahun)}"
        )
    if not turvar:
        turvar = {0: ""}
    if not turtahun:
        turtahun = {0: ""}

    rev: dict[str, tuple[int, int, int, int, int]] = {}
    for vv_id in vervar:
        s_vv = str(vv_id)
        for v_id in var:
            s_v = s_vv + str(v_id)
            for tv_id in turvar:
                s_tv = s_v + str(tv_id)
                for t_id in tahun:
                    s_t = s_tv + str(t_id)
                    for tt_id in turtahun:
                        rev[s_t + str(tt_id)] = (vv_id, v_id, tv_id, t_id, tt_id)

    var_meta = (payload.get("var") or [{}])[0]
    unit = var_meta.get("unit") or ""
    rows: list[dict] = []
    missing: list[str] = []
    for key, value in datacontent.items():
        ids = rev.get(key)
        if ids is None:
            missing.append(key)
            continue
        vv_id, v_id, tv_id, t_id, tt_id = ids
        rows.append({
            "vervar_id": vv_id,
            "vervar_label": vervar[vv_id],
            "var_id": v_id,
            "var_label": var[v_id],
            "turvar_id": tv_id,
            "turvar_label": turvar[tv_id],
            "tahun_id": t_id,
            "tahun_label": tahun[t_id],
            "turtahun_id": tt_id,
            "turtahun_label": turtahun[tt_id],
            "unit": unit,
            "value": value,
        })
    if missing:
        raise RuntimeError(
            f"BPS datacontent has {len(missing)} keys that do not map to any "
            f"(vervar, var, turvar, tahun, turtahun) tuple. First 5: {missing[:5]}"
        )
    return rows
