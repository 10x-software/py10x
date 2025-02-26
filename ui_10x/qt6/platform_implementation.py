from PyQt6.QtWidgets import QWidget, QLayout, QBoxLayout, QVBoxLayout, QHBoxLayout, QFormLayout, QApplication
from PyQt6.QtWidgets import QLabel, QCalendarWidget, QMessageBox, QGroupBox, QButtonGroup, QRadioButton
from PyQt6.QtWidgets import QListWidgetItem, QListWidget, QLineEdit, QPlainTextEdit, QTreeWidgetItem, QTreeWidget, QCheckBox, QComboBox
from PyQt6.QtWidgets import QFrame, QSplitter, QDialog, QScrollArea, QPushButton, QStyle, QSizePolicy
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QBuffer, QIODevice, QPoint    #, QByteArray
from PyQt6.QtGui import QColor, QGuiApplication, QPixmap, QMouseEvent

import platform

def missing_attr(self, item):
    t = item.title()
    item = t[0].lower() + t[1:].replace('_', '')
    return QObject.__getattribute__(self, item)

Object = QObject

signal_decl = pyqtSignal

MouseEvent                      = QMouseEvent
MouseEvent.is_left_button       = lambda self: self.button() == Qt.MouseButton.LeftButton
MouseEvent.is_right_button      = lambda self: self.button() == Qt.MouseButton.RightButton

Point                           = QPoint

SizePolicy                      = QSizePolicy
SizePolicy.MinimumExpanding     = QSizePolicy.Policy.MinimumExpanding

Color                           = QColor

Widget                          = QWidget
Widget.__getattr__              = missing_attr

Layout                          = QLayout

BoxLayout                       = QBoxLayout
BoxLayout.__getattr__           = missing_attr

HBoxLayout                      = QHBoxLayout
VBoxLayout                      = QVBoxLayout

FormLayout                      = QFormLayout
FormLayout.add_row              = QFormLayout.addRow

Label                           = QLabel
Label.set_text                  = QLabel.setText

Style                           = QStyle

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

MatchExactly                    = Qt.MatchFlag.MatchExactly

ListWidget                      = QListWidget
ListWidget.clicked_connect      = lambda self, bound_method:    self.clicked.connect(bound_method)

TreeItem                        = QTreeWidgetItem

TreeWidget                      = QTreeWidget
TreeWidget.item_clicked_connect = lambda self, bound_method:    self.itemClicked.connect(bound_method)

CalendarWidget                  = QCalendarWidget
CalendarWidget.selected_date    = lambda self:                  self.selectedDate().toPyDate()

Dialog                          = QDialog
#Dialog.__getattr__              = missing_attr

MessageBox                      = QMessageBox
MessageBox.is_yes_button        = lambda sb:                    sb == QMessageBox.StandardButton.Yes

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

def init(style = '') -> QApplication:
    if not style:
        style = platform.system()

    app = QApplication([])
    app.setStyle(style)
    return app

def to_clipboard(text: str, **kwargs):
    cp = QGuiApplication.clipboard()
    cp.setText(text)

def from_clipboard(**kwargs) -> str:
    cp = QGuiApplication.clipboard()
    return cp.text()

def separator(horizontal = True) -> QLabel:
    direction = QFrame.Shape.HLine if horizontal else QFrame.Shape.VLine
    sep = QLabel()
    sep.setFrameStyle(direction | QFrame.Shadow.Sunken)
    return sep

def is_ui_thread() -> bool:
    return QThread.currentThread() is QGuiApplication.instance().thread()


