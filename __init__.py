"""Support for PH-803W."""
from datetime import timedelta
import logging
import threading
import time

import voluptuous as vol

from .lib import device
from .const import DOMAIN

from homeassistant.components import persistent_notification
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
SCAN_INTERVAL = timedelta(seconds=10)
ERROR_INTERVAL = timedelta(seconds=300)
MAX_FAILS = 10
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


def setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up waterfurnace platform."""

    config = base_config[DOMAIN]

    host = config[CONF_HOST]

    ph_device = device.Device(host)
    try:
        if not ph_device.run(once=True):
            _LOGGER.error("Device found but no measuremetn was received")
            return False
    except TimeoutError:
        _LOGGER.error("Could no connect ot device")
        return False

    hass.data[DOMAIN] = DeviceData(hass, ph_device)
    hass.data[DOMAIN].start()

    discovery.load_platform(hass, Platform.SENSOR, DOMAIN, {}, config)
    discovery.load_platform(hass, Platform.BINARY_SENSOR, DOMAIN, {}, config)
    return True


class DeviceData(threading.Thread):
    """PH-803W Data Collector.

    This is implemented as a dedicated thread polling the device as the
    device requires ping/pong every 4s. The alternative is to reconnect
    for every new data, could work for the pH and ORP data but for the
    switches a more direct feedback is wanted."""

    def __init__(self, hass, client: device.Device) -> None:
        super().__init__()
        self.hass = hass
        self.client = client
        self.unit = self.client.host
        self._shutdown = False
        self._fails = 0

    # def _reconnect(self):
    #     """Reconnect on a failure."""

    #     self._fails += 1
    #     if self._fails > MAX_FAILS:
    #         _LOGGER.error("Failed to reconnect. Thread stopped")
    #         persistent_notification.create(
    #             self.hass,
    #             "Error:<br/>Connection to PH-803W device failed "
    #             "the maximum number of times. Thread has stopped",
    #             title=NOTIFICATION_TITLE,
    #             notification_id=NOTIFICATION_ID,
    #         )

    #         self._shutdown = True
    #         return

    #     # sleep first before the reconnect attempt
    #     _LOGGER.debug("Sleeping for fail # %s", self._fails)
    #     time.sleep(self._fails * ERROR_INTERVAL.total_seconds())

    #     try:
    #         self.client.run(once=False)
    #     except:
    #         _LOGGER.exception("Failed to reconnect attempt %s", self._fails)
    #     else:
    #         _LOGGER.debug("Reconnected to device")
    #         self._fails = 0

    def run(self):
        """Thread run loop."""

        @callback
        def register():
            """Connect to hass for shutdown."""

            def shutdown(event):
                """Shutdown the thread."""
                _LOGGER.debug("Signaled to shutdown")
                self._shutdown = True
                self.client.abort()
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

            if self._fails > MAX_FAILS:
                _LOGGER.error("Failed to reconnect. Thread stopped")
                persistent_notification.create(
                    self.hass,
                    "Error:<br/>Connection to PH-803W device failed "
                    "the maximum number of times. Thread has stopped",
                    title=NOTIFICATION_TITLE,
                    notification_id=NOTIFICATION_ID,
                )
                return

            try:
                self.client.run(once=False)
            except device.DeviceError:
                _LOGGER.exception("Failed to read data, attempting to recover")
                self.client.close()
                self._fails += 1
                sleep_time = self._fails * ERROR_INTERVAL.total_seconds()
                _LOGGER.debug(
                    "Sleeping for fail #%s, in %s seconds", self._fails, sleep_time
                )
                self.client.reset_socket()
                time.sleep(sleep_time)

        # while True:
        #     if self._shutdown:
        #         _LOGGER.debug("Graceful shutdown")
        #         return

        #     try:
        #         self.data = self.client.run(once=False)

        #     except WFException:
        #         # WFExceptions are things the WF library understands
        #         # that pretty much can all be solved by logging in and
        #         # back out again.
        #         _LOGGER.exception("Failed to read data, attempting to recover")
        #         self._reconnect()

        #     else:
        #         dispatcher_send(self.hass, UPDATE_TOPIC)
        #         time.sleep(SCAN_INTERVAL.total_seconds())


# async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Set up Hello World from a config entry."""
#     # Store an instance of the "connecting" class that does the work of speaking
#     # with your actual devices.
#     hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub.Hub(hass, entry.data["host"])

#     # This creates each HA object for each platform your device requires.
#     # It's done by calling the `async_setup_entry` function in each platform module.
#     hass.config_entries.async_setup_platforms(entry, PLATFORMS)
#     return True


# async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Unload a config entry."""
#     # This is called when an entry/configured device is to be removed. The class
#     # needs to unload itself, and remove callbacks. See the classes for further
#     # details
#     unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
#     if unload_ok:
#         hass.data[DOMAIN].pop(entry.entry_id)

#     return unload_ok
