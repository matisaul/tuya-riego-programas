"""Coordinator: lee el DP de programas y expone la lista decodificada."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import device, timer_codec
from .const import (
    CONF_DEVICE_ID,
    CONF_DP,
    CONF_HOST,
    CONF_LOCAL_KEY,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    DEFAULT_DP,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class RiegoCoordinator(DataUpdateCoordinator[dict[int, timer_codec.Program]]):
    """Mantiene {program_id: Program} sincronizado con el equipo."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        cfg = {**entry.data, **entry.options}
        self.dev_id: str = cfg[CONF_DEVICE_ID]
        self.host: str = cfg[CONF_HOST]
        self.local_key: str = cfg[CONF_LOCAL_KEY]
        self.version: str = cfg[CONF_PROTOCOL]
        self.dp: int = int(cfg.get(CONF_DP, DEFAULT_DP))
        self.raw_value: str | None = None
        self._lock = asyncio.Lock()
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.dev_id}",
            update_interval=timedelta(
                seconds=int(cfg.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            ),
        )

    async def _read_value(self) -> str:
        dps = await self.hass.async_add_executor_job(
            device.read_dps, self.dev_id, self.host, self.local_key, self.version, self.dp
        )
        if str(self.dp) not in dps:
            raise device.TuyaLocalError(
                f"El equipo no reportó el DP {self.dp}. DPs recibidos: {sorted(dps)}"
            )
        return dps[str(self.dp)] or ""

    async def _async_update_data(self) -> dict[int, timer_codec.Program]:
        try:
            value = await self._read_value()
            programs = timer_codec.decode(value)
        except (device.TuyaLocalError, timer_codec.TimerFormatError, OSError) as err:
            raise UpdateFailed(str(err)) from err
        self.raw_value = value
        return {p.program_id: p for p in programs}

    async def async_set_program_enabled(self, program_id: int, enabled: bool) -> None:
        """Lee el valor vigente, cambia solo el switch de ese programa y lo escribe."""
        async with self._lock:
            try:
                current = await self._read_value()
                new_value = timer_codec.set_enabled(current, program_id, enabled)
                if new_value != current:
                    await self.hass.async_add_executor_job(
                        device.write_dp,
                        self.dev_id,
                        self.host,
                        self.local_key,
                        self.version,
                        self.dp,
                        new_value,
                    )
            except (device.TuyaLocalError, timer_codec.TimerFormatError, OSError) as err:
                raise HomeAssistantError(f"No se pudo cambiar el programa: {err}") from err
        await asyncio.sleep(1)
        await self.async_request_refresh()
