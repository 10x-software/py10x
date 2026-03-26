from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Callable

from core_10x.trait import TRAIT_METHOD
from core_10x.traitable import Traitable, T, RT
from core_10x.py_class import PyClass
from core_10x.exec_control import GRAPH_ON

class TraitEntry:
    def __init__(self, original_getter, modified_getter, target_func, compiled_target_func, target_src: str, used: bool):
        self.original_getter = original_getter
        self.modified_getter = modified_getter
        self.target_func = target_func
        self.compiled_target_func = compiled_target_func
        self.target_src = target_src
        self.used = used

class TraitableCompiler:
    s_compiled_getters: dict[type[Traitable], dict[str, TraitEntry]] = {}
    @classmethod
    def py_function_and_unique_name(cls, traitable_class: type[Traitable], trait_name: str) -> tuple[Callable, str]:
        trait = traitable_class.trait(trait_name, throw = True)
        getter = trait.custom_f_get()
        if getter is None:   #-- no custom getter defined
            return (None, None)

        return (
            getter,
            f"{PyClass.name(traitable_class).replace('.', '_')}_{getter.__name__}"
        )

    def generate_cython_source(self, getter: Callable, unique_name: str) -> list:
        src = textwrap.dedent(inspect.getsource(getter))
        tree = ast.parse(src)

        #-- AST transform: self.attr → self_attr
        transformer = _SelfAttrTransformer(traitable_class)
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        func_def: ast.FunctionDef = new_tree.body[0]

        #-- infer types for other local variables
        self_attr_names = {f'self_{a}' for a in transformer.attrs}
        local_types = _infer_local_types(func_def, exclude = self_attr_names | {'self'})

        #-- imports
        all_known = self_attr_names | set(local_types) | {'self'}
        import_lines = _extract_imports(getter, exclude = all_known)

        #-- rename function: price_get → ClassName_price_get
        func_def.name = unique_name

        lines = [ '# cython: language_level=3' ]

        #-- unparse transformed body, insert cdef declarations after def line
        body_lines = ast.unparse(func_def).split('\n')

        cdef_lines: list[str] = []
        #-- self.attr extractions: cdef type self_attr = self.attr  (or untyped)
        for attr, cy in transformer.attrs.items():
            lhs = f'self_{attr}'
            if cy:
                cdef_lines.append(f'    cdef {cy} {lhs} = self.{attr}')
            else:
                cdef_lines.append(f'    {lhs} = self.{attr}')

        #-- other inferred locals: cdef type var  (body handles initialisation)
        for var, cy in sorted(local_types.items()):
            cdef_lines.append(f'    cdef {cy} {var}')

        lines.extend(import_lines)
        lines.extend(cdef_lines)
        lines.extend(body_lines)

        return lines

    @classmethod
    def compile_getter(cls, traitable_class: type[Traitable], trait_name: str, use_it = True) -> TraitEntry:
        trait = traitable_class.trait(trait_name, throw = True)
        getters = cls.s_compiled_getters
        data_per_trait = getters.setdefault(traitable_class, {})
        entry = data_per_trait.get(trait_name)
        if entry is None:
            from core_10x.jit.getter_compiler import GetterCompiler     #-- just to avoid import cycle, as GetterCompiler imports TraitableCompiler

            with GRAPH_ON():
                gc = GetterCompiler(traitable_class = traitable_class, trait_name = trait_name)
                try:
                    gc.compiled_target_getter
                except Exception as ex:
                    raise ValueError(f'Compilation failed:\n{str(ex)}\n\nFunction source:\n{gc.target_getter_src()}')

                entry = TraitEntry(
                    gc.original_getter,
                    gc.modified_getter,
                    gc.target_getter,
                    gc.compiled_target_getter,
                    gc.target_getter_src(),
                    use_it
                )

            data_per_trait[trait_name] = entry

        if use_it:
            trait.set_f_get(entry.modified_getter, True)
        else:
            trait.set_f_get(entry.original_getter, True)

        return entry

