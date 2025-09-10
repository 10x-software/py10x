import inspect

from core_10x.xnone import XNone

#===================================================================================================================================
#   @cache must be used to cache results of function calls globally (at the process level)
#
#   Notes:
#
#   - non-hashable args are NOT supported for performance reasons
#   - args MUST follow the declaration order for performance reasons (otherwise, the same result may be cached multiple times
#       e.g. f(a=1, b=2) and f(b=2, a=1)
#   - the most common 'users' are class methods
#===================================================================================================================================
ARGS_KWARGS = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)

def cache(f):
    sig = inspect.signature(f)
    params = sig.parameters
    num_args = len(params)
    if num_args == 0:
        return _cache_no_args(f)

    if num_args == 1:
        for name, param in params.items():
            if param.kind not in ARGS_KWARGS and param.default is inspect.Parameter.empty:
                return _cache_single_arg(f)

    return _cache_with_args(f)

def _cache_no_args(f):
    the_value = [XNone]
    def getter():
        v = the_value[0]
        if v is XNone:
            the_value[0] = v = f()
        return v

    def clear():    the_value[0] = XNone

    getter.__name__ = f.__name__
    getter.value = the_value
    getter.clear = clear
    return getter

def _cache_single_arg(f):
    the_cache = {}
    def getter(arg):
        value = the_cache.get(arg, the_cache)      #-- will throw if arg is not hashable!
        if value is the_cache:          #-- i.e., arg is seen for the first time
            value = f(arg)
            the_cache[arg] = value

        return value

    getter.__name__ = f.__name__
    getter.cache = the_cache
    getter.clear = lambda: the_cache.clear()
    return getter

def _cache_with_args(f):
    the_cache = {}
    def getter(*args, **kwargs):
        key = *args, *tuple(kwargs.items())
        value = the_cache.get( key, the_cache )     #-- will throw if key is not hashable!
        if value is the_cache:                      #-- i.e., key is seen for the first time
            value = f(*args, **kwargs)
            the_cache[key] = value

        return value

    getter.__name__ = f.__name__
    getter.cache = the_cache
    getter.clear = lambda: the_cache.clear()
    return getter

def standard_key(args: tuple, kwargs: dict) -> tuple:
    sorted_kwargs = tuple((k, kwargs[k]) for k in sorted(kwargs))
    return *args, *sorted_kwargs

#========= The singleton

def ___operator_new(cls, *args, **kwargs):
    key = standard_key((cls, *args), kwargs)
    ptr = cls.___instances.get(key)
    if not ptr:
        ptr = object.__new__(cls)
        cls.___ctor(ptr, *args, **kwargs)
        cls.___instances[key] = ptr
    return ptr

def ___operator_reset(cls):   cls.___instances = {}

def singleton(cls):
    cls.___instances = {}
    cls.__new__ = ___operator_new
    cls.___ctor = cls.__init__
    cls.__init__ = lambda self, *args, **kwargs: None
    cls._reset_singleton = lambda: ___operator_reset( cls )
    return cls

# def hash_key( obj ) -> int:
#     try:
#         return hash( obj )
#     except Exception:
#         return hash(str(obj))
