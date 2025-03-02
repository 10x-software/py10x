#import abc

from core_10x.trait import Trait, T, Ui
from core_10x.rc import RC, RC_TRUE

from ui_10x.utils import UxStyleSheet

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
        trait = trait_editor.trait
        w_type = trait_editor.ui_hint.widget_type
        if w_type is Ui.WIDGET_TYPE.NONE:
            return None

        w_cls = TraitWidget.widget_class(w_type)
        return w_cls(trait_editor)

    def __init__(self, trait_editor):
        self.trait_editor = trait_editor
        self.trait: Trait = trait_editor.trait
        self.program_edit = False

        self._create()

        if self.trait.flags_on(T.READONLY) or self.trait.ui_hint.flags_on(Ui.SELECT_ONLY):
            self.set_read_only()

        self.set_tool_tip(self.trait.ui_hint.tip)

        entity = self.trait_editor.entity
        sh = entity.get_style_sheet(self.trait)
        UxStyleSheet.update(self, sh)

        #self.create_ui_node()  #-- TODO: implement!
        self.set_widget_value(entity.get_value(self.trait))

    def is_read_only(self) -> bool:
        return self.trait.is_read_only() or self.trait_editor.is_read_only()

    def widget_value(self):
        return self.value()

    def set_widget_value(self, value) -> bool:
        self.program_edit = True
        try:
            self.set_value(value)
        except Exception:       #-- the real widget is gone (so far, has encountered this only in Qt on Mac OS)
            #self.clean()   #-- TODO: fix!
            return False

        sh = self.trait_editor.entity.get_style_sheet(self.trait)
        UxStyleSheet.update(self.widget(), sh)
        self.program_edit = False
        return True

    s_bg_colors = ('orange', 'while', 'blue')
    def update_trait_value(self, value = None, invalidate = False):
        if not self.program_edit:
            entity = self.trait_editor.entity
            if invalidate:
                entity.invalidate_value(self.trait)
                rc = RC_TRUE
            else:
                if value is None:
                    value = self.widget_value()
                rc = entity.set_value(self.trait, value)

            tip = rc.error() if not rc else self.trait.ui_hint.tip
            self.set_tool_tip(tip)
            self.set_style_sheet(f'background-color: {self.s_bg_colors[bool(rc)]}')

    def refresh(self, ui_node):
        editor = self.trait_editor
        trait = self.trait
        if not editor or not trait:     #-- the widget could be gone
            return

        value = editor.entity.get_value(trait) #-- no dep (yet) (?)
        self.relink_nodes(ui_node)
        self.set_widget_value(value)

    def ui_node_class(cls):         raise NotImplementedError
    def _create(self):              raise NotImplementedError
    def _set_read_only(self, flag): raise NotImplementedError
    def _value(self):               raise NotImplementedError
    def _set_value(self, value):    raise NotImplementedError


