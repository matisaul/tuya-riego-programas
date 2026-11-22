"""Acceso local (LAN) al riego vía tinytuya. Todas las funciones son bloqueantes."""
from __future__ import annotations

import time

import tinytuya


class TuyaLocalError(Exception):
    """Error de comunicación local con el equipo."""


def _device(dev_id: str, host: str, local_key: str, version: str) -> tinytuya.Device:
    dev = tinytuya.Device(
        dev_id,
        address=host,
        local_key=local_key,
        version=float(version),
        connection_timeout=5,
        connection_retry_limit=2,
        connection_retry_delay=1,
    )
    dev.set_socketPersistent(False)
    return dev


def read_dps(dev_id: str, host: str, local_key: str, version: str, dp: int) -> dict:
    """Lee el estado. Si el DP de programas no viene, lo pide explícitamente."""
    dev = _device(dev_id, host, local_key, version)
    data = dev.status()
    if not data or "Error" in data:
        raise TuyaLocalError((data or {}).get("Error", "sin respuesta"))
    dps = dict(data.get("dps", {}))
    if str(dp) not in dps:
        dev.set_socketPersistent(True)
        dev.updatedps([dp])
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            msg = dev.receive()
            if msg and "dps" in msg:
                dps.update(msg["dps"])
                if str(dp) in dps:
                    break
        dev.close()
    return dps


def write_dp(dev_id: str, host: str, local_key: str, version: str, dp: int, value) -> None:
    dev = _device(dev_id, host, local_key, version)
    res = dev.set_value(dp, value)
    if res and isinstance(res, dict) and "Error" in res:
        raise TuyaLocalError(res["Error"])


def detect_version(dev_id: str, host: str, local_key: str, versions: list[str]) -> str:
    """Prueba versiones de protocolo hasta que una responda con datos."""
    last = "sin respuesta"
    for ver in versions:
        try:
            dev = _device(dev_id, host, local_key, ver)
            data = dev.status()
            if data and "dps" in data:
                return ver
            last = (data or {}).get("Error", last)
        except Exception as err:  # noqa: BLE001
            last = str(err)
    raise TuyaLocalError(last)
