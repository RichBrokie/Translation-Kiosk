# Cloudflare WARP GUI Toggle - Setup Walkthrough

I have successfully prepared the necessary components for your Cloudflare WARP GUI toggle on Zorin OS, mirroring the setup described in the Medium article.

## What was completed
1. **Created the Bash Script**: I wrote the connection toggle script and saved it to `~/.local/bin/warp-toggle-gui`. This script checks the VPN status using `warp-cli` and prompts you with a Wayland-friendly `zenity` dialog to connect or disconnect. It also sends desktop notifications.
2. **Created the Desktop Entry**: I added a `.desktop` application file at `~/.local/share/applications/warp-toggle-gui.desktop`. This allows you to launch the WARP toggle directly from your application launcher or pin it to your taskbar.

## Final Manual Step: Installing Dependencies

Because adding new system repositories and installing packages requires elevated privileges (`sudo`), you will need to run the final installation script yourself. I have prepared an installation script for you.

> [!IMPORTANT]
> Please open your terminal and run the following script. It will prompt for your `sudo` password to install the required packages.

```bash
./install_warp_deps.sh
```

**What the script does:**
- Adds the official Cloudflare repository for Ubuntu Noble (which your Zorin OS system is based on).
- Installs `cloudflare-warp`, `zenity` (for the dialogs), and `libnotify-bin` (for notifications).
- Enables the `warp-svc` background daemon.
- Registers your device as a new WARP client.

## Verification
Once you have run the script successfully:
1. Open your Zorin OS application menu.
2. Search for **"WARP VPN Toggle"**.
3. Click it. A dialog should appear asking if you want to connect to WARP. 
4. Once you click Yes, you will see a desktop notification indicating that you are connected!

Enjoy your seamless, native-feeling VPN toggle!
