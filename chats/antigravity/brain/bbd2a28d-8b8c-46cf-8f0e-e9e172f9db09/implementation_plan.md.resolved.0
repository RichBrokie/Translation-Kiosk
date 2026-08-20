# Setup Weylus for iPad Screen Extension and Apple Pencil Support

This plan outlines the steps to install Weylus, configure it for full Apple Pencil support, and set up a virtual monitor on GNOME Wayland so that you can *extend* your display rather than just mirroring it.

## User Review Required

> [!IMPORTANT]  
> Wayland makes extending displays to virtual screens notoriously tricky because it doesn't allow applications to easily spoof new monitors for security reasons. To achieve an *extended* display (rather than just mirrored), you will need to install a GNOME Shell Extension. Furthermore, enabling full Apple Pencil pressure requires adding your user to a system group, which means you will need to **restart your computer** (or log out and log back in) after the script finishes for the changes to take effect. 

## Open Questions

- You are currently running Zorin OS 18.1 with Wayland. Do you already have a method for creating virtual monitors (e.g., a physical dummy HDMI plug), or would you prefer I guide you through installing the GNOME extension for virtual monitors?

## Proposed Changes

I will create an installation script (`setup_weylus.sh`) that will:
1. Download the latest version of Weylus from GitHub and install it to `~/.local/bin/`.
2. Configure system permissions (`udev` rules) to grant your user access to `/dev/uinput`. This is **required** for Weylus to inject touch and Apple Pencil pressure events into the Linux kernel.

### `setup_weylus.sh`
#### [NEW] setup_weylus.sh
The script will perform the following commands:
```bash
#!/bin/bash
# 1. Download Weylus
wget https://github.com/H-M-H/Weylus/releases/latest/download/linux.zip -O /tmp/weylus.zip
unzip /tmp/weylus.zip -d /tmp/weylus
cp /tmp/weylus/Weylus ~/.local/bin/weylus
chmod +x ~/.local/bin/weylus

# 2. Setup Uinput rules for Apple Pencil
sudo groupadd -r uinput
sudo usermod -aG uinput $USER
echo 'KERNEL=="uinput", MODE="0660", GROUP="uinput", OPTIONS+="static_node=uinput"' | sudo tee /etc/udev/rules.d/60-weylus.rules
sudo udevadm control --reload
sudo udevadm trigger

echo "Weylus installed! Please RESTART your computer to apply the uinput group permissions."
```

## Are there better alternatives?

You asked if there are better alternatives. If your requirements are specifically **extending your screen** while retaining **Apple Pencil pressure and tilt support**, **Weylus is currently the absolute best option for Linux.**

However, here are other alternatives and why they might or might not work for you:

1. **GNOME Remote Desktop (RDP)**
   - *How it works:* You enable RDP in GNOME settings and use the Microsoft Remote Desktop app on your iPad. GNOME 46 has a built-in feature to create an extended virtual monitor automatically upon connection.
   - *Pros:* Completely native to your system, extremely stable, very easy to extend the display.
   - *Cons:* **Does not support Apple Pencil pressure**. It will only emulate a basic mouse pointer.
2. **Deskreen**
   - *How it works:* Shares your screen over a web browser.
   - *Pros:* Works on anything with a browser.
   - *Cons:* No Apple Pencil support, and still requires a virtual display workaround on Wayland.
3. **Sunshine + Moonlight**
   - *How it works:* GPU-accelerated game streaming.
   - *Pros:* Incredible latency and performance.
   - *Cons:* Primarily for mirroring (unless you have a dummy HDMI plug), and again, no native Apple Pencil pressure mapping.

## Verification Plan

### Automated Tests
- The script will run without errors and `~/.local/bin/weylus` will be executable.

### Manual Verification
1. Approve this plan to let me run the setup script.
2. After the script runs, **Restart your laptop**.
3. Install the **"Virtual Monitors" GNOME Extension** (I will provide the link in the Walkthrough). 
4. Create a virtual monitor using the extension.
5. Open Weylus, select the newly created virtual monitor in the "Screen" dropdown, check "Enable Uinput", and connect from your iPad via Safari.
