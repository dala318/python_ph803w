"""A PH-803W device value collector."""
import threading
import socket
import logging
from time import sleep

PH803W_DEFAULT_TCP_PORT = 12416
PH803W_PING_INTERVAL = 4
RECONNECT_DELAY = 10
# RESPONSE_TIMEOUT = 5000
ABORT_AFTER_CONSECUTIVE_EMPTY = 10

_LOGGER = logging.getLogger(__name__)


class DeviceError(ConnectionError):
    pass


class Device(object):
    def __init__(self, host):
        self.host = host
        self.passcode = ""
        self._measurements = []
        self._measurements_counter = 0
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._loop = True
        self._empty_counter = 0
        self._pong_thread = None

    async def run_async(self, once: bool = True) -> bool:
        return self.run(once)

    def run(self, once: bool = True) -> bool:
        if once:
            self._connect()
            return self._run(once)
        else:
            measurements = -1
            while self._loop:
                if measurements == self._measurements_counter:
                    _LOGGER.error("Aborting reconnects, no new measurements")
                    break
                measurements = self._measurements_counter
                self._connect()
                try:
                    self._run(once)
                except:
                    _LOGGER.warning("Exception in run loop")
                    self.close()
                    sleep(RECONNECT_DELAY)
            return not self._loop and self._measurements_counter > 0

    def _connect(self) -> bool:
        self._loop = True
        self._socket.connect((self.host, PH803W_DEFAULT_TCP_PORT))

        # Send request for connection
        data = bytes.fromhex("0000000303000006")
        self._socket.sendall(data)

        # Receive response and passcode
        response = self._socket.recv(1024)
        passcode_lenth = response[9]
        passcode_raw = response[10 : 10 + passcode_lenth]
        self.passcode = passcode_raw.decode("utf-8")
        _LOGGER.debug(self.passcode)

        # Send passcode confirmation
        data = (
            bytes.fromhex("000000030f00000800")
            + passcode_lenth.to_bytes(1, "little")
            + passcode_raw
        )
        self._socket.sendall(data)

        # Receive confirmation
        response = self._socket.recv(1024)
        if response[8] != 0:
            raise DeviceError("Error connecting")

    def _run(self, once: bool = True) -> bool:
        # Connection established, start requesting data,
        # from now on some cyclig bahavior
        data = bytes.fromhex("000000030400009002")
        self._socket.sendall(data)

        # If continous reading ping/pong needs to be run cyclic
        if not once:
            self._pong_thread = threading.Thread(target=self._ping_loop)
            self._pong_thread.daemon = True
            self._pong_thread.start()
        else:
            self._send_ping()

        while self._loop:
            response = self._socket.recv(1024)
            if self._empty_counter > ABORT_AFTER_CONSECUTIVE_EMPTY:
                _LOGGER.error("Too many empty consecutive packages")
                raise DeviceError("Too many empty consecutive packages")
            if len(response) == 0:
                _LOGGER.debug(self._empty_bar() + "Empty message received")
                self._empty_counter += 1
                continue
            self._empty_counter = 0

            self._handle_response(response)

            if once and len(self._measurements) > 0:
                self._loop = False
        self.close()
        return (once and len(self._measurements) > 0) or not once

    def _empty_bar(self) -> str:
        empty_filled = int(self._empty_counter * 10 / ABORT_AFTER_CONSECUTIVE_EMPTY)
        empty_clear = 10 - empty_filled
        return "[" + ("#" * empty_filled) + (" " * empty_clear) + "]"

    def _handle_response(self, data):
        if data[0] != 0 and data[1] != 0 and data[2] != 0 and data[2] != 3:
            _LOGGER.warning(
                "Ignore data package because invalid prefix: %s" % data[0:3]
            )
            return
        data_length = data[4]
        if len(data) != data_length + 5:
            if len(data) > data_length:
                additional_data = data[data_length : len(data)]
                data = data[0:data_length]
                _LOGGER.debug(
                    "Split into two data packages because additional data detected."
                )
                self._handle_response(additional_data)
            else:
                _LOGGER.warning(
                    "Ignore data package because invalid length(%s): %s"
                    % (data_length, data)
                )
                return

        message_type = data[7]
        if message_type == 0x07:
            self._handle_passcode_response(data)
        elif message_type == 0x09:
            self._handle_login_response(data)
        elif message_type == 0x16:
            self._handle_ping_pong_response()
        elif message_type == 0x91:
            self._handle_data_response(data)
        elif message_type == 0x94:
            self._handle_data_extended_response(data)
        else:
            pass
            _LOGGER.warning("Ignore data package because invalid message type %s" % message_type)

    def _handle_passcode_response(self, data):
        pass
        _LOGGER.warning("Passcode resonse ignored")

    def _handle_login_response(self, data):
        pass
        _LOGGER.warning("Login resonse ignored")

    def _handle_data_response(self, data):
        if len(data) == 18:
            meas = Measurement(data)
            self._measurements.append(meas)
            self._measurements_counter += 1
        else:
            pass
        _LOGGER.debug(self._empty_bar() +  str(meas))

    def _handle_data_extended_response(self, data):
        pass
        _LOGGER.warning("Extended data ignored")

    def _handle_ping_pong_response(self):
        # if self._pong_thread is None or self._pong_thread.done:
        #     self._pong_thread = asyncio.create_task(self._async_queue_ping())
        #     pass
        # else:
        #     _LOGGER.debug("Pong thread alredy running")
        _LOGGER.debug(self._empty_bar() + "Pong message received")

    def _send_ping(self):
        pong_data = bytes.fromhex("0000000303000015")
        self._socket.sendall(pong_data)
        _LOGGER.debug(self._empty_bar() + "Ping sent")

    def _ping_loop(self):
        while self._loop:
            sleep(PH803W_PING_INTERVAL)
            self._send_ping()

    # async def _async_queue_ping(self):
    #     await asyncio.sleep(PH803W_PING_INTERVAL)
    #     self._send_ping()

    def abort(self):
        self._loop = False

    def close(self):
        try:
            self._socket.close()
        except:
            pass

    def get_latest_measurement_and_empty(self):
        if len(self._measurements) > 0:
            m = self._measurements.pop()
            self._measurements.clear()
            return m
        return None

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class Measurement:
    def __init__(self, data) -> None:
        flag1 = data[8]
        self.in_water = flag1 & 0b0000_0100 != 0
        flag2 = data[9]
        self.orp_on = flag2 & 0b0000_0010 != 0
        self.ph_on = flag2 & 0b0000_0001 != 0
        ph_raw = data[10:12]
        self.ph = int.from_bytes(ph_raw, "big") * 0.01
        redox_raw = data[12:14]
        self.redox = int.from_bytes(redox_raw, "big") - 2000
        unknown1_raw = data[14:16]
        self.unknown1 = int.from_bytes(unknown1_raw, "big")
        unknown2_raw = data[15:18]
        self.unknown2 = int.from_bytes(unknown2_raw, "big")

    def __str__(self) -> str:
        return "pH: %s, Redox: %s, In-water: %s, pH-on: %s, Orp-on: %s" % (
            self.ph,
            self.redox,
            self.in_water,
            self.ph_on,
            self.orp_on,
        )
