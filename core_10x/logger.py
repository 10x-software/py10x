import os
import time
from datetime import datetime
import psutil
from typing import Any
import multiprocessing as mp
import socket

from py10x_kernel import OsUser
from core_10x.traitable import Traitable, T, RT
from core_10x.xdate_time import XDateTime


def LOG(payload: Any):
    if payload is not None:
        data = dict(
            ns          = time.perf_counter_ns(),
            mem_pc      = LOGGER.ps.memory_percent(),
            num_threads = LOGGER.ps.num_threads(),
            payload     = payload
        )
    else:
        data = None

    LOGGER.log(data)

class LogMessage(Traitable, custom_collection = True, keep_history = False):
    ns: int             = T(T.ID)
    mem_pc: float       = T()
    num_threads: int    = T()
    payload: Any        = T()

def logger_process(
        queue: mp.Queue,
        coll_name: str,
        do_print: bool
):
    data = queue.get()
    if data is None:
        return

    first_msg = LogMessage(_replace = True, _collection_name = coll_name, **data)
    #start: datetime = first_msg.payload
    t1 = first_msg.ns
    first_msg.save()

    while True:
        data = queue.get()
        if data is None:
            break

        msg = LogMessage(_replace = True, _collection_name = coll_name, **data)
        msg.save()
        if do_print:
            t2 = msg.ns
            dt = t2 - t1
            t1 = t2
            print(f'{(dt) / 1.e9}: {msg.payload}')

class Logger:
    def __init__(
        self,
        app_name: str,
        started_at: datetime = None,
        do_print = True
    ):
        self.app_name = app_name
        if started_at is None:
            started_at = datetime.utcnow()
        self.started_at = started_at
        pid = os.getpid()
        full_name = f'{app_name}/{OsUser.me.name()}/{socket.gethostname()}/{XDateTime.datetime_to_str(started_at, False)}/{pid}'
        self.ps = psutil.Process(pid)

        self.queue = mp.Queue()
        self.proc = mp.Process(target = logger_process, args = (self.queue, full_name, do_print))
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
            LOG(datetime.utcnow())

class LogReader:
    ...

LOGGER: Logger = None
