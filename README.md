![Logo](ph803w.png)
# PH-803W
With a lot of inspiration and help from https://github.com/Apollon77/node-ph803w project I ported the basic functionallity to python with the hope and expectation to deploy it as an Home Assistant intagration without need for a docker service and MQTT.
Still a lot left to do but at least it can poll the device and show values in Home Assistant.
In desktop mode (running cyclic with lib/main.py) it performs a bit better.

# Installation

## Option 1: HACS
1. Go to HACS -> Integrations
2. Click the three dots on the top right and select `Custom Repositories`
3. Enter `https://github.com/dala318/python_ph803w` as repository, select the category `Integration` and click Add
4. A new custom integration shows up for installation (PH-803W) - install it
5. Restart Home Assistant

## Option 2: Manual

1. Copy the `ph803w` folder to HA `<config_dir>/custom_components/ph803w/`
2. Restart Home Assistant

# Configuration

Setup `$HA_CONFIG_DIR/configuration.yaml`

```yaml
ph803w:
  host: 192.168.1.2    # IP of your device
```
