from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, LOGGER

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    hub_coordinator = data["hub"]
    
    if hub_coordinator is None:
        LOGGER.debug("Update check is disabled, skipping Beszel Hub Update entity")
        return
    
    async_add_entities([BeszelHubUpdate(hub_coordinator, entry.entry_id, entry.data.get("url"))])

class BeszelHubUpdate(CoordinatorEntity, UpdateEntity):
    def __init__(self, coordinator, entry_id: str, base_url: str):
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._base_url = base_url.rstrip("/") if base_url else base_url

    @property
    def unique_id(self):
        return f"beszel_hub_update_{self._entry_id}"

    @property
    def name(self):
        return "Beszel Hub Update"

    @property
    def installed_version(self):
        return self.coordinator.data.get("hub_version")

    @property
    def latest_version(self):
        return self.coordinator.data.get("latest_version")

    @property
    def release_url(self):
        return self.coordinator.data.get("latest_release_url")

    @property
    def in_progress(self) -> bool:
        return False

    @property
    def supported_features(self) -> int:
        return UpdateEntityFeature(0)

    @property
    def device_info(self):
        hub = self.coordinator.data
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Beszel Hub",
            "manufacturer": "Beszel",
            "sw_version": hub.get("hub_version"),
        }