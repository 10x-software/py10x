from __future__ import annotations

from dataclasses import dataclass

from ui_10x.examples.guess_word import Game
from ui_10x.rio.component_builder import UserSessionContext
from ui_10x.utils import UxDialog

import rio


def guess_word_dialog() -> tuple[Game, UxDialog]:
    """Same tree as desktop ``guess_word.__main__``."""
    game = Game()
    w = game.widget()
    dialog = UxDialog(
        w,
        title=f'You have {game.count} attempts to guess a word',
        ok='',
        cancel='',
        open_callback=game.bind,
    )
    return game, dialog


@dataclass
class GuessWordSession:
    """Per-session Game/dialog. Not Rio component state (avoids a rebuild loop)."""

    game: Game | None = None
    dialog: UxDialog | None = None

    @classmethod
    def of(cls, session: rio.Session) -> GuessWordSession:
        try:
            return session[cls]
        except Exception:  # noqa: BLE001 - missing attachment
            bag = cls()
            session.attach(bag)
            return bag

    def ensure(self) -> None:
        if self.game is None:
            self.game, self.dialog = guess_word_dialog()
            self.dialog.on_open()


class GuessWordComponent(rio.Component):
    def build(self) -> rio.Component:
        bag = GuessWordSession.of(self.session)
        if bag.dialog is None:
            with self.session[UserSessionContext]:
                bag.ensure()
        return bag.dialog()
