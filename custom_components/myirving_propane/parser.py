"""Pure HTML parsing helpers for the MyIrving account portal.

The portal only serves server rendered HTML, so every value is extracted with
BeautifulSoup and a small number of anchored regular expressions. Parsing never
raises for missing or malformed fields: it returns ``None`` and lets the
coordinator decide whether the page as a whole is usable.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
import re
from typing import TypedDict

from bs4 import BeautifulSoup
from bs4.element import Tag

from .const import (
    ACCOUNT_LABEL_DELIVERY_DATE,
    ACCOUNT_LABEL_DELIVERY_LITRES,
    ACCOUNT_LABEL_DELIVERY_LITRES_US,
    ACCOUNT_LABEL_TODAYS_PRICE,
    LOGIN_FIELD_PASSWORD,
    LOGIN_FIELD_SUBMIT,
    TANK_GAUGE_ID,
)

_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?", re.IGNORECASE)
_PERCENT_RE = re.compile(
    r"percent\s+in\s+tank\s*:?\s*(\d{1,3}(?:\.\d+)?)\s*%", re.IGNORECASE
)
_READING_RE = re.compile(
    r"last\s+reading\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})", re.IGNORECASE
)
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

_TWO_DIGIT_YEAR_PIVOT = 70


@dataclass(frozen=True, slots=True)
class TankData:
    """A snapshot of the tank values shown on the account home page."""

    percent_full: int | None = None
    last_reading: date | None = None
    last_delivery_date: datetime | None = None
    last_delivery_litres: float | None = None
    todays_price: float | None = None


class TankGaugeValues(TypedDict):
    """The two values carried by the tank gauge summary block."""

    percent_full: int | None
    last_reading: date | None


class AccountTableValues(TypedDict):
    """The delivery and price values carried by the account summary table."""

    last_delivery_date: datetime | None
    last_delivery_litres: float | None
    todays_price: float | None


def parse_tank_gauge(html: str | BeautifulSoup) -> TankGaugeValues:
    """Extract the fill percentage and last reading date from the gauge block."""
    return _parse_tank_gauge(to_soup(html))


def parse_account_table(html: str | BeautifulSoup) -> AccountTableValues:
    """Extract delivery and price values from the account summary table."""
    return _parse_account_table(to_soup(html))


def parse_user_home(html: str | BeautifulSoup) -> TankData:
    """Parse the /user-home page into a single immutable data snapshot."""
    soup = to_soup(html)
    gauge = _parse_tank_gauge(soup)
    account = _parse_account_table(soup)
    return TankData(
        percent_full=gauge["percent_full"],
        last_reading=gauge["last_reading"],
        last_delivery_date=account["last_delivery_date"],
        last_delivery_litres=account["last_delivery_litres"],
        todays_price=account["todays_price"],
    )


def is_login_page(html: str | BeautifulSoup) -> bool:
    """Return True when the page is the portal login page instead of account data."""
    soup = to_soup(html)
    if soup.find(id=TANK_GAUGE_ID) is not None:
        return False

    for form in soup.find_all("form"):
        names = {
            element.get("name")
            for element in form.find_all(["input", "button"])
            if element.get("name")
        }
        if LOGIN_FIELD_SUBMIT in names or LOGIN_FIELD_PASSWORD in names:
            return True
        if "csrf_token" in names:
            return True

    return False


def to_soup(html: str | BeautifulSoup) -> BeautifulSoup:
    """Return a BeautifulSoup tree, reusing an already parsed one.

    Callers that inspect several facts about one response can parse it once and
    hand the tree to every helper instead of re-parsing the same HTML string.
    """
    if isinstance(html, BeautifulSoup):
        return html
    return BeautifulSoup(html or "", "html.parser")


def _parse_tank_gauge(soup: BeautifulSoup) -> TankGaugeValues:
    """Read the gauge summary element and normalize its two values."""
    result: TankGaugeValues = {
        "percent_full": None,
        "last_reading": None,
    }

    gauge = soup.find(id=TANK_GAUGE_ID)
    if gauge is None:
        return result

    text = gauge.get_text(" ", strip=True)

    if (percent_match := _PERCENT_RE.search(text)) is not None:
        percent = int(float(percent_match.group(1)))
        if 0 <= percent <= 100:
            result["percent_full"] = percent

    if (reading_match := _READING_RE.search(text)) is not None:
        result["last_reading"] = _parse_date(reading_match.group(1))

    return result


def _parse_account_table(soup: BeautifulSoup) -> AccountTableValues:
    """Read the account summary table, preferring the live column layout.

    The portal renders the summary as a bootstrap table with a header row and a
    following data row. When that shape is not present the older label/value
    pair layout is still accepted so a portal restyle cannot silently blank
    every delivery sensor.
    """
    result: AccountTableValues = {
        "last_delivery_date": None,
        "last_delivery_litres": None,
        "todays_price": None,
    }

    if not _parse_account_columns(soup, result):
        _parse_account_pairs(soup, result)

    return result


def _parse_account_columns(soup: BeautifulSoup, result: AccountTableValues) -> bool:
    """Map header cells to column indexes and read the first following data row.

    Returns True when a header row naming at least one wanted field was found
    and a data row could be read, so the caller knows the primary layout
    applied and should not fall back to the label/value pair layout.
    """
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        index = 0
        while index < len(rows):
            if not _is_header_row(_row_cells(rows[index])):
                index += 1
                continue

            columns: dict[
                str, tuple[int, Callable[[str], datetime | float | None]]
            ] = {}
            while index < len(rows) and _is_header_row(_row_cells(rows[index])):
                _merge_header_columns(_row_cells(rows[index]), columns)
                index += 1

            if not columns:
                # A header for some other table (for example the delivery
                # history): keep scanning instead of reading its data row.
                continue

            data_row = _first_data_row(rows, index)
            if data_row is None:
                continue

            _apply_columns(columns, data_row, result)
            return True

    return False


def _parse_account_pairs(soup: BeautifulSoup, result: AccountTableValues) -> None:
    """Match known labels to the cell immediately to their right, row by row."""
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        for index, cell in enumerate(cells[:-1]):
            field = _LABEL_TO_FIELD.get(
                _normalize_label(cell.get_text(" ", strip=True))
            )
            if field is None or result[field[0]] is not None:
                continue
            value = field[1](cells[index + 1].get_text(" ", strip=True))
            if value is not None:
                result[field[0]] = value


def _row_cells(row: Tag) -> list[Tag]:
    """Return a row's own th/td cells, ignoring cells of nested tables."""
    return row.find_all(["td", "th"], recursive=False)


def _is_header_row(cells: list[Tag]) -> bool:
    """Return True for a row built only of th cells, the bootstrap header shape."""
    return bool(cells) and all(cell.name == "th" for cell in cells)


def _merge_header_columns(
    cells: list[Tag],
    columns: dict[str, tuple[int, Callable[[str], datetime | float | None]]],
) -> None:
    """Record the column index of every wanted field named by a header row.

    ``data-field`` wins over the visible text because the live table carries
    both and only the attribute is stable when labels gain sort icons or
    responsive wrappers. Repeated labels keep their first column.
    """
    for position, cell in enumerate(cells):
        raw_label = cell.get("data-field") or cell.get_text(" ", strip=True)
        field = _LABEL_TO_FIELD.get(_normalize_label(str(raw_label)))
        if field is not None and field[0] not in columns:
            columns[field[0]] = (position, field[1])


def _first_data_row(rows: list[Tag], start: int) -> list[Tag] | None:
    """Return the cells of the first non-header row at or after ``start``."""
    for row in rows[start:]:
        cells = _row_cells(row)
        if not cells:
            continue
        if _is_header_row(cells):
            return None
        return cells
    return None


def _apply_columns(
    columns: dict[str, tuple[int, Callable[[str], datetime | float | None]]],
    data_cells: list[Tag],
    result: AccountTableValues,
) -> None:
    """Read each wanted field from its column in the data row."""
    for field_name, (position, parse) in columns.items():
        if position >= len(data_cells):
            continue
        value = parse(data_cells[position].get_text(" ", strip=True))
        if value is not None:
            result[field_name] = value


def _parse_delivery_datetime(value: str) -> datetime | None:
    """Parse a MM/DD/YYYY delivery value with an optional 12 or 24 hour time."""
    parsed_date = _parse_date(value)
    if parsed_date is None:
        return None

    time_match = _TIME_RE.search(value)
    if time_match is None:
        return datetime.combine(parsed_date, time())

    hour = int(time_match.group(1))
    minute = int(time_match.group(2))
    meridiem = (time_match.group(3) or "").lower().replace(".", "")

    if minute > 59:
        return datetime.combine(parsed_date, time())
    if meridiem:
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    if hour > 23:
        return datetime.combine(parsed_date, time())

    return datetime.combine(parsed_date, time(hour, minute))


def _parse_date(value: str) -> date | None:
    """Parse the first MM/DD/YYYY date found in a value into a date object."""
    match = _DATE_RE.search(value)
    if match is None:
        return None

    month, day, raw_year = (int(part) for part in match.groups())
    year = _normalize_year(raw_year)

    try:
        return date(year, month, day)
    except ValueError:
        return None


def _normalize_year(year: int) -> int:
    """Expand a two digit year so values such as 26 become 2026."""
    if year >= 100:
        return year
    if year < _TWO_DIGIT_YEAR_PIVOT:
        return 2000 + year
    return 1900 + year


def _parse_number(value: str) -> float | None:
    """Return the first number in a value, ignoring currency and unit text."""
    match = _NUMBER_RE.search(value)
    if match is None:
        return None

    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def _normalize_label(value: str) -> str:
    """Lowercase a table label, normalize quotes and drop trailing punctuation."""
    normalized = value.replace("\u2019", "'").replace("\u2018", "'")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.rstrip(":").strip().lower()


_LABEL_TO_FIELD: dict[str, tuple[str, Callable[[str], datetime | float | None]]] = {
    ACCOUNT_LABEL_DELIVERY_DATE: ("last_delivery_date", _parse_delivery_datetime),
    ACCOUNT_LABEL_DELIVERY_LITRES: ("last_delivery_litres", _parse_number),
    ACCOUNT_LABEL_DELIVERY_LITRES_US: ("last_delivery_litres", _parse_number),
    ACCOUNT_LABEL_TODAYS_PRICE: ("todays_price", _parse_number),
}
