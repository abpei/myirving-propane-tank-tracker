"""Data update coordinator for the MyIrving propane tank integration."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MyIrvingAuthError, MyIrvingClient, MyIrvingError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    MAX_SCAN_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_HOURS,
)
from .parser import TankData, parse_user_home

_LOGGER = logging.getLogger(__name__)


def scan_interval_to_timedelta(value: float | str | None) -> timedelta:
    """Convert an options value into a clamped polling interval."""
    hours = DEFAULT_SCAN_INTERVAL_HOURS
    if value is not None:
        try:
            hours = int(float(value))
        except (TypeError, ValueError):
            hours = DEFAULT_SCAN_INTERVAL_HOURS
    hours = max(MIN_SCAN_INTERVAL_HOURS, min(MAX_SCAN_INTERVAL_HOURS, hours))
    return timedelta(hours=hours)


class MyIrvingCoordinator(DataUpdateCoordinator[TankData]):
    """Poll the account portal and expose the parsed tank snapshot."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MyIrvingClient,
        entry: ConfigEntry,
    ) -> None:
        """Create a coordinator using the entry's configured polling interval."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=scan_interval_to_timedelta(
                entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS)
            ),
        )
        self.client = client

    async def _async_update_data(self) -> TankData:
        """Fetch the account home page and parse it into a tank snapshot."""
        try:
            document = await self.client.async_get_user_home()
        except MyIrvingAuthError as err:
            # Only the user can fix rejected credentials or an MFA wall, so the
            # coordinator surfaces this as an auth failure instead of a retry:
            # HA starts the reauth flow from it, both during setup and on a
            # later scheduled poll.
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except MyIrvingError as err:
            raise UpdateFailed(str(err)) from err

        # The client already parsed the response once; only the extraction runs
        # here, off the event loop because it is still CPU work.
        data = await self.hass.async_add_executor_job(parse_user_home, document)

        if data.percent_full is None and data.last_reading is None:
            raise UpdateFailed(
                "Tank gauge not found in the portal response "
                "(page layout may have changed)"
            )

        if None in (
            data.percent_full,
            data.last_reading,
            data.last_delivery_date,
            data.last_delivery_litres,
            data.todays_price,
        ):
            _LOGGER.debug(
                "Some tank values were missing from the portal response; "
                "their sensors will be unavailable until the next poll"
            )

        return data
