from functools import total_ordering
from typing import Self


@total_ordering
class ID:
    __slots__ = ('value', 'collection_name')

    def __init__(self, id_value: str = None, collection_name: str = None):
        self.value = id_value
        self.collection_name = collection_name

    def __eq__(self, other: Self):
        if not isinstance(other, ID):
            return NotImplemented
        return self.value == other.value and self.collection_name == other.collection_name

    def __bool__(self):
        return bool(self.value)

    def __repr__(self):
        return f'{self.value}' if not self.collection_name else f'{self.collection_name}/{self.value}'

    def __hash__(self):
        return hash((self.value, self.collection_name))

    def __lt__(self, other: Self) -> bool:
        if not isinstance(other, ID):
            return NotImplemented
        return (self.collection_name, self.value) < (other.collection_name, other.value)