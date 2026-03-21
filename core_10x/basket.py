from __future__ import annotations

import bisect
import functools
from typing import Callable
import inspect
from types import GeneratorType
import itertools

from core_10x import trait
from core_10x.traitable import Traitable, Trait, T, RT, RC, RC_TRUE, XNone
from core_10x.named_constant import NamedConstant, NamedCallable
from core_10x.xinf import XInf


#-- TODO: uncomment when T.EMBEDDED is not required to hold an embeddable
#class Bucket(Traitable, root_class = True, embeddable = True):
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


    def _insert(self, obj: Traitable, qty: float):      raise NotImplementedError
    def _insert_bucket(self, bucket: Bucket):           raise NotImplementedError
    def is_member(self, obj: Traitable) -> bool:        raise NotImplementedError
    def members(self):                                  raise NotImplementedError
    def members_qtys(self):                             raise NotImplementedError

class BucketSet(Bucket):
    data: set[Traitable] = T(T.STICKY)

    def _insert(self, obj: Traitable, qty: float):
        self.data.add(obj)

    def _insert_bucket(self, bucket: BucketSet):
        self.data.update(bucket.data)

    def is_member(self, obj: Traitable) -> bool:
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

class BucketList(Bucket):
    data: list = T(T.STICKY)

    def _insert(self, obj: Traitable, qty: float):
        self.data.append(obj)

    def _insert_bucket(self, bucket: BucketList):
        self.data.extend(bucket.data)

    def is_member(self, obj: Traitable) -> bool:
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

class BucketDict(Bucket):
    data: dict[Traitable, float] = T(T.STICKY)

    def _insert(self, obj: Traitable, qty: float = 1):
        data = self.data
        ex_qty = data.get(obj, 0.)
        data[obj] = ex_qty + qty

    def _insert_bucket(self, bucket: BucketDict):
        data = self.data
        for obj, qty in bucket.data.items():
            ex_qty = data.get(obj, 0.)
            data[obj] = ex_qty + qty

    def is_member(self, obj: Traitable) -> bool:
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

    def contents(self, basket: Basket, qty: float = 1.):
        target_class = basket.base_class
        for member, mem_qty in self.members_qtys():
            if isinstance(member, target_class):
                basket.add(member, qty * mem_qty)
            else:
                member.contents(basket, qty = qty * mem_qty)


    def is_member(self, obj: Basketable) -> bool:   raise NotImplementedError
    def members_qtys(self):                         raise NotImplementedError


class Bucketizer(Traitable, embeddable = True):
    buckets_spec: list  = T()
    bucket_tags: set    = RT()

    def bucket_tags_get(self) -> set:
        return set(self.buckets_spec)

    def calc_bucketizing_value(self, obj: Traitable):
        raise NotImplementedError

    def calc_bucket_tag(self, bucketizing_value):
        known_tags = self.bucket_tags
        return bucketizing_value if not known_tags or bucketizing_value in known_tags else None

    @classmethod
    def verify_base_class(cls, base_class):
        if not base_class or not inspect.isclass(base_class) or not issubclass(base_class, Traitable):
            raise AssertionError('base_class must be a subclass of Traitable')

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
    def by_class(cls, base_class: type[Traitable], *known_subclasses) -> Bucketizer:
        cls.verify_base_class(base_class)
        if known_subclasses:
            if not all(inspect.isclass(ca) and issubclass(ca, base_class) for ca in known_subclasses):
                raise AssertionError(f'Each class in subclasses_allowed must be a subclass of {base_class}')

        return BucketizerByClass(base_class = base_class, buckets_spec = list(known_subclasses))

    @classmethod
    def by_feature(cls, base_class: type[Traitable], feature_calc, *buckets_spec, bucket_tag_calc = None) -> Bucketizer:
        cls.verify_base_class(base_class)
        cls.verify_custom_f(feature_calc, 'feature_calc')
        if not bucket_tag_calc:
            return BucketizerByFeature(base_class = base_class, f_bucketizing_value = feature_calc, buckets_spec = buckets_spec)

        cls.verify_custom_f(bucket_tag_calc, 'bucket_tag_calc')
        return BucketizerByFeature(base_class = base_class, f_bucketizing_value = feature_calc, f_bucket_tag = bucket_tag_calc, buckets_spec = buckets_spec)

    @classmethod
    def by_range(cls, base_class: type[Traitable], value_for_range_calc, *intervals_spec) -> Bucketizer:
        cls.verify_base_class(base_class)
        cls.verify_custom_f(value_for_range_calc, 'value_for_range_calc')
        return BucketizerByRange(base_class = base_class, f_bucketizing_value = value_for_range_calc, buckets_spec = intervals_spec)

    @classmethod
    def by_breakpoints(cls, base_class: type[Traitable], value_for_range_calc, *breakpoints) -> Bucketizer:
        cls.verify_base_class(base_class)
        cls.verify_custom_f(value_for_range_calc, 'value_for_range_calc')
        return BucketizerByBreakPoints(base_class = base_class, f_bucketizing_value = value_for_range_calc, buckets_spec = breakpoints)


class BucketizerByClass(Bucketizer):
    #def is_acceptable(self, obj: Traitable) -> bool:
    #    return isinstance(obj, self.base_class)

    def calc_bucketizing_value(self, obj: Traitable):
        return obj.__class__

class BucketizerByFeature(Bucketizer):
    f_bucketizing_value: NamedCallable  = T(T.NOT_EMPTY)
    f_bucket_tag: NamedCallable         = T()

    def calc_bucketizing_value(self, obj: Traitable):
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

class BucketizerByRange(BucketizerByFeature):
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

class BucketizerByBreakPoints(BucketizerByFeature):
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

"""
Example of aggregator:

class FIN_AGGREGATOR(NamedCallable):
    PRICE       = FinInstrument.aggregate_price
    PRICE_CCY   = Portfolio.aggregate_price
    LIFE_CYCLE  = LifeCycler.aggregate_life_cycle
    LEAVES      = lambda basket:    raise NotSupportedError 
"""
class Basket(Traitable, root_class = True, embeddable = True):
    s_bucket_shape: BUCKET_SHAPE = BUCKET_SHAPE.DICT
    def __init_subclass__(cls, bucket_shape: BUCKET_SHAPE = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if bucket_shape is not None:
            cls.s_bucket_shape = bucket_shape

    bucket_shape: BUCKET_SHAPE              = RT()

    base_class: type[Traitable]             = T(T.NOT_EMPTY)
    subclasses_allowed: bool                = T(True)
    aggregator_class: type[NamedCallable]   = T()
    bucketizers: list[Bucketizer]           = T(T.EMBEDDED)

    the_bucket: Bucket                      = T(T.STICKY)       #-- single bucket if there are no bucketizers
    all_buckets: dict                       = T(T.STICKY)       #-- tagged buckets WRT bucketizers, i.e.: {(t1_i,t2_i,...): bucket_i}

    def bucket_shape_get(self) -> BUCKET_SHAPE:
        base_class = self.base_class
        if issubclass(base_class, Basketable):
            return base_class.s_bucket_shape
        return self.__class__.s_bucket_shape

    def the_bucket_get(self) -> Bucket:
        return self.new_bucket()

    def bucketizers_set(self, trait, bucketizers: list[Bucketizer]) -> RC:
        if not isinstance(bucketizers, list) or not all(isinstance(b, Bucketizer) for b in bucketizers):
            return RC(False, 'bucketizers must be a list of instances of Bucketizer')

        self.invalidate_value('the_bucket')
        self.invalidate_value('all_buckets')

        return self.raw_set_value(trait, bucketizers)

    def add_bucketizer(self, bucketizer: Bucketizer) -> bool:
        new_buckets = {}
        for tag, bucket in self.tags_buckets():
            for member, qty in bucket.members_qtys():
                b_value = bucketizer.calc_bucketizing_value(member)
                b_tag = bucketizer.calc_bucket_tag(b_value)
                if b_tag is None:
                    continue

                key = *tag, b_tag
                new_bucket = new_buckets.get(key)
                if new_bucket is None:
                    new_bucket = self.new_bucket()
                    new_buckets[key] = new_bucket
                new_bucket._insert(member, qty)

        self.invalidate_value('the_bucket')
        self.raw_set_value('all_buckets', new_buckets)
        return True

    def new_bucket(self) -> Bucket:
        return self.bucket_shape.value()

    def is_acceptable(self, obj: Traitable) -> bool:
        return isinstance(obj, self.base_class) if self.subclasses_allowed else obj.__class__ is self.base_class

    def add(self, obj: Traitable, qty: float = 1.) -> bool:
        if not self.is_acceptable(obj):
            return False

        bucketizers = self.bucketizers
        if not bucketizers:
            bucket = self.the_bucket
        else:
            tags = []
            for bucketizer in bucketizers:
                b_value = bucketizer.calc_bucketizing_value(obj)
                b_tag = bucketizer.calc_bucket_tag(b_value)
                if b_tag is None:
                    return False

                tags.append(b_tag)

            key = tuple(tags)
            data = self.all_buckets
            bucket = data.get(key)
            if bucket is None:
                bucket = self.new_bucket()
                data[key] = bucket

        bucket._insert(obj, qty)
        return True

    def tags_buckets(self):
        if not self.bucketizers:
            return ( v for v in ((XNone, self.the_bucket),) )

        return ( (key, bucket) for key, bucket in self.all_buckets.items() )

    def members_qtys(self):
        return itertools.chain.from_iterable(bucket.members_qtys() for _, bucket in self.all_buckets())

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
        if not self.bucketizers:
            return self.the_bucket.calc_trait_values(trait_name, aggregator_f)

        return {
            tag: bucket.calc_trait_values(trait_name, aggregator_f)
            for tag, bucket in self.all_buckets()
        }

    def _lift_by_trait_name(self, trait_name: str, aggregator_f: Callable, *args):
        if not self.bucketizers:
            return self.the_bucket.calc_trait_values_with_args(trait_name, aggregator_f, *args)

        return {
            tag: bucket.calc_trait_values_with_args(trait_name, aggregator_f, *args)
            for tag, bucket in self.all_buckets()
        }

    def _lift_by_method_name(self, method_name: str, aggregator_f: Callable, *args, **kwargs):
        if not self.bucketizers:
            return self.the_bucket.calc_method(method_name, aggregator_f, *args, **kwargs)

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

