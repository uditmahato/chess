"""A FIDE-compliant standard chess rules engine.

Public API::

    from chess import Game, Move, Board

See :mod:`chess.game` for the rule implementations and the audit report in
``AUDIT.md`` for the rule-by-rule compliance matrix.
"""

from .board import STARTING_FEN, Board
from .constants import (
    BLACK,
    WHITE,
    parse_square,
    square_name,
)
from .game import (
    AGREEMENT,
    AUTOMATIC_END_REASONS,
    CHECKMATE,
    CLAIMABLE_DRAW_REASONS,
    DEAD_POSITION,
    FIFTY_MOVE,
    FIVEFOLD,
    RESIGNATION,
    RESULT_BLACK,
    RESULT_DRAW,
    RESULT_ONGOING,
    RESULT_WHITE,
    SEVENTYFIVE_MOVE,
    STALEMATE,
    THREEFOLD,
    Game,
    GameOverError,
    IllegalMoveError,
)
from .move import Move

__all__ = [
    "Board",
    "Game",
    "Move",
    "STARTING_FEN",
    "WHITE",
    "BLACK",
    "parse_square",
    "square_name",
    "IllegalMoveError",
    "GameOverError",
    "CHECKMATE",
    "STALEMATE",
    "DEAD_POSITION",
    "FIVEFOLD",
    "SEVENTYFIVE_MOVE",
    "THREEFOLD",
    "FIFTY_MOVE",
    "AGREEMENT",
    "RESIGNATION",
    "RESULT_WHITE",
    "RESULT_BLACK",
    "RESULT_DRAW",
    "RESULT_ONGOING",
    "AUTOMATIC_END_REASONS",
    "CLAIMABLE_DRAW_REASONS",
]
