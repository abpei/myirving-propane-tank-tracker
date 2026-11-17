# Tests

Pytest suite for the MyIrving Propane Tank Tracker. The current tests cover the
pure HTML parser in `custom_components/myirving_propane/parser.py`; no Home
Assistant install or running container is required, because the parser is plain
Python plus BeautifulSoup and `tests/conftest.py` registers a lightweight package
shell so the HA-dependent component `__init__.py` is never executed.

## Running the tests

```bash
uv venv .venv --python 3.14
uv pip install -r requirements-test.txt
.venv/bin/python -m pytest
```

Any environment with `pytest` and `beautifulsoup4` works too, for example
`python -m pytest` from the repository root. `pytest.ini` sets
`testpaths = tests`, so no path arguments are needed.

## The scrubbed fixture

`tests/fixtures/user_home_scrubbed.html` is the page the tests run against. It
reproduces the structure verified against the live portal on 2026-11-17:

- `div#tank_gauge_summary` -> `Percent in tank: 61%`, `Last Reading: 11/15/2026`
- Account summary table, in the live bootstrap layout: one header row of `th`
  cells carrying `data-field` names (`Product Name`, `Delivery Prov/State`,
  `Last Delivery Date`, `Last Delivery Litres`, `Today&rsquo;s Price`) followed
  by one bare `td` data row with the matching values (`EC Propane`, `PE`,
  `04/12/2026 4:00am`, `442.00`, `$0.99`). The parser maps header labels to
  column indexes and reads only the wanted columns, so a change of column order
  or extra columns does not affect it.

Those five values are the expected sensor values in `tests/test_parser.py`
(`EXPECTED_*` constants), so a fixture refresh and a parser expectation change
have to happen together.

Provenance note: the raw portal capture was not retained in this repository.
It carried account identifiers, and the live login sits behind a credential
boundary (credentials are entered by the user in the HA config flow and are
never available to workers). The committed fixture is therefore a structural
replica built from the documented scrape facts: same element id, same table
labels, same values, synthetic identifiers. When a fresh raw capture is
available, replace this file with a properly scrubbed copy and update the
`EXPECTED_*` constants plus the placeholder list below.

## Scrubbing rules (hard requirement)

Raw HTML from the portal must never be committed. It is gitignored via:

- `tests/fixtures/raw/` for captures dropped in that directory
- `*.unscrubbed.html` for captures named that way anywhere in the tree

Before promoting a capture into `tests/fixtures/user_home_scrubbed.html`:

1. Replace the customer name, service address, postal code, email address,
   account number, tank serial, phone number, meter or device identifiers, and
   every session id, csrf token, or hidden form value.
2. Use reserved placeholders: `Jane Doe`, `123 Example Street`,
   `Exampleville, NS A1A 1A1`, `jane.doe@example.com`, `support@example.com`,
   `0000000`, `TANK-0000000`, `(000) 000-0000`.
3. Keep the structural markup and values the parser depends on (the
   `tank_gauge_summary` div, the account summary table labels and values).
4. Run `pytest`. These tests enforce the policy: `test_fixture_uses_only_reserved_identifiers`
   rejects non `@example.com` addresses and non zero long digit runs,
   `test_fixture_keeps_obvious_placeholders` keeps the placeholders present,
   `test_fixture_has_no_credential_fields` rejects password/login fields, and
   `test_gitignore_blocks_unscrubbed_fixture_drops` keeps the ignore rules in
   place.

## What is covered

- All five scrape values from the fixture, plus per-field assertions.
- Missing gauge element, missing table, empty input, unclosed markup, and every
  truncation of the fixture (parser must return `TankData`, never raise).
- Percentage edge cases: 0, 100, decimals, missing space, non breaking space,
  out of range, non numeric.
- Date and time edge cases: one digit month/day, two digit year, invalid dates,
  date-only values, 12am/12pm, 24 hour times, out of range times.
- Numeric edge cases: currency symbols, thousands separators, unit suffixes,
  non numeric values.
- Table header/column mapping: header row split from the data row, curly
  apostrophe and `data-field` labels, column order, duplicate header columns,
  extra ignored columns, missing optional columns, short data row, missing data
  row, an unrelated table before the account table, and the legacy label/value
  pair layout kept as a fallback.
- Label matching: case, padding, trailing colon, US `Liters` spelling, nested
  markup in header and data cells.
- Login page detection for the session-expiry path.
- `TankData` immutability.
- Fixture scrub guarantees listed above.

## CI

`.github/workflows/validate.yml` runs this suite in a dedicated `pytest` job that
installs `requirements-test.txt`. No Home Assistant dependency is needed there.
