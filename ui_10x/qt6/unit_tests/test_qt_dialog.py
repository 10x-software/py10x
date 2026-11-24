"""Qt6 counterpart of rio/widgets/unit_tests/test_dialog.py, plus the modal paths Rio has no exec() for.

Rio measures the rendered dialog in the browser; Qt sizes a dialog from its layout's size hint, so these check
that instead: a dialog fits its content, and a declared minimum width -- not wrapping text -- widens it.
"""

from core_10x.rc import RC

import ui_10x.qt6.platform_implementation as ux
from ui_10x.qt6.testlib import qt_helpers as h
from ui_10x.utils import UxDialog


def _dialog(content: ux.Widget, **kwargs):
    dialog = UxDialog(content, title = 'Sized dialog', ok = 'Ok', cancel = '', **kwargs)
    dialog.show()
    return dialog


def _text_edit(text: str, min_width: int = 0) -> ux.TextEdit:
    content = ux.TextEdit()
    content.set_plain_text(text)
    content.set_line_wrap_mode(ux.TextEdit.LineWrapMode.WidgetWidth)
    if min_width:
        content.set_minimum_width(min_width)
    return content


def test_dialog_small_content_sizes_to_content() -> None:
    dialog = _dialog(ux.Label('content'))
    screen = dialog.screen().availableGeometry()
    assert dialog.height() == dialog.size_hint().height()  #-- the width also has Qt's minimum for a dialog
    assert dialog.width() < screen.width()
    assert dialog.height() < screen.height()


def test_wrapping_text_alone_does_not_widen_the_dialog() -> None:
    plain       = _dialog(_text_edit('short'))
    wrapping    = _dialog(_text_edit('A single line of text needing far more than a few hundred pixels to avoid wrapping.'))
    assert wrapping.width() == plain.width()


def test_declared_minimum_width_widens_the_dialog() -> None:
    plain   = _dialog(_text_edit('short'))
    wide    = _dialog(_text_edit('short', min_width = 1500))
    assert wide.width() > plain.width()
    assert wide.width() >= 1500


def test_dialog_ok_runs_accept_callback_and_closes() -> None:
    accepted    = []
    dialog      = UxDialog(ux.Label('content'), accept_callback = lambda: accepted.append(True) or RC(True))
    assert h.run_modal(dialog.exec, lambda d: h.click(h.button(d, 'Ok'))) == 1
    assert accepted == [True]


def test_dialog_rejected_accept_stays_open_with_its_message() -> None:
    def interact(d):
        h.click(h.button(d, 'Ok'))
        assert d.is_visible(), 'a failed accept must keep the dialog open'
        assert d.w_message.text() == 'not yet'
        h.click(h.button(d, 'Cancel'))

    dialog = UxDialog(ux.Label('content'), accept_callback = lambda: RC(False, 'not yet'))
    assert h.run_modal(dialog.exec, interact) == 0


def test_message_box_question_reports_the_answer() -> None:
    answers = []
    ux.MessageBox.question(None, 'Question', 'Sure?', on_close = lambda sb: answers.append(ux.MessageBox.is_yes_button(sb)))
    box = next(iter(ux.MessageBox.s_boxes_by_parent.values()))
    assert [b.text().replace('&', '') for b in box.buttons()] == ['Yes', 'No']

    h.click(box.button(ux.MessageBox.StandardButton.Yes))
    assert answers == [True]


def test_message_box_warning_blocks_until_ok() -> None:
    def ok(box):
        assert box.text() == 'careful'
        h.click(box.button(ux.MessageBox.StandardButton.Ok))

    rc = h.run_modal(lambda: ux.MessageBox.warning(None, 'Warning', 'careful', on_close = None), ok)
    assert rc == ux.MessageBox.StandardButton.Ok.value
