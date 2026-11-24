"""Qt6 counterpart of rio/unit_tests/test_multi_choice.py."""

from __future__ import annotations

from PyQt6.QtWidgets import QListWidget, QRadioButton, QTreeWidget

from core_10x.code_samples.directories import ANIMALS
from ui_10x.choice import MultiChoice
from ui_10x.qt6.testlib import qt_helpers as h


def _selection(mc) -> list[str]:
    return [mc.selection_list.item(r).text() for r in range(mc.selection_list.count())]


def _shown(mc):
    return h.show(mc.widget())


def test_multi_choice_flat_select_deselect() -> None:
    mc      = MultiChoice(choices = ['Alpha', 'Beta', 'Gamma'])
    widget  = mc.widget()  #-- held: deleting it deletes the panes too
    assert widget is not None

    mc.on_item_selected(None, 'Alpha', True)
    assert mc.values_selected == ['Alpha']
    assert _selection(mc) == ['Alpha']

    mc.on_selection_list_selection(mc.selection_list.item(0))
    assert mc.values_selected == []
    assert mc.selection_list.count() == 0


def test_multi_choice_directory_builds() -> None:
    mc      = MultiChoice(choices = ANIMALS)
    widget  = mc.widget()
    assert widget is not None
    assert mc.rb is not None  #-- selection mode radios only appear for a Directory source
    assert mc.rb.choice() is not None


def test_multi_choice_flat_click_select_deselect() -> None:
    mc      = MultiChoice(choices = ['Alpha', 'Beta', 'Gamma'])
    widget  = _shown(mc)
    source  = next(lw for lw in widget.findChildren(QListWidget) if lw is not mc.selection_list)
    assert [source.item(r).text() for r in range(source.count())] == ['Alpha', 'Beta', 'Gamma']

    h.click_item(source, source.item(0))
    assert mc.values_selected == ['Alpha']
    assert _selection(mc) == ['Alpha']

    h.click_item(mc.selection_list, mc.selection_list.item(0))
    assert mc.values_selected == []
    assert mc.selection_list.count() == 0


def test_multi_choice_directory_click_select_deselect() -> None:
    mc      = MultiChoice(choices = ANIMALS)
    widget  = _shown(mc)
    tree    = widget.findChildren(QTreeWidget)[0]
    items   = h.tree_items(tree)
    assert mc.rb.title() == 'Selection Mode'
    assert {'Microorganisms', 'Salt Water', 'Mollusks'} <= set(items)  #-- a single-child parent keeps its own label

    h.click_item(tree, items['Mollusks'])
    assert mc.values_selected == ['Mollusks']
    assert _selection(mc) == ['Mollusks']

    h.click_item(mc.selection_list, mc.selection_list.item(0))
    assert mc.values_selected == []
    assert mc.selection_list.count() == 0

    radios = {rb.text(): rb for rb in widget.findChildren(QRadioButton)}
    h.click(radios['LEAF'])
    assert mc.select_mode() is mc.SELECT_MODE.LEAF

    h.click_item(tree, items['Mammals'])  #-- LEAF: a parent is not added
    assert mc.values_selected == []

    h.click_item(tree, items['Mollusks'])
    assert mc.values_selected == ['Mollusks']


def test_multi_choice_directory_subdir_mode() -> None:
    """SUBDIR replaces selected children when a parent is chosen."""
    mc      = MultiChoice(choices = ANIMALS)
    widget  = _shown(mc)
    tree    = widget.findChildren(QTreeWidget)[0]
    tree.expandAll()
    items   = h.tree_items(tree)

    h.click({rb.text(): rb for rb in widget.findChildren(QRadioButton)}['SUBDIR'])
    assert mc.select_mode() is mc.SELECT_MODE.SUBDIR

    h.click_item(tree, items['Cats'])
    h.click_item(tree, items['Dogs'])
    assert mc.values_selected == ['Cats', 'Dogs']

    h.click_item(tree, items['Mammals'])
    assert mc.values_selected == ['Mammals']
    assert _selection(mc) == ['Mammals']

    h.click_item(tree, items['Cats'])
    assert mc.values_selected == ['Mammals']
