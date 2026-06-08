"""Production research-portal namespace.

The crawler/ingest code still lives at ``playground/research/`` while
each vendor is being productionalised. The first piece promoted here is
:mod:`imdr.research.auth` — a single authenticating module that owns
every vendor's Playwright ``BrowserContext`` acquisition, verifies
session liveness, and snapshots state for portability.
"""
