"""Set up the MyIrving Propane Tank Tracker integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .api import MyIrvingClient
from .const import DOMAIN, ENTRY_TITLE
from .coordinator import MyIrvingCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one Irving Energy account from a config entry."""
    # Entries created before the generic title existed carry the account email
    # in the title; rewrite it in place so the UI never shows that address.
    if entry.title != ENTRY_TITLE:
        hass.config_entries.async_update_entry(entry, title=ENTRY_TITLE)

    # Credentials live in the config entry data and are only passed to the
    # client, which never logs them.
    client = MyIrvingClient(
        hass,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = MyIrvingCoordinator(hass, client, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        # A failed first refresh leaves no entities behind; release the socket
        # held by the requests session before Home Assistant retries setup.
        await client.async_close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and close its portal session."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    coordinator: MyIrvingCoordinator | None = hass.data.get(DOMAIN, {}).pop(
        entry.entry_id, None
    )
    if coordinator is not None:
        await coordinator.client.async_close()
        await coordinator.async_shutdown()
    return True
