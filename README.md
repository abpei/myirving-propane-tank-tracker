# MyIrving Propane Tank Tracker

![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.11%2B-03a9f4.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

A Home Assistant custom integration that turns the propane tank data in an
Irving Energy MyIrving residential account into five sensors. It signs in to
[myaccount.irvingenergy.com](https://myaccount.irvingenergy.com/) with the email
address and password you already use, reads your own account page, and keeps
that data inside your Home Assistant instance.

This integration is unofficial. See [Disclaimer](#disclaimer).

## Sensors

One service device named **MyIrving Propane Tank** carries five entities:

| Sensor | Entity id suffix | Unit or type | Reports |
|---|---|---|---|
| Tank level | `myirving_propane_tank_tank_level` | `%` | Tank capacity used at the last monitor reading |
| Last reading | `myirving_propane_tank_last_reading` | date | Date of the last tank monitor reading |
| Last delivery date | `myirving_propane_tank_last_delivery_date` | date | Date of the last delivery |
| Last delivery volume | `myirving_propane_tank_last_delivery_volume` | `L` | Litres delivered on that delivery |
| Today's price | `myirving_propane_tank_today_s_price` | `$` | Price per litre as posted for the current day |

The values come from the same page you see when you sign in to the portal.
Tank level and last delivery volume carry `state_class: measurement`; the two
dates use `device_class: date` and report ISO dates (`2026-11-16`).

Each sensor is refreshed together on every poll. When the portal omits a field,
only that sensor becomes `unavailable`, and it returns with the next poll that
contains the value. The integration does not invent or hold a stale value.

### Entity ids

Home Assistant builds each entity id from the device name and the entity name,
and it prefixes the id with the area the device is assigned to. The part that
is stable across installations is the device prefix
`myirving_propane_tank_` shown in the table above. If the device is assigned to
an area called Garage, Home Assistant prepends that area name to the id (for
example `sensor.` followed by `garage_` and the device prefix), so the same
sensor can have a different full id in another installation.

Use the `myirving_propane_tank_` part, or the entity picker, when you write
automations and dashboards. Do not copy a full entity id from another
installation, because the area prefix will differ. The apostrophe in
"Today's price" is slugified by Home Assistant, which is why the price entity
id contains `today_s_price`. Entity ids can be renamed in the UI if you prefer
a different scheme.

### Why the price unit is `$` and not `$/L`

The price sensor reports **dollars per litre**, the same number the portal
shows (for example `0.99` means 0.99 dollars per litre). The unit is the
currency alone because Home Assistant has no money-per-volume unit: its
monetary device class only allows `state_class: total`, which does not fit a
price measurement and would block long-term statistics.

The unit and state class follow the Home Assistant core fuel-price convention,
where the currency is the unit and the state class is `measurement`. History
and long-term statistics therefore work normally. Read the state as a rate per
litre, not as a total, and add a template sensor or a unit label in your
dashboard if you need the rate to be explicit.

## Requirements

- Home Assistant 2026.11.0 or newer.
- HACS, or the ability to copy files into your configuration directory.
- An Irving Energy MyIrving residential account that can sign in at the portal.
- An account without multi factor authentication. MFA and verification
  challenge pages are not supported and are reported as an authentication
  error.

## Installation

### HACS custom repository (recommended)

1. Open HACS, open the menu in the top right corner, and choose **Custom
   repositories**.
2. Enter `https://github.com/abpei/myirving-propane-tank-tracker` and choose
   category **Integration**, then add the repository.
3. Search HACS for **MyIrving Propane Tank Tracker** and install it.
4. Restart Home Assistant.

### Manual installation

1. Copy the `custom_components/myirving_propane` directory from this repository
   into `<config>/custom_components/`.
2. Restart Home Assistant.

The Python dependency (`beautifulsoup4`) is declared in `manifest.json`, so
Home Assistant installs it during setup.

## Configuration

1. Go to **Settings > Devices & services > Add integration**.
2. Search for and select **MyIrving Propane Tank Tracker**.
3. Enter the email address and password for the portal account.
4. Optionally change the polling interval. The default is 6 hours, the minimum
   is 1 hour, and the maximum is 24 hours.
5. Submit the form.

The integration validates the credentials before it creates the entry by
signing in and fetching the account page. If the portal rejects the email and
password, the form reports an authentication error and no entry is created. If
the portal cannot be reached, it reports a connection error instead.

The entry is titled **MyIrving Propane Tank**. The title is deliberately
generic: the email address is stored only in the config entry data, is never
logged, and is never used as a label, so screenshots, diagnostics, and support
threads do not expose it. The password is stored in the config entry data as
well and is never written to the log.

### Options

Select **Configure** on the integration entry to change the polling interval
between 1 and 24 hours. Credentials are not requested again. To use a different
account email, remove the integration and add it again.

Six hours is the default because tank monitor readings usually arrive once a
day or two, and the portal is polled by scraping a page. A lower interval
increases the load on the portal without producing new readings.

### Sessions and reauthentication

The client keeps a portal session and reuses its cookie between polls. If the
session expires, the integration signs in again automatically and retries the
request once, without interrupting the sensors. If the portal rejects the
stored password, for example because it was changed on the website, Home
Assistant starts a reauthentication flow: enter the new password once, the
integration verifies it, updates the stored entry data, and reloads the entry.
The account email, the entry, and the polling options stay unchanged.

### Privacy and data flow

The integration contacts only `myaccount.irvingenergy.com`. Credentials, request
bodies, and portal HTML are never written to the Home Assistant log. The values
read from your account page become ordinary sensor states inside your Home
Assistant instance, where they are handled like any other entity history.

## Troubleshooting

- **Authentication error while adding the integration**: the email or password
  was rejected, or the account needs multi factor authentication. Sign in at
  the portal in a browser to confirm the credentials and check whether a
  verification code is requested.
- **Connection error**: the portal could not be reached. Check the network and
  try again later.
- **One sensor is unavailable**: the portal did not provide that value on the
  last poll. Other sensors keep updating, and the missing one normally returns
  with a later poll.
- **All sensors unavailable**: the portal was unreachable, the session could
  not be renewed, or the page layout changed. Check the Home Assistant log; a
  layout change is reported as a missing tank gauge or a missing table value.
- **Values do not change**: the portal itself updates readings only when a new
  monitor reading or delivery is posted. An unchanged value is not a failed
  poll; the coordinator log line `Finished fetching myirving_propane data`
  records each successful scrape.

To see debug messages for the integration, add this to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.myirving_propane: debug
```

The integration never logs credentials, request bodies, or portal HTML.

## Development and testing

The parser is plain Python plus BeautifulSoup, so the test suite runs without a
Home Assistant installation or a running container.

```bash
uv venv .venv --python 3.14
uv pip install -r requirements-test.txt
.venv/bin/python -m pytest
.venv/bin/ruff check custom_components tests
.venv/bin/ruff format --check custom_components tests
```

The suite contains 87 pytest tests in `tests/test_parser.py`, driven by
`tests/fixtures/user_home_scrubbed.html`, a scrubbed structural replica of the
portal's `/user-home` page. Coverage includes all five scrape values, every
truncation of the fixture, malformed and partial markup, percentage, date and
number edge cases, table header and column mapping, login page detection, and
the scrub guarantees listed below.

### The scrubbed fixture and scrub rules

Raw portal HTML contains account identifiers and must never be committed. The
repository ignores `tests/fixtures/raw/` and any file named `*.unscrubbed.html`.
A capture is promoted into `tests/fixtures/user_home_scrubbed.html` only after
the customer name, address, postal code, email address, account number, tank
serial, phone number, meter and device identifiers, session ids, CSRF tokens,
and hidden form values have been replaced with the reserved placeholders
documented in [tests/README.md](tests/README.md). The tests enforce the policy:
they reject non `@example.com` addresses and non zero long digit runs, require
the reserved placeholders to be present, reject credential fields, and check
that the gitignore rules still block unscrubbed drops.

When a fresh live capture becomes available, follow the promotion procedure in
[tests/README.md](tests/README.md): scrub the copy, replace the fixture, and
update the `EXPECTED_*` constants in `tests/test_parser.py` in the same change.

### Continuous integration

`.github/workflows/validate.yml` runs five jobs on pushes to `main`, on pull
requests, and on a daily schedule: a compile gate on Python 3.13 and 3.14,
ruff lint and format checks, HACS validation, hassfest validation, and the
pytest suite.

## Disclaimer

This integration is unofficial and is not affiliated with, endorsed by, or
supported by Irving Oil Limited. It works by signing in to the Irving Energy
residential account portal with credentials you provide in the config flow,
and by reading the page that the portal renders for your own account. Use of
this integration must comply with the terms of service of the portal. The
portal is a scrape target, so a layout change can break the integration until
it is updated.

## License

MIT. See [LICENSE](LICENSE).
