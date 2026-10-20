# AADC API Reference

## Active types

| Type | Description |
|------|-------------|
| `idouble` | Active scalar float — propagates adjoints through recording |
| `iint` | Active scalar int |
| `ibool` | Active scalar bool — result of comparisons on `idouble` values |
| `passive` | Context manager: temporarily treat values as constants (no adjoint propagation) |

## Recording

```python
with aadc.record_kernel() as kernel:
    ...                         # everything here is recorded

aadc.is_recording()             # → bool; True inside record_kernel block
aadc.record_function(...)       # record a reusable sub-function inside a kernel
```

## Control flow

Python `if` does not work on `ibool` during recording — use `iif` instead:

```python
aadc.iif(cond: ibool, a: idouble, b: idouble) -> idouble
```

## aadc.math — scalar functions

Drop-in replacements for `math.*` / builtins that propagate through the recorded kernel.

| Category | Functions |
|----------|-----------|
| Arithmetic | `add`, `subtract`, `pow`, `abs`, `sign`, `cbrt`, `sqrt` |
| Rounding | `floor`, `ceil`, `trunc`, `copysign` |
| Exp / Log | `exp`, `exp2`, `expm1`, `log`, `log2`, `log10`, `log1p` |
| Trig | `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2` |
| Hyperbolic | `sinh`, `cosh`, `tanh`, `asinh`, `acosh`, `atanh` |
| Special | `erf`, `erfc`, `cdf_normal` |
| Comparisons | `less`, `leq`, `greater`, `geq`, `equal_to`, `not_equal`, `min`, `max` |

Currently swapped in `AADCContext`: `exp`, `log`, `min`.

## aadc.numpy_compat — array functions

Drop-in replacements for numpy operations on active arrays.

**Statistical** (`aadc.numpy_compat.statistical_functions`):
`sum`, `mean`, `std`, `var`, `prod`, `min`, `max`, `cumulative_sum`, `diff`, `average`, `cov`

**Other** (`aadc.numpy_compat.other_functions`):
- `interpolate_1d` — recorded 1-D interpolation; could replace the `USE_PY_LINEAR` swap in `CurveParams`
- `searchsorted` — recorded binary search
- `iwhere` — recorded `np.where`
- `clip` — recorded clamp
- `iall`, `iany`, `iallclose`, `iisclose` — recorded boolean reductions
- `iand`, `ior` — recorded logical ops

**Ufuncs** (`aadc.numpy_compat.ufuncs`): active versions of numpy ufuncs (sin, exp, etc.) on arrays.

## Root solving

```python
aadc.root_scalar(f, x0, xtol)   # recorded fixed-iteration Newton solver
```

Used inside `AADCContext` to replace `root_solver.root_scalar_impl` during recording.
