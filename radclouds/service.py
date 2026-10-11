# Version: V26.284.1723
"""Config, state, activity log, backups, and the engine that runs the clouds.

Data lives next to the project (config.json, state.json, backups/, logs/), or in
the folder named by RADCLOUDS_DATA (the Home Assistant add-on uses /data).
"""
from __future__ import annotations

import copy
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from . import clouds
from .apex import Apex, ApexError

ROOT = Path(os.environ.get("RADCLOUDS_DATA") or Path(__file__).resolve().parent.parent)
CONFIG = ROOT / "config.json"
STATE = ROOT / "state.json"
BACKUPS = ROOT / "backups"
LOGS = ROOT / "logs"
ACTIVITY = LOGS / "activity.jsonl"

DEFAULT_USER = "admin"          # Apex factory login, used when the fields are left blank
DEFAULT_PASSWORD = "1234"

POLL_SECONDS = 10      # longest gap between checks of the virtual outlet
DEFAULT_SPEED = 1.0    # 1x = the base move sizes
DEFAULT_INTERVAL = 60  # seconds between steps while the outlet is ON
KEEP_BACKUPS = 30
KEEP_EVENTS = 20       # activity log length: only the newest events are kept


class ConfigError(ValueError):
    pass


def default_config() -> dict:
    return {
        "apex": {"host": "", "username": "", "password": ""},
        "enabled": True,
        "profile_id": None,
        "virtual_did": "",
        "speed": DEFAULT_SPEED,
        "interval_seconds": DEFAULT_INTERVAL,
        "channels": {k: {"min": 20, "max": 80} for k in clouds.KEYS},
    }


def load_config(path: Path = CONFIG) -> dict:
    cfg = default_config()
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        cfg["apex"].update(saved.get("apex", {}))
        for k in ("enabled", "profile_id", "virtual_did", "speed", "interval_seconds"):
            if k in saved:
                cfg[k] = saved[k]
        for k, r in (saved.get("channels") or {}).items():
            if k in cfg["channels"] and isinstance(r, dict):
                cfg["channels"][k].update({x: r[x] for x in ("min", "max") if x in r})
    return cfg


def save_config(cfg: dict, path: Path = CONFIG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def connect(cfg: dict) -> Apex:
    a = cfg["apex"]
    if not a.get("host"):
        raise ConfigError("Enter the Apex address first")
    # Blank login falls back to the Apex factory defaults.
    return Apex(a["host"], (a.get("username") or "").strip() or DEFAULT_USER, a.get("password") or DEFAULT_PASSWORD)


# -- activity / state / backups ------------------------------------------------

def log_activity(source: str, ok: bool, message: str, detail: dict | None = None) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now().isoformat(timespec="seconds"), "source": source,
           "ok": ok, "message": message}
    if detail:
        row["detail"] = detail
    with ACTIVITY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    _trim_log()


def _trim_log() -> None:
    try:
        lines = ACTIVITY.read_text(encoding="utf-8").splitlines()
        if len(lines) > KEEP_EVENTS:
            ACTIVITY.write_text("\n".join(lines[-KEEP_EVENTS:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def read_activity(n: int = KEEP_EVENTS) -> list[dict]:
    if not ACTIVITY.exists():
        return []
    out = []
    for line in ACTIVITY.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return list(reversed(out))


def read_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(**kv) -> None:
    st = read_state()
    st.update(kv)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def backup_profile(profile: dict, why: str) -> str:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now():%Y%m%d-%H%M%S}-pconf{profile['ID']}-{why}.json"
    (BACKUPS / name).write_text(json.dumps(profile, indent=2), encoding="utf-8")
    for old in sorted(BACKUPS.glob("*.json"))[:-KEEP_BACKUPS]:
        old.unlink(missing_ok=True)
    return name


# -- writing the profile -----------------------------------------------------------

def read_values(profile: dict) -> dict[str, int]:
    """The cloud-walk channel values currently stored in a Radion profile."""
    data = profile.get("data") or {}
    try:
        return {k: int(data[clouds.data_key(k)]) for k in clouds.KEYS}
    except (KeyError, TypeError, ValueError):
        raise ApexError(f"profile {profile.get('name')!r} is missing Radion channel values") from None


def write_values(apex: Apex, pid: int, values: dict[str, int]) -> dict:
    """Merge `values` into the profile, PUT the whole object, read it back."""
    profile = apex.profile(pid)
    if profile.get("type") != "radion":
        raise ApexError(f"profile {profile.get('name')!r} is type {profile.get('type')!r}, not Radion")
    new = copy.deepcopy(profile)
    for k, v in values.items():
        new["data"][clouds.data_key(k)] = int(v)
    resp = apex.put_profile(new)
    if isinstance(resp, dict) and resp.get("errorCode"):
        raise ApexError(f"Apex refused the profile: {resp.get('errorMessage') or resp['errorCode']}")
    back = apex.profile(pid)
    wrong = [k for k, v in values.items() if back["data"].get(clouds.data_key(k)) != int(v)]
    if wrong:
        raise ApexError("read-back mismatch on " + ", ".join(clouds.LABELS[k] for k in wrong))
    return back


def configured(cfg: dict) -> str | None:
    """None when ready, otherwise what is missing."""
    if cfg.get("profile_id") in (None, ""):
        return "Choose a profile"
    if not cfg.get("virtual_did"):
        return "Choose a virtual outlet"
    return None


# -- the engine ----------------------------------------------------------------------

class Engine(threading.Thread):
    """Polls the virtual outlet; while it is ON, moves the clouds every `interval_seconds`."""

    def __init__(self) -> None:
        super().__init__(daemon=True, name="radclouds-engine")
        self.lock = threading.Lock()        # one Apex conversation at a time
        self._halt = threading.Event()
        self.snapshot: dict = {"engine": "starting"}
        self._prev_on: bool | None = None
        self._next_step = 0.0
        self._wait = float(POLL_SECONDS)   # how long the loop sleeps before its next check
        self._last_error = ""

    def stop(self) -> None:
        self._halt.set()

    # -- manual actions (from the web page) ----------------------------------

    def apply_medians(self, source: str = "Manual") -> dict:
        cfg = load_config()
        problem = configured(cfg)
        if problem:
            raise ConfigError(problem)
        ranges = clouds.validate_ranges(cfg["channels"])
        with self.lock:
            apex = connect(cfg)
            vals = self._write(apex, cfg, clouds.medians(ranges), source, "Set to median values", backup=True)
        return vals

    def step_now(self, source: str = "Manual") -> dict:
        cfg = load_config()
        problem = configured(cfg)
        if problem:
            raise ConfigError(problem)
        ranges = clouds.validate_ranges(cfg["channels"])
        with self.lock:
            apex = connect(cfg)
            return self._step(apex, cfg, ranges, source)

    # -- internals -------------------------------------------------------------------

    def _write(self, apex: Apex, cfg: dict, values: dict, source: str, message: str,
               backup: bool = False) -> dict:
        pid = int(cfg["profile_id"])
        if backup:
            backup_profile(apex.profile(pid), "before-start")
        back = write_values(apex, pid, values)
        now = read_values(back)
        write_state(values=now, last_write_at=datetime.now().isoformat(timespec="seconds"))
        log_activity(source, True, f"{message} ({back['name']})", {"values": now})
        return now

    def _step(self, apex: Apex, cfg: dict, ranges: dict, source: str) -> dict:
        scale = clouds.validate_speed(cfg.get("speed", DEFAULT_SPEED))
        tag = f"Step {scale:g}x"
        cur = read_values(apex.profile(int(cfg["profile_id"])))
        new = clouds.step(cur, ranges, scale)
        changed = {k: [cur[k], new[k]] for k in clouds.KEYS if cur[k] != new[k]}
        if not changed:
            log_activity(source, True, f"{tag}: no channel moved", {"values": new})
            write_state(values=new, last_step_at=datetime.now().isoformat(timespec="seconds"))
            return new
        back = write_values(apex, int(cfg["profile_id"]), new)
        now = read_values(back)
        write_state(values=now, last_step_at=datetime.now().isoformat(timespec="seconds"))
        log_activity(source, True, f"{tag}: " + ", ".join(
            f"{clouds.LABELS[k]} {a}->{b}" for k, (a, b) in changed.items()), {"values": now})
        return now

    def _publish(self, **kv) -> None:
        self.snapshot = {**self.snapshot, **kv, "updated": datetime.now().isoformat(timespec="seconds")}

    def run(self) -> None:
        print("RADclouds engine running", flush=True)
        while not self._halt.is_set():
            self._wait = POLL_SECONDS
            try:
                self._tick()
            except (ApexError, ConfigError, ValueError) as e:
                msg = str(e)
                if msg != self._last_error:           # log a repeating failure once
                    log_activity("Engine", False, msg)
                    self._last_error = msg
                self._publish(engine="error", error=msg)
            except Exception as e:  # never let the loop die
                msg = f"{type(e).__name__}: {e}"
                if msg != self._last_error:
                    log_activity("Engine", False, msg)
                    self._last_error = msg
                self._publish(engine="error", error=msg)
            self._halt.wait(self._wait)

    def _tick(self) -> None:
        cfg = load_config()
        if not cfg.get("enabled", True):
            self._prev_on = None
            self._publish(engine="disabled", error="", outlet=None)
            return
        problem = configured(cfg)
        if problem:
            self._prev_on = None
            self._publish(engine="not configured", error=problem, outlet=None)
            return
        ranges = clouds.validate_ranges(cfg["channels"])
        interval = clouds.validate_interval(cfg.get("interval_seconds", DEFAULT_INTERVAL))
        with self.lock:
            apex = connect(cfg)
            raw = apex.outlet_state(cfg["virtual_did"])
            if raw is None:
                raise ApexError(f"virtual outlet {cfg['virtual_did']} not found on the Apex")
            on = raw in ("ON", "AON")
            now = time.monotonic()

            if on and self._prev_on is not True:
                if self._prev_on is None:
                    # Engine (re)started while already ON: keep walking from where the
                    # profile is rather than jolting the lights back to the median.
                    cur = read_values(apex.profile(int(cfg["profile_id"])))
                    start = {k: clouds.next_value(cur[k], ranges[k]["min"], ranges[k]["max"], 3)
                             for k in clouds.KEYS}
                    self._write(apex, cfg, start, "Engine", "Resumed with outlet already ON", backup=True)
                else:
                    self._write(apex, cfg, clouds.medians(ranges), "Engine",
                                "Outlet turned ON: set to median values", backup=True)
                self._next_step = time.monotonic() + interval
            elif on and now >= self._next_step:
                self._step(apex, cfg, ranges, "Engine")
                self._next_step = time.monotonic() + interval
            elif not on and self._prev_on is True:
                log_activity("Engine", True, "Outlet turned OFF: clouds stopped, profile left as is")

            self._prev_on = on
            self._last_error = ""
            nxt = None
            if on:
                # A shorter interval saved while running takes effect at once.
                self._next_step = min(self._next_step, time.monotonic() + interval)
                nxt = max(0, int(self._next_step - time.monotonic()))
                self._wait = max(1.0, min(POLL_SECONDS, self._next_step - time.monotonic()))
            self._publish(engine="running", error="", outlet=raw, on=on, next_step_in=nxt)
