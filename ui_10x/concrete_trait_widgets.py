from core_10x.trait import Trait, T, Ui
from core_10x.concrete_traits import list_trait

from ui_10x.utils import ux, UxClipBoard, ux_push_button
from ui_10x.choice import Choice
from ui_10x.trait_widget import TraitWidget

class LineEditWidget(TraitWidget, ux.LineEdit, widget_type = Ui.WIDGET_TYPE.LINE):
    def _create(self):
        ux.LineEdit.__init__(self)

        self.text_edited_connect(self.on_editing)
        self.editing_finished_connect(self.on_editing_finished)
        self.was_edited = False

    def on_editing(self, text):
        self.was_edited = True

    def on_editing_finished(self):
        if self.was_edited:
            self.was_edited = False
            str_value = self.text()
            if not str_value:   #-- user cleared the field, let's get the value back!
                self.update_trait_value(invalidate = True)
            else:
                ##value = self.trait.from_str(str_value)
                self.update_trait_value(value = str_value, invalidate = False)

    def mouse_press_event(self, event: ux.MouseEvent):
        if event.is_right_button():
            if not self.trait_editor.is_read_only():
                cb = UxClipBoard()
                cb.popup(self, self.entity, self.trait.name)
            else:
                ux.LineEdit.mouse_press_event(self, event)

    def _set_read_only(self, flag):
        self.set_read_only(flag)

    def _value(self):
        str_value = self.text()
        return self.trait.from_str(str_value)

    def _set_value(self, value):
        str_value = self.trait.to_str(value)
        self.set_text(str_value)

def create_text_widget(editor, trait: Trait):
    if isinstance(trait, list_trait):
        return TextEditForListWidget(editor, trait)

    return TextEditWidget(editor, trait)
TraitWidget.s_hinted_widgets[Ui.WIDGET_TYPE.TEXT] = create_text_widget

class TextEditWidget(TraitWidget, ux.TextEdit):
    def _create(self):
        ux.TextEdit.__init__(self)

    def focus_out_event(self, event):
        value = self._value()
        self.update_trait_value(value = value) if value else self.update_trait_value(invalidate = True)

    def _set_read_only(self, flag):
        self.set_readonly(flag)

    def _value(self):
        return self.to_plain_text()

    def _set_value(self, value):
        if not isinstance(value, str):
            value = ''
        self.set_plain_text(value)

class TextEditForListWidget(TextEditWidget):
    def _value(self) -> list:
        text = self.to_plain_text()
        return text.split('\n')

    def _set_value(self, value):
        if value:
            if not isinstance(value, list):
                raise AssertionError('list is expected')

            value = '\n'.join(value)
            self.set_plain_text(value)

class PasswordWidget(LineEditWidget, widget_type = Ui.WIDGET_TYPE.PASSWORD):
    def _create(self):
        super()._create()
        self.set_password_mode()
        self.set_text('')

class CheckBoxWidget(TraitWidget, ux.CheckBox, widget_type = Ui.WIDGET_TYPE.CHECK):
    def _create(self):
        ux.CheckBox.__init__(self)
        if self.trait.ui_hint.param('right_label', False):
            self.set_text(self.trait.ui_hint.label)

        self.state_changed_connect(self.on_state_changed)

    def on_state_changed(self, flag):
        self.update_trait_value(value = bool(flag))

    def _set_read_only(self, flag):
        self.set_enabled(flag)

    def _value(self):
        return bool(self.is_checked())

    def _set_value(self, value):
        self.set_checked(bool(value))

class ChoiceWidget(TraitWidget, ux.Widget, widget_type = Ui.WIDGET_TYPE.CHOICE):
    def _create(self):
        ux.Widget.__init__(self)

        lay = ux.HBoxLayout()
        lay.set_spacing(0)
        lay.set_contents_margins(0, 0, 0, 0)
        self.set_layout(lay)

        #-- Line edit
        self.line_edit = le = ux.LineEdit()
        if self.trait_editor.is_read_only():
            le.set_readonly(True)

        le.editing_finished_connect(self.on_editing_finished)
        lay.add_widget(le)

        #-- Arrow down button
        self.button = ux_push_button('', callback = self.show_popup, style_icon = 'ArrowDown')
        lay.add_widget(self.button)

        entity = self.trait_editor.entity
        trait = self.trait
        self.choice = Choice(f_choices = lambda: entity.get_choices(trait), f_selection_callback = lambda item: self.on_selection(item))

    def _value(self):
        selection = self.choice.values_selected
        return selection[0] if selection else None

    def _set_value(self, value):
        if not self.choice.directory:
            value = self.choice.inverted_choices.get(value)

        if not value:
            value = ''
        self.line_edit.set_text(value)

    def _set_read_only(self, flag):
        self.line_edit.set_read_only(flag)
        self.button.set_enabled(not flag)

    # def on_current_index_changed(self, index):
    #     self.update_trait_value()

    def show_popup(self):
        self.popup = d = self.choice.popup(parent = self, _open = False)
        w = self.width()
        h = self.height()
        xy = self.map_to_global(ux.Point(0, 0))

        d.set_modal(True)
        d.show()
        d.set_geometry(xy.x(), xy.y(), max(w, d.width()), h)

    def on_selection(self, item):
        self.line_edit.set_text(item)
        self.update_trait_value(value = self.choice.values_selected[0], invalidate = False)

    def on_editing_finished(self):
        str_value = self.line_edit.text()
        if not str_value:
            self.update_trait_value(invalidate = True)
        else:
            value = self.choice.choices.get(str_value, str_value)
            self.update_trait_value(value = value, invalidate = False)

class PixmapLabelWidget(TraitWidget, ux.Label, widget_type = Ui.WIDGET_TYPE.PIXMAP):
    def _create(self):
        ux.Label.__init__(self)
        #self.pixmap = UxPixmap()
    ...

class PushButtonWidget(TraitWidget, ux.PushButton, widget_type = Ui.WIDGET_TYPE.PUSH):
    def _create(self):
        ux.PushButton.__init__(self)
        self.set_text(self.trait.ui_hint.label)
    ...

    def _set_read_only(self, flag):
        pass

    def _value(self):
        pass

    def _set_value(self, value):
        if value is None:
            value = True
        self.set_enabled(value)
