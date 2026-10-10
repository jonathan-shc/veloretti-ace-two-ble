"""Bounded raw packet samples; no peripheral address or display serial."""

from dataclasses import asdict


async def async_get_config_entry_diagnostics(hass, entry):
    c = entry.runtime_data
    return {
        "version": "0.1.0",
        "experimental": True,
        "connected": c.connected,
        "live": c.live,
        "last_battery_read": c.last_seen.isoformat() if c.last_seen else None,
        "last_error": c.last_error,
        "data": asdict(c.data),
    }
