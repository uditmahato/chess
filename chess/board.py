"""Board representation, FEN handling and low-level attack detection.

The :class:`Board` only knows about piece placement.  All rules that depend on
game state (castling rights, side to move, en passant, clocks) live in
:class:`chess.game.Game`.
"""

from __future__ import annotations

from typing import List, Optional

from .constants import (
    BISHOP,
    BISHOP_DIRS,
    KING,
    KING_DELTAS,
    KNIGHT,
    KNIGHT_DELTAS,
    PAWN,
    QUEEN,
    ROOK,
    ROOK_DIRS,
    WHITE,
    file_of,
    on_board,
    rank_of,
    square,
)

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class Board:
    """An 8x8 board of piece characters (or ``None``)."""

    __slots__ = ("squares",)

    def __init__(self, squares: Optional[List[Optional[str]]] = None):
        if squares is None:
            self.squares = [None] * 64
        else:
            if len(squares) != 64:
                raise ValueError("board must have 64 squares")
            self.squares = list(squares)

    # -- construction ----------------------------------------------------
    @classmethod
    def from_placement(cls, placement: str) -> "Board":
        """Build a board from the piece-placement field of a FEN string."""
        board = cls()
        ranks = placement.split("/")
        if len(ranks) != 8:
            raise ValueError("FEN placement must have 8 ranks")
        # FEN lists rank 8 first, down to rank 1.
        for fen_rank_index, rank_text in enumerate(ranks):
            rank = 7 - fen_rank_index
            file = 0
            for ch in rank_text:
                if ch.isdigit():
                    file += int(ch)
                    if file > 8:
                        raise ValueError("rank overflow in FEN placement")
                elif ch in "pnbrqkPNBRQK":
                    if file > 7:
                        raise ValueError("rank overflow in FEN placement")
                    board.squares[square(file, rank)] = ch
                    file += 1
                else:
                    raise ValueError(f"invalid FEN character: {ch!r}")
            if file != 8:
                raise ValueError("rank does not describe 8 files")
        return board

    def placement(self) -> str:
        """Return the piece-placement field of a FEN string."""
        rows = []
        for rank in range(7, -1, -1):
            row = []
            empty = 0
            for file in range(8):
                piece = self.squares[square(file, rank)]
                if piece is None:
                    empty += 1
                else:
                    if empty:
                        row.append(str(empty))
                        empty = 0
                    row.append(piece)
            if empty:
                row.append(str(empty))
            rows.append("".join(row))
        return "/".join(rows)

    def copy(self) -> "Board":
        return Board(self.squares)

    # -- access ----------------------------------------------------------
    def piece_at(self, sq: int) -> Optional[str]:
        return self.squares[sq]

    def set(self, sq: int, piece: Optional[str]) -> None:
        self.squares[sq] = piece

    def king_square(self, color: str) -> Optional[int]:
        target = KING if color == WHITE else KING.lower()
        for sq, piece in enumerate(self.squares):
            if piece == target:
                return sq
        return None

    def pieces(self):
        """Iterate over ``(square, piece)`` for every occupied square."""
        for sq, piece in enumerate(self.squares):
            if piece is not None:
                yield sq, piece

    # -- attack detection ------------------------------------------------
    def is_attacked(self, sq: int, by_color: str) -> bool:
        """Return ``True`` if *sq* is attacked by any piece of *by_color*.

        This is used both for check detection (3.9) and for the castling
        "not attacked" restrictions (3.8.2.2).  It is independent of whose
        turn it is.
        """
        f = file_of(sq)
        r = rank_of(sq)

        # Pawn attacks.  A pawn of `by_color` attacks diagonally forward, so it
        # sits one rank *behind* the target from its own point of view.
        pawn = PAWN if by_color == WHITE else PAWN.lower()
        pawn_rank = r - 1 if by_color == WHITE else r + 1
        for df in (-1, 1):
            if on_board(f + df, pawn_rank):
                if self.squares[square(f + df, pawn_rank)] == pawn:
                    return True

        # Knight attacks.
        knight = KNIGHT if by_color == WHITE else KNIGHT.lower()
        for df, dr in KNIGHT_DELTAS:
            if on_board(f + df, r + dr):
                if self.squares[square(f + df, r + dr)] == knight:
                    return True

        # King attacks (adjacency).
        king = KING if by_color == WHITE else KING.lower()
        for df, dr in KING_DELTAS:
            if on_board(f + df, r + dr):
                if self.squares[square(f + df, r + dr)] == king:
                    return True

        # Sliding attacks: bishops/queens on diagonals, rooks/queens on lines.
        bishop = BISHOP if by_color == WHITE else BISHOP.lower()
        rook = ROOK if by_color == WHITE else ROOK.lower()
        queen = QUEEN if by_color == WHITE else QUEEN.lower()

        for df, dr in BISHOP_DIRS:
            nf, nr = f + df, r + dr
            while on_board(nf, nr):
                piece = self.squares[square(nf, nr)]
                if piece is not None:
                    if piece == bishop or piece == queen:
                        return True
                    break
                nf += df
                nr += dr

        for df, dr in ROOK_DIRS:
            nf, nr = f + df, r + dr
            while on_board(nf, nr):
                piece = self.squares[square(nf, nr)]
                if piece is not None:
                    if piece == rook or piece == queen:
                        return True
                    break
                nf += df
                nr += dr

        return False

    def attackers_of_king(self, color: str) -> List[int]:
        """Squares of *opponent* pieces giving check to *color*'s king.

        Used to demonstrate single vs. double check.  Returns an empty list if
        the king is not in check (or absent).
        """
        king_sq = self.king_square(color)
        if king_sq is None:
            return []
        enemy = "b" if color == WHITE else "w"
        result = []
        f = file_of(king_sq)
        r = rank_of(king_sq)

        pawn = PAWN if enemy == WHITE else PAWN.lower()
        pawn_rank = r - 1 if enemy == WHITE else r + 1
        for df in (-1, 1):
            if on_board(f + df, pawn_rank) and self.squares[square(f + df, pawn_rank)] == pawn:
                result.append(square(f + df, pawn_rank))

        knight = KNIGHT if enemy == WHITE else KNIGHT.lower()
        for df, dr in KNIGHT_DELTAS:
            if on_board(f + df, r + dr) and self.squares[square(f + df, r + dr)] == knight:
                result.append(square(f + df, r + dr))

        bishop = BISHOP if enemy == WHITE else BISHOP.lower()
        rook = ROOK if enemy == WHITE else ROOK.lower()
        queen = QUEEN if enemy == WHITE else QUEEN.lower()
        for df, dr in BISHOP_DIRS:
            nf, nr = f + df, r + dr
            while on_board(nf, nr):
                piece = self.squares[square(nf, nr)]
                if piece is not None:
                    if piece == bishop or piece == queen:
                        result.append(square(nf, nr))
                    break
                nf += df
                nr += dr
        for df, dr in ROOK_DIRS:
            nf, nr = f + df, r + dr
            while on_board(nf, nr):
                piece = self.squares[square(nf, nr)]
                if piece is not None:
                    if piece == rook or piece == queen:
                        result.append(square(nf, nr))
                    break
                nf += df
                nr += dr
        return result

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Board) and self.squares == other.squares

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        lines = []
        for rank in range(7, -1, -1):
            row = []
            for file in range(8):
                piece = self.squares[square(file, rank)]
                row.append(piece if piece else ".")
            lines.append(" ".join(row))
        return "\n".join(lines)
