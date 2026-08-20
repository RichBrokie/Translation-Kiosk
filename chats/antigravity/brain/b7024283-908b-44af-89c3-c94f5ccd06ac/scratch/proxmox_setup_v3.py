import paramiko
import time

HOST = "192.168.86.57"
USER = "root"
PASS = "Malhi5$2"
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

    # 1. Setup Env on Proxmox Host
    print("--- Setting up Env on Host ---")
    run_cmd(client, "apt update")
    run_cmd(client, "apt install -y python3-venv python3-pip git wget")
    run_cmd(client, "python3 -m venv /opt/hf_env")
    run_cmd(client, "/opt/hf_env/bin/pip install huggingface_hub hf_transfer")

    # 2. Create Download Script on Host
    script_content = f"""#!/bin/bash
export HF_HUB_ENABLE_HF_TRANSFER=1
export PATH="/opt/hf_env/bin:$PATH"
echo "Starting Model Downloads on Host..."

while true; do
    echo "Downloading Whisper large-v3-turbo..."
    if huggingface-cli download openai/whisper-large-v3-turbo --local-dir /mnt/hdd/whisper-large-v3-turbo; then
        echo "Whisper Downloaded!"
        break
    fi
    echo "Failed, retrying in 10s..."
    sleep 10
done

while true; do
    echo "Downloading Pyannote 3.1..."
    if huggingface-cli download pyannote/speaker-diarization-3.1 --token {HF_TOKEN} --local-dir /mnt/hdd/pyannote-3.1; then
        echo "Pyannote Downloaded!"
        break
    fi
    echo "Failed, retrying in 10s..."
    sleep 10
done

while true; do
    echo "Downloading Qwen-2.5-72B-Instruct-AWQ..."
    if huggingface-cli download Qwen/Qwen2.5-72B-Instruct-AWQ --local-dir /mnt/hdd/qwen2.5-72b-instruct-awq; then
        echo "Qwen Downloaded!"
        break
    fi
    echo "Failed, retrying in 10s..."
    sleep 10
done

echo "All base models downloaded successfully!"
"""
    # Write script safely
    run_cmd(client, f"bash -c \"cat << 'EOF' > /opt/download.sh\n{script_content}\nEOF\"")
    run_cmd(client, "chmod +x /opt/download.sh")

    # 3. Create Systemd Service on Host
    service_content = """[Unit]
Description=Model Downloader Auto-Resume
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/opt/download.sh
StandardOutput=append:/mnt/hdd/download.log
StandardError=append:/mnt/hdd/download.log
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
"""
    run_cmd(client, f"bash -c \"cat << 'EOF' > /etc/systemd/system/model-download.service\n{service_content}\nEOF\"")
    
    # 4. Stop the broken LXC service and enable the host one
    run_cmd(client, "pct exec 107 -- systemctl stop model-download.service || true")
    run_cmd(client, "pct exec 107 -- systemctl disable model-download.service || true")
    
    # Start on host
    run_cmd(client, "systemctl daemon-reload")
    run_cmd(client, "systemctl enable model-download.service")
    run_cmd(client, "systemctl start model-download.service")

    print("Systemd service started ON HOST! Downloads will now survive power outages and automatically resume.")
    
    client.close()

if __name__ == "__main__":
    setup_proxmox()
