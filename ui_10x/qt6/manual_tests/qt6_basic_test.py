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

if __name__ == '__main__':
    app = ux.init()

    w = ux.Label('a')
    w = ux.PushButton('b')
    w = ux.LineEdit()
    w = ux.RadioButton()
    w = ux.CheckBox('Check')
    w = ux.ListWidget()
    w = ux.TreeWidget()





