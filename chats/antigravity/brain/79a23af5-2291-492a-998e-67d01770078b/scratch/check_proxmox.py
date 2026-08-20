import paramiko
import sys

def run_remote_commands(host, port, username, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {username}@{host}:{port}...")
        ssh.connect(host, port=port, username=username, password=password, timeout=10)
        print("Connected successfully!\n")
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)
        
    commands = [
        ("Disk space (df -hT)", "df -hT"),
        ("ZFS Pools status (zpool list)", "zpool list"),
        ("ZFS Datasets (zfs list)", "zfs list"),
        ("LVM Volume Groups (vgs)", "vgs"),
        ("LVM Logical Volumes (lvs)", "lvs"),
        ("Top level directories size on root (du -xhd 1 /)", "du -xhd 1 / | sort -h"),
        ("Proxmox local storage dump (vz)", "du -xhd 1 /var/lib/vz | sort -h"),
        ("Systemd Journal size", "journalctl --disk-usage"),
        ("Top 20 largest files on root filesystem (>100M)", "find / -xdev -type f -size +100M -exec du -h {} + 2>/dev/null | sort -rh | head -n 20"),
        ("Proxmox VM List", "qm list"),
        ("Proxmox Container List", "pct list")
    ]
    
    for title, cmd in commands:
        print("="*60)
        print(f" COMMAND: {title} ({cmd})")
        print("="*60)
        try:
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
            out = stdout.read().decode('utf-8', errors='replace')
            err = stderr.read().decode('utf-8', errors='replace')
            if out.strip():
                print(out)
            if err.strip():
                print("ERROR/STDERR:")
                print(err)
        except Exception as e:
            print(f"Failed to execute command: {e}")
        print("\n")
        
    ssh.close()

if __name__ == "__main__":
    run_remote_commands("192.168.86.57", 22, "root", "Malhi5$2")
