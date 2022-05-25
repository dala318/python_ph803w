import socket
import asyncio

PH803W_UDP_PORT = 12414


class Discovery(object):
    def __init__(self):
        self.result = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        # Enable broadcasting mode
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Set a timeout so the socket does not block
        # indefinitely when trying to receive data.
        self.socket.settimeout(1)

    async def run_async(self):
        self.run()

    def run(self):
        data = bytes.fromhex('0000000303000003')
        self.socket.sendto(data, ('<broadcast>', PH803W_UDP_PORT))
        print("Sent request message!")
        
        data, remote = self.socket.recvfrom(1024)

        if data[0] != 0 and data[1] != 0 and data[2] != 0 and data[2] != 3:
            print('Ignore data package because invalid prefix: %s' % data[0:3])
            self.result['status'] = ['Error', 'Ignore data package because invalid prefix']
            return
        data_length = data[4]
        if len(data) != data_length + 5:
            print('Ignore data package because invalid length(%s): %s' % (data_length, data))
            self.result['status'] = ['Error', 'Ignore data package because invalid length']
            return
        if data[7] == 3:
            self.result['status'] = ['Unknown']
            return
        if data[7] != 4:
            print('Ignore data package because invalid message type ${data[7]}')
            self.result['status'] = ['Error', 'Ignore data package because invalid message type']
            return

        print('Parsing discovered device: %s: %s - %s' % (remote[0], remote[1], data[7:]))
        self.result['status'] = ['Error']  # Temporary until all pass
        self.result['result'] = {'ip' : remote[0]}

        id1_length = data[9]
        id1_raw = data[10 : 10 + id1_length]
        self.result['result']['id1'] = id1_raw.decode("utf-8")

        id2_length = data[9 + id1_length + 12]
        id2_raw = data[9 + id1_length + 13 : 9 + id1_length + 13 + id2_length]
        self.result['result']['id2'] = id2_raw.decode("utf-8")

        idx = 9 + id1_length + 13 + id2_length + 8
        idx_start = idx
        while data[idx] != 0:
            idx += 1
        api_server_raw = data[idx_start: idx]
        self.result['result']['api_server'] = api_server_raw.decode("utf-8")

        idx += 1

        idx_start = idx
        while data[idx] != 0:
            idx += 1
        version_raw = data[idx_start: idx]
        self.result['result']['version_server'] = version_raw.decode("utf-8")

        self.result['status'] = ['success']

    def close(self):
        self.socket.close()

    def get_result(self):
        return self.result

    def __enter__(self):
        self.run()
        return self

    def __exit__(self, type, value, traceback):
        self.close()

if __name__ == '__main__':
    with Discovery() as d:
        print(d.get_result())

    loop = asyncio.get_event_loop()
    discovery = Discovery()
    loop.run_until_complete(discovery.run_async())
    print(discovery.get_result())
    loop.close()
