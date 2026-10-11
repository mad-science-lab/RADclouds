# Version: V26.284.1900
# Stage the RADclouds Home Assistant add-on into dist\radclouds\ - a folder ready
# to copy to the HA machine's /addons share (\\<ha-ip>\addons\radclouds).
#
# Installing from GitHub does not need this: the repository root IS the add-on
# folder (see repository.yaml). This script is for the Samba-share route, which
# builds from its own folder only, so just the files the add-on needs are staged.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$dist = Join-Path $root "dist\radclouds"

if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
New-Item -ItemType Directory -Force $dist | Out-Null

foreach ($f in "config.yaml", "build.yaml", "Dockerfile", "README.md", "CHANGELOG.md", "settings.example.json") {
    Copy-Item (Join-Path $root $f) $dist
}
# The start script must be LF-only with no BOM or the container won't start
$runsh = (Get-Content (Join-Path $root "addon-run.sh") -Raw) -replace "`r`n", "`n"
[System.IO.File]::WriteAllText((Join-Path $dist "addon-run.sh"), $runsh, (New-Object System.Text.UTF8Encoding($false)))

Copy-Item (Join-Path $root "radclouds") (Join-Path $dist "radclouds") -Recurse
Get-ChildItem (Join-Path $dist "radclouds") -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

Write-Host "Staged add-on at: $dist"
Write-Host "Next: copy it to \\<ha-ip>\addons\radclouds, then in HA: Settings > Add-ons > Add-on Store >"
Write-Host "three-dot menu > Check for updates, and install RADclouds from 'Local add-ons'."
