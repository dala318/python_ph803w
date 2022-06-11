![Logo](ph803w.png)
# python_ph803w
With a lot of inspiration and help from https://github.com/Apollon77/node-ph803w project I ported the basic functionallity to python with the hope and expectation to deploy it as an Home Assistant intagration without need for a docker service and MQTT.
Still a lot left to do but at least it can poll the device and show values in Home Assistant.
In desktop mode (running cyclic with lib/main.py) it performs a bit better.

## Installation of HA component

1. Clone this repo as `ph803w` dir into `$HA_CONFIG_DIR/custom_components/`
   ```
   $ cd custom_components
   $ git clone git@github.com:dala318/ph803w.git ./ph803w
   ```
2. Setup `$HA_CONFIG_DIR/configuration.yaml`

```yaml
ph803w:
  host: 192.168.1.2    # IP of your device
```
## Changelog
