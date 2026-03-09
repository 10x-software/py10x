from __future__ import annotations

import functools
from typing import Callable

from py10x_kernel import PyLinkage

from core_10x.traitable import Traitable, Trait, T, RT, RC, RC_TRUE
from core_10x.trait_filter import f, OR


class BasketLike(Traitable):
    s_container_class: type[BasketContainer] = None
    def __init_subclass__(cls, container = None, **kwargs):
        if container is not None:
            assert container in (BasketSet, Basket), 'container must be either BasketSet or Basket'
            cls.s_container_class = container

        super().__init_subclass__(**kwargs)

    def _lifter(self, method_name: str, *args, **kwargs):
        results = []
        for member, qty in self.items():
            trait = getattr(member.__class__, method_name, None)
            if trait:
                if isinstance(trait, Trait):
                    value = member.get_value(trait) if not trait.getter_params else member.get_value(trait, *args)
                elif isinstance(trait, Callable):   #-- 'trait' is a method of member.__class__
                    value = trait(member, *args, **kwargs)
                else:
                    value = trait   #-- just some data attribute of member.__class__ (? - TODO: revisit)
            else:
                value = None

            results.append((value, qty))

        return results

    def __getattr__(self, method_name: str):
        return functools.partial(self._lifter, method_name)

    def is_member(self, obj: BasketLike) -> bool:   raise NotImplementedError
    def items(self):                                raise NotImplementedError

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

    def contents(self, target_class: type[BasketLike], leaves = False, filter: f = None, container: BasketContainer = None, qty: float = 1.) -> BasketContainer:
        if container is None:
            container = target_class.s_container_class(member_class = target_class)

        for member, mem_qty in self.items():
            if isinstance(member, target_class):
                if leaves:
                    container.add_items(member, qty = qty * mem_qty, member_filter = filter)
                elif not filter or filter.eval(member):
                    container.add_member(member, qty * mem_qty)
            else:
                member.contents(target_class, filter = filter, container = container, qty = qty * mem_qty)

        return container

class BasketContainer(BasketLike):
    member_class: type[BasketLike]  = T()
    subclasses_allowed: bool        = T(True)

    def _keys(self):    raise NotImplementedError

    def _lifter(self, method_name: str, *args, **kwargs):
        member_class = self.member_class
        trait = getattr(member_class, method_name, None)
        if trait:
            if isinstance(trait, Trait):
                if not trait.getter_params:
                    f = lambda obj, *args, **kwargs: member_class.get_value(obj, trait)
                else:
                    f = lambda obj, *args, **kwargs: member_class.get_value(obj, trait, *args)
            elif isinstance(trait, Callable):  #-- 'trait' is a method of member.__class__
                f = lambda obj, *args, **kwargs: trait(obj, *args, **kwargs)
            else:
                f = lambda obj, *args, **kwargs: trait   # -- just some data attribute of member.__class__ (? - TODO: revisit)
        else:
            return None

        return [ (f(member, *args, **kwargs), qty) for member, qty in self.items() ]

    def __getattr__(self, method_name: str):
        if not self.subclasses_allowed:
            lifter = self._lifter
        else:
            same_type = PyLinkage.same_type(self._keys())
            lifter = super()._lifter if same_type is None else self._lifter

        return functools.partial(lifter, method_name)

    def add_member(self, obj: BasketLike, qty: float = 1., check = True):               raise NotImplementedError

    def add_items(self, obj: BasketLike, qty: float = 1., member_filter: f = None):
        member_cls = self.member_class
        subclasses_allowed = self.subclasses_allowed
        for member, mem_qty in obj.items():
            rc = isinstance(member, member_cls) if subclasses_allowed else member.__class__ is member_cls
            if not rc:
                continue

            if not member_filter or member_filter.eval(member):
                self.add_member(member, qty = qty * mem_qty, check = False)

    def check_new_member(self, obj: BasketLike):
        member_cls = self.member_class
        obj_cls = obj.__class__
        rc = issubclass(obj_cls, member_cls) if self.subclasses_allowed else obj_cls is member_cls
        if not rc:
            raise TypeError(f'{obj_cls} may not be a member of {self.__class__}')


class BasketSet(BasketContainer):
    members: set[BasketLike]    = T()

    def __post_init__(self):
        self.members = self.members

    def _keys(self):    return self.members

    def is_member(self, obj: Traitable) -> bool:
        return obj in self.members

    def add_member(self, obj: BasketLike, qty: float = 1., check = True):
        if check:
            self.check_new_member(obj)
        self.members.add(obj)

    class Iter:
        def __init__(self, members: set):
            self.it = iter(members)

        def __iter__(self):
            return self

        def __next__(self):
            return (self.it.__next__(), 1.)

    def items(self):
        return self.Iter(self.members)

class Basket(BasketContainer):
    members: dict[BasketLike, float] = T({})

    def __post_init__(self):
        self.members = self.members

    def _keys(self):    return self.members.keys()

    def is_member(self, obj: BasketLike) -> bool:
        return obj in self.members.keys()

    def add_member(self, obj: BasketLike, qty: float = 1., check = True):
        if check:
            self.check_new_member(obj)
        members = self.members
        ex_qty = members.get(obj, 0.)
        members[obj] = ex_qty + qty

    def items(self):
        return self.members.items()

