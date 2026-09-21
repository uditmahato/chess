"""Rules 1, 2, 3, 4, 25: board/initial position, piece movement, legal moves,
captures and correct turn handling."""

import unittest

from chess import STARTING_FEN, Board, Game, IllegalMoveError
from chess.constants import WHITE, BLACK

from .helpers import moves_from, uci_set


class InitialPositionTest(unittest.TestCase):
    def test_starting_fen(self):
        self.assertEqual(Game().fen(), STARTING_FEN)

    def test_starting_material_and_placement(self):
        b = Board.from_placement(STARTING_FEN.split()[0])
        # 32 pieces total.
        self.assertEqual(sum(1 for _ in b.pieces()), 32)
        # White back rank a1..h1.
        self.assertEqual(
            [b.piece_at(i) for i in range(0, 8)],
            list("RNBQKBNR"),
        )
        # Black back rank a8..h8.
        self.assertEqual(
            [b.piece_at(i) for i in range(56, 64)],
            list("rnbqkbnr"),
        )

    def test_white_moves_first(self):
        self.assertEqual(Game().side_to_move, WHITE)

    def test_twenty_opening_moves(self):
        self.assertEqual(len(Game().legal_moves()), 20)


class PieceMovementTest(unittest.TestCase):
    def test_knight_from_centre(self):
        # A lone black rook keeps this from being a K+N-vs-K dead position.
        g = Game("r3k3/8/8/8/4N3/8/8/4K3 w - - 0 1")
        self.assertEqual(
            moves_from(g, "e4"),
            {"e4d6", "e4f6", "e4g5", "e4g3", "e4f2", "e4d2", "e4c3", "e4c5"},
        )

    def test_bishop_is_blocked_by_own_pieces(self):
        g = Game("4k3/8/8/8/8/2P5/3B4/4K3 w - - 0 1")
        # Bishop d2: blocked toward c3 by own pawn; other diagonals open.
        got = moves_from(g, "d2")
        self.assertNotIn("d2c3", got)
        self.assertIn("d2e3", got)
        self.assertIn("d2c1", got)

    def test_rook_slides_and_stops_at_capture(self):
        # Enemy pawn on a5; own king on e1 blocks the rank at d1.
        g = Game("4k3/8/8/p7/8/8/8/R3K3 w Q - 0 1")
        got = moves_from(g, "a1")
        self.assertIn("a1a5", got)     # captures the pawn
        self.assertNotIn("a1a6", got)  # cannot slide past the captured pawn
        self.assertIn("a1d1", got)     # along the rank up to the king's neighbour
        self.assertNotIn("a1f1", got)  # own king blocks at e1

    def test_pawn_double_push_only_from_start(self):
        g = Game()
        self.assertIn("e2e4", moves_from(g, "e2"))
        g.push_uci("e2e4")
        g.push_uci("a7a6")
        # Pawn now on e4 cannot double-push.
        self.assertEqual(moves_from(g, "e4"), {"e4e5"})

    def test_queen_combines_rook_and_bishop(self):
        g = Game("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1")
        self.assertEqual(len(moves_from(g, "d4")), 27)


class CaptureTest(unittest.TestCase):
    def test_capture_removes_enemy_piece(self):
        # Black pawn on d5, White knight on c3 which attacks d5.
        g = Game("4k3/8/8/3p4/8/2N5/8/4K3 w - - 0 1")
        self.assertIn("c3d5", uci_set(g))
        g.push_uci("c3d5")  # Nc3xd5 captures the pawn
        self.assertEqual(g.board.piece_at(35), "N")  # d5 index = 4*8+3 = 35
        self.assertIsNone(g.board.piece_at(18))  # c3 index = 2*8+2 = 18, now empty

    def test_cannot_capture_own_piece(self):
        g = Game("4k3/8/8/8/8/2P5/3B4/4K3 w - - 0 1")
        self.assertNotIn("d2c3", uci_set(g))


class TurnHandlingTest(unittest.TestCase):
    def test_cannot_move_opponent_piece(self):
        g = Game()
        with self.assertRaises(IllegalMoveError):
            g.push_uci("e7e5")  # black pawn, but white to move

    def test_alternation_and_fullmove_counter(self):
        g = Game()
        self.assertEqual(g.fullmove_number, 1)
        g.push_uci("e2e4")
        self.assertEqual(g.side_to_move, BLACK)
        self.assertEqual(g.fullmove_number, 1)  # unchanged after White's move
        g.push_uci("e7e5")
        self.assertEqual(g.side_to_move, WHITE)
        self.assertEqual(g.fullmove_number, 2)  # incremented after Black's move

    def test_halfmove_clock_resets_and_increments(self):
        g = Game()
        g.push_uci("g1f3")  # knight move -> clock increments
        self.assertEqual(g.halfmove_clock, 1)
        g.push_uci("g8f6")
        self.assertEqual(g.halfmove_clock, 2)
        g.push_uci("e2e4")  # pawn move -> resets
        self.assertEqual(g.halfmove_clock, 0)

    def test_cannot_move_after_game_over(self):
        # Fool's mate.
        g = Game()
        for u in ("f2f3", "e7e5", "g2g4", "d8h4"):
            g.push_uci(u)
        self.assertTrue(g.is_over())
        from chess import GameOverError

        with self.assertRaises(GameOverError):
            g.push_uci("a2a3")


if __name__ == "__main__":
    unittest.main()
