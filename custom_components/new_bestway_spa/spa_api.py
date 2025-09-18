from __future__ import annotations

import hashlib
import logging
import random
import string
import time
from typing import Any, Dict

from aiohttp import ClientError, ClientResponseError, ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed

_LOGGER = logging.getLogger(__name__)


class BestwaySpaError(Exception):
    """Raised when the Bestway Spa API returns an error response."""


async def authenticate(session: ClientSession, config: dict) -> str | None:
    BASE_URL = "https://smarthub-eu.bestwaycorp.com"
    APPID = "AhFLL54HnChhrxcl9ZUJL6QNfolTIB"
    APPSECRET = "4ECvVs13enL5AiYSmscNjvlaisklQDz7vWPCCWXcEFjhWfTmLT"

    def generate_auth():
        nonce = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
        ts = str(int(time.time()))
        sign = hashlib.md5((APPID + APPSECRET + nonce + ts).encode("utf-8")).hexdigest().upper()
        return nonce, ts, sign

    push_type = config.get("push_type", "fcm")

    payload = {
        "app_id": APPID,
        "lan_code": "en",
        "location": "GB",
        "push_type": push_type,
        "timezone": "GMT",
        "visitor_id": config["visitor_id"],
        "registration_id": config["registration_id"]
    }

    if push_type == "fcm":
        client_id = config.get("client_id")
        if not client_id:
            _LOGGER.error("Client ID is required when using FCM push type")
            return None
        payload["client_id"] = client_id

    nonce, ts, sign = generate_auth()
    headers = {
        "pushtype": push_type,
        "appid": APPID,
        "nonce": nonce,
        "ts": ts,
        "accept-language": "en",
        "sign": sign,
        "Authorization": "token",
        "Host": "smarthub-eu.bestwaycorp.com",
        "Connection": "Keep-Alive",
        "User-Agent": "okhttp/4.9.0",
        "Content-Type": "application/json; charset=UTF-8"
    }

    _LOGGER.debug("Authenticating with payload: %s", payload)

    async with session.post(
        f"{BASE_URL}/api/enduser/visitor",
        headers=headers,
        json=payload,
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()

    _LOGGER.debug("Auth response: %s", data)

    if isinstance(data, dict):
        code = data.get("code")
        if code not in (None, 0, "0"):
            _LOGGER.error("Authentication failed with API response: %s", data)
            return None

    return data.get("data", {}).get("token") if isinstance(data, dict) else None


class BestwaySpaAPI:
    BASE_URL = "https://smarthub-eu.bestwaycorp.com"
    APPID = "AhFLL54HnChhrxcl9ZUJL6QNfolTIB"
    APPSECRET = "4ECvVs13enL5AiYSmscNjvlaisklQDz7vWPCCWXcEFjhWfTmLT"

    def __init__(self, session: ClientSession, config: dict, token: str) -> None:
        self.session = session
        self._credentials = dict(config)
        self.token = token
        self.device_id = config.get("device_id") or config["device_name"]
        self.product_id = config.get("product_id") or config["device_name"]
        self.client_id = config.get("client_id")
        self.registration_id = config.get("registration_id")
        self.push_type = config.get("push_type", "fcm")

    def _generate_auth_headers(self):
        nonce = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
        ts = str(int(time.time()))
        sign = hashlib.md5((self.APPID + self.APPSECRET + nonce + ts).encode("utf-8")).hexdigest().upper()
        return {
            "pushtype": self.push_type,
            "appid": self.APPID,
            "nonce": nonce,
            "ts": ts,
            "accept-language": "en",
            "sign": sign,
            "Authorization": f"token {self.token}",
            "Host": "smarthub-eu.bestwaycorp.com",
            "Connection": "Keep-Alive",
            "User-Agent": "okhttp/4.9.0",
            "Content-Type": "application/json; charset=UTF-8"
        }

    async def _refresh_token(self) -> None:
        try:
            new_token = await authenticate(self.session, self._credentials)
        except ClientResponseError as err:
            if err.status == 401:
                raise ConfigEntryAuthFailed("Invalid credentials") from err
            raise ConfigEntryAuthFailed("Failed to refresh authentication token") from err
        except ClientError as err:
            raise ConfigEntryAuthFailed("Failed to refresh authentication token") from err

        if not new_token:
            raise ConfigEntryAuthFailed("Authentication failed during token refresh")

        self.token = new_token
        _LOGGER.debug("Successfully refreshed Bestway Spa API token")

    async def _post(self, endpoint: str, payload: Dict[str, Any], *, attempt_refresh: bool = True) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{endpoint}"
        headers = self._generate_auth_headers()

        try:
            async with self.session.post(url, headers=headers, json=payload) as resp:
                try:
                    resp.raise_for_status()
                except ClientResponseError as err:
                    if err.status == 401:
                        if attempt_refresh:
                            await self._refresh_token()
                            return await self._post(endpoint, payload, attempt_refresh=False)
                        raise ConfigEntryAuthFailed("Authentication failed") from err
                    raise
                data = await resp.json()
        except ClientResponseError as err:
            if err.status == 401:
                raise ConfigEntryAuthFailed("Authentication failed") from err
            raise
        except ClientError as err:
            raise BestwaySpaError("Error communicating with Bestway Spa API") from err

        return self._validate_response(data)

    @staticmethod
    def _validate_response(data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise BestwaySpaError("Unexpected response from Bestway Spa API")

        code = data.get("code")
        if code not in (None, 0, "0"):
            message = data.get("msg") or data.get("message") or "Unknown error"
            if str(code) == "401":
                raise ConfigEntryAuthFailed(message)
            raise BestwaySpaError(f"API error {code}: {message}")

        return data.get("data", {}) if "data" in data else data

    async def get_status(self):
        payload = {
            "device_id": self.device_id,
            "product_id": self.product_id
        }

        _LOGGER.debug("Sending get_status payload: %s", payload)

        data = await self._post("/api/device/thing_shadow/", payload)
        _LOGGER.debug("Full API response: %s", data)

        raw_data = data
        _LOGGER.debug("Raw data from API: %s", raw_data)

        if "state" in raw_data:
            if "reported" in raw_data["state"]:
                device_state = raw_data["state"]["reported"]
                _LOGGER.debug("Found reported state: %s", device_state)
            elif "desired" in raw_data["state"]:
                device_state = raw_data["state"]["desired"]
                _LOGGER.debug("Found desired state: %s", device_state)
            else:
                device_state = raw_data["state"]
                _LOGGER.debug("Found state object: %s", device_state)
        else:
            device_state = raw_data

        mapped = {
            "wifi_version": device_state.get("wifivertion"),
            "ota_status": device_state.get("otastatus"),
            "mcu_version": device_state.get("mcuversion"),
            "trd_version": device_state.get("trdversion"),
            "connect_type": device_state.get("ConnectType"),
            "power_state": device_state.get("power_state"),
            "heater_state": device_state.get("heater_state"),
            "wave_state": device_state.get("wave_state"),
            "filter_state": device_state.get("filter_state"),
            "temperature_setting": device_state.get("temperature_setting"),
            "temperature_unit": device_state.get("temperature_unit"),
            "water_temperature": device_state.get("water_temperature"),
            "warning": device_state.get("warning"),
            "error_code": device_state.get("error_code"),
            "hydrojet_state": device_state.get("hydrojet_state"),
            "is_online": device_state.get("is_online"),
        }

        _LOGGER.debug("Normalized data: %s", mapped)
        return mapped

    async def set_state(self, key, value):
        if isinstance(value, bool):
            value = int(value)
        elif isinstance(value, (int, float)):
            value = int(round(value))

        payload = {
            "device_id": self.device_id,
            "product_id": self.product_id,
            "desired": {
                "state": {
                    "desired": {
                        key: value
                    }
                }
            }
        }

        _LOGGER.debug("Sending set_state payload: %s", payload)

        response = await self._post("/api/device/command/", payload)
        _LOGGER.debug("set_state response: %s", response)
        return response
