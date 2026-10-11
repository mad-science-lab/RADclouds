# Version: V26.284.1723
"""Local web page: choose the profile and virtual outlet, set the ranges, watch it run."""
from __future__ import annotations

import json
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import clouds
from . import service as svc
from .apex import ApexError

STATIC = Path(__file__).resolve().parent / "static"


def config_out(cfg: dict) -> dict:
    out = json.loads(json.dumps(cfg))
    out["apex"]["has_password"] = bool(out["apex"].get("password"))
    out["apex"]["password"] = ""
    out["channel_labels"] = [{"key": k, "label": l} for k, l in clouds.CHANNELS]
    out["min_delta"] = clouds.MIN_DELTA
    out["limits"] = {"speed": [clouds.MIN_SPEED, clouds.MAX_SPEED, clouds.SPEED_STEP],
                     "interval": [clouds.MIN_INTERVAL, clouds.MAX_INTERVAL]}
    out["moves"] = {str(r): m for r, m in clouds.MOVES.items()}
    return out


def save_config(incoming: dict) -> dict:
    cfg = svc.load_config()
    a = incoming.get("apex", {})
    if a.get("host"):
        cfg["apex"]["host"] = str(a["host"]).strip()
    if "username" in a:  # blank is allowed: it means "use the default admin"
        cfg["apex"]["username"] = str(a["username"] or "").strip()
    if a.get("password"):
        cfg["apex"]["password"] = a["password"]
    if "enabled" in incoming:
        cfg["enabled"] = bool(incoming["enabled"])
    if "profile_id" in incoming:
        pid = incoming["profile_id"]
        cfg["profile_id"] = int(pid) if pid not in (None, "") else None
    if "virtual_did" in incoming:
        cfg["virtual_did"] = str(incoming["virtual_did"] or "").strip()
    if "speed" in incoming:
        cfg["speed"] = clouds.validate_speed(incoming["speed"])
    if "interval_seconds" in incoming:
        cfg["interval_seconds"] = clouds.validate_interval(incoming["interval_seconds"])
    if "channels" in incoming:
        cfg["channels"] = clouds.validate_ranges(incoming["channels"])
    svc.save_config(cfg)
    svc.log_activity("Manual", True, "Settings saved")
    return config_out(cfg)


def options() -> dict:
    cfg = svc.load_config()
    apex = svc.connect(cfg)
    profiles = [{"id": p["ID"], "name": p["name"], "data": p.get("data")}
                for p in apex.profiles() if p.get("type") == "radion"]
    outlets = [{"did": o["did"], "name": o.get("name") or o["did"]} for o in apex.virtual_outlets()]
    return {"profiles": profiles, "outlets": outlets}


def status(engine: svc.Engine) -> dict:
    cfg = svc.load_config()
    return {
        "engine": engine.snapshot,
        "state": svc.read_state(),
        "activity": svc.read_activity(),
        "missing": svc.configured(cfg),
        "poll_seconds": svc.POLL_SECONDS,
    }


def make_handler(engine: svc.Engine):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def _send(self, code: int, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def _run(self, fn):
            try:
                self._send(200, fn())
            except (ApexError, svc.ConfigError, ValueError, KeyError) as e:
                self._send(400, {"error": str(e)})
            except Exception as e:
                traceback.print_exc()
                self._send(500, {"error": f"{type(e).__name__}: {e}"})

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            routes = {
                "/api/config": lambda: config_out(svc.load_config()),
                "/api/options": options,
                "/api/status": lambda: status(engine),
            }
            if path in routes:
                return self._run(routes[path])
            self._send(404, {"error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path
            body = self._body()
            routes = {
                "/api/config": lambda: save_config(body),
                "/api/medians": lambda: {"values": engine.apply_medians()},
                "/api/step": lambda: {"values": engine.step_now()},
            }
            if path in routes:
                return self._run(routes[path])
            self._send(404, {"error": "not found"})

    return Handler


def serve(bind: str = "127.0.0.1", port: int = 8789, open_browser: bool = True,
          run_engine: bool = True) -> None:
    engine = svc.Engine()
    # No address reuse: on Windows it lets a second copy share the port silently.
    ThreadingHTTPServer.allow_reuse_address = False
    try:
        httpd = ThreadingHTTPServer((bind, port), make_handler(engine))
    except OSError:
        raise SystemExit(f"Port {port} is already in use - RADclouds is probably already running. "
                         f"Open http://127.0.0.1:{port}/ or start with --port <other>.")
    if run_engine:
        engine.start()
    url = f"http://{'127.0.0.1' if bind in ('0.0.0.0', '') else bind}:{port}/"
    print(f"RADclouds running at {url}  (Ctrl+C to stop)", flush=True)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        engine.stop()
