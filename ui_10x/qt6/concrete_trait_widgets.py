from core_10x.trait import Trait, T
from core_10x.ui_hint import UiHint

from ui_10x.utils import ux
from ui_10x.trait_widget import TraitWidget

class LineEditWidget(ux.LineEdit, hint = UiHint.WIDGET_TYPE.LINE):
    def create_widget(self):

        w = ux.LineEdit()

        w.text_edited_connect(self.on_editing)
        w.editing_finished_connect(self.on_editing_finished)

        if self.trait.ui_hint.flags_on(UiHint.SELECT_ONLY):
            w.set_read_only()

        self.was_edited = False
        return w

    def on_editing(self, text):
        self.was_edited = True

    def on_editing_finished(self):
        if self.was_edited:
            self.was_edited = False
            str_value = self.widget.text()
            if not str_value:   #-- user cleared the field, let's get the value back!
                self.update_trait_value(invalidate = True)
            else:
                self.update_trait_value(value = str_value, invalidate = False)

    def set_read_only(self):
        self.widget.set_read_only()