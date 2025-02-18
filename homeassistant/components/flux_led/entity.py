"""Support for Magic Home lights."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any

from flux_led.aiodevice import AIOWifiLedBulb

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FluxLedUpdateCoordinator
from .const import CONF_MINOR_VERSION, CONF_MODEL, SIGNAL_STATE_UPDATED


def _async_device_info(
    unique_id: str, device: AIOWifiLedBulb, entry: config_entries.ConfigEntry
) -> DeviceInfo:
    version_num = device.version_num
    if minor_version := entry.data.get(CONF_MINOR_VERSION):
        sw_version = version_num + int(hex(minor_version)[2:]) / 100
        sw_version_str = f"{sw_version:0.3f}"
    else:
        sw_version_str = str(device.version_num)
    return DeviceInfo(
        connections={(dr.CONNECTION_NETWORK_MAC, unique_id)},
        manufacturer="Zengge",
        model=device.model,
        name=entry.data[CONF_NAME],
        sw_version=sw_version_str,
        hw_version=entry.data.get(CONF_MODEL),
    )


class FluxBaseEntity(Entity):
    """Representation of a Flux entity without a coordinator."""

    def __init__(
        self,
        device: AIOWifiLedBulb,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Initialize the light."""
        self._device: AIOWifiLedBulb = device
        self.entry = entry
        if entry.unique_id:
            self._attr_device_info = _async_device_info(
                entry.unique_id, self._device, entry
            )


class FluxEntity(CoordinatorEntity):
    """Representation of a Flux entity with a coordinator."""

    coordinator: FluxLedUpdateCoordinator

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._device: AIOWifiLedBulb = coordinator.device
        self._responding = True
        self._attr_name = name
        self._attr_unique_id = unique_id
        if unique_id:
            self._attr_device_info = _async_device_info(
                unique_id, self._device, coordinator.entry
            )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the attributes."""
        return {"ip_address": self._device.ipaddr}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.last_update_success != self._responding:
            self.async_write_ha_state()
        self._responding = self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_STATE_UPDATED.format(self._device.ipaddr),
                self.async_write_ha_state,
            )
        )
        await super().async_added_to_hass()


class FluxOnOffEntity(FluxEntity):
    """Representation of a Flux entity that supports on/off."""

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified device on."""
        await self._async_turn_on(**kwargs)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @abstractmethod
    async def _async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified device on."""

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the specified device off."""
        await self._device.async_turn_off()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
