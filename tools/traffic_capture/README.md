# Automated Traffic Capture Toolkit

This directory packages a reusable [mitmproxy](https://mitmproxy.org/) environment that mirrors the manual Charles Proxy walkthrough from the root `README`. It exposes a ready-to-use HTTPS interception proxy plus a lightweight web UI for inspecting captured requests.

## Prerequisites

- Docker Engine 20.10+ with Docker Compose V2
- Your desktop/laptop and the mobile device that will run the Bestway app must share the same Wi-Fi network.

## Quick start

```bash
cd tools/traffic_capture
MITMPROXY_PORT=8080 MITMWEB_PORT=8081 docker compose up -d
```

The command launches `mitmweb` listening on `0.0.0.0:<MITMPROXY_PORT>` for proxy traffic and exposes the web inspector on `http://localhost:<MITMWEB_PORT>`.

> The default ports (`8080` and `8081`) are chosen to avoid conflicts with the README's Charles defaults. Adjust them with environment variables if required.

Once the container is running:

1. Visit `http://<docker-host>:8081/` in a desktop browser to open mitmproxy's web UI.
2. Click **?** (Help) → **Install Certificate** to download the interception certificate. Alternatively, fetch it directly from the proxy with `http://mitm.it` on the mobile device.
3. Follow the platform-specific prompts on the device to trust the certificate system-wide.
4. On the mobile device, edit the connected Wi-Fi network and configure the proxy host to your desktop's IP with port `8080` (or your custom value).
5. Open the Bestway Smart Hub app and complete the pairing/login flow. Requests will appear in the mitmproxy UI, and a replayable stream is saved under `tools/traffic_capture/data/session.mitm`.

### Stopping the capture

```bash
docker compose down
```

Captured sessions remain in `data/` so you can parse them later. Remove the directory if you no longer need the recordings.

## Exporting captured sessions

The mitmproxy UI allows exporting sessions as HAR files via **File → Export → Export all flows**. Save the HAR into the project root or directly into `tools/traffic_capture/data/` and feed it into the credential extractor described below.

## Advanced usage

- To rotate certificates without rebuilding the container, delete `data/` and restart the stack.
- Add `--set upstream_cert=false` to the command in `docker-compose.yml` if you encounter servers with certificate pinning issues.
- Enable transparent mode by supplying your own command override if you prefer routing traffic without configuring Wi-Fi proxies.
