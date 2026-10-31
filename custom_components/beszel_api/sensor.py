import re

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.icon import icon_for_battery_level

from .const import DOMAIN, LOGGER

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = []
    known_gpu_sensors = set()

    try:
        # Get systems and stats from coordinator data
        systems = coordinator.data['systems']
        stats_data = coordinator.data.get('stats', {})

        for system in systems:
            try:
                entities.append(BeszelCPUSensor(coordinator, system))
                entities.append(BeszelRAMSensor(coordinator, system))
                entities.append(BeszelRAMTotalSensor(coordinator, system))
                entities.append(BeszelDiskSensor(coordinator, system))
                entities.append(BeszelDiskTotalSensor(coordinator, system))
                entities.append(BeszelBandwidthSensor(coordinator, system))
                entities.append(BeszelNetworkReceiveSensor(coordinator, system))
                entities.append(BeszelNetworkSendSensor(coordinator, system))
                entities.append(BeszelUptimeSensor(coordinator, system))

                # Get stats for this system
                system_stats = stats_data.get(system.id, {})

                if system.info.get("dt") is not None:
                    entities.append(BeszelTemperatureSensor(coordinator, system))

                if system_stats and 'su' in system_stats:
                    entities.append(BeszelSWAPSensor(coordinator, system))

                entities.extend(_build_gpu_sensors(coordinator, system, known_gpu_sensors))

                # Create EFS sensors if EFS data is available
                if system_stats and 'efs' in system_stats and isinstance(system_stats['efs'], dict):
                    for disk_name in system_stats['efs'].keys():
                        entities.append(BeszelEFSDiskSensor(coordinator, system, disk_name))
                        entities.append(BeszelDiskTotalSensor(coordinator, system, disk_name))
                        LOGGER.info(f"Created EFS sensors for {system.name} - {disk_name}")

                # Create battery sensor if data is available
                if system_stats and 'bat' in system_stats and isinstance(system_stats['bat'], list):
                    entities.append(BeszelBatterySensor(coordinator, system))

            except Exception as e:
                LOGGER.error(f"Failed to create sensors for system {system.name if hasattr(system, 'name') else 'unknown'}: {e}")
                continue

        LOGGER.info(f"Created {len(entities)} sensors total")
        async_add_entities(entities)
    except Exception as e:
        LOGGER.error(f"Failed to setup sensors: {e}")
        raise

    @callback
    def _async_add_new_gpu_sensors():
        """Add sensors for GPUs (or GPU metrics) that appear after the initial setup."""
        if not coordinator.data:
            return
        new_entities = []
        for system in coordinator.data.get("systems", []):
            try:
                new_entities.extend(_build_gpu_sensors(coordinator, system, known_gpu_sensors))
            except Exception as e:
                LOGGER.error(f"Failed to create GPU sensors for system {getattr(system, 'name', 'unknown')}: {e}")
        if new_entities:
            LOGGER.info(f"Adding {len(new_entities)} new GPU sensors")
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_gpu_sensors))


def _get_gpu_stats(stats_data):
    gpus = (stats_data or {}).get("g")
    return gpus if isinstance(gpus, dict) else {}


def _get_gpu_temperature(stats_data, gpu_data):
    temperatures = (stats_data or {}).get("t")
    gpu_name = gpu_data.get("n")
    if not isinstance(temperatures, dict) or not gpu_name:
        return None
    return temperatures.get(gpu_name)


def _gpu_memory_percent(gpu_data):
    total = gpu_data.get("mt")
    if not total:
        return None
    return gpu_data.get("mu", 0) / total * 100


# Beszel omits zero values for "mu", "p" and "pp" (omitzero), so a missing key
# on a reported GPU means 0 once we know the GPU supports that metric.
GPU_METRICS = {
    "usage": {
        "label": "Usage",
        "icon": "mdi:expansion-card",
        "unit": "%",
        "precision": 1,
        "supported": lambda gpu, stats: True,
        "value": lambda gpu, stats: gpu.get("u"),
    },
    "memory_used": {
        "label": "VRAM Used",
        "icon": "mdi:memory",
        "unit": "MB",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "precision": 0,
        "supported": lambda gpu, stats: "mu" in gpu or "mt" in gpu,
        "value": lambda gpu, stats: gpu.get("mu", 0),
    },
    "memory_total": {
        "label": "VRAM Total",
        "icon": "mdi:memory",
        "unit": "MB",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "precision": 0,
        "supported": lambda gpu, stats: "mt" in gpu,
        "value": lambda gpu, stats: gpu.get("mt"),
    },
    "memory_percent": {
        "label": "VRAM Usage",
        "icon": "mdi:memory",
        "unit": "%",
        "precision": 1,
        "supported": lambda gpu, stats: "mt" in gpu,
        "value": lambda gpu, stats: _gpu_memory_percent(gpu),
    },
    "power": {
        "label": "Power",
        "icon": "mdi:flash",
        "unit": "W",
        "device_class": SensorDeviceClass.POWER,
        "precision": 2,
        "supported": lambda gpu, stats: "p" in gpu,
        "value": lambda gpu, stats: gpu.get("p", 0),
    },
    "power_package": {
        "label": "Package Power",
        "icon": "mdi:flash",
        "unit": "W",
        "device_class": SensorDeviceClass.POWER,
        "precision": 2,
        "supported": lambda gpu, stats: "pp" in gpu,
        "value": lambda gpu, stats: gpu.get("pp", 0),
    },
    "temperature": {
        "label": "Temperature",
        "unit": "°C",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "precision": 1,
        "supported": lambda gpu, stats: _get_gpu_temperature(stats, gpu) is not None,
        "value": lambda gpu, stats: _get_gpu_temperature(stats, gpu),
    },
}


def _build_gpu_sensors(coordinator, system, known_sensors):
    """Create sensors for every GPU (any number) reported in the latest system stats."""
    stats_data = coordinator.data.get("stats", {}).get(system.id, {}) or {}
    entities = []
    for gpu_key, gpu_data in _get_gpu_stats(stats_data).items():
        if not isinstance(gpu_data, dict):
            continue
        for metric, description in GPU_METRICS.items():
            marker = (system.id, str(gpu_key), metric)
            if marker in known_sensors or not description["supported"](gpu_data, stats_data):
                continue
            known_sensors.add(marker)
            entities.append(BeszelGPUSensor(coordinator, system, gpu_key, metric))
            LOGGER.debug(f"Created GPU {metric} sensor for {system.name} - GPU {gpu_key}")
    return entities

class BeszelBaseSensor(CoordinatorEntity, SensorEntity):
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
    def stats_data(self):
        return self.coordinator.data.get('stats', {}).get(self._system_id, {})

    @property
    def available(self):
        return super().available and self.system is not None

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

class BeszelCPUSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_cpu"

    @property
    def name(self):
        return f"{self.system.name} CPU" if self.system else None

    @property
    def icon(self):
        return "mdi:memory"

    @property
    def native_value(self):
        return self.system.info.get("cpu") if self.system else None

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelGPUSensor(BeszelBaseSensor):
    """A single metric of a single GPU. One instance is created per GPU and metric."""

    def __init__(self, coordinator, system, gpu_key, metric="usage"):
        super().__init__(coordinator, system)
        self._gpu_key = str(gpu_key)
        self._metric = metric
        self._description = GPU_METRICS[metric]

    @property
    def gpu_data(self):
        data = _get_gpu_stats(self.stats_data).get(self._gpu_key)
        return data if isinstance(data, dict) else None

    @property
    def gpu_name(self):
        gpu_data = self.gpu_data or {}
        return gpu_data.get("n") or f"GPU {self._gpu_key}"

    @property
    def unique_id(self):
        # The usage sensor keeps its original unique_id for backwards compatibility
        if self._metric == "usage":
            return f"beszel_{self._system_id}_gpu_{self._gpu_key}"
        return f"beszel_{self._system_id}_gpu_{self._gpu_key}_{self._metric}"

    @property
    def name(self):
        if not self.system:
            return None
        return f"{self.system.name} {self.gpu_name} {self._description['label']}"

    @property
    def icon(self):
        return self._description.get("icon")

    @property
    def available(self):
        if not super().available or self.gpu_data is None:
            return False
        if self._metric == "usage":
            return self.gpu_data.get("u") is not None
        return True

    @property
    def native_value(self):
        gpu_data = self.gpu_data
        if gpu_data is None:
            return None
        return self._description["value"](gpu_data, self.stats_data)

    @property
    def device_class(self):
        return self._description.get("device_class")

    @property
    def native_unit_of_measurement(self):
        return self._description["unit"]

    @property
    def suggested_display_precision(self):
        return self._description.get("precision")

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        gpu_data = self.gpu_data or {}
        attributes = {
            "gpu_id": self._gpu_key,
            "gpu_name": self.gpu_name,
        }
        if self._metric != "usage":
            return attributes

        attributes["gpu_vram_mb"] = gpu_data.get("mt")

        gpu_memory_used = gpu_data.get("mu")
        if gpu_memory_used is not None:
            attributes["gpu_memory_used_mb"] = gpu_memory_used

        gpu_power = gpu_data.get("p")
        if gpu_power is not None:
            attributes["gpu_power_w"] = gpu_power

        engines = gpu_data.get("e")
        if isinstance(engines, dict):
            for engine, value in engines.items():
                attributes[f"engine_{re.sub(r'[^a-z0-9]+', '_', engine.lower()).strip('_')}"] = value

        return attributes


class BeszelRAMSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_ram"

    @property
    def name(self):
        return f"{self.system.name} RAM" if self.system else None

    @property
    def icon(self):
        return "mdi:chip"

    @property
    def native_value(self):
        return self.system.info.get("mp") if self.system else None

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        """Total and Used RAM in GB"""

        attributes = {}
        attributes['ram_used_gb'] = self.stats_data.get("mu")
        attributes['ram_total_gb'] = self.stats_data.get("m")

        return attributes

class BeszelSWAPSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_swap"

    @property
    def name(self):
        return f"{self.system.name} SWAP" if self.system else None

    @property
    def icon(self):
        return "mdi:chip"
    
    @property
    def available(self):
        if not super().available:
            return False
        swap_used = self.stats_data.get("su")
        swap_total = self.stats_data.get("s")
        return swap_used is not None and swap_total is not None and swap_total > 0

    @property
    def native_value(self):
        swap_used = self.stats_data.get("su")
        swap_total = self.stats_data.get("s")
        if self.available:
            return (swap_used / swap_total * 100)
        return None

    @property
    def native_unit_of_measurement(self):
        return "%"
    
    @property
    def suggested_display_precision(self):
        return 2

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        """Total and Used SWAP in GB"""

        attributes = {}
        attributes['swap_used_gb'] = self.stats_data.get("su")
        attributes['swap_total_gb'] = self.stats_data.get("s")

        return attributes


class BeszelDiskSensor(BeszelBaseSensor):

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_disk"

    @property
    def name(self):
        return f"{self.system.name} Disk" if self.system else None

    @property
    def icon(self):
        return "mdi:harddisk"

    @property
    def native_value(self):
        return self.system.info.get("dp") if self.system else None

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        """Total and Used DISK in GB"""

        attributes = {}
        attributes['disk_used_gb'] = self.stats_data.get("du")
        attributes['disk_total_gb'] = self.stats_data.get("d")

        return attributes


class BeszelBandwidthSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_bandwidth"

    @property
    def name(self):
        return f"{self.system.name} Bandwidth" if self.system else None

    @property
    def icon(self):
        return "mdi:router-network"
    
    @property
    def available(self):
        if not super().available:
            return False
        bandwidth = self.system.info.get("bb") if self.system else None
        return bandwidth is not None

    @property
    def native_value(self):
        bandwidth = self.system.info.get("bb") if self.system else None
        return bandwidth / 1024000 if bandwidth is not None else None

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_RATE

    @property
    def native_unit_of_measurement(self):
        return "MB/s"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT
    
    @property
    def suggested_display_precision(self):
        return 8


class BeszelNetworkReceiveSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_network_receive"

    @property
    def name(self):
        return f"{self.system.name} Network Receive" if self.system else None

    @property
    def icon(self):
        return "mdi:download-network"

    @property
    def native_value(self):
        b_data = self.stats_data.get("b")
        return b_data[1] / 1024 if self.system and b_data else None

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_RATE

    @property
    def native_unit_of_measurement(self):
        return "kB/s"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self):
        return 2
        
class BeszelNetworkSendSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_network_send"

    @property
    def name(self):
        return f"{self.system.name} Network Send" if self.system else None

    @property
    def icon(self):
        return "mdi:upload-network"

    @property
    def native_value(self):
        b_data = self.stats_data.get("b")
        return b_data[0] / 1024 if self.system and b_data else None

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_RATE

    @property
    def native_unit_of_measurement(self):
        return "kB/s"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self):
        return 2

class BeszelTemperatureSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_temperature"

    @property
    def name(self):
        return f"{self.system.name} temperature" if self.system else None
    
    @property
    def available(self):
        if not super().available:
            return False
        temperature = self.system.info.get("dt") if self.system else None
        return temperature is not None

    @property
    def native_value(self):
        return self.system.info.get("dt") if self.system else None

    @property
    def device_class(self):
        return SensorDeviceClass.TEMPERATURE

    @property
    def native_unit_of_measurement(self):
        return "°C"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        temperatures = self.stats_data.get("t")

        attributes = {}
        for key, value in (temperatures or {}).items():
            attributes[f"temperature_{key}"] = value

        return attributes


class BeszelUptimeSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_uptime"

    @property
    def name(self):
        return f"{self.system.name} uptime" if self.system else None

    @property
    def icon(self):
        return "mdi:sort-clock-descending"

    @property
    def device_class(self):
        return SensorDeviceClass.DURATION

    @property
    def native_value(self):
        return self.system.info.get("u") / 60 if self.system else None

    @property
    def suggested_display_precision(self):
        return 2

    @property
    def state_class(self):
        return SensorStateClass.TOTAL_INCREASING

    @property
    def native_unit_of_measurement(self):
        return "min"

class BeszelEFSDiskSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, disk_name):
        super().__init__(coordinator, system)
        self._disk_name = disk_name

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_efs_{self._disk_name}"

    @property
    def name(self):
        return f"{self.system.name} EFS {self._disk_name}" if self.system else None

    @property
    def icon(self):
        return "mdi:harddisk"

    @property
    def native_value(self):
        if not self.stats_data:
            return None

        efs_data = self.stats_data.get('efs', {})
        disk_data = efs_data.get(self._disk_name, {})

        total_space = disk_data.get('d')
        used_space = disk_data.get('du')

        # Calculate disk usage percentage
        if total_space and used_space and total_space > 0:
            return (used_space / total_space) * 100
        return None

    @property
    def native_unit_of_measurement(self):
        return "%"
    
    @property
    def suggested_display_precision(self):
        return 2

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        """Return additional state attributes for the EFS disk."""
        if not self.stats_data:
            return {}

        efs_data = self.stats_data.get('efs', {})
        disk_data = efs_data.get(self._disk_name, {})

        return {
            "total_disk_space_gb": disk_data.get('d'),
            "disk_used_gb": disk_data.get('du'),
            "read_mb_s": disk_data.get('r'),
            "write_mb_s": disk_data.get('w'),
        }



class BeszelBatterySensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_battery"

    @property
    def name(self):
        return f"{self.system.name} Battery" if self.system else None

    @property
    def icon(self):
        if not self.stats_data and "bat" not in self.stats_data:
            return "mdi:battery-unknown"
        level, state = self.stats_data.get("bat")
        # https://github.com/henrygd/beszel/blob/4d05bfdff0ec90b68e820ad5dc32a5c4bccf8f0f/internal/site/src/lib/enums.ts#L41-L48
        charging = state == 3

        return icon_for_battery_level(level, charging)

    @property
    def device_class(self):
        return SensorDeviceClass.BATTERY

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if not self.stats_data:
            return None
        return self.stats_data.get("bat")[0]

    @property
    def native_unit_of_measurement(self):
        return "%"


class BeszelRAMTotalSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_ram_total"

    @property
    def name(self):
        return f"{self.system.name} RAM Total" if self.system else None

    @property
    def icon(self):
        return "mdi:chip"

    @property
    def native_value(self):
        if not self.stats_data:
            return None
        return self.stats_data.get("m")

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def native_unit_of_measurement(self):
        return "GB"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelDiskTotalSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, disk_name=None):
        super().__init__(coordinator, system)
        self._disk_name = disk_name

    @property
    def unique_id(self):
        suffix = f"_{self._disk_name}" if self._disk_name else ""
        return f"beszel_{self._system_id}_disk_total{suffix}"

    @property
    def name(self):
        label = f" {self._disk_name}" if self._disk_name else ""
        return f"{self.system.name} Disk Total{label}" if self.system else None

    @property
    def icon(self):
        return "mdi:harddisk"

    @property
    def native_value(self):
        if not self.stats_data:
            return None

        if self._disk_name:
            disk_data = self.stats_data.get("efs", {}).get(self._disk_name, {})
            if isinstance(disk_data, dict):
                return disk_data.get("d")
            return None

        return self.stats_data.get("d")

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def native_unit_of_measurement(self):
        return "GB"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT
