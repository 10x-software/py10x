# py10x-kernel-test

Minimal uv harness directory for running the real core tests against editable builds of the py10x components.

## Usage (standard for cxx10x devs)

From this directory (with `py10x` checked out next to `cxx10x`):

```bash
uv sync --upgrade
uv run python ../../infra_10x/tests/test.py
```

The above will:

- Resolve `py10x-kernel`, `py10x-core`, and `py10x-infra` as editable from the sibling checkouts.
- Automatically build native extensions.
- Execute the test suite from the source tree.

The `--upgrade` flag is useful after making changes in the source trees.

This pattern gives you an isolated, correctly-configured environment for testing.
