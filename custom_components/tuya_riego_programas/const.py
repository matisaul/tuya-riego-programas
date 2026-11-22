"""Constantes de Tuya Riego Programas."""

DOMAIN = "tuya_riego_programas"

CONF_DEVICE_ID = "device_id"
CONF_HOST = "host"
CONF_LOCAL_KEY = "local_key"
CONF_PROTOCOL = "protocol_version"
CONF_DP = "dp"
CONF_ZONE_NAMES = "zone_names"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_DP = 38  # normal_timer
DEFAULT_SCAN_INTERVAL = 15  # segundos (conexión local, sin cuota de API)
PROTOCOLS = ["3.5", "3.4", "3.3", "3.1"]
