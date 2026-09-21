"""Core constants and small helpers for the chess engine.

Board representation
--------------------
Squares are integers 0..63 with ``index = rank * 8 + file`` where ``rank == 0``
is White's first rank (rank "1") and ``file == 0`` is the a-file.  Hence
``a1 == 0``, ``h1 == 7``, ``a8 == 56`` and ``h8 == 63``.

Pieces are single characters, upper-case for White and lower-case for Black,
matching Forsyth-Edwards Notation (FEN): ``P N B R Q K`` / ``p n b r q k``.
Empty squares are represented by ``None`` in the board array.
"""

from __future__ import annotations

WHITE = "w"
BLACK = "b"

# Piece letters (colour-agnostic, upper case is the canonical "kind").
PAWN = "P"
KNIGHT = "N"
BISHOP = "B"
ROOK = "R"
QUEEN = "Q"
KING = "K"

PIECE_KINDS = (PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING)
PROMOTION_KINDS = (QUEEN, ROOK, BISHOP, KNIGHT)  # 3.7.5.1: Q, R, B or N only.

FILES = "abcdefgh"
RANKS = "12345678"


def color_of(piece: str) -> str:
    """Return the colour (``WHITE``/``BLACK``) of a FEN piece character."""
    return WHITE if piece.isupper() else BLACK


def kind_of(piece: str) -> str:
    """Return the colour-agnostic kind (upper-case letter) of a piece."""
    return piece.upper()


def opposite(color: str) -> str:
    return BLACK if color == WHITE else WHITE


def square(file: int, rank: int) -> int:
    return rank * 8 + file


def file_of(sq: int) -> int:
    return sq % 8


def rank_of(sq: int) -> int:
    return sq // 8


def on_board(file: int, rank: int) -> bool:
    return 0 <= file < 8 and 0 <= rank < 8


def square_name(sq: int) -> str:
    """Algebraic name of a square, e.g. ``0 -> 'a1'``."""
    return FILES[file_of(sq)] + RANKS[rank_of(sq)]


def parse_square(name: str) -> int:
    """Parse an algebraic square name such as ``'e4'`` into an index."""
    name = name.strip().lower()
    if len(name) != 2 or name[0] not in FILES or name[1] not in RANKS:
        raise ValueError(f"invalid square name: {name!r}")
    return square(FILES.index(name[0]), RANKS.index(name[1]))


# Movement offset tables expressed as (file_delta, rank_delta).
KNIGHT_DELTAS = (
    (1, 2), (2, 1), (2, -1), (1, -2),
    (-1, -2), (-2, -1), (-2, 1), (-1, 2),
)
KING_DELTAS = (
    (1, 0), (1, 1), (0, 1), (-1, 1),
    (-1, 0), (-1, -1), (0, -1), (1, -1),
)
BISHOP_DIRS = ((1, 1), (1, -1), (-1, 1), (-1, -1))
ROOK_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
QUEEN_DIRS = BISHOP_DIRS + ROOK_DIRS
