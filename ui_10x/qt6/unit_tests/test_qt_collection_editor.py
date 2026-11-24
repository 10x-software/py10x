"""Qt6 counterpart of rio/unit_tests/test_collection_editor.py.

Fields are found by trait name (each trait widget knows its trait) where Rio's test counts DOM inputs. 'edit'
and 'New' open their dialog with exec(), so the dialog is driven from inside it with run_modal().
"""

import gc
import weakref
from datetime import date

import pytest
from PyQt6.QtWidgets import QListWidget

from core_10x.code_samples.person import Person
from core_10x.exec_control import CACHE_ONLY, INTERACTIVE
from ui_10x.collection_editor import Collection, CollectionEditor
from ui_10x.qt6.testlib import qt_helpers as h
from ui_10x.traitable_editor import TraitableEditor
from xxcommon.conftest import ts_instance


@pytest.fixture
def mock_db_ops(monkeypatch):
    with CACHE_ONLY():
        sasha   = Person(first_name = 'Sasha', last_name = 'Davidovich', weight_lbs = 150, _replace = True)
        ilya    = Person(first_name = 'Ilya', last_name = 'Pevzner', weight_lbs = 200, dob = date(1971, 7, 3), _replace = True)
    monkeypatch.setattr(Person, 'load_ids', lambda: [sasha.id(), ilya.id()])
    monkeypatch.setattr(Person, 'load_data', lambda id: {sasha.id(): sasha, ilya.id(): ilya}[id])
    yield


def _editor(**kwargs):
    ce = CollectionEditor(coll = Collection(cls = Person), **kwargs)
    return ce, h.show(ce.main_widget())


def _list(widget) -> QListWidget:
    return widget.findChildren(QListWidget)[0]


def _rows(widget) -> list[str]:
    lw = _list(widget)
    return [lw.item(r).text() for r in range(lw.count())]


def _select(widget, text: str) -> None:
    lw = _list(widget)
    h.click_item(lw, lw.find_items(text, h.Qt.MatchFlag.MatchExactly)[0])


def _weight(root) -> tuple[str, str]:
    fields = h.trait_widgets(root)
    return fields['weight'].display_text(), fields['weight_qu'].display_text()


def _edit(widget, interact) -> None:
    h.run_modal(lambda: h.click(h.button(widget, 'edit')), interact)


def _release(ce, widget) -> None:
    """The editor stays reachable through its widget's callbacks, as long as the widget is."""
    searchable_list = ce.searchable_list
    wr              = weakref.ref(ce)
    del ce
    gc.collect()
    assert wr() is not None, 'select_hook must keep CollectionEditor reachable via the widget tree'
    searchable_list.release()
    widget.close()


def test_collection_editor(mock_db_ops) -> None:
    with INTERACTIVE():
        ce, widget = _editor()
        assert _rows(widget) == ['Ilya|Pevzner', 'Sasha|Davidovich']

        _select(widget, 'Ilya|Pevzner')
        assert _weight(widget) == ('200.00', 'LB')

        def change_unit(dialog):
            assert _weight(dialog) == ('200.00', 'LB')
            h.click(h.trait_widgets(dialog)['weight_qu'].button)
            picker  = h.dialog('Pick your choice')
            units   = picker.findChildren(QListWidget)[0]
            h.click_item(units, units.find_items('G', h.Qt.MatchFlag.MatchExactly)[0])
            assert not picker.is_visible(), 'picking a value closes the picker'
            assert _weight(dialog) == ('90,702.95', 'G')
            h.click(h.button(dialog, 'Ok'))

        _edit(widget, change_unit)
        assert _weight(widget) == ('90,702.95', 'G')
        _release(ce, widget)


def test_collection_editor_edit_dob_calendar_does_not_close_parent_dialog(mock_db_ops) -> None:
    """Accepting the nested date-picker dialog must not close the entity-edit dialog that opened it."""
    with INTERACTIVE():
        ce, widget = _editor()
        _select(widget, 'Ilya|Pevzner')

        def edit(outer):
            def pick(inner):
                assert inner is not outer
                h.click(h.button(inner, 'Ok'))

            h.run_modal(lambda: h.click(h.button(outer, 'Dob...')), pick)
            assert outer.is_visible(), 'accepting the nested date dialog closed the entity dialog'
            assert _weight(outer) == ('200.00', 'LB')
            h.click(h.button(outer, 'Ok'))

        _edit(widget, edit)
        _release(ce, widget)


def test_traitable_editor_edit_tags_multichoice_does_not_close_parent_dialog() -> None:
    """Same as the dob test, for ``list_cb`` / MultiChoice: what ``EntityStocker.on_edit_entity`` opens."""
    with INTERACTIVE():
        with CACHE_ONLY():
            entity = Person(first_name = 'Widget', last_name = 'Tagged', tags = ['red', 'green', 'blue'], _replace = True)

        def edit(outer):
            h.click(h.button(outer, 'Tags...'))
            inner = next(d for d in h.dialogs() if d is not outer)
            shown = [lw.item(r).text() for lw in inner.findChildren(QListWidget) for r in range(lw.count())]
            assert shown.count('red') == 2, f"'red' must be listed and pre-selected, got {shown}"

            h.click(h.button(inner, 'Ok'))
            assert not inner.is_visible()
            assert outer.is_visible(), 'accepting the nested Tags dialog closed the entity dialog'
            h.click(h.button(outer, 'Ok'))

        h.run_modal(TraitableEditor.editor(entity).popup, edit)
        assert entity.tags == ['red', 'green', 'blue'], 'the pre-populated selection must round-trip unchanged'


def _edit_weight_lbs(widget, row: str, weight_lbs: str) -> None:
    """Select `row`, edit its weight_lbs and accept, without saving."""
    _select(widget, row)

    def edit(dialog):
        h.type_text(h.trait_widgets(dialog)['weight_lbs'], weight_lbs)
        h.click(h.button(dialog, 'Ok'))

    _edit(widget, edit)


def test_collection_editor_track_changes_switch_entities_and_save(monkeypatch, ts_instance) -> None:  # noqa: F811
    """Edits to two entities stay in their own ``EntityStocker.change_trackers`` entry until each is saved."""
    with ts_instance, INTERACTIVE():
        alice   = Person(first_name = 'Trackchangesalice', last_name = 'Trackchangesaliceln', weight_lbs = 150, _replace = True)
        bob     = Person(first_name = 'Trackchangesbob', last_name = 'Trackchangesbobln', weight_lbs = 200, dob = date(1971, 7, 3), _replace = True)
        alice.save().throw()
        bob.save().throw()
        monkeypatch.setattr(Person, 'load_ids', lambda: [alice.id(), bob.id()])
        monkeypatch.setattr(Person, 'load_data', lambda id: {alice.id(): alice, bob.id(): bob}[id])
        try:
            ce, widget = _editor(track_changes = True)

            _edit_weight_lbs(widget, 'Trackchangesalice|Trackchangesaliceln', '222.5')
            assert set(ce.stocker.change_trackers) == {alice}
            assert alice.weight_lbs == 150.0, 'accepting the dialog must not export the tracked edit'

            _edit_weight_lbs(widget, 'Trackchangesbob|Trackchangesbobln', '155.5')
            assert set(ce.stocker.change_trackers) == {alice, bob}
            assert bob.weight_lbs == 200.0
            assert alice.weight_lbs == 150.0, 'Alice edit must still be isolated after editing Bob'

            _select(widget, 'Trackchangesalice|Trackchangesaliceln')
            h.click(h.button(widget, 'save'))
            assert set(ce.stocker.change_trackers) == {bob}, 'only Alice must be cleared after her save'
            assert Person.collection().load(alice.id().value)['weight_lbs'] == 222.5
            assert Person.collection().load(bob.id().value)['weight_lbs'] == 200.0, 'Bob must remain unsaved in the store'

            _select(widget, 'Trackchangesbob|Trackchangesbobln')
            h.click(h.button(widget, 'save'))
            assert ce.stocker.change_trackers == {}
            assert Person.collection().load(bob.id().value)['weight_lbs'] == 155.5

            _release(ce, widget)
        finally:
            alice.delete()
            bob.delete()


def test_collection_editor_new_and_delete_entity(monkeypatch, ts_instance) -> None:  # noqa: F811
    """'New' saves the entity and lists it; 'delete' asks, and only 'Yes' deletes it, drops its row and clears the pane."""
    with ts_instance, INTERACTIVE():
        monkeypatch.setattr(Person, 'load_ids', list)  #-- nothing listed up front
        row = 'Newentityfirst|Newentitylast'
        try:
            ce, widget = _editor()

            def create(dialog):
                fields = h.trait_widgets(dialog)
                h.type_text(fields['first_name'], 'Newentityfirst')
                h.type_text(fields['last_name'], 'Newentitylast')
                h.type_text(fields['weight_lbs'], '165.5')
                h.click(h.button(dialog, 'Save'))

            h.run_modal(lambda: h.click(h.button(widget, 'New')), create)
            assert _rows(widget) == [row]
            stored = Person.collection().load(row)
            assert stored is not None, 'Save must persist the new entity'
            assert stored['weight_lbs'] == 165.5, 'dialog edits must reach the saved entity'

            _select(widget, row)
            assert ce.current_entity.id().value == row

            h.click(h.button(widget, 'delete'))
            h.click(h.message_box().button(h.QMessageBox.StandardButton.No))
            assert Person.collection().load(row) is not None, 'declining must not delete'
            assert _rows(widget) == [row]

            h.click(h.button(widget, 'delete'))
            h.click(h.message_box().button(h.QMessageBox.StandardButton.Yes))
            assert Person.collection().load(row) is None, 'confirmed delete must remove the entity'
            assert _rows(widget) == []
            assert not h.buttons(widget, 'delete'), 'stocker pane must be cleared after deletion'

            _release(ce, widget)
        finally:
            Person.collection().delete(row)  #-- no-op once the UI delete above succeeded
