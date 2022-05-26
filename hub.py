"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

# In a real implementation, this would be in an external library that's on PyPI.
# The PyPI package needs to be included in the `requirements` section of manifest.json
# See https://developers.home-assistant.io/docs/creating_integration_manifest
# for more information.
# This dummy hub always returns 3 rollers.
import asyncio
import socket
import random

from .lib import discovery, device

from homeassistant.core import HomeAssistant

PH803W_DEFAULT_TCP_PORT = 12416


class Hub:
    """Dummy hub for Hello World example."""

    manufacturer = "Demonstration Corp"

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Init dummy hub."""
        # Discovery is not working in Home Assistant, could it be something to do with UDP broadcast?
        # discover = discovery.Discovery()
        # res = discover.run()

        with device.Device(host) as d:
            self.online = d.run(once=True)
            result = d.get_latest_measurement_and_empty()
            uid = d.passcode

        if not self.online:
            return

        self._host = host
        self._hass = hass
        self._name = "pH-803w"
        self._id = uid.lower()
        self.probe = Probe(f"{self._id}", f"{self._name}", self, result)

    @property
    def hub_id(self) -> str:
        """ID for dummy hub."""
        return self._id

    async def test_connection(self) -> bool:
        """Test connectivity to the Dummy hub is OK."""
        with device.Device(self._host) as d:
            return d.run(once=True)


class Probe:
    """Dummy roller (device for HA) for Hello World example."""

    def __init__(
        self, id: str, name: str, hub: Hub, result: device.Measurement
    ) -> None:
        """Init dummy roller."""
        self._id = id
        self.hub = hub
        self.name = name
        self._ph_value = result.ph
        self._orp_value = result.redox
        self._ph_on = result.ph_on
        self._opp_on = result.orp_on
        self._in_water = result.in_water
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()

        # Some static information about this device
        self.firmware_version = f"0.0.{random.randint(1, 9)}"
        self.model = "Test Device"

    @property
    def id(self) -> str:
        """Return ID for roller."""
        return self._id

    async def delayed_update(self) -> None:
        """Publish updates, with a random delay to emulate interaction with device."""
        await asyncio.sleep(random.randint(1, 10))
        self.moving = 0
        await self.publish_updates()

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    # In a real implementation, this library would call it's call backs when it was
    # notified of any state changeds for the relevant device.
    async def publish_updates(self) -> None:
        """Schedule call all registered callbacks."""
        pass
        # self._current_position = self._target_position
        # for callback in self._callbacks:
        #     callback()

    @property
    def online(self) -> float:
        """Roller is online."""
        # The dummy roller is offline about 10% of the time. Returns True if online,
        # False if offline.
        return random.random() > 0.1

    @property
    def ph(self) -> float:
        """Return the pH measurement."""
        return self._ph_value

    @property
    def orp(self) -> float:
        """Return the ORP measurement."""
        return self._orp_value
