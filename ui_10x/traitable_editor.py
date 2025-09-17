from collections.abc import Callable

from core_10x.exec_control import INTERACTIVE
from core_10x.global_cache import cache
from core_10x.py_class import PyClass
from core_10x.rc import RC, RC_TRUE
from core_10x.trait import Ui
from core_10x.traitable import Traitable

from ui_10x.trait_editor import TraitEditor
from ui_10x.traitable_view import TraitableView
from ui_10x.utils import UxDialog, ux, ux_warning


class TraitableEditor:
    """
    For many Traitables, a default Editor is sufficient.
    A custom Editor, if needed, should be in a particular class, module and package.
    Suppose your traitable class is abc.zyz.messages.TextMessage
    - the custom editor class must be TextMessageEditor
    - its module name must be messages_ui
    - the module may be in either abc.xyz, abc.xyz.ui or alternative packages
    - an editor class is searched first in alternative packages, if any; then in abc.xyz and abc.xyz.ui
    - if a custom class is not found, the default TraitableEditor is used.
    """
    @staticmethod
    @cache
    def find_editor_class(traitable_class, *alternative_packages, traitable_class_parent = None, verify_custom_class = True):
        assert issubclass(traitable_class, Traitable), f'{traitable_class} is not a subclass of Traitable'
        assert not traitable_class_parent or issubclass(traitable_class, traitable_class_parent), f'{traitable_class} is not a subclass of {traitable_class_parent}'

        found = PyClass.find_related_class(traitable_class, 'ui', 'Editor', *alternative_packages, alternative_parent_class = traitable_class_parent)
        if found:
            if verify_custom_class:
                assert issubclass(found, TraitableEditor), f'{traitable_class} has a custom editor class {found} which is not a subclass of TraitableEditor'

            return found

        return TraitableEditor

    @staticmethod
    def editor(
        entity: Traitable,
        *alternative_packages,                  #-- if custom editor class should be looked up somewhere else
        traitable_class_parent      = None,     #-- if a custom editor of entity's parent class could be used if it's missing for the entity.__class__
        verify_custom_class: bool   = True,     #-- if a custom editor class should be verified if exists
        view: TraitableView         = None,     #-- if a specific view for the entity should be used
        read_only: bool             = False     #-- browser if True
    ) -> 'TraitableEditor':
        editor_class = TraitableEditor.find_editor_class(
            entity.__class__,
            *alternative_packages,
            traitable_class_parent  = traitable_class_parent,
            verify_custom_class     = verify_custom_class
        )
        return editor_class(entity, view = view, read_only = read_only, _confirm = True)

    def __init__(self, entity: Traitable, view: TraitableView = None, read_only = False, _confirm = False):
        assert _confirm, 'Do not call TraitableEditor() directly, use TraitableEditor.editor() instead'
        assert isinstance(entity, Traitable), 'entity must be an instance of Traitable'

        entity_class = entity.__class__
        if view is None:
            view = TraitableView.default(entity_class, read_only = read_only)
        else:
            assert issubclass(entity_class, view.cls), f'Given view is not for {entity_class}'

        self.entity = entity
        self.traitable_processor = None

        trait_dir = entity_class.s_dir
        self.trait_hints = trait_hints = {trait_dir[trait_name]: ui_hint for trait_name, ui_hint in view.ui_hints.items() if not ui_hint.flags_on(Ui.HIDDEN)}

        self.main_w: ux.Widget|None = None
        self.callbacks_for_traits = {}
        self.init()

        callbacks = self.callbacks_for_traits
        self.trait_editors = {
            trait.name: TraitEditor(entity, trait, ui_hint, custom_callback = callbacks.get(trait.name), traitable_processor = lambda : self.traitable_processor)
            for trait, ui_hint in trait_hints.items()
        }

    def init(self):
        ...

    def set_callback_for_trait(self, trait_name: str, bound_method):
        self.callbacks_for_traits[trait_name] = bound_method

    def callback_for_trait(self, trait_name: str):
        return self.callbacks_for_traits.get(trait_name)

    def main_layout(self) -> ux.Layout:
        lay = ux.FormLayout()

        te: TraitEditor
        for te in self.trait_editors.values():
            label = te.new_label()
            w = te.new_widget()
            lay.add_row(label, w)
            if te.ui_hint.flags_on(Ui.SEPARATOR):
                lay.add_row(ux.separator())

        return lay

    def row_layout(self) -> ux.Layout:
        row = ux.HBoxLayout()

        stretched_trait_found = False
        for te in self.trait_editors.values():
            stretch = te.ui_hint.param('stretch', None)
            if stretch is not None:
                stretched_trait_found = True

            row.add_widget(te.new_label())
            row.add_widget(te.new_widget(), stretch=stretch)

            if te.ui_hint.flags_on(Ui.SEPARATOR):
                row.add_widget(ux.separator(horizontal = False))

        if stretched_trait_found:
            row.add_widget(ux.Label(), stretch = 1)

        return row

    def main_widget(self) -> ux.Widget:
        self.main_w = w = ux.Widget()
        lay = self.main_layout()
        w.set_layout(lay)
        return w

    def _cleanup_tp(self, apply:bool):
        self.main_w = None
        if self.traitable_processor:
            if apply:
                self.traitable_processor.export_nodes()
            self.traitable_processor=None

    def _dialog(self, layout: ux.Layout, title: str, ok: str, min_width: int, on_accept: Callable[[],RC]) -> UxDialog:
        ux.init()
        if layout is not None:
            w = self.main_w = ux.Widget()
            w.set_layout(layout)
        else:
            w = self.main_widget()

        def accept_callback():
            self._cleanup_tp(True)
            rc = self.entity.verify()
            if rc:
                return on_accept()
            return rc

        def cancel_callback():
            self._cleanup_tp(False)

        return UxDialog(w, title = title, accept_callback = accept_callback, cancel_callback = cancel_callback, ok = ok, min_width = min_width)

    def dialog(self, layout: ux.Layout = None, copy_entity = True, title = '', save = False, accept_hook = None, min_width = 0) -> UxDialog:
        if title is None:
            title = ''
        elif not title:
            title = self.entity.__class__.__name__

        ok = 'Save' if save else 'Ok'

        def on_accept():
            rc = self.entity.save() if save else RC_TRUE
            if not rc:
                self.warning(rc.error())
            if accept_hook:
                accept_hook(rc)
            return rc

        if copy_entity:
            self.traitable_processor = INTERACTIVE()

        return self._dialog(layout, title, ok, min_width, on_accept=on_accept)

    def popup(self, layout: ux.Layout = None, copy_entity = True, title = '', save = False, accept_hook = None, min_width = 0) -> None:
        self.dialog(layout = layout, copy_entity = copy_entity, title = title, save = save, accept_hook = accept_hook, min_width = min_width).show()

    def warning(self, msg: str, title = ''):
        ux_warning(msg, parent = self.main_w, title = title, on_close=lambda ctx: None)
