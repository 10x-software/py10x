import inspect
import ast
import textwrap
from typing import Any
import numba

from core_10x.trait import Trait
from core_10x.traitable import Traitable, T, RT

class NodeTransforfmer(ast.NodeTransformer):
    def __init__(self, method_name: str):
        self.method_name = method_name
        self.self_traits = []
        self.params = []

    def visit_FunctionDef(self, node):
        node.name = self.method_name

        node = self.generic_visit(node)

        node.args = ast.arguments(
            posonlyargs = [],
            args        = [ast.arg(arg = p) for p in self.params],
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
                trait_name = node.attr
                if not trait_name in self.self_traits:
                    self.self_traits.append(trait_name)
                    param = f'self_{trait_name}'
                    self.params.append(param)
                    return ast.copy_location(ast.Name(id = param, ctx = ast.Load()), node)

        return node

class GetterCompiler(Traitable):
    s_target_getter_suffix = 'numba'

    traitable_class: type[Traitable]    = RT()
    trait_name: str                     = RT()

    original_getter: Any                = RT()
    target_getter_name: str             = RT()

    ast_node_transformer: NodeTransforfmer  = RT(T.STICKY)

    target_ast_tree: Any                = RT()
    target_getter: Any                  = RT()
    compiled_target_getter: Any         = RT()
    modified_getter: Any                = RT()


    def original_getter_get(self):
        return self.traitable_class.trait(self.trait_name).f_get

    def target_getter_name_get(self) -> str:
        return f'{self.trait_name}_get_{self.__class__.s_target_getter_suffix}'

    def ast_node_transformer_get(self) -> NodeTransforfmer:
        return NodeTransforfmer(self.target_getter_name)

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
        setattr(self.traitable_class, target_getter_name, target_getter)

        return target_getter

    def compiled_target_getter_get(self):
        target_getter = numba.njit(self.target_getter)
        return target_getter

    def modified_getter_get(self):
        param_trait_names = self.ast_node_transformer.self_traits
        compiled_getter = self.compiled_target_getter
        def _mod_getter(obj):
            args = tuple(obj.get_value(name) for name in param_trait_names)
            return compiled_getter(*args)
        return _mod_getter

    def print_target_getter(self):
        print(ast.unparse(self.target_ast_tree))
