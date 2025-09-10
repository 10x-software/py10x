import importlib
import inspect

from core_10x.global_cache import cache
from core_10x.py_class import PyClass


CLASS_ID_DELIMITER = '/'

class PackageRefactoring:
    s_module_name   = '_refactoring'
    s_records_name  = '_records'

    s_instances = {}
    @classmethod
    def register_top_level_packages(cls, *top_level_packages):
        instances = cls.s_instances
        for top_level_package in top_level_packages:
            pkg_refact = cls(top_level_package)
            instances[top_level_package] = pkg_refact

    @staticmethod
    def default_class_id(cls = None, canonical_class_name: str = None) -> str:
        if canonical_class_name is None:
            assert cls and inspect.isclass(cls), f'{cls} is not a valid class'
            canonical_class_name = PyClass.name(cls)
        return canonical_class_name.replace('.', CLASS_ID_DELIMITER)

    def __init__(self, top_package_name: str):
        try:
            pkg_init = importlib.import_module(top_package_name)
            self.file_name = pkg_init.__file__.replace('__init__', self.__class__.s_module_name)
        except Exception:
            raise EnvironmentError(f'Unknown top-level package {top_package_name}')

        self.package_name = top_package_name
        try:
            module = importlib.import_module(self.s_module_name, top_package_name)
        except Exception:
            self.cid_to_path = {}
            self.path_to_cid = {}
            return

        self.cid_to_path = records = getattr(module, self.s_records_name, None)
        if records is None:
            raise EnvironmentError(f'{top_package_name}.{self.s_module_name} is missing refactoring records {self.s_records_name}')

        self.path_to_cid = path_to_cid = {}
        for class_id, canonical_class_name in records.items():
            assert isinstance(class_id, str), f'{class_id} must be a str'
            assert isinstance(canonical_class_name, str), f'{canonical_class_name} must be a canonical class name'

            path_to_cid[canonical_class_name] = class_id

    def _refactor(self, cur_path: str, new_path: str):
        cid = self.path_to_cid.get(cur_path)
        if cid is None:
            raise EnvironmentError(f'Unknown canonical class name {cur_path}')

        self.cid_to_path[cid] = new_path
        del self.path_to_cid[cur_path]
        self.path_to_cid[new_path] = cid

    def _save(self):
        text = [f'{self.__class__.s_records_name} = {{']
        for cid, path in self.cid_to_path.items():
            text.append(f'\t{cid}:\t\t"{path}"')
        text.append('}')
        s = '\n'.join(text)
        with open(self.file_name, mode = 'w') as f:
            f.write(s)

    @staticmethod
    @cache
    def find_class_id(cls) -> str:
        canonical_class_name = PyClass.name(cls)
        pkg_refact: PackageRefactoring
        for pkg_refact in PackageRefactoring.s_instances.values():
            cid = pkg_refact.path_to_cid.get(canonical_class_name)
            if cid is not None:
                return cid

        return PackageRefactoring.default_class_id(cls)

    @staticmethod
    @cache
    def find_class(class_id: str):
        pkg_refact: PackageRefactoring
        for pkg_refact in PackageRefactoring.s_instances.values():
            path = pkg_refact.cid_to_path.get(class_id)
            if path is not None:
                canonical_class_name = path
                break
        else:
            canonical_class_name = class_id.replace(CLASS_ID_DELIMITER, '.')

        cls = PyClass.find(canonical_class_name)
        if cls is None or not inspect.isclass(cls):
            raise EnvironmentError(f'Unknown class {canonical_class_name}; class_id = {class_id}')

        return cls

    @staticmethod
    def _find_or_create_instance(canonical_class_name) -> 'PackageRefactoring':
        parts = canonical_class_name.split('.', maxsplit = 1)
        if len(parts) < 2:
            raise ValueError(f'Invalid canonical class name {canonical_class_name}')

        package_name = parts[0]
        pkg_refactor: PackageRefactoring = PackageRefactoring.s_instances.get(package_name)
        if not pkg_refactor:
            pkg_refactor = PackageRefactoring(package_name)
            PackageRefactoring.s_instances[package_name] = pkg_refactor

        return pkg_refactor

    @staticmethod
    def remove_class(canonical_class_name: str, save = True):
        pkg_refactor = PackageRefactoring._find_or_create_instance(canonical_class_name)
        cid = pkg_refactor.path_to_cid.get(canonical_class_name)
        if cid is None:
            raise ValueError(f'Unknown canonical class name {canonical_class_name}')

        del pkg_refactor.cid_to_path[canonical_class_name]
        del pkg_refactor.path_to_cid[cid]

        if save:
            pkg_refactor._save()

    @staticmethod
    def move_class(cur_path: str, new_path: str):
        refactor1 = PackageRefactoring._find_or_create_instance(cur_path)
        refactor2 = PackageRefactoring._find_or_create_instance(new_path)
        the_same = refactor1 is refactor2
        cid = refactor1.path_to_cid.get(cur_path)
        if cid is not None:
            del refactor1.path_to_cid[cur_path]
            del refactor1.cid_to_path[cid]
            if not the_same:
                refactor1._save()

        else:
            cid = PackageRefactoring.default_class_id(canonical_class_name = cur_path)

        refactor2.cid_to_path[cid] = new_path
        refactor2.path_to_cid[new_path] = cid
        refactor2._save()



