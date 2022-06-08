"""Platform for sensor integration."""
from __future__ import annotations
import logging

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from . import UPDATE_TOPIC
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BinaryDeviceSensorConfig:
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
    BinaryDeviceSensorConfig(
        "PH-803W In water",
        "in_water",
        "mdi:water-check",
        "",
        BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinaryDeviceSensorConfig(
        "PH-803W pH switch on",
        "ph_on",
        "mdi:water-plus",
        "",
        BinarySensorDeviceClass.RUNNING,
    ),
    BinaryDeviceSensorConfig(
        "PH-803W ORP switch on",
        "orp_on",
        "mdi:water-plus",
        "",
        BinarySensorDeviceClass.RUNNING,
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
    device_data = hass.data[DOMAIN]
    for sconfig in SENSORS:
        sensors.append(DeviceSensor(device_data, sconfig))

    add_entities(sensors)


class DeviceSensor(BinarySensorEntity):
    """Implementing the Waterfurnace sensor."""

    def __init__(self, device_data, config):
        """Initialize the sensor."""
        self.device_data = device_data
        self._name = config.friendly_name
        self._attr = config.field
        self._state = None
        if self.device_data.device_client.get_latest_measurement() is not None:
            self._state = getattr(
                self.device_data.device_client.get_latest_measurement(),
                self._attr,
                None,
            )
        self._icon = config.icon
        self._unit_of_measurement = config.unit_of_measurement
        self._attr_device_class = config.device_class

        # This ensures that the sensors are isolated per waterfurnace unit
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"wf_{slugify(self.device_data.host)}_{slugify(self._attr)}"
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {
            "identifiers": {(DOMAIN, self.device_data.device_client.passcode)},
            "name": self.device_data.device_client.get_unique_name(),
        }

    @property
    def unique_id(self):
        """Return the sensor unique id."""
        return self.device_data.device_client.passcode + self._attr

    @property
    def is_on(self):
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
        if self.device_data.device_client.get_latest_measurement() is not None:
            self._state = getattr(
                self.device_data.device_client.get_latest_measurement(),
                self._attr,
                None,
            )
        else:
            self._state = None
        self.async_write_ha_state()
