"""BofA-specific PDF fetcher.

Most BofA PDFs come back as a direct ``application/pdf`` body via a
single GET on ``research1.ml.com/C?q=<token>&e=<urlenc-email>&h=<hash>``
— the auth is self-contained in the HMAC ``h=`` parameter, no session
cookies required. Verified across multiple recent reports.

Older reports (publication date > ~6 months back) instead show an
**ASP.NET "Expired" interstitial** — a tiny ~2KB HTML page titled
"Research Content" warning the report may be stale, with a form::

    <form method="post" action="./?q=<token>&e=...&h=..." id="GetDoc">
      <input type="hidden" name="__VIEWSTATE" value="..." />
      <input type="hidden" name="__VIEWSTATEGENERATOR" value="..." />
      <input type="hidden" name="__EVENTVALIDATION" value="..." />
      <input type="submit" name="Proceed" value="Proceed" />
    </form>

The user must click "Proceed" to acknowledge the report may be stale.

**Why we don't POST the form via the request client:** the Proceed
acknowledgement is bound to the live POST→meta-refresh→redirect
*navigation*, not to a reusable cookie. Replaying it with
``ctx.request.post`` lands back on the interstitial, and the resulting
``/C/?q=...`` URL still returns the interstitial on a bare GET. Only a
real browser navigation gets through — and then Chrome renders the PDF
*inline*, which Playwright's ``response.body()`` can't read (it returns
the PDF-viewer shell, not the bytes).

So for the expired case we: (1) set ``always_open_pdf_externally`` in
the profile so Chrome downloads PDFs instead of rendering them, then
(2) ``page.goto`` the interstitial, click ``#Proceed`` and capture the
resulting download. Verified end-to-end on report 12905458 (59-page,
2.05 MB PDF recovered).

Some forwarded / foreign-recipient ``rsch.baml.com/r?q=...&e=<recipient>``
links redirect to an **HTML viewer page** (Liferay DXP, title like
"BofA - India Watch" / "Report - Liferay DXP") rather than returning
a PDF directly. For this case:

- The viewer HTML contains a re-minted ``research1.ml.com/C?q=...`` URL
  bound to *our* authenticated entitlement (ignoring the original
  recipient address). We extract and fetch that URL first.
- If the re-minted URL is absent or returns something other than a PDF,
  we fall back to clicking the PDF button (``a[title="PDF"]``) in the
  rendered page and capturing the resulting download.

Verified end-to-end on doc 12985511 (7-page, 1.27 MB PDF recovered).

Used by ``ingest_today.py``'s BofA branch (signature matches
``fetch.py.fetch_pdf`` so it can drop in as a per-vendor fetcher).
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

_PDF_MAGIC = b"%PDF-"
_FETCH_TIMEOUT_MS = 120_000
_DOWNLOAD_TIMEOUT_MS = 60_000

_PROCEED_SELECTOR = "#Proceed"

# Ordered list of selectors tried when clicking the PDF download button
# inside the viewer page. The first match wins.
_PDF_BUTTON_SELECTORS = [
    'a[title="PDF"]',
    'a[title*="PDF" i]',
    'a[aria-label*="PDF" i]',
    '[onclick*="pdf" i]',
]

# Matches the re-minted research1.ml.com/C? URL (with &amp; or &).
# The URL appears inside HTML attribute values, so & is HTML-encoded.
_REMINTED_URL_RE = re.compile(
    r"https://research1\.ml\.com/C/?(?:&amp;|\?)q=[^'\"&\s]+"
    r"(?:(?:&amp;|&)[^'\"&\s]+)*"
)


class FetchError(Exception):
    pass


def _extract_reminted_pdf_url(html: str) -> str | None:
    """Return the first re-minted ``research1.ml.com/C?...`` URL found in
    *html*, with ``&amp;`` decoded to ``&``, or ``None`` if absent.

    BofA's viewer page renders the authenticated PDF URL inside an HTML
    attribute (e.g. ``onclick="...loadAndPrintPdf('https://research1.ml.com/
    C?q=...&amp;e=adoshi%40rvcapital.com&amp;h=...',...)"``). The URL is
    bound to the *current* session's entitlement, not the original forwarded
    recipient.
    """
    m = _REMINTED_URL_RE.search(html)
    if m is None:
        return None
    return m.group(0).replace("&amp;", "&")


def _looks_like_viewer(body: bytes, url: str) -> bool:
    """Return True when *body* looks like the BofA HTML report viewer page.

    Conservative: only triggers when the response is HTML (not a PDF or
    the known ASP.NET expired interstitial) AND carries viewer-specific
    markers. This avoids mis-routing unexpected responses.
    """
    if body.startswith(_PDF_MAGIC):
        return False
    if _looks_like_expired_interstitial(body):
        return False
    # Must be an HTML-like response of meaningful size.
    if len(body) < 10_000:
        return False
    sample = body[:8000]
    if b"research1.ml.com" in sample:
        return True
    if b"Liferay" in sample:
        return True
    # The /r? forwarding host redirects into the viewer.
    from urllib.parse import urlparse  # noqa: PLC0415
    host = urlparse(url).netloc
    if host == "rsch.baml.com":
        return True
    return False


def _looks_like_expired_interstitial(body: bytes) -> bool:
    """The interstitial is ~2KB, mentions 'Expired', and has a
    ``name="Proceed"`` submit input."""
    if len(body) > 20_000:
        return False
    txt = body[:5000].decode("utf-8", errors="ignore")
    return "Expired" in txt and 'name="Proceed"' in txt


def _ensure_pdf_downloads(profile_dir: Path) -> None:
    """Set ``plugins.always_open_pdf_externally=True`` in the profile's
    Chrome ``Preferences`` so PDFs download instead of rendering inline.

    Idempotent and benign: it only changes how PDF *navigations* behave;
    the direct ``ctx.request.get`` fast path is unaffected. Must run
    before the context is launched (Chrome reads Preferences at startup).
    """
    prefs_path = profile_dir / "Default" / "Preferences"
    try:
        prefs = (
            json.loads(prefs_path.read_text(encoding="utf-8"))
            if prefs_path.exists() else {}
        )
    except (OSError, ValueError):
        prefs = {}
    plugins = prefs.setdefault("plugins", {})
    if plugins.get("always_open_pdf_externally") is True:
        return
    plugins["always_open_pdf_externally"] = True
    prefs_path.parent.mkdir(parents=True, exist_ok=True)
    prefs_path.write_text(json.dumps(prefs), encoding="utf-8")


async def _fetch_via_proceed_page(ctx, url: str) -> bytes:
    """Recover an expired-interstitial report by clicking Proceed in a
    real page and capturing the resulting download.

    Relies on ``always_open_pdf_externally`` having been set on the
    profile (see :func:`_ensure_pdf_downloads`) so the post-Proceed PDF
    triggers a download event rather than rendering inline.
    """
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded",
                        timeout=_FETCH_TIMEOUT_MS)
        await page.wait_for_timeout(800)
        try:
            async with page.expect_download(
                timeout=_DOWNLOAD_TIMEOUT_MS,
            ) as dl_info:
                await page.click(_PROCEED_SELECTOR,
                                 timeout=_DOWNLOAD_TIMEOUT_MS)
            download = await dl_info.value
        except Exception as exc:  # noqa: BLE001
            raise FetchError(
                f"BofA: expired-interstitial Proceed click did not "
                f"produce a download (url={url[:120]}, page={page.url}, "
                f"err={exc!s:.120})"
            ) from exc

        # Stream the download to a temp file, then read it back.
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "bofa.pdf"
            await download.save_as(str(dest))
            body = dest.read_bytes()
        if body.startswith(_PDF_MAGIC):
            return body
        raise FetchError(
            f"BofA: expired-interstitial download was not a PDF "
            f"(url={url[:120]}, first16={body[:16]!r})"
        )
    finally:
        try:
            await page.close()
        except Exception:  # noqa: BLE001
            pass


async def _fetch_via_viewer(ctx, url: str) -> bytes:
    """Fetch a PDF from a BofA HTML viewer page (Liferay DXP).

    Strategy:
    1. Navigate to *url* (typically ``rsch.baml.com/r?...``), wait for the
       viewer to fully render.
    2. PRIMARY — extract the re-minted ``research1.ml.com/C?...`` URL from
       the rendered HTML via :func:`_extract_reminted_pdf_url`. If found,
       fetch it with ``ctx.request.get``. If the response is a PDF, return
       it; if it's the expired interstitial, route through
       :func:`_fetch_via_proceed_page`.
    3. FALLBACK — if the re-minted URL is absent or does not yield a PDF,
       click the PDF button (``a[title="PDF"]``) via ``expect_download`` and
       read the resulting file.

    Requires ``always_open_pdf_externally`` to have been set on the profile
    (see :func:`_ensure_pdf_downloads`) so PDF navigations download rather
    than rendering inline.
    """
    page = await ctx.new_page()
    reminted: str | None = None
    try:
        await page.goto(url, wait_until="domcontentloaded",
                        timeout=_FETCH_TIMEOUT_MS)
        # Give the Liferay SPA a moment to finish hydrating so the PDF URL
        # is injected into the DOM before we read page content.
        await page.wait_for_load_state("networkidle", timeout=30_000)
        await page.wait_for_timeout(2_000)

        html = await page.content()
        reminted = _extract_reminted_pdf_url(html)

        if reminted:
            resp = await ctx.request.get(reminted, timeout=_FETCH_TIMEOUT_MS)
            if resp.status == 200:
                body = await resp.body()
                if body.startswith(_PDF_MAGIC):
                    return body
                if _looks_like_expired_interstitial(body):
                    # Re-minted URL is stale — click through the interstitial.
                    return await _fetch_via_proceed_page(ctx, reminted)

        # Fallback: click the PDF button and capture the download.
        for selector in _PDF_BUTTON_SELECTORS:
            try:
                async with page.expect_download(
                    timeout=_DOWNLOAD_TIMEOUT_MS,
                ) as dl_info:
                    await page.click(selector, timeout=10_000)
                download = await dl_info.value
                with tempfile.TemporaryDirectory() as tmp:
                    dest = Path(tmp) / "bofa.pdf"
                    await download.save_as(str(dest))
                    body = dest.read_bytes()
                if body.startswith(_PDF_MAGIC):
                    return body
                raise FetchError(
                    f"BofA viewer: PDF button download was not a PDF "
                    f"(selector={selector!r}, first16={body[:16]!r})"
                )
            except FetchError:
                raise
            except Exception:  # noqa: BLE001
                continue

        raise FetchError(
            f"BofA viewer: neither re-minted URL nor PDF button yielded a PDF "
            f"(url={url[:120]}, reminted={reminted and reminted[:120]!r})"
        )
    finally:
        try:
            await page.close()
        except Exception:  # noqa: BLE001
            pass


async def fetch_pdf(url: str, profile_dir: Path) -> bytes:
    """Drop-in replacement for :func:`fetch.fetch_pdf` for BofA URLs.

    1. Direct GET — most recent reports return PDF bytes immediately via
       ``research1.ml.com/C?q=...`` (HMAC self-auth, no session required).
    2. Expired interstitial — ASP.NET "Research Content" page; navigate in
       a real page, click ``Proceed``, capture the download.
    3. HTML viewer — Liferay DXP viewer page (``rsch.baml.com/r?...``
       forwarded links); extract the re-minted ``research1.ml.com/C?...``
       URL and fetch it, or fall back to clicking the PDF button.
    """
    from playwright.async_api import async_playwright  # noqa: PLC0415

    # Must run before launch so Chrome downloads (not renders) PDFs,
    # which the expired-interstitial and viewer-fallback paths depend on.
    _ensure_pdf_downloads(profile_dir)

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=False,
            accept_downloads=True,
        )
        try:
            # Fast path — most recent reports return PDF directly.
            resp = await ctx.request.get(url, timeout=_FETCH_TIMEOUT_MS)
            if resp.status != 200:
                raise FetchError(
                    f"BofA: GET {url[:120]} returned HTTP {resp.status}"
                )
            body = await resp.body()
            if body.startswith(_PDF_MAGIC):
                return body
            if _looks_like_expired_interstitial(body):
                return await _fetch_via_proceed_page(ctx, url)
            if _looks_like_viewer(body, url):
                return await _fetch_via_viewer(ctx, url)
            head = body[:120].decode("utf-8", errors="replace")
            ct = resp.headers.get("content-type", "")
            raise FetchError(
                f"BofA: GET {url[:120]} did not return PDF "
                f"(ct={ct}, first 120 bytes={head!r})"
            )
        finally:
            await ctx.close()
