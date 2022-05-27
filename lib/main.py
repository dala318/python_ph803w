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

    while True:
        try:
            with device.Device(result.ip) as dev:
                loop.run_until_complete(dev.run_async(once=False))
        except:
            _LOGGER.error("Exception in run loop, restarting...")

    loop.close()
