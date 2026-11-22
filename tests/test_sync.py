import base64
from unittest.mock import patch
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er
from custom_components.tuya_riego_programas.const import DOMAIN

P1 = "AQTdAX8AAAAAAAQAAAAAAAAAAAAAAA=="
TWO = "AQTdAX8AAAAAAAQAAAAAAAAAAAAAAAIBaAECAAAAAAABAAAAAAAAAAAAAAA="
fake = {"v": TWO, "writes": []}

def read_dps(*a): return {"1": False, "38": fake["v"]}
def write_dp(dev, host, key, ver, dp, value):
    fake["writes"].append(value); fake["v"] = value

async def test_flow(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="Riego Terraza", data={
        "device_id": "eb263", "host": "1.2.3.4", "local_key": "k",
        "protocol_version": "3.4", "dp": 38}, options={"zone_names": {"1": "Pasto Terraza"}})
    entry.add_to_hass(hass)
    with patch("custom_components.tuya_riego_programas.device.read_dps", read_dps), \
         patch("custom_components.tuya_riego_programas.device.write_dp", write_dp), \
         patch("asyncio.sleep", return_value=None):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        states = {s.entity_id: s for s in hass.states.async_all("switch")}
        print({k: (v.state, v.name) for k, v in states.items()})
        assert len(states) == 2
        eid1 = er.async_get(hass).async_get_entity_id("switch", DOMAIN, "eb263_programa_1")
        await hass.services.async_call("switch", "turn_off", {"entity_id": eid1}, blocking=True)
        await hass.async_block_till_done()
        assert fake["writes"][-1] == "AQTdAH8AAAAAAAQAAAAAAAAAAAAAAAIBaAECAAAAAAABAAAAAAAAAAAAAAA="
        assert hass.states.get(eid1).state == "off"
        # borrar programa 2 en la app
        fake["v"] = P1
        coord = hass.data[DOMAIN][entry.entry_id]
        await coord.async_refresh(); await hass.async_block_till_done()
        assert len(hass.states.async_all("switch")) == 1
        assert er.async_get(hass).async_get_entity_id("switch", DOMAIN, "eb263_programa_2") is None
        # nuevo programa 3
        raw = bytearray(base64.b64decode(P1)); raw[0] = 3; raw[1:3] = (420).to_bytes(2, "big")
        fake["v"] = base64.b64encode(base64.b64decode(P1) + bytes(raw)).decode()
        await coord.async_refresh(); await hass.async_block_till_done()
        print({s.entity_id: (s.state, s.name, s.attributes.get("zonas")) for s in hass.states.async_all("switch")})
        assert len(hass.states.async_all("switch")) == 2
        # error de lectura no borra entidades
        def boom(*a):
            from custom_components.tuya_riego_programas.device import TuyaLocalError
            raise TuyaLocalError("offline")
        with patch("custom_components.tuya_riego_programas.device.read_dps", boom):
            await coord.async_refresh(); await hass.async_block_till_done()
        assert len(hass.states.async_all("switch")) == 2
        assert all(s.state == "unavailable" for s in hass.states.async_all("switch"))
