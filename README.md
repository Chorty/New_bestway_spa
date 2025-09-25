## Bestway Smart Spa (Custom Component)

This Home Assistant integration allows you to control your Bestway SmartHub-enabled spa via the Bestway cloud API.

---

## Installation

1. Copy the `new_bestway_spa/` folder into `custom_components/` in your Home Assistant configuration directory.
2. Restart Home Assistant.
3. Go to **Settings > Devices & Services** and click **Add Integration**.
4. Search for **Bestway Spa** and follow the configuration flow.

---

## Prerequisites

### Required Equipment
- A **PC or Mac** with [Charles Proxy](https://www.charlesproxy.com/download/) installed
- Two smartphones (Android or iOS):
  - **Phone A**: with the Bestway Smart Hub app installed and already connected to your spa (used to share the QR code)
  - **Phone B**: used to capture traffic through Charles Proxy (the SSL certificate will be installed on this device)

### Network
- PC and both smartphones must be connected to the **same Wi-Fi network**

---

## Option A – Automated capture workflow

If you prefer a scripted approach, use the toolkit in [`tools/traffic_capture/`](tools/traffic_capture/) to launch a pre-configured [mitmproxy](https://mitmproxy.org/) instance and capture traffic without touching the Charles UI. The short version:

1. Run `docker compose up -d` inside `tools/traffic_capture/` (customise ports as required).
2. Install the interception certificate from `http://mitm.it` on the capture phone.
3. Configure the phone's Wi-Fi proxy to the machine running Docker.
4. Complete the Bestway login/QR pairing flow — flows are saved under `tools/traffic_capture/data/` and can be exported as HAR from the mitmproxy UI.
5. Feed the exported HAR (or a Charles `.chlsj` export) into [`tools/extract_credentials.py`](tools/extract_credentials.py) to pull out the Home Assistant credentials automatically:

   ```bash
   ./tools/extract_credentials.py tools/traffic_capture/data/session.har -o credentials.json
   ```

   The script prints the extracted identifiers and writes them to `credentials.json` for reuse in the config flow.

The classic manual Charles Proxy workflow is still documented below if you do not wish to use Docker.

## Option B – Manual capture with Charles Proxy

### Step 1 – Setup Charles Proxy

1. Launch **Charles Proxy** on your PC
2. Go to `Proxy > Proxy Settings` and note the HTTP port (default: `8888`)
3. Go to `Help > SSL Proxying > Install Charles Root Certificate` (install it on your PC)

---

## Step 2 – Configure Phone B

### A. Set Wi-Fi Proxy
- On **Phone B**, go to Wi-Fi settings
- Long press the connected network > Modify > Advanced options
- Set Proxy to **Manual**:
  - **Proxy host**: your PC’s IP address
  - **Port**: `8888`

### B. Install SSL Certificate
> Required to decrypt HTTPS traffic

#### Android (to be confirmed)
- Visit `http://charlesproxy.com/getssl` on Phone B
- Download the certificate
- Install it: `Settings > Security > Encryption & credentials > Install from storage`

#### iOS
- Open Safari: [https://chls.pro/ssl](https://chls.pro/ssl)
- Accept and install the profile
- Go to: `Settings > General > VPN & Device Management > Charles Proxy CA`
- Enable in: `Settings > General > About > Certificate Trust Settings`

---

## Step 3 – Enable SSL Proxying

In Charles:
1. Go to `Proxy > SSL Proxying Settings`
2. Click **Add**
3. Set:
   - Host: `*`
   - Port: `443`

---

## Step 4 – Capture the Data

# ⚠️*It is important to follow these steps in this direction in order to recover all the necessary identifiers.*

1. Start recording in Charles (click the **●** button)
2. Install the Bestway Smart Hub app on **Phone B**
3. Open the Bestway Smart Hub
4. Select **United Kingdom** region and scan the QR code
5. Watch for requests like `thing_shadow`, `command`, or to `api.bestwaycorp`

---

## Step 5 – Retrieve Credentials

1. **Automated**: Run `./tools/extract_credentials.py <capture-file>` and copy the generated values into Home Assistant. The script flags the request path that produced each identifier so you can verify the result in your proxy export.
2. **Manual**: Look for a **POST** request to `/enduser/visitor` on [https://smarthub-eu.bestwaycorp.com](https://smarthub-eu.bestwaycorp.com) and check **Request > JSON** or **Text**.

### Useful credentials to extract (manual method)
- `visitor_id`
- `client_id` (for Android)
- `device_id`
- `product_id`

### Additional (manual method)
- `registration_id` and `client_id` can be found in `/api/enduser/visitor`
- `device_id` and `product_id` may be in `/api/enduser/home/room/devices`

---

## Cleanup

- Disable the proxy on Phone B
- Remove the Charles SSL certificate if no longer needed



---

## Configuration Options

| Field            | Required | Notes                                      |
|------------------|----------|--------------------------------------------|
| `device_name`    | ✅       | Display name in Home Assistant             |
| `visitor_id`     | ✅       | From intercepted app traffic               |
| `registration_id`| ✅       | Same as above                              |
| `client_id`      | ❌       | Only for Android (`push_type = fcm`)       |
| `device_id`      | ✅       | Needed to control the spa                  |
| `product_id`     | ✅       | Needed to control the spa                  |
| `push_type`      | ❌       | `fcm` (Android) or `apns` (iOS), default `fcm` |

---

## API Notes

- `filter_state` returns `2` when active, `0` when off — the integration handles this automatically.
- `select` gives the possibility to choose  the bubble/wave mode OFF/L1/L2 (not available from the official app)
- To **turn on** any feature, the integration sends `1`. To **turn off**, it sends `0`.
- All values are polled from `/api/device/thing_shadow/`

---

## Features

- Toggle spa power, filter, heater, and wave jets
- Adjust water target temperature
- View current water temperature
- Monitor connection status, warnings, and error codes

---

## Example Lovelace Card
![image](https://github.com/user-attachments/assets/e551d76e-e72a-432e-aec0-8da2fa5e751a)

```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.spa_thermostat
    name: Chauffage Spa
  - type: horizontal-stack
    cards:
      - type: button
        name: Chauffage ON
        icon: mdi:fire
        tap_action:
          action: call-service
          service: climate.set_hvac_mode
          target:
            entity_id: climate.spa_thermostat
          data:
            hvac_mode: heat
      - type: button
        name: Chauffage OFF
        icon: mdi:power
        tap_action:
          action: call-service
          service: climate.set_hvac_mode
          target:
            entity_id: climate.spa_thermostat
          data:
            hvac_mode: "off"
  - type: history-graph
    title: Historique Température Spa
    hours_to_show: 24
    refresh_interval: 60
    entities:
      - entity: sensor.spa_water_temperature
  - type: entities
    title: Commandes Spa
    show_header_toggle: false
    entities:
      - entity: switch.spa_spa_power
        name: Alimentation Spa
        icon: mdi:power
      - entity: switch.spa_filter
        name: Filtration
        icon: mdi:air-filter
      - entity: select.spa_bulles
        name: Bulles
        icon: mdi:chart-bubble

```

## Disclaimer
This is a community-made integration. It is not affiliated with or endorsed by Bestway.
Use at your own risk — the code interacts with a private API which may change.
