from collections.abc import Generator

import core_10x.trait_definition as trait_definition
from core_10x.entity import RC, RC_TRUE, RT, Entity, T, Ui

from ui_10x.platform_interface import HBoxLayout, PushButton, VBoxLayout, Widget
from ui_10x.table_view import TableView
from ui_10x.utils import UxDialog, ux


class CHAR_STATE:
    NONE        = ( 'lightgray',    'black' )
    WRONG_POS   = ( 'white',        'black' )
    BINGO       = ( 'darkgreen',    'white' )


class GuessResult( Entity ):
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

class Game(Entity):
    the_word: str   = RT()
    num_chars: int  = RT()
    guess: str      = RT( ui_hint = Ui('>'))
    push: bool      = RT( ui_hint = Ui('*', widget_type = Ui.WIDGET_TYPE.PUSH, right_label = True, max_width = 3))

    count: int      = RT(6)
    current: int    = RT(0)

    guess_res_class: type   = RT()
    attempts: list          = RT()
    table: TableView        = RT()

    def the_word_set(self, trait, value: str) -> RC:
        self.raw_set_value(trait, value.upper())
        return RC_TRUE

    def guess_set(self, trait, value: str) -> RC:
        self.raw_set_value(trait, value.upper())
        return RC_TRUE

    def num_chars_get(self) -> int:
        return len(self.the_word)

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


    def table_get( self ) -> TableView:
        table = TableView( self.attempts() )
        hv = table.horizontalHeader()
        hv.setStretchLastSection( False )

        return table

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
    def keyboard( self ):
        w = Widget()
        lay = VBoxLayout()
        w.setLayout( lay )

        for i, keys in enumerate( self.s_keys ):
            hlay = HBoxLayout()
            for j, c in enumerate( keys ):
                b = PushButton( c )
                styles = self.s_style.get( i )
                if styles:
                    sh = styles.get( j )
                    if sh:
                        b.setStyleSheet( sh )

                avg_char_width = w.fontMetrics().averageCharWidth()
                b.setMaximumWidth( 3 * avg_char_width )

                hlay.addWidget( b )
            lay.addLayout( hlay )

        return w

    def widget( self ):
        ux.init()
        w = Widget()
        lay = VBoxLayout()
        w.setLayout( lay )

        self.m_top_editor = top_editor = EntityEditor( self )
        top = top_editor.row()
        lay.addLayout( top )
        lay.addWidget( ux.separator() )

        table = self.table()
        lay.addWidget( table )

        lay.addWidget( ux.separator() )
        lay.addWidget( self.keyboard() )

        return w

if __name__ == '__main__':
    from asu.ui.entity_editor import EntityEditor

    game = Game( the_word = 'credo' )
    w = game.widget()

    d = UxDialog( w, title = f'You have {game.count()} attempts to guess a word' )
    d.exec_()
