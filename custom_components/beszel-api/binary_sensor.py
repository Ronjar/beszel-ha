from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # Get systems from coordinator data
    systems = coordinator.data['systems']

    for system in systems:
        entities.append(BeszelStatusBinarySensor(coordinator, system))
    async_add_entities(entities)

class BeszelStatusBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, system):
        super().__init__(coordinator)
        self._system_id = system.id

    @property
    def system(self):
        systems = self.coordinator.data['systems']
        for s in systems:
            if s.id == self._system_id:
                return s
        return None

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_status"

    @property
    def name(self):
        return f"{self.system.name} Status" if self.system else None

    @property
    def is_on(self):
        return self.system.status == "up" if self.system else False

    @property
    def device_class(self):
        return "connectivity"

    @property
    def device_info(self):
        sys = self.system
        if sys is None:
            return None
        info = getattr(sys, "info", {})
        return {
            "identifiers": {(DOMAIN, sys.id)},
            "name": sys.name,
            "manufacturer": "Beszel",
            "model": info.get("m"),
            "sw_version": info.get("v"),
            "hw_version": info.get("k"),
        }
