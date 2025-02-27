import abc

from core_10x.trait import Trait, Ui
from core_10x.rc import RC, RC_TRUE


class TraitWidget(abc.ABC):
    s_hinted_widgets = {}
    def __init_subclass__(cls, widget_type: Ui.WIDGET_TYPE = None, **kwargs):
        if widget_type:
            TraitWidget.s_hinted_widgets[widget_type] = cls

    @staticmethod
    def widget_class(widget_type: Ui.WIDGET_TYPE):
        w_cls = TraitWidget.s_hinted_widgets.get(widget_type)
        assert w_cls, f'Unknown trait widget type: {widget_type}'

    @staticmethod
    def instance(trait_editor) -> 'TraitWidget':
        trait = trait_editor.trait
        w_type = trait.t_def.ui_hint.widget_type
        if w_type is Ui.WIDGET_TYPE.NONE:
            return None

        w_cls = TraitWidget.widget_class(w_type)
        w_cls(trait_editor)

    def __init__(self, trait_editor, create_ui_node = True):
        self.trait_editor = trait_editor
        self.trait = trait
        self.program_edit = False
        #-- self.widget and self.label - to be set by self.create()

        self.create_widget()

        self.set_tooltip(trait.ui_hint.tip())
        if self.is_read_only():
            self.set_read_only(True)

        entity = self.trait_editor.entity
        sh = entity.get_style_sheet(trait)
        self.style_sheet_class().update(self.widget(), sh)

        if create_ui_node:
            self.create_ui_node()

        self.set_widget_value(entity.get_value(trait))

    def is_read_only(self) -> bool:
        return self.trait.is_read_only() or self.trait_editor.is_read_only()

    def widget_value(self):
        return self.value()

    def set_widget_value(self, value) -> bool:
        self.program_edit = True
        try:
            self.set_value(value)
        except Exception:       #-- the real widget is gone (so far, has encountered this only in Qt on Mac OS)
            self.clean()
            return False

        sh = self.trait_editor.entity.get_style_sheet(self.trait)
        self.style_sheet_class().update(self.widget(), sh)
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

            tip = rc.error() if not rc else trait.ui_hint.tip
            self.widget.set_tool_tip(tip)
            self.widget.set_style_sheet(f'background-color: {self.s_bg_colors[bool(rc)]}')

    def refresh(self, ui_node):
        editor = self.trait_editor
        trait = self.trait
        if not editor or not trait:     #-- the widget could be gone
            return

        value = editor.entity.get_value(trait) #-- no dep (yet) (?)
        self.relink_nodes(ui_node)
        self.set_widget_value(value)

    def create(self):
        ...

    @classmethod
    @abc.abstractmethod
    def ui_node_class(cls): ...

    @classmethod
    @abc.abstractmethod
    def style_sheet_class(cls):  ...

    @abc.abstractmethod
    def create_widget(self):    ...

    @abc.abstractmethod
    def value(self):    ...

    @abc.abstractmethod
    def set_value(self, value):  ...


