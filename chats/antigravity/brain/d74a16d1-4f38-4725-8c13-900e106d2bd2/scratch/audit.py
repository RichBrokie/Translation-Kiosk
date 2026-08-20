import paramiko
import json
import os
import sys

host = "192.168.86.41"
username = "hassio"
password = "Malhi5$2"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting to SSH...")
client.connect(host, username=username, password=password, timeout=10)
print("Connected!")

def run_cmd(cmd, use_sudo=False):
    if use_sudo:
        full_cmd = f"echo '{password}' | sudo -S {cmd}"
    else:
        full_cmd = cmd
    stdin, stdout, stderr = client.exec_command(full_cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    err_filtered = "\n".join([line for line in err.splitlines() if "[sudo] password for" not in line])
    return out, err_filtered

results = {}

# 1. DISK USAGE
out, err = run_cmd("df -h")
results["1. DISK USAGE"] = out or err

# 2. DOCKER CONTAINERS
out, err = run_cmd("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Size}}'", use_sudo=True)
results["2. DOCKER CONTAINERS"] = out or err

# 3. HA VERSION
out, err = run_cmd("docker exec homeassistant python3 -m homeassistant --version", use_sudo=True)
if not out.strip() or "No module named" in out:
    out, err = run_cmd("docker inspect --format '{{.Config.Image}}' homeassistant", use_sudo=True)
results["3. HA VERSION"] = out.strip() or err.strip()

# 4. ADDONS LIST
out, err = run_cmd("docker ps -a", use_sudo=True)
results["4. ADDONS LIST"] = out or err

# 5. INTEGRATIONS
out, err = run_cmd("docker exec homeassistant cat /config/.storage/core.config_entries", use_sudo=True)
integrations_str = ""
if out.strip():
    try:
        data = json.loads(out)
        entries = data.get("data", {}).get("entries", [])
        integrations_list = []
        for entry in entries:
            domain = entry.get("domain", "unknown")
            title = entry.get("title", "unknown")
            entry_id = entry.get("entry_id", "")
            integrations_list.append(f"- Domain: {domain} | Title: {title} (ID: {entry_id})")
        integrations_str = "\n".join(integrations_list)
    except Exception as e:
        integrations_str = f"Error parsing core.config_entries JSON: {e}\nRaw output:\n{out[:1000]}"
else:
    integrations_str = err
results["5. INTEGRATIONS"] = integrations_str

# 6. AUTOMATIONS
out, err = run_cmd("docker exec homeassistant head -n 200 /config/automations.yaml", use_sudo=True)
results["6. AUTOMATIONS"] = out or err

# 7. CUSTOM COMPONENTS
out, err = run_cmd("docker exec homeassistant ls -la /config/custom_components/", use_sudo=True)
results["7. CUSTOM COMPONENTS"] = out or err

# 8. DATABASE SIZE
out, err = run_cmd("docker exec homeassistant ls -lh /config/home-assistant_v2.db", use_sudo=True)
results["8. DATABASE SIZE"] = out or err

# 9. LOGS/ERRORS
out, err = run_cmd("docker logs --tail 50 homeassistant 2>&1", use_sudo=True)
lines = (out + err).splitlines()
error_warn_lines = [l for l in lines if "ERROR" in l or "WARNING" in l or "ERR" in l or "WARN" in l]
results["9. LOGS/ERRORS"] = "\n".join(error_warn_lines) if error_warn_lines else "No ERROR or WARNING lines found in last 50 log entries.\nRecent 20 logs:\n" + "\n".join(lines[-20:])

# 10. DASHBOARDS
out, err = run_cmd("docker exec homeassistant cat /config/.storage/lovelace_dashboards", use_sudo=True)
results["10. DASHBOARDS"] = out or err

# 11. GO2RTC CONFIG
out, err = run_cmd("docker exec homeassistant cat /config/go2rtc.yaml", use_sudo=True)
results["11. GO2RTC CONFIG"] = out or err

# 12. RECORDER CONFIG & 13. CONFIGURATION.YAML
out, err = run_cmd("docker exec homeassistant cat /config/configuration.yaml", use_sudo=True)
results["13. CONFIGURATION.YAML"] = out or err

recorder_lines = []
if out:
    in_recorder = False
    for line in out.splitlines():
        if line.strip().startswith("recorder:"):
            in_recorder = True
            recorder_lines.append(line)
        elif in_recorder:
            if line and not line.startswith(" ") and not line.startswith("\t") and not line.startswith("#"):
                in_recorder = False
            else:
                recorder_lines.append(line)
results["12. RECORDER CONFIG"] = "\n".join(recorder_lines) if recorder_lines else "No explicit 'recorder:' section found in configuration.yaml"

# 14. LEFTOVER FILES (wyoming, frigate)
out1, err1 = run_cmd("docker exec homeassistant find /config -name '*wyoming*' -o -name '*frigate*'", use_sudo=True)
out2, err2 = run_cmd("find / -name '*wyoming*' -o -name '*frigate*' 2>/dev/null | grep -v '/proc' | grep -v '/sys'", use_sudo=True)
results["14. LEFTOVER FILES"] = f"--- HA Config Search ---\n{out1 or 'None'}\n--- Host System Search ---\n{out2 or 'None'}"

# 15. MEMORY/CPU
out_mem, err_mem = run_cmd("free -h")
out_cpu, err_cpu = run_cmd("uptime")
results["15. MEMORY/CPU"] = f"Memory:\n{out_mem}\nUptime / CPU Load:\n{out_cpu}"

client.close()

# Format final output document
output_filepath = "/home/ahmad/antigravity/ha_audit_results.txt"
with open(output_filepath, "w") as f:
    f.write("=====================================================\n")
    f.write("       HOME ASSISTANT AUDIT DIAGNOSTIC REPORT        \n")
    f.write("=====================================================\n\n")

    for key, value in results.items():
        f.write(f"=====================================================\n")
        f.write(f"{key}\n")
        f.write(f"=====================================================\n")
        f.write(f"{value.strip() if value else 'N/A'}\n\n")

print(f"Audit completed successfully. Output saved to {output_filepath}")
