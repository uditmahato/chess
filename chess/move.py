"""The :class:`Move` value object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .constants import square_name


@dataclass(frozen=True)
class Move:
    """A single move.

    Attributes
    ----------
    frm, to:
        Origin and destination square indices (0..63).
    promotion:
        Upper-case piece kind (``Q``/``R``/``B``/``N``) when the move promotes a
        pawn, otherwise ``None``.
    is_castle_kingside, is_castle_queenside:
        Set for the two castling moves.
    is_en_passant:
        Set when the move is an en passant capture.
    is_double_pawn_push:
        Set when a pawn advances two squares (creates an en passant target).
    """

    frm: int
    to: int
    promotion: Optional[str] = None
    is_castle_kingside: bool = False
    is_castle_queenside: bool = False
    is_en_passant: bool = False
    is_double_pawn_push: bool = False

    def uci(self) -> str:
        """Long algebraic (UCI) representation, e.g. ``e2e4`` or ``e7e8q``."""
        text = square_name(self.frm) + square_name(self.to)
        if self.promotion:
            text += self.promotion.lower()
        return text

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.uci()
