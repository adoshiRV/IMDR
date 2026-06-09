"""Shared building blocks for BBG-sourced extractors (FX + rates).

The BBG R pipeline writes one 3-row-header CSV per pair / curve under
``Z:\\BBG_mirror\\``. FX and rates extractors share the parser core;
domain-specific quirks (FX divisor table, rates folder taxonomy) stay
in their own modules.

* :mod:`imdr.bbg.csv_parser` — 3-header CSV -> long DataFrame.

Lives at the top of the ``imdr`` namespace (peer to ``imdr.domains``
and ``imdr.vendors``) deliberately: importing ``imdr.vendors.<x>``
triggers the vendor-registry side-effect import, which would create a
circular import when a rates pipeline imported via the registry needed
the shared parser.
"""
from __future__ import annotations
