import asyncio
from lib import discovery, device

loop = asyncio.get_event_loop()

discover = discovery.Discovery()
loop.run_until_complete(discover.run_async())
result = discover.get_result()
print(result)

dev = device.Device(result['result']['ip'])
# listener = loop.create_task(dev.run_async())
# asyncio.wait([listener])
loop.run_until_complete(dev.run_async())
print(dev.get_result())

loop.close()

