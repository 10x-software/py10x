from datetime import date
import inspect
from collections import deque

from ui_10x.platform import ux

from core_10x.named_constant import NamedConstant
from core_10x.global_cache import cache, singleton
from core_10x.directory import Directory

class UxAsync(ux.Object):
    SIGNAL = ux.signal_decl()
    s_instances = {}

    @classmethod
    def init(cls, bound_method):
        instance = cls.s_instances.get(bound_method)
        if not instance:
            if not ux.is_ui_thread():
                raise RuntimeError(f'You must have called UxAsync.init({bound_method.__name__}) in the UI thread')

            instance = cls()
            cls.s_instances[bound_method] = instance

            instance.SIGNAL.connect(bound_method)

        return instance

    @classmethod
    def call(cls, bound_method):
        instance = cls.init(bound_method)
        instance.SIGNAL.emit()


class UxRadioBox(ux.GroupBox):
    def __init__(self, named_constant_class, title = '', horizontal = False, default_value: NamedConstant = None):
        assert inspect.isclass(named_constant_class) and issubclass(named_constant_class, NamedConstant), 'subclass of NamedConstant is expected'

        self.nm_class = named_constant_class
        self.values = values = list(named_constant_class.s_dir.values())

        if default_value is None:
            default = 0
        else:
            assert isinstance(default_value, named_constant_class), f'{named_constant_class} - unknown default_values = {default_value}'
            for i, c_def in enumerate(values):
                if c_def is default_value:
                    default = i
                    break
            else:
                assert False, f'{default_value} is not found'

        if title:
            super().__init__(title)
        else:
            super().__init__()


        lay = ux.HBoxLayout() if horizontal else ux.VBoxLayout()
        self.set_layout(lay)

        self.group = group = ux.ButtonGroup()
        for i, c_def in enumerate(named_constant_class.s_dir.values()):
            rb = ux.RadioButton(c_def.label)
            lay.add_widget(rb)
            group.add_button(rb, id = i)
        group.button(default).set_checked(True)

    def choice(self):
        i = self.group.checked_id()
        return self.values[i]

def ux_success(text: str, parent = None, title = ''):
    if not title:
        title = 'Success'
    if not parent:
        parent = None
    ux.MessageBox.information(parent, title, text)

def ux_warning(text: str, parent = None, title = ''):
    if not title:
        title = 'Warning'
    if not parent:
        parent = None
    ux.MessageBox.warning(parent, title, text)

def ux_answer(question: str, parent = None, title = '') -> bool:
    if not title:
        title = 'Waiting for your answer...'
    if not parent:
        parent = None
    sb = ux.MessageBox.question(parent, title, question)
    return ux.MessageBox.is_yes_button(sb)

def ux_multi_choice_answer(named_constant_class, parent = None, title = '', default_value: NamedConstant = None):
    if not title:
        title = 'Pick one of the choices below:'

    if not parent:
        parent = None

    box = UxRadioBox(named_constant_class, default_value = default_value)
    d = UxDialog(box, parent = parent, title = title, cancel = '')
    d.exec()
    return box.choice()

def ux_push_button(label: str, callback = None, style_icon = None, flat = False):
    if style_icon:
        if isinstance(style_icon, str):
            try:
                style_icon = getattr(ux.Style.StandardPixmap, f'SP_{style_icon}')
            except AttributeError:
                assert False, f"Unknown style_icon = '{style_icon}'"

        assert isinstance(style_icon, int), 'Currently only str or int are supported for style_icon'

        style = ux.Application.style()
        icon = style.standard_icon(style_icon)
        button = ux.PushButton(icon, label)
    else:
        button = ux.PushButton(label)

    if callback:
        button.clicked_connect(callback)

    if flat:
        button.set_flat(True)

    return button

class UxDialog(ux.Dialog):
    def _createButton(self, ok: bool, button_spec) -> ux.PushButton:
        if not button_spec:
            return None

        if isinstance(button_spec, str):
            label = button_spec
            icon = ''

        elif isinstance(button_spec, tuple):
            try:
                label, icon = button_spec
            except Exception:
                return None

        else:
            return None

        cb = self.onOk if ok else self.onCancel
        return ux_push_button(label, callback = cb, style_icon = icon)

    def __init__(
            self,
            w: ux.Widget,
            parent: ux.Widget   = None,
            title: str          = None,
            ok                  = 'Ok',
            cancel              = 'Cancel',
            accept_callback     = None,
            cancel_callback     = None,
            min_width           = 0,
            min_height          = 0,
            #window_flags        = None
    ):
        """
        :param w:               a Widget to show
        :param parent:          parent widget, if any
        :param title:           dialog title
        :param accept_callback: context.method, where: method( context ) -> RC
        :param ok, cancel:      labels and corresponding roles for Ok and Cancel buttons. No button if empty
        """
        super().__init__(parent)
        if title:
            self.set_window_title( title )

        # if window_flags is None:
        #     window_flags = Qt.WindowType.CustomizeWindowHint | Qt.WindowType.Window | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint

        ##self.setWindowFlags(window_flags)
        self.accept_callback = accept_callback
        self.cancel_callback = cancel_callback if cancel_callback else self.reject

        if ok:
            ok = self._createButton(True, ok)
        if cancel:
            cancel = self._createButton(False, cancel)

        lay = ux.VBoxLayout()
        self.set_layout(lay)

        lay.add_widget(w)

        self.w_message = ux.Label()
        self.w_message.set_style_sheet('color: red;')
        lay.add_widget(self.w_message)

        if ok or cancel:
            lay.add_widget(ux.separator())

            bar = ux.HBoxLayout()
            lay.add_layout(bar)

            bar.add_widget(ux.Label(), stretch = 1)
            if ok:
                bar.add_widget(ok)
            if cancel:
                bar.add_widget(cancel)

        if min_width > 0:
            self.set_minimum_width(min_width)
        if min_height > 0:
            self.set_minimum_height(min_height)

    def onOk(self):
        if self.accept_callback:
            rc = self.accept_callback()
            if not rc:
                self.message(rc.err())
                return

        self.done(1)

    def onCancel(self):
        self.reject()
        self.done(0)

    def message(self, text: str):
        self.w_message.set_text(text)

def ux_pick_date(title = 'Pick a Date', show_date: date = None, grid = True, default = None):
    cal = ux.CalendarWidget()
    cal.set_grid_visible(bool(grid))
    if show_date:
        cal.set_selected_date(show_date)
    dlg = UxDialog(cal, title = title)
    rc = dlg.exec()

    return cal.selected_date() if rc else default

class UxStyleSheet:
    def __init__(self, widget):
        self.widget = widget
        sh = widget.style_sheet()
        self.data = self.loads(sh)
        self.replacement_stack = deque()

    def set(self):
        self.widget.set_style_sheet(self.dumps(self.data))

    def update(self, named_sheet_attrs: dict, _system = False):
        if not named_sheet_attrs:
            return

        data = self.data
        if not any(value != data.get(name) for name, value in named_sheet_attrs.items()):   #-- no attribute values changed, nothing to do!
            return

        if _system:
            old_data = { name: data.get(name) for name in named_sheet_attrs.keys() }
            self.replacement_stack.append(old_data)

        data.update(named_sheet_attrs)
        self.set()

    def restore(self):
        if self.replacement_stack:
            old_data = self.replacement_stack.pop()
            data = self.data
            for name, value in old_data.items():
                if value is None:
                    data.pop(name, None)
                else:
                    data[name] = value

            self.set()

    @classmethod
    def dumps(cls, data: dict) -> str:
        return '\n'.join(f'{name}: {value};' for name, value in data.items())

    @classmethod
    def loads(cls, sheet: str) -> dict:
        res = {}
        pairs = sheet.split(';')
        for pair in pairs:
            pair = pair.strip()
            if pair:
                name_value = pair.split(':')
                if len(name_value) == 2:
                    name = name_value[0].strip()
                    value = name_value[1].strip()
                    res[name] = value

        return res

    @classmethod
    def modify(cls, widget, named_sheet_attrs: dict):
        if not named_sheet_attrs:
            return

        sh = widget.style_sheet()
        data = cls.loads(sh)
        data.update(named_sheet_attrs)
        widget.set_style_sheet(cls.dumps(data))


s_verticalAlignmentMap = {
    -1:     ux.TEXT_ALIGN.TOP,
    0:      ux.TEXT_ALIGN.V_CENTER,
    1:      ux.TEXT_ALIGN.BOTTOM,
}
s_horizontalAlignmentMap = {
    -1:     ux.TEXT_ALIGN.LEFT,
    0:      ux.TEXT_ALIGN.CENTER,
    1:      ux.TEXT_ALIGN.RIGHT,
}
def ux_text_alignment(align_value: int, horizontal = True) -> int:
    if horizontal:
        return s_horizontalAlignmentMap.get(align_value, ux.TEXT_ALIGN.RIGHT) | ux.TEXT_ALIGN.V_CENTER

    raise NotImplementedError

def ux_make_scrollable(w: ux.Widget, h = ux.SCROLL.AS_NEEDED, v = ux.SCROLL.AS_NEEDED) -> ux.Widget:
    if h == ux.SCROLL.OFF and v == ux.SCROLL.OFF:
        return w

    sa = ux.ScrollArea()
    sa.set_widget(w)
    sa.set_horizontal_scroll_bar_policy(h)
    sa.set_vertical_scroll_bar_policy(v)
    return sa

class UxSearchableList(ux.GroupBox):
    def __init__(
        self,
        text_widget: ux.LineEdit = None,
        reset_selection = True,
        choices: list   = None,
        select_hook     = None,
        sort            = False,
        case_sensitive  = False,
        title           = ''
    ):
        """
        :param text_widget: if an external text_widget given, it is used, otherwise its own is created on top of the list
        :param reset_selection: if True, text_widget will be reset on new selection
        :param choices: all choices
        :param select_hook: if given, will be called after a new selection is made: select_hook( selected_choice: str )
        :param sort: sort choices if True
        :param case_sensitive: whether to search with case sensitivity
        :param title: an optional title
        """
        super().__init__()
        self.sort = sort
        self.initial_choices = choices if not sort else sorted(choices)
        self.current_choices = self.initial_choices
        self.hook = select_hook
        self.reset_selection = reset_selection
        self.case_sensitive = case_sensitive
        self.choice = None

        if title:
            self.set_title(title)
        lay = ux.VBoxLayout()

        if text_widget:
            self.w_field = text_widget
        else:
            self.w_field = ux.LineEdit()
            lay.add_widget(self.w_field)
        self.w_field.text_edited_connect(self.process_input)

        self.w_list = ux.ListWidget()

        self.w_list.add_items(self.initial_choices)
        self.w_list.clicked_connect(self.item_selected)
        lay.add_widget(self.w_list)

        self.set_layout(lay)

    def add_choice(self, choice: str):
        if not choice in self.initial_choices:
            self.initial_choices.append(choice)
            if self.sort:
                self.initial_choices = sorted(self.initial_choices)

            self.w_list.clear()
            self.w_list.add_items(self.initial_choices)

    def remove_choice(self, choice: str):
        if choice in self.initial_choices:
            self.initial_choices.remove(choice)
            self.w_list.clear()
            self.w_list.add_items(self.initial_choices)

    def process_input(self, input):
        self.w_list.clear()
        if not input:
            self.current_choices = self.initial_choices
        else:
            if not self.current_choices:
                self.current_choices = self.initial_choices

            if not self.case_sensitive:
                input = input.lower()
                self.current_choices = [s for s in self.current_choices if not s.lower().find(input) == -1]
            else:
                self.current_choices = [s for s in self.current_choices if not s.find(input) == -1]

        self.w_list.add_items(self.current_choices)

    def item_selected(self, item: ux.ListItem):
        i = item.row()
        text = self.current_choices[i]
        self.reset()

        items = self.w_list.find_items(text, ux.MatchExactly)
        if len(items):
            items[0].set_selected(True)
            text_s = '' if self.reset_selection else text
            self.w_field.set_text(text_s)

        self.choice = text
        if self.hook:
            self.hook(text)

    def choice(self) -> str:
        return self.choice

    def reset(self):
        if not self.current_choices == self.initial_choices:
            self.current_choices = self.initial_choices
            self.w_list.clear()
            self.w_list.add_items( self.initial_choices)

class UxTreeViewer(ux.TreeWidget):
    s_label_max_length  = 40

    def __init__(self, dir: Directory, select_hook = None, label_max_length = -1, expand = False, **kwargs):
        super().__init__()
        if label_max_length < 0:
            label_max_length = self.s_label_max_length

        self.dir = dir
        self.select_hook = select_hook

        dir_value = dir.value
        dir_name = dir.name
        if dir_value and dir_name and dir_name != dir_value:
            num_cols = 2
            header_labels = [dir_name, 'Description']
        else:
            num_cols = 1
            header_labels = [dir.show_value()]

        self.num_cols = num_cols
        self.set_column_count(num_cols)
        self.set_header_labels(header_labels)
        self.item_clicked_connect(self.tree_item_clicked)

        for subdir in dir.members.values():     #-- without the root!
            self.create_tree(subdir, self, label_max_length, num_cols)

        if expand:
            for i in range(self.top_level_item_count()):
                top = self.top_level_item(i)
                top.set_expanded(True)

        self.resize_column_to_contents(0)
        if num_cols == 2:
            self.resize_column_to_contents(1)
        self.set_size_policy(ux.SizePolicy.MinimumExpanding, ux.SizePolicy.MinimumExpanding)

    class TreeItem(ux.TreeItem):
        def __init__(self, parent_node, dir: Directory):
            super().__init__(parent_node)
            self.dir = dir

    @classmethod
    def create_tree(cls, dir: Directory, parent_node, label_max_length: int, num_cols: int):
        node = cls.TreeItem(parent_node, dir)
        show_value = dir.show_value()
        node.set_text(0, show_value)
        if num_cols == 2:
            label = dir.name
            if label and label != show_value:
                if len(label) > label_max_length:
                    label = label[ :label_max_length ] + '...'

                node.set_text(1, label)

        node.set_tool_tip(num_cols-1, dir.name)

        for subdir in dir.members.values():
            cls.create_tree(subdir, node, label_max_length, num_cols)

    def tree_item_clicked(self, item: TreeItem):
        self.on_tag_selected(item.dir)

    def on_tag_selected(self, dir: Directory):
        if self.select_hook:
            self.select_hook(dir)

# class UxPixmap:
#     COLOR_AUTO      = Qt.ColorScheme.AutoColor
#     COLOR_DITHER    = Qt.ColorScheme.ColorOnly
#     COLOR_MONO      = Qt.ColorScheme.MonoOnly
#     RATIO_IGNORE    = Qt.ColorScheme.IgnoreAspectRatio
#     RATIO_KEEP      = Qt.ColorScheme.KeepAspectRatio
#     RATIO_KEEP_EXP  = Qt.ColorScheme.KeepAspectRatioByExpanding
#
#     s_sourceTypeMap = {
#         str:        QPixmap.load,
#         bytes:      QPixmap.loadFromData,
#         bytearray:  QPixmap.loadFromData,
#     }
#     def __init__( self, source = None, image_format = '', color_flags = COLOR_AUTO ):
#         self.m_pixmap = QPixmap()
#         rc = self.load( source, image_format = image_format, color_flags = color_flags )
#         if not rc:
#             raise RuntimeError( rc.err() )
#
#     def load( self, source, image_format = '', color_flags = COLOR_AUTO ) -> RC:
#         if not source:
#             return RC( True )
#
#         method = self.s_sourceTypeMap.get( type( source ) )
#         if not method:
#             return RC( False, f'UxPixmap - unknown type of source = {type( source )}' )
#
#         rc = method( self.m_pixmap, source, format = image_format, flags = color_flags )
#         if not rc:
#             return RC( False, f'UxPixmap - failed to initialize from source = {source}' )
#
#         return RC( True )
#
#     def _toData( self, array: bytearray, format = '', quality = -1 ) -> bool:
#         buffer = QBuffer( array )
#         buffer.open( QIODevice.WriteOnly )
#         return self.m_pixmap.save( buffer, format = format, quality = quality )
#
#     s_destinationTypeMap = {
#         str:        QPixmap.save,
#         bytearray:  _toData,
#     }
#     def save( self, destination, color_format = '', quality = -1 ) -> RC:
#         method = self.s_destinationTypeMap.get( type( destination ) )
#         if not method:
#             return RC( False, f'UxPixmap - unknown destination type = {type( destination )}' )
#
#         rc = method( self, destination, format = color_format, quality = quality )
#         if not rc:
#             return RC( False, f'UxPixmap - failed to save to destination = {destination}' )
#
#         return RC( True )
#
#     def render( self, label: QLabel, w = 0, h = 0, scaled = RATIO_IGNORE, smooth = True ):
#         transform_mode = Qt.SmoothTransformation if smooth else Qt.FastTransformation
#         pixmap = self.m_pixmap
#         if w > 0 and h > 0:
#             pixmap = pixmap.scaled( w, h, aspectRatioMode = scaled, transformMode = transform_mode )
#         label.setPixmap( pixmap )

@singleton
class UxClipBoard:
    def __init__(self):
        self.dir = {}
        self.entity = None
        self.trait_name = ''

    # def copy(self, tag: str, value):
    #     self.dir[tag] = value
    #
    # def paste(self, tag: str):
    #     return self.dir.get(tag)
    #
    # def clear(self):
    #     self.dir = {}
    #
    # def default_tag( self ) -> str:
    #     assert self.entity and self.trait_name, 'entity and trait name are not defined'
    #
    #     cls = self.entity.__class__
    #     trait = cls.trait(self.trait_name)
    #     assert trait, f"{cls}: unknown trait '{self.trait_name}'"
    #     #tag_label = trait.label if trait.label else self.trait_name
    #     tag_label = self.trait_name
    #     return f"{self.entity}: '{tag_label}'"
    #
    # def layout(self) -> QWidget:
    #     w = QWidget()
    #     lay = QVBoxLayout()
    #     w.setLayout(lay)
    #
    #     add_row = QHBoxLayout()
    #     add_b = uxPushButton('Add', callback = self.onCopy)
    #     self.m_addNameWidget = add_name = QLineEdit()
    #     add_name.setText(self.default_tag())
    #     add_row.addWidget(add_b)
    #     add_row.addWidget(add_name)
    #     lay.addLayout(add_row)
    #
    #     lay.addWidget(uxSeparator())
    #
    #     self.m_sl = sl = UxSearchableList(choices = list( self.dir.keys() ), select_hook = self.onPaste, title = 'Use Data')
    #     lay.addWidget(sl)
    #
    #     return w
    #
    # def popup(self, parent_widget: QWidget, entity, trait_name: str):
    #     self.m_parent = parent_widget
    #     self.entity = entity
    #     self.trait_name = trait_name
    #     self.m_d = d = UxDialog(self.layout(), parent = parent_widget, cancel = '', title = 'Copy or Paste Data')
    #     d.exec()
    #
    # def onCopy(self):
    #     name = self.m_addNameWidget.text()
    #     if name:
    #         value = self.entity.get_value( self.trait_name )
    #         if value is not None:
    #             self.copy( name, value )
    #
    #     self.m_d.close()
    #
    # def onPaste( self, name: str ):
    #     value = self.paste( name )
    #     if value is not None:
    #         rc = self.m_entity.setValue( self.m_traitName, value )
    #         if not rc:
    #             uxWarning(
    #                 f"Data '{name}' is not suitable for '{self.m_entity.trait( self.m_traitName ).m_label}'",
    #                 parent = self.m_parent,
    #                 title = 'Invalid Data'
    #             )
    #
    #     self.m_d.close()


