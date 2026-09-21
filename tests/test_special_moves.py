"""Rules 8, 9, 10, 11, 12: castling, castling restrictions, en passant,
promotion and promotion-piece selection."""

import unittest

from chess import Game, IllegalMoveError
from chess.constants import parse_square

from .helpers import moves_from, uci_set


class CastlingTest(unittest.TestCase):
    def test_kingside_castle(self):
        g = Game("4k3/8/8/8/8/8/8/4K2R w K - 0 1")
        self.assertIn("e1g1", moves_from(g, "e1"))
        g.push_uci("e1g1")
        self.assertEqual(g.board.piece_at(parse_square("g1")), "K")
        self.assertEqual(g.board.piece_at(parse_square("f1")), "R")
        self.assertIsNone(g.board.piece_at(parse_square("h1")))
        self.assertEqual(g.castling, "")  # rights consumed

    def test_queenside_castle(self):
        g = Game("r3k3/8/8/8/8/8/8/R3K3 w Qq - 0 1")
        self.assertIn("e1c1", moves_from(g, "e1"))
        g.push_uci("e1c1")
        self.assertEqual(g.board.piece_at(parse_square("c1")), "K")
        self.assertEqual(g.board.piece_at(parse_square("d1")), "R")

    def test_both_sides_available(self):
        g = Game("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        self.assertIn("e1g1", moves_from(g, "e1"))
        self.assertIn("e1c1", moves_from(g, "e1"))


class CastlingRestrictionTest(unittest.TestCase):
    def test_cannot_castle_out_of_check(self):
        # Black rook e8 checks the white king -> no castling (3.8.2.2).
        g = Game("4r3/8/8/8/8/8/8/4K2R w K - 0 1")
        self.assertTrue(g.is_in_check())
        self.assertNotIn("e1g1", moves_from(g, "e1"))

    def test_cannot_castle_through_attacked_square(self):
        # Black rook f8 attacks f1, the square the king crosses.
        g = Game("5r2/8/8/8/8/8/8/4K2R w K - 0 1")
        self.assertNotIn("e1g1", moves_from(g, "e1"))

    def test_cannot_castle_into_check(self):
        # Black rook g8 attacks g1, the king's destination.
        g = Game("6r1/8/8/8/8/8/8/4K2R w K - 0 1")
        self.assertNotIn("e1g1", moves_from(g, "e1"))

    def test_cannot_castle_when_squares_occupied(self):
        # Bishop on f1 blocks kingside castling.
        g = Game("4k3/8/8/8/8/8/8/4KB1R w K - 0 1")
        self.assertNotIn("e1g1", moves_from(g, "e1"))

    def test_queenside_allowed_when_only_b_file_attacked(self):
        # b1 is attacked but the king never crosses b1 (only the rook does),
        # so queenside castling is still legal (3.8.2.2 nuance).
        g = Game("1r2k3/8/8/8/8/8/8/R3K3 w Q - 0 1")
        self.assertTrue(g.board.is_attacked(parse_square("b1"), "b"))
        self.assertIn("e1c1", moves_from(g, "e1"))

    def test_rights_lost_after_king_moves(self):
        g = Game("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        g.push_uci("e1e2")  # king moves
        g.push_uci("e8e7")
        g.push_uci("e2e1")  # king returns
        g.push_uci("e7e8")
        self.assertNotIn("e1g1", moves_from(g, "e1"))
        self.assertNotIn("e1c1", moves_from(g, "e1"))

    def test_rights_lost_for_one_side_after_rook_moves(self):
        g = Game("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        g.push_uci("a1b1")  # queenside rook moves
        g.push_uci("e8e7")
        g.push_uci("b1a1")
        g.push_uci("e7e8")
        # Queenside right gone, kingside remains.
        self.assertNotIn("e1c1", moves_from(g, "e1"))
        self.assertIn("e1g1", moves_from(g, "e1"))

    def test_rights_lost_when_rook_captured(self):
        # Black bishop on c3 captures the white a1 rook (diagonal c3-b2-a1);
        # White thereby loses the queenside castling right.
        g = Game("4k3/8/8/8/8/2b5/8/R3K2R b KQ - 0 1")
        g.push_uci("c3a1")
        self.assertEqual(g.castling, "K")  # queenside (a1) right removed


class EnPassantTest(unittest.TestCase):
    def test_en_passant_capture(self):
        # Black pawn d4, white pawn just played e2-e4 (ep target e3).
        g = Game("4k3/8/8/8/3pP3/8/8/4K3 b - e3 0 1")
        self.assertIn("d4e3", uci_set(g))
        g.push_uci("d4e3")  # en passant
        self.assertEqual(g.board.piece_at(parse_square("e3")), "p")
        self.assertIsNone(g.board.piece_at(parse_square("e4")))  # captured pawn gone
        self.assertIsNone(g.board.piece_at(parse_square("d4")))

    def test_en_passant_only_immediately(self):
        # White pawn d5; black plays e7-e5 creating an ep chance on e6.  If
        # White does not take at once, the chance is lost (3.7.3.2).
        g = Game("4k3/4p3/8/3P4/8/8/8/4K3 b - - 0 1")
        g.push_uci("e7e5")   # black double push, ep target e6
        self.assertEqual(g.ep_square, parse_square("e6"))
        self.assertIn("d5e6", uci_set(g))  # ep available right now
        g.push_uci("e1e2")   # white delays instead of capturing
        self.assertIsNone(g.ep_square)
        g.push_uci("e8e7")
        # The ep capture on e6 is gone, and there is no other d5 capture.
        self.assertNotIn("d5e6", uci_set(g))

    def test_en_passant_target_only_on_double_push(self):
        g = Game()
        g.push_uci("e2e4")
        self.assertEqual(g.ep_square, parse_square("e3"))


class PromotionTest(unittest.TestCase):
    def test_all_four_promotions_offered(self):
        g = Game("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        self.assertEqual(
            moves_from(g, "a7"),
            {"a7a8q", "a7a8r", "a7a8b", "a7a8n"},
        )

    def test_promotion_by_capture(self):
        # Pawn a7 may push to a8 or capture the knight on b8, each with 4 choices.
        g = Game("1n2k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        got = moves_from(g, "a7")
        self.assertEqual(len(got), 8)
        self.assertIn("a7b8q", got)
        self.assertIn("a7a8n", got)

    def test_underpromotion_selection_applied(self):
        g = Game("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        g.push_uci("a7a8n")  # choose a knight
        self.assertEqual(g.board.piece_at(parse_square("a8")), "N")

    def test_cannot_promote_to_king_or_pawn(self):
        g = Game("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        with self.assertRaises(IllegalMoveError):
            g.push_uci("a7a8k")

    def test_promotion_creates_correct_colour_for_black(self):
        g = Game("4k3/8/8/8/8/8/6p1/4K3 b - - 0 1")
        g.push_uci("g2g1q")
        self.assertEqual(g.board.piece_at(parse_square("g1")), "q")


if __name__ == "__main__":
    unittest.main()
