from core_10x.xnone import XNone


class TraitMethodError(Exception):
    """
    NOTE: other_exc must be set in except clause ONLY!
    """

    @staticmethod
    def create(traitable, traitable_class, trait_name: str, method_name: str, value=XNone, other_exc: Exception = None, args=()):
        assert other_exc

        if isinstance(other_exc, TraitMethodError):
            return other_exc

        msg = []
        traitable_class = traitable_class or traitable.__class__
        msg.append(f'Failed in {traitable_class}.{trait_name}.{method_name}')
        if traitable:
            msg.append(f'    object = {traitable.id()};')

        if value is not XNone:
            msg.append(f'    value = {value}')

        if args:
            msg.append(f'    args = {args}')

        if other_exc:
            msg.append(f'original exception = {type(other_exc).__name__}: {other_exc!s}')

        exc = TraitMethodError('\n'.join(msg))

        if other_exc and (tb := other_exc.__traceback__):
            exc = exc.with_traceback(tb)

        return exc
