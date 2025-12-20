import asyncio
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL, UPDATE_INTERVAL, LOGGER
from .api import BeszelApiClient

PLATFORMS = ["sensor", "binary_sensor"]

async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})

    url = entry.data[CONF_URL]
    username = entry.data.get(CONF_USERNAME, None)
    password = entry.data.get(CONF_PASSWORD, None)
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)
    client = BeszelApiClient(url, username, password, verify_ssl)

    async def async_update_data():
        try:
            systems = await hass.async_add_executor_job(client.get_systems)

            if not systems:
                LOGGER.warning("No systems found in Beszel API")
                return {"systems": [], "stats": {}}

            # Create a stats dictionary to store stats by system ID
            stats_data = {}

            # Fetch system stats for each system
            for system in systems:
                try:
                    stats = await hass.async_add_executor_job(client.get_system_stats, system.id)
                    if stats:
                        # Store stats in the stats dictionary
                        stats_data[system.id] = stats.stats if hasattr(stats, 'stats') else {}
                    else:
                        stats_data[system.id] = {}
                except Exception as e:
                    LOGGER.warning(f"Failed to fetch stats for system {system.id}: {e}")
                    stats_data[system.id] = {}

            return {"systems": systems, "stats": stats_data}
        except Exception as err:
            LOGGER.error(f"Error fetching systems: {err}")
            raise UpdateFailed(f"Error fetching systems: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name="Beszel API",
        update_method=async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as e:
        LOGGER.error(f"Failed to initialize coordinator: {e}")
        raise

    hass.data[DOMAIN][entry.entry_id] = coordinator

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as e:
        LOGGER.error(f"Failed to setup platforms: {e}")
        raise
    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
