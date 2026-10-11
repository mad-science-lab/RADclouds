<!-- Version: V26.284.1445 -->
# RADclouds

Makes a Radion lighting profile on a Neptune Apex drift like passing clouds.
While a virtual outlet you choose is ON, RADclouds nudges each color of the
profile up and down inside a Min/Max range you set, once a minute.

## Related projects

| Name | Link | Description |
|---|---|---|
| **ReefHub** | <https://github.com/mad-science-lab/ReefHub> | Neptune Apex to MQTT bridge: read every outlet and probe, control outlets and feed modes. Home Assistant add-on and Docker. |
| **LunarReef** | <https://github.com/mad-science-lab/LunarReef> | Makes the lunar channel of EcoTech Radion XR15 lights follow the real moon at your location. Home Assistant add-on and local web app. |
| **RADclouds** | <https://github.com/mad-science-lab/RADclouds> | Drifts an EcoTech Radion profile on a Neptune Apex like passing clouds. Home Assistant add-on and local web app. |

## What it does

1. Pick the **Radion profile** and the **virtual outlet** on the web page.
2. Set a **Min** and **Max** for each color and the End intensity. Max minus Min must be more than 15, or set
   Min and Max to the same value to hold that color at that value.
   Optionally set **Cloud speed** (1x to 3x, scales every move) and **Time between steps** (15 to 120 seconds).
3. On the Apex, add `If Output <outlet> = ON Then <profile>` to each Radion's program (the page shows the exact line).
4. Add the virtual switch to the Apex Dashboard, or add logic that controls the switch's state, so the clouds can start and stop.

Python 3.9+ standard library only. Runs on Windows, macOS or a Raspberry Pi, and as a
Home Assistant add-on.

## Install

### Home Assistant add-on

1. In Home Assistant: **Settings > Add-ons > Add-on Store > three-dot menu > Repositories**.
2. Add `https://github.com/mad-science-lab/RADclouds` and close the dialog.
3. Find **RADclouds** in the store, **Install**, **Start**, then open it from the sidebar.

Updates appear under the add-on as usual (three-dot menu, **Check for updates**).
Settings, backups and logs live in the add-on's `/data`, which is included in HA backups.

To install from a Samba share instead, run `.\build_addon.ps1` (stages `dist\radclouds`), copy it to
the HA `addons` share and install it from *Local add-ons*. A local install and a GitHub install
are separate add-ons with separate settings, so use one or the other.

### Standalone (without Home Assistant)

Runs on any computer that can reach the Apex. Nothing to install beyond Python 3.9+.
Keep it running, because the clouds only move while it is.

- **Windows:** double-click `run.bat` (opens <http://127.0.0.1:8789>).
- **macOS / Pi:** `./run.sh` (add `--bind 0.0.0.0` to reach it from a phone).
- **Command line:** `python -m radclouds show | medians | step`

## How it works

When the outlet turns ON the profile is set to the median of each range. Then every
step each of the nine values rolls 1 to 5 on its own (a step is every 60 s by default):

| Roll | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Change at 1x | -4 | -2 | none | +2 | +4 |
| Change at 3x | -12 | -6 | none | +6 | +12 |

At Min or Max a move that would go past the edge is reversed; elsewhere a move that
would go past stops at the edge. All new values are written to the profile in one save,
read back and verified. The Start intensity is never changed.

When the outlet turns OFF the clouds stop and the profile is left as it was. If the
app starts while the outlet is already ON it keeps walking from the profile's current
values instead of jumping back to the median.

## Safety

- Only the chosen profile's color and End values are written, with the rest of the profile
  object preserved. Each start of a run saves the profile to `backups/` first.
- Test against a throwaway Radion profile that no outlet program references before pointing
  it at one your lights use.
- The Apex's local REST API is undocumented and may change between firmware versions.

## Development

```bash
python -m unittest discover tests
```

## License and trademarks

Licensed under the [GNU Affero General Public License v3.0](LICENSE). Free for anyone to use; any copy, part or modified version, including one run as a hosted service, must stay open source under the same license.

RADclouds is an independent project, not affiliated with or endorsed by Neptune
Systems or EcoTech Marine. Neptune Apex is a trademark of Neptune Systems; EcoTech
and Radion are trademarks of EcoTech Marine. They are named only to describe the
equipment RADclouds works with.
