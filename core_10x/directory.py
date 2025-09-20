import inspect
from typing import Any

from core_10x.entity import Entity
from core_10x.py_class import PyClass
from core_10x.xnone import XNone


class Directory:
    @staticmethod
    def _dir_class(value):
        if isinstance(value, Entity):
            return DxEntity

        if inspect.isclass(value) and issubclass(value, Entity):
            return DxClass

        return Directory

    @staticmethod
    def instance(value: Any = None, **kwargs) -> 'Directory':
        dir_class = Directory._dir_class(value)
        return dir_class(value=value, **kwargs)

    # fmt: off
    def __init__(
        self,
        name: str           = '',
        value               = None,
        members: dict       = None,
        parent: 'Directory' = None
    ):
        # fmt: on
        self.check_dir_value(value)

        self.name = name
        self.value = value
        self.members = members or {}
        self.parent = parent

    @classmethod
    def check_dir_value(cls, value):
        f = getattr(value, '__hash__', None)
        assert f, f'Directory value must be hashable ({value})'

    def show_value(self) -> str:
        return str(self.value) if self.value else self.name

    def is_leaf(self) -> bool:
        return not self.members

    def subdirs(self) -> dict:
        return self.members

    def _add_subdir(self, subdir: 'Directory'):
        self.members[subdir.value] = subdir
        subdir.parent = self

    def _get_or_add_subdir(self, value, **subdir_values):
        subdir = self.members.get(value)
        if subdir is None:
            subdir = Directory.instance(value, **subdir_values)
            subdir.parent = self
            self.members[value] = subdir

        return subdir

    def insert(self, value, *path, **subdir_values):
        if not path:
            self._get_or_add_subdir(value, **subdir_values)
        else:
            p_value = path[0]
            subdir = self._get_or_add_subdir(p_value)
            subdir.insert(value, *path[1:], **subdir_values)

    def insert_many(self, values: list, **subdir_values):
        for value in values:
            self._get_or_add_subdir(value, **subdir_values)

    def subdir_at(self, *path) -> 'Directory':
        if not path:
            return self

        subdir = self.members.get(path[0])
        return subdir.subdir_at(*path[1:]) if subdir else None

    def remove(self, value, *path) -> bool:
        subdir = self.subdir_at(*path)
        if not subdir:
            return False

        return self.members.pop(value, XNone) is not XNone

    def remove_everywhere(self, value):
        self.remove(value)
        for subdir in self.members.values():
            subdir.remove(value)

    def _find_paths(self, value, paths_found: list, *current_path):
        found = self.members.get(value)
        if found:
            paths_found.append((*current_path, value))

        for sub_value, subdir in self.members.items():
            subdir._find_paths(value, paths_found, *current_path, sub_value)

    def find_paths(self, value) -> list:
        paths_found = [()] if value == self.value else []
        self._find_paths(value, paths_found)
        return paths_found

    def _flatten(self, res: dict, *current_path):
        path = *current_path, self.value
        label = self.name
        if not label:
            label = self.show_value()
        res[path] = label
        for subdir in self.members.values():
            subdir._flatten(res, *path)

    def flatten(self, with_root: bool = False) -> dict:
        res = {}
        if with_root:
            self._flatten(res)
        else:
            for subdir in self.members.values():
                subdir._flatten(res)

        return res

    def choices(self, with_root: bool = False, path_delimiter: str = '/') -> dict:
        f = self.flatten(with_root = with_root)
        v_n_map = { path[-1]: name for path, name in f.items() }
        res = {}
        cr = 1
        for path in f.keys():
            label = path_delimiter.join(v_n_map[p] for p in path)
            value = path[-1]
            already_in = res.get(label)
            if already_in:
                if already_in == value:
                    continue

                label = f'{label}({cr})'
                cr += 1

            res[label] = value

        return res

    def contains(self, value) -> bool:
        if self.value == value:
            return True

        for subdir in self.members.values():
            if subdir.contains(value):
                return True

        return False

    def is_value_contained(self, value, by_other_value) -> bool:
        if self.value == by_other_value:
            return self.contains(value)

        for subdir in self.members.values():
            if subdir.is_value_contained(value, by_other_value):
                return True

        return False

    def _collect_leaf_values(self, res: set, data_accessor):
        if self.is_leaf():
            res.add(data_accessor(self.value))
        else:
            for subdir in self.members.values():
                subdir._collect_leaf_values(res, data_accessor)

    def leaf_values(self, data_accessor):       #-- data_accessor: callable(leaf_value)
        res = set()
        self._collect_leaf_values(res, data_accessor)
        return list(res)

    @classmethod
    def define(cls, value_name, members: list) -> 'Directory':
        if isinstance(value_name, tuple):     #-- ( value, name ) is given
            assert len(value_name) == 2, 'a pair of ( value, name ) is expected'
            value, name = value_name

        else:       #-- just a value
            value = value_name
            name = None

        dir = Directory.instance(value, name = name)

        sub_value_name = None
        for elem in members:
            if not sub_value_name:
                sub_value_name = elem
                continue

            if isinstance(elem, list):  #-- sub dirs are given
                sudir = cls.define(sub_value_name, elem)
                dir._add_subdir(sudir)
                sub_value_name = None

            else:   #-- no sub dirs are given, just value_name
                sudir = cls.define(sub_value_name, [])
                dir._add_subdir(sudir)
                sub_value_name = elem

        if sub_value_name:
            sudir = cls.define(sub_value_name, [])
            dir._add_subdir(sudir)

        return dir


class DxEntity(Directory):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value: Entity
        self.name = self.value.id()

    @classmethod
    def check_dir_value(cls, value):
        assert isinstance(value, Entity), f'entity is expected ({value})'

    def show_value(self) -> str:
        return self.value.id()  # -- TODO: id_repr()


class DxClass(Directory):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cls = self.value
        self.name = PyClass.name(cls) if cls else ''

    @classmethod
    def check_dir_value(cls, value):
        assert inspect.isclass(value) and issubclass(value, Entity), f'subclass of Entity is expected ({value})'

    # def matching_entities(self) -> dict:
    #     """
    #     Applicable for an entity class with a "reasonable" number of entities in the collection
    #     TODO: need to provide a different mechanism (a view) for huge collections
    #     """
    #     cls = self.value
    #     return { e.id(): e for e in cls.sharedInstances( _cache = self.cache_only(), **self.filters() ) }
