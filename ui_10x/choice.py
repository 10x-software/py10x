from core_10x.directory import Directory
from core_10x.xnone import XNone
from core_10x.named_constant import Enum

from ui_10x.utils import ux, UxSearchableList, UxTreeViewer, UxDialog, UxRadioBox


class Choice:
    """
    choices     - a dict of labels to tags values or Directory; if given, f_choices is ignored
    f_choices   - a fully bound function that must return choices (see above)

    Q1: do we want to allow setting tags_selected with tags outside of all_choices? If so, what about updating all_choices
        and potentially saving such Choice instance?
    """
    def __init__(self, choices = XNone, f_choices = None, f_selection_callback = None, **kwargs):
        self.choices: dict = XNone
        self.inverted_choices: dict = XNone
        self.f_choices = None
        self.f_selection_cb = None
        self.directory: Directory = None
        self.kwargs = {}

        self.values_selected = []

        self.set(choices = choices, f_choices = f_choices, f_selection_callback = f_selection_callback, **kwargs)

    def set(self, choices = XNone, f_choices = None, f_selection_callback = None, **kwargs):
        assert choices or f_choices, f'Either choices or f_choices must be given'

        self.f_selection_cb = f_selection_callback

        if (choices):
            self.f_choices = None
        else:
            self.f_choices = f_choices
            choices = f_choices()       #-- TODO: we may want to wrap it in try - except

        self.kwargs.update(kwargs)

        if isinstance(choices, Directory):
            self.directory = choices
            self.choices = choices.choices()

        elif isinstance(choices, dict):
            self.directory = None
            self.choices = choices

        else:   #-- must be an iterable then!
            self.directory = None
            try:
                self.choices = {hint: hint for hint in choices}
            except Exception:
                self.choices = {}

        self.inverted_choices = {value: label for label, value in self.choices.items()}

    def widget(self) -> ux.Widget:
        if self.directory:
            return UxTreeViewer(
                self.directory,
                select_hook = lambda dir: self.on_item_selected(dir, dir.value, False),
                **self.kwargs
            )

        return UxSearchableList(
            choices     = list(self.choices.keys()),
            select_hook = lambda item_value: self.on_item_selected(None, item_value, True),
            **self.kwargs
        )

    def on_item_selected(self, dir: Directory, item, convert_choice: bool):
        item_value = self.choices.get(item) if convert_choice else item
        if item_value is not None:
            self.on_value_selected(dir, item_value, convert_value = convert_choice)
            if self.f_selection_cb:
                self.f_selection_cb(item)

    def on_value_selected(self, dir: Directory, item_value, convert_value = False):
        self.values_selected = [item_value]

    def _on_selection_in_dialog(self, d: UxDialog, current_selection_cb, item_value):
        if current_selection_cb:
            current_selection_cb(item_value)
        d.done(1)
        self.f_selection_cb = current_selection_cb

    def popup(self, parent: ux.Widget = None, _open = True) -> UxDialog:
        _d = UxDialog(
            self.widget(),
            parent = parent,
            title = 'Pick your choice',
            ok = '', cancel = '',
            #window_flags = Qt.FramelessWindowHint | Qt.Window | Qt.CustomizeWindowHint
        )

        current_selection_cb = self.f_selection_cb
        self.f_selection_cb = lambda item_value: self._on_selection_in_dialog(_d, current_selection_cb, item_value)

        if _open:
            _d.show()

        return _d


class MultiChoice(Choice):
    class SELECT_MODE(Enum):
        ANY     = ()
        LEAF    = ()
        SUBDIR  = ()

    def __init__(self, *choices_selected, choices = XNone, f_choices = None, **kwargs):
        super().__init__(choices = choices, f_choices = f_choices, **kwargs)
        self._set_choices_selected(choices_selected)

    def set(self, *choices_selected, choices = XNone, f_choices = None, **kwargs):
        super().set(choices = choices, f_choices = f_choices, **kwargs)
        self._set_choices_selected(choices_selected)

    def _set_choices_selected(self, choices_selected: tuple):
        all_choices = self.choices
        self.values_selected.extend(tuple(value for choice in choices_selected if (value := all_choices.get(choice) )))

    def select_mode(self):
        return self.rb.choice() if self.rb else self.SELECT_MODE.ANY

    def widget(self) -> ux.Widget:
        self.sw = sw = super().widget()
        if not sw:
            return None

        w = ux.Splitter(ux.Horizontal)

        if isinstance(sw, UxTreeViewer):
            left = ux.Widget()
            left_lay = ux.VBoxLayout()
            left.set_layout(left_lay)

            self.rb = rb = UxRadioBox(self.SELECT_MODE, horizontal = True, title = 'Selection Mode')
            left_lay.add_widget(rb)
            left_lay.add_widget(sw)
        else:
            left = sw
            self.rb = None

        w.add_widget(left)

        self.selection_list = selection_list = ux.ListWidget()
        labels = self.values_selected
        if not self.directory:
            map = self.inverted_choices
            labels = [map.get(v) for v in labels if map.get(v)]

        selection_list.add_items(labels)
        selection_list.clicked_connect(self.on_selection_list_selection)
        w.add_widget(selection_list)

        return w

    def on_selection_list_selection(self, item: ux.ListItem):
        label = item.text()
        if not self.directory:
            value = self.choices.get(label)
        else:
            value = label

        assert value, f"Value for '{label}' must exist"

        self.values_selected.remove(value)
        row = self.selection_list.row(item)
        self.selection_list.take_item(row)

    def on_value_selected(self, subdir: Directory, item_value, convert_value = False):
        values_selected = self.values_selected
        if not item_value in values_selected:
            mode = self.select_mode()
            handler = self.s_select_table.get(mode)
            if handler(self, subdir, values_selected, item_value):
                values_selected.append(item_value)
                if convert_value:
                    item_value = self.inverted_choices.get( item_value )
                self.selection_list.add_item(item_value)

    def _select_leaf(self, subdir: Directory, values_selected: list, item_value) -> bool:
        return subdir.is_leaf()

    def _select_subdir(self, subdir: Directory, values_selected: list, item_value) -> bool:
        dir = self.directory
        assert dir, 'This is not a Directory'

        n = len(values_selected)
        for value in list(values_selected):
            if dir.is_value_contained(item_value, value):
                return False    #-- it's a subdir of something already selected

            if subdir.contains(value):
                values_selected.remove(value)

        if n > len(values_selected):    #-- one or more subdirs contained by the subdir got removed
            self.selection_list.clear()
            self.selection_list.add_items(values_selected)

        return True

    s_select_table = {
        SELECT_MODE.ANY:       lambda self, x,y,z: True,
        SELECT_MODE.LEAF:      _select_leaf,
        SELECT_MODE.SUBDIR:    _select_subdir
    }
