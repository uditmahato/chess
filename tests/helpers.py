"""Shared test helpers."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chess import Game  # noqa: E402
from chess.constants import parse_square  # noqa: E402


def uci_set(game: Game):
    """Return the set of legal moves as UCI strings."""
    return {m.uci() for m in game.legal_moves()}


def moves_from(game: Game, square_name: str):
    """Legal moves originating from a given square (as UCI strings)."""
    sq = parse_square(square_name)
    return {m.uci() for m in game.legal_moves() if m.frm == sq}


def play(game: Game, *ucis: str):
    """Play a sequence of UCI moves, returning the game for chaining."""
    for u in ucis:
        game.push_uci(u)
    return game
