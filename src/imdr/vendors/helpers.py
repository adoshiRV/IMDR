"""Small helpers shared by pipeline builders across vendor feeds."""
from __future__ import annotations

from sqlalchemy import text

from imdr.connectors.mssql import MSSQLConnector


def resolve_vendor_id(connector: MSSQLConnector, vendor_code: str) -> int:
    """Look up ``dbo.dim_vendor.id`` for a given vendor_code.

    Every vendor feed needs this to populate ``vendor_id`` on fact
    rows.  Fail loudly if the code isn't seeded — that's a migration
    gap, not a runtime condition.
    """
    with connector.session() as session:
        result = session.execute(
            text("SELECT id FROM [dbo].[dim_vendor] WHERE vendor_code = :code"),
            {"code": vendor_code},
        ).scalar_one_or_none()

    if result is None:
        raise RuntimeError(
            f"Vendor code {vendor_code!r} not found in dbo.dim_vendor — "
            f"check migration 018 and subsequent seeds."
        )
    return int(result)
