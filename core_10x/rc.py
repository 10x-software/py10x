import sys
import traceback

from core_10x.named_constant import ErrorCode, Enum

class RC:
    """
    Stands for 'Return Code'. Main usage is for functions returning 'success' or 'error' with an optional payload.

    For just a 'success':
        RC_TRUE (a constant RC(True) instance)
        return RC_TRUE

    For 'success' with a single data:
        return RC(True, data)
        RC(enum, data)      - an instance of Enum subclass with a positive value

    For 'success' with multiple data:
            rc = RC(True)
            ...
                rc.add_data(data)
            ...
            return rc

    For a single error:
        return RC(False)    - if you are in except: to catch an exception with stack info
        return RC(False, message)
        return RC(error, message)   - an instance of ErrorCode subclass (with a non-positive value)

    For multiple errors:
            rc = RC(True)
            ...
                rc.add_error(message)
            ...
            return rc
    """
    __slots__ = ( 'rc', 'payload' )

    @classmethod
    def show_exception_info(cls, ex_info = None) -> str:
        if not ex_info:
            ex_info = sys.exc_info()

        assert isinstance(ex_info, tuple) and len(ex_info) == 3, f'Invalid ex_info: {ex_info}'

        ss = traceback.StackSummary.extract(traceback.walk_tb(ex_info[2]))
        return f"{ex_info[0]} ({ex_info[1]})\n{''.join(ss.format())}"

    def __init__(self, rc, data = None):
        self.rc = rc
        self.payload = [ data ] if data is not None else []

    def __bool__(self):
        rc = self.rc
        dt = type(rc)
        if dt is bool:
            return rc

        if issubclass(dt, Enum):
            rc = rc.value
        else:
            assert dt is int, f'Invalid rc: {rc}'

        return rc > 0

    def __repr__(self):
        if self.__bool__():
            data = self.payload
        else:
            data = self.error()
        return f'{self.rc}: {data}'

    def __iadd__(self, err):
        return self.add_error(err)

    def __ilshift__(self, err):
        return self.add_error(err)

    def unwrap(self) -> tuple:  #-- ( rc, payload)
        return (self.rc, self.payload)

    def data(self):
        print('cpp payload() called: ', self.payload)
        payload = self.payload
        return payload if len(payload) > 1 else payload[0]

    def error(self) -> str:
        if self.__bool__():
            return ''

        payload = self.payload
        n = len(payload)
        if n == 0:
            return self.__class__.show_exception_info()

        if n == 1:
            data = payload[0]
            if isinstance(self.rc, ErrorCode):
                return self.rc(**data)
            return data

        #-- multiple errors
        return '\n'.join(payload)

    def add_error(self, err) -> 'RC':
        if self.__bool__():
            self.rc = False

        dt = type(err)
        if dt is str:
            self.payload.append(err)

        elif dt is RC:
            self.payload.extend(err.payload)

        else:
            assert False, f'Expected str or RC; got {type(err)}'

        return self

    def add_data(self, data) -> 'RC':
        assert self.__bool__(), 'May not add_data() to an "error" RC'
        self.payload.append(data)
        return self

    def throw(self, exc = RuntimeError):
        err = self.error()
        if err:
            raise exc(err)

class _RcTrue(RC):
    def __init__(self):
        super().__init__(True)

    def add_error(self, err = ''):
        assert False, 'May not add error to a constant RC_TRUE'

    def add_data(self, data):
        assert False, 'May not add error to a constant RC_TRUE'

RC_TRUE = _RcTrue()

