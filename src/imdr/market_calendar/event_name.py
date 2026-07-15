"""Canonical ``event_name`` normalization shared by the TE and BQL calendar feeds.

``calendar.cb_events`` has a filtered unique index
(``UX_cb_events_vendor_date_country_event``) on
``(vendor_id, event_date, country_id, event_name)`` under an accent- and
case-insensitive collation. Feed-side Python string comparisons are
byte-exact, so two spellings of the same event that differ only by
diacritics or case — e.g. TE's ``data-event`` slug "ecb vujcic speech" vs a
rendered-text fallback "ecb vujčić speech" — were treated as *different* rows
by the upsert's MATCH/ON clause while the DB index treats them as the *same*
row. The MERGE picked the ``NOT MATCHED`` (INSERT) branch and collided with
the existing row (``pyodbc.IntegrityError`` 2601), which aborted the whole
run.

Normalizing to one canonical form before it ever reaches the MERGE — for
both the in-memory dedup key and the value written to the DB — closes the
gap: any accent/case variant of the same event collapses to one byte-
identical string, so there is no representation left for the feed and the
index to disagree over.
"""
from __future__ import annotations

import unicodedata


def normalize_event_name(name: str) -> str:
    """Casefold + strip diacritics, collapsing accent/case variants to one form.

    ``normalize_event_name("ECB Vujčić Speech") == normalize_event_name("ecb vujcic speech")``.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold().strip()
