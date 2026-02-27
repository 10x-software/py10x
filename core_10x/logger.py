import os
from datetime import datetime
import psutil
from typing import Any

from core_10x.traitable import Traitable, T, RT
from core_10x.global_cache import cache


@cache
def process() -> psutil.Process:
    return psutil.Process(os.getpid())

class LogMessage(Traitable):
    at: datetime        = T(T.ID)
    mem_pc: float       = T()
    num_threads: int    = T()
    payload: Any        = T()

    def at_get(self):
        return datetime.utcnow()

    def mem_pc_get(self):
        return process().memory_percent()

    def num_threads_get(self):
        return process().num_threads()

class Logger(Traitable):
    ...
