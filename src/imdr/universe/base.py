"""Base universe ABC for all asset classes."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseUniverse(ABC):
    """Base class for domain-specific instrument universes."""

    @abstractmethod
    def instruments(self) -> list[str]:
        """Return all instruments in dotted notation (e.g. 'EUR.USD')."""
        ...

    @abstractmethod
    def api_symbols(self) -> list[str]:
        """Return all instruments in compact API format (e.g. 'EURUSD')."""
        ...
