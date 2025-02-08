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
        for _, param in params.items():
            if not param.kind in ARGS_KWARGS:
                return _cache_single_arg(f)

    return _cache_with_args(f)

def _cache_no_args(f):
    the_value = [ XNone ]
    def getter():
        v = the_value[0]
        if v is XNone:
            the_value[0] = v = f()
        return v

    getter.__name__ = f.__name__
    getter.value = the_value
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
    return getter

def standard_key(args: tuple, kwargs: dict) -> tuple:
    sorted_kwargs = tuple((k, kwargs[k]) for k in sorted(kwargs))
    return *args, *sorted_kwargs

# def hash_key( obj ) -> int:
#     try:
#         return hash( obj )
#     except Exception:
#         return hash(str(obj))
