import paramiko
import sys
import re

def execute_actions(host, port, username, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, port=port, username=username, password=password, timeout=10)
        print("Connected to Proxmox successfully!\n")
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)

    # 1. Vacuum Systemd Journal
    print("="*60)
    print("Action 1: Vacuuming Systemd Journal...")
    print("="*60)
    stdin, stdout, stderr = ssh.exec_command("journalctl --vacuum-size=500M")
    print(stdout.read().decode('utf-8', errors='replace'))
    print(stderr.read().decode('utf-8', errors='replace'))

    # 2. Cleanup old backups (older than 2026-05-29)
    print("="*60)
    print("Action 2: Cleaning up old backups (older than 2026-05-29)...")
    print("="*60)
    
    cleanup_dirs = ["/var/lib/vz/dump", "/mnt/lums-cloud/dump"]
    date_regex = re.compile(r'(\d{4})_(\d{2})_(\d{2})')
    
    for d in cleanup_dirs:
        print(f"Scanning directory: {d}")
        # List files
        stdin, stdout, stderr = ssh.exec_command(f"ls -1 {d}")
        files = stdout.read().decode('utf-8', errors='replace').splitlines()
        
        deleted_count = 0
        deleted_size = 0
        
        for f in files:
            if not f.startswith("vzdump-"):
                continue
            
            match = date_regex.search(f)
            if match:
                year, month, day = map(int, match.groups())
                file_date = (year, month, day)
                # If date is before 2026-05-29
                if file_date < (2026, 5, 29):
                    # Get size before deleting
                    stdin_s, stdout_s, stderr_s = ssh.exec_command(f"du -sh {d}/{f}")
                    size_info = stdout_s.read().decode('utf-8', errors='replace').split()
                    size_str = size_info[0] if size_info else "unknown"
                    
                    print(f"Deleting: {f} (Size: {size_str})")
                    # Delete the file or directory
                    ssh.exec_command(f"rm -rf {d}/{f}")
                    deleted_count += 1
                    
        print(f"Cleaned up {deleted_count} files/directories in {d}.\n")

    # 3. Modify jobs.cfg
    print("="*60)
    print("Action 3: Updating Proxmox Backup Schedules & Retention...")
    print("="*60)
    
    # Read current jobs.cfg
    stdin, stdout, stderr = ssh.exec_command("cat /etc/pve/jobs.cfg")
    jobs_cfg = stdout.read().decode('utf-8', errors='replace')
    
    print("Original /etc/pve/jobs.cfg:")
    print(jobs_cfg)
    print("-" * 40)
    
    # Modify backup-b0ca3ea1-ea8a (local job)
    # 1. schedule */4:00 -> schedule daily
    # 2. prune-backups keep-daily=3,keep-last=6,keep-monthly=1,keep-weekly=2 -> prune-backups keep-last=3
    modified_cfg = jobs_cfg
    
    # Let's perform precise replacements
    # 1. Local backup job schedule
    local_job_sec = re.search(r'(vzdump: backup-b0ca3ea1-ea8a\s+(?:[^\n]+\n)+)', modified_cfg)
    if local_job_sec:
        orig_sec = local_job_sec.group(1)
        new_sec = orig_sec
        new_sec = re.sub(r'schedule \*/4:00', 'schedule daily', new_sec)
        new_sec = re.sub(r'prune-backups [^\n]+', 'prune-backups keep-last=3', new_sec)
        modified_cfg = modified_cfg.replace(orig_sec, new_sec)
        
    # Modify backup-db2342ea-22cd (offsite job)
    # 1. prune-backups keep-last=6 -> prune-backups keep-last=3
    offsite_job_sec = re.search(r'(vzdump: backup-db2342ea-22cd\s+(?:[^\n]+\n)+)', modified_cfg)
    if offsite_job_sec:
        orig_sec = offsite_job_sec.group(1)
        new_sec = orig_sec
        new_sec = re.sub(r'prune-backups [^\n]+', 'prune-backups keep-last=3', new_sec)
        modified_cfg = modified_cfg.replace(orig_sec, new_sec)

    print("Modified /etc/pve/jobs.cfg:")
    print(modified_cfg)
    print("-" * 40)
    
    # Write back to Proxmox
    # To do this safely, we can write the modified_cfg to a temp file on host and then mv it over
    # Escape quotes and write
    import tempfile
    
    # Write config via SFTP or simple echo. Let's use SFTP for reliability.
    sftp = ssh.open_sftp()
    try:
        with sftp.file('/etc/pve/jobs.cfg', 'w') as f:
            f.write(modified_cfg)
        print("Successfully updated /etc/pve/jobs.cfg via SFTP!")
    except Exception as e:
        print(f"SFTP write failed: {e}. Trying command-line write...")
        # Fallback to echo
        escaped_cfg = modified_cfg.replace("'", "'\\''")
        stdin, stdout, stderr = ssh.exec_command(f"echo '{escaped_cfg}' > /etc/pve/jobs.cfg")
        err_msg = stderr.read().decode('utf-8')
        if err_msg.strip():
            print(f"Command-line write failed: {err_msg}")
        else:
            print("Successfully updated /etc/pve/jobs.cfg via fallback!")
    sftp.close()

    # 4. Show final disk space
    print("="*60)
    print("Final Disk Space Status:")
    print("="*60)
    stdin, stdout, stderr = ssh.exec_command("df -hT /")
    print(stdout.read().decode('utf-8'))

    ssh.close()

if __name__ == "__main__":
    execute_actions("192.168.86.57", 22, "root", "Malhi5$2")
