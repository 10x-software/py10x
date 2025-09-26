import inspect

from core_10x.traitable import Trait, Traitable
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, QVariant
from PyQt5.QtWidgets import QAbstractScrollArea, QTableView

from ui_10x.table_header_view import HeaderModel, HeaderView
from ui_10x.traitable_editor import TraitableEditor
from ui_10x.traitable_view import TraitableView
from ui_10x.utils import UxStyleSheet, ux_text_alignment


# ruff: noqa: N802 # Function name should be lowercase
class Model(QAbstractTableModel):
    def __init__(self, model: HeaderModel, data, parent = None):
        super().__init__(parent = parent)
        self.model = model
        self.data = data
        self.col2name = { i: name for i, name in enumerate( model.traits ) }
        self.name2col = { name: i for i, name in self.col2name.items() }

    def trait_name(self, col: int) -> str:
        return self.col2name.get(col)

    def rowCount(self, parent = None, *args, **kwargs):
        return len(self.data)

    def columnCount( self, parent = None, *args, **kwargs ):
        if not self.data:
            return 0
        return len(self.col2name)

    def data(self, index: QModelIndex, role: int = None):
        if role == Qt.UserRole:
            return self.model

        entity: Traitable = self.data[index.row()]
        trait_name = self.col2name.get(index.column())

        cls = entity.__class__
        trait: Trait = cls.trait(trait_name)
        if role == Qt.DisplayRole and index.isValid():
            if trait:
                value = entity.get_value(trait)
                text = trait.to_str(value)
            else:
                text = ''
            return text

        if role == Qt.ForegroundRole:
            sh = entity.get_style_sheet(trait)
            return UxStyleSheet.fg_color(sh)

        if role == Qt.BackgroundRole:
            sh = entity.get_style_sheet(trait)
            return UxStyleSheet.bg_color(sh)

        if role == Qt.TextAlignmentRole:
            return ux_text_alignment(trait.ui_hint.param('align_h', 0), horizontal = True)

        return QVariant()

    def set_data(self, i: QModelIndex, dummy, role = None) -> bool:
        self.dataChanged.emit(i, i)
        return True

    def change_data(self, row: int, trait_name: str):
        col = self.name2col.get(trait_name)
        i = QModelIndex(row, col)
        self.set_data(i, None, role = None)

    def insertRows(self, row: int, num_rows: int, parent = None, *args, **kwargs) -> bool:
        #self.beginInsertRows( QModelIndex(), row, row + num_rows )
        return True

    def extendData(self, data) -> bool:
        """
        :param data: an iterable of entities
        :return: True if model reset happened as well
        """
        if data:
            the_data = self.data
            is_empty = not bool(the_data)
            if is_empty:
                self.beginResetModel()

            first = len(the_data)
            last = first + len(data) - 1
            self.beginInsertRows(QModelIndex(), first, last)
            the_data.extend(data)
            self.insertRows(first, len( data))
            self.endInsertRows()

            if is_empty:
                self.endResetModel()
            return is_empty

    def entity(self, row: int) -> Traitable:
        return self.data[row]

class TableView(QTableView):
    def __init__(self, entities_or_class, view: TraitableView = None):
        assert entities_or_class, 'first arg must not be empty'

        if inspect.isclass(entities_or_class):
            assert issubclass(entities_or_class, Traitable), 'first arg is a class, but not a subclass of Traitable'
            proto = entities_or_class
            entities = []
        else:
            entities = entities_or_class
            proto = entities[0]

        if not view:
            view = TraitableView.default(proto)

        super().__init__()
        self.wheel_enabled = True

        hv = HeaderView(view, parent = self)
        hv.setStretchLastSection(True)

        self.setHorizontalHeader(hv)
        model = Model(hv.model(), entities, self)
        self.setModel(model)

        self.setAlternatingRowColors(True)
        self.resizeColumnsToContents()

        self.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)

    def wheelEvent(self, *args, **kwargs):
        if self.wheel_enabled:
            QTableView.wheelEvent(self, args[0])

    def keyPressEvent(self, *args, **kwargs):
        if self.wheel_enabled:
            QTableView.keyPressEvent(self, args[0])

    def mousePressEvent(self, *args, **kwargs):
        mouse_event = args[0]
        row = self.rowAt(mouse_event.y())
        col = self.columnAt(mouse_event.x())
        if row == -1 or col == -1:
            return

        entity = self.model().entity(row)
        trait_name = self.model().trait_name(col)
        if not trait_name:
            return

        editor_class = TraitableEditor.findEditorClass(entity.__class__)     #-- no alternative packages, look under ui subdir only
        mouse_btn = mouse_event.button()
        if mouse_btn == Qt.LeftButton:
            cb = editor_class.leftMouseCallback(trait_name)
        elif mouse_btn == Qt.RightButton:
            cb = editor_class.rightMouseCallback(trait_name)
        else:
            return

        if cb:
            cb(self, entity)
        else:
            super().mousePressEvent(*args, **kwargs)

    def render_entity(self, row: int, entity: Traitable):
        last_col = len(self.model().col2name) - 1
        first_index = self.model().create_index(row, 0)
        last_index = self.model().create_index(row, last_col)
        self.model().dataChanged.emit(first_index, last_index)

    def extendData( self, data ):
        if self.model().extendData(data):
            self.resizeColumnsToContents()
            #self.resizeRowsToContents()
