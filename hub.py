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
        # discover = discovery.Discovery()
        # res = discover.run()
        dev = device.Device(host)
        res = dev.run()
        # dev.close()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, PH803W_DEFAULT_TCP_PORT))

        data = bytes.fromhex("0000000303000006")
        self.socket.sendall(data)
        response = self.socket.recv(1024)
        passcode_lenth = response[9]
        passcode_raw = response[10 : 10 + passcode_lenth]
        passcode = passcode_raw.decode("utf-8")

        data = (
            bytes.fromhex("000000030f00000800")
            + passcode_lenth.to_bytes(1, "little")
            + passcode_raw
        )
        self.socket.sendall(data)
        response = self.socket.recv(1024)
        if response[8] != 0:
            print("Error connecting")

        # Connection established, from now on some cyclig bahavior
        data = bytes.fromhex("000000030400009002")
        self.socket.sendall(data)
        empty_counter = 0
        data = bytes.fromhex("0000000303000015")
        response = self.socket.recv(1024)
        # if len(response) == 0:
        #     empty_counter += 1
        #     continue
        empty_counter = 0
        # print(response)
        if len(response) == 18:
            flag1 = response[8]
            if flag1 & 0b0000_0100:
                print("In water")
            flag2 = response[9]
            if flag2 & 0b0000_0010:
                print("ORP on")
            if flag2 & 0b0000_0001:
                print("PH on")
            # state_raw = response[8 : 9]
            ph_raw = response[10:12]
            self.ph = int.from_bytes(ph_raw, "big") * 0.01
            redox_raw = response[12:14]
            self.redox = int.from_bytes(redox_raw, "big") - 2000
            unknown1_raw = response[14:16]
            unknown1 = int.from_bytes(unknown1_raw, "big")
            unknown2_raw = response[15:18]
            unknown2 = int.from_bytes(unknown2_raw, "big")

        self._host = host
        self._hass = hass
        self._name = host
        self._id = host.lower()
        self.probe = Probe(f"{self._id}_1", f"{self._name} 1", self)
        self.online = True

    @property
    def hub_id(self) -> str:
        """ID for dummy hub."""
        return self._id

    async def test_connection(self) -> bool:
        """Test connectivity to the Dummy hub is OK."""
        await asyncio.sleep(1)
        return True


class Probe:
    """Dummy roller (device for HA) for Hello World example."""

    def __init__(self, id: str, name: str, hub: Hub) -> None:
        """Init dummy roller."""
        self._id = id
        self.hub = hub
        self.name = name
        self._ph_value = hub.ph
        self._orp_value = hub.redox
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()

        # Some static information about this device
        self.firmware_version = f"0.0.{random.randint(1, 9)}"
        self.model = "Test Device"

    @property
    def id(self) -> str:
        """Return ID for roller."""
        return self._id

    # async def set_position(self, position: int) -> None:
    #     """
    #     Set dummy cover to the given position.

    #     State is announced a random number of seconds later.
    #     """
    #     self._target_position = position

    #     # Update the moving status, and broadcast the update
    #     self.moving = position - 50
    #     await self.publish_updates()

    #     self._loop.create_task(self.delayed_update())

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
        """Battery level as a percentage."""
        return self._ph_value

    @property
    def orp(self) -> float:
        """Return a random voltage roughly that of a 12v battery."""
        return self._orp_value
