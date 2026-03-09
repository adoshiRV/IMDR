from __future__ import annotations

from unittest.mock import MagicMock, patch

from imdr.config.settings import Settings
from imdr.connectors.mssql import MSSQLConnector


class TestMSSQLConnector:
    @patch("imdr.connectors.mssql.create_engine")
    def test_engine_created_with_url(self, mock_create_engine: MagicMock) -> None:
        settings = Settings(mssql_host="testhost", mssql_database="testdb")
        MSSQLConnector(settings)
        mock_create_engine.assert_called_once()
        call_args = mock_create_engine.call_args
        assert "testhost" in call_args.args[0]
        assert "testdb" in call_args.args[0]

    @patch("imdr.connectors.mssql.create_engine")
    def test_session_commits_on_success(self, mock_create_engine: MagicMock) -> None:
        settings = Settings(mssql_host="testhost", mssql_database="testdb")
        connector = MSSQLConnector(settings)
        mock_session = MagicMock()
        connector._session_factory = MagicMock(return_value=mock_session)

        with connector.session():
            pass

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("imdr.connectors.mssql.create_engine")
    def test_session_rolls_back_on_error(self, mock_create_engine: MagicMock) -> None:
        settings = Settings(mssql_host="testhost", mssql_database="testdb")
        connector = MSSQLConnector(settings)
        mock_session = MagicMock()
        connector._session_factory = MagicMock(return_value=mock_session)

        try:
            with connector.session():
                raise ValueError("test error")
        except ValueError:
            pass

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    @patch("imdr.connectors.mssql.create_engine")
    def test_dispose(self, mock_create_engine: MagicMock) -> None:
        settings = Settings(mssql_host="testhost", mssql_database="testdb")
        connector = MSSQLConnector(settings)
        connector.dispose()
        mock_create_engine.return_value.dispose.assert_called_once()
