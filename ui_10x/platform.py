import os
import typing

if typing.TYPE_CHECKING:
    import platform_interface as ux
else:
    pname = os.getenv('UI_PLATFORM')
    if pname is None:
        pname = 'Qt6'

    if pname == 'Qt6':
        import ui_10x.qt6.platform_implementation as ux
    elif pname == 'Rio':
        import ui_10x.rio.platform_implementation as ux
    else:
        assert False, 'UI implementation is not available'

#-- from ui_10x.platform import ux


