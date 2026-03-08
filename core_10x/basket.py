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

    def leaves(self, member_filter: f = None) -> BasketLike:    raise NotImplementedError

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

    def contents(self, member_class: type[BasketLike], qty: float = 1., member_filter: f = None, container: BasketContainer = None) -> BasketContainer:
        if container is None:
            container = member_class.s_container_class(member_class = member_class)

        for member, mem_qty in self.items():
            if isinstance(member, member_class):
                if not member_filter or member_filter.eval(member):
                    container.add_member(member, qty * mem_qty)
            else:
                member.contents(member_class, qty = qty * mem_qty, member_filter = member_filter, container = container)

        return container

class BasketContainer(BasketLike):
    member_class: type[BasketLike]  = T()
    subclasses_allowed: bool        = T(True)

    def add_member(self, obj: BasketLike, qty: float = 1., check = True):                       raise NotImplementedError
    def add_basket(self, basket: BasketContainer, qty: float = 1., member_filter: f = None):    raise NotImplementedError

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

    def add_basket(self, basket: BasketContainer, qty: float = 1., member_filter: f = None):
        if not isinstance(basket, BasketSet):
            raise TypeError(f'{basket.__class__} is not a BasketSet')

        if not basket.member_class is self.member_class:
            raise TypeError(f'{basket.member_class} is not {self.member_class}')

        new_members = { member for member in basket.members if member_filter.eval(member) } if member_filter else basket.members
        self.members.update(new_members)

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

    def add_basket(self, basket: BasketContainer, qty: float = 1., member_filter: f = None):
        if not isinstance(basket, Basket):
            raise TypeError(f'{basket.__class__} is not a Basket')

        if not basket.member_class is self.member_class:
            raise TypeError(f'{basket.member_class} is not {self.member_class}')

        for new_member, new_qty in basket.members.items():
            if not member_filter or member_filter.eval(new_member):
                self.add_member(new_member, new_qty * qty)

    def items(self):
        return self.members.items()

