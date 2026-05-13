from __future__ import annotations

from datetime import datetime, timezone
import time

from core_10x.traitable import Traitable, T, RT, RC
from core_10x.trait_filter import BETWEEN, LT, LE, GT, GE, f


#class Event(Traitable, custom_collection = True, keep_history = False):
class Event(Traitable, keep_history = False):
    s_base_perf: int = None
    s_base_wall: int = 0
    #at: int = RT(T.ID_LIKE)

    at_dt: datetime     = T(1)
    at_ns: int          = T(1)

    # def at_get(self) -> int:
    #     ns = time.perf_counter_ns()
    #     if self.s_base_perf is None:
    #         self.s_base_wall = time.time_ns()
    #         self.s_base_perf = ns
    #     return ns

    # def at_dt_get(self) -> datetime:
    #     ...

    @classmethod
    def between(cls, start: datetime, end: datetime, including_start = True, including_end = True, _coll_name: str = None):
        if start is None:
            assert end is not None, 'Either start or end must be provided'
            op = LE(end) if including_end else LT(end)
        elif end is None:
            op = GE(start) if including_start else GT(start)
        else:
            op = BETWEEN(start, end, bounds = (including_start, including_end))

        return cls.load_many(query = f(at = op), _coll_name = _coll_name)

    @classmethod
    def penultimate(cls, when: datetime, _coll_name: str = None) -> Event:
        res = cls.load_many(query = f(at = LT(when)), _coll_name = _coll_name, _at_most = 1)    #-- TODO: assumption - sorted by 'at'
        return res[0] if res else None