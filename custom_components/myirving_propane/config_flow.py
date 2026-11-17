"""Config and options flows for the MyIrving Propane Tank Tracker integration."""

from collections.abc import Mapping
import logging
from typing import Any

import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import MyIrvingAuthError, MyIrvingClient, MyIrvingError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    ENTRY_TITLE,
    MAX_SCAN_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_HOURS,
)
from .coordinator import MyIrvingCoordinator, scan_interval_to_timedelta

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="username",
            )
        ),
        probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
        probatio.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_HOURS
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_SCAN_INTERVAL_HOURS,
                max=MAX_SCAN_INTERVAL_HOURS,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="h",
            )
        ),
    }
)


STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


def _scan_interval_schema(default: float) -> probatio.Schema:
    """Build the options schema for the polling interval."""
    return probatio.Schema(
        {
            probatio.Optional(CONF_SCAN_INTERVAL, default=default): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL_HOURS,
                    max=MAX_SCAN_INTERVAL_HOURS,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="h",
                )
            )
        }
    )


class MyIrvingPropaneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial account setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for portal credentials and verify them before creating the entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = str(user_input[CONF_USERNAME]).strip()
            password = str(user_input[CONF_PASSWORD])
            client = MyIrvingClient(self.hass, username, password)

            try:
                # A full fetch proves the credentials work and that the portal
                # still serves the page the parser depends on.
                await client.async_get_user_home()
            except MyIrvingAuthError:
                errors["base"] = "invalid_auth"
            except MyIrvingError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unexpected error while validating MyIrving portal credentials"
                )
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(username.casefold())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=ENTRY_TITLE,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                    options={
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS
                        )
                    },
                )
            finally:
                await client.async_close()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication when the portal rejects the stored password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password, verify it, then update the existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        username = str(entry.data[CONF_USERNAME])

        if user_input is not None:
            password = str(user_input[CONF_PASSWORD])
            client = MyIrvingClient(self.hass, username, password)

            try:
                # Verify the new password with the same full fetch the initial
                # setup uses, so a wrong password never replaces a working one.
                await client.async_get_user_home()
            except MyIrvingAuthError:
                errors["base"] = "invalid_auth"
            except MyIrvingError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unexpected error while validating MyIrving portal credentials"
                )
                errors["base"] = "unknown"
            else:
                # Only the password changes: the entry, its unique id and its
                # options stay intact and the entry is reloaded afterwards.
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: password},
                )
            finally:
                await client.async_close()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"username": username},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow for an existing entry."""
        return MyIrvingPropaneOptionsFlow()


class MyIrvingPropaneOptionsFlow(OptionsFlow):
    """Allow the polling interval to change without re-entering credentials."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the polling interval."""
        if user_input is not None:
            coordinator: MyIrvingCoordinator | None = self.hass.data.get(
                DOMAIN, {}
            ).get(self.config_entry.entry_id)
            if coordinator is not None:
                coordinator.update_interval = scan_interval_to_timedelta(
                    user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS)
                )
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS
        )
        default_hours = scan_interval_to_timedelta(current).total_seconds() / 3600
        return self.async_show_form(
            step_id="init",
            data_schema=_scan_interval_schema(default_hours),
        )
