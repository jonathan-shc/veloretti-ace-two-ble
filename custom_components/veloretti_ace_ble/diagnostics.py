"""Bounded raw packet samples; no peripheral address or display serial."""

from dataclasses import asdict
from homeassistant.loader import async_get_integration


async def async_get_config_entry_diagnostics(hass, entry):
    c = entry.runtime_data
    integration = await async_get_integration(hass, entry.domain)
    return {
        "version": integration.manifest.get("version"),
        "experimental": True,
        "connected": c.connected,
        "live": c.live,
        "last_battery_read": c.last_seen.isoformat() if c.last_seen else None,
        "last_error": c.last_error,
        "data": asdict(c.data),
        "capture": c.capture.snapshot(),
    }
