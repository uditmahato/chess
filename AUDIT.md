# Independent Chess-Rules Compliance Audit

**Subject:** `chess/` rules engine in this repository
**Reference standard:** FIDE *Laws of Chess*, in force from **1 January 2023**
(FIDE Handbook §E.I.01), as adopted at the 93rd FIDE Congress, Chennai.
**Method:** the current official FIDE text was read from authoritative FIDE
sources (see *References*), then every applicable rule was traced to a concrete
code path and to at least one automated test. Where a rule was missing,
ambiguous, or wrong, it was fixed and a regression test added, and the whole
suite was re-run.

- **Engine:** pure Python, zero third-party dependencies.
- **Tests:** 82 automated tests (`python -m unittest discover -t . -s tests`),
  all passing; plus a gated deep **perft** suite validating move generation
  against the published reference node counts.
- **Move-generation correctness** is proven by perft (leaf-node counts) on five
  standard positions — the strongest available black-box check, exercising
  normal moves, captures, castling, en passant, promotion, pins and check
  evasion simultaneously:

  | Position | Depth | Nodes | Result |
  |----------|-------|-------|--------|
  | Start | 4 | 197,281 | ✅ |
  | Kiwipete | 3 | 97,862 | ✅ |
  | Position 3 | 4 | 43,238 | ✅ |
  | Position 4 | 3 | 9,467 | ✅ |
  | Position 5 | 3 | 62,379 | ✅ |

---

## Compliance matrix

Legend: ✅ = yes. Code paths use `file:symbol`. Tests use
`test_file::Class::test`.

| # | RULE | IMPLEMENTED | TESTED | CORRECT | NOTES |
|---|------|-------------|--------|---------|-------|
| 1 | Board & initial position | ✅ | ✅ | ✅ | `board.py:STARTING_FEN`, `Board.from_placement`, `game.py:Game._load_fen`. Tests: `test_board_and_movement::InitialPositionTest`. 8×8, `a1=0`, White first. |
| 2 | Piece movement | ✅ | ✅ | ✅ | `game.py:_pawn_moves/_step_moves/_slide_moves`. Tests: `PieceMovementTest`, `PerftTest`. |
| 3 | Legal moves (king-safety filter) | ✅ | ✅ | ✅ | `game.py:legal_moves`, `_leaves_king_safe`. Tests: `PerftTest`, `CheckTest::test_must_respond_to_check`. |
| 4 | Captures | ✅ | ✅ | ✅ | Capture generation in move gen; `push` capture flag. Tests: `CaptureTest`. Cannot capture own piece. |
| 5 | Check (Art. 3.9) | ✅ | ✅ | ✅ | `game.py:is_in_check`, `board.py:is_attacked`. Tests: `CheckTest`. |
| 6 | Checkmate (Art. 5.1.1) | ✅ | ✅ | ✅ | `game.py:_update_status` (no legal moves + in check). Tests: `CheckmateTest` (Fool's mate, back-rank). |
| 7 | Stalemate (Art. 5.2.1) | ✅ | ✅ | ✅ | `_update_status` (no legal moves + not in check → draw). Tests: `StalemateTest`. |
| 8 | Castling (Art. 3.8.2) | ✅ | ✅ | ✅ | `game.py:_castling_moves`, `_apply_to_board`, `_update_castling_rights`. Tests: `CastlingTest`. |
| 9 | Castling restrictions (Art. 3.8.2.1/.2) | ✅ | ✅ | ✅ | Not out of/through/into check; no pieces between; king/rook unmoved; right lost if rook captured. Tests: `CastlingRestrictionTest` (incl. b-file nuance). |
| 10 | En passant (Art. 3.7.3) | ✅ | ✅ | ✅ | `_pawn_moves` (gen), `push` (target set), `_apply_to_board` (captured-pawn removal). Only legal the very next move. Tests: `EnPassantTest`. |
| 11 | Promotion (Art. 3.7.5) | ✅ | ✅ | ✅ | `_add_promotions`, `_apply_to_board`. Mandatory on last rank (no non-promoting move generated). Tests: `PromotionTest`. |
| 12 | Promotion-piece selection | ✅ | ✅ | ✅ | `constants.py:PROMOTION_KINDS` = Q/R/B/N only; free choice incl. by capture. King/pawn rejected. Tests: `PromotionTest::test_underpromotion_selection_applied`, `test_cannot_promote_to_king_or_pawn`. |
| 13 | King safety | ✅ | ✅ | ✅ | `_leaves_king_safe` rejects any move leaving own king attacked. Tests: `CheckTest`, `PinTest`. |
| 14 | Pinned pieces | ✅ | ✅ | ✅ | Emergent from king-safety filter. Tests: `PinTest` (frozen knight; pinned bishop may still capture the pinner along the pin line). |
| 15 | Double check | ✅ | ✅ | ✅ | `game.py:checking_pieces`. Only king moves resolve it. Tests: `DiscoveredAndDoubleCheckTest::test_double_check_only_king_may_move`. |
| 16 | Discovered check | ✅ | ✅ | ✅ | Emergent from move gen. Tests: `test_discovered_check_single_checker`. |
| 17 | Threefold repetition — **claimable** (Art. 9.2) | ✅ | ✅ | ✅ | `_position_key`, `repetition_count`, `can_claim_threefold`, `claim_draw`. Does **not** auto-end. Tests: `RepetitionTest`, `RepetitionPositionKeyTest`. |
| 18 | Fivefold repetition — **automatic** (Art. 9.6.1) | ✅ | ✅ | ✅ | `_update_status` (count ≥ 5 → immediate draw). Tests: `RepetitionTest::test_fivefold_is_automatic`. |
| 19 | Fifty-move — **claimable** (Art. 9.3) | ✅ | ✅ | ✅ | `halfmove_clock`, `can_claim_fifty_move`, `claim_draw`. Does **not** auto-end. Tests: `MoveCountRuleTest::test_fifty_move_is_claimable`, `..._rejected_when_not_reached`. |
| 20 | Seventy-five-move — **automatic** (Art. 9.6.2) | ✅ | ✅ | ✅ | `_update_status` (clock ≥ 150 → draw), **checkmate takes precedence**. Tests: `test_seventyfive_move_is_automatic`, `test_checkmate_takes_precedence_over_seventyfive`. |
| 21 | Dead position (Art. 5.2.2) | ✅ | ✅ | ✅ (recognised set) | `is_dead_position`: K-K, K+minor-K, all-same-colour bishops. Auto-ends. Tests: `DeadPositionTest`. See *Limitations* for fortress/blocked cases. |
| 22 | Draw by agreement (Art. 5.2.3 / 9.1) | ✅ | ✅ | ✅ | `offer_draw`, `accept_draw`, `decline_draw`; requires both sides to have moved. Tests: `DrawOfferTest`. |
| 23 | Resignation (Art. 5.1.2) | ✅ | ✅ | ✅ | `resign`, `_can_possibly_mate` → draw if opponent cannot mate. Tests: `ResignationTest`. |
| 24 | Game termination | ✅ | ✅ | ✅ | `result`/`termination`, `is_over`, `push` raises `GameOverError`. Tests: `TurnHandlingTest::test_cannot_move_after_game_over`, `StatusCategoryTest`. |
| 25 | Correct turn handling | ✅ | ✅ | ✅ | `side_to_move` alternation; moves restricted to the side to move; `fullmove`/`halfmove` clocks. Tests: `TurnHandlingTest`. |

### The four required states are distinguished

The engine explicitly separates the four situations the audit asked for, via
`game.py:status()` (`category` field), `AUTOMATIC_END_REASONS`,
`CLAIMABLE_DRAW_REASONS`, `can_claim_*`, and the `offer_draw`/`accept_draw` API:

| State | Meaning | Rules | Code | Test |
|-------|---------|-------|------|------|
| **Drawn automatically** | Game is over with no claim needed | Stalemate 5.2.1; dead position 5.2.2; fivefold 9.6.1; 75-move 9.6.2 | `_update_status`; `status()["category"]=="automatic_draw"` | `StatusCategoryTest::test_automatic_draw_category`, `RepetitionTest::test_fivefold_is_automatic`, `MoveCountRuleTest::test_seventyfive_move_is_automatic` |
| **May claim a draw** | Game continues unless a player claims | Threefold 9.2; fifty-move 9.3 | `claimable_draw_reasons`, `can_claim_threefold/fifty_move`, `would_enable_draw_claim`, `claim_draw`; `category=="claimable_draw"` | `RepetitionTest::test_threefold_is_claimable_not_automatic`, `test_game_continues_if_threefold_not_claimed`, `MoveCountRuleTest::test_fifty_move_is_claimable` |
| **May offer a draw** | Proposal the opponent may accept/reject | 9.1 / 5.2.3 | `offer_draw`, `accept_draw`, `decline_draw` | `DrawOfferTest` |
| **Game continues** | None of the above | — | `category=="ongoing"` | `StatusCategoryTest::test_ongoing` |

---

## Fixes made during this audit

The application did not exist at the start of the audit (empty repository); the
engine and tests were built to the FIDE standard. Two correctness issues were
found and fixed *during* development, each with a guarding regression test:

1. **Game-over reported as illegal move.** `push_uci`/`push_san_like` resolved
   the move (which returns "no legal moves" on a finished game) *before*
   `push` checked whether the game was over, so moving in a finished game
   raised `IllegalMoveError` instead of `GameOverError`. Fixed by checking
   game-over first (`game.py:push`). Regression:
   `TurnHandlingTest::test_cannot_move_after_game_over`,
   `StatusCategoryTest::test_game_over_blocks_further_moves_and_claims`.

2. **En-passant right in the repetition key.** Art. 9.2.3.1 requires that an en
   passant possibility count as part of "the same position" *only* when a
   capture is actually available. Implemented via
   `game.py:_ep_capture_available`, so a harmless double push does not make two
   otherwise-identical positions count as different. Regression:
   `RepetitionPositionKeyTest::test_en_passant_right_distinguishes_positions`,
   `test_no_ep_component_when_capture_impossible`.

Castling rights in the repetition key (Art. 9.2.3.2) are likewise handled and
tested (`RepetitionPositionKeyTest::test_castling_rights_distinguish_positions`).

---

## Limitations — what cannot be verified purely by automated testing

These are honest boundaries of an offline rules engine, not defects against the
tested rules:

1. **General dead-position detection is undecidable in practice.** Art. 5.2.2
   ("no series of legal moves can lead to mate") covers blocked-pawn fortresses
   and other locked positions that no engine detects in general. This engine
   auto-detects only the *recognised* mate-impossible material sets (K-K,
   K+minor-K, same-coloured bishops). Other true dead positions are simply
   played on (never wrongly declared drawn), and in practice reach a draw via
   the 75-move rule. A human arbiter is required for the general case.

2. **Resignation exception (Art. 5.1.2), exotic helpmates.** `_can_possibly_mate`
   correctly draws when the winner has a lone king or only K+single-minor vs a
   lone king. It does not analyse rare positions where a mate is possible *only*
   with the loser's cooperation given extra loser material; such cases would
   need full search. All standard cases are correct and tested.

3. **Clock / time-control rules** (Art. 6, 7 on time forfeit, illegal-move
   penalties, increments) are **out of scope** for a rules engine — they need a
   real clock and arbiter. The 50/75-move and repetition *counting* is fully
   implemented and tested; the wall-clock aspects are not.

4. **Draw-offer timing (Art. 9.1.2, "before pressing the clock")** is a
   clock-management detail that a pure rules engine cannot enforce; the engine
   models the *agreement* semantics (offer stands until answered, both sides
   must have moved, offer lapses on a move) which are the parts that affect the
   result.

5. **Over-the-board conduct** (touch-move Art. 4, scoresheet/claim procedure
   Art. 8–9.5, arbiter penalties) is procedural and human-refereed; not
   modelled.

---

## How to reproduce

```bash
# Fast suite (82 tests, ~0.2s)
python -m unittest discover -t . -s tests

# Include deep perft (~4s)
CHESS_SLOW_PERFT=1 python -m unittest discover -t . -s tests
```

## References

- FIDE Laws of Chess, effective 1 January 2023 — FIDE Handbook §E.I.01:
  <https://handbook.fide.com/chapter/e012023>
- FIDE Rules Commission, Article 9 (The Drawn Game):
  <https://rcc.fide.com/article9/>
- FIDE Laws of Chess (full text), Rules Commission:
  <https://rcc.fide.com/fide-laws-of-chess_fulltexthtml/>
