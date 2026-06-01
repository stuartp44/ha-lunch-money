"""
Sensor platform for Lunch Money integration.
"""
import logging
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

METRIC_SENSORS = {
    "transactions_awaiting_review": {
        "name": "Transactions Awaiting Review",
        "icon": "mdi:clipboard-alert-outline",
    },
    "transactions_pending": {
        "name": "Pending Transactions",
        "icon": "mdi:clock-outline",
    },
    "transactions_delete_pending": {
        "name": "Transactions Delete Pending",
        "icon": "mdi:alert-outline",
    },
    "uncategorized_transactions_month": {
        "name": "Uncategorized Transactions (This Month)",
        "icon": "mdi:tag-off-outline",
    },
    "net_income_month": {
        "name": "Net Income (This Month)",
        "icon": "mdi:cash-plus",
    },
    "savings_rate_month": {
        "name": "Savings Rate (This Month)",
        "icon": "mdi:percent-outline",
        "unit": PERCENTAGE,
    },
    "last_transaction": {
        "name": "Last Transaction",
        "icon": "mdi:bank-transfer",
    },
}

BALANCE_TYPE_ICONS = {
    "cash": "mdi:cash-multiple",
    "credit": "mdi:credit-card-outline",
    "loan": "mdi:hand-coin-outline",
    "investment": "mdi:chart-line",
    "brokerage": "mdi:finance",
    "retirement": "mdi:bank-outline",
    "real estate": "mdi:home-city-outline",
    "cryptocurrency": "mdi:bitcoin",
    "other": "mdi:wallet-outline",
}


def _balance_icon(type_name: str) -> str:
    return BALANCE_TYPE_ICONS.get(type_name.strip().lower(), "mdi:wallet-outline")


def _currency_unit(coordinator):
    return coordinator.data.get("currency")

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
        self._attr_name = type_name
        self._attr_unique_id = f"lunch_money_{type_name.lower().replace(' ', '_')}"
        self._attr_native_unit_of_measurement = _currency_unit(coordinator)
        self._attr_icon = _balance_icon(type_name)

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
        unit = metadata.get("unit")
        if unit:
            self._attr_native_unit_of_measurement = unit
        elif metric_key == "last_transaction":
            self._attr_native_unit_of_measurement = _currency_unit(coordinator)
        elif metric_key == "net_income_month":
            self._attr_native_unit_of_measurement = _currency_unit(coordinator)

    @property
    def native_value(self):
        payload = self.coordinator.data.get("metrics", {}).get(self.metric_key)
        if isinstance(payload, dict) and "state" in payload:
            return payload.get("state")
        return payload

    @property
    def extra_state_attributes(self):
        payload = self.coordinator.data.get("metrics", {}).get(self.metric_key)
        if isinstance(payload, dict):
            attributes = payload.get("attributes")
            if isinstance(attributes, dict):
                return attributes
        return None
