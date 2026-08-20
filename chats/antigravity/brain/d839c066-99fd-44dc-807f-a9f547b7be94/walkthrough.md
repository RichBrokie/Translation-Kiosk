# Energy Dashboard Fix Walkthrough

I have successfully resolved the issues causing negative and incorrect values to display on your Energy Dashboard.

## What Was Fixed

### 1. Database Statistics Repair
The root cause was identified: at exactly **04:01 AM on August 2nd**, a brief drop to `0` from the inverter's total lifetime sensors caused Home Assistant to think the meters were replaced. It incorrectly reset the accumulated totals (e.g., your total solar production dropped from ~1203 kWh to 0) which threw off all Energy Dashboard calculations moving forward.

To fix this:
- Stopped Home Assistant safely.
- Created a backup of the database (`/config/home-assistant_v2.db.bak_before_stats_fix`).
- Traced the exact reset timestamp for 6 critical lifetime sensors:
  - `sensor.inverter_total_production` (+1203.0 kWh)
  - `sensor.inverter_total_energy_import` (+3140.8 kWh)
  - `sensor.inverter_total_energy_export` (+216.0 kWh)
  - `sensor.inverter_total_load_consumption` (+4110.3 kWh)
  - `sensor.inverter_total_energy` (+1185.3 kWh)
  - `sensor.total_solar_production` (+4301.1 kWh)
- Added the "lost" accumulated values back into the `statistics` and `statistics_short_term` tables for all records following the reset.

### 2. Energy Dashboard Configuration Cleanup
You had two duplicate solar sources configured in your Energy Dashboard, and one of them was stale/broken.
- **Removed**: "On-Grid Solar" source. This was pointing to `sensor.total_solar_production` (from the Shine Monitor integration), which is currently stuck at 46.93 kWh. It was also pointing to a deleted Solcast forecast configuration.
- **Kept**: "Hybrid Production" source. This uses `sensor.inverter_total_production` from your active Solarman integration.

Home Assistant has been successfully restarted. The Energy Dashboard will now use the correct continuous historical data and solely rely on the active Solarman integration!

> [!TIP]
> The Energy Dashboard aggregates data hourly, so you may need to wait up to an hour or refresh the page to see the newly restored positive statistics populate on the graphs.
