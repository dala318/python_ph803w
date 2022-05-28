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
    # discovery.load_platform(hass, Platform.BINARY_SENSOR, DOMAIN, {}, config)
    return True


class DeviceData(threading.Thread):
    """PH-803W Data Collector.

    This is implemented as a dedicated thread polling the device as the
    device requires ping/pong every 4s. The alternative is to reconnect
    for every new data, could work for the pH and ORP data but for the
    switches a more direct feedback is wanted."""

    def __init__(self, hass, client: device.Device) -> None:
        super().__init__()
        self.name = "Ph803wThread"
        self.hass = hass
        self.client = client
        self.unit = self.client.host
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
