from __future__ import annotations

import pytest

from imdr.config.settings import Settings


class TestSettings:
    def test_defaults(self) -> None:
        s = Settings(mssql_host="localhost", mssql_database="TestDB")
        assert s.mssql_host == "localhost"
        assert s.mssql_port == 1433
        assert s.pool_size == 5

    def test_connection_url_format(self) -> None:
        s = Settings(mssql_host="server01", mssql_database="MarketData")
        url = s.mssql_connection_url
        assert url.startswith("mssql+pyodbc://")
        assert "server01" in url
        assert "MarketData" in url
        assert "Trusted_Connection=yes" in url

    def test_connection_url_contains_driver(self) -> None:
        s = Settings(mssql_host="localhost", mssql_database="IMDR")
        assert "ODBC+Driver+17+for+SQL+Server" in s.mssql_connection_url

    def test_env_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IMDR_MSSQL_HOST", "custom-host")
        monkeypatch.setenv("IMDR_MSSQL_DATABASE", "custom-db")
        s = Settings()
        assert s.mssql_host == "custom-host"
        assert s.mssql_database == "custom-db"
