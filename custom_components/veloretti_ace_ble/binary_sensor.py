"""Live requires a connection and a recent decoded battery frame."""

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from .entity import AceEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([AceConnection(entry.runtime_data, "connectivity")])


class AceConnection(AceEntity, BinarySensorEntity):
    _attr_name = "Live batterijgegevens"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self):
        return self.coordinator.live
