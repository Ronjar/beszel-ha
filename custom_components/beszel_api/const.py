import logging

DOMAIN = "beszel_api"
CONF_URL = "url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_VERIFY_SSL = "verify_ssl"
CONF_UPDATE_INTERVAL = "update_interval"
LOGGER = logging.getLogger(__package__)

SMART_CURATED_ATTRIBUTES = frozenset({
    "ssd_life_left",
    "percentage_used",
    "wear_leveling_count",
    "media_wearout_indicator",
    "reallocated_sector_ct",
    "reallocated_event_count",
    "current_pending_sector",
    "offline_uncorrectable",
    "reported_uncorrect",
    "udma_crc_error_count",
    "sata_crc_error_count",
    "crc_error_count",
    "sata_phy_error_count",
    "seek_error_rate",
    "unsafe_shutdown_count",
    "unsafe_shutdowns",
    "flash_writes_gib",
    "lifetime_writes_gib",
    "lifetime_reads_gib",
    "data_units_written",
    "data_units_read",
    "total_lbas_written",
    "total_lbas_read",
    "average_erase_count",
    "max_erase_count",
    "total_erase_count",
    "load_cycle_count",
    "start_stop_count",
    "power_on_hours",
    "temperature_celsius",
})
