"""Shared vintage (revision) predicate for IMDR's append-only fact tables.

Several fact tables capture data revisions as new vintages rather than
overwriting in place (econ.fact_indicator, fx.fact_index_value, ...). The rule
for a re-loaded observation, given the current latest-vintage value, is
identical across them; this is the single canonical statement of it. The
set-based T-SQL in each loader is the runtime source of truth; this pure
function is the testable contract that mirrors it.
"""

from __future__ import annotations


def classify_fact_action(exists: bool, incoming_value, current_value) -> str:
    """Classify a re-loaded observation against the current latest vintage.

    - ``exists=False``                          -> ``"new"``      (insert at vintage 0)
    - existing, ``incoming_value is None``       -> ``"skip"``     (never clobber with NULL)
    - existing, current NULL or value changed    -> ``"revision"`` (insert at cur_vintage+1)
    - existing, value unchanged                  -> ``"skip"``
    """
    if not exists:
        return "new"
    if incoming_value is None:
        return "skip"
    if current_value is None or incoming_value != current_value:
        return "revision"
    return "skip"
