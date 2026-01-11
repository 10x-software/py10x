from core_10x.named_constant import NamedConstant
from core_10x.py_class import PyClass

class TS_STORE_TYPE(NamedConstant):
    """
    All known TsStore subclasses must be "registered" here.
    """
    MONGODB     = 'infra_10x.mongodb_store.MongoStore'
    ...

    @classmethod
    def ts_store_class(cls, uri_protocol: str):
        """
        example: TS_STORE_TYPE.ts_store_class('mongodb')
        """
        symbol = cls.s_dir.get(uri_protocol.upper())
        if symbol is None:
            raise ValueError(f'Unknown URI protocol: {uri_protocol}')

        ts_class = PyClass.find(symbol.value)
        if not ts_class:
            raise TypeError(f'{symbol.value} - unknown TsStore class')

        return ts_class

