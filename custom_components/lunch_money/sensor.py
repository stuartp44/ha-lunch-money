"""
Sensor platform for Lunch Money integration.
"""
import logging
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CURRENCY_DOLLAR
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

METRIC_SENSORS = {
    "transactions_awaiting_review": {
        "name": "Lunch Money Transactions Awaiting Review",
        "icon": "mdi:clipboard-alert-outline",
    },
    "transactions_pending": {
        "name": "Lunch Money Pending Transactions",
        "icon": "mdi:clock-outline",
    },
    "transactions_delete_pending": {
        "name": "Lunch Money Transactions Delete Pending",
        "icon": "mdi:alert-outline",
    },
    "uncategorized_transactions_month": {
        "name": "Lunch Money Uncategorized Transactions (This Month)",
        "icon": "mdi:tag-off-outline",
    },
}

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    # Not used with config entries
    return

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Lunch Money sensors from a config entry using DataUpdateCoordinator."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    async def async_update_data():
        return await api.async_get_dashboard_data()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Lunch Money Data",
        update_method=async_update_data,
        update_interval=timedelta(hours=1),
    )

    await coordinator.async_config_entry_first_refresh()

    balance_types = coordinator.data.get("balances", {}).keys()
    sensors = [
        LunchMoneyBalanceSensor(coordinator, type_name)
        for type_name in balance_types
    ]
    sensors.extend(
        LunchMoneyMetricSensor(coordinator, metric_key)
        for metric_key in METRIC_SENSORS
    )
    async_add_entities(sensors, True)

class LunchMoneyBalanceSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, type_name):
        super().__init__(coordinator)
        self.type_name = type_name
        self._attr_name = f"Lunch Money {type_name}"
        self._attr_unique_id = f"lunch_money_{type_name.lower().replace(' ', '_')}"
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR

    @property
    def native_value(self):
        return self.coordinator.data.get("balances", {}).get(self.type_name)


class LunchMoneyMetricSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, metric_key):
        super().__init__(coordinator)
        self.metric_key = metric_key
        metadata = METRIC_SENSORS[metric_key]
        self._attr_name = metadata["name"]
        self._attr_unique_id = f"lunch_money_{metric_key}"
        self._attr_icon = metadata["icon"]

    @property
    def native_value(self):
        return self.coordinator.data.get("metrics", {}).get(self.metric_key)
