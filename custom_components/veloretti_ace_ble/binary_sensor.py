"""Live requires a connection and a recent decoded battery frame."""

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from .entity import AceEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            AceConnection(entry.runtime_data, "connectivity"),
            AceCharging(entry.runtime_data, "charging"),
            AceLights(entry.runtime_data, "lights"),
        ]
    )


class AceConnection(AceEntity, BinarySensorEntity):
    _attr_name = "Live batterijgegevens"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self):
        return self.coordinator.live


class AceCharging(AceEntity, BinarySensorEntity):
    """Experimental status: do not restore a stale charging flag after disconnect."""

    _attr_name = "Laden (experimenteel)"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    @property
    def available(self):
        return (
            self.coordinator.charging_available
            and self.coordinator.data.charging is not None
        )

    @property
    def is_on(self):
        return self.coordinator.data.charging


class AceLights(AceEntity, BinarySensorEntity):
    """Event-derived light status, unknown until observed in each connection."""

    _attr_name = "Verlichting (experimenteel)"
    _attr_device_class = BinarySensorDeviceClass.LIGHT

    @property
    def available(self):
        return self.coordinator.live and self.coordinator.data.lights is not None

    @property
    def is_on(self):
        return self.coordinator.data.lights
