# Cloudflare WARP GUI Toggle Setup

This plan outlines the steps to install and configure a GUI toggle for Cloudflare WARP on your Zorin OS system, matching the functionality described in the Medium article.

## Proposed Changes

### System Requirements & Dependencies
- Add the Cloudflare APT repository for Ubuntu Noble (which your Zorin OS version is based on).
- Install `cloudflare-warp`, `zenity` (for the GUI dialogs), and `libnotify-bin` (for desktop notifications).
- Ensure the `warp-svc` background service is enabled and running.
- Register your device with WARP using `warp-cli registration new`.

### User Script
#### [NEW] warp-toggle-gui
Create a bash script at `~/.local/bin/warp-toggle-gui` that will serve as the core toggle logic. The script will:
- Check the current connection status using `warp-cli status`.
- Prompt the user to connect or disconnect using a Wayland-friendly `zenity` dialog.
- Send desktop notifications about the status change using `notify-send`.

### Desktop Integration
#### [NEW] warp-toggle-gui.desktop
Create a desktop entry at `~/.local/share/applications/warp-toggle-gui.desktop` so the toggle can be launched from the Zorin OS application menu or pinned to the taskbar.

## Verification Plan

### Automated Tests
- Verify the script is executable and the `.desktop` file is correctly formatted.
- Ensure the Cloudflare WARP service is running and properly registered.

### Manual Verification
- You will need to click the "WARP VPN Toggle" in your application menu to verify that the GUI prompts appear and successfully toggle the VPN connection.
