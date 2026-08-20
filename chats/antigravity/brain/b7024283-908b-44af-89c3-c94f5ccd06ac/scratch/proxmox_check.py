import paramiko

def run_ssh_cmd(host, user, password, cmd):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=user, password=password, timeout=10)
        stdin, stdout, stderr = client.exec_command(cmd)
        print(f"--- OUTPUT for {cmd} ---")
        print(stdout.read().decode())
        client.close()
    except Exception as e:
        print(f"Failed: {e}")

run_ssh_cmd("192.168.86.57", "root", "Malhi5$2", "lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT")
run_ssh_cmd("192.168.86.57", "root", "Malhi5$2", "blkid")
