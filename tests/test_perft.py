"""Perft (move-generation) validation.

Perft counts the number of leaf nodes in the move tree to a given depth.  It is
the gold-standard correctness check for a move generator: it exercises normal
moves, captures, castling, en passant, promotions, pins, check evasion and
turn handling simultaneously.  The reference node counts are the widely
published values for these standard positions.

Deep plies are gated behind CHESS_SLOW_PERFT=1 to keep the default suite fast.
"""

import os
import unittest

from .helpers import Game


def perft(game: Game, depth: int) -> int:
    if depth == 0:
        return 1
    if depth == 1:
        return len(game.legal_moves())
    total = 0
    for mv in game.legal_moves():
        child = game.copy()
        child._make(mv)
        total += perft(child, depth - 1)
    return total


SLOW = os.environ.get("CHESS_SLOW_PERFT") == "1"


class PerftTest(unittest.TestCase):
    START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
    POS3 = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"
    POS4 = "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1"
    POS5 = "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8"

    def test_start_shallow(self):
        self.assertEqual(perft(Game(self.START), 1), 20)
        self.assertEqual(perft(Game(self.START), 2), 400)
        self.assertEqual(perft(Game(self.START), 3), 8902)

    def test_kiwipete_shallow(self):
        # Rich in castling, en passant and promotions.
        self.assertEqual(perft(Game(self.KIWIPETE), 1), 48)
        self.assertEqual(perft(Game(self.KIWIPETE), 2), 2039)

    def test_pos3_shallow(self):
        self.assertEqual(perft(Game(self.POS3), 1), 14)
        self.assertEqual(perft(Game(self.POS3), 2), 191)
        self.assertEqual(perft(Game(self.POS3), 3), 2812)

    def test_pos4_shallow(self):
        # Promotions and pins near the edge; the FEN is a mirrored castling case.
        self.assertEqual(perft(Game(self.POS4), 1), 6)
        self.assertEqual(perft(Game(self.POS4), 2), 264)

    def test_pos5_shallow(self):
        self.assertEqual(perft(Game(self.POS5), 1), 44)
        self.assertEqual(perft(Game(self.POS5), 2), 1486)

    @unittest.skipUnless(SLOW, "set CHESS_SLOW_PERFT=1 for deep perft")
    def test_deep(self):
        self.assertEqual(perft(Game(self.START), 4), 197281)
        self.assertEqual(perft(Game(self.KIWIPETE), 3), 97862)
        self.assertEqual(perft(Game(self.POS3), 4), 43238)
        self.assertEqual(perft(Game(self.POS4), 3), 9467)
        self.assertEqual(perft(Game(self.POS5), 3), 62379)


if __name__ == "__main__":
    unittest.main()
