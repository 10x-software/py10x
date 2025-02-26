# from PyQt6.QtWidgets import QWidget, QLayout, QBoxLayout, QVBoxLayout, QHBoxLayout, QFormLayout, QApplication
# from PyQt6.QtWidgets import QLabel, QCalendarWidget, QMessageBox, QGroupBox, QButtonGroup, QRadioButton
# from PyQt6.QtWidgets import QListWidgetItem, QListWidget, QLineEdit, QPlainTextEdit, QTreeWidgetItem, QTreeWidget, QCheckBox, QComboBox
# from PyQt6.QtWidgets import QFrame, QSplitter, QDialog, QScrollArea, QPushButton, QStyle, QSizePolicy
# from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QBuffer, QIODevice, QPoint    #, QByteArray
# from PyQt6.QtGui import QColor, QGuiApplication, QPixmap, QMouseEvent
#
# import platform
#
#
# Object = QObject
#
# signal_decl = pyqtSignal
#
# class MouseEvent(QMouseEvent):
#     def is_left_button(self) -> bool:   return self.button() == Qt.MouseButton.LeftButton
#     def is_right_button(self) -> bool:  return self.button() == Qt.MouseButton.RightButton

from ui_10x.platform import ux
from ui_10x.utils import UxRadioBox

from core_10x.named_constant import NamedConstant

class Radio(ux.GroupBox):
    def __init__(self):
        super().__init__()

class Radio2(ux.GroupBox):
    def __init__(self, *args):
        super().__init__(*args)

class COLOR(NamedConstant):
    RED     = ()
    GREEN   = ()
    BLUE    = ()

if __name__ == '__main__':
    app = ux.init()

    r = Radio()
    r2 = Radio2('Test')

    ux.QWidget.set_layout = ux.QWidget.setLayout

    #rbox = UxRadioBox(COLOR, title = 'Test')

