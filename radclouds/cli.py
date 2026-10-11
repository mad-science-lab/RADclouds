# Version: V26.284.1723
"""Command line: `python -m radclouds web` (default), `show`, `medians`, `step`."""
from __future__ import annotations

import argparse
import json
import sys

from . import clouds
from . import service as svc
from .apex import ApexError


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="radclouds", description="Drift a Radion profile like passing clouds.")
    sub = p.add_subparsers(dest="cmd")
    w = sub.add_parser("web", help="start the web page and the cloud engine (default)")
    w.add_argument("--bind", default="127.0.0.1", help="0.0.0.0 to reach it from another device")
    w.add_argument("--port", type=int, default=8789)
    w.add_argument("--no-browser", action="store_true")
    w.add_argument("--no-engine", action="store_true", help="page only; do not drive the profile")
    sub.add_parser("show", help="print the profile's current cloud values")
    sub.add_parser("medians", help="write the median values to the profile now")
    sub.add_parser("step", help="move the clouds one step now")
    args = p.parse_args(argv)

    if args.cmd in (None, "web"):
        from .web import serve
        serve(getattr(args, "bind", "127.0.0.1"), getattr(args, "port", 8789),
              not getattr(args, "no_browser", False), not getattr(args, "no_engine", False))
        return

    try:
        cfg = svc.load_config()
        problem = svc.configured(cfg)
        if problem:
            raise svc.ConfigError(problem + " (open the web page, or edit config.json)")
        if args.cmd == "show":
            prof = svc.connect(cfg).profile(int(cfg["profile_id"]))
            vals = svc.read_values(prof)
            print(f"{prof['name']} (ID {prof['ID']})")
            for k, label in clouds.CHANNELS:
                r = cfg["channels"][k]
                print(f"  {label:<14} {vals[k]:>3}   range {r['min']}..{r['max']}")
        else:
            engine = svc.Engine()
            vals = engine.apply_medians("CLI") if args.cmd == "medians" else engine.step_now("CLI")
            print(json.dumps(vals))
    except (ApexError, svc.ConfigError, ValueError) as e:
        sys.exit(f"error: {e}")
