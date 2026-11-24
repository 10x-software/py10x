"""Qt6 counterpart of rio/widgets/unit_tests/test_group_box.py."""

import ui_10x.qt6.platform_implementation as ux
from ui_10x.qt6.testlib import qt_helpers as h


def _group_box(title: str, *children: ux.Widget) -> ux.GroupBox:
    widget, lay = ux.GroupBox(title), ux.VBoxLayout()
    widget.set_layout(lay)
    for child in children:
        lay.add_widget(child)
    return h.show(widget)


def _children(widget: ux.GroupBox) -> list[ux.Widget]:
    lay = widget.layout()
    return [lay.item_at(i).widget() for i in range(lay.count())]


def test_group_box() -> None:
    widget = _group_box('Test Group')
    assert widget.title() == 'Test Group'

    widget.set_title('Updated Group')
    assert widget.title() == 'Updated Group'


def test_group_box_positional_title_string() -> None:
    assert ux.GroupBox('Selection Mode').title() == 'Selection Mode'  #-- UxRadioBox uses this


def test_group_box_positional_parent_only() -> None:
    parent = ux.Label('parent')
    widget = ux.GroupBox(parent)
    assert widget.title() == ''
    assert widget.parent() is parent


def test_group_box_with_children() -> None:
    label, checkbox, button = ux.Label('Label inside group'), ux.CheckBox('Checkbox inside group'), ux.PushButton('Button inside group')
    widget                  = _group_box('Group with children', label, checkbox, button)
    assert widget.title() == 'Group with children'
    assert _children(widget) == [label, checkbox, button]
    assert all(child.parent() is widget and child.is_visible() for child in (label, checkbox, button))


def test_group_box_add_remove_children() -> None:
    widget          = _group_box('Dynamic Group')
    label, button   = ux.Label('Dynamic Label'), ux.PushButton('Dynamic Button')
    assert _children(widget) == []

    widget.layout().add_widget(label)
    widget.layout().add_widget(button)
    assert _children(widget) == [label, button]

    widget.layout().remove_widget(label)
    label.set_parent(None)
    assert _children(widget) == [button]

    widget.layout().remove_widget(button)
    button.set_parent(None)
    assert _children(widget) == []


def test_group_box_disabled_disables_children() -> None:
    label   = ux.Label('Child Label')
    widget  = _group_box('Enabled Group', label)
    widget.set_enabled(False)
    assert not label.is_enabled()

    widget.set_enabled(True)
    assert label.is_enabled()
