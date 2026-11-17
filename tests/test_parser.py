"""Unit tests for the pure /user-home HTML parser.

Expected values come from the verified 2026-11-17 scrape facts. Every case runs
against the scrubbed fixture or a minimal inline snippet shaped like the parts of
the portal page the parser anchors on: ``div#tank_gauge_summary`` and the
bootstrap account table (a header row of ``th`` cells followed by one bare
``td`` data row).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import FrozenInstanceError
from datetime import date, datetime
from pathlib import Path
import re

from bs4 import BeautifulSoup
import pytest

from custom_components.myirving_propane.parser import (
    TankData,
    is_login_page,
    parse_account_table,
    parse_tank_gauge,
    parse_user_home,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Expected values from the live /user-home scrape of 2026-11-17.
EXPECTED_PERCENT = 61
EXPECTED_LAST_READING = date(2026, 11, 15)
EXPECTED_DELIVERY_DATE = datetime(2026, 4, 12, 4, 0)
EXPECTED_DELIVERY_LITRES = 442.0
EXPECTED_PRICE = 0.99

# Matches any address shaped token; the fixture must only contain reserved names.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LONG_DIGITS_RE = re.compile(r"\d{7,}")


def _gauge(inner: str) -> str:
    """Wrap gauge text in the portal's summary div so the parser can find it."""
    return (
        '<html><body><div id="tank_gauge_summary" class="text-center">'
        f"{inner}</div></body></html>"
    )


def _column_table(headers: Sequence[str], values: Sequence[str]) -> str:
    """Build the live table shape: a th header row then one bare td data row.

    Every header cell carries ``data-field`` equal to its visible text, which is
    how the portal's bootstrap table names its columns.
    """
    header_cells = "".join(
        f'<th data-field="{header}">{header}</th>' for header in headers
    )
    body = (
        f"<tr>{''.join(f'<td>{value}</td>' for value in values)}</tr>" if values else ""
    )
    return (
        "<html><body><table><thead>"
        f"<tr>{header_cells}</tr>"
        f"</thead><tbody>{body}</tbody></table></body></html>"
    )


def _single_column(label: str, value: str) -> str:
    """Build a one column live layout table for a single label and value."""
    return _column_table([label], [value])


def _table(*rows: tuple[str, str]) -> str:
    """Build the legacy label/value table with one pair per row."""
    body = "".join(
        f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in rows
    )
    return f"<html><body><table><tbody>{body}</tbody></table></body></html>"


def _delivery_date(value: str) -> datetime | None:
    """Parse one Last Delivery Date cell through the public table extractor."""
    return parse_account_table(_single_column("Last Delivery Date", value))[
        "last_delivery_date"
    ]


def _litres(value: str) -> float | None:
    """Parse one Last Delivery Litres cell through the public table extractor."""
    return parse_account_table(_single_column("Last Delivery Litres", value))[
        "last_delivery_litres"
    ]


def _price(value: str) -> float | None:
    """Parse one Today's Price cell through the public table extractor."""
    return parse_account_table(_single_column("Today's Price", value))["todays_price"]


# --- Fixture driven happy path -------------------------------------------------


def test_parse_user_home_matches_whole_scraped_snapshot(user_home_html: str) -> None:
    """The scrubbed page parses into one snapshot with all five scrape facts."""
    assert parse_user_home(user_home_html) == TankData(
        percent_full=EXPECTED_PERCENT,
        last_reading=EXPECTED_LAST_READING,
        last_delivery_date=EXPECTED_DELIVERY_DATE,
        last_delivery_litres=EXPECTED_DELIVERY_LITRES,
        todays_price=EXPECTED_PRICE,
    )


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("percent_full", EXPECTED_PERCENT),
        ("last_reading", EXPECTED_LAST_READING),
        ("last_delivery_date", EXPECTED_DELIVERY_DATE),
        ("last_delivery_litres", EXPECTED_DELIVERY_LITRES),
        ("todays_price", EXPECTED_PRICE),
    ],
    ids=[
        "tank_percentage",
        "last_reading_date",
        "last_delivery_date",
        "last_delivery_litres",
        "todays_price",
    ],
)
def test_parse_user_home_extracts_each_scraped_value(
    user_home_html: str, field: str, expected: object
) -> None:
    """Each of the five sensor values is extracted independently from the page."""
    assert getattr(parse_user_home(user_home_html), field) == expected


def test_parse_tank_gauge_block(user_home_html: str) -> None:
    """The gauge extractor returns only the gauge block's two values."""
    assert parse_tank_gauge(user_home_html) == {
        "percent_full": EXPECTED_PERCENT,
        "last_reading": EXPECTED_LAST_READING,
    }


def test_parse_account_table_block(user_home_html: str) -> None:
    """The table extractor returns the delivery and price values."""
    assert parse_account_table(user_home_html) == {
        "last_delivery_date": EXPECTED_DELIVERY_DATE,
        "last_delivery_litres": EXPECTED_DELIVERY_LITRES,
        "todays_price": EXPECTED_PRICE,
    }


def test_curly_apostrophe_label_is_matched(user_home_html: str) -> None:
    """The portal's Today&rsquo;s Price label normalizes to the ASCII label key."""
    assert "Today&rsquo;s Price" in user_home_html
    assert parse_user_home(user_home_html).todays_price == EXPECTED_PRICE


def test_fixture_uses_live_two_row_table_layout(user_home_html: str) -> None:
    """The fixture reproduces the header row plus bare data row of the portal."""
    soup = BeautifulSoup(user_home_html, "html.parser")
    table = soup.find("table", class_="table-striped")
    assert table is not None
    rows = table.find_all("tr")
    assert len(rows) == 2

    header = [cell.get("data-field") for cell in rows[0].find_all("th")]
    assert header == [
        "Product Name",
        "Delivery Prov/State",
        "Last Delivery Date",
        "Last Delivery Litres",
        "Today\u2019s Price",
    ]
    assert [cell.get_text(strip=True) for cell in rows[1].find_all("td")] == [
        "EC Propane",
        "PE",
        "04/12/2026 4:00am",
        "442.00",
        "$0.99",
    ]


# --- Missing or broken markup --------------------------------------------------


def test_missing_gauge_div_returns_none_values() -> None:
    """A page without the gauge element yields Nones instead of raising."""
    assert parse_tank_gauge("<html><body><table></table></body></html>") == {
        "percent_full": None,
        "last_reading": None,
    }


def test_missing_account_table_returns_none_values() -> None:
    """A page without the summary table yields Nones instead of raising."""
    assert parse_account_table("<html><body></body></html>") == {
        "last_delivery_date": None,
        "last_delivery_litres": None,
        "todays_price": None,
    }


def test_empty_html_returns_default_snapshot() -> None:
    """Empty input produces an all None snapshot, matching TankData defaults."""
    assert parse_user_home("") == TankData()
    assert parse_user_home("   \n\t ") == TankData()


def test_unclosed_gauge_markup_does_not_raise() -> None:
    """Malformed, unclosed HTML is tolerated by the parser."""
    data = parse_user_home(
        '<div id="tank_gauge_summary">Percent in tank: 61% Last Reading: 11/15/2026'
    )
    assert data.percent_full == EXPECTED_PERCENT
    assert data.last_reading == EXPECTED_LAST_READING


def test_truncated_fixture_never_raises(user_home_html: str) -> None:
    """Parsing every truncation of the fixture returns a snapshot, never an error."""
    for cut in range(0, len(user_home_html), 200):
        assert isinstance(parse_user_home(user_home_html[:cut]), TankData)


# --- Tank gauge parsing rules --------------------------------------------------


@pytest.mark.parametrize(
    ("inner", "expected"),
    [
        ("Percent in tank: 61% <br>Last Reading: 11/15/2026", 61),
        ("Percent in tank: 0% Last Reading: 11/15/2026", 0),
        ("Percent in tank: 100% Last Reading: 11/15/2026", 100),
        ("Percent in tank: 61.9% Last Reading: 11/15/2026", 61),
        ("Percent in tank:61% Last Reading: 11/15/2026", 61),
        ("Percent&nbsp;in tank: 61% Last Reading: 11/15/2026", 61),
        ("percent IN tank : 61 % last reading: 11/15/2026", 61),
        ("Percent in tank: 150% Last Reading: 11/15/2026", None),
        ("Percent in tank: not a number Last Reading: 11/15/2026", None),
        ("Last Reading: 11/15/2026", None),
    ],
    ids=[
        "scrape_value",
        "zero",
        "full",
        "decimal_truncated",
        "no_space_after_colon",
        "non_breaking_space",
        "case_and_spacing",
        "out_of_range",
        "non_numeric",
        "missing_percent",
    ],
)
def test_percent_parsing(inner: str, expected: int | None) -> None:
    """The gauge percentage is read as a bounded integer between 0 and 100."""
    assert parse_tank_gauge(_gauge(inner))["percent_full"] == expected


@pytest.mark.parametrize(
    ("inner", "expected"),
    [
        ("Last Reading: 11/15/2026", date(2026, 11, 15)),
        ("Last Reading: 1/2/2026", date(2026, 1, 2)),
        ("Last Reading: 11/15/26", date(2026, 11, 15)),
        ("Last Reading: 11/15/99", date(1999, 11, 15)),
        ("Last Reading: 13/45/2026", None),
        ("Last Reading: 02/30/2026", None),
        ("Last Reading: pending", None),
    ],
    ids=[
        "scrape_value",
        "single_digit_month_and_day",
        "two_digit_year",
        "two_digit_year_last_century",
        "invalid_month_and_day",
        "invalid_day_for_month",
        "non_date",
    ],
)
def test_last_reading_date_parsing(inner: str, expected: date | None) -> None:
    """Last Reading dates are converted to date objects, invalid ones to None."""
    assert parse_tank_gauge(_gauge(inner))["last_reading"] == expected


# --- Delivery date and time parsing -------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("04/12/2026 4:00am", datetime(2026, 4, 12, 4, 0)),
        ("04/12/2026 4:00 am", datetime(2026, 4, 12, 4, 0)),
        ("04/12/2026 4:00AM", datetime(2026, 4, 12, 4, 0)),
        ("04/12/2026 12:00am", datetime(2026, 4, 12, 0, 0)),
        ("04/12/2026 12:30pm", datetime(2026, 4, 12, 12, 30)),
        ("04/12/2026 11:59pm", datetime(2026, 4, 12, 23, 59)),
        ("04/12/2026 16:45", datetime(2026, 4, 12, 16, 45)),
        ("04/12/2026", datetime(2026, 4, 12, 0, 0)),
        ("04/12/2026 25:00", datetime(2026, 4, 12, 0, 0)),
        ("04/12/2026 10:99", datetime(2026, 4, 12, 0, 0)),
        ("04/12/2026 pending", datetime(2026, 4, 12, 0, 0)),
        ("pending", None),
        ("13/45/2026 4:00am", None),
    ],
    ids=[
        "scrape_value",
        "space_before_meridiem",
        "uppercase_meridiem",
        "midnight_am",
        "noon_pm",
        "late_evening",
        "twenty_four_hour",
        "date_only",
        "hour_out_of_range",
        "minute_out_of_range",
        "unparseable_time",
        "unparseable_date",
        "invalid_date",
    ],
)
def test_delivery_datetime_parsing(value: str, expected: datetime | None) -> None:
    """Delivery values become naive datetimes, with midnight for absent times."""
    assert _delivery_date(value) == expected


# --- Numeric parsing -----------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("442.00", 442.0),
        ("442.00 L", 442.0),
        ("1,200.50", 1200.5),
        ("1,200.50 L", 1200.5),
        (" 442 ", 442.0),
        ("", None),
        ("n/a", None),
    ],
    ids=[
        "plain",
        "with_unit",
        "thousands_separator",
        "thousands_separator_with_unit",
        "padded",
        "empty",
        "no_number",
    ],
)
def test_litres_parsing(value: str, expected: float | None) -> None:
    """Litres tolerate unit suffixes and thousands separators."""
    assert _litres(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("$0.99", 0.99),
        ("0.99", 0.99),
        ("$1.05", 1.05),
        ("$1,234.56", 1234.56),
        ("  $ 0.99 / L", 0.99),
        ("free", None),
        ("", None),
    ],
    ids=[
        "scrape_value",
        "no_currency_symbol",
        "dollar",
        "thousands_separator",
        "unit_suffix",
        "non_numeric",
        "empty",
    ],
)
def test_price_parsing(value: str, expected: float | None) -> None:
    """Price values drop the currency symbol and parse as floats."""
    assert _price(value) == expected


# --- Table header/column mapping ----------------------------------------------

# The exact two row shape confirmed against the live portal on 2026-11-17.
LIVE_TABLE_HTML = """
<table class="table table-striped">
  <tr>
    <th data-field="Product Name">Product Name</th>
    <th data-field="Delivery Prov/State">Delivery Prov/State</th>
    <th data-field="Last Delivery Date">Last Delivery Date</th>
    <th data-field="Last Delivery Litres">Last Delivery Litres</th>
    <th data-field="Today's Price">Today's Price</th>
  </tr>
  <tr>
    <td>EC Propane</td>
    <td>PE</td>
    <td>04/12/2026 4:00am</td>
    <td>442.00</td>
    <td>$0.99</td>
  </tr>
</table>
"""


def test_plain_two_row_table_matches_live_snippet() -> None:
    """The header row is split from the data row exactly as the portal serves it."""
    assert parse_account_table(LIVE_TABLE_HTML) == {
        "last_delivery_date": EXPECTED_DELIVERY_DATE,
        "last_delivery_litres": EXPECTED_DELIVERY_LITRES,
        "todays_price": EXPECTED_PRICE,
    }


@pytest.mark.parametrize(
    "label",
    [
        "Last Delivery Date",
        "Last Delivery Date:",
        "last delivery date",
        "LAST DELIVERY DATE",
        "  Last   Delivery   Date  ",
    ],
    ids=["canonical", "trailing_colon", "lowercase", "uppercase", "extra_spaces"],
)
def test_delivery_date_header_matching(label: str) -> None:
    """Header lookup ignores case, padding, collapsed spaces, and a colon."""
    html = _single_column(label, "04/12/2026 4:00am")
    assert parse_account_table(html)["last_delivery_date"] == EXPECTED_DELIVERY_DATE


def test_us_liters_spelling_is_accepted() -> None:
    """The US spelling of litres is accepted for the same sensor."""
    html = _single_column("Last Delivery Liters", "442.00")
    assert parse_account_table(html)["last_delivery_litres"] == 442.0


def test_column_order_does_not_matter() -> None:
    """Values are read through the header map, so column order does not matter."""
    html = _column_table(
        ["Today's Price", "Last Delivery Litres", "Last Delivery Date"],
        ["$0.99", "442.00", "04/12/2026 4:00am"],
    )
    assert parse_account_table(html) == {
        "last_delivery_date": EXPECTED_DELIVERY_DATE,
        "last_delivery_litres": EXPECTED_DELIVERY_LITRES,
        "todays_price": EXPECTED_PRICE,
    }


def test_extra_columns_are_ignored() -> None:
    """Columns the integration does not need are skipped without side effects."""
    html = _column_table(
        [
            "Product Name",
            "Delivery Prov/State",
            "Tank Size",
            "Last Delivery Litres",
            "Notes",
        ],
        ["EC Propane", "PE", "500 USG", "442.00", "ignore me"],
    )
    assert parse_account_table(html) == {
        "last_delivery_date": None,
        "last_delivery_litres": 442.0,
        "todays_price": None,
    }


def test_missing_optional_columns_return_none() -> None:
    """A table that omits optional columns still yields the columns it has."""
    html = _single_column("Last Delivery Date", "04/12/2026 4:00am")
    assert parse_account_table(html) == {
        "last_delivery_date": EXPECTED_DELIVERY_DATE,
        "last_delivery_litres": None,
        "todays_price": None,
    }


def test_missing_data_row_returns_none_values() -> None:
    """A header row with no following data row yields Nones instead of raising."""
    html = _column_table(
        ["Last Delivery Date", "Last Delivery Litres", "Today's Price"], []
    )
    assert parse_account_table(html) == {
        "last_delivery_date": None,
        "last_delivery_litres": None,
        "todays_price": None,
    }


def test_short_data_row_returns_none_for_missing_cells() -> None:
    """A truncated data row only fills the columns it actually carries."""
    html = _column_table(
        ["Last Delivery Date", "Last Delivery Litres", "Today's Price"],
        ["04/12/2026 4:00am"],
    )
    assert parse_account_table(html) == {
        "last_delivery_date": EXPECTED_DELIVERY_DATE,
        "last_delivery_litres": None,
        "todays_price": None,
    }


def test_duplicate_header_columns_use_first_value() -> None:
    """A repeated header label keeps the first matching column, not the last."""
    html = _column_table(["Today's Price", "Today's Price"], ["$0.99", "$1.25"])
    assert parse_account_table(html)["todays_price"] == EXPECTED_PRICE


def test_unrelated_table_before_account_table_is_skipped() -> None:
    """A header naming no wanted field does not swallow the following table's row."""
    html = """
    <html><body>
    <table>
      <thead>
        <tr><th>Date</th><th>Product</th><th>Litres</th><th>Amount</th></tr>
      </thead>
      <tbody>
        <tr>
          <td>04/12/2026</td><td>EC Propane</td>
          <td>442.00</td><td>$437.58</td>
        </tr>
      </tbody>
    </table>
    <table>
      <thead>
        <tr>
          <th data-field="Last Delivery Date">Last Delivery Date</th>
          <th data-field="Today's Price">Today's Price</th>
        </tr>
      </thead>
      <tbody><tr><td>04/12/2026 4:00am</td><td>$0.99</td></tr></tbody>
    </table>
    </body></html>
    """
    assert parse_account_table(html) == {
        "last_delivery_date": EXPECTED_DELIVERY_DATE,
        "last_delivery_litres": None,
        "todays_price": EXPECTED_PRICE,
    }


def test_data_field_attribute_wins_over_header_text() -> None:
    """The stable data-field name is used when the visible header text differs."""
    html = """
    <html><body><table>
      <thead>
        <tr>
          <th data-field="Last Delivery Date"><div class="th-inner">Delivered</div></th>
          <th data-field="Today's Price"><span class="sort"></span>Rate</th>
        </tr>
      </thead>
      <tbody><tr><td>04/12/2026 4:00am</td><td>$0.99</td></tr></tbody>
    </table></body></html>
    """
    data = parse_user_home(html)
    assert data.last_delivery_date == EXPECTED_DELIVERY_DATE
    assert data.todays_price == EXPECTED_PRICE


def test_legacy_label_value_rows_still_parse() -> None:
    """The older label then value row layout remains a supported fallback."""
    html = _table(
        ("Product Name", "EC Propane"),
        ("Last Delivery Date", "04/12/2026 4:00am"),
        ("Last Delivery Litres", "442.00"),
        ("Today's Price", "$0.99"),
    )
    assert parse_account_table(html) == {
        "last_delivery_date": EXPECTED_DELIVERY_DATE,
        "last_delivery_litres": EXPECTED_DELIVERY_LITRES,
        "todays_price": EXPECTED_PRICE,
    }


def test_nested_markup_inside_cells_is_flattened() -> None:
    """Whitespace and inline tags inside header and data cells do not disturb extraction."""
    html = """
    <html><body><table>
      <thead>
        <tr>
          <th data-field="Last Delivery Date">Last <em>Delivery</em> Date</th>
          <th>Today&rsquo;s <em>Price</em></th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><span>04/12/2026</span> <strong>4:00am</strong></td>
          <td><span class="price">$0.99</span></td>
        </tr>
      </tbody>
    </table></body></html>
    """
    data = parse_user_home(html)
    assert data.last_delivery_date == EXPECTED_DELIVERY_DATE
    assert data.todays_price == EXPECTED_PRICE


# --- Login page detection ------------------------------------------------------

LOGIN_FORM_HTML = """
<html><body>
<form action="/index.php" method="post">
  <input type="hidden" name="csrf_token" value="token-abc123">
  <input type="text" name="email_check" value="">
  <input type="password" name="password_check" value="">
  <button type="submit" name="cmdLogin">Sign In</button>
</form>
</body></html>
"""


def test_is_login_page_detects_submit_button() -> None:
    """A form posting cmdLogin marks the response as the login page."""
    assert is_login_page(LOGIN_FORM_HTML) is True


def test_is_login_page_detects_csrf_only_form() -> None:
    """A csrf_token form without the gauge element also counts as login."""
    html = '<form><input type="hidden" name="csrf_token" value="x"></form>'
    assert is_login_page(html) is True


def test_is_login_page_false_for_account_page(user_home_html: str) -> None:
    """The account home page is not mistaken for the login page."""
    assert is_login_page(user_home_html) is False


def test_is_login_page_false_when_gauge_present() -> None:
    """A page carrying the gauge wins over any incidental form on the page."""
    html = LOGIN_FORM_HTML.replace(
        "</body>",
        '<div id="tank_gauge_summary">Percent in tank: 61%</div></body>',
    )
    assert is_login_page(html) is False


def test_is_login_page_false_for_empty_input() -> None:
    """Empty input is not a login page."""
    assert is_login_page("") is False


# --- Data model contract -------------------------------------------------------


def test_tank_data_is_frozen() -> None:
    """The snapshot handed to the coordinator cannot be mutated in place."""
    data = TankData(percent_full=61)
    with pytest.raises(FrozenInstanceError):
        data.percent_full = 10  # type: ignore[misc]


# --- Fixture scrub guarantees --------------------------------------------------


def test_fixture_uses_only_reserved_identifiers(user_home_html: str) -> None:
    """The committed fixture must not contain a real email, account, or phone."""
    emails = set(EMAIL_RE.findall(user_home_html))
    assert emails, "fixture should still exercise placeholder email markup"
    assert all(email.endswith("@example.com") for email in emails), emails
    assert not [e for e in emails if "irving" in e.lower()], emails
    for digits in LONG_DIGITS_RE.findall(user_home_html):
        assert set(digits) == {"0"}, f"non placeholder digit run: {digits}"


def test_fixture_keeps_obvious_placeholders(user_home_html: str) -> None:
    """Placeholder name, address, account number, and tank serial stay intact."""
    for placeholder in (
        "Jane Doe",
        "123 Example Street",
        "Account #: 0000000",
        "TANK-0000000",
        "(000) 000-0000",
    ):
        assert placeholder in user_home_html


def test_fixture_has_no_credential_fields(user_home_html: str) -> None:
    """A data page fixture carries no password input or login form field names."""
    lowered = user_home_html.lower()
    assert 'type="password"' not in lowered
    assert "password_check" not in lowered
    assert "email_check" not in lowered
    assert "<form" not in lowered


def test_fixture_contains_exactly_one_gauge_element(user_home_html: str) -> None:
    """The fixture keeps one summary element so parser expectations stay unambiguous."""
    assert user_home_html.count('id="tank_gauge_summary"') == 1


def test_gitignore_blocks_unscrubbed_fixture_drops() -> None:
    """Raw portal captures are gitignored so real account data cannot be committed."""
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "tests/fixtures/raw/" in gitignore
    assert "*.unscrubbed.html" in gitignore
