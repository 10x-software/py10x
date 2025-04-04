from core_10x.xnone import XNone

class TraitMethodError(Exception):
    """
    NOTE: other_exc must be set in except clause ONLY!
    """
    @staticmethod
    def create(
        traitable,
        trait_name: str,
        method_name: str,
        reason: str             = '',
        value                   = XNone,
        args: tuple             = (),
        other_exc: Exception    = None
    ):
        if isinstance(other_exc, TraitMethodError):
            return other_exc

        msg = []
        msg.append(f'Failed in {traitable.__class__.__name__}.{trait_name}.{method_name}')
        msg.append(f'    object = {traitable.id()};')

        if reason:
            msg.append(f'    reason = {reason}')

        if value is not None:
            msg.append(f'    value = {value}')

        if args:
            msg.append(f'    args = {args}')

        if other_exc:
            msg.append(f'original exception = {str(other_exc)}')

        return TraitMethodError('\n'.join(msg))

