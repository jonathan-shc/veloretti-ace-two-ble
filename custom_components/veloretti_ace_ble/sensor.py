"""Last known battery and measurement timestamp, restored across restarts."""

from datetime import datetime
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfSpeed
from .entity import AceEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            AceSensor(entry.runtime_data, "battery"),
            AceSensor(entry.runtime_data, "last_seen"),
            AceSensor(entry.runtime_data, "range"),
            AceSensor(entry.runtime_data, "speed"),
        ]
    )


class AceSensor(AceEntity, RestoreSensor):
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self.key = key
        self._restored = None
        if key == "battery":
            self._attr_name = "Batterij (experimenteel)"
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key == "speed":
            self._attr_name = "Snelheid (experimenteel)"
            self._attr_device_class = SensorDeviceClass.SPEED
            self._attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 1
        elif key == "range":
            self._attr_name = "Resterend bereik"
            self._attr_device_class = SensorDeviceClass.DISTANCE
            self._attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 0
        else:
            self._attr_name = "Laatste batterijmeting"
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None:
            value = last.native_value
            if self.key == "last_seen" and isinstance(value, datetime):
                self._restored = value
            elif (
                self.key == "battery"
                and isinstance(value, (int, float))
                and 0 <= value <= 100
            ):
                self._restored = value
            elif (
                self.key == "range"
                and isinstance(value, (int, float))
                and 0 <= value <= 655.35
            ):
                self._restored = value

    @property
    def available(self):
        if self.key == "speed":
            return self.coordinator.speed_available
        return True

    @property
    def native_value(self):
        value = {
            "battery": self.coordinator.data.battery_soc,
            "range": self.coordinator.data.range_km,
            "speed": self.coordinator.data.speed_kmh,
            "last_seen": self.coordinator.last_seen,
        }[self.key]
        return value if value is not None else self._restored
