import paramiko

HOST = "192.168.86.57"
USER = "root"
PASS = "Malhi5$2"
VMID = "107"

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

    print("--- Fixing DNS and Retrying Installation ---")
    # Fix DNS
    run_cmd(client, f"pct set {VMID} --nameserver 8.8.8.8")
    run_cmd(client, f"pct exec {VMID} -- systemctl restart systemd-resolved || true")
    run_cmd(client, f"pct exec {VMID} -- systemctl restart systemd-networkd || true")
    
    # Test DNS
    status, out, err = run_cmd(client, f"pct exec {VMID} -- ping -c 1 archive.ubuntu.com")
    if status != 0:
        # Hardcode resolv.conf just in case
        run_cmd(client, f"pct exec {VMID} -- bash -c \"echo 'nameserver 8.8.8.8' > /etc/resolv.conf\"")

    # Re-run Env Setup
    run_cmd(client, f"pct exec {VMID} -- apt update")
    run_cmd(client, f"pct exec {VMID} -- apt install -y python3 python3-venv python3-pip git wget")
    run_cmd(client, f"pct exec {VMID} -- python3 -m venv /opt/hf_env")
    run_cmd(client, f"pct exec {VMID} -- /opt/hf_env/bin/pip install huggingface_hub hf_transfer")

    # Restart the service to begin downloading now that hf-cli is installed
    run_cmd(client, f"pct exec {VMID} -- systemctl restart model-download.service")
    print("DNS fixed, environment installed, service restarted!")
    
    client.close()

if __name__ == "__main__":
    setup_proxmox()
