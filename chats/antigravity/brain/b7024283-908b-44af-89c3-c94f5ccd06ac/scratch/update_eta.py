import paramiko

HOST = "192.168.86.57"
USER = "root"
PASS = "Malhi5$2"

new_monitor_script = """import time
import re
import json
import subprocess
import sys
import math

LOG_FILE = "/mnt/hdd/download.log"
QWEN_TOTAL_BYTES = 41.6 * 1024 * 1024 * 1024  # 41.6 GB

def get_dir_size(path):
    try:
        out = subprocess.check_output(["du", "-sb", path]).decode()
        return int(out.split()[0])
    except Exception:
        return 0

def get_tx_bytes():
    try:
        with open('/sys/class/net/veth107i0/statistics/tx_bytes', 'r') as f:
            return int(f.read().strip())
    except Exception:
        return 0

def run_daemon():
    last_bytes = get_tx_bytes()
    last_time = time.time()
    
    while True:
        queue = [
            {"name": "Whisper large-v3-turbo", "status": "pending"},
            {"name": "Pyannote 3.1", "status": "pending"},
            {"name": "Qwen-2.5-72B-Instruct", "status": "pending"}
        ]
        
        current_model = "Waiting..."
        percentage = "0"
        eta = "--:--:--"
        
        try:
            with open(LOG_FILE, 'r', errors='ignore') as f:
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
                        for q in queue: q["status"] = "done"
        except FileNotFoundError:
            pass
            
        # Calculate real-time network speed for LXC 107
        current_bytes = get_tx_bytes()
        current_time = time.time()
        delta_bytes = current_bytes - last_bytes
        delta_time = current_time - last_time
        
        speed_mbps = 0.0
        if delta_time > 0:
            speed_mbps = (delta_bytes * 8) / (1_000_000 * delta_time) # Mbps
            speed = f"{speed_mbps:.1f} Mbps"
        else:
            speed = "0.0 Mbps"
            
        last_bytes = current_bytes
        last_time = current_time
        
        if current_model == "All Downloads Complete!":
            speed = "0.0 Mbps"
            
        # ELEGANT BYTE-BASED ETA CALCULATION FOR QWEN
        if current_model == "Qwen 72B (INT4)":
            downloaded = get_dir_size('/mnt/hdd/qwen2.5-72b-instruct-awq')
            percent = (downloaded / QWEN_TOTAL_BYTES) * 100
            percentage = str(min(99, int(percent)))
            
            if speed_mbps > 5.0: # Only calc ETA if downloading
                bytes_left = QWEN_TOTAL_BYTES - downloaded
                # speed in bytes per second
                bytes_per_sec = (speed_mbps * 1_000_000) / 8
                seconds_left = bytes_left / bytes_per_sec
                
                if seconds_left < 0: seconds_left = 0
                
                hours = int(seconds_left // 3600)
                minutes = int((seconds_left % 3600) // 60)
                seconds = int(seconds_left % 60)
                
                if hours > 0:
                    eta = f"{hours}h {minutes}m"
                else:
                    eta = f"{minutes}m {seconds}s"
            else:
                eta = "--:--:--"

        data = {
            "current_model": current_model,
            "percentage": percentage,
            "eta": eta,
            "speed": speed,
            "queue": queue
        }
        
        try:
            with open('/tmp/download_stats.json', 'w') as f:
                json.dump(data, f)
            subprocess.run(["pct", "push", "103", "/tmp/download_stats.json", "/var/www/html/download_stats.json"], check=False)
        except Exception:
            pass
            
        time.sleep(2)

if __name__ == "__main__":
    run_daemon()
"""

def deploy():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=10)

    sftp = client.open_sftp()
    with sftp.file('/opt/download_monitor.py', 'w') as f:
        f.write(new_monitor_script)
    sftp.close()

    print("Restarting download monitor service with elegant ETA tracking...")
    client.exec_command("systemctl restart download-monitor.service")
    
    print("Update complete!")
    client.close()

if __name__ == "__main__":
    deploy()
