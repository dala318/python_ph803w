if __name__ == '__main__':

    import asyncio
    import discovery, device
    import logging

    logging.basicConfig(level=logging.DEBUG)
    _LOGGER = logging.getLogger(__name__)

    loop = asyncio.get_event_loop()

    try:
        disc = discovery.Discovery()
        loop.run_until_complete(disc.run_async())
        result = disc.get_result()
        _LOGGER.debug(result)
    except:
        result = discovery.DeviceDiscovery('192.168.1.89', None)

    dev = device.Device(result.ip)
    # listener = loop.create_task(dev.run_async())
    # asyncio.wait([listener])
    loop.run_until_complete(dev.run_async(once=False))
    #print(dev.get_result())

    loop.close()
