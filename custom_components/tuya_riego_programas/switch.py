"""Un switch por cada programa de riego guardado en la app Tuya/Smart Life."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CONF_ZONE_NAMES, DOMAIN
from .coordinator import RiegoCoordinator


def _unique_id(dev_id: str, program_id: int) -> str:
    return f"{dev_id}_programa_{program_id}"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: RiegoCoordinator = hass.data[DOMAIN][entry.entry_id]
    registry = er.async_get(hass)
    known: dict[int, ProgramSwitch] = {}

    @callback
    def _sync() -> None:
        if not coordinator.last_update_success or coordinator.data is None:
            return  # sin datos confiables: no crear ni borrar nada
        current = set(coordinator.data)

        # Programas nuevos en la app -> switch nuevo
        new = [ProgramSwitch(coordinator, entry, pid) for pid in current - set(known)]
        for ent in new:
            known[ent.program_id] = ent
        if new:
            async_add_entities(new)

        # Programas borrados en la app -> se elimina la entidad de HA
        for pid in set(known) - current:
            known.pop(pid)
        valid = {_unique_id(coordinator.dev_id, pid) for pid in current}
        for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
            if reg.domain == "switch" and reg.unique_id not in valid:
                registry.async_remove(reg.entity_id)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))


class ProgramSwitch(CoordinatorEntity[RiegoCoordinator], SwitchEntity):
    """Activa/desactiva un programa sin modificar sus horarios ni zonas."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:sprinkler-variant"

    def __init__(self, coordinator: RiegoCoordinator, entry: ConfigEntry, program_id: int) -> None:
        super().__init__(coordinator)
        self.program_id = program_id
        self._entry = entry
        self._attr_unique_id = _unique_id(coordinator.dev_id, program_id)
        # entity_id estable aunque cambie la hora del programa en la app
        self.entity_id = f"switch.{slugify(entry.title)}_programa_{program_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.dev_id)},
            name=entry.title,
            manufacturer="Tuya",
            model="Riego WiFi (programas)",
        )

    @property
    def _program(self):
        return (self.coordinator.data or {}).get(self.program_id)

    @property
    def _zone_names(self) -> dict[int, str]:
        raw = {**self._entry.data, **self._entry.options}.get(CONF_ZONE_NAMES, {}) or {}
        return {int(k): v for k, v in raw.items() if v}

    @property
    def available(self) -> bool:
        return super().available and self._program is not None

    @property
    def name(self) -> str:
        prog = self._program
        return f"Programa {prog.label(self._zone_names)}" if prog else f"Programa {self.program_id}"

    @property
    def is_on(self) -> bool | None:
        prog = self._program
        return prog.enabled if prog else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        prog = self._program
        if not prog:
            return {}
        names = self._zone_names
        return {
            "id_programa": prog.program_id,
            "hora_inicio": prog.start_time,
            "dias": prog.days,
            "ciclo": prog.cycle,
            "modo": prog.mode,
            "zonas": {names.get(z, f"Zona {z}"): m for z, m in prog.zones.items()},
            "duracion_total_min": prog.total_minutes,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_program_enabled(self.program_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_program_enabled(self.program_id, False)
