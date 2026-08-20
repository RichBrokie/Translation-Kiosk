# Comprehensive Zorin OS Optimization Plan

Your system is already in decent shape (xanmod kernel, ananicy-cpp, zram, tlp, psd, powertop, bbr). Below are the remaining optimizations I can apply, grouped by impact.

## System Audit Summary

| Component | Current | Status |
|---|---|---|
| Kernel | xanmod 6.19.11 | ✅ Great |
| CPU Governor | performance (AC) | ✅ Good |
| I/O Scheduler | none (NVMe) | ✅ Optimal |
| Swappiness | 10 | ✅ Good |
| zram | 9.6GB | ✅ Good |
| TCP | bbr + fq_codel | ✅ Great |
| ananicy-cpp | active | ✅ Great |
| TLP | active | ⚠️ Needs tuning |
| Boot time | 8s to desktop | ⚠️ Can improve |
| Btrfs mount opts | missing `noatime`, `commit=120` | ⚠️ Needs tuning |
| VM tuning | defaults | ⚠️ Needs tuning |
| Hyper-V services | 3 running | ❌ Wasteful on bare metal |

---

## Proposed Changes

### 1. Sysctl — Memory & Network Tuning
Create `/etc/sysctl.d/99-performance.conf` with CachyOS-inspired tweaks:

- `vm.dirty_bytes` / `vm.dirty_background_bytes` — use fixed byte values for more predictable write-back on your 20GB RAM system
- `vm.compaction_proactiveness=0` — stop proactive memory compaction (wastes CPU)
- `vm.watermark_boost_factor=0` — disable watermark boosting (unnecessary with zram)
- `vm.page-cluster=0` — read single pages from swap since zram is instant
- `vm.watermark_scale_factor=125` — reclaim memory earlier to avoid stalls
- `net.ipv4.tcp_fastopen=3` — enable TCP Fast Open for both client and server
- `kernel.split_lock_mitigate=0` — avoid performance penalty from split-lock mitigation

> [!IMPORTANT]
> All of these are used by CachyOS and are well-tested on desktop systems. They are safe and reversible.

---

### 2. Boot Speed — Disable Unnecessary Services
These services are wasting boot time and running resources on your laptop:

| Service | Why disable | Boot savings |
|---|---|---|
| `hv-fcopy-daemon` | Hyper-V only, useless on bare metal | ~50ms |
| `hv-kvp-daemon` | Hyper-V only | ~50ms |
| `hv-vss-daemon` | Hyper-V only | ~50ms |
| `NetworkManager-wait-online` | Blocks boot for network, unnecessary for desktop | **~4.5s** |
| `fwupd` | Firmware updater, can run on-demand only | **~2.7s** |
| `gnome-remote-desktop` | Remote desktop server, unlikely needed | ~150ms |
| `ModemManager` | Cellular modem support, not needed on WiFi-only laptop | ~100ms |
| `openvpn` | VPN daemon, should start on-demand | ~50ms |
| `kerneloops` | Sends kernel crash reports to Ubuntu — optional | ~50ms |

> [!WARNING]
> I will **mask** (not delete) these services. You can re-enable any of them at any time with `systemctl unmask <service>`.

---

### 3. GRUB — Faster Boot + Kernel Params
- Set `GRUB_TIMEOUT=0` (you have a single OS, no need to wait 10 seconds)
- Add `nowatchdog` to kernel params (saves power, you already have nmi_watchdog=0)
- Add `nmi_watchdog=0` to make it persistent
- Add `mitigations=off` — **only if you accept the trade-off**: disables Spectre/Meltdown mitigations for a noticeable CPU speed boost (~5-15% depending on workload)

> [!CAUTION]
> `mitigations=off` gives a real speed boost but reduces security against CPU side-channel attacks. On a personal laptop this is generally acceptable. **Let me know if you want this or not.**

---

### 4. Btrfs — Filesystem Optimization
Update `/etc/fstab` to add missing mount options:
- `noatime` — stop updating file access timestamps (reduces writes significantly)
- `commit=120` — flush data every 120s instead of 30s (reduces disk activity, data is still safe in RAM)

---

### 5. TLP — Battery Refinements
Your TLP config is good but missing some useful settings:
- `PCIE_ASPM_ON_BAT=powersupersave` — aggressive PCIe power saving on battery
- `WIFI_PWR_ON_BAT=on` — enable WiFi power management on battery
- `RUNTIME_PM_ON_BAT=auto` — enable runtime PM for all devices on battery

---

### 6. Snap Cleanup
Slack is your only user-facing snap. The rest are dependencies. Nothing to remove here, but I can set snap refresh to only happen weekly instead of 4x daily to reduce background activity.

---

## Open Questions

1. **`mitigations=off`** — Do you want the CPU speed boost at the cost of reduced Spectre/Meltdown protection? On a personal laptop this is generally fine.
2. **Do you use OpenVPN?** If not, I'll disable the service.
3. **Do you ever use GNOME Remote Desktop?** If not, I'll disable it.
4. **Do you have a dual-boot setup?** If GRUB_TIMEOUT=0, you won't see the GRUB menu (can still hold Shift to access it).

## Verification Plan

### Automated Tests
- `systemd-analyze` before/after to measure boot time improvement
- `sysctl -a | grep` to confirm all values applied
- `mount | grep btrfs` to verify new mount options
- Full reboot test to confirm everything works
