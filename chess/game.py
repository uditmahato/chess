"""Game state and the full rules of standard chess (FIDE Laws, 2023).

This module ties the board together with side to move, castling rights, the en
passant target, the move clocks and position history, and implements:

* legal move generation with king-safety filtering (pins, discovered/double
  check all fall out of this naturally);
* castling and its restrictions (Art. 3.8.2);
* en passant (Art. 3.7.3);
* promotion and promotion-piece selection (Art. 3.7.5);
* check / checkmate / stalemate (Art. 3.9, 5.1.1, 5.2.1);
* dead position / insufficient material (Art. 5.2.2);
* threefold (claimable) and fivefold (automatic) repetition (Art. 9.2 / 9.6.1);
* fifty-move (claimable) and seventy-five-move (automatic) rules
  (Art. 9.3 / 9.6.2);
* draw by agreement (Art. 5.2.3 / 9.1) and resignation (Art. 5.1.2).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .board import STARTING_FEN, Board
from .constants import (
    BISHOP,
    BISHOP_DIRS,
    KING,
    KING_DELTAS,
    KNIGHT,
    KNIGHT_DELTAS,
    PROMOTION_KINDS,
    QUEEN,
    QUEEN_DIRS,
    ROOK,
    ROOK_DIRS,
    WHITE,
    BLACK,
    color_of,
    file_of,
    kind_of,
    on_board,
    opposite,
    rank_of,
    square,
    square_name,
)
from .move import Move

# ---------------------------------------------------------------------------
# Result and status vocabulary
# ---------------------------------------------------------------------------
RESULT_ONGOING = "*"
RESULT_WHITE = "1-0"
RESULT_BLACK = "0-1"
RESULT_DRAW = "1/2-1/2"

# Reasons a game has ended (or can end).
CHECKMATE = "checkmate"
STALEMATE = "stalemate"
DEAD_POSITION = "dead_position"
FIVEFOLD = "fivefold_repetition"
SEVENTYFIVE_MOVE = "seventyfive_move"
THREEFOLD = "threefold_repetition"
FIFTY_MOVE = "fifty_move"
AGREEMENT = "draw_by_agreement"
RESIGNATION = "resignation"

#: Reasons that end the game automatically, with no claim required (Art. 9.6,
#: 5.2.1, 5.2.2, 5.1.1).
AUTOMATIC_END_REASONS = frozenset(
    {CHECKMATE, STALEMATE, DEAD_POSITION, FIVEFOLD, SEVENTYFIVE_MOVE}
)
#: Reasons a player *may claim* but which do not end the game automatically
#: (Art. 9.2, 9.3).
CLAIMABLE_DRAW_REASONS = frozenset({THREEFOLD, FIFTY_MOVE})


class IllegalMoveError(ValueError):
    """Raised when an illegal move is attempted."""


class GameOverError(RuntimeError):
    """Raised when trying to move in a game that has already ended."""


class Game:
    """A full chess game with FIDE rule enforcement."""

    def __init__(self, fen: str = STARTING_FEN):
        self.board: Board
        self.side_to_move: str
        self.castling: str
        self.ep_square: Optional[int]
        self.halfmove_clock: int
        self.fullmove_number: int
        self._load_fen(fen)

        # Terminal state.
        self.result: str = RESULT_ONGOING
        self.termination: Optional[str] = None

        # Draw-offer bookkeeping (Art. 9.1).
        self.pending_draw_offer: Optional[str] = None  # colour that offered

        # Position history for repetition detection (Art. 9.2/9.6.1).
        # Maps position key -> number of occurrences.  Seeded with the initial
        # position.
        self._position_counts: Dict[str, int] = {}
        self._ply: int = 0  # half-moves played, for "both players moved" checks
        self._record_position()
        # A position loaded directly from FEN may already be terminal
        # (checkmate, stalemate, dead position, or past the 75-move limit).
        self._update_status()

    # ------------------------------------------------------------------
    # FEN
    # ------------------------------------------------------------------
    def _load_fen(self, fen: str) -> None:
        parts = fen.strip().split()
        if len(parts) < 4:
            raise ValueError("FEN must have at least 4 fields")
        placement, active, castling, ep = parts[0], parts[1], parts[2], parts[3]
        halfmove = parts[4] if len(parts) > 4 else "0"
        fullmove = parts[5] if len(parts) > 5 else "1"

        self.board = Board.from_placement(placement)
        if active not in ("w", "b"):
            raise ValueError("active colour must be 'w' or 'b'")
        self.side_to_move = WHITE if active == "w" else BLACK

        if castling == "-":
            self.castling = ""
        else:
            for ch in castling:
                if ch not in "KQkq":
                    raise ValueError(f"invalid castling field: {castling!r}")
            # Keep canonical order KQkq.
            self.castling = "".join(c for c in "KQkq" if c in castling)

        self.ep_square = None if ep == "-" else self._parse_ep(ep)
        self.halfmove_clock = int(halfmove)
        self.fullmove_number = int(fullmove)

    @staticmethod
    def _parse_ep(ep: str) -> int:
        from .constants import parse_square

        return parse_square(ep)

    def fen(self) -> str:
        active = "w" if self.side_to_move == WHITE else "b"
        castling = self.castling if self.castling else "-"
        ep = square_name(self.ep_square) if self.ep_square is not None else "-"
        return " ".join(
            [
                self.board.placement(),
                active,
                castling,
                ep,
                str(self.halfmove_clock),
                str(self.fullmove_number),
            ]
        )

    # ------------------------------------------------------------------
    # Basic queries
    # ------------------------------------------------------------------
    def is_over(self) -> bool:
        return self.result != RESULT_ONGOING

    def is_in_check(self, color: Optional[str] = None) -> bool:
        """Whether *color* (default: side to move) is in check (Art. 3.9)."""
        color = color or self.side_to_move
        king_sq = self.board.king_square(color)
        if king_sq is None:
            return False
        return self.board.is_attacked(king_sq, opposite(color))

    def checking_pieces(self, color: Optional[str] = None) -> List[int]:
        """Squares of pieces giving check to *color* (default side to move).

        Length 2 means double check (Art.: only a king move can escape).
        """
        color = color or self.side_to_move
        return self.board.attackers_of_king(color)

    # ------------------------------------------------------------------
    # Move generation
    # ------------------------------------------------------------------
    def _pseudo_legal_moves(self, color: str) -> List[Move]:
        """All moves for *color* ignoring whether they leave the king in check.

        Castling is added by :meth:`legal_moves` because its legality depends on
        attacked squares.
        """
        moves: List[Move] = []
        for sq, piece in self.board.pieces():
            if color_of(piece) != color:
                continue
            kind = kind_of(piece)
            if kind == "P":
                self._pawn_moves(sq, color, moves)
            elif kind == "N":
                self._step_moves(sq, color, KNIGHT_DELTAS, moves)
            elif kind == "K":
                self._step_moves(sq, color, KING_DELTAS, moves)
            elif kind == "B":
                self._slide_moves(sq, color, BISHOP_DIRS, moves)
            elif kind == "R":
                self._slide_moves(sq, color, ROOK_DIRS, moves)
            elif kind == "Q":
                self._slide_moves(sq, color, QUEEN_DIRS, moves)
        return moves

    def _step_moves(self, sq, color, deltas, moves):
        f, r = file_of(sq), rank_of(sq)
        for df, dr in deltas:
            nf, nr = f + df, r + dr
            if not on_board(nf, nr):
                continue
            target = square(nf, nr)
            occupant = self.board.piece_at(target)
            if occupant is None or color_of(occupant) != color:
                moves.append(Move(sq, target))

    def _slide_moves(self, sq, color, dirs, moves):
        f, r = file_of(sq), rank_of(sq)
        for df, dr in dirs:
            nf, nr = f + df, r + dr
            while on_board(nf, nr):
                target = square(nf, nr)
                occupant = self.board.piece_at(target)
                if occupant is None:
                    moves.append(Move(sq, target))
                else:
                    if color_of(occupant) != color:
                        moves.append(Move(sq, target))
                    break
                nf += df
                nr += dr

    def _pawn_moves(self, sq, color, moves):
        f, r = file_of(sq), rank_of(sq)
        direction = 1 if color == WHITE else -1
        start_rank = 1 if color == WHITE else 6
        promo_rank = 7 if color == WHITE else 0

        # Single push.
        one = square(f, r + direction)
        if on_board(f, r + direction) and self.board.piece_at(one) is None:
            if r + direction == promo_rank:
                self._add_promotions(sq, one, moves)
            else:
                moves.append(Move(sq, one))
            # Double push.
            if r == start_rank:
                two = square(f, r + 2 * direction)
                if self.board.piece_at(two) is None:
                    moves.append(Move(sq, two, is_double_pawn_push=True))

        # Captures (including promotion captures).
        for df in (-1, 1):
            nf, nr = f + df, r + direction
            if not on_board(nf, nr):
                continue
            target = square(nf, nr)
            occupant = self.board.piece_at(target)
            if occupant is not None and color_of(occupant) != color:
                if nr == promo_rank:
                    self._add_promotions(sq, target, moves)
                else:
                    moves.append(Move(sq, target))
            # En passant capture (Art. 3.7.3).
            elif occupant is None and self.ep_square == target:
                moves.append(Move(sq, target, is_en_passant=True))

    @staticmethod
    def _add_promotions(frm, to, moves):
        for kind in PROMOTION_KINDS:
            moves.append(Move(frm, to, promotion=kind))

    def _castling_moves(self, color: str) -> List[Move]:
        """Generate legal castling moves for *color* (Art. 3.8.2)."""
        moves: List[Move] = []
        if self.is_in_check(color):
            return moves  # 3.8.2.2 (a): cannot castle out of check.

        enemy = opposite(color)
        if color == WHITE:
            king_from, rank = square(4, 0), 0
            k_right, q_right = "K", "Q"
        else:
            king_from, rank = square(4, 7), 7
            k_right, q_right = "k", "q"

        # King must actually be on its home square with the right present.
        king_piece = KING if color == WHITE else KING.lower()
        if self.board.piece_at(king_from) != king_piece:
            return moves

        # Kingside: squares f,g between king and h-rook must be empty; king
        # must not pass through or land on an attacked square.
        if k_right in self.castling:
            f_sq, g_sq = square(5, rank), square(6, rank)
            rook_sq = square(7, rank)
            rook_piece = ROOK if color == WHITE else ROOK.lower()
            if (
                self.board.piece_at(f_sq) is None
                and self.board.piece_at(g_sq) is None
                and self.board.piece_at(rook_sq) == rook_piece
                and not self.board.is_attacked(f_sq, enemy)
                and not self.board.is_attacked(g_sq, enemy)
            ):
                moves.append(Move(king_from, g_sq, is_castle_kingside=True))

        # Queenside: squares b,c,d must be empty; king crosses d and lands on c,
        # neither of which may be attacked (b may be attacked — only the rook
        # passes over it).
        if q_right in self.castling:
            d_sq, c_sq, b_sq = square(3, rank), square(2, rank), square(1, rank)
            rook_sq = square(0, rank)
            rook_piece = ROOK if color == WHITE else ROOK.lower()
            if (
                self.board.piece_at(d_sq) is None
                and self.board.piece_at(c_sq) is None
                and self.board.piece_at(b_sq) is None
                and self.board.piece_at(rook_sq) == rook_piece
                and not self.board.is_attacked(d_sq, enemy)
                and not self.board.is_attacked(c_sq, enemy)
            ):
                moves.append(Move(king_from, c_sq, is_castle_queenside=True))

        return moves

    def legal_moves(self) -> List[Move]:
        """All legal moves for the side to move (Art. 3.9 king safety)."""
        if self.is_over():
            return []
        color = self.side_to_move
        legal: List[Move] = []
        for move in self._pseudo_legal_moves(color):
            if self._leaves_king_safe(move, color):
                legal.append(move)
        legal.extend(self._castling_moves(color))
        return legal

    def _leaves_king_safe(self, move: Move, color: str) -> bool:
        """Apply *move* to a scratch board and check the mover's king (3.9)."""
        board = self.board.copy()
        self._apply_to_board(board, move, color)
        king_sq = board.king_square(color)
        if king_sq is None:
            return False
        return not board.is_attacked(king_sq, opposite(color))

    # ------------------------------------------------------------------
    # Move application
    # ------------------------------------------------------------------
    def _apply_to_board(self, board: Board, move: Move, color: str) -> None:
        """Mutate *board* by playing *move* (no state/clock bookkeeping)."""
        piece = board.piece_at(move.frm)
        board.set(move.frm, None)

        if move.is_en_passant:
            # Remove the pawn that is captured en passant (behind the target).
            captured_rank = rank_of(move.to) + (-1 if color == WHITE else 1)
            board.set(square(file_of(move.to), captured_rank), None)

        if move.promotion:
            promoted = move.promotion if color == WHITE else move.promotion.lower()
            board.set(move.to, promoted)
        else:
            board.set(move.to, piece)

        if move.is_castle_kingside:
            rank = rank_of(move.frm)
            board.set(square(7, rank), None)
            rook = ROOK if color == WHITE else ROOK.lower()
            board.set(square(5, rank), rook)
        elif move.is_castle_queenside:
            rank = rank_of(move.frm)
            board.set(square(0, rank), None)
            rook = ROOK if color == WHITE else ROOK.lower()
            board.set(square(3, rank), rook)

    def _find_legal_move(self, frm: int, to: int, promotion: Optional[str]) -> Move:
        promo = promotion.upper() if promotion else None
        matches = [
            m
            for m in self.legal_moves()
            if m.frm == frm and m.to == to and m.promotion == promo
        ]
        if not matches:
            raise IllegalMoveError(
                f"illegal move {square_name(frm)}{square_name(to)}"
                + (f"={promo}" if promo else "")
            )
        return matches[0]

    def push_uci(self, uci: str) -> Move:
        """Play a move given in UCI form (``e2e4``, ``e7e8q``, ``e1g1``)."""
        uci = uci.strip()
        from .constants import parse_square

        frm = parse_square(uci[0:2])
        to = parse_square(uci[2:4])
        promotion = uci[4].upper() if len(uci) > 4 else None
        return self.push(Move(frm, to, promotion=promotion))

    def push_san_like(self, frm: str, to: str, promotion: Optional[str] = None) -> Move:
        """Play a move given by from/to square names (test convenience)."""
        from .constants import parse_square

        promo = promotion.upper() if promotion else None
        return self.push(Move(parse_square(frm), parse_square(to), promotion=promo))

    def push(self, move: Move) -> Move:
        """Validate and play *move*, updating all game state and status."""
        # Game-over must be checked before move legality so that attempting to
        # move in a finished game reports GameOverError, not IllegalMoveError.
        if self.is_over():
            raise GameOverError(f"game is over ({self.result}, {self.termination})")

        # Confirm the move is legal (also normalises flags for castling/ep).
        legal = self._find_legal_move(move.frm, move.to, move.promotion)
        self._make(legal)
        self._update_status()
        return legal

    def _make(self, legal: Move) -> None:
        """Apply an already-validated legal move and update state (no status)."""
        color = self.side_to_move

        moving_piece = self.board.piece_at(legal.frm)
        is_pawn_move = kind_of(moving_piece) == "P"
        is_capture = self.board.piece_at(legal.to) is not None or legal.is_en_passant

        # Apply on the real board.
        self._apply_to_board(self.board, legal, color)

        # Castling-rights updates (Art. 3.8.2.1: rights lost when king or rook
        # move; also lost if a home rook is captured).
        self._update_castling_rights(legal, color, moving_piece)

        # En passant target for the *next* move (Art. 3.7.3.1).
        if legal.is_double_pawn_push:
            mid_rank = rank_of(legal.frm) + (1 if color == WHITE else -1)
            self.ep_square = square(file_of(legal.frm), mid_rank)
        else:
            self.ep_square = None

        # Move clocks (Art. 9.3: reset on pawn move or capture).
        if is_pawn_move or is_capture:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # Turn handling (Art. 1.3 / 2.3): alternate; fullmove++ after Black.
        if color == BLACK:
            self.fullmove_number += 1
        self.side_to_move = opposite(color)
        self._ply += 1

        # Any pending draw offer lapses once a move is made / accepted-or-not.
        self.pending_draw_offer = None

        self._record_position()

    def _update_castling_rights(self, move: Move, color: str, moving_piece: str) -> None:
        rights = set(self.castling)
        kind = kind_of(moving_piece)

        if kind == "K":
            if color == WHITE:
                rights.discard("K")
                rights.discard("Q")
            else:
                rights.discard("k")
                rights.discard("q")

        # Rook leaving a home square.
        corner_rights = {
            square(0, 0): "Q",
            square(7, 0): "K",
            square(0, 7): "q",
            square(7, 7): "k",
        }
        if move.frm in corner_rights:
            rights.discard(corner_rights[move.frm])
        # Rook captured on a home square (the destination of the move).
        if move.to in corner_rights:
            rights.discard(corner_rights[move.to])

        self.castling = "".join(c for c in "KQkq" if c in rights)

    # ------------------------------------------------------------------
    # Position keys / repetition
    # ------------------------------------------------------------------
    def _ep_capture_available(self) -> bool:
        """Whether an en passant capture is actually available right now.

        Art. 9.2.3.1: for the "same position" test, an en passant possibility
        only counts when a pawn could really make the capture.
        """
        if self.ep_square is None:
            return False
        color = self.side_to_move
        direction = 1 if color == WHITE else -1
        target_rank = rank_of(self.ep_square)
        pawn_rank = target_rank - direction
        pawn = "P" if color == WHITE else "p"
        f = file_of(self.ep_square)
        for df in (-1, 1):
            nf = f + df
            if on_board(nf, pawn_rank) and self.board.piece_at(square(nf, pawn_rank)) == pawn:
                # Ensure the capture is pseudo-legally possible (it is by
                # construction); king-safety is ignored here, matching the
                # "possible moves" comparison used by 9.2.3.
                return True
        return False

    def _position_key(self) -> str:
        """A key capturing everything Art. 9.2.3 considers part of a position."""
        active = "w" if self.side_to_move == WHITE else "b"
        castling = self.castling if self.castling else "-"
        ep = square_name(self.ep_square) if self._ep_capture_available() else "-"
        return f"{self.board.placement()} {active} {castling} {ep}"

    def _record_position(self) -> None:
        key = self._position_key()
        self._position_counts[key] = self._position_counts.get(key, 0) + 1

    def repetition_count(self) -> int:
        """How many times the current position has occurred."""
        return self._position_counts.get(self._position_key(), 0)

    # ------------------------------------------------------------------
    # Terminal-state detection
    # ------------------------------------------------------------------
    def _update_status(self) -> None:
        """Set :attr:`result`/:attr:`termination` after a move (Art. 5, 9.6).

        Ordering matters: checkmate is checked first so it takes precedence over
        the automatic 75-move / fivefold rules (Art. 9.6.2).
        """
        moves = self.legal_moves()
        in_check = self.is_in_check(self.side_to_move)

        if not moves:
            if in_check:
                # Side to move is checkmated; the side that just moved wins.
                self.termination = CHECKMATE
                self.result = RESULT_WHITE if self.side_to_move == BLACK else RESULT_BLACK
            else:
                self.termination = STALEMATE
                self.result = RESULT_DRAW
            return

        if self.is_dead_position():
            self.termination = DEAD_POSITION
            self.result = RESULT_DRAW
            return

        if self.repetition_count() >= 5:
            self.termination = FIVEFOLD
            self.result = RESULT_DRAW
            return

        if self.halfmove_clock >= 150:
            self.termination = SEVENTYFIVE_MOVE
            self.result = RESULT_DRAW
            return

        # Otherwise the game continues (claimable draws are handled separately).

    # ------------------------------------------------------------------
    # Dead position / insufficient material (Art. 5.2.2)
    # ------------------------------------------------------------------
    def _material(self) -> Tuple[List[Tuple[int, str]], List[Tuple[int, str]]]:
        white: List[Tuple[int, str]] = []
        black: List[Tuple[int, str]] = []
        for sq, piece in self.board.pieces():
            if color_of(piece) == WHITE:
                white.append((sq, kind_of(piece)))
            else:
                black.append((sq, kind_of(piece)))
        return white, black

    def is_dead_position(self) -> bool:
        """Recognised material combinations where neither side can ever mate.

        Covers K vs K, K+minor vs K, and same-coloured bishops only.  Broader
        blocked/fortress dead positions are undecidable in general and are not
        auto-detected (see the audit report).
        """
        white, black = self._material()
        non_king = [(sq, k) for group in (white, black) for (sq, k) in group if k != "K"]

        # Any pawn, rook or queen means a mate is possible.
        for _sq, k in non_king:
            if k in (QUEEN, ROOK, "P"):
                return False

        # Only kings and minor pieces (bishops/knights) remain.
        if len(non_king) == 0:
            return True  # K vs K
        if len(non_king) == 1:
            return True  # K + single minor vs K

        # More than one minor: only a draw if every remaining piece is a bishop
        # and all bishops sit on the same colour of square.
        if all(k == BISHOP for _sq, k in non_king):
            colors = {(file_of(sq) + rank_of(sq)) % 2 for sq, _k in non_king}
            if len(colors) == 1:
                return True

        return False

    # ------------------------------------------------------------------
    # Claimable draws (Art. 9.2 threefold, 9.3 fifty-move)
    # ------------------------------------------------------------------
    def can_claim_threefold(self) -> bool:
        """Current position has occurred at least three times (Art. 9.2.2)."""
        return not self.is_over() and self.repetition_count() >= 3

    def can_claim_fifty_move(self) -> bool:
        """At least 50 moves by each side without pawn move/capture (Art. 9.3)."""
        return not self.is_over() and self.halfmove_clock >= 100

    def claimable_draw_reasons(self) -> List[str]:
        reasons = []
        if self.can_claim_threefold():
            reasons.append(THREEFOLD)
        if self.can_claim_fifty_move():
            reasons.append(FIFTY_MOVE)
        return reasons

    def would_enable_draw_claim(self, move: Move) -> List[str]:
        """Which claimable draws *move* would create (Art. 9.2.1 / 9.3.1).

        Models the "I intend to play this move, which will complete the
        repetition / 50-move count" form of a claim, without mutating state.
        """
        legal = self._find_legal_move(move.frm, move.to, move.promotion)
        probe = self.copy()
        # Play on the probe (bypassing status side effects is unnecessary; we
        # only read counters).
        probe.push(legal)
        reasons = []
        if probe.repetition_count() >= 3:
            reasons.append(THREEFOLD)
        if probe.halfmove_clock >= 100:
            reasons.append(FIFTY_MOVE)
        return reasons

    def claim_draw(self, reason: str) -> bool:
        """Claim a draw under Art. 9.2 or 9.3.

        Returns ``True`` and ends the game if the claim is correct; otherwise
        returns ``False`` and the game continues (Art. 9.5.2/9.5.3).
        """
        if self.is_over():
            raise GameOverError("game is already over")
        if reason == THREEFOLD and self.can_claim_threefold():
            self.termination = THREEFOLD
            self.result = RESULT_DRAW
            return True
        if reason == FIFTY_MOVE and self.can_claim_fifty_move():
            self.termination = FIFTY_MOVE
            self.result = RESULT_DRAW
            return True
        return False

    # ------------------------------------------------------------------
    # Draw offers (Art. 9.1 / 5.2.3) and resignation (Art. 5.1.2)
    # ------------------------------------------------------------------
    def offer_draw(self, color: str) -> None:
        """Record a draw offer from *color* (Art. 9.1).

        Either player may offer while the game is in progress.  The exact
        clock-timing of an offer ("after moving, before pressing the clock",
        Art. 9.1.2) is a clock-management concern outside a pure rules engine
        and is not enforced here.  The offer stands until the opponent accepts
        or rejects it, or a move is made (Art. 9.1.2).
        """
        if self.is_over():
            raise GameOverError("game is already over")
        if color not in (WHITE, BLACK):
            raise ValueError("colour must be WHITE or BLACK")
        self.pending_draw_offer = color

    def accept_draw(self) -> None:
        """Accept a pending draw offer (Art. 5.2.3 / 9.1).

        Acceptance concludes the game as a draw by agreement, provided both
        players have made at least one move (Art. 5.2.3).
        """
        if self.is_over():
            raise GameOverError("game is already over")
        if self.pending_draw_offer is None:
            raise ValueError("no draw has been offered")
        if self._ply < 2:
            # 5.2.3: both players must have made at least one move.
            raise ValueError("both players must have made at least one move")
        self.termination = AGREEMENT
        self.result = RESULT_DRAW
        self.pending_draw_offer = None

    def decline_draw(self) -> None:
        """Decline a pending draw offer (Art. 9.1.2)."""
        self.pending_draw_offer = None

    def _can_possibly_mate(self, attacker: str) -> bool:
        """Whether *attacker* could conceivably checkmate the other king.

        Used for Art. 5.1.2 (resignation is a draw if the opponent cannot mate
        by any series of legal moves).  A lone king can never deliver mate; a
        king with a single minor cannot mate a lone king.  Richer helpmate-only
        positions are not specially analysed (documented limitation).
        """
        white, black = self._material()
        mine = white if attacker == WHITE else black
        theirs = black if attacker == WHITE else white
        my_non_king = [k for _sq, k in mine if k != "K"]
        their_non_king = [k for _sq, k in theirs if k != "K"]

        if not my_non_king:
            return False  # lone king can never checkmate anything
        # K + single minor vs lone king: mate impossible.
        if (
            len(my_non_king) == 1
            and my_non_king[0] in (BISHOP, KNIGHT)
            and not their_non_king
        ):
            return False
        return True

    def resign(self, color: str) -> None:
        """*color* resigns (Art. 5.1.2).

        The opponent wins, unless the opponent cannot possibly mate, in which
        case the game is drawn.
        """
        if self.is_over():
            raise GameOverError("game is already over")
        opponent = opposite(color)
        self.termination = RESIGNATION
        if self._can_possibly_mate(opponent):
            self.result = RESULT_WHITE if opponent == WHITE else RESULT_BLACK
        else:
            self.result = RESULT_DRAW

    # ------------------------------------------------------------------
    # High-level status summary
    # ------------------------------------------------------------------
    def status(self) -> Dict[str, object]:
        """A structured summary distinguishing the four FIDE categories.

        ``category`` is one of:

        * ``"automatic_draw"`` / ``"decisive"`` – the game has already ended;
        * ``"claimable_draw"`` – the game continues but a player may claim a
          draw (Art. 9.2/9.3);
        * ``"ongoing"`` – the game continues with no claim available.
        """
        if self.is_over():
            if self.result == RESULT_DRAW:
                category = "decisive_draw" if self.termination in (
                    AGREEMENT,
                    RESIGNATION,
                    THREEFOLD,
                    FIFTY_MOVE,
                ) else "automatic_draw"
            else:
                category = "decisive"
            return {
                "over": True,
                "result": self.result,
                "termination": self.termination,
                "category": category,
            }

        claimable = self.claimable_draw_reasons()
        return {
            "over": False,
            "result": RESULT_ONGOING,
            "termination": None,
            "category": "claimable_draw" if claimable else "ongoing",
            "claimable": claimable,
            "in_check": self.is_in_check(),
        }

    def copy(self) -> "Game":
        clone = Game.__new__(Game)
        clone.board = self.board.copy()
        clone.side_to_move = self.side_to_move
        clone.castling = self.castling
        clone.ep_square = self.ep_square
        clone.halfmove_clock = self.halfmove_clock
        clone.fullmove_number = self.fullmove_number
        clone.result = self.result
        clone.termination = self.termination
        clone.pending_draw_offer = self.pending_draw_offer
        clone._position_counts = dict(self._position_counts)
        clone._ply = self._ply
        return clone

    def __repr__(self) -> str:  # pragma: no cover
        return f"Game({self.fen()!r})"
