"""Connector surface for IMDR.

Only `MSSQLConnector` is re-exported here — it is the one piece of plumbing
every pipeline needs and the canonical place to acquire a SQLAlchemy session.
The vendor-specific clients (`citi_velocity`, `bulk`, `reader`, etc.) stay
accessible via their full submodule paths so call sites and `grep` results
remain explicit about which connector is in use.
"""
from imdr.connectors.mssql import MSSQLConnector

__all__ = ["MSSQLConnector"]
