from __future__ import annotations

from functools import total_ordering


@total_ordering
class ID:
    __slots__ = ('collection_name', 'value')

    def __init__(self, id_value: str = None, collection_name: str = None):
        self.value = id_value
        self.collection_name = collection_name

    def __eq__(self, other: ID):
        if not isinstance(other, ID):
            return NotImplemented
        if self.value is None or other.value is None:
            return self is other
        return self.value == other.value and self.collection_name == other.collection_name

    def __bool__(self):
        return bool(self.value)

    def __repr__(self):
        return f'{self.value}' if not self.collection_name else f'{self.collection_name}/{self.value}'

    def __hash__(self):
        if self.value is None:
            raise TypeError(
                f'unshared ID ({self.collection_name or "no collection"}) is not hashable: its value is not set yet, '
                'so the hash would change when share() lands it and the entry would be lost. Share or save first.'
            )
        return hash((self.value, self.collection_name))

    def __lt__(self, other: ID) -> bool:
        if not isinstance(other, ID):
            return NotImplemented
        return (self.collection_name, self.value) < (other.collection_name, other.value)
