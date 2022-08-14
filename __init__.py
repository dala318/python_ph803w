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
ERROR_ITERVAL_MAPPING = [0, 10, 60, 300, 600, 3000, 6000]
ERROR_RECONNECT_INTERVAL = 300
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

    hass.data[DOMAIN] = DeviceData(hass, config)
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

    def __init__(self, hass, config) -> None:
        super().__init__()
        self.name = "Ph803wThread"
        self.hass = hass
        self.host = config[CONF_HOST]
        self.device_client = None
        self._shutdown = False
        self._fails = 0

    def connected(self):
        return self.device_client is not None

    def passcode(self):
        if self.device_client is not None:
            return self.device_client.passcode
        return None

    def unique_name(self):
        if self.device_client is not None:
            return self.device_client.get_unique_name()
        return None

    def measurement(self):
        if self.device_client is not None:
            return self.device_client.get_latest_measurement()
        return None

    def run(self):
        """Thread run loop."""

        @callback
        def register():
            """Connect to hass for shutdown."""

            def shutdown(event):
                """Shutdown the thread."""
                _LOGGER.info("Signaled to shutdown")
                self._shutdown = True
                if self.device_client is not None:
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
            self.device_client = None

            _LOGGER.info(f"Attempting to connect to device at {self.host}")
            device_client = device.Device(self.host)

            try:
                if not device_client.run(once=True):
                    _LOGGER.info(
                        f"Device found but no measurement was received, reconnecting in {ERROR_RECONNECT_INTERVAL} seconds")
                    time.sleep(ERROR_RECONNECT_INTERVAL)
                    continue

            except Exception as e:
                _LOGGER.info(
                    f"Error connecting to device at {self.host}: {str(e)}")
                _LOGGER.info(
                    f"Retrying connection in {ERROR_RECONNECT_INTERVAL} seconds")
                time.sleep(ERROR_RECONNECT_INTERVAL)
                continue

            self.device_client = device_client
            _LOGGER.debug("Registering callbacks")
            self.device_client.register_callback(self.dispatcher_new_data)
            self.device_client.register_callback(self.reset_fail_counter)

            while True:
                if self._shutdown:
                    _LOGGER.debug("Graceful shutdown")
                    return

                try:
                    _LOGGER.info("Starting device client loop")
                    self.device_client.run(once=False)
                except Exception as e:
                    _LOGGER.exception(f"Failed to read data: {str(e)}")
                    self.device_client.close()
                    self._fails += 1
                    error_mapping = self._fails
                    if error_mapping >= len(ERROR_ITERVAL_MAPPING):
                        error_mapping = len(ERROR_ITERVAL_MAPPING) - 1
                    sleep_time = ERROR_ITERVAL_MAPPING[error_mapping]
                    _LOGGER.info(
                        f"Sleeping {str(sleep_time)}s for failure #{str(self._fails)}")
                    self.device_client.reset_socket()
                    time.sleep(sleep_time)

    @callback
    def reset_fail_counter(self):
        self._fails = 0

    @callback
    def dispatcher_new_data(self):
        """Noyifying HASS that new data is ready to read."""
        dispatcher_send(self.hass, UPDATE_TOPIC)
