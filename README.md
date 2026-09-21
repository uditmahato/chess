# chess — a FIDE-compliant chess rules engine

A dependency-free Python implementation of the standard rules of chess,
following the **FIDE Laws of Chess (in force from 1 January 2023)**, with a
comprehensive automated test suite and a rule-by-rule compliance audit.

See [`AUDIT.md`](AUDIT.md) for the full compliance matrix (every rule mapped to
its code path and test) and the list of things that cannot be verified purely by
automated testing.

## Quick start

```python
from chess import Game

g = Game()                     # standard starting position
g.push_uci("e2e4")
g.push_uci("e7e5")
print(g.legal_moves())         # list[Move]
print(g.status())              # {'over': False, 'category': 'ongoing', ...}
```

### What it enforces

- Full legal move generation with king-safety (pins, discovered/double check).
- Castling and every castling restriction; en passant; promotion (Q/R/B/N).
- Check, checkmate, stalemate.
- Dead position / insufficient material (auto-draw).
- Repetition: **threefold** (claimable) and **fivefold** (automatic).
- Move counters: **fifty-move** (claimable) and **seventy-five-move**
  (automatic), with checkmate taking precedence.
- Draw by agreement, resignation, and correct game termination.

It distinguishes the four FIDE situations explicitly: *drawn automatically*,
*a player may claim a draw*, *a player may offer a draw*, and *the game
continues* — via `Game.status()`, `Game.can_claim_*`, `Game.claim_draw`, and
the `offer_draw`/`accept_draw` API.

## Layout

```
chess/            the engine (constants, board, move, game)
tests/            unittest suite (perft + rule-by-rule tests)
AUDIT.md          FIDE compliance matrix and audit report
```

## Running the tests

```bash
python -m unittest discover -t . -s tests               # fast suite
CHESS_SLOW_PERFT=1 python -m unittest discover -t . -s tests   # + deep perft
```
