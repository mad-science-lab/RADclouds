#!/usr/bin/with-contenv bashio
# Version: V26.284.1723
# One process: the settings web page (served to Home Assistant through Ingress)
# with the cloud engine running inside it.
set -e

export RADCLOUDS_DATA=/data      # config.json, backups/, logs/, state.json survive restarts
cd /opt/radclouds

# Ingress reaches the add-on over the internal network; the port isn't published.
bashio::log.info "Starting RADclouds on port 8789 (open it from the HA sidebar)"
exec python3 -m radclouds web --bind 0.0.0.0 --port 8789 --no-browser
