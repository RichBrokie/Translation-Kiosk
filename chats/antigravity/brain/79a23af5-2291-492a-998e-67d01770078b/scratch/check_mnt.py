import paramiko
import sys

def run_remote_commands(host, port, username, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, port=port, username=username, password=password, timeout=10)
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)
        
    commands = [
        ("Mount status", "mount | grep -E 'lums|cloud' || echo 'No lums-cloud mount'"),
        ("Size of /mnt directories", "du -xhd 2 /mnt | sort -h"),
        ("Files in /mnt/lums-cloud/dump", "ls -lhR /mnt/lums-cloud/dump/ 2>/dev/null || echo 'No lums-cloud dump'"),
        ("Files in /var/lib/vz/dump", "ls -lh /var/lib/vz/dump"),
        ("Proxmox backup configuration", "cat /etc/pve/vzdump.cron || echo 'No vzdump.cron'"),
        ("Proxmox storage configuration", "cat /etc/pve/storage.cfg")
    ]
    
    with open("/home/ahmad/.gemini/antigravity/brain/79a23af5-2291-492a-998e-67d01770078b/scratch/diagnostic_output.txt", "w") as f:
        for title, cmd in commands:
            f.write("="*60 + "\n")
            f.write(f" COMMAND: {title} ({cmd})\n")
            f.write("="*60 + "\n")
            try:
                stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
                out = stdout.read().decode('utf-8', errors='replace')
                err = stderr.read().decode('utf-8', errors='replace')
                if out.strip():
                    f.write(out + "\n")
                if err.strip():
                    f.write("ERROR/STDERR:\n" + err + "\n")
            except Exception as e:
                f.write(f"Failed to execute command: {e}\n")
            f.write("\n\n")
        
    ssh.close()

if __name__ == "__main__":
    run_remote_commands("192.168.86.57", 22, "root", "Malhi5$2")
