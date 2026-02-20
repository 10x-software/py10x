from __future__ import annotations

import os
import random
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QHeaderView

import core_10x.trait_definition as trait_definition
from core_10x.global_cache import cache
from core_10x.traitable import RC, RC_TRUE, RT, T, Traitable, Ui

from ui_10x.utils import ux, ux_warning, ux_success, ux_push_button

from ui_10x.table_view import TableView
from ui_10x.traitable_editor import TraitableEditor

if TYPE_CHECKING:
    from collections.abc import Generator


class CHAR_STATE:
    NONE        = ('lightgray',    'black')
    WRONG_POS   = ('white',        'black')
    BINGO       = ('darkgreen',    'white')

class GuessResult(Traitable):
    the_word: str    = RT(T.HIDDEN)
    guess: str       = RT(T.HIDDEN)
    num_chars: int   = RT(T.HIDDEN)

    demo_class: type = RT(T.HIDDEN)

    char_state: list = RT(T.HIDDEN)

    guessed_chars: list = RT(T.HIDDEN)
    current_char: int = RT(T.HIDDEN, default = 0)

    def guessed_chars_get(self) -> list:
        return list(self.num_chars * ' ')

    def set_current_char(self, c: str):
        i = self.current_char
        guessed_chars = self.guessed_chars
        guessed_chars[i] = c
        self.current_char = i + 1

    def delete_char(self):
        i = self.current_char
        if i:
            i -= 1
            guessed_chars = self.guessed_chars
            guessed_chars[i] = ' '
            self.current_char = i

    def accept_guess(self):
        self.guess = ''.join(self.guessed_chars)

    def num_chars_get(self) -> int:
        return len(self.the_word)

    def char_state_get(self) -> list:
        num_chars = self.num_chars
        res = [CHAR_STATE.NONE] * num_chars
        word = list(self.the_word)
        for i, c in enumerate(self.guess):
            try:
                pos = word.index(c)
                res[i] = CHAR_STATE.BINGO if pos == i else CHAR_STATE.WRONG_POS
                word[pos] = ''
            except ValueError:
                pass

        return res

    def guess_get(self) -> str:
        return self.num_chars * ' '

    @classmethod
    def _create_char_trait(cls, i: int):
        name = f'char_{i}'
        getter_name = f'{name}_get'
        sh_name = f'{name}_style_sheet'
        getter = lambda self: self.guess[i]
        getter.__name__ = getter_name
        sh_getter = lambda self: T.colors(*self.char_state[i])
        sh_getter.__name__ = sh_name
        setattr(cls, getter_name, getter)
        setattr(cls, sh_name, sh_getter)
        return (
            name,
            trait_definition.TraitDefinition(
                **{
                    trait_definition.NAME_TAG:      name,
                    trait_definition.DATATYPE_TAG:  str,
                    trait_definition.FLAGS_TAG:     T.RUNTIME,
                    trait_definition.UI_HINT_TAG:   Ui(label = f'{i+1}')
                }
            )
        )


# class Key:
#     def __init__(self, guess: GuessResult, c: str, stylesheet: str, callback):
#         self.guess = guess
#         self.c = c
#         self.stylesheet = stylesheet
#         self.callback = callback
#         self.w = None
#
#     # def widget(self, parent_w: ux.Widget) -> ux.PushButton:
#     def widget(self) -> ux.PushButton:
#         if not self.w:
#             self.w = b = ux.PushButton(self.c)
#             b.clicked_connect(lambda w: self.callback(w))
#             b.set_style_sheet(self.stylesheet)
#
#         return self.w
#
#
# class Keyboard:
#     s_keys = [
#         'qwertyuiop',
#         'asdfghjkl',
#         '*zxcvbnm<',
#     ]
#     s_special_chars = {
#         2:  {
#             0:                      ( 'background-color: green; color: white',  GuessResult.accept_guess ),
#             len(s_keys[2]) - 1:     ( 'background-color: red; color: white',    GuessResult.delete_char ),
#         }
#     }
#
#     def __init__(self, guess: GuessResult):
#         self.guess = guess
#         special_chars = self.s_special_chars
#         num_rows = len(self.s_keys)
#         self.keys = keys = [[]] * num_rows
#         for i, symbols in enumerate(self.s_keys):
#             for j, c in enumerate(symbols):
#                 sh = ''
#                 cb = GuessResult.set_current_char
#                 exc = special_chars.get(i)
#                 if exc:
#                     spec = exc.get(j)
#                     if spec:
#                         sh, cb = spec
#
#                 key = Key(guess, c, sh, cb)
#                 keys[i].append(key)
#
#     def widget(self) -> ux.Widget:
#         w = ux.Widget()
#         lay = ux.VBoxLayout()
#         w.set_layout(lay)
#
#         special_chars = self.s_special_chars
#         for i, keys in enumerate(self.s_keys):
#             hlay = ux.HBoxLayout()
#             for j, c in enumerate(keys):
#                 sh = ''
#                 cb = GuessResult.set_current_char
#                 exc = special_chars.get(i)
#                 if exc:
#                     spec = exc.get(j)
#                     if spec:
#                         sh, cb = spec
#
#                 b = ux_push_button(c, callback = cb)
#                 b.set_style_sheet(sh)
#                 avg_char_width = w.font_metrics().average_char_width()
#                 b.setMaximumWidth(3 * avg_char_width)
#
#                 hlay.add_widget(b)
#             lay.add_layout(hlay)
#
#
#         return w

class Game(Traitable):
    num_chars: int  = RT(T.HIDDEN, default = 5)

    the_word: str   = RT(T.HIDDEN)
    guess: str      = RT( ui_hint = Ui('>'))
    push: bool      = RT( ui_hint = Ui('Try', widget_type = Ui.WIDGET_TYPE.PUSH, right_label = True))

    count: int      = RT(T.HIDDEN, default = 6)
    current: int    = RT(T.HIDDEN, default = 0)

    guess_res_class: type   = RT(T.HIDDEN)
    attempts: list          = RT(T.HIDDEN)

    top_editor: TraitableEditor = RT()
    table: TableView        = RT()
    # keyboard: Keyboard      = RT()

    def the_word_get(self) -> str:
        return _GuessWordData.new_word(self.num_chars).upper()

    def guess_set(self, trait, value: str) -> RC:
        self.raw_set_value(trait, value.upper())
        return RC_TRUE

    def guess_res_class_get(self):
        num_chars = self.num_chars

        class Demo(GuessResult):
            @classmethod
            def own_trait_definitions(cls) -> Generator[tuple[str, trait_definition.TraitDefinition]]:
                yield from (tri for i in range(num_chars) if (tri := GuessResult._create_char_trait(i)))

        Demo.traits()
        return Demo

    def guess_result(self, guess: str):
        demo_class = self.guess_res_class
        return demo_class(the_word=self.the_word, guess=guess)

    def push_get(self) -> bool:
        return self.current < self.count

    def attempts_get(self) -> list:
        num_chars = self.num_chars
        return [self.guess_result(num_chars * ' ') for _ in range(self.count)]

    def push_action(self, editor):
        current = self.current
        guess = self.guess
        if len(guess) != self.num_chars:
            ux_warning(f'The word is {self.num_chars} characters long.')
            return

        if not _GuessWordData.word_exists(guess):
            ux_warning(f"Unfamiliar noun '{guess}'")
            return

        gr = self.guess_result(self.guess)
        attempts = self.attempts
        attempts[current] = gr
        self.table.render_traitable(current, None)

        if all(s == CHAR_STATE.BINGO for s in gr.char_state):
            ux_success('Great job - you got it!')
            return

        current += 1
        if current >= self.count:
            ux_warning('Unfortunately you have failed this time')

        self.current = current

    def top_editor_get(self) -> TraitableEditor:
        return TraitableEditor.editor(self)

    def table_get(self) -> TableView:
        table = TableView(self.attempts)
        hv = table.horizontalHeader()
        hv.setStretchLastSection(False)
        return table

    # def keyboard_get(self) -> Keyboard:
    #     return Keyboard(GuessResult())

    def widget(self):
        ux.init()
        w = ux.Widget()
        lay = ux.VBoxLayout()
        w.set_layout(lay)

        top = self.top_editor.row_layout()
        lay.add_layout(top)
        lay.add_widget(ux.separator())

        lay.add_widget(self.table)

        #lay.add_widget(ux.separator())
        #lay.add_widget(self.keyboard.widget())

        return w


class _GuessWordData:
    MODULE_NAME = '_guess_word_data'
    NUM_CHARS   = (5, 6)

    @classmethod
    def download_nouns(cls, filename: str):
        import nltk
        from nltk.corpus import wordnet as wn

        if os.path.exists(filename):
            return

        nltk.download('wordnet')
        noun_pool = [
            w.name() for s in wn.all_synsets('n') for w in s.lemmas() if len(w.name()) in cls.NUM_CHARS and w.name().isalpha() and w.name().islower()
        ]

        with open(filename, 'w') as f:
            print('noun_pool = {', file=f)
            for n in cls.NUM_CHARS:
                print(f'\t{n}: [', file=f)
                pool = [w for w in noun_pool if len(w) == n]
                for w in pool:
                    print(f'\t\t{w!r},', file=f)
                print('\t],', file=f)
            print('}', file=f)

    @classmethod
    @cache
    def noun_pool(cls) -> dict:
        import importlib
        import importlib.util
        from pathlib import Path

        package_name = cls.__module__.rsplit('.', 1)[0]
        spec = importlib.util.find_spec(package_name)
        assert spec.submodule_search_locations
        package_dir = Path(spec.submodule_search_locations[0])
        file_name = package_dir / f'{cls.MODULE_NAME}.py'
        #cls.download_nouns(file_name)

        module_name = f'{package_name}.{cls.MODULE_NAME}'
        m = importlib.import_module(module_name)
        noun_pool = getattr(m, 'NOUN_POOL', None)
        assert noun_pool and type(noun_pool) is dict, 'noun_pool must be a non-empty dict by num chars'
        return noun_pool

    @classmethod
    def word_exists(cls, w: str) -> bool:
        noun_pool = cls.noun_pool()
        n = len(w)
        words = noun_pool.get(n)
        return words and w.lower() in words

    @classmethod
    def new_word(cls, n: int) -> str:
        noun_pool = cls.noun_pool()
        words = noun_pool.get(n)
        if words is None:
            raise AssertionError(f'There are no {n}-letter words available')
        return random.choice(words)


if __name__ == '__main__':
    from core_10x.exec_control import INTERACTIVE
    from ui_10x.examples.guess_word import Game, _GuessWordData
    from ui_10x.utils import UxDialog

    with INTERACTIVE():
        game = Game()
        w = game.widget()

        d = UxDialog(w, title = f'You have {game.count} attempts to guess a word')
        d.exec()
