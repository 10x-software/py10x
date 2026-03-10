import os
from datetime import datetime
import psutil
from typing import Any
import multiprocessing as mp

from py10x_kernel import OsUser
from core_10x.traitable import Traitable, T, RT


def LOG(payload: Any):
    if payload is not None:
        data = dict(
            at          = datetime.utcnow(),
            mem_pc      = LOGGER.ps.memory_percent(),
            num_threads = LOGGER.ps.num_threads(),
            payload     = payload
        )
    else:
        data = None

    LOGGER.log(data)

class LogMessage(Traitable, custom_collection = True, keep_history = False):
    at: datetime        = T(T.ID)
    mem_pc: float       = T()
    num_threads: int    = T()
    payload: Any        = T()

def logger_process(queue: mp.Queue, coll_name: str):
    while True:
        data = queue.get()
        if data is None:
            break

        msg = LogMessage(_replace = True, _collection_name = coll_name, **data)
        msg.save()

class Logger:
    def __init__(
        self,
        app_name: str,
        started_at: datetime = None
    ):
        self.app_name = app_name
        if started_at is None:
            started_at = datetime.utcnow()
        self.started_at = started_at
        pid = os.getpid()
        full_name = f'{app_name}/{OsUser.me.name()}/{started_at}/{pid}'
        self.ps = psutil.Process(pid)

        self.queue = mp.Queue()
        self.proc = mp.Process(target = logger_process, args = (self.queue, full_name))
        self.proc.daemon = True
        self.proc.start()

    def log(self, data: dict):
        self.queue.put(data)

    def shutdown(self):
        self.queue.put(None)
        self.proc.join()

    @classmethod
    def init(cls, app_name: str):
        global LOGGER
        if LOGGER is None:
            LOGGER = cls(app_name)

LOGGER: Logger = None
