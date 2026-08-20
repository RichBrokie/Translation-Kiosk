import paramiko

HOST = "192.168.86.57"
USER = "root"
PASS = "Malhi5$2"
VMID = "107"
HF_TOKEN = "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"

script_content = f"""#!/bin/bash
export HF_HUB_ENABLE_HF_TRANSFER=1
export PATH="/opt/hf_env/bin:$PATH"
echo "Starting Model Downloads in LXC via Ethernet..."

while true; do
    echo "Downloading Whisper large-v3-turbo..."
    if hf download openai/whisper-large-v3-turbo --local-dir /models/whisper-large-v3-turbo; then
        echo "Whisper Downloaded!"
        break
    fi
    echo "Failed, retrying in 10s..."
    sleep 10
done

while true; do
    echo "Downloading Pyannote 3.1..."
    if hf download pyannote/speaker-diarization-3.1 --token {HF_TOKEN} --local-dir /models/pyannote-3.1; then
        echo "Pyannote Downloaded!"
        break
    fi
    echo "Failed, retrying in 10s..."
    sleep 10
done

while true; do
    echo "Downloading Qwen-2.5-72B-Instruct-AWQ..."
    if hf download Qwen/Qwen2.5-72B-Instruct-AWQ --local-dir /models/qwen2.5-72b-instruct-awq; then
        echo "Qwen Downloaded!"
        break
    fi
    echo "Failed, retrying in 10s..."
    sleep 10
done

echo "All base models downloaded successfully!"
"""

def fix():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=10)

    sftp = client.open_sftp()
    with sftp.file('/tmp/download.sh', 'w') as f:
        f.write(script_content)
    sftp.close()

    print("Pushing fixed script...")
    client.exec_command(f"pct push {VMID} /tmp/download.sh /models/download.sh")
    client.exec_command(f"pct exec {VMID} -- chmod +x /models/download.sh")
    client.exec_command(f"pct exec {VMID} -- systemctl restart model-download.service")
    
    print("Fixed script deployed and service restarted!")
    client.close()

if __name__ == "__main__":
    fix()
