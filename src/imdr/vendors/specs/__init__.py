"""Vendor-feed specs.

Each module in this package defines one or more ``VendorFeed``s and
registers them via ``register_feed()`` at import time.  The parent
``imdr.vendors`` package imports every module here so the registry
populates on ``import imdr.vendors`` without extra wiring.

To add a new feed:
  1. Create ``imdr/vendors/specs/{vendor}_{feed}.py``
  2. Build the spec + pipeline_builder + formatter + ``VendorFeed``
  3. Call ``register_feed(...)`` at module scope
  4. Import it from this package's ``__init__`` (pattern below)
"""
from __future__ import annotations

# Importing a module here runs its top-level ``register_feed(...)`` call.
from imdr.vendors.specs import barclays_skew  # noqa: F401
