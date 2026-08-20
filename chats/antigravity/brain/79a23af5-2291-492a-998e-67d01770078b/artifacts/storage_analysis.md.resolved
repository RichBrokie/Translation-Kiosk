# Proxmox Storage Usage Analysis & Resolution

The Proxmox root filesystem (`/dev/mapper/pve-root`) was at **100% capacity** (65GB used / 68GB total). This has been resolved. The disk usage is now at **60% capacity** (39GB used / 26GB free).

Below is the detailed breakdown of the diagnostics and the actions that were successfully applied to clean up and prevent this issue from recurring.

---

## 📊 Storage Breakdown (Before and After)

| Component | Size (Before) | Size (After) | Action Taken |
| :--- | :---: | :---: | :--- |
| `/var/lib/vz/dump/` (Local Backups) | **41.0 GB** | **17.9 GB** | Deleted 42 old backup files/directories (retaining the most recent 2 backup runs from May 29 & 31). |
| `/mnt/lums-cloud/dump/` (OneDrive Backups) | **7.0 GB** | **1.8 GB** | Deleted 15 old backup files from April 18 (which have already synced to OneDrive). |
| `/var/log/journal/` (Systemd Logs) | **2.6 GB** | **0.4 GB** | Vacuumed logs to a maximum of 500MB. |
| `/var/lib/vz/template/iso/` (Windows ISO) | **5.5 GB** | **5.5 GB** | Kept intact as it is currently attached to the stopped VM 104 (`win11`). |
| **Total Root Disk Space Free** | **0 GB** | **26 GB** | **~26 GB of disk space successfully reclaimed.** |

---

## 🔧 Applied Configuration Changes

To prevent the root filesystem from filling up again, the backup job definitions in `/etc/pve/jobs.cfg` have been modified:

### 1. Local Backup Job (`backup-b0ca3ea1-ea8a`)
* **Schedule**: Changed from `*/4:00` (every 4 hours) to `daily`.
* **Retention Policy**: Changed from keeping up to 12 backups (`keep-daily=3,keep-last=6,keep-monthly=1,keep-weekly=2`) to keeping only the **last 3 backups** (`keep-last=3`).
* **Why**: Running every 4 hours and keeping 12 backups of large VMs (~5.86GB per backup set) was guaranteed to exceed the 68GB disk space capacity. Changing to daily runs and keeping 3 backups ensures space utilization stays well within limits.

### 2. OneDrive Backups (`backup-db2342ea-22cd`)
* **Retention Policy**: Reduced from `keep-last=6` to `keep-last=3`.
* **Why**: Because the `onedrive` sync container bind-mounts this local folder to sync it to the cloud, these backups occupy space on the host root partition until they are pruned. Pruning after 3 copies prevents them from accumulating too much local space.

---

## ✅ System Status
* **Root filesystem**: `/dev/mapper/pve-root` is healthy at **60% utilization**.
* **Backup service configuration**: Successfully updated and saved.
* **OneDrive sync client**: Active and syncing inside Container 105.
