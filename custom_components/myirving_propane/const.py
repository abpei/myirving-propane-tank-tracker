"""Constants for the MyIrving Propane Tank Tracker integration."""

from typing import Final

DOMAIN: Final = "myirving_propane"
# The entry title is rendered in the Home Assistant UI, so it stays generic:
# the account email lives only in entry data and is never used as a label.
ENTRY_TITLE: Final = "MyIrving Propane Tank"
DEVICE_NAME: Final = ENTRY_TITLE

# Portal endpoints. The login page is a server rendered PHP form and the
# account data lives on /user-home behind a session cookie.
BASE_URL: Final = "https://myaccount.irvingenergy.com"
LOGIN_URL: Final = f"{BASE_URL}/"
USER_HOME_URL: Final = f"{BASE_URL}/user-home"

# Portal form field names, verified against the live portal on 2026-11-17.
LOGIN_FIELD_EMAIL: Final = "email_check"
LOGIN_FIELD_PASSWORD: Final = "password_check"
LOGIN_FIELD_SUBMIT: Final = "cmdLogin"

# The account table labels the integration reads. Matching is done on the
# normalized label text, or on a header cell's data-field attribute when the
# portal provides one, never on row position.
ACCOUNT_LABEL_DELIVERY_DATE: Final = "last delivery date"
ACCOUNT_LABEL_DELIVERY_LITRES: Final = "last delivery litres"
ACCOUNT_LABEL_DELIVERY_LITRES_US: Final = "last delivery liters"
ACCOUNT_LABEL_TODAYS_PRICE: Final = "today's price"

# Element id that carries the tank gauge summary on /user-home.
TANK_GAUGE_ID: Final = "tank_gauge_summary"

# Text fragments that indicate an interactive challenge page. They are only
# consulted when no login form is present, so ordinary help text on the login
# page cannot trigger a false positive.
MFA_MARKERS: Final = (
    "verification code",
    "verify your identity",
    "one-time passcode",
    "one time passcode",
    "authenticator code",
    "multi-factor authentication is required",
    "two-factor authentication is required",
)

CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_SCAN_INTERVAL_HOURS: Final = 6
MIN_SCAN_INTERVAL_HOURS: Final = 1
MAX_SCAN_INTERVAL_HOURS: Final = 24

# Portal responses are ~37 KB of HTML; 30 s is generous without hanging setup.
REQUEST_TIMEOUT: Final = 30

# The portal may reject requests from the default python-requests user agent.
USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Sensor keys are stable identifiers: they are used for unique IDs and
# translation keys, so they must not change between releases.
SENSOR_KEY_TANK_PERCENT: Final = "tank_percent"
SENSOR_KEY_LAST_READING: Final = "last_reading"
SENSOR_KEY_LAST_DELIVERY_DATE: Final = "last_delivery_date"
SENSOR_KEY_LAST_DELIVERY_LITRES: Final = "last_delivery_litres"
SENSOR_KEY_TODAYS_PRICE: Final = "todays_price"
