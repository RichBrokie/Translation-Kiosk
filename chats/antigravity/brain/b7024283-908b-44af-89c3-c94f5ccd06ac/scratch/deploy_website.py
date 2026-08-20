import paramiko

HOST = "192.168.86.57"
USER = "root"
PASS = "Malhi5$2"

# Read the local index.html
with open('/home/ahmad/.gemini/antigravity/brain/b7024283-908b-44af-89c3-c94f5ccd06ac/scratch/index.html', 'r') as f:
    index_html = f.read()

monitor_script = """import time
import re
import json
import subprocess
import sys

LOG_FILE = "/mnt/hdd/download.log"

def parse_tqdm(line):
    # Regex to catch percentage, eta, and speed in tqdm
    # e.g., 45%|████▍ | 1.2G/2.6G [00:15<00:10, 12MB/s]
    # Sometimes it's just percentages without all fields.
    match = re.search(r'(\d{1,3})%\|.*?\[.*?<(.*?), *(.*?)[\]\s]', line)
    if match:
        return {
            "percentage": match.group(1),
            "eta": match.group(2),
            "speed": match.group(3)
        }
    return None

def update_monitor():
    queue = [
        {"name": "Whisper large-v3-turbo", "status": "pending"},
        {"name": "Pyannote 3.1", "status": "pending"},
        {"name": "Qwen-2.5-72B-Instruct", "status": "pending"}
    ]
    
    current_model = "Waiting..."
    percentage = "0"
    eta = "--:--:--"
    speed = "-- MB/s"
    
    try:
        with open(LOG_FILE, 'r', errors='ignore') as f:
            # We split by \\r and \\n to get individual tqdm updates
            content = f.read()
            lines = re.split(r'[\\r\\n]+', content)
            
            for line in lines:
                if not line.strip(): continue
                
                if "Downloading Whisper large-v3-turbo" in line:
                    current_model = "Whisper v3"
                    queue[0]["status"] = "downloading"
                elif "Whisper Downloaded!" in line:
                    queue[0]["status"] = "done"
                
                if "Downloading Pyannote 3.1" in line:
                    current_model = "Pyannote 3.1"
                    queue[1]["status"] = "downloading"
                    queue[0]["status"] = "done"
                elif "Pyannote Downloaded!" in line:
                    queue[1]["status"] = "done"
                    
                if "Downloading Qwen-2.5-72B" in line:
                    current_model = "Qwen 72B (INT4)"
                    queue[2]["status"] = "downloading"
                    queue[0]["status"] = "done"
                    queue[1]["status"] = "done"
                elif "Qwen Downloaded!" in line:
                    queue[2]["status"] = "done"
                
                if "All base models downloaded successfully!" in line:
                    current_model = "All Downloads Complete!"
                    percentage = "100"
                    eta = "00:00"
                    speed = "0 MB/s"
                    for q in queue: q["status"] = "done"
                
                # Parse progress if we are downloading
                parsed = parse_tqdm(line)
                if parsed:
                    percentage = parsed["percentage"]
                    eta = parsed["eta"]
                    speed = parsed["speed"]
    except FileNotFoundError:
        pass
        
    data = {
        "current_model": current_model,
        "percentage": percentage,
        "eta": eta,
        "speed": speed,
        "queue": queue
    }
    
    with open('/tmp/download_stats.json', 'w') as f:
        json.dump(data, f)
        
    subprocess.run(["pct", "push", "103", "/tmp/download_stats.json", "/var/www/html/download_stats.json"])

if __name__ == "__main__":
    while True:
        update_monitor()
        time.sleep(2)
"""

def deploy():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=10)

    print("Deploying index.html to Proxmox temp...")
    sftp = client.open_sftp()
    
    # Save index.html to Proxmox
    with sftp.file('/tmp/new_index.html', 'w') as f:
        f.write(index_html)
        
    # Save monitor script to Proxmox
    with sftp.file('/opt/download_monitor.py', 'w') as f:
        f.write(monitor_script)
        
    sftp.close()

    print("Pushing index.html to Website LXC (103)...")
    client.exec_command("pct push 103 /tmp/new_index.html /var/www/html/index.html")
    
    print("Setting up monitor systemd service on Proxmox...")
    service_content = """[Unit]
Description=Download Monitor Sync
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/download_monitor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    client.exec_command(f"bash -c \"cat << 'EOF' > /etc/systemd/system/download-monitor.service\n{service_content}\nEOF\"")
    client.exec_command("systemctl daemon-reload")
    client.exec_command("systemctl enable download-monitor.service")
    client.exec_command("systemctl restart download-monitor.service")

    print("Deployment complete!")
    client.close()

if __name__ == "__main__":
    deploy()
