"""A set has one stored form and one ID, whatever the process: Nucleus.ordered_set() and what uses it."""

from __future__ import annotations

import os
import pickle
import subprocess
import sys

from core_10x.exec_control import CACHE_ONLY
from core_10x.nucleus import Nucleus
from core_10x.traitable import T, Traitable


class Tagged(Traitable):
    tags: set = T(T.ID)
    more: set = T()


class TestSetOrder:
    def test_items_of_one_ordered_type_are_sorted_by_value(self):
        assert Nucleus.ordered_set({'b', 'c', 'a'}) == ['a', 'b', 'c']
        assert Nucleus.ordered_set({10, 9, 100}) == [9, 10, 100]  # by value, not as text
        assert Nucleus.ordered_set(set()) == []
        assert Nucleus.ordered_set({'only'}) == ['only']

    def test_other_items_are_ordered_by_class_id_and_stored_form(self):
        assert Nucleus.ordered_set({1, 'a', 2.5, 'b'}) == [2.5, 1, 'a', 'b']  # float, int, str: items of several types do not compare
        with CACHE_ONLY():
            x, y = Tagged(tags = {'x'}), Tagged(tags = {'y'})  # a Traitable has no order of its own
            assert Nucleus.ordered_set({x, y}) == Nucleus.ordered_set({y, x}) == [x, y]

    def test_a_set_trait_has_one_stored_form_and_one_id(self):
        with CACHE_ONLY():
            tagged      = Tagged(tags = {'b', 'c', 'a'}, _update = True)
            tagged.more = {'b', 'c', 'a'}

            assert tagged.id().value == "{'a', 'b', 'c'}"  # written as str() writes a set
            assert tagged.serialize_object()['more'] == ['builtins/str', 'a', 'b', 'c']
            assert Tagged.trait('more').serialize(set()) == []
            assert Tagged.trait('more').deserialize(['builtins/str', 'c', 'a', 'b']) == {'a', 'b', 'c'}  # a form stored before: any order is read

    def test_a_set_is_the_same_in_every_process(self):
        # the iteration order of a set of strings follows the hash seed, which differs from one process to the next
        script  = '\n'.join((
            'from core_10x.exec_control import CACHE_ONLY',
            'from core_10x.unit_tests.test_set_order import Tagged',
            'with CACHE_ONLY():',
            "    tagged = Tagged(tags = {'one', 'two', 'three', 'four', 'five', 'six'}, _update = True)",
            "    tagged.more = {'one', 'two', 'three', 'four', 'five', 'six'}",
            "    print(tagged.id().value, tagged.serialize_object()['more'])",
        ))
        seen    = {
            subprocess.run([sys.executable, '-c', script], env = {**os.environ, 'PYTHONHASHSEED': seed}, capture_output = True, text = True, check = True).stdout.strip().splitlines()[-1]
            for seed in ('1', '2', '3')
        }
        assert seen == {"{'five', 'four', 'one', 'six', 'three', 'two'} ['builtins/str', 'five', 'four', 'one', 'six', 'three', 'two']"}

    def test_a_set_inside_another_value_is_a_typed_record(self):
        record = Nucleus.serialize_any({'b', 'a'}, False)
        assert record == {Nucleus.TYPE_TAG(): Nucleus.TYPE_RECORD_TAG(), Nucleus.CLASS_TAG(): 'builtins/set', Nucleus.OBJECT_TAG(): ['builtins/str', 'a', 'b']}
        assert Nucleus.deserialize_record(record) == {'a', 'b'}

        stored = Nucleus.serialize_list([{'b', 'a'}, {'c'}], False)  # a list of sets
        assert stored == ['builtins/set', ['builtins/str', 'a', 'b'], ['builtins/str', 'c']]
        assert Nucleus.deserialize_list(stored) == [{'a', 'b'}, {'c'}]

    def test_a_set_pickled_before_is_still_read(self):
        pickled = {Nucleus.TYPE_TAG(): Nucleus.PICKLE_RECORD_TAG(), Nucleus.CLASS_TAG(): 'builtins/set', Nucleus.OBJECT_TAG(): pickle.dumps({'a', 'b'})}
        assert Nucleus.deserialize_record(pickled) == {'a', 'b'}
