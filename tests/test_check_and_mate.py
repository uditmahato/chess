"""Rules 5, 6, 7, 13, 14, 15, 16: check, checkmate, stalemate, king safety,
pinned pieces, double check and discovered check."""

import unittest

from chess import Game, RESULT_BLACK, RESULT_WHITE, RESULT_DRAW, CHECKMATE, STALEMATE
from chess.constants import parse_square

from .helpers import moves_from


class CheckTest(unittest.TestCase):
    def test_in_check_detected(self):
        g = Game("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1")  # rook e2 checks Ke1
        self.assertTrue(g.is_in_check())
        self.assertEqual(g.checking_pieces(), [parse_square("e2")])

    def test_not_in_check(self):
        self.assertFalse(Game().is_in_check())

    def test_must_respond_to_check(self):
        # White in check from the rook; every legal move must leave the king safe.
        g = Game("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1")
        for mv in g.legal_moves():
            probe = g.copy()
            probe._make(mv)
            self.assertFalse(probe.is_in_check(g.side_to_move))


class CheckmateTest(unittest.TestCase):
    def test_fools_mate(self):
        g = Game()
        for u in ("f2f3", "e7e5", "g2g4", "d8h4"):
            g.push_uci(u)
        self.assertTrue(g.is_over())
        self.assertEqual(g.termination, CHECKMATE)
        self.assertEqual(g.result, RESULT_BLACK)
        self.assertTrue(g.is_in_check())          # side to move (White) is mated
        self.assertEqual(g.legal_moves(), [])

    def test_back_rank_mate_loaded(self):
        # Black is checkmated: Ra8#, king boxed in by its own pawns.
        g = Game("R5k1/5ppp/8/8/8/8/8/6K1 b - - 0 1")
        self.assertTrue(g.is_over())
        self.assertEqual(g.termination, CHECKMATE)
        self.assertEqual(g.result, RESULT_WHITE)


class StalemateTest(unittest.TestCase):
    def test_stalemate_is_draw(self):
        # Black to move, king on f8 has no moves and is not in check.
        g = Game("5k2/5P2/5K2/8/8/8/8/8 b - - 0 1")
        self.assertTrue(g.is_over())
        self.assertEqual(g.termination, STALEMATE)
        self.assertEqual(g.result, RESULT_DRAW)
        self.assertFalse(g.is_in_check())


class PinTest(unittest.TestCase):
    def test_absolutely_pinned_knight_cannot_move(self):
        # White knight e2 is pinned to Ke1 by the black rook on e8.
        g = Game("4r3/8/8/8/8/8/4N3/4K3 w - - 0 1")
        self.assertFalse(g.is_in_check())          # knight blocks the check
        self.assertEqual(moves_from(g, "e2"), set())  # knight is frozen
        # The king may step off the file.
        self.assertTrue(moves_from(g, "e1"))

    def test_pinned_piece_may_capture_the_pinner(self):
        # White bishop f2 is pinned to Kg1 by the black bishop on c5
        # (diagonal c5-d4-e3-f2-g1).  It may only move along that diagonal.
        # (A lone black rook keeps this from being a dead same-coloured-bishop
        # position, so the game is still in progress.)
        g = Game("r3k3/8/8/2b5/8/8/5B2/6K1 w - - 0 1")
        self.assertFalse(g.is_in_check())
        got = moves_from(g, "f2")
        self.assertIn("f2c5", got)     # capture the pinner
        self.assertIn("f2e3", got)     # stay on the pin line
        self.assertIn("f2d4", got)     # stay on the pin line
        self.assertNotIn("f2g3", got)  # leaving the diagonal exposes the king


class DiscoveredAndDoubleCheckTest(unittest.TestCase):
    def test_discovered_check_single_checker(self):
        # Moving the knight off the e-file discovers the rook's check on Ke8.
        g = Game("4k3/8/8/8/4N3/8/8/4R1K1 w - - 0 1")
        g.push_uci("e4c3")  # knight steps aside (does not itself check)
        self.assertTrue(g.is_in_check("b"))
        self.assertEqual(g.checking_pieces("b"), [parse_square("e1")])  # the rook

    def test_double_check_only_king_may_move(self):
        # Black king e8 checked by both Re1 (file) and Bh5 (diagonal).
        g = Game("r3k3/8/8/7B/8/8/8/4R1K1 b - - 0 1")
        self.assertEqual(len(g.checking_pieces("b")), 2)
        king_sq = parse_square("e8")
        self.assertTrue(g.legal_moves())  # king can escape
        for mv in g.legal_moves():
            self.assertEqual(mv.frm, king_sq)  # only king moves are legal


if __name__ == "__main__":
    unittest.main()
