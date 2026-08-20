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
        ("Onedrive logs", "pct exec 105 -- journalctl -u onedrive@root -n 100 --no-pager"),
        ("Onedrive config status", "pct exec 105 -- onedrive --display-config"),
        ("Check disk space inside container 105", "pct exec 105 -- df -h")
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
