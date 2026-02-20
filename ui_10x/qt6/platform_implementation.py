from __future__ import annotations
import sys
from typing import Callable, Any

from PyQt6.QtWidgets import QWidget, QLayout, QBoxLayout, QVBoxLayout, QHBoxLayout, QFormLayout, QApplication
from PyQt6.QtWidgets import QLabel, QCalendarWidget, QMessageBox, QGroupBox, QButtonGroup, QRadioButton
from PyQt6.QtWidgets import QListWidgetItem, QListWidget, QLineEdit, QPlainTextEdit, QTreeWidgetItem, QTreeWidget, QCheckBox, QComboBox
from PyQt6.QtWidgets import QFrame, QSplitter, QDialog, QScrollArea, QPushButton, QStyle, QSizePolicy, QStyleOptionHeader
from PyQt6.QtWidgets import QHeaderView, QTableView
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QBuffer, QIODevice, QPoint, QModelIndex    #, QByteArray
from PyQt6.QtGui import QColor, QGuiApplication, QPixmap, QMouseEvent, QFontMetrics, QPalette, QPainter
from PyQt6.QtGui import QStandardItemModel, QStandardItem

import platform

from core_10x.global_cache import cache

def missing_attr(self, item):
    t = item.title()
    item = t[0].lower() + t[1:].replace('_', '')
    return QObject.__getattribute__(self, item)

Object = QObject

QueuedConnection                = Qt.ConnectionType.QueuedConnection
AutoConnection                  = Qt.ConnectionType.AutoConnection
DirectConnection                = Qt.ConnectionType.DirectConnection
UniqueConnection                = Qt.ConnectionType.UniqueConnection
BlockingQueuedConnection        = Qt.ConnectionType.BlockingQueuedConnection

signal_decl = pyqtSignal

MouseEvent                      = QMouseEvent
MouseEvent.is_left_button       = lambda self: self.button() == Qt.MouseButton.LeftButton
MouseEvent.is_right_button      = lambda self: self.button() == Qt.MouseButton.RightButton

Point                           = QPoint

SizePolicy                      = QSizePolicy
SizePolicy.MINIMUM_EXPANDING    = QSizePolicy.Policy.MinimumExpanding
SizePolicy.PREFERRED            = QSizePolicy.Policy.Preferred

StandardItemModel               = QStandardItemModel
StandardItemModel.__getattr__   = missing_attr

StandardItem                    = QStandardItem
ModelIndex                      = QModelIndex

HeaderView                      = QHeaderView
HeaderView.section_resized_connect  = lambda self, bound_method: self.sectionResized.connect(bound_method)

Color                           = QColor

FontMetrics                     = QFontMetrics
FontMetrics.__getattr__         = missing_attr

Widget                          = QWidget
Widget.__getattr__              = missing_attr

Horizontal                      = Qt.Orientation.Horizontal
Vertical                        = Qt.Orientation.Vertical

Layout                          = QLayout

BoxLayout                       = QBoxLayout
BoxLayout.__getattr__           = missing_attr

HBoxLayout                      = QHBoxLayout
VBoxLayout                      = QVBoxLayout

FormLayout                      = QFormLayout
FormLayout.__getattr__          = missing_attr

Label                           = QLabel
Label.set_text                  = QLabel.setText

Splitter                        = QSplitter

Style                           = QStyle
Style.State_Active              = QStyle.StateFlag.State_Active

Style.__getattr__               = missing_attr

PushButton                      = QPushButton
PushButton.clicked_connect      = lambda self, bound_method:    self.clicked.connect(bound_method)

LineEdit                        = QLineEdit
LineEdit.text_edited_connect    = lambda self, bound_method:    self.textEdited.connect(bound_method)
LineEdit.editing_finished_connect = lambda self, bound_method:  self.editingFinished.connect(bound_method)
LineEdit.set_password_mode      = lambda self:                  self.setEchoMode(QLineEdit.EchoMode.Password)

TextEdit                        = QPlainTextEdit

CheckBox                        = QCheckBox
CheckBox.state_changed_connect  = lambda self, bound_method:    self.stateChanged.connect(bound_method)

ComboBox                        = QComboBox

GroupBox                        = QGroupBox

RadioButton                     = QRadioButton

ButtonGroup                     = QButtonGroup
ButtonGroup.__getattr__         = missing_attr

ListItem                        = QListWidgetItem
ListItem.__getattr__            = missing_attr

MatchExactly                    = Qt.MatchFlag.MatchExactly

ListWidget                      = QListWidget
ListWidget.clicked_connect      = lambda self, bound_method:    self.clicked.connect(bound_method)

TreeItem                        = QTreeWidgetItem
TreeItem.__getattr__            = missing_attr

TreeWidget                      = QTreeWidget
TreeWidget.item_clicked_connect = lambda self, bound_method:    self.itemClicked.connect(bound_method)
TreeWidget.item_expanded_connect = lambda self, bound_method:   self.itemExpanded.connect(bound_method)
TreeWidget.item_pressed_connect = lambda self, bound_method:    self.itemPressed.connect(bound_method)
TreeWidget.item_changed_connect = lambda self, bound_method:    self.itemChanged.connect(bound_method)

CalendarWidget                  = QCalendarWidget
CalendarWidget.selected_date    = lambda self:                  self.selectedDate().toPyDate()

class Dialog(QDialog):
    s_open_dialogs = set()
    def __init__(self,parent=None,*args,**kwargs):
        super().__init__(parent or init().activeModalWidget(),*args,**kwargs)

    def _on_finished(self):
        open_dialogs = self.s_open_dialogs
        in_open_dialogs = self in open_dialogs
        print(f'finishing {self}: {in_open_dialogs}')

        if in_open_dialogs:
            self.s_open_dialogs.remove(self)

    def show(self):
        print(f'showing {self}')
        self.s_open_dialogs.add(self)
        self.finished.connect(self._on_finished)
        super().show()
        self.raise_()
        self.activateWindow()
        self.s_open_dialogs.add(self)


class MessageBox(QMessageBox):
    s_boxes_by_parent = {}
    def __init__(self, on_close: Callable[[Any],None] = None, parent: Widget = None):
        super().__init__(parent)
        self._on_close = on_close
        self.finished.connect(self._handle_finished)

        # Set the default values for the message box
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint|Qt.WindowType.WindowStaysOnTopHint)
        self.setStandardButtons(QMessageBox.StandardButton.Ok)
        self.setDefaultButton(QMessageBox.StandardButton.Ok)
        self.setEscapeButton(QMessageBox.StandardButton.Ok)

        self.setModal(True)
        self.s_boxes_by_parent[self.parent()] = self

    def _handle_finished(self, result):
        if self._on_close:
            self._on_close(result)
        self.s_boxes_by_parent.pop(self.parent())
        self.deleteLater()

    @classmethod
    def _create_message_box(cls, parent: Widget, title, message, on_close: Callable[[Any],None], icon) -> MessageBox:
        msg_box = cls(on_close,parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)
        return msg_box

    @classmethod
    def question(cls, parent: Widget, title: str, message: str, on_close: Callable[[Any],None]) -> MessageBox.StandardButton:
        msg_box = cls._create_message_box(
            parent=parent,
            title=title,
            message=message,
            on_close=on_close,
            icon=QMessageBox.Icon.Question,
        )

        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setEscapeButton(QMessageBox.StandardButton.No)

        if on_close:
            msg_box.show()
        else:
            return msg_box.exec()

    @classmethod
    def warning(cls, parent: Widget, title: str, message: str, on_close: Callable[[Any],None]) -> MessageBox.StandardButton:
        msg_box = cls._create_message_box(
                parent=parent,
                title=title,
                message=message,
                on_close=on_close,
                icon=QMessageBox.Icon.Warning,
          )

        if on_close:
            msg_box.show()
        else:
            return msg_box.exec()

    @classmethod
    def information(cls, parent: Widget, title: str, message: str, on_close: Callable[[Any],None]) -> MessageBox.StandardButton:
        msg_box = cls._create_message_box(
                parent=parent,
                title=title,
                message=message,
                on_close=on_close,
                icon=QMessageBox.Icon.Information,
          )

        if on_close:
            msg_box.show()
        else:
            return msg_box.exec()

    @classmethod
    def is_yes_button(cls, sb: QMessageBox.StandardButton) -> bool:
        return sb == QMessageBox.StandardButton.Yes


Application                     = QApplication

class TEXT_ALIGN:
    TOP       = Qt.AlignmentFlag.AlignTop
    V_CENTER  = Qt.AlignmentFlag.AlignVCenter
    BOTTOM    = Qt.AlignmentFlag.AlignBottom
    LEFT      = Qt.AlignmentFlag.AlignLeft
    CENTER    = Qt.AlignmentFlag.AlignCenter
    RIGHT     = Qt.AlignmentFlag.AlignRight

class SCROLL:
    OFF         = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    ON          = Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    AS_NEEDED   = Qt.ScrollBarPolicy.ScrollBarAsNeeded

ScrollArea                      = QScrollArea

ForegroundRole                  = Qt.ItemDataRole.ForegroundRole
BackroundRole                   = Qt.ItemDataRole.BackgroundRole

Palette                         = QPalette
Palette.ButtonText              = QPalette.ColorRole.ButtonText
Palette.Button                  = QPalette.ColorRole.Button
Palette.Window                  = QPalette.ColorRole.Window

StyleOptionHeader               = QStyleOptionHeader
Separator                       = QLabel

@cache
def init(style = '') -> QApplication:
    if not style:
        style = platform.system()

    app = QApplication([])
    app.setStyle(style)

    if sys.platform == 'darwin':
        from ui_10x.qt6.mac_os_global_commit_filter import MacEditCommitFilter
        MacEditCommitFilter.install(app)

    return app

def to_clipboard(text: str, **kwargs):
    cp = QGuiApplication.clipboard()
    cp.setText(text)

def from_clipboard(**kwargs) -> str:
    cp = QGuiApplication.clipboard()
    return cp.text()

def separator(horizontal = True) -> Separator:
    direction = QFrame.Shape.HLine if horizontal else QFrame.Shape.VLine
    sep = QLabel()
    sep.setFrameStyle(direction | QFrame.Shadow.Sunken)
    return sep

def is_ui_thread() -> bool:
    return QThread.currentThread() is QGuiApplication.instance().thread()


