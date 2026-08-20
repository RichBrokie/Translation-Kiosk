import paramiko
import time
import sys

HOST = "192.168.86.57"
USER = "root"
PASS = "Malhi5$2"

def run_cmd(client, cmd):
    print(f"Running: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    
    # Wait for the command to finish and print output line by line if possible
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    err = stderr.read().decode()
    
    if out:
        print(f"OUT:\n{out}")
    if err:
        print(f"ERR:\n{err}")
    
    return exit_status, out, err

def setup_proxmox():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, username=USER, password=PASS, timeout=10)
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # 1. Mount NTFS Drive safely
    print("--- 1. Mounting NTFS HDD ---")
    run_cmd(client, "apt update && apt install -y ntfs-3g")
    run_cmd(client, "mkdir -p /mnt/hdd")
    run_cmd(client, "mount -t ntfs-3g /dev/sda1 /mnt/hdd || echo 'Already mounted or error'")
    
    # Check if mounted
    status, out, err = run_cmd(client, "mount | grep /mnt/hdd")
    if "/mnt/hdd" not in out:
        print("Failed to mount HDD.")
        return

    # 2. Get next free VMID
    status, vmid_str, err = run_cmd(client, "pvesh get /cluster/nextid")
    vmid = vmid_str.strip()
    if not vmid:
        vmid = "106"
    print(f"Using VMID: {vmid}")

    # 3. Create LXC
    print(f"--- 2. Creating LXC {vmid} ---")
    # pveam available showed: system  ubuntu-24.04-standard_24.04-2_amd64.tar.zst
    # Wait, need to check which storage has the template. Usually `local:vztmpl/...`
    # Let's download if not present, but pveam available shows it can be downloaded.
    run_cmd(client, "pveam download local ubuntu-24.04-standard_24.04-2_amd64.tar.zst || echo 'Template might already exist'")
    
    template = "local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
    create_cmd = f"pct create {vmid} {template} --arch amd64 --hostname model-downloader --rootfs local-lvm:8 --memory 4096 --cores 2 --net0 name=eth0,bridge=vmbr0,ip=dhcp --unprivileged 0"
    status, out, err = run_cmd(client, create_cmd)
    
    if status != 0 and "already exists" not in err:
        print("Failed to create LXC.")
        return

    # Configure power outage protection & bind mount
    run_cmd(client, f"pct set {vmid} -onboot 1")
    run_cmd(client, f"pct set {vmid} -mp0 /mnt/hdd,mp=/models")
    
    # Start LXC
    run_cmd(client, f"pct start {vmid}")
    print("Waiting for LXC to start and get IP...")
    time.sleep(15)

    # 4. Setup LXC Environment
    print("--- 3. Setting up LXC Env ---")
    run_cmd(client, f"pct exec {vmid} -- apt update")
    run_cmd(client, f"pct exec {vmid} -- apt install -y python3 python3-pip git wget")
    # In ubuntu 24.04, pip might complain about externally managed environment. Let's use venv or --break-system-packages
    run_cmd(client, f"pct exec {vmid} -- apt install -y python3-venv")
    run_cmd(client, f"pct exec {vmid} -- python3 -m venv /opt/hf_env")
    run_cmd(client, f"pct exec {vmid} -- /opt/hf_env/bin/pip install huggingface_hub hf_transfer")

    # 5. Download Models
    print("--- 4. Downloading Models ---")
    hf_cli = "/opt/hf_env/bin/huggingface-cli"
    
    # Let's create a download script inside the LXC
    dl_script = f"""cat << 'EOF' > /models/download.sh
#!/bin/bash
export HF_HUB_ENABLE_HF_TRANSFER=1
echo "Downloading Whisper large-v3-turbo..."
{hf_cli} download openai/whisper-large-v3-turbo --local-dir /models/whisper-large-v3-turbo
echo "Downloading Qwen-2.5-72B-Instruct-AWQ..."
{hf_cli} download Qwen/Qwen2.5-72B-Instruct-AWQ --local-dir /models/qwen2.5-72b-instruct-awq
echo "Done!"
EOF
"""
    run_cmd(client, f"pct exec {vmid} -- bash -c \"{dl_script}\"")
    run_cmd(client, f"pct exec {vmid} -- chmod +x /models/download.sh")
    
    # We will run the download script in background in the LXC so SSH doesn't time out if it takes long
    # Or just run it and let paramiko wait (but it might take an hour for 40GB)
    # Better to run it via nohup or screen inside LXC.
    run_cmd(client, f"pct exec {vmid} -- apt install -y screen")
    run_cmd(client, f"pct exec {vmid} -- screen -dmS download_session bash -c '/models/download.sh > /models/download.log 2>&1'")
    
    print("Models download started in the background inside the LXC (screen session: download_session).")
    print("Logs are available at /models/download.log inside the LXC.")
    
    client.close()

if __name__ == "__main__":
    setup_proxmox()
