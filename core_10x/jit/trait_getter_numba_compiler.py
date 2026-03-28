import inspect
import ast
import textwrap
import typing
import numba

from core_10x.traitable import Traitable, Trait

from core_10x.jit.traitable_method_optimizer import TraitableMethodOptimizer

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
                if name not in self.self_attrs:
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


class NumbaCompiler(TraitableMethodOptimizer):
    s_target_getter_suffix = 'numba'

    def __init__(self, traitable_class: type[Traitable], attr_name: str):
        super().__init__(traitable_class, attr_name)

        self.target_getter_name = f'{self.data.original_method.__name__}_{self.__class__.s_target_getter_suffix}'
        self.ast_node_transformer = NodeTransforfmer(self.data.traitable_class, self.target_getter_name)
        self.compiled_getter = None

    @classmethod
    def is_lazy(cls) -> bool:
        return True

    def generate_optimized_method(self) -> typing.Callable:
        tg = self.target_getter()
        jit = numba.jit(forceobj = True) if not self.ast_node_transformer.njit else numba.njit
        self.compiled_getter = op_method = jit(tg)
        return self.modified_getter(op_method)

    def target_getter(self):
        src = inspect.getsource(self.data.original_method)
        src = textwrap.dedent(src)
        tree = ast.parse(src)

        transformer = self.ast_node_transformer
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)
        self.target_ast_tree = new_tree

        code = compile(new_tree, '<jit>', 'exec')

        g = self.data.original_method.__globals__
        target_getter_name = self.target_getter_name
        ns = {}
        exec(code, g, ns)
        target_getter = ns[target_getter_name]

        return target_getter

    def modified_getter(self, compiled_getter):
        # param_traits = list(self.ast_node_transformer.traits.values())
        param_names = self.ast_node_transformer.self_params
        def _mod_getter(obj):
            #args = tuple(obj.get_value(name) for name in param_trait_names)
            args = tuple(getattr(obj, name) for name in param_names)
            return compiled_getter(*args)
        return _mod_getter

    def target_getter_src(self) -> str:
        return ast.unparse(self.target_ast_tree)

