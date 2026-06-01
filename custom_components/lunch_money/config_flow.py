"""
Config flow for Lunch Money integration.
"""
import logging

from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError
from lunchmoney.exceptions import ApiException
import voluptuous as vol

from .api import LunchMoneyAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def validate_input(api_key: str) -> dict:
    """Validate the user input allows us to connect."""
    api = LunchMoneyAPI(api_key)
    try:
        me = await api.async_get_me()
    except ApiException as err:
        if getattr(err, "status", None) in {401, 403}:
            raise InvalidAuth from err
        _LOGGER.warning("Unable to connect to Lunch Money API: %s", err)
        raise CannotConnect from err
    except Exception as err:
        _LOGGER.warning("Unexpected Lunch Money API error: %s", err)
        raise CannotConnect from err
    finally:
        await api.async_close()

    me_id = getattr(me, "id", None)
    return {
        "title": "Lunch Money",
        "unique_id": f"{DOMAIN}_{me_id}" if me_id else DOMAIN,
    }

class LunchMoneyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(user_input["api_key"])
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("api_key"): str
            }),
            errors=errors
        )
