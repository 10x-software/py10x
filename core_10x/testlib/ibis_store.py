from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core_10x.trait import Trait


class IbisStore:
    """Mixin for ibis-backed stores — provides dtype mapping and who/when helpers."""

    _TRAIT_DTYPE_MAP: dict = {}  # populated after concrete_traits are importable

    @classmethod
    def _build_dtype_map(cls) -> dict:
        from core_10x.concrete_traits import (
            bool_trait,
            date_trait,
            datetime_trait,
            float_trait,
            int_trait,
            named_constant_trait,
            str_trait,
        )
        return {
            bool_trait:           'bool',
            int_trait:            'int64',
            float_trait:          'float64',
            str_trait:            'str',
            datetime_trait:       'timestamp',
            date_trait:           'date',
            named_constant_trait: 'str',
        }

    @classmethod
    def ibis_dtype(cls, trait: Trait) -> str:
        if not cls._TRAIT_DTYPE_MAP:
            cls._TRAIT_DTYPE_MAP = cls._build_dtype_map()
        return cls._TRAIT_DTYPE_MAP.get(type(trait), 'json')

    @classmethod
    def ibis_column(cls, table, trait_name: str, trait: Trait):
        """Return an ibis column expression for the given trait."""
        dtype = cls.ibis_dtype(trait)
        col = table._data.json_extract_string(f'$.{trait_name}')
        if dtype == 'json':
            return col
        if dtype == 'bool':
            return col.cast('boolean')
        return col.cast(dtype)

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
