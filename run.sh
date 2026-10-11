#!/bin/sh
# Version: V26.284.1723
# Start RADclouds (macOS / Raspberry Pi). Add --bind 0.0.0.0 to reach it from your phone.
cd "$(dirname "$0")"
exec python3 -m radclouds web "$@"
