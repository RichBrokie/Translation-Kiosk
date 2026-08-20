# Background Service Management

I have successfully updated the `auto-animations.sh` battery script to manage your heavy background services along with the UI animations!

## Changes Made
- Modified `~/.local/bin/auto-animations.sh` to include a list of user-level services that consume background resources.
- When your laptop switches to **battery power**, the script now runs `systemctl --user stop` on the following services:
  - `onedrive.service` & `rclone-onedrive.service` (Cloud sync)
  - `tracker-miner-fs-3.service` (GNOME File Indexing)
  - `evolution-*` services (Background Calendar/Contacts Sync)
- When your laptop is plugged back into **AC power**, the script runs `systemctl --user start` to seamlessly resume them without you noticing!

## What was Tested
- I restarted the script and verified that it correctly parses the service list.
- I verified that the services successfully shut down cleanly when the script triggered the battery mode.

> [!NOTE]
> Since we only targeted user-level services, this will happen completely silently in the background. You will never be bothered by a password prompt when unplugging your charger!
