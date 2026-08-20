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
        ("Container status", "pct status 105"),
        ("Processes in container 105", "pct exec 105 -- ps aux"),
        ("Systemd services in container 105", "pct exec 105 -- systemctl list-units --type=service --state=running"),
        ("Check if braunegg onedrive client is installed", "pct exec 105 -- which onedrive || echo 'no onedrive binary'"),
        ("Check onedrive status/config", "pct exec 105 -- onedrive --display-config 2>/dev/null || echo 'not braunegg onedrive'"),
        ("Check onedrive systemd log", "pct exec 105 -- journalctl -u onedrive -n 50 --no-pager || echo 'no onedrive journal'")
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
