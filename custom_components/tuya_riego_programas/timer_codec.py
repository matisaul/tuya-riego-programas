"""Codificación/decodificación del DP 38 (normal_timer) del riego Tuya.

Formato observado en el equipo (22 bytes por programa, sin cabecera):

  byte 0      ID del programa (lo asigna la app, estable)
  byte 1-2    hora de inicio en minutos (big endian)
  byte 3      configuración
                bits 0-1: 00 = desactivado, 01 = activado
                bits 2-3: 00 = zonas en secuencia, 01 = simultáneas
                bits 4-7: 0000 semanal, 0001 días impares, 0010 días pares
  byte 4      días (bit0 = domingo ... bit6 = sábado). 0 = una sola vez
  byte 5-9    reservado (se conserva tal cual)
  byte 10-21  duración en minutos por zona 1..12 (0 = zona sin riego)
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

RECORD_LEN = 22
ZONES_OFFSET = 10
ZONES_MAX = 12

DAY_NAMES = ["Do", "Lu", "Ma", "Mi", "Ju", "Vi", "Sá"]
CYCLE_NAMES = {0: "semanal", 1: "días impares", 2: "días pares"}
MODE_NAMES = {0: "secuencial", 1: "simultáneo"}


class TimerFormatError(ValueError):
    """El valor del DP no calza con el formato esperado."""


@dataclass
class Program:
    """Un programa de riego guardado en el equipo."""

    raw: bytearray

    @property
    def program_id(self) -> int:
        return self.raw[0]

    @property
    def start_minutes(self) -> int:
        return (self.raw[1] << 8) | self.raw[2]

    @property
    def start_time(self) -> str:
        m = self.start_minutes
        return f"{m // 60:02d}:{m % 60:02d}"

    @property
    def enabled(self) -> bool:
        return (self.raw[3] & 0x03) == 0x01

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.raw[3] = (self.raw[3] & 0xFC) | (0x01 if value else 0x00)

    @property
    def mode(self) -> str:
        return MODE_NAMES.get((self.raw[3] >> 2) & 0x03, "desconocido")

    @property
    def cycle(self) -> str:
        return CYCLE_NAMES.get((self.raw[3] >> 4) & 0x0F, "desconocido")

    @property
    def days_mask(self) -> int:
        return self.raw[4]

    @property
    def days(self) -> str:
        mask = self.days_mask
        if (self.raw[3] >> 4) & 0x0F:
            return self.cycle
        if mask == 0:
            return "Una vez"
        if mask & 0x7F == 0x7F:
            return "Todos los días"
        if mask & 0x7F == 0x3E:
            return "Lu-Vi"
        if mask & 0x7F == 0x41:
            return "Sá-Do"
        # Orden lunes..domingo
        order = [1, 2, 3, 4, 5, 6, 0]
        return " ".join(DAY_NAMES[i] for i in order if mask & (1 << i))

    @property
    def zones(self) -> dict[int, int]:
        """{zona: minutos} solo para zonas con riego configurado."""
        durs = self.raw[ZONES_OFFSET : ZONES_OFFSET + ZONES_MAX]
        return {i + 1: d for i, d in enumerate(durs) if d}

    @property
    def total_minutes(self) -> int:
        return sum(self.zones.values())

    def label(self, zone_names: dict[int, str] | None = None) -> str:
        zone_names = zone_names or {}
        zs = ", ".join(
            f"{zone_names.get(z, f'Z{z}')} {m} min" for z, m in self.zones.items()
        )
        return f"{self.start_time} · {self.days}" + (f" · {zs}" if zs else "")


def decode(value: str | None) -> list[Program]:
    """Convierte el base64 del DP en la lista de programas."""
    if not value:
        return []
    try:
        data = base64.b64decode(value)
    except (ValueError, TypeError) as err:
        raise TimerFormatError(f"normal_timer no es base64 válido: {err}") from err
    if len(data) % RECORD_LEN:
        raise TimerFormatError(
            f"normal_timer mide {len(data)} bytes, no es múltiplo de {RECORD_LEN}"
        )
    programs = [
        Program(bytearray(data[i : i + RECORD_LEN]))
        for i in range(0, len(data), RECORD_LEN)
    ]
    ids = [p.program_id for p in programs]
    if len(set(ids)) != len(ids):
        raise TimerFormatError(f"IDs de programa repetidos: {ids}")
    return programs


def encode(programs: list[Program]) -> str:
    """Vuelve a armar el base64 del DP, en el mismo orden."""
    return base64.b64encode(b"".join(bytes(p.raw) for p in programs)).decode()


def set_enabled(value: str, program_id: int, enabled: bool) -> str:
    """Devuelve el nuevo valor del DP con solo el switch del programa cambiado."""
    programs = decode(value)
    for prog in programs:
        if prog.program_id == program_id:
            prog.enabled = enabled
            return encode(programs)
    raise TimerFormatError(f"El programa {program_id} ya no existe en el equipo")
