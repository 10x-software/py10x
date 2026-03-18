from __future__ import annotations

import bisect
import functools
from typing import Callable, Any
import inspect
from types import GeneratorType

from core_10x.traitable import Traitable, Trait, T, RT, RC, RC_TRUE, XNone
from core_10x.named_constant import NamedConstant, NamedCallable
from core_10x.xinf import XInf


class ComboIter:
    def __init__(self, *iterators):
        assert iterators
        self.iterators = iterators
        self.i = 0
        self.it = iterators[0]

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return self.it.__next__()
        except StopIteration:
            self.i += 1
            if self.i == len(self.iterators):
                raise StopIteration

            self.it = self.iterators[self.i]
            return self.it.__next__()


class Bucket(Traitable):
    def calc_trait_values(self, trait_name: str, aggregator_f: Callable):
        data_gen = ( (member.get_value(trait_name), qty) for member, qty in self.members_qtys() )
        return data_gen if not aggregator_f else aggregator_f(data_gen)

    def calc_trait_values_with_args(self, trait_name: str, aggregator_f: Callable, *args):
        data_gen = ( (member.get_value(trait_name, *args), qty) for member, qty in self.members_qtys() )
        return data_gen if not aggregator_f else aggregator_f(data_gen)

    def calc_method(self, method_name: str, aggregator_f: Callable, *args, **kwargs):
        data_gen = ( (getattr(member, method_name)(*args, **kwargs), qty) for member, qty in self.members_qtys() )
        return data_gen if not aggregator_f else aggregator_f(data_gen)


    def _insert(self, obj: Basketable, qty: float):     raise NotImplementedError
    def _insert_bucket(self, bucket: Bucket):           raise NotImplementedError
    def is_member(self, obj: Basketable) -> bool:       raise NotImplementedError
    def members(self):                                  raise NotImplementedError
    def members_qtys(self):                             raise NotImplementedError

#class BucketSet(Bucket, embeddable = True):
class BucketSet(Bucket):
    data: set['Basketable'] = T(T.OFFGRAPH_SET)

    def _insert(self, obj: Basketable, qty: float):
        self.data.add(obj)

    def _insert_bucket(self, bucket: BucketSet):
        self.data.update(bucket.data)

    def is_member(self, obj: Basketable) -> bool:
        return obj in self.data

    class Iter:
        def __init__(self, members: set):
            self.it = iter(members)

        def __iter__(self):
            return self

        def __next__(self):
            return (self.it.__next__(), 1.)

    def members(self):
        return iter(self.data)

    def members_qtys(self):
        return self.Iter(self.data)

class BucketList(Bucket, embeddable = True):
    data: list = T(T.OFFGRAPH_SET)

    def _insert(self, obj: Basketable, qty: float):
        self.data.append(obj)

    def _insert_bucket(self, bucket: BucketList):
        self.data.extend(bucket.data)

    def is_member(self, obj: Basketable) -> bool:
        return obj in self.data

    class Iter:
        def __init__(self, members: list):
            self.it = iter(members)

        def __iter__(self):
            return self

        def __next__(self):
            return (self.it.__next__(), 1.)

    def members(self):
        return iter(self.data)

    def members_qtys(self):
        return self.Iter(self.data)

#class BucketDict(Bucket, embeddable = True):
class BucketDict(Bucket):
    data: dict['Basketable', float] = T(T.OFFGRAPH_SET)

    def _insert(self, obj: Basketable, qty: float = 1):
        data = self.data
        ex_qty = data.get(obj, 0.)
        data[obj] = ex_qty + qty

    def _insert_bucket(self, bucket: BucketDict):
        data = self.data
        for obj, qty in bucket.data.items():
            ex_qty = data.get(obj, 0.)
            data[obj] = ex_qty + qty

    def is_member(self, obj: Basketable) -> bool:
        return obj in self.data

    def members(self):
        return self.data.keys()

    def members_qtys(self):
        return self.data.items()

class BUCKET_SHAPE(NamedConstant):
    SET     = BucketSet
    DICT    = BucketDict
    LIST    = BucketList

class Basketable:
    s_bucket_shape: BUCKET_SHAPE = None
    def __init_subclass__(cls, bucket_shape: BUCKET_SHAPE = None, **kwargs):
        if bucket_shape is not None:
            cls.s_bucket_shape = bucket_shape

        super().__init_subclass__(**kwargs)

    def contents(self, target_class: type[Basketable], basket: Basket, qty: float = 1.):
        for member, mem_qty in self.members_qtys():
            if isinstance(member, target_class):
                basket.add(member, qty * mem_qty)
            else:
                member.contents(target_class, basket, qty = qty * mem_qty)


    def is_member(self, obj: Basketable) -> bool:   raise NotImplementedError
    #def baskets(self):                              raise NotImplementedError
    def members_qtys(self):                         raise NotImplementedError

"""
Example of aggregator:

class FIN_AGGREGATOR(NamedCallable):
    PRICE       = FinInstrument.aggregate_price
    PRICE_CCY   = Portfolio.aggregate_price
    LIFE_CYCLE  = LifeCycler.aggregate_life_cycle
    LEAVES      = lambda basket:    raise NotSupportedError 
"""
class Basket(Traitable):
    base_class: type[Basketable]            = T(T.NOT_EMPTY)
    subclasses_allowed: bool                = T(True)
    aggregator_class: type[NamedCallable]   = T()

    def is_simple(self) -> bool:
        return False

    def all_buckets(self):
        raise NotImplementedError

    def all_members(self):
        return ComboIter(*tuple(bucket.members() for bucket in self.buckets.values()))

    def __getattr__(self, method_name: str):
        base_class = self.base_class
        trait = getattr(base_class, method_name, None)
        if trait is None:
            return None

        aggregator_f = self.f_aggregator(method_name, throw = False)
        if isinstance(trait, Trait):
            if not trait.getter_params:
                return self.calc_trait_values(method_name, aggregator_f)

            return functools.partial(self._lift_by_trait_name, method_name, aggregator_f)

        if callable(trait):
            return functools.partial(self._lift_by_method_name, method_name, aggregator_f)

        return None

    def calc_trait_values(self, trait_name: str, aggregator_f: Callable):
        if self.is_simple():
            for _, bucket in self.all_buckets():
                return bucket.calc_trait_values(trait_name, aggregator_f)

        return {
            tag: bucket.calc_trait_values(trait_name, aggregator_f)
            for tag, bucket in self.all_buckets()
        }

    def _lift_by_trait_name(self, trait_name: str, aggregator_f: Callable, *args):
        bucket: Bucket
        if self.is_simple():
            for _, bucket in self.all_buckets():
                return bucket.calc_trait_values_with_args(trait_name, aggregator_f, *args)

        return {
            tag: bucket.calc_trait_values_with_args(trait_name, aggregator_f, *args)
            for tag, bucket in self.all_buckets()
        }

    def _lift_by_method_name(self, method_name: str, aggregator_f: Callable, *args, **kwargs):
        bucket: Bucket
        if self.is_simple():
            for _, bucket in self.all_buckets():
                return bucket.calc_method(method_name, aggregator_f, *args, **kwargs)

        return {
            tag: bucket.calc_method(method_name, aggregator_f, *args, **kwargs)
            for tag, bucket in self.all_buckets()
        }

    def finalize_results(self, results):
        if isinstance(results, GeneratorType):
            return list(results)

        if isinstance(results, dict):
            return { tag: list(r) if isinstance(r, GeneratorType) else r for tag, r in results.items() }

        return results

    def f_aggregator(self, method_name: str, throw = True) -> Callable:
        f = self.aggregator_class.s_dir.get(method_name.upper())
        if throw and f is None:
            raise AssertionError(f"Basket: aggregator for method '{method_name}' is not defined")
        return f

    def new_bucket(self) -> Bucket:
        return self.base_class.s_bucket_shape.value()

    def is_acceptable(self, obj: Basketable) -> bool:
        return isinstance(obj, self.base_class) if self.subclasses_allowed else obj.__class__ is self.base_class

    def add(self, obj: Basketable, qty: float = 1.) -> bool:
        raise NotImplementedError

    @classmethod
    def verify_base_class(cls, base_class):
        if not base_class or not inspect.isclass(base_class) or not issubclass(base_class, Basketable):
            raise AssertionError('base_class must be a subclass of Basketable')

    @classmethod
    def verify_custom_f(cls, custom_f, label: str, arg_data_type: type = None):
        if isinstance(custom_f, NamedCallable):
            custom_f = custom_f.value

        if not callable(custom_f):
            raise AssertionError(f'{label}: {custom_f} is not callable')

        if arg_data_type is not None:
            sig = inspect.signature(custom_f)
            params = list(sig.parameters.values())
            if len(params) != 1:
                raise AssertionError(f'{label}: {custom_f} must accept exactly one parameter')
            p = params[0]
            dtype = p.annotation
            if not dtype is inspect.Signature.empty and not dtype is arg_data_type:
                raise AssertionError(f'{label}: {custom_f} must accept single {arg_data_type}')

    @classmethod
    def simple(cls, base_class: type[Basketable], subclasses_allowed = True) -> Basket:
        cls.verify_base_class(base_class)
        return SimpleBasket(base_class = base_class, subclasses_allowed = subclasses_allowed)

    @classmethod
    def by_class(cls, base_class: type[Basketable], *known_subclasses) -> Basket:
        cls.verify_base_class(base_class)
        if known_subclasses:
            if not all(inspect.isclass(ca) and issubclass(ca, base_class) for ca in known_subclasses):
                raise AssertionError(f'Each class in subclasses_allowed must be a subclass of {base_class}')

        return BasketByClass(base_class = base_class, buckets_spec = set(known_subclasses))

    @classmethod
    def by_feature(cls, base_class: type[Basketable], feature_calc, *buckets_spec, bucket_tag_calc = None) -> Basket:
        cls.verify_base_class(base_class)
        cls.verify_custom_f(feature_calc, 'feature_calc')
        if not bucket_tag_calc:
            return BasketByFeature(base_class = base_class, f_bucketizing_value = feature_calc, buckets_spec = buckets_spec)

        cls.verify_custom_f(bucket_tag_calc, 'bucket_tag_calc')
        return BasketByFeature(base_class = base_class, f_bucketizing_value = feature_calc, f_bucket_tag = bucket_tag_calc, buckets_spec = buckets_spec)

    @classmethod
    def by_range(cls, base_class: type[Basketable], value_for_range_calc, *intervals_spec) -> Basket:
        cls.verify_base_class(base_class)
        cls.verify_custom_f(value_for_range_calc, 'value_for_range_calc')
        return BasketByRange(base_class = base_class, f_bucketizing_value = value_for_range_calc, buckets_spec = intervals_spec)

    @classmethod
    def by_breakpoints(cls, base_class: type[Basketable], value_for_range_calc, *breakpoints) -> Basket:
        cls.verify_base_class(base_class)
        cls.verify_custom_f(value_for_range_calc, 'value_for_range_calc')
        return BasketByBreakPoints(base_class = base_class, f_bucketizing_value = value_for_range_calc, buckets_spec = breakpoints)

class SimpleBasket(Basket):
    bucket: Bucket = T(T.OFFGRAPH_SET)

    def bucket_get(self) -> Bucket:
        return self.new_bucket()

    def is_simple(self) -> bool:
        return True

    def add(self, obj: Basketable, qty: float = 1.) -> bool:
        if not self.is_acceptable(obj):
            return False

        self.bucket._insert(obj, qty)
        return True

class ComboBasket(Basket):
    buckets_spec: list              = T()
    buckets: dict[Any, Bucket]      = T(T.OFFGRAPH_SET)

    bucket_tags: set                = RT()

    def bucket_tags_get(self) -> set:
        return set(self.buckets_spec)

    def num_buckets(self) -> int:
        return len(self.buckets)

    def calc_bucketizing_value(self, obj: Basketable):
        raise NotImplementedError

    def calc_bucket_tag(self, bucketizing_value):
        known_tags = self.bucket_tags
        return bucketizing_value if not known_tags or bucketizing_value in known_tags else None

    def add(self, obj: Basketable, qty: float = 1.) -> bool:
        if not self.is_acceptable(obj):
            return False

        bucketizing_value = self.calc_bucketizing_value(obj)
        tag = self.calc_bucket_tag(bucketizing_value)
        if tag is None:
            return False

        all_buckets = self.buckets
        bucket = all_buckets.get(tag)
        if bucket is None:
            bucket = self.new_bucket()
            all_buckets[tag] = bucket
        bucket._insert(obj, qty)
        return True

    def all_buckets(self):
        return self.buckets.items()

    def members_by_bucket(self, bucket_tag):
        bucket = self.buckets.get(bucket_tag, XNone)
        return bucket.members()


class BasketByClass(ComboBasket):
    def is_acceptable(self, obj: Basketable) -> bool:
        return isinstance(obj, self.base_class)

    def calc_bucketizing_value(self, obj: Basketable):
        return obj.__class__

class BasketByFeature(ComboBasket):
    f_bucketizing_value: NamedCallable  = T(T.NOT_EMPTY)
    f_bucket_tag: NamedCallable         = T()

    def calc_bucketizing_value(self, obj: Basketable):
        return self.f_bucketizing_value.value(obj)

    def calc_bucket_tag(self, bucketizing_value):
        f_bucket_tag = self.f_bucket_tag
        return f_bucket_tag.value(bucketizing_value) if f_bucket_tag else super().calc_bucket_tag(bucketizing_value)

class Interval:
    def __init__(self, a, b, inclusive = True, label: str = None):
        if inclusive:
            self.test_f = lambda v: a <= v and v <= b
        else:
            self.test_f = lambda v: a <= v and v < b

        if label is None:
            left_bracket = '(' if a is -XInf else '['
            right_bracket = ')' if b is XInf or not inclusive else ']'
            label = f'{left_bracket} {a} : {b} {right_bracket}'
        self.label = label

class BasketByRange(BasketByFeature):
    """
    interval    := [ label, low, high ]         #-- low <= x <= high: 'label'
                |= [ low, high ]                #-- same as [ '[low - high]', low, high ]
                |= ( label, low, high )         #-- low <= x < high: 'label'
                |= ( low, high )                #-- same as ( '[low - high )', low, high )
    """
    intervals: list[Interval]   = RT()

    def intervals_get(self) -> list:
        res = []
        for spec in self.buckets_spec:
            if isinstance(spec, list):
                inclusive = True
            elif isinstance(spec, tuple):
                inclusive = False
            else:
                raise TypeError('Each interval must either be list or tuple')

            n = len(spec)
            if n < 2 or n > 3:
                raise ValueError('Each interval must be either <label, low, high> or <low, high>')

            if n == 3:
                label, low, high = spec
                interval = Interval(low, high, inclusive = inclusive, label = label)
            else:
                low, high = spec
                interval = Interval(low, high, inclusive = inclusive)

            res.append(interval)

        return res

    def calc_bucket_tag(self, bucketizing_value) -> str:
        interval: Interval
        for interval in self.intervals:
            if interval.test_f(bucketizing_value):
                return interval.label

        return None

class BasketByBreakPoints(BasketByFeature):
    include_last: bool          = T(False)

    intervals: list[Interval]   = RT()

    def intervals_get(self) -> list:
        points = self.buckets_spec
        n = len(points)
        if n < 2:
            return []

        res = []
        include_last = self.include_last
        low = points[0]
        for i in range(1, n):
            point = points[i]
            if point is None:
                raise ValueError('None is not a valid point')

            try:
                rc = low < point
            except Exception:
                raise ValueError(f'Uncomparable points detected: ({low}, {point})')

            if not rc:
                raise ValueError(f'Points must be in strict ascending order: ({low}, {point})')

            inclusive = include_last if i == n - 1 else True
            interval = Interval(low, point, inclusive = inclusive)
            res.append(interval)

            low = point

        return res

    def calc_bucket_tag(self, bucketizing_value) -> str:
        break_points = self.buckets_spec
        intervals = self.intervals

        i = bisect.bisect_right(break_points, bucketizing_value) - 1
        if i < 0:
            return None

        if i == len(intervals):
            if not self.include_last:
                return None

            last = intervals[-1]
            return last.label if bucketizing_value == break_points[-1] else None

        return intervals[i].label


