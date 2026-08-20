import paramiko
import time

HOST = "192.168.86.57"
USER = "root"
PASS = "Malhi5$2"
VMID = "107"
HF_TOKEN = "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"

def run_cmd(client, cmd):
    print(f"Running: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(f"OUT:\n{out}")
    if err: print(f"ERR:\n{err}")
    return exit_status, out, err

def setup_proxmox():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=10)

    # 1. Clean up Host services if any left
    print("--- Cleaning up Host ---")
    run_cmd(client, "systemctl stop model-download.service || true")
    run_cmd(client, "systemctl disable model-download.service || true")
    run_cmd(client, "rm /etc/systemd/system/model-download.service || true")
    run_cmd(client, "systemctl daemon-reload || true")
    run_cmd(client, "rm /opt/download.sh || true")

    # 2. Configure LXC to use Ethernet via vmbr0 with DHCP
    print("--- Configuring LXC to use Ethernet (vmbr0) ---")
    run_cmd(client, f"pct stop {VMID} || true")
    time.sleep(3)
    # Using dhcp on vmbr0, removing static IP and nameserver
    run_cmd(client, f"pct set {VMID} --net0 name=eth0,bridge=vmbr0,ip=dhcp")
    run_cmd(client, f"pct set {VMID} --nameserver ''")
    run_cmd(client, f"pct start {VMID}")
    
    print("Waiting 15s for Ethernet DHCP...")
    time.sleep(15)

    # Verify LXC internet
    status, out, err = run_cmd(client, f"pct exec {VMID} -- ping -c 1 8.8.8.8")
    if status != 0:
        print("LXC still has no internet on Ethernet! Check cable.")
        return

    # 3. Setup LXC Env
    print("--- Setting up LXC Env ---")
    run_cmd(client, f"pct exec {VMID} -- apt update")
    run_cmd(client, f"pct exec {VMID} -- apt install -y python3 python3-venv python3-pip git wget")
    run_cmd(client, f"pct exec {VMID} -- python3 -m venv /opt/hf_env")
    run_cmd(client, f"pct exec {VMID} -- /opt/hf_env/bin/pip install huggingface_hub hf_transfer")

    # 4. Create Download Script inside LXC
    print("--- Creating Download Script inside LXC ---")
    script_content = f"""#!/bin/bash
export HF_HUB_ENABLE_HF_TRANSFER=1
export PATH="/opt/hf_env/bin:$PATH"
echo "Starting Model Downloads in LXC via Ethernet..."

while true; do
    echo "Downloading Whisper large-v3-turbo..."
    if huggingface-cli download openai/whisper-large-v3-turbo --local-dir /models/whisper-large-v3-turbo; then
        echo "Whisper Downloaded!"
        break
    fi
    echo "Failed, retrying in 10s..."
    sleep 10
done

while true; do
    echo "Downloading Pyannote 3.1..."
    if huggingface-cli download pyannote/speaker-diarization-3.1 --token {HF_TOKEN} --local-dir /models/pyannote-3.1; then
        echo "Pyannote Downloaded!"
        break
    fi
    echo "Failed, retrying in 10s..."
    sleep 10
done

while true; do
    echo "Downloading Qwen-2.5-72B-Instruct-AWQ..."
    if huggingface-cli download Qwen/Qwen2.5-72B-Instruct-AWQ --local-dir /models/qwen2.5-72b-instruct-awq; then
        echo "Qwen Downloaded!"
        break
    fi
    echo "Failed, retrying in 10s..."
    sleep 10
done

echo "All base models downloaded successfully!"
"""
    run_cmd(client, f"pct exec {VMID} -- bash -c \"cat << 'EOF' > /models/download.sh\n{script_content}\nEOF\"")
    run_cmd(client, f"pct exec {VMID} -- chmod +x /models/download.sh")

    # 5. Create Systemd Service inside LXC
    service_content = """[Unit]
Description=Model Downloader Auto-Resume
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/models/download.sh
StandardOutput=append:/models/download.log
StandardError=append:/models/download.log
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
"""
    run_cmd(client, f"pct exec {VMID} -- bash -c \"cat << 'EOF' > /etc/systemd/system/model-download.service\n{service_content}\nEOF\"")
    
    run_cmd(client, f"pct exec {VMID} -- systemctl daemon-reload")
    run_cmd(client, f"pct exec {VMID} -- systemctl enable model-download.service")
    run_cmd(client, f"pct exec {VMID} -- systemctl start model-download.service")

    print("Systemd service started INSIDE LXC via Ethernet! Downloads are securely isolated.")
    
    client.close()

if __name__ == "__main__":
    setup_proxmox()
