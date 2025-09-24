from datetime import date, datetime

from core_10x.rc import RC, RC_TRUE
from core_10x.xnone import XNone

from ui_10x.utils import UxDialog, ux


class PyDataBrowser:
    class Item(ux.TreeItem):
        def __init__(self, parent_node, key, value):
            super().__init__(parent_node)
            self.key = key
            self.value = value
            self.new_value = value

        def path(self) -> list:
            res = []
            node = self
            while node:
                res.insert(0, node.key)
                node = node.parent()

            return res

        def accept_edit(self, results):
            n = self.child_count()
            if not n:
                if self.value != self.new_value:
                    path = self.path()
                    x = results
                    for key in path[:-1]:
                        x = x[key]
                    x[path[-1]] = self.new_value
            else:
                for i in range(n):
                    child = self.child(i)
                    child.accept_edit(results)

    def __init__(
            self,
            data,
            on_select = None,
            edit = False,
            custom_editor = None,
            max_label_len = 50,
            max_value_len = 70
    ):
        """
        Browse any python data.
        :param data:
        :param on_select: a callable on item selection. If given, will call on_select( the_browser, path_to_item: list, item_value )
        :param edit: allow editing if True
        :param custom_editor: if given, is used for editing - fn( the_browser, item: PyDataBrowser: Item )
        :param max_label_len: max label width (if exceeds, gets truncated showing '...' and the end)
        :param max_value_len: max value width (if exceeds, gets truncated showing '...' and the end)
        Tooltip (full label/value, if possible) is shown as usual
        """
        self.data = data
        self.edit = edit
        self.custom_editor = custom_editor
        self.select_cb = on_select
        self.max_label_len = max_label_len
        self.max_value_len = max_value_len

    def fill(self, value, node: ux.TreeItem, label = True):
        if label:
            i = 0
            n = self.max_label_len
            tip = True
        else:
            i = 1
            n = self.max_value_len
            tip = isinstance(value, str)
        text = str(value)
        if len(text) > n:
            show = text[: n] + '...'
        else:
            show = text
        node.set_text(i, show)
        if tip:
            node.set_tool_tip(i, text)

    s_bool_vmap = {
        'True':     True,
        'False':    False,
        '1':        True,
        '0':        False
    }

    s_use_as_is = {
        type:           None,
        type(None):     None,
        type(XNone):    None,
        bool:           lambda x:   PyDataBrowser.s_bool_vmap.get(x, bool(x)),
        str:            lambda x:   x,
        int:            lambda x:   int(x),
        float:          lambda x:   float(x),
        datetime:       lambda x:   datetime.strptime(x, '%Y-%m-%d %H:%M:%S'),
        date:           lambda x:   datetime.strptime(x, '%Y-%m-%d').date(),
    }

    s_dict_handler  = lambda data: data.items()
    s_list_handler  = lambda data: enumerate(data)
    s_type_handlers = {
        tuple:      s_list_handler,
        list:       s_list_handler,
        dict:       s_dict_handler,
    }
    def create_tree(self, key, item, parent_node):
        node = self.Item(parent_node, key, item)
        self.fill(key, node, label = True)
        self.fill(item, node, label = False)

        dtype = type(item)
        if dtype in self.s_use_as_is:
            pass
        else:
            handler = self.s_type_handlers.get(dtype)
            if not handler:
                try:
                    text = item.__repr__()
                    node.set_text(1, text)
                except Exception:
                    node.set_text(1, '???')
                    return

                try:
                    item = item.to_dict()
                    handler = self.__class__.s_dict_handler
                except Exception:
                    return

            for key, value in handler(item):
                self.create_tree(key, value, node)

    def widget(self) -> ux.TreeWidget:
        self.tree = tree = ux.TreeWidget()
        tree.set_column_count(2)
        tree.set_header_labels(['Key', 'Value'])

        data = self.data
        dtype = type(data)
        handler = self.s_type_handlers.get(dtype)
        if not handler:
            data = { str(dtype): data }
            handler = self.s_dict_handler

        for key, item in handler(data):
            self.create_tree(key, item, tree)

        if len(data) == 1:
            tree.top_level_item(0).set_expanded(True)

        tree.resize_column_to_contents(0)
        tree.resize_column_to_contents(1)

        tree.item_expanded_connect(lambda item: tree.resize_column_to_contents(0))
        tree.item_pressed_connect(self.on_item_pressed)
        tree.item_changed_connect(self.on_item_changed)

        return tree

    def on_item_pressed(self, item: Item, col: int):
        if item:
            if col == 0 or not self.edit:
                if self.select_cb:
                    self.select_cb(self, item.path(), item.value)
                return

            if self.custom_editor:
                self.custom_editor(self, item)
            else:
                if not item.child_count():
                    self.generic_editor(item)

    def on_item_changed(self, item: Item, col: int):
        if col != 1:
            return

        dtype = type(item.value)
        from_str_handler = self.s_use_as_is.get(dtype)
        if from_str_handler:
            text = item.text(col)
            try:
                item.new_value = from_str_handler(text)
            except Exception:
                pass

    def generic_editor(self, item: Item):
        self.tree.open_persistent_editor(item, 1)
        self.tree.edit_item(item, 1)

    def accept_edit(self) -> RC:
        for i in range(self.tree.top_level_item_count()):
            item = self.tree.top_level_item(i)
            item.accept_edit(self.data)
        return RC_TRUE

    @classmethod
    def show(cls, data, on_select = None, title = '', w = 1000, h = 800):
        if not title:
            title = 'Python Data Browser'

        br = cls(data, on_select = on_select)
        d = UxDialog(
            br.widget(),
            title       = title,
            ok          = '',
            cancel      = 'Close',
            min_width   = w,
            min_height  = h
        )
        d.exec()

    @classmethod
    def edit(cls, data, on_select = None, custom_editor = None, title = '', w = 1000, h = 800) -> bool:
        if not title:
            title = 'Python Data Editor'

        br = cls(data, on_select = on_select, edit = True, custom_editor = custom_editor)
        d = UxDialog(
            br.widget(),
            accept_callback = br.accept_edit,
            title           = title,
            min_width       = w,
            min_height      = h
        )
        rc = d.exec()
        return bool(rc)

    @classmethod
    def path_to_str(cls, path: list, delims = ('/', '/')) -> str:
        res = []
        for i, key in enumerate(path):
            delim = delims[ isinstance(key, int) ]
            n = len(delim)
            if n == 0:
                continue

            if n == 1:
                key = f'{delim}{key}' if i > 0 else str(key)
            else:
                key = f'{delim[0]}{key}{delim[1]}'

            res.append(key)

        return ''.join(res)

