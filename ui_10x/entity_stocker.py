from typing import Any

from core_10x.traitable import RT, T, Traitable
from core_10x.ts_store import SaveIfChanged

from ui_10x.traitable_editor import TraitableEditor, TraitableView
from ui_10x.utils import ux, ux_answer, ux_push_button, ux_warning


class StockerPlug(Traitable):
    master: Traitable
    # fmt: off
    current_class_trait_name: str   = RT('current_class')
    current_entity_trait_name: str  = RT('current_entity')
    changed_entity_cb_name: str     = RT('on_changed_entity')        #-- f(ce: Traitable) - after accepting edits and reloading
    deleted_entity_cb_name: str     = RT('on_deleted_entity')        #-- f(de: Traitable)
    track_changes_trait_name: str     = RT('track_changes')
    # fmt: on

    new_entity_cb: Any
    changed_entity_cb: Any
    deleted_entity_cb: Any

    current_class: type
    current_entity: Traitable
    track_changes: bool

    def _cb(self, cb_name: str):
        m = self.master
        if m:
            cls = m.__class__
            method = getattr(cls, cb_name, None)
            if method:
                return lambda e: method(m, e)

        return lambda e: None

    # fmt: off
    def changed_entity_cb_get(self):    return self._cb(self.changed_entity_cb_name)
    def deleted_entity_cb_get(self):    return self._cb(self.deleted_entity_cb_name)
    # fmt: on

    def current_class_get(self) -> type:
        m = self.master
        if not m:
            return None

        cls = m.get_value(self.current_class_trait_name)
        if not cls:
            ce = self.current_entity
            if ce:
                cls = ce.__class__

        return cls

    def current_entity_get(self) -> Traitable:
        m = self.master
        if not m:
            return None

        return m.get_value(self.current_entity_trait_name)

    def track_changes_get(self) -> bool:
        m = self.master
        if not m:
            return None

        return m.get_value(self.track_changes_trait_name)


class EntityStocker(Traitable):
    plug: StockerPlug
    entity_viewer: TraitableEditor
    buttons_spec: dict
    change_trackers: dict[Traitable, SaveIfChanged] = RT(T.STICKY, default={})

    def _on_accept(self, rc, ce: Traitable, ed: TraitableEditor):
        # Only tracked edits belong here. Without the guard an untracked edit stores
        # `None` and pins `ce` in this STICKY dict for the stocker's lifetime, since
        # entries are dropped only on save/reload.
        if ed.change_tracker is not None:
            self.change_trackers[ce] = ed.change_tracker
        self.plug.changed_entity_cb(ce)

    def entity_viewer_get(self) -> TraitableEditor:
        ce = self.plug.current_entity
        if not ce:
            return None

        return TraitableEditor.editor(ce, view=TraitableView.default(ce.__class__, read_only=True))

    def top_layout(self) -> ux.HBoxLayout:
        lay = ux.HBoxLayout()
        lay.set_spacing(0)

        for name, (cb, icon) in self.buttons_spec.items():
            lay.add_widget(ux_push_button(name, callback=cb, style_icon=icon))

        return lay

    def main_widget(self) -> ux.Widget:
        entity_viewer = self.entity_viewer
        if entity_viewer:
            lay = ux.VBoxLayout()
            lay.add_layout(self.top_layout(), stretch=0)
            lay.add_widget(entity_viewer.main_widget())

        else:
            lay = self.top_layout()

        w = ux.Widget()
        w.set_layout(lay)
        return w

    # def on_new_entity(self):
    #     cls = self.plug.current_class
    #     if cls:
    #         new_entity = cls()
    #         ed = TraitableEditor.editor(new_entity)
    #         if ed.popup(copy_entity = False, title = f'New Entity of {cls.__name__}', save = True):
    #             rc = new_entity.share(False)    #-- not accepting existing entity values, if any
    #             if not rc:
    #                 ux_warning(rc.error(), parent = None)   #-- TODO: parent must be an existing appropriate widget
    #                 #-- TODO: what to do with a temp new_entity?
    #
    #             else:
    #                 self.plug.new_entity_cb(new_entity)

    def on_edit_entity(self):
        ce = self.plug.current_entity
        if ce:
            ed = TraitableEditor.editor(ce)
            track_changes = self.plug.track_changes
            if track_changes and (tracker := self.change_trackers.get(ce)):
                ed.change_tracker = tracker
            ed.popup(track_changes=track_changes, accept_hook=lambda rc: self._on_accept(rc, ce, ed))

    def on_reload_entity(self):
        ce = self.plug.current_entity
        if not ce:
            return

        tracker = self.change_trackers.get(ce)
        # Only reload the tracker once `ce` itself came back: a successful
        # tracker.reload() clears everything it tracked, so running it after a failed
        # ce.reload() would leave an empty tracker still listed in change_trackers —
        # and the next Save would then report success having written nothing.
        ok = ce.reload() and (tracker is None or tracker.reload())

        if not ok:
            ux_warning(f'Failed to reload entity {ce.__class__}/{ce.id()}', parent=None, on_close=lambda ctx: None)
        else:
            self.change_trackers.pop(ce, None)
            self.plug.changed_entity_cb(ce)

    def on_save_entity(self):
        ce = self.plug.current_entity
        if not ce:
            return

        tracker = self.change_trackers.get(ce)

        rc = tracker.save() if tracker else ce.save()
        if rc:
            self.change_trackers.pop(ce, None)
        else:
            ux_warning(rc.error(), parent=None, on_close=lambda ctx: None)

    def on_delete_entity(self):
        ce = self.plug.current_entity
        if ce:

            def on_close(accepted: bool):
                if accepted:
                    if not ce.delete():
                        ux_warning('Deletion failed: {ce.__class__}/{ce.id()', parent=None, on_close=lambda ctx: None)
                    self.plug.deleted_entity_cb(ce)

            ux_answer(f'Please confirm deletion of {ce.__class__}/{ce.id()}', parent=None, on_close=on_close)

    def buttons_spec_get(self) -> dict:
        # fmt: off
        return {
            #'new':   (self.on_new_entity,        'FileIcon'),
            'edit':   (self.on_edit_entity,       'FileDialogDetailedView'),
            'reload': (self.on_reload_entity,     'ArrowDown'),
            'save':   (self.on_save_entity,       'DriveNetIcon'),
            'delete': (self.on_delete_entity,     'DialogDiscardButton')
        }
        # fmt: on
