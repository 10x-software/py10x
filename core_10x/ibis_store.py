from __future__ import annotations

from datetime import datetime, timezone

from core_10x.ts_store import TsStore


class IbisStore(TsStore):
    """Abstract base for ibis-backed stores.

    Provides plain add_who/add_when helpers (no $set/$currentDate wrappers).
    Concrete subclasses must supply resource_name and implement all TsStore abstract methods.
    """

    def add_who(self, field: str, serialized_data: dict) -> dict:
        if field in serialized_data:
            raise RuntimeError(f'Field {field} is already in use.')
        serialized_data['_who'] = self.auth_user()
        return serialized_data

    def add_when(self, field: str, serialized_data: dict) -> dict:
        if field in serialized_data:
            raise RuntimeError(f'Field {field} is already in use.')
        serialized_data[field] = datetime.now(timezone.utc)
        return serialized_data
