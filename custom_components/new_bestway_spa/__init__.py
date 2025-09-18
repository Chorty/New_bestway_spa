from datetime import timedelta
import logging

from aiohttp import ClientError, ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .spa_api import BestwaySpaAPI, authenticate

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "number", "sensor", "climate", "select", "button"]
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bestway Spa from a config entry."""

    session = async_get_clientsession(hass)

    try:
        token = await authenticate(session, entry.data)
    except ClientResponseError as err:
        if err.status == 401:
            raise ConfigEntryAuthFailed("Invalid credentials") from err
        raise ConfigEntryNotReady("Error communicating with Bestway Spa API") from err
    except ClientError as err:
        raise ConfigEntryNotReady("Error communicating with Bestway Spa API") from err

    if not token:
        raise ConfigEntryAuthFailed("Authentication failed: No token returned")

    api = BestwaySpaAPI(session, entry.data, token)

    async def async_update_data():
        try:
            return await api.get_status()
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error fetching spa data: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Bestway Spa",
        update_method=async_update_data,
        update_interval=timedelta(seconds=60),
    )

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "credentials": dict(entry.data),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
