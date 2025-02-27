"""A PH-803W device value collector."""
from statistics import stdev, mean, StatisticsError
import threading
import socket
import logging
from time import sleep

PH803W_DEFAULT_TCP_PORT = 12416
PH803W_PING_INTERVAL = 4
RECONNECT_DELAY = 10
# RESPONSE_TIMEOUT = 5000
ABORT_AFTER_CONSECUTIVE_EMPTY = 30

_LOGGER = logging.getLogger(__name__)


class DeviceError(ConnectionError):
    pass


class Device(object):
    def __init__(self, host):
        self.host = host
        self.passcode = ""
        self._measurements = []
        self._latest_measurement = None
        self._measurements_filter = None
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._loop = True
        self._empty_counter = 0
        self._pong_thread = None
        self._callbacks = []

    def reset_socket(self):
        try:
            self._socket.close()
        except:
            pass
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    async def run_async(self, once: bool = True) -> bool:
        return self.run(once)

    def run(self, once: bool = True) -> bool:
        self._loop = True
        if self._socket.fileno() == -1:
            self.reset_socket()
        self._connect()
        if once:
            return self._run(once)
        else:
            self._run(once)
            return not self._loop

    def register_callback(self, callback_function):
        self._callbacks.append(callback_function)

    def get_unique_name(self) -> str:
        return "PH-803W_%s" % self.passcode

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
        self._empty_counter = 0

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
                _LOGGER.warning("Too many empty consecutive packages")
                raise DeviceError("Too many empty consecutive packages")
            if len(response) == 0:
                self._empty_counter += 1
                if self._empty_counter % 10 == 0:
                    _LOGGER.warning(
                        "%s %s empty messages received"
                        % (self._empty_bar(), self._empty_counter)
                    )
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
            _LOGGER.warning(
                "Ignore data package because invalid message type %s" % message_type
            )

    def _handle_passcode_response(self, data):
        _LOGGER.warning("Passcode resonse ignored")

    def _handle_login_response(self, data):
        _LOGGER.warning("Login resonse ignored")

    def _handle_data_response(self, data):
        if len(data) == 18:
            meas = Measurement(data)
            if self._measurements_filter is None:
                self._measurements_filter = MeasOutlierFilter(meas.ph, meas.orp)
            else:
                self._measurements_filter.add(meas.ph, meas.orp)
            meas.add_filtered(
                self._measurements_filter.get_ph(), self._measurements_filter.get_orp()
            )
            _LOGGER.debug("Adding result: %s" % meas)
            self._measurements.append(meas)
            self._latest_measurement = meas
            if len(self._measurements) > 100:
                self._measurements.pop(0)
            for callback in self._callbacks:
                callback()
            _LOGGER.debug(meas)

    def _handle_data_extended_response(self, data):
        _LOGGER.warning("Extended data ignored")

    def _handle_ping_pong_response(self):
        _LOGGER.debug("Pong message received")

    def _send_ping(self):
        pong_data = bytes.fromhex("0000000303000015")
        self._socket.sendall(pong_data)
        _LOGGER.debug("Ping sent")

    def _ping_loop(self):
        while self._loop:
            self._send_ping()
            sleep(PH803W_PING_INTERVAL)

    def abort(self):
        self._loop = False

    def close(self):
        self._loop = False
        self._latest_measurement = None
        # self._measurements.clear()
        try:
            self._socket.close()
        except:
            pass
        for callback in self._callbacks:
            callback()

    def get_measurements_and_empty(self):
        meas = self._measurements
        self._measurements.clear()
        return meas

    def get_latest_measurement(self):
        return self._latest_measurement

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class MeasOutlierFilter:
    def __init__(self, ph: float, orp: float, history: int = 10) -> None:
        self._ph_filter = OutlierFilter(ph, history)
        self._orp_filter = OutlierFilter(orp, history)

    def add(self, ph: float, orp: float) -> None:
        self._ph_filter.add(ph)
        self._orp_filter.add(orp)

    def get_ph(self) -> float:
        return self._ph_filter.get()

    def get_orp(self) -> float:
        return self._orp_filter.get()


class OutlierFilter:
    def __init__(self, init_value: float, history: int = 10) -> None:
        self._values = []
        self._values.append(init_value)
        self._history = history

    def add(self, value: float) -> None:
        self._values.append(value)
        if len(self._values) > self._history:
            self._values.pop(0)

    def get(self) -> float:
        try:
            stddev_val = stdev(self._values)
            mean_val = mean(self._values)
            for val in reversed(self._values):
                if (val <= mean_val + stddev_val) and (val >= mean_val - stddev_val):
                    return val
        except StatisticsError:
            return self._values[-1]
        _LOGGER.warning("No match in outlier filter shall never happen!")
        return self._values[-1]


class Measurement:
    def __init__(self, data) -> None:
        flag1 = data[8]
        self.in_water = flag1 & 0b0000_0100 != 0
        flag2 = data[9]
        self.orp_on = flag2 & 0b0000_0010 != 0
        self.ph_on = flag2 & 0b0000_0001 != 0
        ph_raw = data[10:12]
        self.ph = int.from_bytes(ph_raw, "big") * 0.01
        orp_raw = data[12:14]
        self.orp = int.from_bytes(orp_raw, "big") - 2000
        unknown1_raw = data[14:16]
        self.unknown1 = int.from_bytes(unknown1_raw, "big")
        unknown2_raw = data[15:18]
        self.unknown2 = int.from_bytes(unknown2_raw, "big")

    def add_filtered(self, ph_filt: float, orp_filt: float) -> None:
        self.ph = ph_filt
        self.orp = orp_filt

    def __str__(self) -> str:
        return "pH: %s, Orp: %s, In-water: %s, pH-on: %s, Orp-on: %s" % (
            self.ph,
            self.orp,
            self.in_water,
            self.ph_on,
            self.orp_on,
        )
