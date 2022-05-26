import socket

PH803W_DEFAULT_TCP_PORT = 12416
PH803W_PING_INTERVAL = 4000
RECONNECT_DELAY = 10000
RESPONSE_TIMEOUT = 5000


class Device(object):
    def __init__(self, host):
        self.result = {}
        self.host = host
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._loop = True

    async def run_async(self):
        self.run()

    def run(self, once: bool = False) -> bool:
        self._loop = True
        self._socket.connect((self.host, PH803W_DEFAULT_TCP_PORT))

        data = bytes.fromhex("0000000303000006")
        self._socket.sendall(data)
        response = self._socket.recv(1024)
        passcode_lenth = response[9]
        passcode_raw = response[10 : 10 + passcode_lenth]
        passcode = passcode_raw.decode("utf-8")
        # print(passcode)

        data = (
            bytes.fromhex("000000030f00000800")
            + passcode_lenth.to_bytes(1, "little")
            + passcode_raw
        )
        self._socket.sendall(data)
        response = self._socket.recv(1024)
        if response[8] != 0:
            #     print("Error connecting")
            return False

        # Connection established, from now on some cyclig bahavior
        data = bytes.fromhex("000000030400009002")
        self._socket.sendall(data)
        empty_counter = 0
        data = bytes.fromhex("0000000303000015")
        while self._loop and empty_counter < 10:
            response = self._socket.recv(1024)
            if len(response) == 0:
                empty_counter += 1
                continue
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
                ph = int.from_bytes(ph_raw, "big") * 0.01
                redox_raw = response[12:14]
                redox = int.from_bytes(redox_raw, "big") - 2000
                unknown1_raw = response[14:16]
                unknown1 = int.from_bytes(unknown1_raw, "big")
                unknown2_raw = response[15:18]
                unknown2 = int.from_bytes(unknown2_raw, "big")
                print(
                    "pH: %s, Redox: %s, U1: %s, U2: %s"
                    % (ph, redox, unknown1, unknown2),
                    flush=True,
                )
            self._socket.sendall(data)
            response = self._socket.recv(1024)
            if once:
                break

    def _handle_response(self, data):
        if data[0] != 0 and data[1] != 0 and data[2] != 0 and data[2] != 3:
            # print("Ignore data package because invalid prefix: %s" % data[0:3])
            self.result["status"] = [
                "Error",
                "Ignore data package because invalid prefix",
            ]
            return
        data_length = data[4]
        if len(data) != data_length + 5:
            if len(data) > data_length:
                additional_data = data[data_length : len(data)]
                data = data[0:data_length]
                # print(
                #     "Split into two data packages because additional data detected. First %s - Second %s}"
                #     % (data.toString("hex"), additional_data.toString("hex"))
                # )
                self._handle_response(additional_data)
            else:
                # print(
                #     "Ignore data package because invalid length(%s): %s"
                #     % (data_length, data)
                # )
                self.result["status"] = [
                    "Error",
                    "Ignore data package because invalid length",
                ]
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
            # print(
            #     "Ignore data package because invalid message type %s: %s"
            #     % (message_type, data)
            # )
            self.result["status"] = [
                "Ignore",
                "Ignore data package because invalid length",
                message_type,
                data,
            ]

    def _handle_passcode_response(self, data):
        pass

    def _handle_login_response(self, data):
        pass

    def _handle_ping_pong_response(self):
        pass

    def _handle_data_extended_response(self, data):
        pass

    def _send_ping(self):
        pass

    #     if (this.pingWaitTimeout) {
    #         clearTimeout(this.pingWaitTimeout);
    #         this.pingWaitTimeout = null;
    #     }
    #     if (this.pingTimeout) {
    #         clearTimeout(this.pingTimeout);
    #         this.pingTimeout = null;
    #     }
    #     debug('received pong');
    #     this.pingTimeout = setTimeout(() => {
    #         this.pingTimeout = null;
    #         this._sendPing();
    #     }, this.options.pingInterval || PH803W_PING_INTERVAL);
    # }    def _handle_data_response(self, data):

    def abort(self):
        self._loop = False

    def close(self):
        self._socket.close()

    def get_result(self):
        return str(self.result)

    def __enter__(self):
        self.run()
        return self

    def __exit__(self, type, value, traceback):
        self._socket.close()
