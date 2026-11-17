"""Sensor platform for the MyIrving Propane Tank Tracker integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_DOLLAR, PERCENTAGE, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BASE_URL,
    DEVICE_NAME,
    DOMAIN,
    SENSOR_KEY_LAST_DELIVERY_DATE,
    SENSOR_KEY_LAST_DELIVERY_LITRES,
    SENSOR_KEY_LAST_READING,
    SENSOR_KEY_TANK_PERCENT,
    SENSOR_KEY_TODAYS_PRICE,
)
from .coordinator import MyIrvingCoordinator
from .parser import TankData


@dataclass(frozen=True, kw_only=True)
class MyIrvingSensorEntityDescription(SensorEntityDescription):
    """A sensor description plus the function that reads its value."""

    value_fn: Callable[[TankData], StateType | date]


SENSOR_DESCRIPTIONS: tuple[MyIrvingSensorEntityDescription, ...] = (
    MyIrvingSensorEntityDescription(
        key=SENSOR_KEY_TANK_PERCENT,
        translation_key=SENSOR_KEY_TANK_PERCENT,
        icon="mdi:propane-tank",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.percent_full,
    ),
    MyIrvingSensorEntityDescription(
        key=SENSOR_KEY_LAST_READING,
        translation_key=SENSOR_KEY_LAST_READING,
        icon="mdi:calendar-check",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda data: data.last_reading,
    ),
    MyIrvingSensorEntityDescription(
        key=SENSOR_KEY_LAST_DELIVERY_DATE,
        translation_key=SENSOR_KEY_LAST_DELIVERY_DATE,
        icon="mdi:truck-delivery",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda data: (
            data.last_delivery_date.date() if data.last_delivery_date else None
        ),
    ),
    MyIrvingSensorEntityDescription(
        key=SENSOR_KEY_LAST_DELIVERY_LITRES,
        translation_key=SENSOR_KEY_LAST_DELIVERY_LITRES,
        icon="mdi:gas-cylinder",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.last_delivery_litres,
    ),
    MyIrvingSensorEntityDescription(
        key=SENSOR_KEY_TODAYS_PRICE,
        translation_key=SENSOR_KEY_TODAYS_PRICE,
        icon="mdi:cash",
        # HA has no unit for a money-per-volume rate and its MONETARY device class
        # only permits state class TOTAL, which would block statistics for a
        # measurement. Core fuel-price sensors (e.g. tankerkoenig) therefore carry
        # the currency as the unit with state class measurement; the value stays
        # dollars per litre, as the portal reports it.
        native_unit_of_measurement=CURRENCY_DOLLAR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.todays_price,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the five propane sensors for one account."""
    coordinator: MyIrvingCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MyIrvingSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class MyIrvingSensor(CoordinatorEntity[MyIrvingCoordinator], SensorEntity):
    """A propane value reported by the Irving Energy account portal."""

    entity_description: MyIrvingSensorEntityDescription

    def __init__(
        self,
        coordinator: MyIrvingCoordinator,
        entry: ConfigEntry,
        description: MyIrvingSensorEntityDescription,
    ) -> None:
        """Attach the entity to the shared coordinator and its device."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer="Irving Energy",
            model="Residential account portal",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=BASE_URL,
        )

    @property
    def native_value(self) -> StateType | date:
        """Return the current value, or None when the portal omitted it."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Report unavailable when the field is missing rather than showing unknown."""
        return super().available and self.native_value is not None
