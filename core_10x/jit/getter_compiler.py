import inspect
import ast
import textwrap
from typing import Any
import numba

from core_10x.traitable import Traitable, T, RT, Trait

from core_10x.jit.traitable_compiler import TraitableCompiler

class NodeTransforfmer(ast.NodeTransformer):
    def __init__(self, traitable_class: type[Traitable], method_name: str):
        self.traitable_class = traitable_class
        self.method_name = method_name
        self.self_attrs = set()
        self.self_params = []
        self.njit = True

    def visit_FunctionDef(self, node):
        node.name = self.method_name

        node = self.generic_visit(node)

        node.args = ast.arguments(
            posonlyargs = [],
            args        = [ast.arg(arg = f'self_{p}') for p in self.self_params],
            vararg      = None,
            kwonlyargs  = [],
            kw_defaults = [],
            kwarg       = None,
            defaults    = []
        )
        return node

    def visit_Attribute(self, node):
        node = self.generic_visit(node)

        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                name = node.attr
                if not name in self.self_attrs:
                    self.self_attrs.add(name)
                    param = f'self_{name}'

                    trait = getattr(self.traitable_class, name, None)
                    if trait is None:
                       raise TypeError(f"{self.traitable_class.__name__} has no attribute '{name}'")

                    if not isinstance(trait, Trait) or trait.getter_params:    #-- self.method() or self.trait_with_args()
                        self.njit = False

                    self.self_params.append(name)
                    return ast.copy_location(ast.Name(id = param, ctx = ast.Load()), node)

        return node

    # def visit_Call(self, node):
    #     node = self.generic_visit(node)
    #
    #     if isinstance(node.func, ast.Attribute):
    #         if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
    #             method_name = node.func.attr
    #             if method_name not in self.self_methods:
    #                 self.self_methods.append(method_name)
    #
    #             node.func = ast.Name(id = method_name, ctx = ast.Load())
    #
    #     return node


class GetterCompiler(Traitable):
    s_target_getter_suffix = 'numba'

    traitable_class: type[Traitable]    = RT()
    trait_name: str                     = RT()
    jit: Any                            = RT()

    original_getter: Any                = RT()
    target_getter_name: str             = RT()

    ast_node_transformer: NodeTransforfmer  = RT(T.STICKY)

    target_ast_tree: Any                = RT()
    target_getter: Any                  = RT()
    compiled_target_getter: Any         = RT()
    modified_getter: Any                = RT()


    def jit_get(self):
        tg = self.target_getter
        jit = numba.jit(forceobj = True) if not self.ast_node_transformer.njit else numba.njit
        #print(jit)
        return jit

    def original_getter_get(self):
        return self.traitable_class.trait(self.trait_name).f_get

    def target_getter_name_get(self) -> str:
        return f'{self.trait_name}_get_{self.__class__.s_target_getter_suffix}'

    def ast_node_transformer_get(self) -> NodeTransforfmer:
        return NodeTransforfmer(self.traitable_class, self.target_getter_name)

    def target_getter_get(self):
        src = inspect.getsource(self.original_getter)
        src = textwrap.dedent(src)
        tree = ast.parse(src)

        transformer = self.ast_node_transformer
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)
        self.target_ast_tree = new_tree

        code = compile(new_tree, '<jit>', 'exec')

        g = self.original_getter.__globals__
        target_getter_name = self.target_getter_name
        ns = {}
        exec(code, g, ns)
        target_getter = ns[target_getter_name]
        #setattr(self.traitable_class, target_getter_name, target_getter)

        return target_getter

    def compiled_target_getter_get(self):
        getter = self.target_getter
        jit = self.jit
        return jit(getter)

    def modified_getter_get(self):
        compiled_getter = self.compiled_target_getter
        # param_traits = list(self.ast_node_transformer.traits.values())
        param_names = self.ast_node_transformer.self_params
        def _mod_getter(obj):
            #args = tuple(obj.get_value(name) for name in param_trait_names)
            args = tuple(getattr(obj, name) for name in param_names)
            return compiled_getter(*args)
        return _mod_getter

    def target_getter_src(self) -> str:
        tg = self.target_getter
        return ast.unparse(self.target_ast_tree)

    def compiled_target(self):
        return self.compiled_target_getter
