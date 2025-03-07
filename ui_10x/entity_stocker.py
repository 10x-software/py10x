from core_10x.traitable import Traitable, Trait, T, RT, RC, Ui

from ui_10x.utils import ux, ux_push_button, ux_warning, ux_success, ux_answer
from ui_10x.traitable_editor import TraitableEditor, TraitableView


class StockerPlug(Traitable):
    master: Traitable               = RT()
    current_class_trait_name: str   = RT('current_class')
    current_entity_trait_name: str  = RT('current_entity')
    new_entity_cb_name: str         = RT('on_new_entity')            #-- f(new_entity: Traitable)
    changed_entity_cb_name: str     = RT('on_changed_entity')        #-- f(ce: Traitable) - after accepting edits and reloading
    deleted_entity_cb_name: str     = RT('on_deleted_entity')        #-- f(de: Traitable)

    new_entity_cb                   = RT()
    changed_entity_cb               = RT()
    deleted_entity_cb               = RT()

    current_class: type             = RT()
    current_entity: Traitable       = RT()

    def _cb(self, cb_name: str):
        m = self.master
        if m:
            cls = m.__class__
            method = getattr(cls, cb_name, None)
            if method:
                return lambda e: method(m, e)

        return lambda e: None

    def new_entity_cb_get(self):        return self._cb(self.new_entity_cb_name)
    def changed_entity_cb_get(self):    return self._cb(self.changed_entity_cb_name)
    def deleted_entity_cb_get(self):    return self._cb(self.deleted_entity_cb_name)

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

class EntityStocker(Traitable):
    plug: StockerPlug               = RT()
    entity_viewer: TraitableEditor  = RT()
    buttons_spec: dict              = RT(T.EVAL_ONCE)

    def entity_viewer_get(self) -> TraitableEditor:
        ce = self.plug.current_entity
        if not ce:
            return None

        return TraitableEditor.editor(ce, view = TraitableView.default(ce.__class__, read_only = True))

    def top_layout(self) -> ux.HBoxLayout:
        lay = ux.HBoxLayout()
        lay.set_spacing(0)

        for name, (cb, icon) in self.buttons_spec.items():
            lay.add_widget(ux_push_button(name, callback = cb, style_icon = icon))

        return lay

    def main_layout(self) -> ux.Layout:
        entity_viewer = self.entity_viewer
        if entity_viewer:
            lay = ux.VBoxLayout()
            lay.add_layout(self.top_layout(), stretch = 0)
            lay.add_widget(entity_viewer.main_widget)

        else:
            lay = self.top_layout()

        return lay

    def on_new_entity(self):
        cls = self.plug.current_class
        if cls:
            new_entity = cls()
            ed = TraitableEditor.editor(new_entity)
            if ed.popup(copy_entity = False, title = f"New Entity of {cls.__name__}"):
                #rc = new_entity.share()     #-- TODO! share()
                rc = RC(True)   #--#--
                if not rc:
                    ux_warning(rc.error(), parent = None)   #-- TODO: parent must be an existing appropriate widget

                else:
                    self.plug.new_entity_cb(new_entity)

    def on_edit_entity(self):
        ce = self.plug.current_entity
        if ce:
            ed = TraitableEditor.editor(ce)
            if ed.popup():
                self.plug.changed_entity_cb(ce)

    def on_reload_entity(self):
        ce = self.plug.current_entity
        if ce:
            rc = ce.reload()
            if not rc:
                ux_warning(f'Failed to reload entity {ce.__class__}/{ce.id()}', parent = None)

            else:
                self.plug.changed_entity_cb(ce)

    def on_save_entity(self):
        ce = self.plug.current_entity
        if ce:
            try:
                rc = ce.save()
                if not rc:
                    ux_warning(rc.error(), parent = None)

                return

            except Exception as e:  #-- revision conflict?
                #-- TODO: resolve revision conflict - MergingEditor
                ...

            #-- The conflict seems to be resolved, try again
            try:
                rc = ce.save()
                if not rc:
                    ux_warning(rc.error(), parent = None)
                    return

            except Exception:
                ux_warning('Failed to resolve revision conflict (most probably due to continuous updates from other session(s)')
                return

            ux_success(f'Conflict resolved, {ce.__class__}/{ce.id()} has been saved')

    def on_delete_entity(self):
        ce = self.plug.current_entity
        if ce:
            if ux_answer(f'Please confirm deletion of {ce.__class__}/{ce.id()}', parent = None):
                id_value = ce.id()
                self.plug.deleted_entity_cb(ce)
                #if not ce.delete():    #-- TODO: implement delete()
                #    ux_warning('Deletion failed: {ce.__class__}/{ce.id()')

    def buttons_spec_get(self) -> dict:
        return dict(
        new     = (self.on_new_entity,      'FileIcon'),
        edit    = (self.on_edit_entity,     'FileDialogDetailedView'),
        reload  = (self.on_reload_entity,   'ArrowDown'),
        save    = (self.on_save_entity,     'DriveNetIcon'),
        delete  = (self.on_delete_entity,   'DialogDiscardButton')
    )
