# Plan for Extracting Cloudflare WARP GUI Toggle Instructions

- [x] Read the Medium article and extract full text.
- [x] Identify and extract all bash scripts.
- [x] Identify and extract .desktop file contents.
- [x] List all file paths mentioned.
- [x] Summarize the setup instructions.
- [x] Provide the final extracted information to the user.

## Findings
- URL: https://medium.com/@Alcaron/how-i-built-a-cloudflare-warp-gui-toggle-on-linux-wayland-friendly-568f299956ca

### 1. Installation Commands (Ubuntu/Debian)
```bash
curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ noble main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
sudo apt update
sudo apt install cloudflare-warp -y
sudo systemctl enable --now warp-svc
```

### 2. First-time Setup
```bash
sudo warp-cli registration new
sudo warp-cli mode warp
sudo warp-cli connect
warp-cli status
```
Verify with: `curl https://www.cloudflare.com/cdn-cgi/trace | grep warp`

### 3. Install Dependencies (Zenity)
```bash
sudo apt install zenity libnotify-bin -y
```

### 4. Toggle Script (`~/.local/bin/warp-toggle-gui`)
```bash
#!/usr/bin/env bash
set -euo pipefail

need() { command -v "$1" >/dev/null 2>&1 || { zenity --error --text="$1 missing"; exit 1; }; }
notify() { command -v notify-send >/dev/null 2>&1 && notify-send "Cloudflare WARP" "$1" || true; }

need zenity
need warp-cli

WARP="sudo -n /usr/bin/warp-cli"

if ! $WARP registration show >/dev/null 2>&1; then
  $WARP registration new || { zenity --error --text="Registration failed"; exit 1; }
fi

STATUS_RAW="$($WARP status 2>/dev/null || true)"
STATE="$(awk -F': ' '/Status update/ {print $2}' <<<"$STATUS_RAW" | head -n1)"
MODE="$(awk -F': ' '/Mode/ {print tolower($2)}' <<<"$STATUS_RAW" | head -n1)"

ON_WARP=false; ON_DOH=false; ON_OFF=false
case "$STATE:$MODE" in
  Connected:warp) ON_WARP=true ;;
  Connected:doh)  ON_DOH=true ;;
  *) ON_OFF=true ;;
esac

CHOICE=$(zenity --list --radiolist \
  --title="Cloudflare WARP" --width=420 --height=280 \
  --text="Status: $STATE | Mode: $MODE" \
  --column=" " --column="Action" \
  $ON_WARP "Enable WARP (VPN)" \
  $ON_DOH "Enable 1.1.1.1 (DoH)" \
  $ON_OFF "Turn OFF")

[ -z "${CHOICE:-}" ] && exit 0

case "$CHOICE" in
  "Enable WARP (VPN)") $WARP mode warp && $WARP connect && notify "Connected (WARP)" ;;
  "Enable 1.1.1.1 (DoH)") $WARP mode doh && $WARP connect && notify "Connected (DoH)" ;;
  "Turn OFF") $WARP disconnect && notify "Disconnected" ;;
esac
```

### 5. .desktop File (`~/.local/share/applications/warp-toggle-gui.desktop`)
```ini
[Desktop Entry]
Type=Application
Name=Cloudflare WARP Toggle (Custom)
Comment=Enable WARP VPN, 1.1.1.1 (DoH), or turn OFF
Exec=warp-toggle-gui
Icon=network-vpn
Terminal=false
Categories=Network;Security;
```
Command to update database: `update-desktop-database ~/.local/share/applications/`

### 6. Sudoers Rule (`/etc/sudoers.d/warp-cli`)
Replace `iceblue` with your actual username.
```bash
sudo visudo -f /etc/sudoers.d/warp-cli
```
Content to paste:
```text
Defaults:<YOUR_USERNAME> env_keep+=DISPLAY
Defaults:<YOUR_USERNAME> env_keep+=XAUTHORITY
<YOUR_USERNAME> ALL=(root) NOPASSWD: /usr/bin/warp-cli connect, /usr/bin/warp-cli disconnect, /usr/bin/warp-cli status, /usr/bin/warp-cli mode warp, /usr/bin/warp-cli mode doh, /usr/bin/warp-cli registration show, /usr/bin/warp-cli registration new
```
