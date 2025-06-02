from core_10x.trait import Trait, T, Ui
from core_10x.rc import RC, RC_TRUE

from ui_10x.utils import ux, UxStyleSheet


class TraitWidget:
    s_hinted_widgets = {}
    def __init_subclass__(cls, widget_type: Ui.WIDGET_TYPE = None, **kwargs):
        if widget_type:
            TraitWidget.s_hinted_widgets[widget_type] = cls

    @staticmethod
    def widget_class(widget_type: Ui.WIDGET_TYPE):
        w_cls = TraitWidget.s_hinted_widgets.get(widget_type)
        assert w_cls, f'Unknown trait widget type: {widget_type}'
        return w_cls

    @staticmethod
    def instance(trait_editor) -> 'TraitWidget':
        w_type = trait_editor.ui_hint.widget_type
        if w_type is not Ui.WIDGET_TYPE.NONE:
            w_cls = TraitWidget.widget_class(w_type)
            return w_cls(trait_editor)

    def __init__(self, trait_editor):
        self.trait_editor = trait_editor
        self.trait: Trait = trait_editor.trait
        self.program_edit = False

        self._create()

        if self.trait_editor.is_read_only():
            self._set_read_only(True)

        self.set_tool_tip(self.trait.ui_hint.tip)

        entity = self.trait_editor.entity

        self.style_sheet = sheet = UxStyleSheet(self)
        sh = entity.get_style_sheet(self.trait)
        sheet.update(sh)

        value = entity.get_value(self.trait)
        self.set_widget_value(value)

        self.refresh_context = ctx = RefreshContext(self)
        entity.create_ui_node(self.trait, ctx.emit_signal)

    def refresh(self):
        entity = self.trait_editor.entity
        trait = self.trait
        entity.update_ui_node(self.trait)

        if not trait.flags_on(T.EXPENSIVE):
            value = entity.get_value(trait)
            self.set_widget_value(value)
        else:
            sh = entity.get_style_sheet(trait)
            self.style_sheet.update(sh)

            if not entity.is_valid(trait):
                self.style_sheet.update({Ui.BG_COLOR: 'lightblue'}, _system = True)

    def widget_value(self):
        return self._value()

    def set_widget_value(self, value) -> bool:
        self.program_edit = True
        try:
            self._set_value(value)
        except Exception:       #-- the real widget is gone (so far, has encountered this only in Qt on Mac OS)
            #self.clean()   #-- TODO: fix!
            self.program_edit = False
            return False

        sh = self.trait_editor.entity.get_style_sheet(self.trait)
        self.style_sheet.update(sh)
        self.program_edit = False
        return True

    def update_trait_value(self, value = None, invalidate = False):
        if not self.program_edit:
            entity = self.trait_editor.entity
            if invalidate:
                entity.invalidate_value(self.trait)
                rc = RC_TRUE
            else:
                if value is None:
                    value = self.widget_value()

                try:
                    rc = entity.set_value(self.trait, value)
                except Exception as e:
                    rc = RC(False, str(e))

            if not rc:
                self.set_tool_tip(rc.error())
                self.style_sheet.update({Ui.BG_COLOR: 'orange'}, _system = True)
            else:
                self.set_tool_tip(self.trait.ui_hint.tip)
                self.style_sheet.restore()

    def _create(self):              raise NotImplementedError
    def _set_read_only(self, flag): raise NotImplementedError
    def _value(self):               raise NotImplementedError
    def _set_value(self, value):    raise NotImplementedError

class RefreshContext(ux.Object):
    REFRESH = ux.signal_decl(object)

    def __init__(self, trait_widget: TraitWidget):
        super().__init__()
        self.trait_widget = trait_widget
        self.REFRESH.connect(TraitWidget.refresh, type = ux.QueuedConnection)

    def emit_signal(self):
        self.REFRESH.emit(self.trait_widget)
