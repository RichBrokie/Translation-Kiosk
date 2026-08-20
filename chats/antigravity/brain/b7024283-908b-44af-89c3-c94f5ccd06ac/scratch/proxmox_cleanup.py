import paramiko

HOST = "192.168.86.57"
USER = "root"
PASS = "Malhi5$2"

def cleanup():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=10)

    print("Cleaning up old vmbr1 NAT bridge if it exists...")
    client.exec_command("ip link set dev vmbr1 down")
    client.exec_command("ip link delete vmbr1 type bridge")
    
    print("Cleaning up iptables rule...")
    client.exec_command("iptables -t nat -D POSTROUTING -s 10.10.10.0/24 -o vmbr0 -j MASQUERADE")
    
    client.close()

if __name__ == "__main__":
    cleanup()
