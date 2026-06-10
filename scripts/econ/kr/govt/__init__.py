"""Korea government policy filings — daily ingest package.

Per-agency fetchers + resolvers + TLS-1.2 patient HTTP session,
sequenced by ``ingest_filings.py``. Each new filing flows through
``imdr.research.filings.ingest_filing`` to land in
``research.dim_report`` + Qdrant + SharePoint
(``{YYYY}/{MM}/{DD}/econ/kr/{vendor}/...``).

Wired into ``scripts/econ/kr/kr_daily.py`` → ``scripts/imdr_daily.py``.

URL recipes + cadence per agency: ``docs/admin/econ/korea/govt_doc_sources.md``.
"""
