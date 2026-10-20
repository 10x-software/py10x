"""TraitableEditor.dialog()/popup() coverage for editing with and without a
change_tracker (track_changes=True/False), including copy_entity interaction.

Uses .dialog() + manual accept_callback()/cancel_callback() invocation rather
than .popup()/.exec(), since .exec() blocks waiting for real UI interaction.
"""

import random
import string

from core_10x.code_samples.person import Person
from core_10x.exec_control import INTERACTIVE
from ui_10x.traitable_editor import TraitableEditor
from xxcommon.conftest import ts_instance


def _person(ts_instance, tags):  # noqa: F811
    # first_name/last_name verify letters-only, so a hex uuid will not do.
    unique = ''.join(random.choices(string.ascii_lowercase, k=20))
    return Person(first_name='tracked', last_name=unique, tags=list(tags), _replace=True)


def test_dialog_copy_entity_stages_and_exports_on_accept(ts_instance):  # noqa: F811
    with ts_instance, INTERACTIVE():
        t = _person(ts_instance, ['a', 'b'])
        ed = TraitableEditor.editor(t)
        d = ed.dialog()  # copy_entity=True (default), track_changes=False

        assert ed.change_tracker is None
        with ed.traitable_processor:
            t.tags = ['x', 'y']
        # Staged in the dialog's own INTERACTIVE -- invisible outside it.
        assert t.tags == ['a', 'b']

        rc = d.accept_callback()
        assert rc
        assert t.tags == ['x', 'y']  # exported to the ambient scope on accept


def test_dialog_copy_entity_false_edits_directly(ts_instance):  # noqa: F811
    with ts_instance, INTERACTIVE():
        t = _person(ts_instance, ['p'])
        ed = TraitableEditor.editor(t)
        ed.dialog(copy_entity=False)

        assert ed.traitable_processor is None
        t.tags = ['q', 'r']
        assert t.tags == ['q', 'r']  # immediately visible, no staging at all


def test_dialog_cancel_discards_staged_edit(ts_instance):  # noqa: F811
    with ts_instance, INTERACTIVE():
        t = _person(ts_instance, ['a'])
        ed = TraitableEditor.editor(t)
        d = ed.dialog()

        with ed.traitable_processor:
            t.tags = ['discarded']
        d.cancel_callback()
        assert t.tags == ['a']  # never exported


def test_dialog_track_changes_stages_and_saves_via_tracker(ts_instance):  # noqa: F811
    with ts_instance, INTERACTIVE():
        t = _person(ts_instance, ['a'])
        ed = TraitableEditor.editor(t)
        d = ed.dialog(track_changes=True)

        # change_tracker is the accumulator; traitable_processor is this dialog's
        # own staging scope nested inside it, and is what edits go through.
        assert ed.change_tracker is not None
        assert ed.traitable_processor is not ed.change_tracker
        with ed.traitable_processor:
            t.tags = ['x', 'y']
        # Staged two levels down -- isolated from the ambient scope until accept,
        # and from the store until save().
        assert t.tags == ['a']

        rc = d.accept_callback()
        assert rc
        # Accept alone doesn't persist -- that's the tracker's job. Person
        # shares one default collection across tests, so check a delta
        # rather than an absolute count.
        before = t.__class__.collection(t._collection_name).count()

        rc = ed.change_tracker.save()
        assert rc
        assert t.__class__.collection(t._collection_name).count() == before + 1


def test_dialog_track_changes_without_copy_entity_edits_directly(ts_instance):  # noqa: F811
    with ts_instance, INTERACTIVE():
        t = _person(ts_instance, ['a'])
        ed = TraitableEditor.editor(t)
        d = ed.dialog(copy_entity=False, track_changes=True)

        # No staging scope: the tracker is the processor, and edits reach the ambient
        # scope as they are made. Tracking still decides what save() persists.
        assert ed.traitable_processor is ed.change_tracker
        with ed.traitable_processor:
            t.tags = ['direct']
        assert t.tags == ['direct']

        d.accept_callback()
        assert ed.change_tracker.save()
        assert t.reload()
        assert t.tags == ['direct']


def test_dialog_track_changes_without_copy_entity_cancel_keeps_the_edit(ts_instance):  # noqa: F811
    """copy_entity=False means edits are not taken back -- there is no scope to drop."""
    with ts_instance, INTERACTIVE():
        t = _person(ts_instance, ['a'])
        ed = TraitableEditor.editor(t)
        d = ed.dialog(copy_entity=False, track_changes=True)

        with ed.traitable_processor:
            t.tags = ['direct']
        d.cancel_callback()
        assert t.tags == ['direct']


def test_dialog_track_changes_reused_across_dialogs(ts_instance):  # noqa: F811
    with ts_instance, INTERACTIVE():
        t = _person(ts_instance, ['a'])
        ed = TraitableEditor.editor(t)

        d1 = ed.dialog(track_changes=True)
        with ed.traitable_processor:
            t.tags = ['first']
        d1.accept_callback()
        first_tracker = ed.change_tracker

        # A second .dialog() call on the SAME editor reuses the SAME accumulator,
        # with a fresh staging scope nested inside it.
        d2 = ed.dialog(track_changes=True)
        assert ed.change_tracker is first_tracker
        with ed.traitable_processor:
            t.tags = ['first', 'second']
        d2.accept_callback()

        rc = ed.change_tracker.save()
        assert rc
        # Person shares one default collection across tests (not
        # custom_collection) -- verify via reload, not a collection-wide count.
        assert t.reload()
        assert t.tags == ['first', 'second']


def test_dialog_track_changes_cancel_discards_only_this_dialogs_edit(ts_instance):  # noqa: F811
    """Cancel drops this dialog's staging scope and never folds it into the
    accumulator, so an edit accepted in an earlier dialog is what gets saved."""
    with ts_instance, INTERACTIVE():
        t = _person(ts_instance, ['orig'])
        ed = TraitableEditor.editor(t)

        d1 = ed.dialog(track_changes=True)
        with ed.traitable_processor:
            t.tags = ['first']
        d1.accept_callback()

        d2 = ed.dialog(track_changes=True)
        with ed.traitable_processor:
            t.tags = ['cancelled']
        d2.cancel_callback()

        assert ed.change_tracker.save()
        assert t.reload()
        assert t.tags == ['first']


def test_dialog_track_changes_cancel_on_first_dialog_saves_nothing(ts_instance):  # noqa: F811
    """With nothing accepted yet, a cancelled dialog leaves the accumulator empty."""
    with ts_instance, INTERACTIVE():
        t = _person(ts_instance, ['orig'])
        t.save().throw()
        ed = TraitableEditor.editor(t)

        d = ed.dialog(track_changes=True)
        with ed.traitable_processor:
            t.tags = ['cancelled']
        d.cancel_callback()

        assert ed.change_tracker.save()
        assert t.reload()
        assert t.tags == ['orig']
