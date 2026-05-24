import inspect
import ast
import math as _math_module
import textwrap
import types
import typing

import jax
import jax.numpy as jnp

from core_10x.traitable import Traitable, Trait
from core_10x.jit.traitable_method_optimizer import TraitableMethodOptimizer

# math.* functions re-routed to jnp equivalents so jitted code can trace through them
_jax_math = types.SimpleNamespace(**{
    name: getattr(jnp, name)
    for name in dir(_math_module)
    if hasattr(jnp, name)
})


class NodeTransformer(ast.NodeTransformer):
    def __init__(self, traitable_class: type[Traitable], method_name: str):
        self.traitable_class = traitable_class
        self.method_name = method_name
        self.self_attrs = set()
        self.self_params = []
        self.has_fori_loop = False
        self._loop_count = 0

    def visit_FunctionDef(self, node):
        node.name = self.method_name
        node = self.generic_visit(node)
        node.args = ast.arguments(
            posonlyargs = [],
            args        = [ast.arg(arg=f'self_{p}') for p in self.self_params],
            vararg      = None,
            kwonlyargs  = [],
            kw_defaults = [],
            kwarg       = None,
            defaults    = [],
        )
        return node

    def visit_Attribute(self, node):
        node = self.generic_visit(node)

        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                name = node.attr
                if name not in self.self_attrs:
                    self.self_attrs.add(name)

                    trait = getattr(self.traitable_class, name, None)
                    if trait is None:
                        raise TypeError(f"{self.traitable_class.__name__} has no attribute '{name}'")

                    self.self_params.append(name)

                return ast.copy_location(ast.Name(id=f'self_{name}', ctx=ast.Load()), node)

        return node

    def visit_For(self, node):
        node = self.generic_visit(node)  # replace self.attr in body/iter first

        # Only handle: for <var> in range(<n>):  with no else clause
        if not (
            isinstance(node.iter, ast.Call) and
            isinstance(node.iter.func, ast.Name) and
            node.iter.func.id == 'range' and
            len(node.iter.args) == 1 and
            isinstance(node.target, ast.Name) and
            not node.orelse
        ):
            return node

        loop_var = node.target.id
        range_arg = node.iter.args[0]

        # Accumulator variables: targets of AugAssign in the immediate body
        carry_vars = []
        seen: set[str] = set()
        for stmt in node.body:
            if isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
                name = stmt.target.id
                if name not in seen and name != loop_var:
                    carry_vars.append(name)
                    seen.add(name)

        if not carry_vars:
            return node

        body_fn_name = f'_jax_loop_{self._loop_count}'
        self._loop_count += 1
        self.has_fori_loop = True

        single = len(carry_vars) == 1
        carry_var = carry_vars[0] if single else None

        if single:
            unpack = [ast.Assign(
                targets=[ast.Name(id=carry_var, ctx=ast.Store())],
                value=ast.Name(id='_carry', ctx=ast.Load()),
                lineno=node.lineno, col_offset=node.col_offset,
            )]
            pack_return = ast.Return(value=ast.Name(id=carry_var, ctx=ast.Load()))
            init_carry = ast.Name(id=carry_var, ctx=ast.Load())
            result_target = [ast.Name(id=carry_var, ctx=ast.Store())]
        else:
            unpack = [ast.Assign(
                targets=[ast.Tuple(
                    elts=[ast.Name(id=v, ctx=ast.Store()) for v in carry_vars],
                    ctx=ast.Store(),
                )],
                value=ast.Name(id='_carry', ctx=ast.Load()),
                lineno=node.lineno, col_offset=node.col_offset,
            )]
            pack_return = ast.Return(value=ast.Tuple(
                elts=[ast.Name(id=v, ctx=ast.Load()) for v in carry_vars],
                ctx=ast.Load(),
            ))
            init_carry = ast.Tuple(
                elts=[ast.Name(id=v, ctx=ast.Load()) for v in carry_vars],
                ctx=ast.Load(),
            )
            result_target = [ast.Tuple(
                elts=[ast.Name(id=v, ctx=ast.Store()) for v in carry_vars],
                ctx=ast.Store(),
            )]

        body_fn = ast.FunctionDef(
            name=body_fn_name,
            args=ast.arguments(
                posonlyargs=[], vararg=None, kwonlyargs=[],
                kw_defaults=[], kwarg=None, defaults=[],
                args=[ast.arg(arg=loop_var), ast.arg(arg='_carry')],
            ),
            body=unpack + node.body + [pack_return],
            decorator_list=[], returns=None,
            lineno=node.lineno, col_offset=node.col_offset,
        )

        fori_call = ast.Call(
            func=ast.Attribute(
                value=ast.Attribute(
                    value=ast.Name(id='jax', ctx=ast.Load()),
                    attr='lax', ctx=ast.Load(),
                ),
                attr='fori_loop', ctx=ast.Load(),
            ),
            args=[ast.Constant(value=0), range_arg,
                  ast.Name(id=body_fn_name, ctx=ast.Load()), init_carry],
            keywords=[],
        )

        result_assign = ast.Assign(
            targets=result_target,
            value=fori_call,
            lineno=node.lineno, col_offset=node.col_offset,
        )

        return [body_fn, result_assign]


class JaxCompiler(TraitableMethodOptimizer):
    s_target_getter_suffix = 'jax'

    def __init__(self, traitable_class: type[Traitable], attr_name: str):
        super().__init__(traitable_class, attr_name)
        self.target_getter_name = f'{self.data.original_method.__name__}_{self.__class__.s_target_getter_suffix}'
        self.ast_node_transformer = NodeTransformer(self.data.traitable_class, self.target_getter_name)
        self.compiled_getter = None

    @classmethod
    def is_lazy(cls) -> bool:
        return True

    def _static_argnums(self) -> tuple[int, ...]:
        if self.ast_node_transformer.has_fori_loop:
            return ()
        tc = self.data.traitable_class
        return tuple(
            i for i, name in enumerate(self.ast_node_transformer.self_params)
            if isinstance(t := getattr(tc, name, None), Trait) and t.data_type is int
        )

    def generate_optimized_method(self) -> typing.Callable:
        if not jax.config.jax_enable_x64:
            jax.config.update('jax_enable_x64', True)
        tg = self.target_getter()
        static = self._static_argnums()
        self.compiled_getter = jax.jit(tg, static_argnums=static)
        return self.modified_getter(self.compiled_getter)

    def target_getter(self) -> typing.Callable:
        src = inspect.getsource(self.data.original_method)
        src = textwrap.dedent(src)
        tree = ast.parse(src)

        transformer = self.ast_node_transformer
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)
        self.target_ast_tree = new_tree

        code = compile(new_tree, '<jit>', 'exec')

        # Shadow numpy → jnp and math → _jax_math so arithmetic is JAX-traceable
        g = {**self.data.original_method.__globals__, 'np': jnp, 'math': _jax_math, 'jax': jax}
        ns = {}
        exec(code, g, ns)
        return ns[self.target_getter_name]

    def modified_getter(self, compiled_getter: typing.Callable) -> typing.Callable:
        param_names = self.ast_node_transformer.self_params

        def _mod_getter(obj):
            args = tuple(getattr(obj, name) for name in param_names)
            result = compiled_getter(*args)
            return result.item() if hasattr(result, 'item') else result

        return _mod_getter

    def target_getter_src(self) -> str:
        return ast.unparse(self.target_ast_tree)
