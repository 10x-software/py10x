from core_10x.xnone import XNone


class TraitMethodError(Exception):
    """
    NOTE: other_exc must be set in except clause ONLY!
    """

    @staticmethod
    def create(
        traitable, traitable_class, trait_name: str, method_name: str, reason: str = '', value=XNone, args: tuple = (), other_exc: Exception = None
    ):
        if isinstance(other_exc, TraitMethodError):
            return other_exc

        msg = []
        traitable_class = traitable_class or traitable.__class__
        msg.append(f'Failed in {traitable_class}.{trait_name}.{method_name}')
        if traitable:
            msg.append(f'    object = {traitable.id()};')

        if reason:
            msg.append(f'    reason = {reason}')

        if value is not None:
            msg.append(f'    value = {value}')

        if args:
            msg.append(f'    args = {args}')

        if other_exc:
            msg.append(f'original exception = {other_exc!s}')

        return TraitMethodError('\n'.join(msg))
