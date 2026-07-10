import inspect
import time
from datetime import timedelta

from core_10x.py_class import PyClass
from core_10x.trait_filter import f, BETWEEN, LT
from core_10x.traitable import Traitable, T
from xx_common.event import Event

PROCESS_METHOD_SUFFIX = 'process'

class EventProcessor(Traitable):
    last_watermarks: dict = T({})   #-- {event_class_name: watermark_datetime}

    s_input_event_classes   = ()
    s_output_event_classes  = ()
    s_input_switch = {}
    def __init_subclass__(cls, inputs = (), outputs = (), **kwargs):
        if inputs:
            cls.s_input_event_classes = inputs
        if outputs:
            cls.s_output_event_classes = outputs

        assert all(issubclass(e, Event) for e in cls.s_output_event_classes),   'outputs must be a tuple of Event subclasses'

        cls.s_input_switch = input_switch = {}
        for ie_class in cls.s_input_event_classes:
            event_class_name = ie_class.__name__
            assert issubclass(ie_class, Event), f'input {ie_class} is not a subclass of Event'
            method_name = f'{event_class_name}_{PROCESS_METHOD_SUFFIX}'
            proc_method = getattr(cls, method_name, None)
            assert callable(proc_method), f'{cls}.{method_name} - method is missing'
            sig = inspect.signature(proc_method, eval_str=True)
            params = list(sig.parameters.values())
            assert len(params) == 2, f'{cls}.{method_name} - expected two params (self, event: Event)'
            assert params[0].name == 'self', f'{cls}.{method_name} - self parameter is missing'
            assert inspect.isclass(ann := params[1].annotation) and issubclass(ann, Event), f'{cls}.{method_name} - second param must be an instance of Event'

            input_switch[ie_class] = proc_method

        super().__init_subclass__(**kwargs)

    def pending_events(self) -> tuple[dict, list[Event]]:
        watermarks_per_class = {}
        watermarks_per_server = {}
        events = []
        event_class: type[Event]
        last_watermarks = self.last_watermarks
        for event_class in self.__class__.s_input_event_classes:
            store = event_class.store()
            watermark = watermarks_per_server.get(store)
            if watermark is None:
                watermark = store.server_time() - timedelta(milliseconds = 1)
                watermarks_per_server[store] = watermark

            event_class_name = PyClass.name(event_class)
            last = last_watermarks.get(event_class_name)
            query = f(_at = BETWEEN(last, watermark, bounds = (False, False))) if last else f(_at = LT(watermark))
            events.extend(event_class.load_many(query = query))
            watermarks_per_class[event_class_name] = watermark
        events.sort(key = lambda e: e._at)
        return watermarks_per_class, events

    def advance(self, watermarks: dict):
        self.last_watermarks = self.last_watermarks | watermarks
        self.save()

    def needs_processing(self, event: Event) -> bool:
        """Whether this processor should apply `event`. Default: everything in its inputs. Override to
        scope a processor to a subset (e.g. one partition) — the per-processor watermark still advances
        over skipped events, so each event is seen once per processor and never re-applied."""
        return True

    def process_pending_events(self) -> int:
        watermarks, events = self.pending_events()
        f_switch = self.s_input_switch
        for event in events:
            if self.needs_processing(event):
                f_switch[event.__class__](self, event)

        self.advance(watermarks)
        return len(events)

    def run_until(self, event: Event = None, timeout: float = 5.0) -> int:
        """Drain pending events until quiescent, then return the total processed.

        Loops `process_pending_events` past the sub-millisecond watermark lag (a just-saved event's
        `_at` is younger than the `server_time - 1ms` watermark) and past cascades (a handler may emit
        further events applied on a later pass). `event` is **advisory** — the event you expect to see
        applied — kept only for call-site readability; draining to quiescence is what actually
        guarantees it and any cascade it triggers. Raises `TimeoutError` if the drain has not settled
        within `timeout` seconds (an unbounded arrival stream, or a handler that keeps re-emitting).
        """
        deadline = time.monotonic() + timeout
        total = 0
        while True:
            n = self.process_pending_events()
            total += n
            if n == 0:
                time.sleep(0.003)  # let just-saved events age past the watermark, then re-check
                n = self.process_pending_events()
                total += n
                if n == 0:
                    return total
            if time.monotonic() > deadline:
                raise TimeoutError(f'{type(self).__name__}.run_until did not settle within {timeout}s')
