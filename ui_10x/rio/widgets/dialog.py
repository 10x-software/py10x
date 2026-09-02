from __future__ import annotations

from typing import TYPE_CHECKING

import rio
import ui_10x.platform_interface as i
from ui_10x.rio.component_builder import DynamicComponent, UserSessionContext, Widget
from ui_10x.rio.internals.app import App10x

if TYPE_CHECKING:
    import uvicorn


class Dialog(Widget, i.Dialog):
    __slots__ = (
        '_auto_min_width',
        '_dialog',
        '_modal',
        '_parent',
        '_server',
        'accepted',
        'on_accept',
        'on_reject',
        'title',
    )
    s_component_class = rio.Column
    # Keep the Column wrapper — Widget.s_unwrap_single_child would discard
    # min_width / grow on the dialog and size only to the inner layout.
    s_unwrap_single_child = False
    s_forced_kwargs = {'grow_x': False, 'grow_y': False}
    # Fraction of the browser width used when auto-sizing (see show()).
    # Height stays natural (content-sized).
    s_default_width_fraction = 0.55
    s_default_min_width_rem = 28.0

    def _make_kwargs(self, **kwargs):
        kwargs = super()._make_kwargs(**kwargs)
        del kwargs['align_y']
        return kwargs

    def __init__(self, parent: Widget | None = None, children=(), title=None, on_accept=None, on_reject=None, **kwargs):
        assert isinstance(parent, Widget | None)
        super().__init__(*children, **kwargs)
        self.on_accept = self._wrapper(on_accept, accept=True)
        self.on_reject = self._wrapper(on_reject)
        self.accepted = True
        self.title = title
        self._dialog = None
        self._server = None
        self._parent = parent
        self._modal = True
        # True until an explicit set_minimum_width() call (UxDialog may set one).
        self._auto_min_width = 'min_width' not in kwargs

    def set_window_title(self, title: str):
        self.title = title

    def _wrapper(self, func, accept=False):
        func = self.callback(func) if func else None

        def wrapper(*args):
            self.accepted = accept
            if func:
                func(*args)
            self._on_close()

        return wrapper

    def reject(self):
        self.accepted = False
        self._on_close()

    def done(self, result: int):
        self.accepted = bool(result)
        self._on_close()

    def _rio_dialog(self):
        future = self._dialog
        if future is None or not future.done():
            return None
        return future.result()

    def _on_close(self):
        """Programmatic close (Ok / Cancel buttons)."""
        dialog = self._rio_dialog()
        self._dialog = None
        if dialog is not None and dialog.is_open:
            dialog._root_component.session.create_task(dialog.close())
        elif self._server:
            self._server.should_exit = True

    def _on_user_close(self):
        """Rio dismissed the dialog (Escape or click outside)."""
        self.accepted = False
        self._dialog = None
        # UxDialog stores cancel_callback; default is reject (already closed — skip).
        cancel = getattr(self, 'cancel_callback', None)
        if callable(cancel) and cancel is not self.reject:
            try:
                cancel()
            finally:
                self.accept_callback = None
                self.cancel_callback = None
        else:
            if hasattr(self, 'accept_callback'):
                self.accept_callback = None
            if hasattr(self, 'cancel_callback'):
                self.cancel_callback = None

    def _on_server_created(self, server: uvicorn.Server):
        self._server = server

    def _on_dialog_open(self, future):
        self._dialog = future

    def exec(self):
        if self.current_session():
            print('Cannot exec() in an existing event loop - using show() instead. WARNING: this only works with callbacks!')
            self.show()
            return

        assert not self._parent, 'Parent is not allowed for top level dialog'

        title = self.title or 'Dialog'
        sessions = set()

        def on_session_start(session):
            sessions.add(session)
            print('on_session_start:', len(sessions))
            with session[UserSessionContext]:
                self.on_open()

        def on_session_close(session):
            for component in session._weak_components_by_id.values():
                if isinstance(component, DynamicComponent):
                    component.builder.component = None
                    component.builder.subcomponent = None
            sessions.remove(session)
            print('on_session_close:', len(sessions))

        def build():
            print('build:', len(sessions))
            if len(sessions) == 1:
                component = DynamicComponent(builder=self)
                if component.session in sessions:
                    return component

            from rio.components.error_placeholder import ErrorPlaceholder

            return ErrorPlaceholder(error_summary='Only one session is allowed for `Dialog.exec`', error_details='')

        app = rio.App(
            name=title,
            build=build,
            on_session_start=on_session_start,
            on_session_close=on_session_close,
            default_attachments=[UserSessionContext()],
        )
        debug = True
        if debug:
            from rio.debug.monkeypatches import apply_monkeypatches

            apply_monkeypatches()
        App10x(app)._run_in_window(debug_mode=debug, on_server_created=self._on_server_created)
        return self.accepted

    def set_minimum_width(self, width: int):
        self._auto_min_width = False
        super().set_minimum_width(width)

    def _apply_default_min_width(self, session: rio.Session) -> None:
        """Size dialog width to a fraction of the live browser width (rem → px)."""
        if not self._auto_min_width:
            return
        rem_w = float(getattr(session, 'window_width', 0) or 0)
        ppf = float(getattr(session, 'pixels_per_font_height', 0) or 16)
        rem = max(self.s_default_min_width_rem, rem_w * self.s_default_width_fraction) if rem_w > 0 else self.s_default_min_width_rem
        # build() converts px → rem via / pixels_per_font_height
        self._kwargs['min_width'] = rem * ppf

    def on_open(self):
        pass

    def show(self):
        if not self.current_session():
            self.exec()
        else:
            self.on_open()
            session = self.current_session()
            self._apply_default_min_width(session)
            future = session.show_custom_dialog(
                build=self,
                on_close=self._on_user_close,
                modal=self._modal,
                # Escape + click-outside dismiss (Rio popup manager).
                user_closable=True,
                owning_component=self._parent.component if self._parent else None,
            )
            session.create_task(future).add_done_callback(self._on_dialog_open)

    def set_window_flags(self, flags):
        raise NotImplementedError

    def set_modal(self, modal: bool):
        self._modal = modal
