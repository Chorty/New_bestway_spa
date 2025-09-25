from __future__ import annotations

from aiohttp import ClientError, ClientResponseError
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .spa_api import authenticate

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry = None

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            unique_id = self._determine_unique_id(user_input)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)

            try:
                token = await authenticate(session, user_input)
            except ClientResponseError as err:
                if err.status == 401:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                if not token:
                    errors["base"] = "invalid_auth"

            if not errors:
                return self.async_create_entry(title=user_input["device_name"], data=user_input)

        schema = self._build_schema(user_input)

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, user_input=None):
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(self, user_input=None):
        assert self._reauth_entry is not None
        errors = {}
        current_data = dict(self._reauth_entry.data)

        if user_input is not None:
            updated = {**current_data, **user_input}
            session = async_get_clientsession(self.hass)

            try:
                token = await authenticate(session, updated)
            except ClientResponseError as err:
                if err.status == 401:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                if not token:
                    errors["base"] = "invalid_auth"

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data=updated,
                    title=updated["device_name"],
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            current_data = updated

        schema = self._build_schema(current_data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def _determine_unique_id(data):
        device_id = data.get(CONF_DEVICE_ID)
        if device_id:
            return device_id
        return f"{data['visitor_id']}_{data['registration_id']}"

    @staticmethod
    def _build_schema(defaults=None):
        defaults = defaults or {}
        return vol.Schema({
            vol.Required("device_name", default=defaults.get("device_name", "")): str,
            vol.Required("visitor_id", default=defaults.get("visitor_id", "")): str,
            vol.Required("registration_id", default=defaults.get("registration_id", "")): str,
            vol.Optional("device_id", default=defaults.get("device_id")): str,
            vol.Optional("product_id", default=defaults.get("product_id")): str,
            vol.Optional("push_type", default=defaults.get("push_type", "fcm")): vol.In(["fcm", "apns"]),
            vol.Optional("client_id", default=defaults.get("client_id")): str,
        })
