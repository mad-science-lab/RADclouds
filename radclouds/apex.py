# Version: V26.284.1723
"""Minimal Neptune Apex local REST client (standard library only).

The same calls the Apex's own web page makes:
  POST /rest/login               session cookie
  GET  /rest/status              live output states
  GET  /rest/config/pconf        all profiles
  GET  /rest/config/oconf        all outputs (for the virtual-outlet list)
  PUT  /rest/config/pconf/<ID>   save one profile (the whole object)
"""
from __future__ import annotations

import http.cookiejar
import json
import time
import urllib.error
import urllib.request
from typing import Any


class ApexError(RuntimeError):
    pass


_HEADERS = {
    "Accept-Version": "1",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/json",
}


class Apex:
    def __init__(self, host: str, username: str, password: str, timeout: float = 15):
        self.host = host.strip().rstrip("/")
        if not self.host.startswith("http"):
            self.host = "http://" + self.host
        self._user, self._pw, self._timeout = username, password, timeout
        self._http = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self._logged_in = False

    def _call(self, method: str, path: str, body: Any = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.host + path, data=data, method=method, headers=_HEADERS)
        try:
            with self._http.open(req, timeout=self._timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise ApexError(f"{method} {path}: HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ApexError(f"cannot reach {self.host}: {getattr(e, 'reason', e)}") from None
        return json.loads(raw) if raw.strip() else None

    def login(self) -> None:
        try:
            self._call("POST", "/rest/login", {"login": self._user, "password": self._pw})
        except ApexError as e:
            raise ApexError(f"login failed ({e}) - check the Apex address, username and password") from None
        self._logged_in = True

    def _authed(self, method: str, path: str, body: Any = None) -> Any:
        if not self._logged_in:
            self.login()
        try:
            return self._call(method, path, body)
        except ApexError as e:
            if "HTTP 401" not in str(e):
                raise
            self._logged_in = False  # session expired: log in once more and retry
            self.login()
            return self._call(method, path, body)

    # -- read -------------------------------------------------------------

    def outlet_state(self, did: str) -> str | None:
        """Raw state of one output: ON / OFF / AON / AOF / TBL, or None if not found."""
        st = self._authed("GET", f"/rest/status?_={int(time.time() * 1000)}") or {}
        for o in st.get("outputs") or []:
            if str(o.get("did")) == did:
                status = o.get("status")
                if isinstance(status, list) and status:
                    return str(status[0] or "").strip().upper()
                return str(o.get("state", "")).strip().upper() or None
        return None

    def profiles(self) -> list[dict]:
        return (self._authed("GET", "/rest/config/pconf") or {}).get("pconf") or []

    def profile(self, pid: int) -> dict:
        for p in self.profiles():
            if p.get("ID") == pid:
                return p
        raise ApexError(f"no profile with ID {pid} on the Apex")

    def virtual_outlets(self) -> list[dict]:
        outs = (self._authed("GET", "/rest/config/oconf") or {}).get("oconf") or []
        return [o for o in outs if o.get("type") == "virtual"]

    # -- write ------------------------------------------------------------

    def put_profile(self, obj: dict) -> Any:
        return self._authed("PUT", f"/rest/config/pconf/{obj['ID']}", obj)
