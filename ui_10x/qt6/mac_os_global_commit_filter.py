from PyQt6.QtCore import QObject, QEvent
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QLineEdit, QAbstractSpinBox


class MacEditCommitFilter(QObject):
    def __init__(self):
        super().__init__()
        self._in_commit = False

    def eventFilter(self, obj, event):
        if self._in_commit:
            return False

        if event.type() == QEvent.Type.MouseButtonPress:
            self._commit_if_click_outside_focused_editor(event)

        return False

    def _commit_if_click_outside_focused_editor(self, event):
        focused = QApplication.focusWidget()
        if focused is None:
            return

        global_pos = event.globalPosition().toPoint()
        clicked = QApplication.widgetAt(global_pos)

        #-- If clicking inside the same widget, do nothing
        w = clicked
        while w is not None:
            if w is focused:
                return
            w = w.parentWidget()

        #-- Commit before click is delivered
        self._in_commit = True
        try:
            QGuiApplication.inputMethod().commit()

            if isinstance(focused, QLineEdit):
                focused.clearFocus()

            elif isinstance(focused, QAbstractSpinBox):
                focused.interpretText()
                focused.clearFocus()

            else:
                commit = getattr(focused, 'commitEditor', None)
                if callable(commit):
                    commit()

        finally:
            self._in_commit = False

    F = None
    @classmethod
    def install(cls, app: QApplication):
        if cls.F is None:
            f = cls()
            app.installEventFilter(f)
            cls.F = f
