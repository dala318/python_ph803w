"""A PH-803W device discovery client."""
import socket
import asyncio
import logging

PH803W_UDP_PORT = 12414

_LOGGER = logging.getLogger(__name__)


class DiscoveryError(ConnectionError):
    pass


class Discovery(object):
    def __init__(self):
        self.device = None
        self._socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )
        # Enable broadcasting mode
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Set a timeout so the socket does not block
        # indefinitely when trying to receive data.
        self._socket.settimeout(1)

    async def run_async(self):
        self.run()

    def run(self):
        # Send dicovery request broadcast
        data = bytes.fromhex("0000000303000003")
        self._socket.sendto(data, ("<broadcast>", PH803W_UDP_PORT))
        self._socket.settimeout(2)
        _LOGGER.debug("Sent request message!")

        # Receive device reaponse to discovery
        data, remote = self._socket.recvfrom(1024)
        if data[0] != 0 and data[1] != 0 and data[2] != 0 and data[2] != 3:
            _LOGGER.error("Ignore data package because invalid prefix: %s" % data[0:3])
            raise DiscoveryError("Ignore data package because invalid prefix")
        data_length = data[4]
        if len(data) != data_length + 5:
            _LOGGER.error(
                "Ignore data package because invalid length(%s): %s"
                % (data_length, data)
            )
            raise DiscoveryError("Ignore data package because invalid length")
        if data[7] == 3:
            _LOGGER.error("Unknown response message type")
            raise DiscoveryError("Unknown response message type")
        if data[7] != 4:
            _LOGGER.error("Ignore data package because invalid message type ${data[7]}")
            raise DiscoveryError("Ignore data package because invalid message type")

        # Parsing result of correct type
        _LOGGER.info(
            "Parsing discovered device: %s: %s - %s" % (remote[0], remote[1], data[7:])
        )
        self.device = DeviceDiscovery(remote[0], data)

    def close(self):
        self._socket.close()

    def get_result(self):
        return self.device

    def __enter__(self):
        self.run()
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class DeviceDiscovery:
    def __init__(self, ip: str, data):
        self.ip = ip

        if data is None:
            _LOGGER.info("Initializing empty device with ip:%s" % ip)
            self.id1 = ""
            self.id2 = ""
            self.api_server = ""
            self.version_server = ""
            return

        id1_length = data[9]
        id1_raw = data[10 : 10 + id1_length]
        self.id1 = id1_raw.decode("utf-8")

        id2_length = data[9 + id1_length + 12]
        id2_raw = data[9 + id1_length + 13 : 9 + id1_length + 13 + id2_length]
        self.id2 = id2_raw.decode("utf-8")

        idx = 9 + id1_length + 13 + id2_length + 8
        idx_start = idx
        while data[idx] != 0:
            idx += 1
        api_server_raw = data[idx_start:idx]
        self.api_server = api_server_raw.decode("utf-8")

        idx += 1
        idx_start = idx
        while data[idx] != 0:
            idx += 1
        version_raw = data[idx_start:idx]
        self.version_server = version_raw.decode("utf-8")

    def __str__(self) -> str:
        return "Devive Discovery: ip: %s" % self.ip
