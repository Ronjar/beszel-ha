from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, LOGGER

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = []

    try:
        # Get systems from coordinator data
        systems = coordinator.data['systems']
        smart_devices_data = coordinator.data.get('smart_devices', {})

        for system in systems:
            try:
                # Add system status sensor
                entities.append(BeszelStatusBinarySensor(coordinator, system))
                
                # Create S.M.A.R.T. sensors for each disk
                system_smart_devices = smart_devices_data.get(system.id, [])
                for device in system_smart_devices:
                    entities.append(BeszelSmartBinarySensor(coordinator, system, device))
                    LOGGER.info(f"Created S.M.A.R.T. sensor for {system.name} - {device.get('name', 'unknown')}")

            except Exception as e:
                LOGGER.error(f"Failed to create binary sensors for system {system.name if hasattr(system, 'name') else 'unknown'}: {e}")
                continue

        LOGGER.info(f"Created {len(entities)} binary sensors total")
        async_add_entities(entities)
    except Exception as e:
        LOGGER.error(f"Failed to setup binary sensors: {e}")
        raise


class BeszelBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for Beszel binary sensors"""
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


class BeszelStatusBinarySensor(BeszelBaseBinarySensor):
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
        return BinarySensorDeviceClass.CONNECTIVITY


class BeszelSmartBinarySensor(BeszelBaseBinarySensor):
    """Binary sensor for disk S.M.A.R.T. status with all data in attributes"""
    
    def __init__(self, coordinator, system, device_data):
        super().__init__(coordinator, system)
        self._device_id = device_data.get('id', '')
        self._device_name = device_data.get('name', '')  # e.g., /dev/sda
        
        # Create clean disk name for entity ID (remove /dev/ prefix)
        self._disk_name = self._device_name.replace('/dev/', '')

    @property
    def _smart_device_data(self):
        """Get current S.M.A.R.T. data for this device from coordinator"""
        smart_devices = self.coordinator.data.get('smart_devices', {})
        system_devices = smart_devices.get(self._system_id, [])
        for device in system_devices:
            if device.get('id') == self._device_id:
                return device
        return {}

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_{self._disk_name}_smart"

    @property
    def name(self):
        device_data = self._smart_device_data
        model = device_data.get('model', self._disk_name)
        # Use short model name if available
        if model:
            # Take first part of model name
            short_model = model.split()[0] if ' ' in model else model
            return f"{self.system.name} {short_model} S.M.A.R.T." if self.system else None
        return f"{self.system.name} {self._disk_name} S.M.A.R.T." if self.system else None

    @property
    def is_on(self):
        """Return True if there's a problem (device_class PROBLEM shows 'on' when problem)"""
        device_data = self._smart_device_data
        if not device_data:
            return None
        
        state = device_data.get('state', '')
        # state is 'PASSED' or 'FAILED'
        return state != 'PASSED'

    @property
    def device_class(self):
        return BinarySensorDeviceClass.PROBLEM

    @property
    def icon(self):
        """Return icon based on status and disk type"""
        device_data = self._smart_device_data
        disk_type = device_data.get('type', '')
        
        if self.is_on:
            return "mdi:harddisk-remove"
        
        # Different icons for SSD vs HDD
        if 'nvme' in self._disk_name.lower() or disk_type == 'nvme':
            return "mdi:expansion-card"
        return "mdi:harddisk"

    @property
    def extra_state_attributes(self):
        """Return all S.M.A.R.T. data as attributes"""
        device_data = self._smart_device_data
        if not device_data:
            return {}

        attributes = {}
        
        # Temperature
        temp = device_data.get('temp')
        if temp is not None:
            attributes['temperature'] = temp
            attributes['temperature_unit'] = '°C'
        
        # Capacity (convert bytes to GB)
        capacity = device_data.get('capacity', 0)
        if capacity:
            attributes['capacity_gb'] = round(capacity / (1024**3), 2)
            attributes['capacity_tb'] = round(capacity / (1024**4), 2)
        
        # Power on hours
        hours = device_data.get('hours')
        if hours is not None:
            attributes['power_on_hours'] = hours
            attributes['power_on_days'] = round(hours / 24, 1)
        
        # Power cycles
        cycles = device_data.get('cycles')
        if cycles is not None:
            attributes['power_cycles'] = cycles
        
        # Device info
        model = device_data.get('model')
        if model:
            attributes['model'] = model
        
        serial = device_data.get('serial')
        if serial:
            attributes['serial'] = serial
        
        firmware = device_data.get('firmware')
        if firmware:
            attributes['firmware'] = firmware
        
        disk_type = device_data.get('type')
        if disk_type:
            attributes['type'] = disk_type
        
        # Device path
        attributes['device'] = self._device_name
        
        # Health state
        state = device_data.get('state', '')
        attributes['health_state'] = state

        return attributes
