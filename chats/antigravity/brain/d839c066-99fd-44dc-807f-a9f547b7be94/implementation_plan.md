# Fix Home Assistant Energy Dashboard

The root cause of the negative values and incorrect data on your Energy Dashboard is that at **04:01 AM on August 2nd**, the inverter either restarted or disconnected, causing all its lifetime total sensors to briefly report `0`. 

Because these are `total_increasing` sensors, Home Assistant interpreted this drop to `0` as a meter replacement and reset their accumulated `sum` to zero. This caused you to lose all the historical accumulation from your statistics, leading to incorrect and negative calculations on the dashboard.

## Proposed Changes

### 1. Fix the Statistics Database
I will run a script to stop Home Assistant, safely back up your database, and apply an SQL fix to the `statistics` and `statistics_short_term` tables. 

This fix will find the exact point where each sensor reset to zero and add back the "lost" accumulated value (e.g., adding back the lost `1203.0 kWh` to your solar production) to all data points recorded since the reset.

The following sensors will be fixed:
- `sensor.inverter_total_production`
- `sensor.inverter_total_energy_import`
- `sensor.inverter_total_energy_export`
- `sensor.inverter_total_load_consumption`
- `sensor.inverter_total_energy`

### 2. Clean Up Energy Dashboard Configuration
Based on the extensive research into your solar entities, there are duplicate integrations providing data, and some are broken/stale:
- You currently have two Solar sources configured in the Energy dashboard: **"On-Grid Solar"** and **"Hybrid Production"**.
- **"On-Grid Solar"** uses `sensor.total_solar_production` (from the Shine Monitor integration). This sensor is currently stuck at `46.93 kWh` and its associated solar forecast integration was deleted from your system.
- **"Hybrid Production"** uses `sensor.inverter_total_production` (from the Solarman integration), which is actively and accurately reporting data.

I will update your Energy Dashboard configuration (`/config/.storage/energy`) to:
1. **Remove** the broken "On-Grid Solar" source to prevent duplicate/stuck data from showing up.
2. **Keep** "Hybrid Production" (Solarman) as your single source of truth for solar generation.
3. **Keep** "Hybrid Solar" as your grid import/export source using the Solarman entities (`sensor.inverter_total_energy_import` / `export`).

## User Review Required
Please review this plan. If you agree with removing the redundant "On-Grid Solar" (Shine Monitor) source from the dashboard and fixing the database sums, click **Proceed** and I will execute the fix.
