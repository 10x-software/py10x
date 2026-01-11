from __future__ import annotations

from typing import TYPE_CHECKING
import os
import random

import core_10x.trait_definition as trait_definition
from core_10x.traitable import RC, RC_TRUE, RT, Traitable, T, Ui
from core_10x.global_cache import cache

from ui_10x.utils import ux, UxDialog
from ui_10x.platform_interface import HBoxLayout, PushButton, VBoxLayout, Widget
#from ui_10x.table_view import TableView
#from ui_10x.traitable_editor import TraitableEditor

if TYPE_CHECKING:
    from collections.abc import Generator

class CHAR_STATE:
    NONE        = ( 'lightgray',    'black' )
    WRONG_POS   = ( 'white',        'black' )
    BINGO       = ( 'darkgreen',    'white' )


class GuessResult(Traitable):
    the_word: str    = RT()
    guess: str       = RT()
    num_chars: int   = RT()

    demo_class: type = RT()

    char_state: list = RT()

    guessed_chars: list = RT()
    current_char: int   = RT(0)

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
        res = [ CHAR_STATE.NONE ] * num_chars
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
        #return ( name, T( str, f'{i+1}' ) )
        return (
            name,
            trait_definition.TraitDefinition(
                **{
                    trait_definition.NAME_TAG:      name,
                    trait_definition.DATATYPE_TAG:  str,
                    trait_definition.FLAGS_TAG:     T.RUNTIME
                }
            )
        )

    def keyboard(self):
        w = Widget()
        lay = VBoxLayout()
        w.set_layout(lay)

        for i, keys in enumerate(self.s_keys):
            hlay = HBoxLayout()
            for j, c in enumerate(keys):
                b = PushButton(c)
                styles = self.s_style.get(i)
                if styles:
                    sh = styles.get(j)
                    if sh:
                        b.set_style_sheet(sh)

                avg_char_width = w.font_metrics().average_char_width()
                b.setMaximumWidth(3 * avg_char_width)

                hlay.add_widget(b)
            lay.add_layout(hlay)

        return w

class Key:
    def __init__(self, guess: GuessResult, c: str, stylesheet: str, callback):
        self.guess = guess
        self.c = c
        self.stylesheet = stylesheet
        self.callback = callback
        self.w: PushButton = None

    def widget(self, parent_w: Widget ) -> PushButton:
        if not self.w:
            self.w = b = PushButton(self.c)
            b.clicked_connect(lambda w: self.callback(w))
            b.set_style_sheet(self.stylesheet)
            avg_char_width = parent_w.font_metrics().average_char_width()
            b.setMaximumWidth(3 * avg_char_width)

        return self.w

class Keyboard:
    s_keys = [
        'qwertyuiop',
        'asdfghjkl',
        '*zxcvbnm<'
    ]
    s_special_chars = {
        2:  {
            0:                      ( 'background-color: green; color: white',  GuessResult.accept_guess ),
            len(s_keys[2]) - 1:     ( 'background-color: red; color: white',    GuessResult.delete_char ),
        }
    }

    def __init__(self, guess: GuessResult):
        self.guess = guess
        special_chars = self.s_special_chars
        num_rows = len(self.s_keys)
        self.keys = keys = [ [] ] * num_rows
        for i, symbols in enumerate(self.s_keys):
            for j, c in enumerate( symbols ):
                sh = ''
                cb = GuessResult.set_current_char
                exc = special_chars.get(i)
                if exc:
                    spec = exc.get(j)
                    if spec:
                        sh, cb = spec

                key = Key(guess, c, sh, cb)
                keys[i].append(key)

    def widget( self ) -> Widget:
        ...

class Game(Traitable):
    num_chars: int  = RT(5)

    the_word: str   = RT()
    guess: str      = RT( ui_hint = Ui('>'))
    push: bool      = RT( ui_hint = Ui('*', widget_type = Ui.WIDGET_TYPE.PUSH, right_label = True, max_width = 3))

    count: int      = RT(6)
    current: int    = RT(0)

    guess_res_class: type   = RT()
    attempts: list          = RT()
    #table: TableView        = RT()

    def the_word_get(self) -> str:
        return _GuessWordData.new_word(self.num_chars).upper()

    def guess_set(self, trait, value: str) -> RC:
        self.raw_set_value(trait, value.upper())
        return RC_TRUE

    def guess_res_class_get(self):
        num_chars = self.num_chars
        class Demo(GuessResult):
            @staticmethod
            def own_trait_definitions(bases: tuple, inherited_trait_dir: dict, class_dict: dict, rc: RC) -> Generator[tuple[str, trait_definition.TraitDefinition]]:
                yield from (tri for i in range( num_chars ) if ( tri := GuessResult._create_char_trait( i ) ))

        Demo.traits()
        return Demo

    def guess_result(self, guess: str):
        demo_class = self.guess_res_class
        return demo_class(the_word = self.the_word, guess = guess)

    def push_get(self) -> bool:
        return self.current < self.count

    def attempts_get(self) -> list:
        num_chars = self.num_chars
        return [ self.guess_result(num_chars * ' ') for _ in range(self.count) ]

    def push_action( self, editor ):
        current = self.current()
        guess = self.guess()
        if len( guess ) != self.num_chars():
            ux.warning( f'The word is {self.num_chars()} characters long.' )
            return

        gr = self.guess_result( self.guess() )
        attempts = self.attempts()
        attempts[ current ] = gr
        self.table().renderEntity( current, None )

        if all( s == CHAR_STATE.BINGO for s in gr.char_state() ):
            ux.success( 'Great job - you got it!')

        current += 1
        if current >= self.count():
            ux.warning( 'Unfortunately you have failed this time' )

        self.current = current


    # def table_get( self ) -> TableView:
    #     table = TableView( self.attempts() )
    #     hv = table.horizontalHeader()
    #     hv.setStretchLastSection( False )
    #
    #     return table

    s_keys = [
        'qwertyuiop',
        'asdfghjkl',
        '*zxcvbnm<'
    ]
    s_style = {
        2:  {
            0:                          'background-color: green; color: white',
            len( s_keys[ 2 ] ) - 1:     'background-color: red; color: white'
        }
    }
    def keyboard(self):
        w = Widget()
        lay = VBoxLayout()
        w.set_layout(lay)

        for i, keys in enumerate(self.s_keys):
            hlay = HBoxLayout()
            for j, c in enumerate(keys):
                b = PushButton(c)
                styles = self.s_style.get(i)
                if styles:
                    sh = styles.get(j)
                    if sh:
                        b.set_style_sheet(sh)

                avg_char_width = w.font_metrics().average_char_width()
                b.setMaximumWidth( 3 * avg_char_width )

                hlay.add_widget(b)
            lay.add_layout(hlay)

        return w

    def widget(self):
        ux.init()
        w = Widget()
        lay = VBoxLayout()
        w.set_layout(lay)

        self.m_top_editor = top_editor = ( self )
        top = top_editor.row()
        lay.add_layout(top)
        lay.add_widget(ux.separator())

        table = self.table()
        lay.add_widget(table)

        lay.add_widget(ux.separator())
        lay.add_widget(self.keyboard())

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
        NOUN_POOL = [
            w.name() for s in wn.all_synsets('n') for w in s.lemmas()
            if len(w.name()) in cls.NUM_CHARS and w.name().isalpha() and w.name().islower()
        ]

        with open(filename, 'w') as f:
            print('NOUN_POOL = {', file = f)
            for n in cls.NUM_CHARS:
                print(f'\t{n}: [', file = f)
                pool = [ w for w in NOUN_POOL if len(w) == n ]
                for w in pool:
                    print(f'\t\t{repr(w)},', file = f)
                print('\t],', file = f)
            print('}', file = f)

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
        cls.download_nouns(file_name)

        module_name = f'{package_name}.{cls.MODULE_NAME}'
        m = importlib.import_module(module_name)
        noun_pool = getattr(m, 'NOUN_POOL', None)
        assert noun_pool and type(noun_pool) is dict, 'NOUN_POOL must be a non-empty dict by num chars'
        return noun_pool

    @classmethod
    def word_exists(cls, w: str) -> bool:
        noun_pool = cls.noun_pool()
        n = len(w)
        words = noun_pool.get(n)
        return words and w in words

    @classmethod
    def new_word(cls, n: int) -> str:
        noun_pool = cls.noun_pool()
        words = noun_pool.get(n)
        if words is None:
            raise AssertionError(f'There are no {n}-letter words available')
        return random.choice(words)

if __name__ == '__main__':
    from ui_10x.examples.guess_word import _GuessWordData, Game

    game = Game()
    #w = game.widget()

    w = game.the_word

    #d = UxDialog( w, title = f'You have {game.count()} attempts to guess a word' )
    #d.exec()
