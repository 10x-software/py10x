from __future__ import annotations

import builtins
import ctypes
import inspect
import re
import subprocess
import sys
import sysconfig
import tempfile
import textwrap
from pathlib import Path
from types import ModuleType
from collections.abc import Callable
import ast
import types
import importlib.util

from core_10x.trait import Trait, ClassTrait
from core_10x.traitable import Traitable
from core_10x.py_class import PyClass
from core_10x.global_cache import cache

from core_10x.jit.tcc_compiler import TCC


def _self_attr(name: str) -> str:       return f'self_{name}'
def _is_self_attr(name: str) -> bool:   return name.startswith('self_')

#==
#   AST transformer
#==
class FuncTreeWalker(ast.NodeTransformer):
    """
    Replaces self.attr -> self_attr for trait getters with no args throughout the function body.
    Collects attrs in order of first appearance, with their Cython types.
    TODO: process those inside loops; we probably don't want to do self_attr = self.attr for everything, as they may be
        TODO: inside 'if' statements.
    TODO: + process self.method() or self.trait_with_args()
    TODO: + process other Traitable obs re all of the above
    """

    s_builtin_names = frozenset(dir(builtins))

    def __init__(self, typenames_of_interest, traitable_class: type[Traitable]):
        self.typenames_of_interest = typenames_of_interest
        self.traitable_class = traitable_class
        self.attrs: dict[str, type] = {}        #-- attr -> data_type
        self.locals: dict[str, str] = {}        #-- local_var -> type_name
        self.others: set[str]       = set()     #-- other vars

    def visit_Name(self, node: ast.Name):
        name = node.id
        if name not in self.s_builtin_names and not _is_self_attr(name):
            self.others.add(name)
        return node

    def visit_Attribute(self, node: ast.Attribute):
        node = self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id == 'self':
            name = node.attr
            if name not in self.attrs:
                trait = self.traitable_class.trait(name)
                if trait and not trait.getter_params:
                    self.attrs[name] = trait.data_type
            return ast.copy_location(ast.Name(id = _self_attr(name), ctx=node.ctx), node)

        return node

    def visit_AnnAssign(self, node: ast.AnnAssign):
        node = self.generic_visit(node)
        if isinstance(node.target, ast.Name):
            type_name = node.annotation.id
            if type_name in self.typenames_of_interest:
                self.locals[node.target.id] = type_name
        return node

    def _const_to_typename(self, node: ast.expr) -> str:
        if not isinstance(node, ast.Constant):
            return None

        dt = type(node.value)
        type_name = dt.__name__
        return type_name if type_name in self.typenames_of_interest else None

    def visit_Assign(self, node: ast.Assign):
        node = self.generic_visit(node)
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id not in self.locals:
                type_name = self._const_to_typename(node.value)
                if type_name:
                    self.locals[target.id] = type_name
        return node

    def visit_For(self, node: ast.For):
        node = self.generic_visit(node)
        if (
            isinstance(node.target, ast.Name)
            and isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == 'range'
        ):
            self.locals[node.target.id] = 'int'
        return node

class CythonCompiler:
    #-- Python -> Cython type maps
    s_pytype_cy_map: dict[type, str] = {
        int:    'long',
        float:  'double',
        bool:   'bint',
    }
    s_pyname_cy_map: dict[str, str] = { pytype.__name__: cy for pytype, cy in s_pytype_cy_map.items() }

    @classmethod
    @cache
    def instance(cls, traitable_class: type[Traitable], trait_name: str) -> CythonCompiler:
        assert issubclass(traitable_class, Traitable), f'{traitable_class} is not a subclass of {Traitable}'
        trait = traitable_class.trait(trait_name, throw = True)
        getter = trait.custom_f_get()
        if getter is None:  #-- no custom getter defined
            return None

        return CythonCompiler(ClassTrait(traitable_class, trait), getter, _kaboom = False)

    def __init__(self, class_trait: ClassTrait, getter: Callable, _kaboom = True):
        assert not _kaboom, f'You must use {self.__class__.__name__}.instance(traitable_class, trait_name)'

        self.class_trait = class_trait
        self.getter = getter
        self.unique_name = f"{PyClass.name(class_trait.cls).replace('.', '_')}_{getter.__name__}"
        self.compiled_getter = None
        self.compiled_module = None

    #== TCC in-memory compilation → Python callable

    def tcc_compile(self):
        """
        Compile C source in-memory with TCC.
        Calls PyInit_<module_name>() to obtain the Python module.
        Sets self.compiled_module and self.compiled_getter.
        """
        c_src = self.generate_c_source()
        module_name = self.unique_name
        python_include = sysconfig.get_path('include')

        binary = TCC.compile(c_src, include_dirs = [python_include])

        init_ptr = binary.symbol(f'PyInit_{module_name}')
        result = ctypes.CFUNCTYPE(ctypes.py_object)(init_ptr)()

        if isinstance(result, types.ModuleType):
            result.__tcc_binary__ = binary  # -- keep TCC memory alive as long as the module lives
            self.compiled_module = result
            self.compiled_getter = getattr(self.compiled_module, self.unique_name)
            return  #-- single-phase init, done

        #-- multi-phase init: result is a PyModuleDef* returned from PyModuleDef_Init,
        #-- wrapped as a Python object whose memory lives in TCC's allocation.
        #-- Pin its refcount so Python's allocator never tries to free TCC memory.
        ctypes.c_ssize_t.from_address(id(result)).value += 1

        #-- PyModule_FromDefAndSpec is static inline in 3.11 headers; use PyModule_FromDefAndSpec2
        spec = importlib.util.spec_from_loader(module_name, loader = None)
        spec.origin = '<tcc_jit>'

        api = ctypes.pythonapi
        api.PyModule_FromDefAndSpec2.restype = ctypes.py_object
        api.PyModule_FromDefAndSpec2.argtypes = [ctypes.c_void_p, ctypes.py_object, ctypes.c_int]
        api.PyModule_ExecDef.restype = ctypes.c_int
        api.PyModule_ExecDef.argtypes = [ctypes.py_object, ctypes.c_void_p]

        def_ptr = id(result)  # -- PyModuleDef* == id() of the wrapped object
        module = api.PyModule_FromDefAndSpec2(def_ptr, spec, sys.api_version)
        rc = api.PyModule_ExecDef(module, def_ptr)
        if rc != 0:
            raise RuntimeError(f'PyModule_ExecDef failed for {module_name}')
        module.__tcc_binary__ = binary  #-- keep TCC memory alive as long as the module lives
        self.compiled_module = module
        self.compiled_getter = getattr(module, self.unique_name)

    def generate_c_source(self) -> str:
        cy_text = self.generate_cython_source()
        return self.cython_to_c('\n'.join(cy_text))

    def generate_cython_source(self) -> list:
        src = textwrap.dedent(inspect.getsource(self.getter))
        tree = ast.parse(src)

        #-- Walk the AST tree and return a potentially modified copy

        walker = FuncTreeWalker(self.s_pyname_cy_map, self.class_trait.cls)
        new_tree = walker.visit(tree)
        ast.fix_missing_locations(new_tree)

        #-- Change the name and extract the body

        func_def: ast.FunctionDef = new_tree.body[0]
        func_def.name = self.unique_name
        body_lines = ast.unparse(func_def).split('\n')

        #-- Produce import lines

        self_attr_names = { _self_attr(name) for name in walker.attrs.keys() }
        all_known = {'self'}
        all_known.update(self_attr_names, set(walker.locals.keys()))
        other_names = walker.others - all_known

        import_lines = self.generate_import_lines(other_names)

        #-- Produce cdef lines

        cdef_lines = []
        for attr, py_type in walker.attrs.items():
            self_attr = _self_attr(attr)
            if py_type:
                cdef_lines.append(f'    cdef {self.s_pytype_cy_map[py_type]} {self_attr} = self.{attr}')
            else:
                cdef_lines.append(f'    {self_attr} = self.{attr}')

        for var, type_name in walker.locals.items():
            cdef_lines.append(f'    cdef {self.s_pyname_cy_map[type_name]} {var}')

        body_lines[1:1] = cdef_lines

        lines = ['# cython: language_level=3']
        lines.extend(import_lines)
        lines.append('')
        lines.extend(body_lines)

        return lines

    def generate_import_lines(self, other_names: set) -> list:
        """
        Use 'free' names in the getter (not excluded, not builtins),
        look them up in getter.__globals__, construct import lines.
        """
        lines = []
        g = self.getter.__globals__
        for name in other_names:
            obj = g.get(name)
            if obj is None:     #-- local, param or a bug in the original getter :-)
                continue

            if isinstance(obj, ModuleType):
                obj_name = obj.__name__
                if obj_name == name:
                    lines.append(f'import {name}')
                else:
                    lines.append(f'import {obj_name} as {name}')
            elif hasattr(obj, '__module__') and hasattr(obj, '__name__'):
                obj_name = obj.__name__
                if obj_name == name:
                    lines.append(f'from {obj.__module__} import {name}')
                else:
                    lines.append(f'from {obj.__module__} import {obj_name} as {name}')

        return lines

    #== Cython -> C  (temp file, Cython as transpiler only)
    def cython_to_c(self, pyx_src: str) -> str:
        module_name = self.unique_name
        with tempfile.TemporaryDirectory() as tmp:
            pyx = Path(tmp) / f'{module_name}.pyx'
            c   = Path(tmp) / f'{module_name}.c'
            pyx.write_text(pyx_src, encoding = 'utf-8')

            result = subprocess.run(
                [sys.executable, '-m', 'cython', '--3str', str(pyx)],
                capture_output = True,
                text = True
            )
            if result.returncode != 0:
                raise RuntimeError(f'Cython transpilation failed:\n{result.stderr}')
            if not c.exists():
                raise FileNotFoundError(f'Cython did not produce {c}')

            c_src = c.read_text(encoding = 'utf-8')
            #-- Remove Cython compile-time size assertions that trip TCC's constant evaluator
            #-- pattern: enum { __pyx_check_sizeof_xxx = 1 / (int)(...) };
            return re.sub(
                r'enum\s*\{\s*__pyx_check_sizeof_\w+\s*=[^}]+}\s*;',
                '',
                c_src,
                flags = re.DOTALL,
            )
