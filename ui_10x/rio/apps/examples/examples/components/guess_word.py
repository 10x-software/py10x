from __future__ import annotations

from ui_10x.examples.guess_word import Game
from ui_10x.rio.component_builder import session_context
from ui_10x.utils import UxDialog

import rio


class GuessWordDialog(UxDialog): ...


class GuessWordComponent(rio.Component):
    def build(self) -> rio.Component:
        try:
            dialog = self.session[GuessWordDialog]
        except KeyError:
            with session_context(self.session):
                game = Game()
                dialog = GuessWordDialog(
                    game.widget(),
                    title=f'You have {game.count} attempts to guess a word',
                    ok='',
                    cancel='',
                    open_callback=game.bind,
                )
                self.session.attach(dialog)
                dialog.on_open()
        return dialog()
