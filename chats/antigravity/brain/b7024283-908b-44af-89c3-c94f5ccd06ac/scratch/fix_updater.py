import paramiko

HOST = "192.168.86.57"
USER = "root"
PASS = "Malhi5$2"

def fix():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=10)

    # Read the current updater.py from LXC 103
    stdin, stdout, stderr = client.exec_command("pct exec 103 -- cat /root/updater.py")
    script = stdout.read().decode()

    # Replace the broken Glances entities with the native Proxmox entities
    script = script.replace(
        '"cpu": "sensor.proxmox_glances_cpu_usage"',
        '"cpu": "sensor.proxmox_cpu_usage"'
    )
    script = script.replace(
        '"ram": "sensor.proxmox_glances_memory_usage"',
        '"ram": "sensor.proxmox_memory_usage_percentage"'
    )

    # Push the fixed script back
    sftp = client.open_sftp()
    with sftp.file('/tmp/updater.py', 'w') as f:
        f.write(script)
    sftp.close()

    client.exec_command("pct push 103 /tmp/updater.py /root/updater.py")
    
    # Restart the updater process inside LXC 103
    # First kill existing
    client.exec_command("pct exec 103 -- pkill -f updater.py")
    
    # We don't need to manually start it if it's managed by a systemd service, 
    # but let's check if it has a service.
    stdin, stdout, stderr = client.exec_command("pct exec 103 -- systemctl restart updater.service || true")
    
    # If not a service, run it in background
    client.exec_command("pct exec 103 -- bash -c 'nohup python3 /root/updater.py > /dev/null 2>&1 &'")

    client.close()
    print("Updater fixed and restarted!")

if __name__ == "__main__":
    fix()
