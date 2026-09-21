"""Rules 17-24: repetition (threefold/fivefold), fifty/seventy-five-move,
dead position, draw by agreement, resignation and game termination, plus the
four-way distinction between automatic draws, claimable draws, draw offers and
the game continuing."""

import unittest

from chess import (
    Game,
    GameOverError,
    RESULT_BLACK,
    RESULT_DRAW,
    RESULT_WHITE,
    RESULT_ONGOING,
    AGREEMENT,
    DEAD_POSITION,
    FIFTY_MOVE,
    FIVEFOLD,
    RESIGNATION,
    SEVENTYFIVE_MOVE,
    THREEFOLD,
)
from chess.constants import parse_square


KNIGHT_SHUFFLE = ("g1f3", "g8f6", "f3g1", "f6g8")


class DeadPositionTest(unittest.TestCase):
    def test_king_vs_king(self):
        g = Game("8/8/8/4k3/8/4K3/8/8 w - - 0 1")
        self.assertTrue(g.is_dead_position())
        self.assertTrue(g.is_over())
        self.assertEqual(g.termination, DEAD_POSITION)
        self.assertEqual(g.result, RESULT_DRAW)

    def test_king_and_bishop_vs_king(self):
        self.assertTrue(Game("8/8/8/4k3/8/4K3/5B2/8 w - - 0 1").is_dead_position())

    def test_king_and_knight_vs_king(self):
        self.assertTrue(Game("8/8/8/4k3/8/4K3/5N2/8 w - - 0 1").is_dead_position())

    def test_same_coloured_bishops_are_dead(self):
        # Black Bb4 and White Bf2 are both on dark squares -> neither can mate.
        g = Game("8/8/4k3/8/1b6/8/4KB2/8 w - - 0 1")
        self.assertTrue(g.is_dead_position())

    def test_opposite_coloured_bishops_not_dead(self):
        # Black Bc4 (light) vs White Bf2 (dark) -> a helpmate exists.
        g = Game("8/8/4k3/8/2b5/8/4KB2/8 w - - 0 1")
        self.assertFalse(g.is_dead_position())

    def test_king_and_rook_not_dead(self):
        self.assertFalse(Game("8/8/8/4k3/8/4K3/5R2/8 w - - 0 1").is_dead_position())

    def test_pawn_present_not_dead(self):
        self.assertFalse(Game("8/8/8/4k3/8/4K3/5P2/8 w - - 0 1").is_dead_position())

    def test_capture_into_dead_position_ends_game(self):
        # K+N vs K+N is not dead, but capturing a knight leaves K+N vs K, which
        # is a dead position and ends the game automatically (Art. 5.2.2).
        g = Game("4k3/8/8/3n4/8/2N5/8/4K3 w - - 0 1")
        self.assertFalse(g.is_over())          # two knights: not dead
        g.push_uci("c3d5")                     # Nc3xd5 removes the black knight
        self.assertTrue(g.is_over())
        self.assertEqual(g.termination, DEAD_POSITION)
        self.assertEqual(g.result, RESULT_DRAW)


class RepetitionTest(unittest.TestCase):
    def test_threefold_is_claimable_not_automatic(self):
        g = Game()
        # Two knight-shuffle cycles return the start position a 3rd time.
        for u in KNIGHT_SHUFFLE * 2:
            g.push_uci(u)
        self.assertFalse(g.is_over())            # NOT automatic
        self.assertEqual(g.repetition_count(), 3)
        self.assertTrue(g.can_claim_threefold())
        self.assertIn(THREEFOLD, g.status()["claimable"])
        # A player elects to claim.
        self.assertTrue(g.claim_draw(THREEFOLD))
        self.assertTrue(g.is_over())
        self.assertEqual(g.termination, THREEFOLD)
        self.assertEqual(g.result, RESULT_DRAW)

    def test_game_continues_if_threefold_not_claimed(self):
        g = Game()
        for u in KNIGHT_SHUFFLE * 2:
            g.push_uci(u)
        self.assertTrue(g.can_claim_threefold())
        # Nobody claims; play continues legally.
        g.push_uci("e2e4")
        self.assertFalse(g.is_over())

    def test_fivefold_is_automatic(self):
        g = Game()
        moves = KNIGHT_SHUFFLE * 4  # four cycles -> start position 5 times
        for u in moves[:-1]:
            g.push_uci(u)
        self.assertFalse(g.is_over())            # only 4 occurrences so far
        g.push_uci(moves[-1])                     # the move that makes it 5
        self.assertTrue(g.is_over())
        self.assertEqual(g.termination, FIVEFOLD)
        self.assertEqual(g.result, RESULT_DRAW)

    def test_would_enable_claim_before_playing(self):
        g = Game()
        for u in KNIGHT_SHUFFLE + KNIGHT_SHUFFLE[:3]:  # one short of 3rd time
            g.push_uci(u)
        # Announcing the completing move enables the claim (Art. 9.2.1).
        from chess import Move

        completing = [m for m in g.legal_moves() if m.uci() == "f6g8"][0]
        self.assertIn(THREEFOLD, g.would_enable_draw_claim(completing))


class RepetitionPositionKeyTest(unittest.TestCase):
    def test_en_passant_right_distinguishes_positions(self):
        # A double push that CAN be answered by en passant makes the position
        # distinct (Art. 9.2.3.1): the ep square is part of the key only when a
        # capture is actually available.
        # Black pawn on d4 sits next to where White's pawn will land.
        g = Game("4k3/8/8/8/3p4/8/4P3/4K3 w - - 0 1")
        g.push_uci("e2e4")           # ep target e3, black d4 pawn can take
        key_with_ep = g._position_key()
        self.assertTrue(g._ep_capture_available())
        self.assertTrue(key_with_ep.endswith("e3"))

    def test_no_ep_component_when_capture_impossible(self):
        # Same double push but no adjacent enemy pawn: ep is not part of the key.
        g = Game("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
        g.push_uci("e2e4")
        self.assertFalse(g._ep_capture_available())
        self.assertTrue(g._position_key().endswith("-"))

    def test_castling_rights_distinguish_positions(self):
        g = Game("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        key_before = g._position_key()
        # Move a rook out and back for both sides; castling rights are gone,
        # so even though the piece placement matches, the key differs.
        for u in ("a1b1", "a8b8", "b1a1", "b8a8"):
            g.push_uci(u)
        self.assertEqual(g.board.placement(), key_before.split()[0])
        self.assertNotEqual(g._position_key(), key_before)
        self.assertEqual(g.repetition_count(), 1)  # not treated as a repeat


class MoveCountRuleTest(unittest.TestCase):
    def test_fifty_move_is_claimable(self):
        # Halfmove clock at 100 = 50 moves by each side.
        g = Game("4k3/8/8/8/8/8/8/R3K3 w - - 100 80")
        self.assertFalse(g.is_over())            # NOT automatic
        self.assertTrue(g.can_claim_fifty_move())
        self.assertIn(FIFTY_MOVE, g.status()["claimable"])
        self.assertTrue(g.claim_draw(FIFTY_MOVE))
        self.assertEqual(g.termination, FIFTY_MOVE)
        self.assertEqual(g.result, RESULT_DRAW)

    def test_fifty_move_claim_rejected_when_not_reached(self):
        g = Game("4k3/8/8/8/8/8/8/R3K3 w - - 98 80")
        self.assertFalse(g.can_claim_fifty_move())
        self.assertFalse(g.claim_draw(FIFTY_MOVE))  # incorrect claim -> continues
        self.assertFalse(g.is_over())

    def test_seventyfive_move_is_automatic(self):
        # Clock at 149; a non-pawn, non-capturing move makes it 150.
        g = Game("4k3/8/8/8/8/8/8/R3K3 w - - 149 90")
        g.push_uci("a1a2")
        self.assertTrue(g.is_over())
        self.assertEqual(g.termination, SEVENTYFIVE_MOVE)
        self.assertEqual(g.result, RESULT_DRAW)

    def test_checkmate_takes_precedence_over_seventyfive(self):
        # The 75th move also delivers checkmate: mate wins (Art. 9.6.2).
        g = Game("6k1/5ppp/8/8/8/8/8/R6K w - - 149 90")
        g.push_uci("a1a8")  # Ra8# and the clock would reach 150
        self.assertTrue(g.is_over())
        self.assertEqual(g.termination, "checkmate")
        self.assertEqual(g.result, RESULT_WHITE)


class DrawOfferTest(unittest.TestCase):
    def test_offer_and_accept(self):
        g = Game()
        g.push_uci("e2e4")
        g.push_uci("e7e5")   # both have moved
        g.offer_draw("w")    # white to move offers
        g.accept_draw()
        self.assertTrue(g.is_over())
        self.assertEqual(g.termination, AGREEMENT)
        self.assertEqual(g.result, RESULT_DRAW)

    def test_offer_declined_game_continues(self):
        g = Game()
        g.push_uci("e2e4")
        g.push_uci("e7e5")
        g.offer_draw("w")
        g.decline_draw()
        self.assertIsNone(g.pending_draw_offer)
        self.assertFalse(g.is_over())

    def test_cannot_agree_before_each_side_moved(self):
        g = Game()
        g.offer_draw("w")
        with self.assertRaises(ValueError):
            g.accept_draw()  # 5.2.3: both must have made at least one move

    def test_either_player_may_offer(self):
        # An offer may come from either side while the game is live.
        g = Game()
        g.push_uci("e2e4")
        g.push_uci("e7e5")  # both players have now moved
        g.offer_draw("b")   # black (who just moved) offers; white will accept
        g.accept_draw()
        self.assertEqual(g.termination, AGREEMENT)
        self.assertEqual(g.result, RESULT_DRAW)

    def test_offer_lapses_after_a_move(self):
        g = Game()
        g.push_uci("e2e4")
        g.push_uci("e7e5")
        g.offer_draw("w")
        g.push_uci("g1f3")   # white moves instead of the offer being accepted
        self.assertIsNone(g.pending_draw_offer)


class ResignationTest(unittest.TestCase):
    def test_resignation_awards_opponent(self):
        g = Game()
        g.resign("w")
        self.assertTrue(g.is_over())
        self.assertEqual(g.termination, RESIGNATION)
        self.assertEqual(g.result, RESULT_BLACK)

    def test_resignation_is_draw_if_opponent_cannot_mate(self):
        # Black has K+Q, White has only a lone king.  If BLACK resigns, White
        # cannot possibly mate -> the game is a draw (Art. 5.1.2).
        g = Game("4k3/q7/8/8/8/8/8/4K3 b - - 0 1")
        g.resign("b")
        self.assertEqual(g.termination, RESIGNATION)
        self.assertEqual(g.result, RESULT_DRAW)

    def test_resignation_wins_when_opponent_can_mate(self):
        # Same material, but WHITE resigns: Black (K+Q) can mate -> Black wins.
        g = Game("4k3/q7/8/8/8/8/8/4K3 b - - 0 1")
        g.resign("w")
        self.assertEqual(g.result, RESULT_BLACK)


class StatusCategoryTest(unittest.TestCase):
    def test_ongoing(self):
        s = Game().status()
        self.assertEqual(s["category"], "ongoing")
        self.assertEqual(s["result"], RESULT_ONGOING)

    def test_claimable_draw_category(self):
        g = Game()
        for u in KNIGHT_SHUFFLE * 2:
            g.push_uci(u)
        self.assertEqual(g.status()["category"], "claimable_draw")

    def test_automatic_draw_category(self):
        g = Game("5k2/5P2/5K2/8/8/8/8/8 b - - 0 1")  # stalemate
        self.assertEqual(g.status()["category"], "automatic_draw")

    def test_decisive_category(self):
        g = Game()
        for u in ("f2f3", "e7e5", "g2g4", "d8h4"):  # fool's mate
            g.push_uci(u)
        self.assertEqual(g.status()["category"], "decisive")

    def test_game_over_blocks_further_moves_and_claims(self):
        g = Game()
        g.resign("w")
        with self.assertRaises(GameOverError):
            g.push_uci("e2e4")
        with self.assertRaises(GameOverError):
            g.claim_draw(THREEFOLD)


if __name__ == "__main__":
    unittest.main()
