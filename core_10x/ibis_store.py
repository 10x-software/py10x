from __future__ import annotations

import abc

from core_10x.ts_store import TsStore


class IbisStore(TsStore):
    """Abstract base for ibis-backed stores.

    Concrete subclasses must supply resource_name and implement all TsStore abstract methods.
    """

    @abc.abstractmethod
    def add_who(self, field: str, serialized_data: dict) -> dict: ...

    @abc.abstractmethod
    def add_when(self, field: str, serialized_data: dict) -> dict: ...
