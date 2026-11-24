"""Qt6 counterpart of rio/unit_tests/test_guess_word.py: the desktop ``exec`` shape (Rio's examples page has no Qt analog)."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableView

from core_10x.exec_control import INTERACTIVE
import ui_10x.examples.guess_word as gw
from ui_10x.examples.guess_word import Game, _GuessWordData
from ui_10x.qt6.testlib import qt_helpers as h
from ui_10x.utils import UxDialog


@pytest.fixture
def silence_message_boxes(monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(gw, 'ux_warning', lambda text, *a, **k: calls.append(('warn', text)))
    monkeypatch.setattr(gw, 'ux_success', lambda text, *a, **k: calls.append(('ok', text)))
    return calls


def test_guess_word_desktop_exec_shape(silence_message_boxes) -> None:
    """``guess_word.__main__``: Game under INTERACTIVE in an exec()'d dialog; type, lose focus, Try."""
    with INTERACTIVE():
        game    = Game()
        dialog  = UxDialog(game.widget(), title = f'You have {game.count} attempts to guess a word', open_callback = game.bind)
        guess   = next(w for w in _GuessWordData.noun_pool()[game.num_chars] if w.upper() != game.the_word).upper()

        def play(d):
            h.type_text(h.trait_widgets(d)['guess'], guess)
            assert game.guess == guess, 'the guess is committed on lost focus'
            h.click(h.button(d, 'Try'))
            assert not [c for c in silence_message_boxes if c[0] == 'warn'], silence_message_boxes

            model   = d.findChildren(QTableView)[0].model()
            row     = ''.join(model.data(model.index(0, c), Qt.ItemDataRole.DisplayRole) for c in range(model.columnCount()))
            assert row == guess
            h.click(h.button(d, 'Cancel'))

        h.run_modal(dialog.exec, play)
