"""Tests for `dev_10x.xx_style`: spacing and alignment of `=`, and what must stay untouched."""

from __future__ import annotations

import ast
from textwrap import dedent

from dev_10x.xx_style import main, restyle


def _check(src: str, expected: str) -> None:
    src, expected   = dedent(src), dedent(expected)
    out             = restyle(src)
    assert out == expected
    assert restyle(out) == out
    assert ast.dump(ast.parse(out)) == ast.dump(ast.parse(src))


def test_kwargs_and_defaults_get_a_space_and_keep_extra_ones():
    _check(
        """\
        def f(a, b=1, *, c: int=2, d  =  3):
            return g(a, key=b, other  =  c, **d)

        h = lambda x=1: x
        class A(Base, flag=True):
            pass
        """,
        """\
        def f(a, b = 1, *, c: int = 2, d  =  3):
            return g(a, key = b, other  =  c, **d)

        h = lambda x = 1: x
        class A(Base, flag = True):
            pass
        """,
    )


def test_other_equals_signs_and_strings_are_untouched():
    src = """\
        x == y
        if (n := 3) != 4 and a <= b:
            c += 1
        s = 'k=v'
        t = f'{x=}'
        u = f'{g(a=1)}'
        a = b = 1
        """
    _check(src, src)


def test_assignment_group_goes_to_tab_stop_and_only_adjacent_lines_join_in_a_function():
    _check(
        """\
        def f():
            a = 1
            longer = 2
            # in a function a comment ends the group
            mid_name=3
            other_name = 4

            x  = 5
        """,
        """\
        def f():
            a       = 1
            longer  = 2
            # in a function a comment ends the group
            mid_name    = 3
            other_name  = 4

            x  = 5
        """,
    )


def test_hand_aligned_group_keeps_its_column():
    src = """\
        class A(Traitable):
            name: str      = T(T.ID)
            qty: float     = T(0.)
        """
    _check(src, src)


def test_class_body_group_spans_blank_and_comment_lines():
    _check(
        """\
        class A(Traitable):
            name: str = T(T.ID)

            # money
            qty: float = T(0.)
            currency_code: str = T()

            def f(self): ...
            z: int  = T()
        """,
        """\
        class A(Traitable):
            name: str           = T(T.ID)

            # money
            qty: float          = T(0.)
            currency_code: str  = T()

            def f(self): ...
            z: int  = T()
        """,
    )


def test_unaligned_group_goes_to_its_rightmost_equals():
    _check(
        """\
        class A(Traitable):
            _at: datetime       = T()

            s_indices = []
        """,
        """\
        class A(Traitable):
            _at: datetime       = T()

            s_indices           = []
        """,
    )


def test_unspaced_group_sharing_a_column_is_aligned():
    _check(
        """\
        t = f(
            A=(1, 2),
            B=(3, 4),
        )

        a=1
        b=2
        """,
        """\
        t = f(
            A   = (1, 2),
            B   = (3, 4),
        )

        a   = 1
        b   = 2
        """,
    )


def test_hand_aligned_kwargs_in_a_table_are_kept():
    src = """\
        TABLE = f(
            DAY     = (lambda d, n: d + delta(days    = n),  dict(C = 1,     W = 1/7)),
            MONTH   = (lambda d, n: d + delta(months  = n),  dict(M = 1,     Q = 1/3)),
        )
        """
    _check(src, src)


def test_multiline_call_kwargs_are_aligned_per_run():
    _check(
        """\
        x = T(
            T.ID,
            default=1,
            fmt = '%d',
            # a comment does not end the run
            long_name='x',
            **extra,
            after=2,
        )
        y = f(a=1,
              bb=2)
        """,
        """\
        x = T(
            T.ID,
            default     = 1,
            fmt         = '%d',
            # a comment does not end the run
            long_name   = 'x',
            **extra,
            after = 2,
        )
        y = f(a = 1,
              bb = 2)
        """,
    )


def test_fmt_off_and_skip_are_respected():
    src = """\
        a=1  # -- kept  # fmt: skip
        # fmt: off
        f(b=2)  # -- kept
        # fmt: on
        f(c=3)  # -- changed
        """
    _check(src, src.replace('c=3)  # --', 'c = 3)  #--'))


def test_comment_leaders_lose_the_space_but_prose_stays():
    _check(
        """\
        # -- note
        f(a=1)  # -- trailing
        # ----------
        # ==========
        #   -- wide
        # --
        #-- already
        # --check is a flag
        y = 2  # == x, prose
        s = '# -- in a string'
        """,
        """\
        #-- note
        f(a = 1)  #-- trailing
        #----------
        #==========
        #-- wide
        #--
        #-- already
        # --check is a flag
        y = 2  # == x, prose
        s = '# -- in a string'
        """,
    )


def test_columns_count_characters_not_bytes():
    _check(
        """\
        s = f('é—', key=1, other=2)
        naïve = 1
        b = 2
        """,
        """\
        s       = f('é—', key = 1, other = 2)
        naïve   = 1
        b       = 2
        """,
    )


def test_crlf_line_endings_are_kept():
    assert restyle('f(a=1)\r\ng(b=2)\r\n') == 'f(a = 1)\r\ng(b = 2)\r\n'


def test_check_reports_without_writing_and_default_mode_writes(tmp_path, capsys):
    path = tmp_path / 'm.py'
    path.write_text('f(a=1)\n')
    assert main(['--check', str(path)]) == 1
    assert path.read_text() == 'f(a=1)\n'
    assert main([str(path)]) == 0
    assert path.read_text() == 'f(a = 1)\n'
    assert main(['--check', str(path)]) == 0
    assert 'would restyle' in capsys.readouterr().out


def test_unparsable_file_is_an_error_not_a_change(tmp_path):
    path = tmp_path / 'bad.py'
    path.write_text('def f(:\n')
    assert main(['--check', str(path)]) == 2
