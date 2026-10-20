"""``export_nodes`` when an object's ID is still in flight.

A traitable built empty has no valid ID until ``share()`` promotes it: until then its
values live in XCache's ``TID*``-keyed temporary cache, and its ID traits may still be
changed freely. ``export_nodes`` walks only the permanent, ``TID``-keyed data, so what a
staged object contributes to its parent scope depends entirely on what ``share()`` did
with it. This is the "new entity" editor flow -- build an empty instance, fill in the
fields, then decide what to do about an entity that may already carry that ID.
"""

from __future__ import annotations

from core_10x.exec_control import INTERACTIVE
from core_10x.trait_definition import RT, T
from core_10x.traitable import Traitable


class P(Traitable):
    # All-runtime, so P is not storable and these tests need no store context at all --
    # everything here is cache behavior.
    name: str = RT(T.ID)
    value: int = RT(default=0)
    other: int = RT(default=0)


def test_share_makes_a_staged_object_exportable():
    """share() is what moves the staged values out of the temporary cache
    (``make_permanent``), so that export_nodes can see them at all."""
    with INTERACTIVE() as i:
        staged = P()
        staged.value = 42  # -- set while the ID is still invalid
        staged.name = 'fresh'  # -- names an entity, but does not yet establish the ID
        assert staged.id().value is None

        assert staged.share(False)
        assert staged.id().value == 'fresh'

    i.export_nodes()

    # `staged` itself is not usable out here (it was born in `i`), but a fresh handle
    # on the same ID reads what was exported.
    assert P(name='fresh').value == 42


def test_without_share_a_staged_object_exports_nothing():
    """The counterpart: no share() means the values never leave the temporary cache.

    export_nodes walks the permanent TID-keyed data only, so this is silent -- no error,
    simply nothing exported.
    """
    with INTERACTIVE() as i:
        staged = P()
        staged.value = 42
        staged.name = 'noshare'
        assert staged.id().value is None

    i.export_nodes()

    assert P(name='noshare').value == 0


def test_share_targets_the_entity_named_by_the_latest_id():
    """ID traits may be re-set while the object is still temporary; endogenous_id() is
    read at share() time, so the last value decides which entity is named."""
    with INTERACTIVE() as i:
        staged = P()
        staged.value = 7
        staged.name = 'first'  # -- names `first`...
        staged.name = 'second'  # -- ...then re-pointed, still allowed pre-share
        assert staged.share(False)
        assert staged.id().value == 'second'

    i.export_nodes()

    assert P(name='second').value == 7
    assert P(name='first').value == 0, 'the abandoned ID must not receive the staged value'


def test_share_false_refuses_an_id_an_outer_object_already_holds():
    """Not accepting existing values: the conflict is reported, and the outer entity is
    left exactly as it was. The failing RC carries the offending ID value."""
    outer = P(name='taken', _replace=True)
    outer.value = 1

    with INTERACTIVE() as i:
        staged = P()
        staged.value = 42
        staged.name = 'taken'

        rc = staged.share(False)
        assert not rc
        assert rc.error() == 'taken'

    i.export_nodes()

    assert outer.value == 1


def test_share_true_adopts_the_outer_object_and_drops_the_staged_values():
    """Accepting existing values: the staged object is re-homed onto the existing entity's
    cache and its own temporary cache is discarded, so the staged edits are lost rather
    than merged. Nothing of the staged object reaches the outer scope.
    """
    outer = P(name='held', _replace=True)
    outer.value = 1
    outer.other = 2

    with INTERACTIVE() as i:
        staged = P()
        staged.value = 42
        staged.name = 'held'

        assert staged.share(True)
        assert staged.value == 1, 'adopted the existing value, discarding the staged one'

    i.export_nodes()

    assert outer.value == 1
    assert outer.other == 2


def test_two_staged_objects_claiming_one_id_do_not_merge():
    """First to share() takes the ID outright; the second conflicts and its values are
    simply lost. There is no merge of the two staged objects' traits.

    The two stay distinct entities throughout -- an unshared ID compares by identity --
    so nothing about them being "the same" is what causes the loss; it is share() itself.
    """
    with INTERACTIVE() as i:
        first = P()
        first.value = 1
        second = P()
        second.value = 2
        second.other = 3
        assert first != second, 'two separate pending entities'

        second.name = 'shared'
        first.name = 'shared'

        assert second.share(False), 'first to share takes the ID'
        assert not first.share(False), 'the other one conflicts'
        assert first != second

    i.export_nodes()

    # second's values, whole; nothing of first's value=1 survived.
    assert (P(name='shared').value, P(name='shared').other) == (2, 3)


def test_staged_object_adopting_a_taken_id_drops_its_own_values():
    """share(True) on the loser re-homes it onto the winner's cache rather than merging."""
    with INTERACTIVE() as i:
        first = P()
        first.value = 1
        second = P()
        second.value = 2
        second.other = 3

        second.name = 'adopted'
        first.name = 'adopted'

        assert second.share(False)
        assert first.share(True)

        assert first == second
        assert (first.value, first.other) == (2, 3), "the winner's values, not a merge"

    i.export_nodes()

    assert (P(name='adopted').value, P(name='adopted').other) == (2, 3)
