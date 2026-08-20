import paramiko

HOST = "192.168.86.57"
USER = "root"
PASS = "Malhi5$2"

def fix():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=10)

    stdin, stdout, stderr = client.exec_command("pct exec 103 -- cat /root/updater.py")
    script = stdout.read().decode()

    # Make get_state return 'unknown' if it's 'unavailable' to avoid NaN in Javascript
    new_func = """def get_state(entity_id):
    try:
        response = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=HEADERS, timeout=5)
        val = response.json().get("state", "unknown")
        if val == "unavailable": return "unknown"
        return val
    except Exception as e:
        return "unknown"
"""
    
    # We replace the old get_state function
    # It currently looks like:
    # def get_state(entity_id):
    #     try:
    #         response = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=HEADERS, timeout=5)
    #         return response.json().get("state", "0")
    #     except Exception as e:
    #         return "0"

    import re
    script = re.sub(r'def get_state\(entity_id\):.*?return "0"', new_func.strip(), script, flags=re.DOTALL)

    sftp = client.open_sftp()
    with sftp.file('/tmp/updater.py', 'w') as f:
        f.write(script)
    sftp.close()

    client.exec_command("pct push 103 /tmp/updater.py /root/updater.py")
    client.exec_command("pct exec 103 -- pkill -f updater.py")
    client.exec_command("pct exec 103 -- bash -c 'nohup python3 /root/updater.py > /dev/null 2>&1 &'")

    client.close()
    print("Updater fixed to prevent NaN!")

if __name__ == "__main__":
    fix()
