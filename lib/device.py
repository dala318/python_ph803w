import socket

PH803W_DEFAULT_TCP_PORT = 12416
PH803W_PING_INTERVAL = 4000
RECONNECT_DELAY = 10000
RESPONSE_TIMEOUT = 5000


class Device(object):
    def __init__(self):
        #self.result = {}

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        # Enable broadcasting mode
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Set a timeout so the socket does not block
        # indefinitely when trying to receive data.
        self.socket.settimeout(1)
