from core_10x.exec_control import GRAPH_ON, BTP

class Scenario:
    s_instances = {}
    def __new__(cls, name: str = None, debug: bool = -1, convert_values: bool = -1):
        s = cls.s_instances.get(name)
        if s is None:
            s = object.__new__(cls)
            if name:
                cls.s_instances[name] = s
            s.name = name
            s.btp = GRAPH_ON(debug = debug, convert_values = convert_values)

        return s

    def __enter__(self):
        self.btp.begin_using()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.btp.end_using()
        if not self.name:
            self.btp = None