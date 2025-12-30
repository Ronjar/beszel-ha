import asyncio
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL, CONF_UPDATE_CHECK, UPDATE_INTERVAL, LOGGER
from .api import BeszelApiClient, BeszelUpdateApi

PLATFORMS = ["sensor", "binary_sensor", "update"]

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

    # Only create hub coordinator if update check is enabled
    update_check_enabled = entry.data.get(CONF_UPDATE_CHECK, False)
    coordinator_hub = None
    
    if update_check_enabled:
        update_api = BeszelUpdateApi(url)
        async def async_update_hub():
            try:
                return await hass.async_add_executor_job(update_api.get_update_info)
            except Exception as err:
                LOGGER.error(f"Error fetching hub update info: {err}")
                raise UpdateFailed(f"Error fetching hub update info: {err}")

        coordinator_hub = DataUpdateCoordinator(
            hass,
            LOGGER,
            name="Beszel Hub",
            update_method=async_update_hub,
            update_interval=timedelta(hours=1),
        )

    try:
        await coordinator.async_config_entry_first_refresh()
        if coordinator_hub is not None:
            await coordinator_hub.async_config_entry_first_refresh()
    except Exception as e:
        LOGGER.error(f"Failed to initialize coordinator: {e}")
        raise

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "hub": coordinator_hub,
        "update_check_enabled": update_check_enabled,
    }

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

async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry to the new version."""
    if config_entry.version == 1:
        new_data = {**config_entry.data}
        if CONF_VERIFY_SSL not in new_data:
            new_data[CONF_VERIFY_SSL] = True
        if CONF_UPDATE_CHECK not in new_data:
            new_data[CONF_UPDATE_CHECK] = False

        pass
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)

    return True