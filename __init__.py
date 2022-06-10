"""Support for PH-803W."""
from datetime import timedelta
import logging
import threading
import time

import voluptuous as vol

from .lib import device
from .const import DOMAIN

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

UPDATE_TOPIC = f"{DOMAIN}_update"
ERROR_ITERVAL_MAPPING = [0, 10, 60, 300, 600, 3000, 6000]
NOTIFICATION_ID = "ph803w_device_notification"
NOTIFICATION_TITLE = "PH-803W Device status"


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
PLATFORMS: list[str] = ["sensor", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello World from a config entry."""
    host = entry.data["host"]

    device_client = device.Device(host)
    try:
        if not device_client.run(once=True):
            _LOGGER.error("Device found but no measuremetn was received")
            return False
    except TimeoutError:
        _LOGGER.error("Could no connect ot device")
        return False

    # device_data = DeviceData(hass, device_client)
    # device_data.start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = DeviceData(hass, device_client)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id].start()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


# def setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
#     """Set up waterfurnace platform."""

#     config = base_config[DOMAIN]

#     host = config[CONF_HOST]

#     device_client = device.Device(host)
#     try:
#         if not device_client.run(once=True):
#             _LOGGER.error("Device found but no measuremetn was received")
#             return False
#     except TimeoutError:
#         _LOGGER.error("Could no connect ot device")
#         return False

#     hass.data[DOMAIN] = DeviceData(hass, device_client)
#     hass.data[DOMAIN].start()

#     discovery.load_platform(hass, Platform.SENSOR, DOMAIN, {}, config)
#     discovery.load_platform(hass, Platform.BINARY_SENSOR, DOMAIN, {}, config)
#     return True


class DeviceData(threading.Thread):
    """PH-803W Data Collector.

    This is implemented as a dedicated thread polling the device as the
    device requires ping/pong every 4s. The alternative is to reconnect
    for every new data, could work for the pH and ORP data but for the
    switches a more direct feedback is wanted."""

    def __init__(self, hass, device_client: device.Device) -> None:
        super().__init__()
        self.name = "Ph803wThread"
        self.hass = hass
        self.device_client = device_client
        self.device_client.register_callback(self.dispatcher_new_data)
        self.device_client.register_callback(self.reset_fail_counter)
        self.host = self.device_client.host
        self._shutdown = False
        self._fails = 0

    def run(self):
        """Thread run loop."""

        @callback
        def register():
            """Connect to hass for shutdown."""

            def shutdown(event):
                """Shutdown the thread."""
                _LOGGER.debug("Signaled to shutdown")
                self._shutdown = True
                self.device_client.abort()
                self.join()

            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

        self.hass.add_job(register)

        # This does a tight loop in sending ping/pong to the
        # device. That's a blocking call, which returns pretty
        # quickly (0.5 second). It's important that we do this
        # frequently though, because if we don't call the websocket at
        # least every 4 seconds the device side closes the
        # connection.
        while True:
            if self._shutdown:
                _LOGGER.debug("Graceful shutdown")
                return

            try:
                self.device_client.run(once=False)
            except (device.DeviceError, RecursionError, ConnectionError):
                _LOGGER.exception("Failed to read data, attempting to recover")
                self.device_client.close()
                self._fails += 1
                error_mapping = self._fails
                if error_mapping >= len(ERROR_ITERVAL_MAPPING):
                    error_mapping = len(ERROR_ITERVAL_MAPPING) - 1
                sleep_time = ERROR_ITERVAL_MAPPING[error_mapping]
                _LOGGER.debug(
                    "Sleeping for fail #%s, in %s seconds", self._fails, sleep_time
                )
                self.device_client.reset_socket()
                time.sleep(sleep_time)

    @callback
    def reset_fail_counter(self):
        self._fails = 0

    @callback
    def dispatcher_new_data(self):
        """Noyifying HASS that new data is ready to read."""
        dispatcher_send(self.hass, UPDATE_TOPIC)
