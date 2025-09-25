from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
import asyncio

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    device_id = entry.title.lower().replace(' ', '_') 
    async_add_entities([
        BestwaySpaTargetTemperature(coordinator, api, entry.title, device_id)
    ])

class BestwaySpaTargetTemperature(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, api, title, device_id):
        super().__init__(coordinator)
        self._api = api
        self._attr_name = f"{title} Target Temperature"
        self._attr_unique_id = f"{device_id}_temperature_setting"
        self._device_id = device_id
        self._attr_native_min_value = 20.0
        self._attr_native_max_value = 40.0
        self._attr_native_step = 0.5
        self._attr_native_unit_of_measurement = "°C"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._attr_name.split(" ")[0],  # lub np. self._device_id
            "manufacturer": "Bestway",
            "model": "Spa",
            "sw_version": self.hass.data[DOMAIN].get("manifest_version", "unknown")
        }

    @property
    def native_value(self):
        return self.coordinator.data.get("temperature_setting")

    async def async_set_native_value(self, value: float):
        target_value = int(round(value))
        await self._api.set_state("temperature_setting", target_value)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
