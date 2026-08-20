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
        ("Check fstab", "cat /etc/fstab"),
        ("Check systemd mount files", "systemctl list-units --type=mount | grep -E 'lums|cloud' || echo 'No systemd mount units matching lums or cloud'"),
        ("Check rclone or other sync processes", "ps aux | grep -E 'rclone|mount|nfs|smb' | grep -v grep || echo 'No matching processes'")
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
