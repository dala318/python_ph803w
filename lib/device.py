import socket
from sys import argv

PH803W_DEFAULT_TCP_PORT = 12416
PH803W_PING_INTERVAL = 4000
RECONNECT_DELAY = 10000
RESPONSE_TIMEOUT = 5000


class Device(object):
    def __init__(self, host):
        self.result = {}
        self.host = host
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def run(self):
        self.loop = True
        self.socket.connect((self.host, PH803W_DEFAULT_TCP_PORT))

        data = bytes.fromhex('0000000303000006')
        self.socket.sendall(data)
        response = self.socket.recv(1024)
        passcode_lenth = response[9]
        passcode_raw = response[10 : 10 + passcode_lenth]
        passcode = passcode_raw.decode("utf-8")

        data = bytes.fromhex('000000030f00000800') + passcode_lenth.to_bytes(1, 'little') + passcode_raw
        self.socket.sendall(data)
        response = self.socket.recv(1024)
        if response[8] != 0:
            print('Error connecting')

        # Connection established, from now on some cyclig bahavior
        data = bytes.fromhex('000000030400009002')
        self.socket.sendall(data)
        empty_counter = 0
        data = bytes.fromhex('0000000303000015')
        while self.loop and empty_counter < 10:
            response = self.socket.recv(1024)
            if len(response) == 0:
                empty_counter += 1
                continue
            empty_counter = 0
            print(response)
            if len(response) == 18:
                flag1 = response[8]
                if flag1 & 0b0000_0100:
                    print('In water')
                flag2 = response[9]
                if flag2 & 0b0000_0010:
                    print('ORP on')
                if flag2 & 0b0000_0001:
                    print('PH on')
                #state_raw = response[8 : 9]
                ph_raw = response[10 : 12]
                ph = int.from_bytes(ph_raw, 'big') * 0.01
                redox_raw = response[12 : 14]
                redox = int.from_bytes(redox_raw, 'big') - 2000
                unknown1_raw = response[14 : 16]
                unknown1 = int.from_bytes(unknown1_raw, 'big')
                unknown2_raw = response[15 : 18]
                unknown2 = int.from_bytes(unknown2_raw, 'big')
                print('pH: %s, Redox: %s, U1: %s, U2: %s' % (ph, redox, unknown1, unknown2))



            self.socket.sendall(data)
            response = self.socket.recv(1024)
            #print(response)


        pass
        #self.socket.bind((host, PH803W_DEFAULT_TCP_PORT))
        #self.socket.listen()
        #conn, addr = self.socket.accept()
        #with conn:
        #    print('Connected to: %s' % addr)
        #    while True:
        #        data = conn.recv(1024)
        #        if not data:
        #            break
        #        conn.sendall(data)

    def abort(self):
        self.loop = False

    def close(self):
        self.socket.close()

    def get_result(self):
        return str(self.result)

    def __enter__(self):
        self.run()
        return self

    def __exit__(self, type, value, traceback):
        self.socket.close()


if __name__ == '__main__':
    with Device('192.168.1.89') as d:
        print(d.get_result())