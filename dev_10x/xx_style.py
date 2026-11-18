"""xx-style: the layout of `=` that no Black-style formatter keeps.

* a space each side of `=` in keyword arguments and parameter defaults: ``f(x = 1)``, ``def f(x = 1)``;
* `=` aligned within a group of consecutive assignments (trait definitions included) and within a group of
  one-per-line keyword arguments of a multi-line call. An aligned group keeps its column; otherwise `=` goes
  to the first multiple-of-4 column at least one space past the longest left side, or to the group's
  rightmost `=` if that is further;
* a class body's group runs across blank and comment lines, a multi-line call's across comment lines;
  any other group is directly consecutive lines;
* comment leaders written ``#--`` and ``#==`` (``#-- note``, ``#----``, ``#====``), not ``# --``; a comment
  naming a flag (``# --check``) or reading ``# == x`` is prose and stays.

Spaces around `=` are only added, never removed, so an `=` never moves left and hand alignment (a table of
calls, say) survives. Nothing else changes, and each file's AST is compared before it is written.
Lines between ``# fmt: off`` and ``# fmt: on``, or ending in ``# fmt: skip``, are left alone.

Usage (from the repo root)::

    uv run xx-style            # restyle the tracked .py files in place
    uv run xx-style --check    # list the files that would change; exit 1 if any
    uv run xx-style --diff     # show the changes, write nothing
    uv run xx-style PATH ...   # only these files / directories
"""

from __future__ import annotations

import argparse
import ast
import difflib
import io
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

EXCLUDE = ('cxx10x/',)  # the C++ packages' helper scripts, excluded from ruff too
TAB     = 4
# `# -- note`, `# ----`, `# ====`, but not `# --flag` or `# == x` (prose)
LEADER  = re.compile(r'# +(--(?=[ -]|$)|==(?==|$))')


@dataclass(frozen = True)
class Site:
    """An `=` and the spaces around it, in char columns of line `row`: `lhs_end` .. `value` is rewritten."""

    row: int
    lhs_end: int
    eq: int
    value: int

    def edit(self, col: int | None = None) -> tuple[int, int, str]:
        """Put `=` at `col`, or else keep its spaces; a side with none gets one."""
        before  = col - self.lhs_end if col is not None else max(1, self.eq - self.lhs_end)
        after   = max(1, self.value - self.eq - 1)
        return self.lhs_end, self.value, ' ' * before + '=' + ' ' * after


def _char_col(line: str, byte_col: int) -> int:
    # ast columns are UTF-8 byte offsets
    return byte_col if line.isascii() else len(line.encode()[:byte_col].decode())


def _site(lines: list[str], lineno: int, byte_col: int) -> Site | None:
    """The `=` right after a left side ending at (`lineno`, `byte_col`), if its value starts on the same line."""
    row     = lineno - 1
    line    = lines[row]
    i       = j = _char_col(line, byte_col)
    while line[j:j + 1] == ' ':
        j += 1
    if line[j:j + 1] != '=' or line[j + 1:j + 2] == '=':
        return None
    k = j + 1
    while line[k:k + 1] == ' ':
        k += 1
    if k >= len(line) or line[k] in '#\\':
        return None
    return Site(row, i, j, k)


def _starts_line(lines: list[str], node: ast.AST) -> bool:
    line = lines[node.lineno - 1]
    return not line[:_char_col(line, node.col_offset)].strip()


def _assign_site(lines: list[str], stmt: ast.stmt) -> Site | None:
    if isinstance(stmt, ast.Assign):
        lhs = stmt.targets[0]
    elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        lhs = stmt.annotation
    else:
        return None
    if lhs.end_lineno != stmt.lineno or not _starts_line(lines, stmt):
        return None
    return _site(lines, lhs.end_lineno, lhs.end_col_offset)


def _default_sites(lines: list[str], args: ast.arguments) -> list[Site | None]:
    positional      = args.posonlyargs + args.args
    with_default    = positional[len(positional) - len(args.defaults):] + [a for a, d in zip(args.kwonlyargs, args.kw_defaults, strict = True) if d is not None]
    return [_site(lines, a.end_lineno, a.end_col_offset) for a in with_default]


def _joined(lines: list[str], end_row: int, next_row: int, comments: bool, blanks: bool) -> bool:
    """Whether only comment lines (if `comments`) and blank lines (if `blanks`) lie strictly between the two rows."""
    for line in lines[end_row + 1:next_row]:
        text = line.strip()
        if not ((comments and text.startswith('#')) or (blanks and not text)):
            return False
    return True


def _runs(lines: list[str], items: list[tuple[ast.AST, Site]], comments: bool, blanks: bool) -> list[list[Site]]:
    runs, run, end_row = [], [], -1
    for node, site in items:
        if run and not _joined(lines, end_row, node.lineno - 1, comments, blanks):
            runs.append(run)
            run = []
        run.append(site)
        end_row = node.end_lineno - 1
    if run:
        runs.append(run)
    return runs


def _column(group: list[Site]) -> int:
    lhs = max(s.lhs_end for s in group)
    eqs = {s.eq for s in group}
    # `a=1` / `b=2` share a column too, but with no space before it
    if len(eqs) == 1 and (col := min(eqs)) > lhs:
        return col
    return max(-(-(lhs + 1) // TAB) * TAB, *eqs)


def _skipped(lines: list[str]) -> set[int]:
    rows, off = set(), False
    for row, line in enumerate(lines):
        text = line.strip()
        if text == '# fmt: off':
            off = True
        elif text == '# fmt: on':
            off = False
        if off or text.endswith('# fmt: skip'):
            rows.add(row)
    return rows


def _leader_edits(src: str, lines: list[str], skip: set[int]) -> list[tuple[int, tuple[int, int, str]]]:
    edits = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT and (row := tok.start[0] - 1) not in skip and (m := LEADER.match(lines[row], tok.start[1])):
            edits.append((row, (m.start(), m.end(), '#' + m.group(1))))
    return edits


def _pass(src: str) -> str:
    raw         = src.split('\n')
    lines       = [r.removesuffix('\r') for r in raw]
    tree        = ast.parse(src)
    skip        = _skipped(lines)
    # f-strings are left alone, `f'{x=}'` included
    in_fstring = {id(n) for js in ast.walk(tree) if isinstance(js, ast.JoinedStr) for n in ast.walk(js)}

    groups:  list[list[Site]] = []
    singles: list[Site]       = []
    for node in ast.walk(tree):
        if id(node) in in_fstring:
            continue
        if isinstance(node, (ast.Call, ast.ClassDef)):
            kws = [(k, s) for k in node.keywords if k.arg and (s := _site(lines, k.lineno, k.col_offset + len(k.arg.encode())))]
            singles += [s for _, s in kws]
            groups  += _runs(lines, [(k, s) for k, s in kws if _starts_line(lines, k) and s.row not in skip], comments = True, blanks = False)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            singles += [s for s in _default_sites(lines, node.args) if s]
        for field in ('body', 'orelse', 'finalbody'):
            stmts = getattr(node, field, None)
            if isinstance(stmts, list):
                items       = [(st, s) for st in stmts if (s := _assign_site(lines, st)) and s.row not in skip]
                in_class    = isinstance(node, ast.ClassDef) and field == 'body'
                groups  += _runs(lines, items, comments = in_class, blanks = in_class)

    edits: dict[int, list[tuple[int, int, str]]]    = {}
    done                                            = set()
    for group in groups:
        col = _column(group) if len(group) > 1 else None
        for s in group:
            edits.setdefault(s.row, []).append(s.edit(col))
            done.add(s)
    for s in singles:
        if s not in done and s.row not in skip:
            edits.setdefault(s.row, []).append(s.edit())
            done.add(s)
    for row, edit in _leader_edits(src, lines, skip):
        edits.setdefault(row, []).append(edit)

    for row, row_edits in edits.items():
        line = lines[row]
        for start, end, text in sorted(row_edits, reverse = True):
            line = line[:start] + text + line[end:]
        lines[row] = line
    return '\n'.join(line + ('\r' if r.endswith('\r') else '') for line, r in zip(lines, raw, strict = True))


def restyle(src: str) -> str:
    """`src` with the house layout of `=`. Raises SyntaxError if it does not parse."""
    before  = ast.dump(ast.parse(src))
    out     = src
    # an edit inside a left side (a kwarg in `f(a=1).x = 2`) moves its `=`: realign until nothing moves
    for _ in range(5):
        new = _pass(out)
        if new == out:
            break
        out = new
    else:
        raise RuntimeError('layout did not settle')
    if ast.dump(ast.parse(out)) != before:
        raise RuntimeError('restyling would change the code')
    return out


def _files(paths: list[str]) -> list[Path]:
    if paths:
        return [f for p in map(Path, paths) for f in (sorted(p.rglob('*.py')) if p.is_dir() else [p])]
    root    = Path(subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output = True, text = True, check = True).stdout.strip())
    tracked = subprocess.run(['git', 'ls-files', '*.py'], cwd = root, capture_output = True, text = True, check = True).stdout.split()
    return [root / f for f in tracked if not f.startswith(EXCLUDE) and (root / f).exists()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog = 'xx-style', description = 'Space and align `=` the py10x way.')
    parser.add_argument('paths', nargs = '*', help = 'files or directories (default: tracked .py files)')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action = 'store_true', help = 'list files that would change; exit 1 if any')
    mode.add_argument('--diff',  action = 'store_true', help = 'print the changes; write nothing; exit 1 if any')
    args = parser.parse_args(argv)

    changed, failed = [], []
    for path in _files(args.paths):
        src = path.read_bytes().decode()
        try:
            new = restyle(src)
        except (SyntaxError, RuntimeError) as e:
            failed.append(f'{path}: {e}')
            continue
        if new == src:
            continue
        changed.append(path)
        if args.diff:
            sys.stdout.writelines(difflib.unified_diff(src.splitlines(True), new.splitlines(True), str(path), str(path)))
        elif not args.check:
            path.write_bytes(new.encode())

    verb = 'would restyle' if args.check or args.diff else 'restyled'
    if not args.diff:
        for path in changed:
            print(f'{verb} {path}')
    for msg in failed:
        print(f'error: {msg}', file = sys.stderr)
    print(f'{len(changed)} file(s) {verb}', file = sys.stderr)
    return 2 if failed else int(bool(changed) and (args.check or args.diff))


if __name__ == '__main__':
    sys.exit(main())
