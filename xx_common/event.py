from __future__ import annotations

from datetime import datetime
import uuid6

from core_10x.traitable import EventBase, T, RT, RC
from core_10x.trait_filter import BETWEEN, LT, LE, GT, GE, f
from core_10x.global_cache import cache


class Event(EventBase):
    @classmethod
    def uuid7_from_dt(dt: datetime) -> str:
        """
        Construct the lowest possible UUID v7 for a given datetime (random bits zeroed)
        """
        ms = int(dt.timestamp() * 1000)
        hi = (ms & 0xFFFFFFFFFFFF) << 16 | 0x7000
        lo = 0x8000000000000000
        return str(uuid6.UUID(int = (hi << 64) | lo))

    @classmethod
    @cache
    def _ensure_at_index(cls):
        coll = cls.collection()
        return coll.create_index('_at_idx', '_at')

    def save(self, save_references = False) -> RC:
        cls = self.__class__
        cls._ensure_at_index()
        return super().save(save_references = False)    #-- must not have references to other objects

    @classmethod
    def between(cls, start: datetime, end: datetime, including_start = True, including_end = True, _coll_name: str = None):
        if start is None:
            assert end is not None, 'Either start or end must be provided'
            op = LE(end) if including_end else LT(end)
        elif end is None:
            op = GE(start) if including_start else GT(start)
        else:
            op = BETWEEN(start, end, bounds = (including_start, including_end))

        return cls.load_many(query = f(_at = op), _coll_name = _coll_name)

    @classmethod
    def penultimate(cls, when: datetime, _coll_name: str = None) -> Event:
        res = cls.load_many(query = f(_at = LT(when)), _coll_name = _coll_name, _at_most = 1)
        return res[0] if res else None