"""Qt6 counterpart of rio/widgets/unit_tests/test_button_group.py."""

import ui_10x.qt6.platform_implementation as ux
from ui_10x.qt6.testlib import qt_helpers as h


def _group(*labels: str) -> tuple[ux.ButtonGroup, ux.Widget, list[ux.RadioButton]]:
    host, lay  = ux.Widget(), ux.VBoxLayout()
    host.set_layout(lay)
    group   = ux.ButtonGroup(host)
    radios  = []
    for i, label in enumerate(labels):
        rb = ux.RadioButton(label)
        group.add_button(rb, i)
        lay.add_widget(rb)
        radios.append(rb)
    return group, h.show(host), radios


def test_button_group() -> None:
    group, _host, (btn1, btn2) = _group('A', 'B')
    assert group.checked_id() == -1

    btn1.set_checked(True)
    assert group.checked_id() == 0

    btn2.set_checked(True)
    assert group.checked_id() == 1
    assert not btn1.is_checked()

    #-- unlike Rio's, a Qt group is exclusive: the checked radio cannot be unchecked, only another one checked
    btn2.set_checked(False)
    assert group.checked_id() == 1


def test_radio_button_label_click_selects() -> None:
    group, _host, (btn1, btn2) = _group('ANY', 'LEAF')
    btn1.set_checked(True)
    assert group.checked_id() == 0

    h.click(btn2)
    assert group.checked_id() == 1
    assert btn2.is_checked()
    assert not btn1.is_checked()

    h.click(btn2)  #-- re-clicking the selected radio keeps it selected
    assert group.checked_id() == 1
    assert group.button(1) is btn2
