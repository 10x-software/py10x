import os
import sys
import typing

if typing.TYPE_CHECKING:
    import platform_interface as ux

    Model: type | None
    TableView: type
else:
    pname = os.getenv('UI_PLATFORM')
    if pname is None:
        pname = 'Qt6' if 'rio' not in sys.modules else 'Rio'

    if pname == 'Qt6':
        import ui_10x.qt6.platform_implementation as ux
        from ui_10x.qt6.table_view import Model, TableView
    elif pname == 'Rio':
        import ui_10x.rio.platform_implementation as ux
        from ui_10x.rio.widgets.table import TableView

        Model = None
    else:
        raise ImportError(f'UI implementation for `{pname}` is not available')


__all__ = ['Model', 'TableView', 'ux']
