from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Literal

from ibis.common.exceptions import TableNotFound

from core_10x.resource import REL_DB, Resource, ResourceSpec

if TYPE_CHECKING:
    import ibis.expr.types as ir
    import polars as pl


class RelDb(Resource, resource_type=REL_DB):

    def __init__(self, uri: str):
        self._uri = uri
        self._connection = None

    @classmethod
    def instance(cls, *args, **kwargs) -> RelDb:
        if args:
            raise ValueError('RelDb.instance accepts keyword arguments only.')
        return cls(ResourceSpec(cls, kwargs).uri())

    def __enter__(self):
        self.begin_using()
        return self

    def on_enter(self):
        try:
            ibis = importlib.import_module('ibis')
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError('ibis is required for RelDb connections.') from e
        self._connection = ibis.connect(self._uri)

    def on_exit(self):
        if self._connection is not None:
            self._connection.disconnect()
            self._connection = None

    def query(self, table_name: str) -> ir.Table|None:
        """Return an ibis Table for the given table, for further ibis manipulation."""
        assert self._connection is not None, 'RelDb must be used as a context manager.'
        try:
            return self._connection.table(table_name)
        except TableNotFound:
            return None

    def insert(self, table_name: str, df: pl.DataFrame, if_exists: Literal['replace', 'append', 'fail'] = 'fail') -> None:
        """Insert a polars DataFrame into a table via Polars ADBC.

        if_exists: 'fail' (default) raises if the table exists;
                   'replace' drops and recreates; 'append' adds rows.
        """
        assert self._connection is not None, 'RelDb must be used as a context manager.'
        df.write_database(table_name, self._uri, engine='adbc', if_table_exists=if_exists)

    def drop_table(self, table_name: str) -> None:
        assert self._connection is not None, 'RelDb must be used as a context manager.'
        self._connection.drop_table(table_name)
