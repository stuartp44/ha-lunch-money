"""
Home Assistant custom integration for Lunch Money.
"""
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .api import LunchMoneyAPI

async def async_setup_entry(hass, entry):
    """Set up Lunch Money from a config entry."""
    api_key = entry.data["api_key"]
    api = LunchMoneyAPI(api_key)

    try:
        await api.async_get_balances()
    except Exception as err:
        await api.async_close()
        raise ConfigEntryNotReady(f"Unable to set up Lunch Money integration: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"api": api}
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass, entry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        await entry_data["api"].async_close()
    return unload_ok
