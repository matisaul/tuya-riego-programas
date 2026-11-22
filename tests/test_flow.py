from unittest.mock import patch
from homeassistant import config_entries
from custom_components.tuya_riego_programas.const import DOMAIN
from .test_sync import read_dps

async def test_config_and_options(hass):
    with patch("custom_components.tuya_riego_programas.device.detect_version", return_value="3.4"), \
         patch("custom_components.tuya_riego_programas.device.read_dps", read_dps):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {
            "name": "Riego Terraza", "device_id": "eb263", "host": "1.2.3.4", "local_key": "k",
            "protocol_version": "auto", "dp": 38})
        assert r["type"] == "create_entry", r
        assert r["data"]["protocol_version"] == "3.4" and "name" not in r["data"]
        await hass.async_block_till_done()
        entry = r["result"]
        r = await hass.config_entries.options.async_init(entry.entry_id)
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"scan_interval": 20, "zona_1": "Pasto Terraza"})
        assert r["data"] == {"scan_interval": 20, "zone_names": {"1": "Pasto Terraza"}}, r["data"]
