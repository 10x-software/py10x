from __future__ import annotations

from typing import TYPE_CHECKING

import rio
import ui_10x.platform_interface as i
from ui_10x.rio.component_builder import DynamicComponent, UserSessionContext, Widget
from ui_10x.rio.internals.app import App10x

if TYPE_CHECKING:
    import uvicorn


class Dialog(Widget, i.Dialog):
    __slots__ = ('_dialog', '_modal', '_parent', '_server', 'accepted', 'on_accept', 'on_reject', 'title')
    s_component_class = rio.Column
    s_forced_kwargs = {'grow_x': True, 'grow_y': True}

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
        self._on_close()

    def done(self, result: int):
        self._on_close()
        self.accepted = bool(result)

    def _on_close(self):
        if self._dialog:
            dialog = self._dialog.result()
            dialog._root_component.session.create_task(dialog.close())
            self._dialog = None
        elif self._server:
            self._server.should_exit = True

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
            default_attachments=[UserSessionContext(host='localhost', dbname='test')],
        )
        debug = True
        if debug:
            from rio.debug.monkeypatches import apply_monkeypatches

            apply_monkeypatches()
        App10x(app)._run_in_window(debug_mode=debug, on_server_created=self._on_server_created)
        return self.accepted

    def show(self):
        if not self.current_session():
            self.exec()
        else:
            future = self.current_session().show_custom_dialog(
                build=self,
                on_close=self._on_close,
                modal=self._modal,
                user_closable=False,
                owning_component=self._parent.component if self._parent else None,
            )
            self.current_session().create_task(future).add_done_callback(self._on_dialog_open)

    def set_window_flags(self, flags):
        raise NotImplementedError

    def set_modal(self, modal: bool):
        self._modal = modal
