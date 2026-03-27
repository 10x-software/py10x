"""Unit tests for the Basket / Bucket / Bucketizer facility (core_10x/basket.py)."""
from __future__ import annotations

import itertools

import pytest

from core_10x.trait_method_error import TraitMethodError

from core_10x.basket import (
    BUCKET_SHAPE,
    Basket,
    Basketable,
    BucketDict,
    BucketList,
    BucketSet,
    Bucketizer,
    BucketizerByBreakPoints,
    BucketizerByClass,
    BucketizerByFeature,
    BucketizerByRange,
    Interval,
)
from core_10x.exec_control import CACHE_ONLY
from core_10x.named_constant import NamedCallable
from core_10x.traitable import RT, T, Traitable
from core_10x.xinf import XInf


# ---------------------------------------------------------------------------
# Domain model shared across all tests
# ---------------------------------------------------------------------------

class Animal(Traitable):
    name: str = T(T.ID)
    weight: float = T()
    species: str = T()


class Dog(Animal):
    breed: str = T()


class Cat(Animal):
    indoor: bool = T()


class SUM_WEIGHT(NamedCallable):
    WEIGHT = lambda gen: sum(v * q for v, q in gen)


# ---------------------------------------------------------------------------
# Bucket primitives
# ---------------------------------------------------------------------------

class TestBucketDict:
    def test_insert_and_members(self):
        with CACHE_ONLY():
            d = BucketDict()
            fido = Animal(name='fido')
            d._insert(fido, 2.0)
            assert d.is_member(fido)
            assert list(d.members()) == [fido]

    def test_qty_accumulates_on_repeated_insert(self):
        with CACHE_ONLY():
            d = BucketDict()
            fido = Animal(name='fido')
            d._insert(fido, 3.0)
            d._insert(fido, 1.5)
            qtys = dict(d.members_qtys())
            assert qtys[fido] == pytest.approx(4.5)

    def test_default_qty_is_one(self):
        with CACHE_ONLY():
            d = BucketDict()
            fido = Animal(name='fido')
            d._insert(fido)
            assert dict(d.members_qtys())[fido] == pytest.approx(1.0)

    def test_insert_bucket_merges_qtys(self):
        with CACHE_ONLY():
            a = Animal(name='a')
            b = Animal(name='b')
            d1 = BucketDict()
            d1._insert(a, 2.0)
            d2 = BucketDict()
            d2._insert(a, 1.0)
            d2._insert(b, 5.0)
            d1._insert_bucket(d2)
            qtys = dict(d1.members_qtys())
            assert qtys[a] == pytest.approx(3.0)
            assert qtys[b] == pytest.approx(5.0)

    def test_non_member_not_found(self):
        with CACHE_ONLY():
            d = BucketDict()
            fido = Animal(name='fido')
            outsider = Animal(name='outsider')
            d._insert(fido, 1.0)
            assert not d.is_member(outsider)


class TestBucketSet:
    def test_insert_and_members(self):
        with CACHE_ONLY():
            s = BucketSet()
            fido = Animal(name='fido')
            s._insert(fido, 1.0)
            assert s.is_member(fido)
            assert fido in list(s.members())

    def test_duplicate_insert_ignored(self):
        with CACHE_ONLY():
            s = BucketSet()
            fido = Animal(name='fido')
            s._insert(fido, 1.0)
            s._insert(fido, 1.0)
            assert len(list(s.members())) == 1

    def test_members_qtys_all_return_one(self):
        with CACHE_ONLY():
            s = BucketSet()
            fido = Animal(name='fido')
            kitty = Animal(name='kitty')
            s._insert(fido, 1.0)
            s._insert(kitty, 1.0)
            for _, qty in s.members_qtys():
                assert qty == pytest.approx(1.0)

    def test_insert_bucket_merges(self):
        with CACHE_ONLY():
            a, b, c = Animal(name='a'), Animal(name='b'), Animal(name='c')
            s1 = BucketSet()
            s1._insert(a, 1.0)
            s1._insert(b, 1.0)
            s2 = BucketSet()
            s2._insert(b, 1.0)
            s2._insert(c, 1.0)
            s1._insert_bucket(s2)
            assert s1.is_member(a)
            assert s1.is_member(b)
            assert s1.is_member(c)


class TestBucketList:
    def test_insert_and_members(self):
        with CACHE_ONLY():
            lst = BucketList()
            fido = Animal(name='fido')
            lst._insert(fido, 1.0)
            assert lst.is_member(fido)
            assert fido in list(lst.members())

    def test_duplicate_insert_allowed(self):
        with CACHE_ONLY():
            lst = BucketList()
            fido = Animal(name='fido')
            lst._insert(fido, 1.0)
            lst._insert(fido, 1.0)
            assert list(lst.members()).count(fido) == 2

    def test_insert_bucket_extends(self):
        with CACHE_ONLY():
            a, b = Animal(name='a'), Animal(name='b')
            l1 = BucketList()
            l1._insert(a, 1.0)
            l2 = BucketList()
            l2._insert(b, 1.0)
            l1._insert_bucket(l2)
            assert list(l1.members()) == [a, b]


# ---------------------------------------------------------------------------
# BUCKET_SHAPE named constant
# ---------------------------------------------------------------------------

def test_bucket_shape_values():
    assert BUCKET_SHAPE.SET.value is BucketSet
    assert BUCKET_SHAPE.DICT.value is BucketDict
    assert BUCKET_SHAPE.LIST.value is BucketList


# ---------------------------------------------------------------------------
# Basket - basics (no bucketizers)
# ---------------------------------------------------------------------------

class TestBasketBasics:
    def test_add_and_iterate(self):
        with CACHE_ONLY():
            fido = Animal(name='fido')
            kitty = Animal(name='kitty')
            b = Basket(base_class=Animal)
            assert b.add(fido)
            assert b.add(kitty)
            members = [m for m, _ in b.the_bucket.members_qtys()]
            assert fido in members
            assert kitty in members

    def test_add_with_qty(self):
        with CACHE_ONLY():
            fido = Animal(name='fido')
            b = Basket(base_class=Animal)
            b.add(fido, 3.5)
            qtys = dict(b.the_bucket.members_qtys())
            assert qtys[fido] == pytest.approx(3.5)

    def test_add_wrong_type_rejected(self):
        with CACHE_ONLY():

            class Other(Traitable):
                name: str = T(T.ID)

            other = Other(name='x')
            b = Basket(base_class=Animal)
            assert not b.add(other)

    def test_subclasses_allowed_by_default(self):
        with CACHE_ONLY():
            dog = Dog(name='rex')
            b = Basket(base_class=Animal)
            assert b.add(dog)

    def test_subclasses_rejected_when_flag_false(self):
        with CACHE_ONLY():
            dog = Dog(name='rex')
            b = Basket(base_class=Animal, subclasses_allowed=False)
            assert not b.add(dog)

    def test_tags_buckets_no_bucketizers(self):
        with CACHE_ONLY():
            fido = Animal(name='fido')
            b = Basket(base_class=Animal)
            b.add(fido)
            pairs = list(b.tags_buckets())
            assert len(pairs) == 1

    def test_default_bucket_shape_is_dict(self):
        with CACHE_ONLY():
            b = Basket(base_class=Animal)
            _ = b.add(Animal(name='a'))
            assert isinstance(b.the_bucket, BucketDict)

    def test_calc_trait_values_without_aggregator(self):
        with CACHE_ONLY():
            fido = Animal(name='fido')
            fido.weight = 10.0
            kitty = Animal(name='kitty')
            kitty.weight = 5.0
            b = Basket(base_class=Animal)
            b.add(fido, 1.0)
            b.add(kitty, 2.0)
            gen = b.calc_trait_values('weight', None)
            pairs = list(gen)
            weights = {v for v, _ in pairs}
            assert 10.0 in weights
            assert 5.0 in weights

    def test_calc_trait_values_with_aggregator(self):
        with CACHE_ONLY():
            fido = Animal(name='fido')
            fido.weight = 10.0
            kitty = Animal(name='kitty')
            kitty.weight = 5.0
            b = Basket(base_class=Animal)
            b.add(fido, 1.0)
            b.add(kitty, 2.0)
            total = b.calc_trait_values('weight', lambda gen: sum(v * q for v, q in gen))
            assert total == pytest.approx(10.0 * 1.0 + 5.0 * 2.0)

    def test_resetting_bucketizers_clears_buckets(self):
        with CACHE_ONLY():
            fido = Animal(name='fido')
            fido.weight = 10.0
            bz = Bucketizer.by_breakpoints(Animal, lambda a: a.weight, 0.0, 20.0, XInf)
            b = Basket(base_class=Animal)
            b.bucketizers = [bz]
            b.add(fido)
            assert len(dict(b.all_buckets)) == 1

            b.bucketizers = []
            b.add(fido)
            assert isinstance(b.the_bucket, BucketDict)


class TestBasketRegressionGuards:
    """Regression tests for real bugs: wrong iteration API, embedded-list append, f_aggregator None."""

    def test_members_qtys_flattens_all_tagged_buckets(self):
        """members_qtys() must chain tags_buckets(); a broken ``all_buckets()`` call would raise TypeError."""
        with CACHE_ONLY():
            light = Animal(name='light_a')
            light.weight = 10.0
            heavy = Animal(name='heavy_a')
            heavy.weight = 90.0
            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 50.0],
                ['heavy', 50.0, XInf],
            )
            b = Basket(base_class=Animal)
            b.bucketizers = [bz]
            b.add(light)
            b.add(heavy)
            flat = list(b.members_qtys())
            assert len(flat) == 2
            members = {m for m, _ in flat}
            assert light in members
            assert heavy in members

    def test_f_aggregator_throw_false_returns_none_without_attrerror(self):
        """Missing NamedCallable member must yield None, not ``None.value`` (AttributeError)."""
        class OtherAgg(NamedCallable):
            OTHER = lambda g: 0

        with CACHE_ONLY():
            a = Animal(name='a')
            a.weight = 3.0
            b = Basket(base_class=Animal, aggregator_class=OtherAgg)
            b.add(a)
            # Trait lift for 'weight' looks up OTHER_AGG.WEIGHT — absent; aggregator_f must be None
            streamed = b.weight
            pairs = list(streamed)
            assert len(pairs) == 1
            assert pairs[0][0] == 3.0

    def test_add_bucketizer_persists_on_bucketizers_trait(self):
        """Embedded ``bucketizers`` list ignores in-place ``append``; replacement must persist."""
        with CACHE_ONLY():
            fido = Animal(name='fido')
            fido.weight = 10.0
            b = Basket(base_class=Animal)
            b.add(fido)
            assert b.bucketizers == []
            bz = Bucketizer.by_range(Animal, lambda a: a.weight, ['only', 0.0, XInf])
            b.add_bucketizer(bz)
            assert len(b.bucketizers) == 1
            assert b.bucketizers[0] is bz


# ---------------------------------------------------------------------------
# Bucketizer.by_class
# ---------------------------------------------------------------------------

class TestBucketizerByClass:
    def test_assigns_exact_class_as_tag(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_class(Animal)
            fido = Dog(name='fido')
            assert bz.calc_bucketizing_value(fido) is Dog
            assert bz.calc_bucket_tag(Dog) is Dog

    def test_unknown_subclass_tag_is_none_when_known_specified(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_class(Animal, Dog)
            kitty = Cat(name='kitty')
            bz_val = bz.calc_bucketizing_value(kitty)
            assert bz.calc_bucket_tag(bz_val) is None

    def test_known_subclass_gets_tag(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_class(Animal, Dog, Cat)
            fido = Dog(name='fido')
            bz_val = bz.calc_bucketizing_value(fido)
            assert bz.calc_bucket_tag(bz_val) is Dog

    def test_bad_base_class_raises(self):
        with pytest.raises(AssertionError, match='base_class must be a subclass of Traitable'):
            Bucketizer.by_class(int)

    def test_non_subclass_raises(self):
        with pytest.raises(AssertionError):
            Bucketizer.by_class(Animal, int)

    def test_basket_split_by_class(self):
        with CACHE_ONLY():
            fido = Dog(name='fido')
            kitty = Cat(name='kitty')
            bz = Bucketizer.by_class(Animal)
            b = Basket(base_class=Animal)
            b.bucketizers = [bz]
            b.add(fido)
            b.add(kitty)
            tags = {tag[0] for tag, _ in b.tags_buckets()}
            assert Dog in tags
            assert Cat in tags


# ---------------------------------------------------------------------------
# Bucketizer.by_feature
# ---------------------------------------------------------------------------

class TestBucketizerByFeature:
    def test_open_feature_no_known_tags(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_feature(Animal, lambda a: a.species)
            fido = Animal(name='fido')
            fido.species = 'canine'
            assert bz.calc_bucketizing_value(fido) == 'canine'
            assert bz.calc_bucket_tag('canine') == 'canine'

    def test_unknown_value_filtered_when_known_tags_given(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_feature(Animal, lambda a: a.species, 'feline', 'canine')
            assert bz.calc_bucket_tag('bovine') is None

    def test_known_value_accepted(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_feature(Animal, lambda a: a.species, 'feline', 'canine')
            assert bz.calc_bucket_tag('canine') == 'canine'

    def test_custom_bucket_tag_calc(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_feature(
                Animal,
                lambda a: a.weight,
                bucket_tag_calc=lambda w: 'heavy' if w > 50 else 'light',
            )
            fido = Animal(name='fido')
            fido.weight = 100.0
            bz_val = bz.calc_bucketizing_value(fido)
            assert bz.calc_bucket_tag(bz_val) == 'heavy'

    def test_non_callable_feature_raises(self):
        with pytest.raises(AssertionError, match='not callable'):
            Bucketizer.by_feature(Animal, 'not_a_callable')

    def test_basket_split_by_feature(self):
        with CACHE_ONLY():
            fido = Animal(name='fido')
            fido.species = 'canine'
            kitty = Animal(name='kitty')
            kitty.species = 'feline'
            bz = Bucketizer.by_feature(Animal, lambda a: a.species)
            b = Basket(base_class=Animal)
            b.bucketizers = [bz]
            b.add(fido)
            b.add(kitty)
            tags = {tag[0] for tag, _ in b.tags_buckets()}
            assert 'canine' in tags
            assert 'feline' in tags


# ---------------------------------------------------------------------------
# Bucketizer.by_range
# ---------------------------------------------------------------------------

class TestBucketizerByRange:
    def test_inclusive_interval_matches(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 50.0],
                ['heavy', 50.0, 200.0],
            )
            fido = Animal(name='fido')
            fido.weight = 25.0
            bz_val = bz.calc_bucketizing_value(fido)
            assert bz.calc_bucket_tag(bz_val) == 'light'

    def test_exclusive_interval_upper_bound(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ('light', 0.0, 50.0),
            )
            fido = Animal(name='fido')
            fido.weight = 50.0  # exclusive upper → not in 'light'
            bz_val = bz.calc_bucketizing_value(fido)
            assert bz.calc_bucket_tag(bz_val) is None

    def test_boundary_inclusive(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 50.0],
            )
            fido = Animal(name='fido')
            fido.weight = 50.0
            bz_val = bz.calc_bucketizing_value(fido)
            assert bz.calc_bucket_tag(bz_val) == 'light'

    def test_no_matching_interval_returns_none(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 50.0],
            )
            fido = Animal(name='fido')
            fido.weight = 200.0
            bz_val = bz.calc_bucketizing_value(fido)
            assert bz.calc_bucket_tag(bz_val) is None

    def test_xinf_as_upper_bound(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['any', 0.0, XInf],
            )
            fido = Animal(name='fido')
            fido.weight = 999_999.0
            bz_val = bz.calc_bucketizing_value(fido)
            assert bz.calc_bucket_tag(bz_val) == 'any'

    def test_basket_split_by_range(self):
        with CACHE_ONLY():
            light = Animal(name='light_animal')
            light.weight = 10.0
            heavy = Animal(name='heavy_animal')
            heavy.weight = 150.0
            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 50.0],
                ['heavy', 50.0, XInf],
            )
            b = Basket(base_class=Animal)
            b.bucketizers = [bz]
            b.add(light)
            b.add(heavy)
            bucket_contents = {tag[0]: list(bucket.members()) for tag, bucket in b.tags_buckets()}
            assert light in bucket_contents['light']
            assert heavy in bucket_contents['heavy']


# ---------------------------------------------------------------------------
# Bucketizer.by_breakpoints
# ---------------------------------------------------------------------------

class TestBucketizerByBreakPoints:
    def test_basic_split(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_breakpoints(Animal, lambda a: a.weight, 0.0, 50.0, 150.0, XInf)
            fido = Animal(name='fido')
            fido.weight = 25.0
            bz_val = bz.calc_bucketizing_value(fido)
            tag = bz.calc_bucket_tag(bz_val)
            assert tag is not None  # falls in [0,50) interval

    def test_value_below_first_breakpoint_is_none(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_breakpoints(Animal, lambda a: a.weight, 10.0, 50.0)
            fido = Animal(name='fido')
            fido.weight = 5.0
            bz_val = bz.calc_bucketizing_value(fido)
            assert bz.calc_bucket_tag(bz_val) is None

    def test_value_above_last_breakpoint_is_none(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_breakpoints(Animal, lambda a: a.weight, 0.0, 50.0)
            fido = Animal(name='fido')
            fido.weight = 100.0
            bz_val = bz.calc_bucketizing_value(fido)
            assert bz.calc_bucket_tag(bz_val) is None

    def test_include_last_includes_final_point(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_breakpoints(
                Animal, Animal.T.weight, 0.0, 50.0, include_last=True
            )
            fido = Animal(name='fido')
            fido.weight = 50.0
            bz_val = bz.calc_bucketizing_value(fido)
            assert bz.calc_bucket_tag(bz_val) is not None

    def test_include_last_with_xinf_raises(self):
        """include_last=True is rejected at construction time when the last breakpoint is XInf."""
        with CACHE_ONLY():
            with pytest.raises(TraitMethodError, match='meaningless'):
                Bucketizer.by_breakpoints(
                    Animal, Animal.T.weight, 0.0, 50.0, XInf, include_last=True
                )

    def test_unordered_breakpoints_raise(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_breakpoints(Animal, lambda a: a.weight, 50.0, 10.0)
            with pytest.raises(TraitMethodError, match='strict ascending order'):
                _ = bz.intervals  # triggers lazy build via runtime trait getter

    def test_none_breakpoint_raises(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_breakpoints(Animal, lambda a: a.weight, 0.0, None, 50.0)
            with pytest.raises(TraitMethodError, match='None is not a valid point'):
                _ = bz.intervals

    def test_single_breakpoint_yields_no_intervals(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_breakpoints(Animal, lambda a: a.weight, 0.0)
            assert bz.intervals == []


# ---------------------------------------------------------------------------
# Compound bucketizers (multiple)
# ---------------------------------------------------------------------------

class TestCompoundBucketizers:
    def test_two_bucketizers_create_compound_keys(self):
        with CACHE_ONLY():
            fido = Dog(name='fido')
            fido.weight = 25.0
            kitty = Cat(name='kitty')
            kitty.weight = 4.0

            bz_class = Bucketizer.by_class(Animal)
            bz_weight = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 20.0],
                ['heavy', 20.0, XInf],
            )

            b = Basket(base_class=Animal)
            b.bucketizers = [bz_class, bz_weight]
            b.add(fido)
            b.add(kitty)

            keys = {tag for tag, _ in b.tags_buckets()}
            assert (Dog, 'heavy') in keys
            assert (Cat, 'light') in keys

    def test_object_not_matching_all_bucketizers_is_excluded(self):
        with CACHE_ONLY():
            fido = Animal(name='fido')
            fido.weight = 25.0

            bz_species = Bucketizer.by_feature(Animal, lambda a: a.species, 'canine')
            bz_weight = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['any', 0.0, XInf],
            )

            b = Basket(base_class=Animal)
            b.bucketizers = [bz_species, bz_weight]
            fido.species = 'feline'  # not in known_tags for species bucketizer
            result = b.add(fido)
            assert not result  # feline not in ['canine'] → filtered


# ---------------------------------------------------------------------------
# add_bucketizer - incremental bucketing
# ---------------------------------------------------------------------------

class TestAddBucketizer:
    def test_add_bucketizer_splits_existing_members(self):
        with CACHE_ONLY():
            fido = Animal(name='fido')
            fido.weight = 10.0
            chonk = Animal(name='chonk')
            chonk.weight = 90.0

            b = Basket(base_class=Animal)
            b.add(fido)
            b.add(chonk)

            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 50.0],
                ['heavy', 50.0, XInf],
            )
            b.add_bucketizer(bz)

            bucket_members = {tag[0]: list(bucket.members()) for tag, bucket in b.tags_buckets()}
            assert fido in bucket_members['light']
            assert chonk in bucket_members['heavy']

    def test_add_bucketizer_excludes_unmatched_members(self):
        with CACHE_ONLY():
            fido = Animal(name='fido')
            fido.weight = 10.0
            # giant has weight outside any interval
            giant = Animal(name='giant')
            giant.weight = 1000.0

            b = Basket(base_class=Animal)
            b.add(fido)
            b.add(giant)

            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['normal', 0.0, 200.0],
            )
            b.add_bucketizer(bz)

            all_members = [m for _, bucket in b.tags_buckets() for m, _ in bucket.members_qtys()]
            assert fido in all_members
            assert giant not in all_members

    def test_add_bucketizers_multiple_at_once(self):
        with CACHE_ONLY():
            fido = Dog(name='fido2')
            fido.weight = 10.0
            kitty = Cat(name='kitty2')
            kitty.weight = 5.0

            b = Basket(base_class=Animal)
            b.add(fido)
            b.add(kitty)

            bz_class = Bucketizer.by_class(Animal)
            bz_weight = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 20.0],
                ['heavy', 20.0, XInf],
            )
            b.add_bucketizers([bz_class, bz_weight])

            keys = {tag for tag, _ in b.tags_buckets()}
            assert (Dog, 'light') in keys
            assert (Cat, 'light') in keys
            assert len(b.bucketizers) == 2

    def test_add_bucketizers_empty_list_is_noop(self):
        """add_bucketizers([]) must leave members and bucket structure untouched."""
        with CACHE_ONLY():
            fido = Animal(name='fido_noop')
            fido.weight = 10.0

            b = Basket(base_class=Animal)
            b.add(fido)
            assert fido in list(b.the_bucket.members())

            b.add_bucketizers([])

            # Single-bucket mode unchanged - fido still there, bucketizers still empty.
            assert b.bucketizers == []
            assert fido in list(b.the_bucket.members())

    def test_add_bucketizers_empty_list_preserves_tagged_structure(self):
        """add_bucketizers([]) on a basket that already has bucketizers must leave
        the tagged bucket structure and bucketizers list unchanged."""
        with CACHE_ONLY():
            fido = Animal(name='fido_noop2')
            fido.weight = 10.0
            chonk = Animal(name='chonk_noop2')
            chonk.weight = 90.0

            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 50.0],
                ['heavy', 50.0, XInf],
            )
            b = Basket(base_class=Animal)
            b.bucketizers = [bz]
            b.add(fido)
            b.add(chonk)

            b.add_bucketizers([])

            # Tagged structure and bucketizers list must be unchanged.
            assert len(b.bucketizers) == 1
            bucket_members = {tag[0]: list(bucket.members()) for tag, bucket in b.tags_buckets()}
            assert fido in bucket_members['light']
            assert chonk in bucket_members['heavy']


# ---------------------------------------------------------------------------
# bucketizers setter - setting bucketizers after members are already in basket
# ---------------------------------------------------------------------------

class TestBucketizersSetterAfterAdd:
    """Tests for the bucketizers setter.

    ``reset_mambers_on_set_bucketizers`` (default ``True``) controls whether
    setting ``basket.bucketizers`` clears existing members or re-sorts them.
    Tests that verify re-sorting behavior opt in with
    ``reset_mambers_on_set_bucketizers=False``.
    """

    # ------------------------------------------------------------------
    # Default behavior: reset_mambers_on_set_bucketizers=True (default)
    # ------------------------------------------------------------------

    def test_setter_default_clears_members(self):
        """With the default reset mode, assigning bucketizers discards all
        existing members — they must be re-added afterwards."""
        with CACHE_ONLY():
            fido = Animal(name='fido_clr')
            fido.weight = 10.0

            b = Basket(base_class=Animal)
            b.add(fido)
            assert fido in list(b.the_bucket.members())

            bz = Bucketizer.by_range(Animal, lambda a: a.weight, ['light', 0.0, XInf])
            b.bucketizers = [bz]  # reset=True → members cleared

            assert list(b.the_bucket.members()) == []
            assert dict(b.all_buckets) == {}

    def test_setter_default_add_after_bucketizers(self):
        """The normal workflow: set bucketizers, then add members.  With default
        reset mode this is the only reliable ordering."""
        with CACHE_ONLY():
            fido = Animal(name='fido_after')
            fido.weight = 10.0
            chonk = Animal(name='chonk_after')
            chonk.weight = 90.0

            b = Basket(base_class=Animal)
            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 50.0],
                ['heavy', 50.0, XInf],
            )
            b.bucketizers = [bz]
            b.add(fido)
            b.add(chonk)

            bucket_members = {tag[0]: list(bucket.members()) for tag, bucket in b.tags_buckets()}
            assert fido in bucket_members['light']
            assert chonk in bucket_members['heavy']

    def test_setter_default_replaces_not_extends_bucketizer_list(self):
        """Assigning to basket.bucketizers must replace the whole list, not
        append to it — this holds regardless of reset mode."""
        with CACHE_ONLY():
            b = Basket(base_class=Animal)

            bz_class = Bucketizer.by_class(Animal)
            b.bucketizers = [bz_class]
            assert len(b.bucketizers) == 1

            bz_weight = Bucketizer.by_range(Animal, lambda a: a.weight, ['light', 0.0, 50.0])
            b.bucketizers = [bz_weight]

            assert len(b.bucketizers) == 1
            assert b.bucketizers[0] is bz_weight

    def test_setter_default_empty_list_clears_members(self):
        """Setting bucketizers to [] with the default reset mode clears members."""
        with CACHE_ONLY():
            fido = Animal(name='fido_clr_empty')
            fido.weight = 10.0
            bz = Bucketizer.by_range(Animal, lambda a: a.weight, ['any', 0.0, XInf])
            b = Basket(base_class=Animal)
            b.bucketizers = [bz]
            b.add(fido)
            assert fido in list(b.tags_buckets())[0][1].members()

            b.bucketizers = []  # reset=True → members lost
            assert b.bucketizers == []
            assert list(b.the_bucket.members()) == []

    # ------------------------------------------------------------------
    # Rebucketing behavior: reset_mambers_on_set_bucketizers=False
    # ------------------------------------------------------------------

    def test_setter_rebuckets_members_added_before(self):
        """With reset_mambers_on_set_bucketizers=False, setting bucketizers
        after members are already in the basket re-sorts those members."""
        with CACHE_ONLY():
            fido = Animal(name='fido_s')
            fido.weight = 10.0
            chonk = Animal(name='chonk_s')
            chonk.weight = 90.0

            b = Basket(base_class=Animal, reset_mambers_on_set_bucketizers=False)
            b.add(fido)
            b.add(chonk)
            assert b.bucketizers == []

            bz = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 50.0],
                ['heavy', 50.0, XInf],
            )
            b.bucketizers = [bz]

            bucket_members = {tag[0]: list(bucket.members()) for tag, bucket in b.tags_buckets()}
            assert fido in bucket_members['light']
            assert chonk in bucket_members['heavy']
            assert len(b.bucketizers) == 1

    def test_setter_replaces_not_extends_existing_bucketizers(self):
        """With rebucketing mode, assigning bucketizers replaces the list and
        re-sorts existing members under the new scheme."""
        with CACHE_ONLY():
            fido = Animal(name='fido_r')
            fido.weight = 10.0
            fido.species = 'canine'

            b = Basket(base_class=Animal, reset_mambers_on_set_bucketizers=False)
            b.add(fido)

            bz_species = Bucketizer.by_feature(Animal, lambda a: a.species, 'canine')
            b.bucketizers = [bz_species]
            assert len(b.bucketizers) == 1

            bz_weight = Bucketizer.by_range(Animal, lambda a: a.weight, ['light', 0.0, 50.0])
            b.bucketizers = [bz_weight]

            # Only bz_weight remains; old species structure is gone, weight tags present
            assert len(b.bucketizers) == 1
            assert b.bucketizers[0] is bz_weight
            keys = list(b.tags_buckets())
            assert all('canine' not in str(tag) for tag, _ in keys)
            assert any(tag == ('light',) for tag, _ in b.tags_buckets())

    def test_setter_with_two_bucketizers_at_once(self):
        """With rebucketing mode, setting two bucketizers at once produces
        compound (class, weight) keys."""
        with CACHE_ONLY():
            fido = Dog(name='fido_t')
            fido.weight = 10.0
            kitty = Cat(name='kitty_t')
            kitty.weight = 5.0

            b = Basket(base_class=Animal, reset_mambers_on_set_bucketizers=False)
            b.add(fido)
            b.add(kitty)

            bz_class = Bucketizer.by_class(Animal)
            bz_weight = Bucketizer.by_range(
                Animal,
                lambda a: a.weight,
                ['light', 0.0, 20.0],
            )
            b.bucketizers = [bz_class, bz_weight]

            keys = {tag for tag, _ in b.tags_buckets()}
            assert (Dog, 'light') in keys
            assert (Cat, 'light') in keys
            assert len(b.bucketizers) == 2

    def test_setter_empty_list_preserves_members_in_the_bucket(self):
        """With rebucketing mode, setting bucketizers to [] collapses all
        segments back into the single the_bucket without losing members."""
        with CACHE_ONLY():
            fido = Animal(name='fido_empty')
            fido.weight = 10.0
            bz = Bucketizer.by_range(Animal, lambda a: a.weight, ['any', 0.0, XInf])
            b = Basket(base_class=Animal, reset_mambers_on_set_bucketizers=False)
            b.bucketizers = [bz]
            b.add(fido)
            assert len(b.bucketizers) == 1

            b.bucketizers = []
            assert b.bucketizers == []

            # fido must survive the reset – no re-add required.
            assert fido in list(b.the_bucket.members())

    def test_setter_invalid_input_is_rejected(self):
        """Non-list or list-with-non-bucketizers must be rejected with a RuntimeError."""
        with CACHE_ONLY():
            b = Basket(base_class=Animal)
            with pytest.raises(RuntimeError, match='must be a list'):
                b.bucketizers = 'not_a_list'
            assert b.bucketizers == []  # original value unchanged

            with pytest.raises(RuntimeError, match='must be a list'):
                b.bucketizers = [42]  # list, but element is not a Bucketizer
            assert b.bucketizers == []


# ---------------------------------------------------------------------------
# Interval helpers
# ---------------------------------------------------------------------------

class TestInterval:
    def test_inclusive_interval(self):
        iv = Interval(0.0, 10.0, inclusive=True)
        assert iv.test_f(0.0)
        assert iv.test_f(5.0)
        assert iv.test_f(10.0)
        assert not iv.test_f(10.001)

    def test_exclusive_interval(self):
        iv = Interval(0.0, 10.0, inclusive=False)
        assert iv.test_f(0.0)
        assert iv.test_f(9.999)
        assert not iv.test_f(10.0)

    def test_custom_label(self):
        iv = Interval(0.0, 10.0, label='zero_to_ten')
        assert iv.label == 'zero_to_ten'

    def test_auto_label_finite(self):
        iv = Interval(0.0, 10.0, inclusive=True)
        assert '0.0' in iv.label
        assert '10.0' in iv.label
        assert iv.label.startswith('[')
        assert iv.label.endswith(']')

    def test_auto_label_xinf_upper(self):
        iv = Interval(0.0, XInf, inclusive=True)
        assert iv.label.endswith(')')  # XInf upper → open

    def test_auto_label_minf_lower(self):
        iv = Interval(-XInf, 10.0, inclusive=True)
        assert iv.label.startswith('(')  # -∞ lower → open


# ---------------------------------------------------------------------------
# Serialization - embedded bucketizers
# ---------------------------------------------------------------------------

class TestBucketizersEmbeddedSerialization:
    """Verify that bucketizers carrying T.EMBEDDED are serialized inline.

    The embedded-list format is a compact sequence where a type-path string is
    emitted before the first object of each new class, followed by one data dict
    per object.  Consecutive objects of the same class share the type entry::

        1 BucketizerByClass  → [type_str, data_dict]
        2 BucketizerByClass  → [type_str, data_dict, data_dict]
        BucketizerByClass + BucketizerByRange → [type_str_cls, data1, type_str_rng, data2]

    A non-embedded (reference) list would instead contain ``{'_id': '...'}`` dicts.
    We use ``by_class`` without subclasses (no lambdas, no class refs in buckets_spec)
    so the test stays fully serializable.
    """

    def _inner(self, basket: Basket) -> dict:
        """Return the traits dict from serialize_object(), stripping any _obj wrapper."""
        s = basket.serialize_object()
        return s['_obj'] if '_obj' in s else s

    def test_bucketizers_serialized_as_inline_objects(self):
        """A single bucketizer is serialized as [type_path, data_dict]."""
        with CACHE_ONLY():
            bz = Bucketizer.by_class(Animal)
            b = Basket(base_class=Animal)
            b.add_bucketizer(bz)

            inner = self._inner(b)
            bz_list = inner.get('bucketizers', [])
            assert len(bz_list) >= 2, f"Unexpected format: {bz_list!r}"
            # Type entry is a class-path string, data entry is a dict.
            type_entry = bz_list[0]
            assert isinstance(type_entry, str) and 'BucketizerByClass' in type_entry, (
                f"First element should be a class-path string, got: {type_entry!r}"
            )
            # No element is an _id reference dict.
            assert all(
                not (isinstance(x, dict) and '_id' in x) for x in bz_list
            ), "Bucketizers must not be serialized as ID references"

    def test_two_bucketizers_both_embedded(self):
        """Two same-class bucketizers share one type entry: [type, data1, data2]."""
        with CACHE_ONLY():
            bz1 = Bucketizer.by_class(Animal)
            bz2 = Bucketizer.by_class(Animal)
            b = Basket(base_class=Animal)
            b.add_bucketizer(bz1)
            b.add_bucketizer(bz2)

            inner = self._inner(b)
            bz_list = inner.get('bucketizers', [])
            # Same-class compact form: [type_str, data_dict, data_dict]
            assert bz_list and isinstance(bz_list[0], str), (
                f"Expected type-path string as first element, got: {bz_list!r}"
            )
            # All data entries must be dicts without _id
            assert all(
                not (isinstance(x, dict) and '_id' in x) for x in bz_list
            ), "Bucketizers must not be serialized as ID references"

    def test_empty_bucketizers_serializes_as_empty_list(self):
        with CACHE_ONLY():
            b = Basket(base_class=Animal)
            inner = self._inner(b)
            assert inner.get('bucketizers') == []


# ---------------------------------------------------------------------------
# Basketable mixin - recursive contents traversal
# ---------------------------------------------------------------------------

class TestBasketable:
    """
    Portfolio → Book → Trade → Instrument hierarchy mirroring the manual test.
    Instrument is a plain Traitable leaf (not Basketable).
    Trade, Book, and Portfolio are Basketable intermediate nodes with proper T()/RT() traits.
    Portfolio holds two separate Basket traits: portfolios (sub-portfolios) and books.
    """

    class Instrument(Traitable):
        ticker: str   = T(T.ID)
        price:  float = T()

    class Trade(Traitable, Basketable, bucket_shape=BUCKET_SHAPE.DICT):
        name:        str    = T(T.ID)
        instruments: Basket = T()

        def members_qtys(self):
            return self.instruments.members_qtys()

    class Book(Traitable, Basketable, bucket_shape=BUCKET_SHAPE.SET):
        name:        str    = T(T.ID)
        trade_names: list   = T()
        trades:      Basket = RT()

        def trades_get(self) -> Basket:
            basket = Basket(base_class=TestBasketable.Trade)
            for n in self.trade_names:
                basket.add(TestBasketable.Trade.existing_instance(name=n))
            return basket

        def members_qtys(self):
            return self.trades.members_qtys()

    class Portfolio(Traitable, Basketable, bucket_shape=BUCKET_SHAPE.SET):
        name:            str    = T(T.ID)
        book_names:      list   = T()
        portfolio_names: list   = T()
        books:           Basket = RT()
        portfolios:      Basket = RT()

        def books_get(self) -> Basket:
            basket = Basket(base_class=TestBasketable.Book)
            for n in self.book_names:
                basket.add(TestBasketable.Book.existing_instance(name=n))
            return basket

        def portfolios_get(self) -> Basket:
            basket = Basket(base_class=TestBasketable.Portfolio, subclasses_allowed=False)
            for n in self.portfolio_names:
                basket.add(TestBasketable.Portfolio.existing_instance(name=n))
            return basket

        def members_qtys(self):
            return itertools.chain(self.portfolios.members_qtys(), self.books.members_qtys())

    def test_contents_trade_to_instrument(self):
        """Trade → Instrument: one Basketable hop, leaf is plain Traitable."""
        with CACHE_ONLY():
            aapl = self.Instrument(ticker='bsk_AAPL')
            aapl.price = 189.0
            msft = self.Instrument(ticker='bsk_MSFT')
            msft.price = 420.0

            t1 = self.Trade(name='bsk_T1')
            t1.instruments = Basket(base_class=self.Instrument)
            t1.instruments.add(aapl, 10.0)
            t1.instruments.add(msft, 5.0)

            basket = Basket(base_class=self.Instrument)
            t1.contents(basket)

            qtys = dict(basket.the_bucket.members_qtys())
            assert qtys[aapl] == pytest.approx(10.0)
            assert qtys[msft] == pytest.approx(5.0)

    def test_contents_portfolio_book_trade_instrument(self):
        """Portfolio → Book → Trade → Instrument: full four-level traversal."""
        with CACHE_ONLY():
            aapl = self.Instrument(ticker='bsk2_AAPL')
            aapl.price = 189.0
            msft = self.Instrument(ticker='bsk2_MSFT')
            msft.price = 420.0

            t1 = self.Trade(name='bsk2_T1')
            t1.instruments = Basket(base_class=self.Instrument)
            t1.instruments.add(aapl, 10.0)
            t1.instruments.add(msft, 5.0)

            book = self.Book(name='bsk2_Equities')
            book.trade_names = ['bsk2_T1']

            portfolio = self.Portfolio(name='bsk2_GlobalFund')
            portfolio.book_names      = ['bsk2_Equities']
            portfolio.portfolio_names = []

            instr_basket = Basket(base_class=self.Instrument)
            portfolio.contents(instr_basket)

            qtys = dict(instr_basket.the_bucket.members_qtys())
            assert qtys[aapl] == pytest.approx(10.0)
            assert qtys[msft] == pytest.approx(5.0)

    def test_contents_nested_portfolios(self):
        """Top → P1 (sub-portfolio) → Book → Trade → Instrument: portfolio nesting."""
        with CACHE_ONLY():
            aapl = self.Instrument(ticker='bsk3_AAPL')
            aapl.price = 189.0

            t1 = self.Trade(name='bsk3_T1')
            t1.instruments = Basket(base_class=self.Instrument)
            t1.instruments.add(aapl, 10.0)

            book = self.Book(name='bsk3_Equities')
            book.trade_names = ['bsk3_T1']

            p1 = self.Portfolio(name='bsk3_P1')
            p1.book_names      = ['bsk3_Equities']
            p1.portfolio_names = []

            top = self.Portfolio(name='bsk3_Top')
            top.portfolio_names = ['bsk3_P1']
            top.book_names      = []

            instr_basket = Basket(base_class=self.Instrument)
            top.contents(instr_basket)

            qtys = dict(instr_basket.the_bucket.members_qtys())
            assert qtys[aapl] == pytest.approx(10.0)

    def test_contents_stop_at_trade_level(self):
        """base_class=Trade stops traversal at Trade; does not descend into Instruments."""
        with CACHE_ONLY():
            aapl = self.Instrument(ticker='bsk4_AAPL')
            aapl.price = 189.0

            t1 = self.Trade(name='bsk4_T1')
            t1.instruments = Basket(base_class=self.Instrument)
            t1.instruments.add(aapl, 10.0)

            book = self.Book(name='bsk4_Equities')
            book.trade_names = ['bsk4_T1']

            portfolio = self.Portfolio(name='bsk4_GlobalFund')
            portfolio.book_names      = ['bsk4_Equities']
            portfolio.portfolio_names = []

            trade_basket = Basket(base_class=self.Trade)
            portfolio.contents(trade_basket)

            members = list(trade_basket.the_bucket.members())
            assert t1 in members
            assert aapl not in members


# ---------------------------------------------------------------------------
# Bucketizer validation helpers
# ---------------------------------------------------------------------------

class TestBucketizerValidation:
    def test_verify_base_class_with_non_class_raises(self):
        with pytest.raises(AssertionError, match='base_class must be a subclass of Traitable'):
            Bucketizer.verify_base_class('not_a_class')

    def test_verify_base_class_with_non_traitable_raises(self):
        with pytest.raises(AssertionError, match='base_class must be a subclass of Traitable'):
            Bucketizer.verify_base_class(int)

    def test_verify_custom_f_with_non_callable_raises(self):
        with pytest.raises(AssertionError, match='not callable'):
            Bucketizer.verify_custom_f('not_callable', 'test_label')

    def test_verify_custom_f_callable_passes(self):
        Bucketizer.verify_custom_f(lambda x: x, 'test_label')

    def test_verify_custom_f_wrong_arg_count_raises(self):
        with pytest.raises(AssertionError):
            Bucketizer.verify_custom_f(lambda x, y: x, 'label', arg_data_type=int)

    def test_bucket_tags_getter(self):
        with CACHE_ONLY():
            bz = Bucketizer.by_feature(Animal, lambda a: a.species, 'canine', 'feline')
            assert bz.bucket_tags == {'canine', 'feline'}
