import abc

from core_10x import trait


class TraitWidget(abc.ABC):
    s_hinted_widgets = {}
    def __init_subclass__(cls, hint = None, **kwargs):
        if hint:
            TraitWidget.s_hinted_widgets[hint] = cls

    @staticmethod
    def widget_class(hint):
        return TraitWidget.s_hinted_widgets.get(hint)

    def __init__(self, trait_editor, trait, create_ui_node = True):
        self.trait_editor = trait_editor
        self.trait = trait
        self.program_edit = False
        #-- self.widget - to be set by self.create()

        self.create()

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

    def refresh(self, ui_node):
        editor = self.trait_editor
        trait = self.trait
        if not editor or not trait:     #-- the widget could be gone
            return

        value = editor.entity.get_value(trait) #-- no dep (yet) (?)
        self.relink_nodes(ui_node)
        self.set_widget_value(value)

    @abc.abstractmethod
    def create(self):   ...

    @abc.abstractmethod
    def set_tooltip(self, tip: str):    ...

    @abc.abstractmethod
    def set_read_only(self, flag: bool):    ...

    @classmethod
    @abc.abstractmethod
    def ui_node_class(cls): ...

    @classmethod
    @abc.abstractmethod
    def style_sheet_class(cls):  ...

    @abc.abstractmethod
    def widget(self):   ...

    @abc.abstractmethod
    def value(self):    ...

    @abc.abstractmethod
    def set_value(self, value):  ...


