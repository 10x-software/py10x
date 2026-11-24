"""Test helpers for the Qt6 backend: real widgets driven headless by QTest, and the generic ui_10x modules run on Qt.

The generic modules (`ui_10x.utils`, `ui_10x.traitable_editor`, ...) bind `ux` when first imported, and
`ui_10x.platform` picks one backend per process -- Rio in a full pytest session, because collecting the Rio tests
imports `rio` first. `qt_backend()` swaps a Qt-bound copy of them into `sys.modules`; ui_10x/qt6/conftest.py enters it
to import each Qt test module and to run each test, so Qt tests import them like any other module.
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from types import ModuleType
from typing import TYPE_CHECKING

from core_10x.testlib.strict import need

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')  #-- must precede the first QApplication

try:
    from PyQt6.QtCore import QEvent, QPoint, Qt, QTimer
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QAbstractItemView, QApplication, QDialog, QLineEdit, QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QWidget
except ImportError as e:  #-- PyQt6, or a system library it loads (libEGL, libxkbcommon on Linux), is missing
    need(False, f'Qt6 does not load: {e}')

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

#-- what binds no backend, or (rio, not listed) only its own; this package holds the swap's state
_NOT_SWAPPED                        = (
    'ui_10x',
    'ui_10x.platform_interface',
    'ui_10x.qt6',
    'ui_10x.qt6.platform_implementation',
    'ui_10x.qt6.mac_os_global_commit_filter',
    __package__,
    __name__,
)
_qt_modules: dict[str, ModuleType]  = {}  #-- generic modules imported under Qt6, kept for the process


def _swapped(name: str) -> bool:
    return name.startswith('ui_10x.') and name not in _NOT_SWAPPED and not name.startswith('ui_10x.rio') and not name.endswith('conftest')


def _install(modules: dict[str, ModuleType]) -> dict[str, ModuleType]:
    """Replaces the swapped modules in sys.modules with `modules`; returns the ones it took out.

    Parent packages that stay keep an attribute per submodule, which `from ui_10x import utils` reads before
    sys.modules, so those attributes are swapped too.
    """
    taken = {name: module for name, module in sys.modules.items() if _swapped(name)}
    for name, module in taken.items():
        del sys.modules[name]
        parent, _, attr = name.rpartition('.')
        if not _swapped(parent) and getattr(sys.modules.get(parent), attr, None) is module:
            delattr(sys.modules[parent], attr)
    for name, module in modules.items():
        sys.modules[name]   = module
        parent, _, attr     = name.rpartition('.')
        if not _swapped(parent) and parent in sys.modules:
            setattr(sys.modules[parent], attr, module)
    return taken


@contextlib.contextmanager
def qt_backend() -> Iterator[None]:
    """Inside, generic ui_10x modules resolve to their Qt-bound copies; after, to whatever was there before."""
    platform                    = os.environ.get('UI_PLATFORM')
    os.environ['UI_PLATFORM']   = 'Qt6'
    before                      = _install(_qt_modules)
    try:
        yield
    finally:
        _qt_modules.update(_install(before))
        if platform is None:
            os.environ.pop('UI_PLATFORM', None)
        else:
            os.environ['UI_PLATFORM'] = platform


@contextlib.contextmanager
def slot_errors() -> Iterator[None]:
    """Raises, on exit, the first exception of a slot or event handler: PyQt would abort the process for it."""
    errors: list[BaseException] = []
    hook                        = sys.excepthook
    sys.excepthook              = lambda _type, error, _traceback: errors.append(error)
    try:
        yield
    finally:
        sys.excepthook = hook
    if errors:
        raise errors[0]


def app() -> QApplication:
    import ui_10x.qt6.platform_implementation as ux

    return ux.init()


def release_widgets() -> None:
    """Closes and deletes every window, so no widget keeps a test's Traitables alive past it."""
    import ui_10x.qt6.platform_implementation as ux

    for box in list(ux.MessageBox.s_boxes_by_parent.values()):
        box.done(0)
    ux.MessageBox.s_boxes_by_parent.clear()
    ux.Dialog.s_open_dialogs.clear()
    if (utils := sys.modules.get('ui_10x.utils')) is not None:
        utils.UxAsync.s_instances.clear()  #-- each holds the bound method it calls, and so its object

    for w in QApplication.topLevelWidgets():
        w.close()
        w.deleteLater()
    #-- deleting a widget defers deleting the slot proxies of its connections, which hold their callables
    for _ in range(3):
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        QApplication.processEvents()


def show(w: QWidget) -> QWidget:
    w.show()
    QTest.qWaitForWindowExposed(w)
    return w


def click(w: QWidget, button = Qt.MouseButton.LeftButton, pos: QPoint | None = None) -> None:
    QTest.mouseClick(w, button, Qt.KeyboardModifier.NoModifier, pos or w.rect().center())
    QApplication.processEvents()


def click_item(view: QAbstractItemView, item) -> None:
    """Clicks a list or tree item where it is drawn, as a user would."""
    view.scrollToItem(item)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, view.visualItemRect(item).center())
    QApplication.processEvents()


def focus(w: QWidget) -> None:
    """A widget in an inactive window takes focus in name only, and then losing it emits nothing."""
    window = w.window()
    if not window.isVisible():
        show(window)
    if not window.isActiveWindow():
        window.activateWindow()
        QTest.qWaitForWindowActive(window)
    w.setFocus()
    QApplication.processEvents()


def type_text(edit: QLineEdit, text: str, commit: bool = True) -> None:
    """Replaces the field's text by typing; `commit` moves focus away, which is when an edit reaches the trait."""
    focus(edit)
    edit.selectAll()
    QTest.keyClicks(edit, text)
    if commit:
        edit.clearFocus()
    QApplication.processEvents()


def buttons(root: QWidget, text: str) -> list[QPushButton]:
    return [b for b in root.findChildren(QPushButton) if b.text() == text and b.isVisible()]


def button(root: QWidget, text: str) -> QPushButton:
    found = buttons(root, text)
    assert len(found) == 1, f'expected one visible {text!r} button, found {len(found)}'
    return found[0]


def line_edits(root: QWidget) -> list[QLineEdit]:
    return [e for e in root.findChildren(QLineEdit) if e.isVisible()]


def texts(root: QWidget) -> list[str]:
    return [e.text() for e in line_edits(root)]


def dialogs() -> list[QDialog]:
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]


def dialog(title: str) -> QDialog:
    found = [d for d in dialogs() if d.windowTitle() == title]
    assert len(found) == 1, f'expected one open {title!r} dialog, found {[d.windowTitle() for d in dialogs()]}'
    return found[0]


def message_box() -> QMessageBox:
    found = [d for d in dialogs() if isinstance(d, QMessageBox)]
    assert len(found) == 1, f'expected one open message box, found {len(found)}'
    return found[0]


def trait_widgets(root: QWidget) -> dict[str, QWidget]:
    """The visible trait widgets under `root`, by trait name: each TraitWidget knows its trait."""
    return {w.trait.name: w for w in root.findChildren(QWidget) if getattr(w, 'trait', None) is not None and w.isVisible()}


def tree_items(tree: QTreeWidget) -> dict[str, QTreeWidgetItem]:
    items   = {}
    it      = QTreeWidgetItemIterator(tree)
    while it.value():
        items[it.value().text(0)] = it.value()
        it += 1
    return items


def wait_until(predicate: Callable[[], object], timeout_s: float = 10.0, message: str = 'condition') -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        assert time.monotonic() < deadline, f'timed out after {timeout_s}s waiting for {message}'
        QTest.qWait(20)


def run_modal(open_modal: Callable[[], object], interact: Callable[[QDialog], None], timeout_s: float = 10.0):
    """Calls `open_modal`, which blocks in a modal dialog's exec(), with `interact(dialog)` run inside that loop.

    `interact` must close the dialog. If it raises, or leaves it open past `timeout_s`, the dialog is rejected so
    exec() returns, and the error is raised here instead of a hang. Nests: `interact` may call run_modal again.
    """
    outer                           = QApplication.activeModalWidget()
    errors: list[BaseException]     = []
    opened                          = False

    def modal():
        dialog = QApplication.activeModalWidget()
        return None if dialog is outer else dialog

    def abort(error: BaseException) -> None:
        errors.append(error)
        if (dialog := modal()) is not None:
            dialog.reject()

    def step():
        nonlocal opened
        if (dialog := modal()) is None:
            starter.start(10)
            return
        opened = True
        try:
            QTest.qWaitForWindowActive(dialog)  #-- exec() shows it, but activation arrives later
            interact(dialog)
        except BaseException as e:  # noqa: BLE001 -- re-raised after exec() returns
            abort(e)

    def timer(callback, ms: int) -> QTimer:
        t = QTimer()
        t.setSingleShot(True)
        t.timeout.connect(callback)
        t.start(ms)
        return t

    starter     = timer(step, 0)
    watchdog    = timer(lambda: abort(TimeoutError(f'modal dialog still open after {timeout_s}s')), int(timeout_s * 1000))
    try:
        result = open_modal()
    finally:
        for t in (starter, watchdog):
            t.stop()
            t.timeout.disconnect()  #-- a timer and the slot that restarts it keep each other alive, unseen by gc
    if errors:
        raise errors[0]
    assert opened, 'open_modal() returned without opening a modal dialog'
    return result
