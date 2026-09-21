"""A tiny zero-dependency web server to play against the chess engine.

Serves a clickable board (``webapp/index.html``) and a small JSON API that
drives the *actual* :class:`chess.Game`, so playing here exercises the real
rules engine.  Run with::

    python server.py            # then open http://localhost:8765

Only the Python standard library is used.
"""

from __future__ import annotations

import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from chess import Game, GameOverError, IllegalMoveError
from chess.constants import (
    BLACK,
    FILES,
    RANKS,
    WHITE,
    file_of,
    kind_of,
    opposite,
    rank_of,
    square_name,
)

HERE = os.path.dirname(os.path.abspath(__file__))
WEBAPP = os.path.join(HERE, "webapp")
PORT = int(os.environ.get("CHESS_PORT", "8765"))
# Bind to all interfaces by default so other devices on the same LAN can join;
# set CHESS_HOST=127.0.0.1 to restrict to this machine only.
HOST = os.environ.get("CHESS_HOST", "0.0.0.0")

# A single shared game for this simple local server.
GAME = Game()
LAST_MOVE = {"frm": None, "to": None}
HISTORY = []  # list of SAN strings, in play order
VERSION = 0   # bumped on every state change so clients can live-sync

# Players and clocks.
PLAYERS = {"w": "White", "b": "Black"}
TIMED = False
BASE_MS = 0            # starting time per side, milliseconds
INC_MS = 0             # increment per move, milliseconds
CLOCK = {"w": 0, "b": 0}   # banked remaining time per side (ms)
RUNNING = None         # colour whose clock is currently ticking, or None
TURN_START = 0.0       # monotonic seconds when the running clock started


def bump():
    """Advance the state version so polling clients pick up the change."""
    global VERSION
    VERSION += 1


def _remaining_ms(color):
    """Live remaining time for *color*, or None when the game is untimed."""
    if not TIMED:
        return None
    ms = CLOCK[color]
    if RUNNING == color and not GAME.is_over():
        ms -= (time.monotonic() - TURN_START) * 1000
    return max(0, int(ms))


def _check_timeout():
    """End the game if the side to move has run out of time (FIDE 6.9)."""
    global RUNNING
    if not TIMED or GAME.is_over() or RUNNING is None:
        return
    if _remaining_ms(RUNNING) <= 0:
        loser = RUNNING
        winner = opposite(loser)
        CLOCK[loser] = 0
        RUNNING = None
        GAME.termination = "timeout"
        # 6.9: a flag-fall loses, unless the opponent cannot possibly mate,
        # in which case the game is drawn.
        if GAME._can_possibly_mate(winner):
            GAME.result = "1-0" if winner == WHITE else "0-1"
        else:
            GAME.result = "1/2-1/2"
        bump()


def lan_ip() -> str:
    """Best-effort LAN IP address of this machine (for the shareable link)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packets are actually sent
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def san_of(game_before, move) -> str:
    """A readable Standard Algebraic Notation string for *move*.

    Computed from the position *before* the move; the check/mate suffix is
    added by the caller after the move is played.
    """
    if move.is_castle_kingside:
        return "O-O"
    if move.is_castle_queenside:
        return "O-O-O"
    piece = game_before.board.piece_at(move.frm)
    kind = kind_of(piece)
    is_capture = game_before.board.piece_at(move.to) is not None or move.is_en_passant
    if kind == "P":
        s = ""
        if is_capture:
            s += FILES[file_of(move.frm)] + "x"
        s += square_name(move.to)
        if move.promotion:
            s += "=" + move.promotion
        return s
    s = kind
    # Disambiguation: other same-kind pieces that can also reach the target.
    others = [
        m
        for m in game_before.legal_moves()
        if m.to == move.to
        and m.frm != move.frm
        and kind_of(game_before.board.piece_at(m.frm)) == kind
    ]
    if others:
        same_file = any(file_of(m.frm) == file_of(move.frm) for m in others)
        same_rank = any(rank_of(m.frm) == rank_of(move.frm) for m in others)
        if not same_file:
            s += FILES[file_of(move.frm)]
        elif not same_rank:
            s += RANKS[rank_of(move.frm)]
        else:
            s += square_name(move.frm)
    if is_capture:
        s += "x"
    s += square_name(move.to)
    return s


def state_dict() -> dict:
    _check_timeout()  # flag-fall may end the game even without a move
    g = GAME
    status = g.status()
    king_sq = None
    if not g.is_over() and g.is_in_check():
        ks = g.board.king_square(g.side_to_move)
        king_sq = square_name(ks) if ks is not None else None
    return {
        "fen": g.fen(),
        "board": list(g.board.squares),  # 64 entries, a1..h8, piece char or null
        "side_to_move": g.side_to_move,
        "legal": sorted(m.uci() for m in g.legal_moves()),
        "over": g.is_over(),
        "result": g.result,
        "termination": g.termination,
        "category": status.get("category"),
        "claimable": g.claimable_draw_reasons(),
        "in_check": (not g.is_over()) and g.is_in_check(),
        "check_square": king_sq,
        "fullmove": g.fullmove_number,
        "halfmove_clock": g.halfmove_clock,
        "repetition_count": g.repetition_count(),
        "pending_draw_offer": g.pending_draw_offer,
        "last_move": LAST_MOVE,
        "history": list(HISTORY),
        "version": VERSION,
        "players": dict(PLAYERS),
        "timed": TIMED,
        "base_ms": BASE_MS,
        "inc_ms": INC_MS,
        "clock": {"w": _remaining_ms("w"), "b": _remaining_ms("b")},
        "running": RUNNING if (TIMED and not g.is_over()) else None,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the console quiet
        pass

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    _CTYPES = {
        ".html": "text/html; charset=utf-8",
        ".svg": "image/svg+xml",
        ".css": "text/css",
        ".js": "application/javascript",
        ".png": "image/png",
    }

    def _send_file(self, path):
        try:
            with open(path, "rb") as fh:
                body = fh.read()
        except OSError:
            self.send_error(404)
            return
        ext = os.path.splitext(path)[1].lower()
        ctype = self._CTYPES.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # Cache immutable assets (pieces), but never cache the HTML shell so UI
        # changes always show on reload.
        if ext == ".html":
            self.send_header("Cache-Control", "no-store")
        else:
            self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, rel_path: str) -> bool:
        """Safely serve a file from the webapp directory. Returns True if sent."""
        rel_path = rel_path.lstrip("/")
        full = os.path.normpath(os.path.join(WEBAPP, rel_path))
        # Prevent path traversal outside the webapp directory.
        if not full.startswith(WEBAPP) or not os.path.isfile(full):
            return False
        self._send_file(full)
        return True

    @staticmethod
    def _parse_uci(uci: str):
        from chess.constants import parse_square

        frm = parse_square(uci[0:2])
        to = parse_square(uci[2:4])
        promotion = uci[4].upper() if len(uci) > 4 else None
        return frm, to, promotion

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_file(os.path.join(WEBAPP, "index.html"))
        elif path == "/api/state":
            self._send_json(state_dict())
        elif path == "/api/info":
            self._send_json({"lan_url": f"http://{lan_ip()}:{PORT}", "port": PORT})
        elif self._serve_static(path):
            return
        else:
            self.send_error(404)

    def do_POST(self):
        global GAME, LAST_MOVE, PLAYERS, TIMED, BASE_MS, INC_MS, CLOCK, RUNNING, TURN_START
        path = urlparse(self.path).path
        data = self._read_json()

        if path == "/api/new":
            GAME = Game()
            LAST_MOVE = {"frm": None, "to": None}
            HISTORY.clear()
            white = (str(data.get("white") or "White").strip() or "White")[:24]
            black = (str(data.get("black") or "Black").strip() or "Black")[:24]
            PLAYERS = {"w": white, "b": black}
            try:
                minutes = float(data.get("minutes", 0) or 0)
                inc = float(data.get("increment", 0) or 0)
            except (TypeError, ValueError):
                minutes, inc = 0, 0
            TIMED = minutes > 0
            BASE_MS = int(minutes * 60_000)
            INC_MS = int(inc * 1000)
            CLOCK = {"w": BASE_MS, "b": BASE_MS}
            RUNNING = WHITE if TIMED else None
            TURN_START = time.monotonic()
            bump()
            self._send_json(state_dict())
            return

        if path == "/api/move":
            uci = str(data.get("uci", ""))
            try:
                if GAME.is_over():
                    raise GameOverError("game is over")
                _check_timeout()
                if GAME.is_over():
                    raise GameOverError("game is over")
                mover = GAME.side_to_move
                # Resolve + describe the move against the pre-move position.
                probe = GAME._find_legal_move(*self._parse_uci(uci))
                base = san_of(GAME, probe)
                mv = GAME.push_uci(uci)
                # Clocks: deduct the mover's elapsed time, add the increment,
                # and start the opponent's clock (unless the game just ended).
                if TIMED:
                    elapsed = (time.monotonic() - TURN_START) * 1000
                    CLOCK[mover] -= elapsed
                    if CLOCK[mover] <= 0 and not GAME.is_over():
                        CLOCK[mover] = 0
                        RUNNING = mover
                        _check_timeout()  # flag fell as the move was made
                    else:
                        if not GAME.is_over():
                            CLOCK[mover] += INC_MS
                        RUNNING = opposite(mover) if not GAME.is_over() else None
                        TURN_START = time.monotonic()
                # Add check / checkmate suffix from the resulting position.
                if GAME.is_over() and GAME.termination == "checkmate":
                    base += "#"
                elif GAME.is_in_check():
                    base += "+"
                HISTORY.append(base)
                LAST_MOVE = {"frm": square_name(mv.frm), "to": square_name(mv.to)}
                bump()
                self._send_json(state_dict())
            except (IllegalMoveError, GameOverError, ValueError) as exc:
                self._send_json({"error": str(exc), **state_dict()}, code=400)
            return

        if path == "/api/resign":
            color = WHITE if data.get("color", "w") == "w" else "b"
            try:
                GAME.resign(color)
                bump()
                self._send_json(state_dict())
            except GameOverError as exc:
                self._send_json({"error": str(exc), **state_dict()}, code=400)
            return

        if path == "/api/claim":
            reason = str(data.get("reason", ""))
            try:
                ok = GAME.claim_draw(reason)
                if ok:
                    bump()
                self._send_json({"claim_ok": ok, **state_dict()})
            except (GameOverError, ValueError) as exc:
                self._send_json({"error": str(exc), **state_dict()}, code=400)
            return

        if path == "/api/offer":
            color = WHITE if data.get("color", "w") == "w" else "b"
            try:
                GAME.offer_draw(color)
                bump()
                self._send_json(state_dict())
            except (GameOverError, ValueError) as exc:
                self._send_json({"error": str(exc), **state_dict()}, code=400)
            return

        if path == "/api/offer/accept":
            try:
                GAME.accept_draw()
                bump()
                self._send_json(state_dict())
            except (GameOverError, ValueError) as exc:
                self._send_json({"error": str(exc), **state_dict()}, code=400)
            return

        if path == "/api/offer/decline":
            GAME.decline_draw()
            bump()
            self._send_json(state_dict())
            return

        self.send_error(404)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Chess engine server running.")
    print(f"  On this computer:      http://localhost:{PORT}")
    if HOST != "127.0.0.1":
        print(f"  Share on your network: http://{lan_ip()}:{PORT}")
        print("  (Both devices must be on the same Wi-Fi/LAN. Windows may show")
        print("   a firewall prompt the first time — allow access on private")
        print("   networks so others can connect.)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
