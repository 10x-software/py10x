from __future__ import annotations

from core_10x.traitable import Traitable, T, RT
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

