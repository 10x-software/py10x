import inspect
import pickle
import io
import sys
import importlib
import importlib.util

from importlib_resources import files
import shlex

from core_10x.global_cache import cache

class PyClass:
    """
    Module top-level classes ONLY
    """

    NO_NAME         = lambda cls: ''
    QUAL_NAME       = lambda cls: cls.__qualname__
    CANONICAL_NAME  = lambda cls: f'{cls.__module__}.{cls.__qualname__}'

    @staticmethod
    def name(cls, name_type = CANONICAL_NAME) -> str:
        try:
            return name_type(cls)
        except Exception as ex:
            raise ValueError( f'cls must be a valid class\n{str(ex)}' )

    @staticmethod
    def top_level_package(cls) -> str:
        return cls.__module__.split('.', maxsplit = 1)[0]

    #===================================================================================================================
    #   Finding classes/symbols in the code base
    #===================================================================================================================
    @staticmethod
    @cache
    def dummy_unpickler() -> pickle.Unpickler:
        file = io.BytesIO()
        return pickle.Unpickler(file)

    @staticmethod
    @cache
    def find_symbol(canonical_symbol_name: str):
        try:
            module_name, symbol_name = canonical_symbol_name.rsplit('.', maxsplit = 1)
        except Exception:
            raise ValueError( f"Invalid canonical_symbol_name = '{canonical_symbol_name}'" )

        try:
            return PyClass.dummy_unpickler().find_class(module_name, symbol_name)

        except Exception:
            return None

    @staticmethod
    def find(canonical_class_name: str, *parents):
        cls = PyClass.find_symbol(canonical_class_name)
        if not cls or not inspect.isclass(cls):
            return None

        subclass = all( issubclass(cls, parent) for parent in parents )
        return cls if subclass else None

    @staticmethod
    @cache
    def find_related_class(cls: type, topic: str, class_name_suffix: str, *alternative_packages ) -> type:
        """
        Tries to find a class whose name is cls.__name__ + class_name_suffix "related" to cls by a topic (e.g., ui10x).
        By convention the module name must be the cls' module short name + _ + topic.
        First, tries the cls-module-package, then the cls-module-package.topic, and lastly, the alternative packages, if any.

        For example:

        Consider class TextMessage in module abc.infra.messenger. Its custom editor class, will be looked up as follows:
            PyClass.find_related_class(TextMessage, 'ui10x', 'Editor', *extra_packages)
                - editor class name:            TextMessageEditor
                - editor short module name:     messenger_ui
                - search for TextMessageEditor in the following order:
                    -- the module abc.infra.messenger_ui
                    -- the module abc.infra.ui10x.messenger_ui
                    -- [ ex_package.messenger_ui for ex_package in extra_packages ]
        """
        parts = cls.__module__.rsplit('.', maxsplit = 1)
        assert len(parts) >= 2, f"{cls} - package is missing"

        the_package         = parts[0]
        short_module_name   = f'{parts[-1]}_{topic}'
        cname               = f'{cls.__name__}{class_name_suffix}'

        #-- check if we have this module in the same package
        found = PyClass.find(f'{the_package}.{short_module_name}.{cname}')
        if not found:   #-- then check if it's in the subpackage pkg.topic
            found = PyClass.find(f'{the_package}.{topic}.{short_module_name}.{cname}')
            if not found:   #-- last resort - look it up in alternative_packages
                for package in alternative_packages:
                    found = PyClass.find(f'{package}.{short_module_name}.{cname}')
                    if found:
                        break

        return found

    @staticmethod
    def derived_from(cls, *parents, exclude_parents = ()) -> bool:
        """
        :param cls: a class
        :param parents: classes the cls must be derived from
        :param exclude_parents: classes the cls must NOT be derived from
        """
        if any( issubclass(cls, parent) for parent in exclude_parents ):
            return False

        return all( issubclass(cls, parent) for parent in parents )

    @staticmethod
    def parents(cls) -> tuple:
        tree = inspect.getclasstree([cls])
        try:
            return tree[ -1 ][ 0 ][ 1 ]
        except Exception:
            assert False, f'Something went wrong with inheritance tree of class {PyClass.name(cls)}'

    @staticmethod
    def class_tree(root_class: type, *classes) -> dict:
        all_nodes = {}
        for cls in classes:
            PyClass._collect_class_nodes(cls, root_class, all_nodes)

        return all_nodes.get(root_class)

    @staticmethod
    def _collect_class_nodes(cls: type, root_class: type, all_nodes: dict):
        if not issubclass(cls, root_class):
            return

        node = all_nodes.get(cls)
        if node is not None:
            return

        node = {}
        all_nodes[cls] = node
        parents = PyClass.parents(cls)
        for p in parents:
            PyClass._collect_class_nodes(p, root_class, all_nodes)
            p_node = all_nodes.get(p)
            if p_node is not None:
                p_node[cls] = node

    @staticmethod
    def inheritancePaths(root_class: type, child_class: type) -> list:
        tree = PyClass.class_tree(root_class, child_class)
        return PyClass._inheritance_paths(tree)

    @staticmethod
    def _inheritance_paths(tree: dict) -> list:
        res = []
        for cls, class_entry in tree.items():
            if not class_entry:
                res.append([cls])
                continue

            cls_paths = PyClass._inheritance_paths(class_entry)
            for path in cls_paths:
                x_path = [cls]
                x_path.extend(path)
                res.append(x_path)

        return res

    @staticmethod
    def full_name_space(cls) -> dict:
        full_ns = {}
        classes = *PyClass.parents(cls), cls
        for c in classes:
            ns = dict( vars(inspect.getmodule(c)) )
            full_ns.update(ns)

        return full_ns

    #---- We may need it to create local vars with particular names and values
    #locals().update( { var_name: var_value } )

    @staticmethod
    def module_class_names(package_name: str, py_file_name: str) -> list:
        try:
            res = []
            src = files(package_name).joinpath(py_file_name).read_text()
            for line in src.split('\n'):
                if line.startswith('class'):
                    class_name = shlex.shlex(line[5:]).get_token()
                    if class_name.isidentifier():
                        res.append(class_name)

            return res

        except Exception:
            return []

    @staticmethod
    def class_names_by_module(*package_names, exclude_packages = ()) -> dict:
        res = {}
        for pname in package_names:
            PyClass._collect_class_names(res, pname, exclude_packages)

        return res

    @staticmethod
    def canonical_class_names(*package_names, exclude_packages = ()) -> list:
        res = []
        for pname in package_names:
            PyClass._collect_class_names(res, pname, exclude_packages)

        return res

    @staticmethod
    def _collect_class_names(res, package_name: str, exclude_packages: tuple):
        if package_name in exclude_packages:
            return

        try:
            dir = files(package_name)

        except Exception:
            assert False, f"'{package_name}' is neither a package, nor a module"

        for item in dir.iterdir():
            name: str = item.name
            if name.startswith('__'):
                continue

            if item.is_dir():
                if isinstance(res, dict):
                    subres = {}
                    PyClass._collect_class_names(subres, package_name + '.' + name, exclude_packages)
                    if subres:
                        res[name] = subres

                else:
                    PyClass._collect_class_names(res, package_name + '.' + name, exclude_packages)

                continue

            if name.endswith('.py'):
                PyClass._collect_module_class_names(res, package_name, name)
                continue

    @staticmethod
    def _collect_module_class_names(res, package_name: str, py_file_name: str):
        class_names = PyClass.module_class_names(package_name, py_file_name)
        if class_names:
            module_name = py_file_name[:-3]
            if isinstance(res, dict):
                res[module_name] = class_names
            else:
                full_module_name = f'{package_name}.{module_name}'
                res.extend([ f'{full_module_name}.{cname}' for cname in class_names ])

    @staticmethod
    def own_attribute(cls, attr_name:str) -> tuple:     #-- (exists, value)
        d = cls.__dict__
        value = d.get(attr_name, d)
        rc = value is not d
        return ( rc, value if rc else None )

    #===================================================================================================================
    #   Class mapping to deal with migrations / refactoring class canonical names
    #===================================================================================================================
#     s_migration_map     = {}
#     s_rev_migration_map = {}
#     @staticmethod
#     def register_migration(canonical_class_name: str, new_canonical_class_name: str):
#         existing_mapping    = PyClass.s_migration_map.get(canonical_class_name)
#         reverse_mapping     = PyClass.s_rev_migration_map.get(new_canonical_class_name)
#
#         if not existing_mapping:
#             PyClass.s_migration_map[canonical_class_name] = new_canonical_class_name
#             PyClass.s_rev_migration_map[new_canonical_class_name] = canonical_class_name
#
#         else:
#             assert existing_mapping == new_canonical_class_name, f'{canonical_class_name} is already migrated to {existing_mapping}'
#             assert reverse_mapping == canonical_class_name, f'{new_canonical_class_name} is mapped to {reverse_mapping}'
#
#         module_name, class_name = canonical_class_name.rsplit('.', 1)
#         new_module_name, new_class_name = new_canonical_class_name.rsplit('.', 1)
#
#         deferred_module = sys.modules.get(module_name)
#         if not isinstance(deferred_module, DeferredModule):
#             assert not hasattr(deferred_module, class_name), f'{class_name} is already defined in {module_name}'
#             deferred_module = DeferredModule(module_name)
#
#         if class_name not in deferred_module.__dict__:
#             setattr(deferred_module, class_name, DeferredClass(module_name = new_module_name, class_name = new_class_name))
#
#     @staticmethod
#     def register_multiple_migrations(migration_map: dict):
#         for canonical_class_name, new_canonical_class_name in migration_map.items():
#             PyClass.register_migration(canonical_class_name, new_canonical_class_name)
#
#     @staticmethod
#     def all_migrations(canonical_class_name: str) -> list:
#         rev_map = PyClass.s_rev_migration_map
#         all_names = []
#         while canonical_class_name:
#             all_names.append(canonical_class_name)
#             canonical_class_name = rev_map.get(canonical_class_name)
#
#         return all_names
#
#     @staticmethod
#     @cache
#     def effective_canonical_name(cls) -> str:
#         return PyClass.all_migrations(PyClass.name(cls))[-1]
#
# class DeferredModule(type(sys)):
#     def __init__(self, module_name: str):
#         super().__init__(module_name)
#         self.deferred_count = None
#         self.module = sys.modules.get(module_name)
#
#         try:
#             self.__spec__ = importlib.util.find_spec(module_name)
#         except ModuleNotFoundError:
#             pass
#
#         sys.modules[module_name] = self
#         parent, _, name = module_name.rpartition('.')
#         assert parent, f'{module_name} - top level deferred modules are not allowed'
#
#         parent_module = sys.modules.get(parent)
#         if not parent_module:
#             top_level = parent.rpartition('.')[0]
#             parent_module = DeferredModule(parent) if top_level else importlib.import_module(parent)
#
#         self.parent = parent
#         self.name = name
#
#         setattr(parent_module, name, self)
#
#     def __getattribute__(self, item):
#         if item == '__path__':
#             parent_path = sys.modules[self.parent].__path__
#             name = self.name
#             return [ f'{p_path}/{name}' for p_path in parent_path ]
#
#         if item[0] in ( 'm', '_' ) and item[1] == '_':
#             return object.__getattribute__(self, item)
#
#         module_name = self.__name__
#
#         d_count = self.deferred_count
#         if d_count is None:
#             assert self is sys.modules[module_name], f'Module {module_name} is different from sys.modules[{module_name}]'
#             module = self.module
#             if module:
#                 getattr(module, item)   #-- import it as it's deferred
#                 self.__dict__.update(module.__dict__)
#             else:
#                 del sys.modules[module_name]
#                 spec = importlib.util.find_spec(module_name)
#                 if spec:
#                     module = importlib.import_module(module_name)
#                     self.__dict__.update(module.__dict__)
#
#                 sys.modules[module_name] = self
#                 setattr(sys.modules[self.parent], self.name, self)
#
#             d_count = sum( isinstance(value, DeferredClass) for value in self.__dict__.values() )
#
#         df_class = self.__dict__.get(item)
#         if isinstance(df_class, DeferredClass):
#             self.__dict__[item] = df_class.finalize()
#             d_count -= 1
#
#         self.deferred_count = d_count
#         return object.__getattribute__(self, item)
#
# class DeferredClass:
#     def __init__(self, module_name: str = None, class_name: str = None):
#         self.module_name = module_name
#         self.class_name  = class_name
#
#     def finalize(self) -> type:
#         module = importlib.import_module(self.module_name)
#         return getattr(module, self.class_name)


