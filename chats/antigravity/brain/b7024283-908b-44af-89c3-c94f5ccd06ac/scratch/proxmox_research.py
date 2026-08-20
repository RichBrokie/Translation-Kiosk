import paramiko

HOST = "192.168.86.57"
USER = "root"
PASS = "Malhi5$2"

def research():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=10)

    print("--- Listing LXC Containers ---")
    stdin, stdout, stderr = client.exec_command("pct list")
    print(stdout.read().decode())

    # Try to find web servers
    print("--- Looking for web servers in running containers ---")
    stdin, stdout, stderr = client.exec_command("pct list | awk 'NR>1 && $2==\"running\" {print $1}'")
    running_vms = stdout.read().decode().strip().split('\n')
    
    for vmid in running_vms:
        if not vmid: continue
        print(f"Checking VMID {vmid} for nginx/apache/lighttpd...")
        stdin, stdout, stderr = client.exec_command(f"pct exec {vmid} -- systemctl is-active nginx apache2 lighttpd 2>/dev/null")
        print(f"VMID {vmid} output: {stdout.read().decode().strip()} {stderr.read().decode().strip()}")
        
        # Check standard web roots
        stdin, stdout, stderr = client.exec_command(f"pct exec {vmid} -- ls /var/www/html 2>/dev/null")
        web_files = stdout.read().decode().strip()
        if web_files:
            print(f"Found files in /var/www/html on VMID {vmid}:\n{web_files}")
            
    client.close()

if __name__ == "__main__":
    research()
