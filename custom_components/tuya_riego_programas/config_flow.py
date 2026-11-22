"""Config flow: conexión local al riego y nombres de zonas."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from . import device, timer_codec
from .const import (
    CONF_DEVICE_ID,
    CONF_DP,
    CONF_HOST,
    CONF_LOCAL_KEY,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    CONF_ZONE_NAMES,
    DEFAULT_DP,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PROTOCOLS,
)

AUTO = "auto"
ZONES = range(1, 13)


class RiegoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()
            args = (user_input[CONF_DEVICE_ID], user_input[CONF_HOST], user_input[CONF_LOCAL_KEY])
            try:
                ver = user_input[CONF_PROTOCOL]
                if ver == AUTO:
                    ver = await self.hass.async_add_executor_job(
                        device.detect_version, *args, PROTOCOLS
                    )
                dps = await self.hass.async_add_executor_job(
                    device.read_dps, *args, ver, user_input[CONF_DP]
                )
                value = dps.get(str(user_input[CONF_DP]))
                if value is None:
                    errors["base"] = "dp_missing"
                else:
                    timer_codec.decode(value)
            except device.TuyaLocalError:
                errors["base"] = "cannot_connect"
            except timer_codec.TimerFormatError:
                errors["base"] = "bad_format"
            if not errors:
                data = {**user_input, CONF_PROTOCOL: ver}
                name = data.pop("name")
                return self.async_create_entry(title=name, data=data)

        schema = vol.Schema(
            {
                vol.Required("name", default="Riego Terraza"): str,
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_LOCAL_KEY): str,
                vol.Required(CONF_PROTOCOL, default=AUTO): vol.In([AUTO, *PROTOCOLS]),
                vol.Required(CONF_DP, default=DEFAULT_DP): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(entry):
        return RiegoOptionsFlow()


class RiegoOptionsFlow(config_entries.OptionsFlow):
    """Nombres de zonas e intervalo de lectura."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            zone_names = {
                str(z): user_input.pop(f"zona_{z}").strip()
                for z in ZONES
                if user_input.get(f"zona_{z}", "").strip()
            }
            for z in ZONES:
                user_input.pop(f"zona_{z}", None)
            return self.async_create_entry(
                data={**user_input, CONF_ZONE_NAMES: zone_names}
            )

        opts = self.config_entry.options
        names = opts.get(CONF_ZONE_NAMES, {})
        fields: dict[Any, Any] = {
            vol.Required(
                CONF_SCAN_INTERVAL, default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
        }
        for z in ZONES:
            fields[vol.Optional(f"zona_{z}", default=names.get(str(z), ""))] = str
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields))
