from __future__ import annotations

from core_10x.traitable import Traitable, T, RT, RC, RC_TRUE
from core_10x.trait_filter import f, OR


class BasketLike(Traitable):
    s_container_class: type[BasketContainer] = None
    def __init_subclass__(cls, container = None, **kwargs):
        if container is not None:
            assert container in (BasketSet, Basket), 'container must be either BasketSet or Basket'
            cls.s_container_class = container

        super().__init_subclass__(**kwargs)

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

