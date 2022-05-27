"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import (
    ELECTRIC_POTENTIAL_MILLIVOLT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from . import UPDATE_TOPIC
from .const import DOMAIN


class DeviceSensorConfig:
    """PH-803W Device Sensor configuration."""

    def __init__(
        self,
        friendly_name,
        field,
        icon="mdi:gauge",
        unit_of_measurement=None,
        device_class=None,
    ):
        """Initialize configuration."""
        self.device_class = device_class
        self.friendly_name = friendly_name
        self.field = field
        self.icon = icon
        self.unit_of_measurement = unit_of_measurement


SENSORS = [
    DeviceSensorConfig("pH Sensor", "ph", "mdi:water-percent"),
    DeviceSensorConfig(
        "ORP Sensor",
        "orp",
        "mdi:water-opacity",
        ELECTRIC_POTENTIAL_MILLIVOLT,
        SensorDeviceClass.VOLTAGE,
    ),
]


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the PH-803W sensor."""
    if discovery_info is None:
        return

    sensors = []
    client = hass.data[DOMAIN]
    for sconfig in SENSORS:
        sensors.append(DeviceSensor(client, sconfig))

    add_entities(sensors)


class DeviceSensor(SensorEntity):
    """Implementing the Waterfurnace sensor."""

    def __init__(self, client, config):
        """Initialize the sensor."""
        self.client = client
        self._name = config.friendly_name
        self._attr = config.field
        self._state = None
        self._icon = config.icon
        self._unit_of_measurement = config.unit_of_measurement
        self._attr_device_class = config.device_class

        # This ensures that the sensors are isolated per waterfurnace unit
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"wf_{slugify(self.client.unit)}_{slugify(self._attr)}"
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return icon."""
        return self._icon

    @property
    def native_unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, UPDATE_TOPIC, self.async_update_callback
            )
        )

    @callback
    def async_update_callback(self):
        """Update state."""
        if self.client.data is not None:
            self._state = getattr(
                self.client.get_latest_measurement_and_empty(), self._attr, None
            )
            self.async_write_ha_state()
