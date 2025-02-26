from PyQt6.QtWidgets import QWidget, QLayout, QBoxLayout, QVBoxLayout, QHBoxLayout, QFormLayout, QApplication
from PyQt6.QtWidgets import QLabel, QCalendarWidget, QMessageBox, QGroupBox, QButtonGroup, QRadioButton
from PyQt6.QtWidgets import QListWidgetItem, QListWidget, QLineEdit, QPlainTextEdit, QTreeWidgetItem, QTreeWidget, QCheckBox, QComboBox
from PyQt6.QtWidgets import QFrame, QSplitter, QDialog, QScrollArea, QPushButton, QStyle, QSizePolicy
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QBuffer, QIODevice, QPoint    #, QByteArray
from PyQt6.QtGui import QColor, QGuiApplication, QPixmap, QMouseEvent

import platform


Object = QObject

signal_decl = pyqtSignal

class MouseEvent(QMouseEvent):
    def is_left_button(self) -> bool:   return self.button() == Qt.MouseButton.LeftButton
    def is_right_button(self) -> bool:  return self.button() == Qt.MouseButton.RightButton

class Point(QPoint):
    x   = QPoint.x
    y   = QPoint.y

class SizePolicy(QSizePolicy):
    MinimumExpanding = QSizePolicy.Policy.MinimumExpanding
    ...

Color = QColor

class Widget(QWidget):
    set_layout                  = QWidget.setLayout
    set_stylesheet              = QWidget.setStyleSheet
    stylesheet                  = QWidget.styleSheet
    set_enabled                 = QWidget.setEnabled
    set_geometry                = QWidget.setGeometry
    width                       = QWidget.width
    height                      = QWidget.height
    map_to_global               = QWidget.mapToGlobal
    mouse_press_event           = QWidget.mousePressEvent
    focus_out_event             = QWidget.focusOutEvent
    set_size_policy             = QWidget.setSizePolicy
    set_minimum_width           = QWidget.setMinimumWidth
    set_minimum_height          = QWidget.setMinimumHeight

class Layout(QLayout):
    add_widget                  = QLayout.addWidget
    set_spacing                 = QLayout.setSpacing
    set_contents_margins        = QLayout.setContentsMargins

class BoxLayout(QBoxLayout):
    add_layout                  = QBoxLayout.addLayout

HBoxLayout  = QHBoxLayout
VBoxLayout  = QVBoxLayout

class FormLayout(QFormLayout):
    add_row                     = QFormLayout.addRow


class Label(QLabel):
    set_text                    = QLabel.setText

class Style(QStyle):
    standard_icon               = QStyle.standardIcon

class PushButton(QPushButton):
    def clicked_connect(self, bound_method):    self.clicked.connect(bound_method)

    set_flat                    = QPushButton.setFlat

class LineEdit(QLineEdit):
    text                        = QLineEdit.text
    set_readonly                = QLineEdit.setReadOnly

    def text_edited_connect(self, bound_method):        self.textEdited.connect(bound_method)
    def editing_finished_connect(self, bound_method):   self.editingFinished.connect(bound_method)

    def set_password_mode(self):                        self.setEchoMode(QLineEdit.EchoMode.Password)

class TextEdit(QPlainTextEdit):
    to_plain_text               = QPlainTextEdit.toPlainText
    set_plain_text              = QPlainTextEdit.setPlainText
    set_readonly                = QPlainTextEdit.setReadOnly

class CheckBox(QCheckBox):
    set_checked                 = QCheckBox.setChecked
    is_checked                  = QCheckBox.isChecked

    def state_changed_connect(self, bound_method):      self.stateChanged.connect(bound_method)

class ComboBox(QComboBox):
    ...

class GroupBox(QGroupBox):
    set_title                   = QGroupBox.setTitle

class RadioButton(QRadioButton):
    set_checked                 = QRadioButton.setChecked

class ButtonGroup(QButtonGroup):
    add_button                  = QButtonGroup.addButton
    button                      = QButtonGroup.button
    checked_id                  = QButtonGroup.checkedId


class ListItem(QListWidgetItem):
    set_selected                = QListWidgetItem.setSelected

MatchExactly = Qt.MatchFlag.MatchExactly
class ListWidget(QListWidget):
    find_items                  = QListWidget.findItems
    add_items                   = QListWidget.addItem
    clear                       = QListWidget.clear

    def clicked_connect(self, bound_method):    self.connect(bound_method)

class TreeItem(QTreeWidgetItem):
    set_expanded                = QTreeWidgetItem.setExpanded
    set_text                    = QTreeWidgetItem.setText
    set_tooltip                 = QTreeWidgetItem.setToolTip

class TreeWidget(QTreeWidget):
    set_column_count            = QTreeWidget.setColumnCount
    set_header_labels           = QTreeWidget.setHeaderLabels
    top_level_item_count        = QTreeWidget.topLevelItemCount
    top_level_item              = QTreeWidget.topLevelItem
    resize_column_to_contents   = QTreeWidget.resizeColumnToContents

    def item_clicked_connect(self, bound_method):       self.itemClicked.connect(bound_method)


class CalendarWidget(QCalendarWidget):
    set_grid_visible            = QCalendarWidget.setGridVisible
    set_selected_date           = QCalendarWidget.setSelectedDate

    def selected_date(self):        return self.selectedDate().toPyDate()

class Dialog(QDialog):
    set_window_title            = QDialog.setWindowTitle
    set_window_flags            = QDialog.setWindowFlags

class MessageBox(QMessageBox):
    @classmethod
    def is_yes_button(cls, sb):
        return sb == QMessageBox.StandardButton.Yes

class Application(QApplication):
    ...

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

class ScrollArea(QScrollArea):
    set_widget                          = QScrollArea.setWidget
    set_horizontal_scrollbar_policy     = QScrollArea.setHorizontalScrollBarPolicy
    set_vertical_scrollbar_policy       = QScrollArea.setVerticalScrollBarPolicy

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


